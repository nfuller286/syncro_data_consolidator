import requests
import json
import os
from typing import Any, Dict, Optional
from datetime import datetime, timezone, timedelta

from sdc.utils.sdc_logger import get_sdc_logger
from sdc.utils.cuis_handler import save_cuis_to_file
from sdc.models.cuis_v1 import CUISV1, CuisEntry
from sdc.utils.date_utils import parse_datetime_utc

STATE_FILE_NAME = 'syncro_ticket_ingestor_state.json'

def _get_file_metadata(file_path: str) -> Dict[str, Any]:
    try:
        stat = os.stat(file_path)
        return {'size': stat.st_size, 'mtime': stat.st_mtime}
    except FileNotFoundError:
        return {}

def _load_ingestor_state(config: Dict[str, Any], logger) -> Dict[str, Any]:
    state_file_path = os.path.join(config['project_paths']['cache_folder'], STATE_FILE_NAME)
    try:
        with open(state_file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logger.info(f"Ingestor state file not found or invalid at {state_file_path}. Starting fresh.")
        return {'files': {}, 'api': {}}

def _save_ingestor_state(state: Dict[str, Any], config: Dict[str, Any], logger) -> None:
    state_file_path = os.path.join(config['project_paths']['cache_folder'], STATE_FILE_NAME)
    try:
        os.makedirs(os.path.dirname(state_file_path), exist_ok=True)
        with open(state_file_path, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=4)
    except IOError as e:
        logger.error(f"Failed to save ingestor state to {state_file_path}: {e}")

def _fetch_all_pages(base_url: str, headers: Dict[str, str], params: Dict[str, Any], logger) -> list:
    all_tickets = []
    page = 1
    while True:
        params['page'] = page
        try:
            response = requests.get(base_url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            tickets = data.get('tickets', [])
            all_tickets.extend(tickets)
            logger.info(f"Fetched page {page}, received {len(tickets)} tickets.")
            meta = data.get('meta', {})
            if page >= meta.get('total_pages', 1):
                break
            page += 1
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching page {page} of Syncro tickets: {e}")
            break
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from page {page}: {e}")
            break
    return all_tickets

def ingest_syncro_tickets(config: Dict[str, Any]) -> None:
    logger = get_sdc_logger(__name__, config)
    logger.info("Starting Syncro Ticket Ingestor...")

    api_config = config.get('syncro_api', {})
    test_file_path = api_config.get('test_file_path')

    tickets_data = []
    ingestor_state = _load_ingestor_state(config, logger)
    processed_successfully = True

    if test_file_path:
        logger.info(f"Processing Syncro tickets from test file: {test_file_path}")
        try:
            current_metadata = _get_file_metadata(test_file_path)
            if ingestor_state.get('files', {}).get(test_file_path) == current_metadata:
                logger.info(f"Test file '{test_file_path}' unchanged. Skipping re-ingestion.")
                return

            with open(test_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                tickets_data = data.get('tickets', [])
            
            ingestor_state.setdefault('files', {})[test_file_path] = current_metadata
            logger.info(f"Loaded {len(tickets_data)} tickets from test file.")

        except FileNotFoundError:
            logger.error(f"Test file not found: {test_file_path}")
            processed_successfully = False
            return
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from test file: {test_file_path}")
            processed_successfully = False
            return
    else:
        api_key = api_config.get('api_key')
        base_url = api_config.get('base_url')
        tickets_endpoint = api_config.get('tickets_endpoint', '/tickets')

        if not api_key or not base_url:
            logger.error("Syncro API key or base URL not found. Aborting.")
            return

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        full_url = f"{base_url.rstrip('/')}{tickets_endpoint}"
        params = {}

        last_updated_at_str = ingestor_state.get('api', {}).get('last_updated_at')
        if last_updated_at_str:
            params['since_updated_at'] = last_updated_at_str
            logger.info(f"Fetching tickets updated since: {last_updated_at_str}")
        else:
            # New logic for initial fetch: only get tickets from the last 6 months (180 days)
            six_months_ago = datetime.now(timezone.utc) - timedelta(days=180)
            created_after_str = six_months_ago.strftime('%Y-%m-%dT%H:%M:%SZ')
            params['created_after'] = created_after_str
            logger.info(f"No previous timestamp found. Performing initial fetch for tickets created after: {created_after_str}")

        tickets_data = _fetch_all_pages(full_url, headers, params, logger)

    last_updated_at_from_state = None
    if not test_file_path and last_updated_at_str:
        try:
            last_updated_at_from_state = parse_datetime_utc(last_updated_at_str, config)
        except (ValueError, TypeError):
            logger.warning(f"Could not parse timestamp from state file: {last_updated_at_str}")

    if last_updated_at_from_state:
        original_count = len(tickets_data)
        tickets_data = [t for t in tickets_data if parse_datetime_utc(t.get('updated_at'), config) > last_updated_at_from_state]
        logger.info(f"Client-side filtering reduced ticket count from {original_count} to {len(tickets_data)} based on timestamp {last_updated_at_str}.")

    if not tickets_data:
        logger.info("No new tickets to process.")
        _save_ingestor_state(ingestor_state, config, logger)
        return

    latest_timestamp_this_run = last_updated_at_from_state
    processed_count, error_count = 0, 0

    for ticket in tickets_data:
        try:
            updated_at_str = ticket.get('updated_at')
            current_ts = parse_datetime_utc(updated_at_str, config)
            if latest_timestamp_this_run is None or current_ts > latest_timestamp_this_run:
                latest_timestamp_this_run = current_ts
            
            cuis_item = CUISV1()
            cuis_item.sdc_core.sdc_source_system = "SyncroRMM"
            cuis_item.sdc_core.sdc_source_sub_type = "Syncro_Ticket"
            cuis_item.sdc_core.sdc_source_primary_id = str(ticket['id'])
            cuis_item.core_content.summary_title_or_subject = ticket.get('subject')
            cuis_item.core_content.creation_timestamp_utc = parse_datetime_utc(ticket.get('created_at'), config)
            cuis_item.core_content.source_data_updated_at_timestamp_utc = current_ts

            # Populate entities_involved
            cuis_item.entities_involved.syncro_customer_name_guessed = ticket.get('customer_business_then_name')
            cuis_item.entities_involved.syncro_contact_name_guessed = ticket.get('contact_fullname')
            cuis_item.entities_involved.primary_actor_user_name_source = ticket.get('creator_name_or_email')

            # Populate source_specific_details
            details = {
                'syncro_ticket_number': ticket.get('number'),
                'syncro_problem_type': ticket.get('problem_type'),
                'syncro_status': ticket.get('status'),
                'syncro_billing_status': ticket.get('billing_status'),
                'syncro_total_formatted_billable_time': ticket.get('total_formatted_billable_time'),
                'syncro_priority': ticket.get('priority'),
                'syncro_tag_list': ticket.get('tag_list', [])
            }
            cuis_item.source_specific_details = {k: v for k, v in details.items() if v is not None}

            # Process comments to create CuisEntry objects
            if 'comments' in ticket and ticket['comments']:
                for comment in ticket['comments']:
                    entry = CuisEntry()
                    entry.entry_id_source = str(comment.get('id'))
                    entry.entry_timestamp_utc = parse_datetime_utc(comment.get('created_at'), config)
                    entry.entry_author_name_source = comment.get('user_name')
                    entry.entry_body_text = comment.get('body')
                    entry.entry_type_source = 'Ticket_Comment'

                    # Deduce the entry type based on available metadata
                    if comment.get('sms_body'):
                        entry.entry_type_deduced = 'SMS'
                    elif comment.get('subject') or comment.get('destination_emails') or comment.get('email_sender'):
                        entry.entry_type_deduced = 'Email'
                    elif comment.get('hidden') is True:
                        entry.entry_type_deduced = 'Private Note'
                    else:
                        entry.entry_type_deduced = 'Public Note'
                    
                    cuis_item.cuis_entries.append(entry)

            save_cuis_to_file(cuis_item, config, logger)
            processed_count += 1
        except Exception as e:
            logger.error(f"Error processing Syncro ticket ID {ticket.get('id', 'N/A')}: {e}", exc_info=True)
            error_count += 1
            processed_successfully = False

    logger.info(f"Syncro Ticket Ingestor finished. Processed: {processed_count}, Errors: {error_count}")

    if error_count > 0:
        logger.warning("Errors occurred during processing. State will not be updated.")
        return

    if processed_successfully and not test_file_path and latest_timestamp_this_run:
        final_timestamp = latest_timestamp_this_run + timedelta(seconds=1)
        ingestor_state['api']['last_updated_at'] = final_timestamp.strftime('%Y-%m-%dT%H:%M:%SZ')
        logger.info(f"Updating last_updated_at timestamp to: {ingestor_state['api']['last_updated_at']}")
        _save_ingestor_state(ingestor_state, config, logger)
