
import os
import sys
import json
import shutil
import zipfile
import tempfile

# --- Configuration ---
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")
SAMPLE_CONFIG_PATH = os.path.join(CONFIG_DIR, "sampleconfig.json")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
TEST_DATA_ARCHIVE = os.path.join(PROJECT_ROOT, "dev docs", "test_data.zip")

def setup_config():
    """
    Creates config.json from sampleconfig.json if it doesn't exist.
    """
    if os.path.exists(CONFIG_PATH):
        print("Configuration file already exists.")
        return

    print("Configuration file not found. Creating from sample...")
    try:
        shutil.copy(SAMPLE_CONFIG_PATH, CONFIG_PATH)
        print(f"Successfully created {CONFIG_PATH}")
        print("!!! ACTION REQUIRED: Please edit config.json to add your API keys and other required values. !!!")
    except FileNotFoundError:
        print(f"FATAL: {SAMPLE_CONFIG_PATH} not found. Cannot create configuration.")
        sys.exit(1)
    except Exception as e:
        print(f"FATAL: An error occurred while creating the config file: {e}")
        sys.exit(1)

def create_directories():
    """
    Creates the directory structure specified in config.json.
    """
    print("\nCreating data directories...")
    try:
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)

        # --- Robust Placeholder Resolution ---
        templates = config.get('project_paths', {})
        if not templates:
            print("WARNING: No 'project_paths' found in config.json. Cannot create directories.")
            return
            
        templates['project_root'] = PROJECT_ROOT

        for _ in range(5):  # Limit iterations to prevent infinite loops
            made_replacement = False
            for key, value in templates.items():
                if isinstance(value, str):
                    new_value = value
                    for placeholder, replacement in templates.items():
                        if f'{{{{{placeholder}}}}}' in new_value and placeholder != key:
                            new_value = new_value.replace(f'{{{{{placeholder}}}}}', str(replacement))
                            made_replacement = True
                    templates[key] = new_value
            if not made_replacement:
                break

        # --- Directory Creation ---
        for key, path in templates.items():
            if key == 'project_root':
                continue

            path = os.path.normpath(path)

            if os.path.splitext(path)[1]:
                dir_to_create = os.path.dirname(path)
            else:
                dir_to_create = path
            
            if not os.path.exists(dir_to_create):
                os.makedirs(dir_to_create, exist_ok=True)
                print(f"  - Created: {dir_to_create}")
            else:
                print(f"  - Exists:  {dir_to_create}")
        print("Directory setup complete.")

    except FileNotFoundError:
        print(f"FATAL: {CONFIG_PATH} not found. Run setup without flags first.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"FATAL: Could not parse {CONFIG_PATH}. Please ensure it is valid JSON.")
        sys.exit(1)
    except Exception as e:
        print(f"FATAL: An error occurred during directory creation: {e}")
        sys.exit(1)

def install_test_data():
    """
    Installs test data from a zip archive by extracting to a temp directory
    and merging the contents into the correct final destinations.
    """
    print("\nAttempting to install test data...")
    
    if not os.path.exists(TEST_DATA_ARCHIVE):
        print("-------")
        print("INFO: Test data archive not found.")
        print(f"To install test data, please place your data archive at the following location:")
        print(f"  -> {TEST_DATA_ARCHIVE}")
        print("-------")
        return

    try:
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
        
        # --- Resolve Destination Paths ---
        templates = config.get('project_paths', {})
        templates['project_root'] = PROJECT_ROOT
        for _ in range(5): # Multi-pass placeholder resolution
            made_replacement = False
            for key, value in templates.items():
                if isinstance(value, str):
                    new_value = value
                    for placeholder, replacement in templates.items():
                        if f'{{{{{placeholder}}}}}' in new_value and placeholder != key:
                            new_value = new_value.replace(f'{{{{{placeholder}}}}}', str(replacement))
                            made_replacement = True
                    templates[key] = new_value
            if not made_replacement:
                break
        
        final_input_dest = os.path.normpath(templates.get('input_folder', ''))
        final_cache_dest = os.path.normpath(templates.get('cache_folder', ''))

        if not all([final_input_dest, final_cache_dest]):
            raise KeyError("Could not resolve 'input_folder' or 'cache_folder' from config.")

        # --- Extraction and Merging ---
        with tempfile.TemporaryDirectory() as temp_dir:
            print(f"Extracting archive to temporary location...")
            with zipfile.ZipFile(TEST_DATA_ARCHIVE, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            # Define source directories from the extracted archive
            temp_input_src = os.path.join(temp_dir, 'input')
            temp_cache_src = os.path.join(temp_dir, 'cache')

            # Move/merge the contents
            if os.path.isdir(temp_input_src):
                print(f"Merging test 'input' data into {final_input_dest}...")
                shutil.copytree(temp_input_src, final_input_dest, dirs_exist_ok=True)

            if os.path.isdir(temp_cache_src):
                print(f"Merging test 'cache' data into {final_cache_dest}...")
                shutil.copytree(temp_cache_src, final_cache_dest, dirs_exist_ok=True)

            print("Test data successfully installed.")

    except FileNotFoundError:
         print(f"FATAL: Could not find {CONFIG_PATH} or one of its parent directories.")
         sys.exit(1)
    except KeyError as e:
        print(f"FATAL: {e}")
        sys.exit(1)
    except zipfile.BadZipFile:
        print(f"FATAL: The file at {TEST_DATA_ARCHIVE} is not a valid zip file.")
        sys.exit(1)
    except Exception as e:
        print(f"FATAL: An error occurred during test data installation: {e}")
        sys.exit(1)

def main():
    """
    Main function to run setup tasks.
    """
    print("--- SDC Project Initial Setup ---")
    
    # Core setup tasks
    setup_config()
    create_directories()

    # Always ask about test data
    try:
        response = input("\nDo you want to install the test data? (y/n): ").lower()
        if response == 'y':
            install_test_data()
        else:
            print("Skipping test data installation.")
    except (KeyboardInterrupt, EOFError):
        print("\n\nSetup aborted by user. Skipping test data installation.")
    
    print("\n--- Setup Complete ---")



if __name__ == "__main__":
    main()
