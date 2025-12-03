# -*- coding: utf-8 -*-
"""
A developer tool to rebuild the entire SQLite index from session files.
"""

import os
import sys
import glob
import logging

# --- Setup sys.path to find the 'sdc' module ---
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# --- Imports from your project ---
try:
    from sdc.utils.config_loader import load_config
    from sdc.utils.sqlite_indexer import SessionDatabaseManager
    from sdc.utils.session_handler import load_session_from_file
    from sdc.utils.sdc_logger import get_sdc_logger
except ImportError as e:
    print(f"Failed to import project modules. Ensure you are running this from the project root directory.")
    print(f"Error: {e}")
    sys.exit(1)

def main():
    """Main execution function to rebuild the index."""
    
    # 1. Setup: Load Config and Logger
    config = load_config()
    if not config:
        print("Configuration could not be loaded. Exiting.")
        return
        
    logger = get_sdc_logger(__name__, config)
    logger.info("--- Starting SQLite Index Rebuild ---")

    try:
        db_path = config['project_paths']['database_file']
        sessions_folder = config['project_paths']['sessions_output_folder']
    except KeyError as e:
        logger.critical(f"Configuration key missing: {e}. Aborting index rebuild.")
        return

    # 2. Init SessionDatabaseManager
    logger.info(f"Initializing database manager for: {db_path}")
    manager = SessionDatabaseManager(db_path, logger)

    # 3. Run manager.init_schema()
    logger.info("Initializing database schema...")
    manager.init_schema()

    # 4. Traverse sessions_output_folder
    session_files = glob.glob(os.path.join(sessions_folder, '*.json'))
    total_files = len(session_files)
    logger.info(f"Found {total_files} session files to process in '{sessions_folder}'.")

    # 5. For each .json file, load and upsert
    for i, file_path in enumerate(session_files):
        try:
            logger.info(f"Processing file {i+1}/{total_files}: {os.path.basename(file_path)}")
            session = load_session_from_file(file_path, logger)
            if session:
                manager.upsert_session(session)
            else:
                logger.warning(f"Could not load session from file: {file_path}")
        except Exception as e:
            logger.error(f"Failed to process file {file_path}: {e}", exc_info=True)

    logger.info("--- Index rebuild complete. Running verification query. ---")

    # Step 5: Verification Query
    try:
        # Test: Count segments where metadata indicates it's a user message.
        # This is a simple but effective way to verify that the metadata column is being populated.
        cursor = manager.conn.execute("""
            SELECT COUNT(*) FROM segments WHERE metadata LIKE '%"is_user": true%'
        """)
        # fetchone() will return a tuple like (count,)
        result = cursor.fetchone()
        count = result[0] if result else 0
        
        print("\n--- Verification Query Results ---")
        print(f"Found {count} segments where 'is_user' is true.")
        print("--------------------------------\n")
        
    except Exception as e:
        logger.error(f"Verification query failed: {e}", exc_info=True)
    finally:
        # Clean up
        manager.close()
        logger.info("--- Rebuild script finished. ---")

if __name__ == "__main__":
    main()
