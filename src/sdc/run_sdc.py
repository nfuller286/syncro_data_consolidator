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
from sdc.processors.session_llm_analyzer import analyze_sessions_with_llm # V2 analyzer


def main():
    """Main entry point for the SDC application."""
    # --- Configuration and Logging Setup ---
    config = load_config()
    if not config:
        print("FATAL: Configuration could not be loaded. Exiting.")
        return

    logger = get_sdc_logger('run_sdc', config)
    logger.info("SDC application starting.")

    # --- Argument Parsing Setup ---
    parser = argparse.ArgumentParser(description="Syncro Data Consolidator (SDC) CLI", formatter_class=argparse.RawTextHelpFormatter)
    subparsers = parser.add_subparsers(dest='command', required=True, help='Available commands')

    # 'ingest' command
    parser_ingest = subparsers.add_parser('ingest', help='Run a specific data ingestor')
    parser_ingest.add_argument('--source', required=True, choices=['all', 'sillytavern', 'syncro', 'notes', 'screenconnect'], help='The data source to ingest')

    # 'process' command
    parser_process = subparsers.add_parser('process', help='Run a specific processing step')
    parser_process.add_argument('--step', required=True, choices=['all', 'customer_linking', 'llm_analysis'], help='The processing step to run')

    # 'run' command
    parser_run = subparsers.add_parser('run', help='Run a predefined pipeline')
    parser_run.add_argument('--pipeline', required=True, choices=['full', 'ingest_only'], help='The pipeline to execute')

    # 'cache' command
    parser_cache = subparsers.add_parser('cache', help='Manage data caches')
    parser_cache.add_argument('--source', required=True, choices=['syncro'], help='The data source to cache')

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
        'llm_analysis': partial(analyze_sessions_with_llm, config, logger)
    }
    
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
            # 1. Cache
            logger.info("Caching Syncro data...")
            cache_syncro_data(config, logger)
            # 2. Ingest All
            for source, func in ingest_map.items():
                logger.info(f"Ingesting from {source}...")
                func()
            # 3. Process (V2) - This is now an explicit step.
            # The user should run 'process --step all' or a specific step after ingestion.
            logger.info("Full ingestion pipeline complete. Run the 'process' command to link customers or perform LLM analysis.")

    logger.info("SDC application finished.")

if __name__ == '__main__':
    main()