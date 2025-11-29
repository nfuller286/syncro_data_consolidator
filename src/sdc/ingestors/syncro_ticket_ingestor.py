import os
import json
from typing import Dict, Any
from datetime import datetime, timezone, timedelta
from sdc.api_clients.syncro_gateway import SyncroGateway
from sdc.utils.sdc_logger import get_sdc_logger
# --- V2 IMPORTS ---
from sdc.models.session_v2 import Session, SessionSegment, SessionMeta, SessionContext, SessionInsights
from sdc.utils.session_handler import save_session_to_file
from sdc.utils.date_utils import parse_datetime_utc
from sdc.utils.session_builder import build_session
from sdc.utils import file_ingestor_state_handler as state_handler

STATE_FILE_NAME = 'syncro_ticket_ingestor_state.json'

def ingest_syncro_tickets(config: Dict[str, Any], logger) -> None:
    logger.info("Starting Syncro Ticket Ingestor...")

    api_config = config.get('syncro_api', {})
    syncro_test_ticket_file = api_config.get('syncro_test_ticket_file')

    tickets_data = []
    state_file_path = os.path.join(config['project_paths']['cache_folder'], STATE_FILE_NAME)
    # The default state ensures 'files' and 'api' keys always exist.
    default_state = {'files': {}, 'api': {}}
    ingestor_state = state_handler.load_state(state_file_path, logger, default_state=default_state)

    processed_successfully = True
    state_needs_saving = False  # Flag to track if we need to save state at the end
    last_updated_at_str = None  # Initialize to handle unbound variable case

    if syncro_test_ticket_file:
        logger.info(f"Processing Syncro tickets from test file: {syncro_test_ticket_file}")
        try:
            current_metadata = state_handler.get_file_metadata(syncro_test_ticket_file)
            if ingestor_state.get('files', {}).get(syncro_test_ticket_file) == current_metadata:
                logger.info(f"Test file '{syncro_test_ticket_file}' unchanged. Skipping re-ingestion.")
                return

            with open(syncro_test_ticket_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                tickets_data = data.get('tickets', [])

            ingestor_state['files'][syncro_test_ticket_file] = current_metadata
            state_needs_saving = True  # We will process this file, so state should be saved on success
            logger.info(f"Loaded {len(tickets_data)} tickets from test file.")

        except FileNotFoundError:
            logger.error(f"Test file not found: {syncro_test_ticket_file}")
            processed_successfully = False
            return
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from test file: {syncro_test_ticket_file}")
            processed_successfully = False
            return
    else:
        try:
            gateway = SyncroGateway(config, logger)
            params = {}
            last_updated_at_str = ingestor_state['api'].get('last_updated_at')
            if last_updated_at_str:
                params['since_updated_at'] = last_updated_at_str
                logger.info(f"Fetching tickets updated since: {last_updated_at_str}")
            else:
                # New logic for initial fetch: only get tickets from the last 6 months (180 days)
                six_months_ago = datetime.now(timezone.utc) - timedelta(days=180)
                created_after_str = six_months_ago.strftime('%Y-%m-%dT%H:%M:%SZ')
                params['created_after'] = created_after_str
                logger.info(f"No previous timestamp found. Performing initial fetch for tickets created after: {created_after_str}")

            tickets_data = gateway.fetch_tickets(**params)
            if tickets_data is None:
                logger.error("Ticket fetching failed. The gateway returned None.")
                tickets_data = [] # Ensure tickets_data is an iterable to prevent downstream errors

        except KeyError:
            logger.critical("Aborting ticket ingestion due to Syncro Gateway initialization failure.")
            return
