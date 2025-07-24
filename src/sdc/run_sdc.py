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

# CHANGED: Import both the V1 and V2 linkers
from sdc.processors.cuis_customer_linker import link_customers_to_cuis
from sdc.processors.session_customer_linker import link_customers_to_sessions


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
    # CHANGED: Added 'session_linking' to the available choices
    parser_process.add_argument('--step', required=True, choices=['all', 'customer_linking', 'session_customer_linking'], help='The processing step to run')

    # 'run' command
    parser_run = subparsers.add_parser('run', help='Run a predefined pipeline')
    # CHANGED: Added 'full_v2' pipeline option
    parser_run.add_argument('--pipeline', required=True, choices=['full', 'full_v2', 'ingest_only'], help='The pipeline to execute')

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
        # CHANGED: Updated logic to handle both V1 and V2 linkers.
        # The 'all' option will now run both.
        if args.step in ['customer_linking', 'all']:
            logger.info("Running V1 CUIS Customer Linker...")
            link_customers_to_cuis(config, logger)
        if args.step in ['session_customer_linking', 'all']:
            logger.info("Running V2 Session Customer Linker...")
            link_customers_to_sessions(config, logger)
        

    elif args.command == 'run':
        if args.pipeline == 'ingest_only':
            logger.info("Executing 'ingest_only' pipeline...")
            ingest_syncro_tickets(config)
            ingest_sillytavern_chats(config, logger)
            ingest_notes(config)
            ingest_screenconnect(config)
        elif args.pipeline == 'full':
            # CHANGED: Clarified this is the V1 pipeline
            logger.info("Executing 'full' V1 pipeline...")
            # 1. Cache
            cache_syncro_data(config, logger)
            # 2. Ingest All
            ingest_syncro_tickets(config)
            ingest_sillytavern_chats(config, logger)
            ingest_notes(config)
            ingest_screenconnect(config)
            # 3. Process (V1)
            link_customers_to_cuis(config, logger)
            
        # ADDED: New V2 pipeline definition
        elif args.pipeline == 'full_v2':
            logger.info("Executing 'full' V2 pipeline...")
            # 1. Cache (re-used)
            cache_syncro_data(config, logger)
            # 2. Ingest All (these now produce V2 Session files)
            ingest_syncro_tickets(config)
            ingest_sillytavern_chats(config, logger)
            ingest_notes(config)
            ingest_screenconnect(config)
            # 3. Process (V2)
            link_customers_to_sessions(config, logger)

    logger.info("SDC application finished.")

if __name__ == '__main__':
    main()