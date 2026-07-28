import os
import json
import uuid
from typing import Dict, Any, List
from datetime import datetime, timezone, timedelta
from sdc.api_clients.syncro_gateway import SyncroGateway
# --- V2 IMPORTS ---
from sdc.models.session_v2 import Session, SessionSegment, SessionMeta, SessionContext, SessionInsights
from sdc.utils.session_handler import save_session_to_file
from sdc.utils.date_utils import parse_datetime_utc
from sdc.utils.session_builder import build_session
from sdc.utils import file_ingestor_state_handler as state_handler

STATE_FILE_NAME = 'syncro_ticket_ingestor_state.json'

def ingest_syncro_tickets(config: Dict[str, Any], logger, **kwargs) -> None:
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

    if not tickets_data:
        logger.info("No new tickets to process.")
        return

    latest_timestamp_this_run = None
    processed_count, error_count = 0, 0

    for ticket in tickets_data:
        try:
            updated_at_str = ticket.get('updated_at')
            current_ts = parse_datetime_utc(updated_at_str, config)

            # Track the latest update timestamp seen this run (successes and
            # failures alike) so the watermark still advances even if some
            # tickets fail to parse below.
            if current_ts:
                if latest_timestamp_this_run is None or current_ts > latest_timestamp_this_run:
                    latest_timestamp_this_run = current_ts

            # --- V2 Session Creation Logic ---
            segments: List[SessionSegment] = []
            ticket_creation_time = parse_datetime_utc(ticket.get('created_at'), config)
            if not ticket_creation_time:
                logger.warning(f"Skipping ticket ID {ticket.get('id')} due to missing or invalid creation date.")
                error_count += 1
                continue

            # Create the first segment for the ticket creation event itself
            segments.append(SessionSegment(
                segment_id=str(uuid.uuid4()),
                start_time_utc=ticket_creation_time,
                end_time_utc=ticket_creation_time,
                type="TicketCreation",
                author=ticket.get('creator_name_or_email'),
                content=ticket.get('subject'),
                metadata={
                    'syncro_ticket_number': ticket.get('number'),
                    'syncro_problem_type': ticket.get('problem_type'),
                    'syncro_status': ticket.get('status'),
                    'syncro_priority': ticket.get('priority'),
                    'syncro_tag_list': ticket.get('tag_list', [])
                }
            ))

            # Create a segment for each comment
            if ticket.get('comments'):
                for comment in ticket['comments']:
                    # Deduce the entry type based on available metadata
                    if comment.get('sms_body'):
                        segment_type = 'SMS'
                    elif comment.get('subject') or comment.get('destination_emails') or comment.get('email_sender'):
                        segment_type = 'Email'
                    elif comment.get('hidden') is True:
                        segment_type = 'PrivateNote'
                    else:
                        segment_type = 'PublicNote'

                    comment_time = parse_datetime_utc(comment.get('created_at'), config) or ticket_creation_time
                    segments.append(SessionSegment(
                        segment_id=str(uuid.uuid4()),
                        start_time_utc=comment_time,
                        end_time_utc=comment_time,
                        type=segment_type,
                        author=comment.get('user_name'),
                        content=comment.get('body'),
                        metadata={
                            'syncro_comment_id': comment.get('id'),
                            'syncro_user_id': comment.get('user_id')
                        }
                    ))

            # Use the session builder to construct the final object
            session_object = build_session(
                segments=segments,
                source_system="SyncroRMM",
                source_identifiers=[f"/tickets/{ticket.get('id')}"],
                customer_name=ticket.get('customer_business_then_name'),
                contact_name=ticket.get('contact_fullname'),
                customer_id=ticket.get('customer_id'),
                contact_id=ticket.get('contact_id'),
                source_title=ticket.get('subject'),
                processing_status="Linked"  # Pre-linked since Syncro provides IDs
            )

            save_session_to_file(session_object, config, logger)
            processed_count += 1
        except Exception as e:
            logger.error(f"Error processing Syncro ticket ID {ticket.get('id', 'N/A')}: {e}", exc_info=True)
            error_count += 1

    logger.info(f"Syncro Ticket Ingestor finished. Processed: {processed_count}, Errors: {error_count}")

    if error_count > 0:
        logger.warning(
            f"{error_count} ticket(s) failed to process this run and were skipped. "
            "The state watermark still advances past this batch (below) so the "
            "tickets that succeeded aren't reprocessed and duplicated on the next "
            "run; failed tickets will not be retried automatically."
        )

    # If it was an API run, update the timestamp. This advances regardless of
    # per-ticket errors above: successfully processed tickets are already
    # saved, and a ticket that failed to parse will fail identically on every
    # retry, so gating the whole batch's progress on it would just cause the
    # successful tickets to be reprocessed (and duplicated — session IDs are
    # randomly generated with no dedup) every run.
    if not syncro_test_ticket_file and latest_timestamp_this_run:
        final_timestamp = latest_timestamp_this_run + timedelta(seconds=1)
        ingestor_state['api']['last_updated_at'] = final_timestamp.strftime('%Y-%m-%dT%H:%M:%SZ')
        logger.info(f"Updating last_updated_at timestamp to: {ingestor_state['api']['last_updated_at']}")
        state_needs_saving = True

    if state_needs_saving:
        logger.info("Saving updated ingestor state.")
        state_handler.save_state(ingestor_state, state_file_path, logger)
