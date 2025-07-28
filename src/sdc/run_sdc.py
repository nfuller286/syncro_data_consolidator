# -*- coding: utf-8 -*-
"""Master orchestrator for the Syncro Data Consolidator (SDC) project."""

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
    parser = argparse.ArgumentParser(description="Syncro Data Consolidator (SDC) CLI")
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

    if args.command == 'cache':
        if args.source == 'syncro':
            cache_syncro_data(config, logger)

    elif args.command == 'ingest':
        if args.source in ['syncro', 'all']:
            ingest_syncro_tickets(config)
        if args.source in ['sillytavern', 'all']:
            ingest_sillytavern_chats(config, logger)
        if args.source in ['notes', 'all']:
            ingest_notes(config)
        if args.source in ['screenconnect', 'all']:
            ingest_screenconnect(config)

    elif args.command == 'process':
        if args.step in ['customer_linking', 'all']:
            logger.info("Running Session Customer Linker...")
            link_customers_to_sessions(config, logger)
        if args.step in ['llm_analysis', 'all']:
            logger.info("Running Session LLM Analyzer...")
            analyze_sessions_with_llm(config, logger)

    elif args.command == 'run':
        if args.pipeline == 'ingest_only':
            logger.info("Executing 'ingest_only' pipeline...")
            ingest_syncro_tickets(config)
            ingest_sillytavern_chats(config, logger)
            ingest_notes(config)
            ingest_screenconnect(config)
        elif args.pipeline == 'full':
            logger.info("Executing 'full' pipeline...")
            # 1. Cache
            cache_syncro_data(config, logger)
            # 2. Ingest All
            ingest_syncro_tickets(config)
            ingest_sillytavern_chats(config, logger)
            ingest_notes(config)
            ingest_screenconnect(config)
            # 3. Process (V2)
            link_customers_to_sessions(config, logger)
            analyze_sessions_with_llm(config, logger)

    logger.info("SDC application finished.")

if __name__ == '__main__':
    main()