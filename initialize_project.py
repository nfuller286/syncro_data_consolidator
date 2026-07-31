import os
import sys
import shutil
import zipfile
import tempfile
import argparse
import time

import yaml

# --- Configuration ---
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")
SAMPLE_CONFIG_PATH = os.path.join(CONFIG_DIR, "sampleconfig.yaml")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.yaml")
TEST_DATA_ARCHIVE = os.path.join(PROJECT_ROOT, "dev docs", "test_data.zip")

sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))
from sdc.utils.config_loader import load_yaml_config, resolve_project_paths

def contains_files(path):
    """
    True if the directory tree holds at least one actual file.

    A plain os.scandir() check is not enough here: create_directories() makes
    the input/cache subfolder skeleton up front, so a freshly initialised (and
    genuinely empty) project would otherwise look like it already had data.
    """
    if not os.path.isdir(path):
        return False
    for _root, _dirs, files in os.walk(path):
        if files:
            return True
    return False

def setup_config():
    """
    Creates config.yaml from sampleconfig.yaml if it doesn't exist.
    Returns True if the file was created, False if it already existed.
    """
    if os.path.exists(CONFIG_PATH):
        print("Configuration file already exists.")
        return False

    print("Configuration file not found. Creating from sample...")
    try:
        shutil.copy(SAMPLE_CONFIG_PATH, CONFIG_PATH)
        print(f"Successfully created {CONFIG_PATH}")
        print("!!! ACTION REQUIRED: Please edit config.yaml to add your API keys and other required values. !!!")
        return True
    except FileNotFoundError:
        print(f"FATAL: {SAMPLE_CONFIG_PATH} not found. Cannot create configuration.")
        sys.exit(1)
    except Exception as e:
        print(f"FATAL: An error occurred while creating the config file: {e}")
        sys.exit(1)

def create_directories(config):
    """
    Creates the directory structure specified in config.yaml.
    """
    print("\nCreating data directories...")
    try:
        project_paths = config.get('project_paths', {})
        if not project_paths:
            print("WARNING: No 'project_paths' found in config.yaml. Cannot create directories.")
            return

        templates = resolve_project_paths(PROJECT_ROOT, project_paths)

        for key, path in templates.items():
            if key == 'project_root': continue
            path = os.path.normpath(path)
            dir_to_create = os.path.dirname(path) if os.path.splitext(path)[1] else path

            if not os.path.exists(dir_to_create):
                os.makedirs(dir_to_create, exist_ok=True)
                print(f"  - Created: {dir_to_create}")
            else:
                print(f"  - Exists:  {dir_to_create}")
        print("Directory setup complete.")

    except Exception as e:
        print(f"FATAL: An error occurred during directory creation: {e}")
        sys.exit(1)

def install_test_data(config):
    """
    Installs test data from a zip archive, with safeguards against overwriting.
    """
    print("\nAttempting to install test data...")
    if not os.path.exists(TEST_DATA_ARCHIVE):
        print(f"INFO: Test data archive not found at {TEST_DATA_ARCHIVE}")
        return

    try:
        templates = resolve_project_paths(PROJECT_ROOT, config.get('project_paths', {}))
        final_input_dest = os.path.normpath(templates.get('input_folder', ''))
        final_cache_dest = os.path.normpath(templates.get('cache_folder', ''))

        if not all([final_input_dest, final_cache_dest]):
            raise KeyError("Could not resolve 'input_folder' or 'cache_folder' from config.")

        # Safeguard against overwriting existing data
        if contains_files(final_input_dest):
            print(f"WARNING: Input directory '{final_input_dest}' is not empty.")
            if sys.stdin.isatty():
                # isatty() can still be True where stdin yields EOF immediately
                # (some CI runners, tool harnesses). Decline rather than crash.
                try:
                    confirm = input("Proceeding will merge and potentially overwrite existing files. Continue? [y/N]: ").lower()
                except (EOFError, KeyboardInterrupt):
                    print("\nNo confirmation received. Test data installation aborted.")
                    return
                if confirm != 'y':
                    print("Test data installation aborted by user.")
                    return
            else:
                print("Running in a non-interactive environment. Aborting to prevent accidental data loss.")
                print("To install test data into a non-empty directory, first clear it using:")
                print("  python initialize_project.py --reset input --yes")
                return

        with tempfile.TemporaryDirectory() as temp_dir:
            print("Extracting archive...")
            with zipfile.ZipFile(TEST_DATA_ARCHIVE, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            for src_sub, dest_path in [('input', final_input_dest), ('cache', final_cache_dest)]:
                temp_src = os.path.join(temp_dir, src_sub)
                if os.path.isdir(temp_src):
                    print(f"Merging test '{src_sub}' data into {dest_path}...")
                    shutil.copytree(temp_src, dest_path, dirs_exist_ok=True)
            print("Test data successfully installed.")

    except Exception as e:
        print(f"FATAL: An error occurred during test data installation: {e}")
        sys.exit(1)

def check_status():
    """Checks and reports on the project's initialization status."""
    print("--- Project Initialization Status ---")

    config_exists = os.path.exists(CONFIG_PATH)
    print(f"\nConfig:\n  - config.yaml exists: {'yes' if config_exists else 'no'}")
    if not config_exists:
        print("\nProject is not initialized. Run `python initialize_project.py` to get started.")
        return

    try:
        config = load_yaml_config(CONFIG_PATH)
        paths = resolve_project_paths(PROJECT_ROOT, config.get('project_paths', {}))

        dir_statuses = {}
        # NOTE: the logs path key is 'logs_folder' (see config/sampleconfig.yaml),
        # not 'log_folder' - using the wrong key silently falls back to '' ->
        # os.path.normpath('') == '.', reporting on the current working
        # directory instead of the actual logs folder.
        for name, key in [('Input', 'input_folder'), ('Output', 'sessions_output_folder'), ('Cache', 'cache_folder'), ('Logs', 'logs_folder')]:
            path = os.path.normpath(paths.get(key, ''))
            exists = os.path.isdir(path)
            dir_statuses[name] = {'path': path, 'exists': exists, 'contains_files': contains_files(path)}

        for name, status in dir_statuses.items():
            print(f"\n{name} data (at {status['path']}):")
            print(f"  - Directory exists: {'yes' if status['exists'] else 'no'}")
            if status['exists']:
                print(f"  - Contains files: {'yes' if status['contains_files'] else 'no'}")

    except Exception as e:
        print(f"\nCould not read directory status. Error: {e}")

def handle_reset(targets, is_confirmed):
    """Handles the logic for resetting parts of the project."""
    print("--- Project Reset ---")

    try:
        config = load_yaml_config(CONFIG_PATH)
        paths = resolve_project_paths(PROJECT_ROOT, config.get('project_paths', {}))
    except Exception as e:
        print(f"FATAL: Could not load configuration to determine paths for reset. Error: {e}")
        return

    # NOTE: the logs path key is 'logs_folder' (see config/sampleconfig.yaml),
    # not 'log_folder' - the wrong key returns None here with no default,
    # which crashes os.path.normpath() below on every --reset call.
    path_map = {
        'input': os.path.normpath(paths.get('input_folder')),
        'output': os.path.normpath(paths.get('sessions_output_folder')),
        'cache': os.path.normpath(paths.get('cache_folder')),
        'logs': os.path.normpath(paths.get('logs_folder'))
    }

    if 'all' in targets:
        targets_to_reset = ['input', 'output', 'cache']
        if 'logs' in targets:
            targets_to_reset.append('logs')
    else:
        targets_to_reset = targets if targets else []

    paths_to_clear = {path_map[t] for t in targets_to_reset if t in path_map}

    if not paths_to_clear:
        print("No valid reset targets specified. Use 'input', 'output', 'cache', 'logs', or 'all'.")
        return

    print("The following directories will be CLEARED:")
    for path in sorted(paths_to_clear):
        print(f"  - {path}")

    if not is_confirmed:
        try:
            confirm = input("\nAre you sure you want to proceed? [y/N]: ").lower()
        except (EOFError, KeyboardInterrupt):
            print("\nNo confirmation received. Reset aborted.")
            return
        if confirm != 'y':
            print("Reset aborted.")
            return

    print("\nProceeding with reset...")
    for path in paths_to_clear:
        if os.path.isdir(path):
            try:
                shutil.rmtree(path)
                os.makedirs(path)
                print(f"  - Cleared and recreated: {path}")
            except Exception as e:
                print(f"  - ERROR clearing {path}: {e}")
        else:
            print(f"  - Skipping (does not exist): {path}")
    print("\nReset complete.")


def input_with_timeout(prompt, timeout=5):
    """Cross-platform input with a timeout."""
    if sys.platform == 'win32':
        import msvcrt
        print(prompt, end=f" (you have {timeout} seconds) [y/n]: ", flush=True)
        start_time = time.time()
        line = ""
        while time.time() - start_time < timeout:
            if msvcrt.kbhit():
                char = msvcrt.getwche()
                if char in '\r\n': print(); return line
                line += char
            time.sleep(0.05)
        print(); return None
    else:
        import select
        print(prompt, end=f" (you have {timeout} seconds) [y/n]: ", flush=True)
        rlist, _, _ = select.select([sys.stdin], [], [], timeout)
        if rlist: return sys.stdin.readline().strip()
        else: print(); return None

def main():
    """Main function to run setup, status, or reset tasks."""
    parser = argparse.ArgumentParser(
        description="SDC project initialization and management script.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--status', action='store_true', help='Check and report the project initialization status.')
    group.add_argument('--reset', nargs='*', choices=['input', 'output', 'cache', 'logs', 'all'], help='Reset specified parts of the project. Can be combined with --install-test-data.')

    parser.add_argument('--install-test-data', action='store_true', help='Install test data. Can be run alone or after a reset.')
    parser.add_argument('--yes', action='store_true', help='Bypass confirmation prompts for reset operations.')

    args = parser.parse_args()

    if args.status:
        check_status()
        return

    if args.reset is not None:
        handle_reset(args.reset, args.yes)
        if args.install_test_data:
            print("\n--- Installing Test Data ---")
            try:
                config = load_yaml_config(CONFIG_PATH)
                install_test_data(config)
            except Exception as e:
                print(f"FATAL: Could not load config to install test data. Error: {e}")
        return

    if args.install_test_data:
        print("--- Installing Test Data ---")
        try:
            config = load_yaml_config(CONFIG_PATH)
            install_test_data(config)
        except Exception as e:
            print(f"FATAL: Could not load config to install test data. Has the project been initialized? Error: {e}")
        return

    # --- Default Initialization Flow (no flags given) ---
    print("--- SDC Project Initial Setup ---")
    config_created = setup_config()
    try:
        config = load_yaml_config(CONFIG_PATH)
        create_directories(config)
    except Exception as e:
        print(f"FATAL: Could not load config to create directories. Error: {e}")
        sys.exit(1)

    # Only prompt on a fresh setup
    if config_created and sys.stdin.isatty():
        response = input_with_timeout("\nDo you want to install the test data?", timeout=5)
        if response is not None and response.lower() == 'y':
            install_test_data(config)
        elif response is None:
            print("No response received after 5 seconds. Continuing without test data.\n")
            print("For headless setup, use: python initialize_project.py --install-test-data")
        else:
            print("Skipping test data installation.")
    elif config_created:
        print("\nNon-interactive environment. Skipping test data prompt. Use --install-test-data to install.")

    print("\n--- Setup Complete ---")

if __name__ == "__main__":
    main()
