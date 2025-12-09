# -*- coding: utf-8 -*-
"""Master orchestrator for the Syncro Data Consolidator (SDC) project."""

from functools import partial
import argparse

# Import project utilities
from sdc.utils.config_loader import load_config
from sdc.utils.sdc_logger import get_sdc_logger

# Import all required functions from other modules
from sdc.ingestors.syncro_customer_contact_cacher import cache_syncro_data
from sdc.ingestors.notes_json_ingestor import ingest_notes
from sdc.ingestors.screenconnect_log_ingestor import ingest_screenconnect
from sdc.ingestors.st_chat_ingestor import ingest_sillytavern_chats
from sdc.ingestors.syncro_ticket_ingestor import ingest_syncro_tickets

# Import the session-based customer linker
from sdc.processors.session_customer_linker import link_customers_to_sessions # V2 linker
from sdc.processors.session_llm_analyzer import run_llm_analysis # V2 analyzer
from sdc.utils.workspace_cleaner import clean_workspace, SOURCE_MAPPING


def main():
    """Main entry point for the SDC application."""
    # --- Configuration and Logging Setup ---
    config = load_config()
    if not config:
        print("FATAL: Configuration could not be loaded. Exiting.")
        return

    logger = get_sdc_logger('run_sdc', config)
    logger.info("SDC application starting.")

    # --- Dynamically build process steps from LLM configs ---
    llm_analysis_tasks = config.get('llm_configs', {}).get('analysis_tasks', {})
    llm_task_keys = list(llm_analysis_tasks.keys())

    # --- Argument Parsing Setup ---
    parser = argparse.ArgumentParser(description="Syncro Data Consolidator (SDC) CLI", formatter_class=argparse.RawTextHelpFormatter)
    subparsers = parser.add_subparsers(dest='command', required=True, help='Available commands')

    # 'ingest' command
    parser_ingest = subparsers.add_parser('ingest', help='Run a specific data ingestor')
    parser_ingest.add_argument('--source', required=True, choices=['all', 'sillytavern', 'syncro', 'notes', 'screenconnect'], help='The data source to ingest')

    # 'process' command
    parser_process = subparsers.add_parser('process', help='Run a specific processing step')
    valid_process_steps = ['all', 'customer_linking'] + llm_task_keys
    parser_process.add_argument('--step', required=True, choices=valid_process_steps, help='The processing step to run')

    # 'run' command
    parser_run = subparsers.add_parser('run', help='Run a predefined pipeline')
    parser_run.add_argument('--pipeline', required=True, choices=['full', 'ingest_only'], help='The pipeline to execute')

    # 'cache' command
    parser_cache = subparsers.add_parser('cache', help='Manage data caches')
    parser_cache.add_argument('--source', required=True, choices=['syncro'], help='The data source to cache')

    # 'clean' command
    valid_clean_targets = list(SOURCE_MAPPING.keys()) + ['all', 'logs']
    parser_clean = subparsers.add_parser('clean', help='Clean workspace by deleting files for specified sources (e.g., screenconnect syncro).')
    parser_clean.add_argument('sources', nargs='+', choices=valid_clean_targets, help='One or more sources to clean. Use "all" to clean all sources and logs.')
    parser_clean.add_argument('--commit', action='store_true', help='Perform the actual deletion. Without this flag, a dry run is performed.')

    # 'query' command
    parser_query = subparsers.add_parser('query', help='Run a natural language query against the data')
    parser_query.add_argument('natural_language_query', help='The natural language query to run')

    args = parser.parse_args()

    # --- Command Execution Logic ---
    logger.info(f"Executing command: {args.command} with arguments: {vars(args)}")
    
    # Using partial to create function objects with pre-filled arguments
    # This standardizes the function signatures for easier calling.
    ingest_map = {
        'syncro': partial(ingest_syncro_tickets, config, logger),
        'sillytavern': partial(ingest_sillytavern_chats, config, logger),
        'notes': partial(ingest_notes, config, logger),
        'screenconnect': partial(ingest_screenconnect, config, logger)
    }
    
    process_map = {
        'customer_linking': partial(link_customers_to_sessions, config, logger),
    }
    # Dynamically add LLM analysis tasks to the process map
    for task_key in llm_task_keys:
        process_map[task_key] = partial(run_llm_analysis, config, logger, analysis_type=task_key)
    
    if args.command == 'cache':
        if args.source == 'syncro':
            cache_syncro_data(config, logger)

    elif args.command == 'ingest':
        sources_to_run = ingest_map.keys() if args.source == 'all' else [args.source]
        for source in sources_to_run:
            if source in ingest_map:
                logger.info(f"Ingesting from {source}...")
                ingest_map[source]()

    elif args.command == 'process':
        steps_to_run = process_map.keys() if args.step == 'all' else [args.step]
        for step in steps_to_run:
            if step in process_map:
                logger.info(f"Running processing step: {step}...")
                process_map[step]()

    elif args.command == 'run':
        if args.pipeline == 'ingest_only':
            logger.info("Executing 'ingest_only' pipeline...")
            for source, func in ingest_map.items():
                logger.info(f"Ingesting from {source}...")
                func()

        elif args.pipeline == 'full':
            logger.info("Executing 'full' pipeline...")
            
            # Check if we are in a test file mode for Syncro
            syncro_test_mode = config.get('syncro_api', {}).get('syncro_test_ticket_file')

            if not syncro_test_mode:
                # 1. Cache (only if not in test mode)
                logger.info("Caching Syncro data...")
                cache_syncro_data(config, logger)
            else:
                logger.info("Syncro test file path is configured. Skipping live data caching.")

            # 2. Ingest All
            for source, func in ingest_map.items():
                logger.info(f"Ingesting from {source}...")
                func()

            # 3. Automated Processing
            logger.info("--- Starting Automated Processing ---")
            
            # Run the customer linker to link all newly ingested sessions.
            logger.info("Running Customer Linker...")
            process_map['customer_linking']()

            logger.info("--- Full pipeline complete. ---")
            logger.info("NOTE: LLM analysis for titles/summaries must be run separately using the 'process' command (e.g., 'process --step llm_title').")

    elif args.command == 'clean':
        # Determine if this is a dry run based on the ABSENCE of --commit
        is_dry_run = not args.commit

        # The dangerous interactive confirmation prompt ONLY appears if we are committing changes.
        if not is_dry_run:
            confirm_sources = ' '.join(args.sources)
            confirm = input(f"WARNING: This will permanently delete files for source(s): '{confirm_sources}'. Are you sure? [y/N] ")
            if confirm.lower() != 'y':
                logger.info("Cleanup aborted by user.")
                return

        # Separate 'logs' from the other sources, as it's handled by a separate flag.
        # The cleaner utility handles the 'all' keyword for sources.
        sources_to_clean = [s for s in args.sources if s != 'logs']
        should_clean_logs = 'logs' in args.sources or 'all' in args.sources

        # Call the new, safer utility function
        clean_workspace(
            sources=sources_to_clean,
            clean_logs=should_clean_logs,
            config=config,
            logger=logger,
            dry_run=is_dry_run
        )
    
    elif args.command == 'query':
        from sdc.agent.executor import run_query
        logger.info(f"Running query: {args.natural_language_query}")
        result = run_query(args.natural_language_query)
        print(result)

    logger.info("SDC application finished.")

if __name__ == '__main__':
    main()