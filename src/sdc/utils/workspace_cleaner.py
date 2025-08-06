# -*- coding: utf-8 -*-
"""Utility for cleaning the workspace by deleting generated files."""

import os
import glob
from typing import List, Dict, Any

# This mapping is the single source of truth for which files belong to which ingestor.
SOURCE_MAPPING = {
    'screenconnect': {
        'state_file': 'screenconnect_log_ingestor_state.json',
        'session_pattern': '*_ScreenConnect_*.json',
        'display_name': 'ScreenConnect'
    },
    'sillytavern': {
        'state_file': 'st_chat_ingestor_file_state.json',
        'session_pattern': '*_SillyTavern_*.json',
        'display_name': 'SillyTavern'
    },
    'syncro': {
        'state_file': 'syncro_ticket_ingestor_state.json',
        'session_pattern': '*_SyncroRMM_*.json',
        'display_name': 'SyncroRMM'
    },
    'notes': {
        'state_file': 'notes_json_ingestor_state.json',
        # The session handler sanitizes 'notes.json' to 'notes_json' in filenames
        'session_pattern': '*_notes_json_*.json',
        'display_name': 'Notes.json'
    }
}

def _find_and_delete_files(
    patterns_and_dirs: List[tuple[str, str]],
    logger,
    dry_run: bool
) -> int:
    """Finds files across multiple directories and patterns, then deletes them, returning the count."""
    all_files_to_delete = []
    for pattern, directory in patterns_and_dirs:
        search_path = os.path.join(directory, pattern)
        try:
            found_files = glob.glob(search_path)
            all_files_to_delete.extend(found_files)
        except Exception as e:
            logger.error(f"Error searching for files with pattern '{pattern}' in '{directory}': {e}")
            continue  # Move to the next pattern
    
    if not all_files_to_delete:
        return 0

    if dry_run:
        for f in all_files_to_delete:
            logger.info(f"  - [DRY RUN] Would delete: {f}")
    else:
        deleted_count = 0
        for f in all_files_to_delete:
            try:
                os.remove(f)
                logger.info(f"  - Deleted {os.path.basename(f)}")
                deleted_count += 1
            except OSError as e:
                logger.error(f"  - Failed to delete {os.path.basename(f)}: {e}")
        return deleted_count
    
    return len(all_files_to_delete)

def clean_workspace(sources: List[str], clean_logs: bool, config: Dict[str, Any], logger, dry_run: bool):
    """
    Cleans the workspace by deleting generated files for specified sources.
    This is an all-or-nothing operation per source, deleting both session
    and state files to maintain consistency.
    """
    sessions_dir = config['project_paths']['sessions_output_folder']
    cache_dir = config['project_paths']['cache_folder']
    logs_dir = config['project_paths']['logs_folder']

    sources_to_clean = set(SOURCE_MAPPING.keys()) if 'all' in sources else set(sources)

    for source in sources_to_clean:
        if source not in SOURCE_MAPPING:
            logger.warning(f"Unknown source '{source}' specified for cleaning. Skipping.")
            continue

        source_config = SOURCE_MAPPING[source]
        display_name = source_config['display_name']
        logger.info(f"Cleaning all data for source: {display_name}...")
        
        files_to_find = [
            (source_config['session_pattern'], sessions_dir),
            (source_config['state_file'], cache_dir)
        ]
        deleted_count = _find_and_delete_files(files_to_find, logger, dry_run)

        if dry_run:
            logger.info(f"[DRY RUN] Found {deleted_count} session/state file(s) to delete for {display_name}.")
        else:
            logger.info(f"Successfully deleted {deleted_count} session/state file(s) for {display_name}.")
        logger.info("NOTE: This does not delete raw cache files (e.g., customer/contact cache).")

    if clean_logs:
        logger.info("Cleaning Log files...")
        deleted_count = _find_and_delete_files([("*.log", logs_dir)], logger, dry_run)
        if dry_run:
            logger.info(f"[DRY RUN] Found {deleted_count} log file(s) to delete.")
        else:
            logger.info(f"Successfully deleted {deleted_count} log file(s).")