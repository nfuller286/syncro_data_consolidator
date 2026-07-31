# -*- coding: utf-8 -*-
"""Master orchestrator for the Syncro Data Consolidator (SDC) project."""

from functools import partial
import argparse
import sys

# Import project utilities needed for argument parsing. The ingestor/processor
# modules pull in heavy dependencies (langchain, google-auth, etc.) and are
# imported lazily inside each command branch below instead, so `--help` and
# argument-parsing errors return immediately instead of paying that cost.
from sdc.utils.config_loader import load_config
from sdc.utils.sdc_logger import get_sdc_logger
from sdc.utils.workspace_cleaner import SOURCE_MAPPING


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
    parser.add_argument('--list-commands', action='store_true', help='Print a detailed list of all available commands and exit.')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # 'ingest' command
    parser_ingest = subparsers.add_parser('ingest', help='Run a specific data ingestor')
    ingest_sources = ['all', 'sillytavern', 'syncro', 'notes', 'screenconnect']
    parser_ingest.add_argument('--source', required=True, choices=ingest_sources, help='The data source to ingest')
    parser_ingest.add_argument('--start-date', help='ScreenConnect only: the start date for fetching data via the API (YYYY-MM-DD). Overrides saved state.')
    parser_ingest.add_argument('--end-date', help='ScreenConnect only: the end date for fetching data via the API (YYYY-MM-DD).')
    parser_ingest.add_argument(
        '--show-filters',
        action='store_true',
        help='ScreenConnect only: display the available filter keys and exit.'
    )
    parser_ingest.add_argument(
        '--filter',
        action='append',
        dest='filters',
        help="ScreenConnect only: add a key=value filter. Can be specified multiple times (e.g., --filter ParticipantName=TechName)."
    )

    # 'process' command
    parser_process = subparsers.add_parser('process', help='Run a specific processing step')
    valid_process_steps = ['all', 'customer_linking'] + llm_task_keys
    parser_process.add_argument('--step', required=True, choices=valid_process_steps, help='The processing step to run')
    parser_process.add_argument(
        '--retry',
        action='store_true',
        help=(
            "Also re-process sessions that previously reached a terminal non-success\n"
            "state for this step. For customer_linking that means sessions marked\n"
            "'No Match Found' or 'Linking Failed'; for LLM steps it means sessions\n"
            "marked as analysed but holding no usable output."
        )
    )

    # 'run' command
    parser_run = subparsers.add_parser('run', help='Run a predefined pipeline')
    run_pipelines = ['full', 'ingest_only']
    parser_run.add_argument('--pipeline', required=True, choices=run_pipelines, help='The pipeline to execute')

    # 'cache' command
    parser_cache = subparsers.add_parser('cache', help='Manage data caches')
    cache_sources = ['syncro']
    parser_cache.add_argument('--source', required=True, choices=cache_sources, help='The data source to cache')

    # 'clean' command
    valid_clean_targets = list(SOURCE_MAPPING.keys()) + ['all', 'logs']
    parser_clean = subparsers.add_parser('clean', help='Clean workspace by deleting files for specified sources (e.g., screenconnect syncro).')
    parser_clean.add_argument('sources', nargs='+', choices=valid_clean_targets, help='One or more sources to clean. Use "all" to clean all sources and logs.')
    parser_clean.add_argument('--commit', action='store_true', help='Perform the actual deletion. Without this flag, a dry run is performed.')

    args = parser.parse_args()

    # --- Pre-computation for command listing ---
    if args.list_commands:
        print("Available SDC commands:\n")

        # Ingest
        print("ingest")
        for source in sorted([s for s in ingest_sources if s != 'all']):
            print(f"  python -m sdc.run_sdc ingest --source {source}")
        print()

        # Process
        print("process")
        for step in sorted(valid_process_steps):
            if step != 'all':
                print(f"  python -m sdc.run_sdc process --step {step}")
        print()

        # Run
        print("run")
        for pipeline in sorted(run_pipelines):
            print(f"  python -m sdc.run_sdc run --pipeline {pipeline}")
        print()

        # Cache
        print("cache")
        for source in sorted(cache_sources):
            print(f"  python -m sdc.run_sdc cache --source {source}")
        print()

        # Clean
        print("clean")
        for target in sorted([t for t in valid_clean_targets if t not in ['all', 'logs']]):
            print(f"  python -m sdc.run_sdc clean {target}")
        print("  python -m sdc.run_sdc clean all")
        print()
        return

    # --- Handle no command ---
    if not args.command:
        print("No command provided.\n")
        print("Syncro Data Consolidator (SDC) CLI")
        print(f"usage: {sys.argv[0]} [-h] {{ingest,process,run,cache,clean}} ...\n")
        print("Available commands:")
        for cmd in sorted(subparsers.choices.keys()):
            print(f"  {cmd}")
        print("\nRun `python -m sdc.run_sdc <command> -h` for more details.")
        return

    if args.command == 'ingest':
        # start_date/end_date/filters/show_filters only have defined behavior for
        # ScreenConnect (the only connector with a queryable API to filter against;
        # the others rely on incremental state tracking instead). Reject them
        # explicitly elsewhere rather than silently accepting and ignoring them.
        screenconnect_only_flags_used = args.start_date or args.end_date or args.filters or args.show_filters
        if screenconnect_only_flags_used and args.source != 'screenconnect':
            parser.error(
                "--start-date, --end-date, --filter, and --show-filters are only supported "
                "with --source screenconnect."
            )

        if args.show_filters:
            from sdc.utils.constants import SCREENCONNECT_QUERY_FIELDS
            print("Available filter keys for ScreenConnect:")
            for field in sorted(SCREENCONNECT_QUERY_FIELDS):
                print(f"- {field}")
            return # Exit the program

    # --- Command Execution Logic ---
    logger.info(f"Executing command: {args.command} with arguments: {vars(args)}")

    if args.command == 'cache':
        from sdc.ingestors.syncro_customer_contact_cacher import cache_syncro_data
        if args.source == 'syncro':
            cache_syncro_data(config, logger)

    elif args.command == 'ingest':
        from sdc.ingestors.notes_json_ingestor import ingest_notes
        from sdc.ingestors.screenconnect_log_ingestor import ingest_screenconnect
        from sdc.ingestors.st_chat_ingestor import ingest_sillytavern_chats
        from sdc.ingestors.syncro_ticket_ingestor import ingest_syncro_tickets

        # Using partial to create function objects with pre-filled arguments.
        # This standardizes the function signatures for easier calling.
        ingest_map = {
            'syncro': partial(ingest_syncro_tickets, config, logger),
            'sillytavern': partial(ingest_sillytavern_chats, config, logger),
            'notes': partial(ingest_notes, config, logger),
            'screenconnect': partial(ingest_screenconnect, config, logger)
        }

        sources_to_run = ingest_map.keys() if args.source == 'all' else [args.source]
        for source in sources_to_run:
            if source in ingest_map:
                logger.info(f"Ingesting from {source}...")
                # Build a dictionary of optional arguments
                ingest_kwargs = {
                    'start_date': args.start_date,
                    'end_date': args.end_date,
                    'filters': args.filters or []
                }
                # Call the ingestor, unpacking the kwargs. This works for ALL ingestors.
                ingest_map[source](**ingest_kwargs)

    elif args.command == 'process':
        from sdc.processors.session_customer_linker import link_customers_to_sessions # V2 linker
        from sdc.processors.session_llm_analyzer import run_llm_analysis # V2 analyzer

        process_map = {
            'customer_linking': partial(link_customers_to_sessions, config, logger, retry=args.retry),
        }
        # Dynamically add LLM analysis tasks to the process map
        for task_key in llm_task_keys:
            process_map[task_key] = partial(run_llm_analysis, config, logger, analysis_type=task_key, retry=args.retry)

        steps_to_run = process_map.keys() if args.step == 'all' else [args.step]
        for step in steps_to_run:
            if step in process_map:
                logger.info(f"Running processing step: {step}...")
                process_map[step]()

    elif args.command == 'run':
        # The 'run' pipelines only ever use the customer-linking processing
        # step (see NOTE below), not LLM analysis, so session_llm_analyzer
        # (and the langchain dependencies it pulls in) is never imported here.
        from sdc.ingestors.syncro_customer_contact_cacher import cache_syncro_data
        from sdc.ingestors.notes_json_ingestor import ingest_notes
        from sdc.ingestors.screenconnect_log_ingestor import ingest_screenconnect
        from sdc.ingestors.st_chat_ingestor import ingest_sillytavern_chats
        from sdc.ingestors.syncro_ticket_ingestor import ingest_syncro_tickets
        from sdc.processors.session_customer_linker import link_customers_to_sessions # V2 linker

        ingest_map = {
            'syncro': partial(ingest_syncro_tickets, config, logger),
            'sillytavern': partial(ingest_sillytavern_chats, config, logger),
            'notes': partial(ingest_notes, config, logger),
            'screenconnect': partial(ingest_screenconnect, config, logger)
        }

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
            link_customers_to_sessions(config, logger)

            logger.info("--- Full pipeline complete. ---")
            logger.info("NOTE: LLM analysis for titles/summaries must be run separately using the 'process' command (e.g., 'process --step title').")

    elif args.command == 'clean':
        from sdc.utils.workspace_cleaner import clean_workspace

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

    logger.info("SDC application finished.")

if __name__ == '__main__':
    main()