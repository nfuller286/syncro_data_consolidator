import pandas as pd
import os
import json
from typing import Any, Dict, List
from datetime import timedelta

from sdc.models.cuis_v1 import CUISV1, CuisEntry
from sdc.utils.cuis_handler import save_cuis_to_file
from sdc.utils.date_utils import parse_datetime_utc
from sdc.utils.sdc_logger import get_sdc_logger

STATE_FILE_NAME = 'screenconnect_log_ingestor_state.json'
SESSION_WINDOW_MINUTES = 30

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
        logger.info(f"State file not found or invalid at {state_file_path}. Starting fresh.")
        return {}

def _save_ingestor_state(state: Dict[str, Any], config: Dict[str, Any], logger) -> None:
    state_file_path = os.path.join(config['project_paths']['cache_folder'], STATE_FILE_NAME)
    try:
        os.makedirs(os.path.dirname(state_file_path), exist_ok=True)
        with open(state_file_path, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=4)
    except IOError as e:
        logger.error(f"Failed to save state to {state_file_path}: {e}")

def ingest_screenconnect(config: Dict[str, Any]) -> None:
    logger = get_sdc_logger(__name__, config)
    logger.info("Starting ScreenConnect ingestion with 'Billable Session Consolidation' logic...")

    log_dir = config['project_paths']['screenconnect_logs']
    try:
        csv_files = sorted([f for f in os.listdir(log_dir) if f.endswith('.csv')])
        if not csv_files:
            logger.warning(f"No CSV files found in {log_dir}")
            return
        target_file = os.path.join(log_dir, csv_files[0])
    except FileNotFoundError:
        logger.error(f"Log directory not found: {log_dir}")
        return

    ingestor_state = _load_ingestor_state(config, logger)
    current_metadata = _get_file_metadata(target_file)

    if ingestor_state.get(target_file) == current_metadata:
        logger.info(f"File '{target_file}' unchanged. Skipping.")
        return

    try:
        df = pd.read_csv(target_file)
        logger.info(f"Loaded {len(df)} events from {target_file}")

        df['ConnectedTime_dt'] = pd.to_datetime(df['ConnectedTime'], errors='coerce')
        df['DisconnectedTime_dt'] = pd.to_datetime(df['DisconnectedTime'], errors='coerce')
        df.dropna(subset=['ConnectedTime_dt', 'DisconnectedTime_dt', 'ParticipantName', 'SessionCustomProperty1'], inplace=True)

        df.sort_values(by=['SessionCustomProperty1', 'ParticipantName', 'ConnectedTime_dt'], inplace=True)

        if df.empty:
            logger.info("DataFrame is empty after cleaning. No sessions to process.")
            return

        sessions = []
        current_session_events = [df.iloc[0].to_dict()]
        session_customer = df.iloc[0]['SessionCustomProperty1']
        session_participant = df.iloc[0]['ParticipantName']
        session_start_time = df.iloc[0]['ConnectedTime_dt']
        session_end_time = df.iloc[0]['DisconnectedTime_dt']

        for _, row in df.iloc[1:].iterrows():
            customer_changed = row['SessionCustomProperty1'] != session_customer
            participant_changed = row['ParticipantName'] != session_participant
            time_gap_exceeded = (row['ConnectedTime_dt'] - session_end_time) > timedelta(minutes=SESSION_WINDOW_MINUTES)

            if customer_changed or participant_changed or time_gap_exceeded:
                sessions.append({
                    'customer': session_customer,
                    'participant': session_participant,
                    'start_time': session_start_time,
                    'end_time': session_end_time,
                    'events': current_session_events
                })
                current_session_events = [row.to_dict()]
                session_customer = row['SessionCustomProperty1']
                session_participant = row['ParticipantName']
                session_start_time = row['ConnectedTime_dt']
                session_end_time = row['DisconnectedTime_dt']
            else:
                current_session_events.append(row.to_dict())
                session_end_time = max(session_end_time, row['DisconnectedTime_dt'])

        if current_session_events:
            sessions.append({
                'customer': session_customer,
                'participant': session_participant,
                'start_time': session_start_time,
                'end_time': session_end_time,
                'events': current_session_events
            })

        logger.info(f"Grouped {len(df)} events into {len(sessions)} consolidated sessions.")

        processed_count = 0
        for session in sessions:
            try:
                session_events = session['events']
                cuis = CUISV1()
                cuis.sdc_core.sdc_source_system = 'ScreenConnect'
                cuis.sdc_core.sdc_source_sub_type = 'ScreenConnect_Session'
                cuis.sdc_core.sdc_source_primary_id = '_'.join([str(e['ConnectionID']) for e in session_events])
                cuis.sdc_core.sdc_source_file_path = target_file

                session_start = session['start_time'].tz_localize('UTC')
                session_end = session['end_time'].tz_localize('UTC')
                cuis.core_content.start_timestamp_utc = session_start
                cuis.core_content.end_timestamp_utc = session_end
                cuis.core_content.duration_seconds = int((session_end - session_start).total_seconds())
                cuis.core_content.summary_title_or_subject = f"ScreenConnect Session for {session['participant']}"

                cuis.entities_involved.primary_actor_user_name_source = session['participant']
                cuis.entities_involved.syncro_customer_name_guessed = session['customer']

                # --- NEW: Capture computer names ---
                computer_names = list(set([e['SessionName'] for e in session_events if e.get('SessionName')]))
                # --- END NEW ---

                details = {
                    'screenconnect_process_type': list(set([e.get('ProcessType') for e in session_events if e.get('ProcessType')])),
                    'screenconnect_session_type': list(set([e.get('SessionSessionType') for e in session_events if e.get('SessionSessionType')])),
                    'screenconnect_session_names': computer_names # --- ADDED: Store the computer names
                }
                cuis.source_specific_details = {k: v for k, v in details.items() if v}

                for event in session_events:
                    entry = CuisEntry(
                        entry_id_source=str(event['ConnectionID']),
                        entry_timestamp_utc=event['ConnectedTime_dt'].tz_localize('UTC'),
                        entry_author_name_source=event['ParticipantName'],
                        entry_body_text=f"Connected to {event['SessionName']}. Duration: {event['DurationSeconds']}s.",
                        entry_type_source='Connection_Event'
                    )

                    # --- NEW: Add disconnect time to metadata ---
                    entry.entry_metadata_source = {
                        'disconnected_timestamp_utc': event['DisconnectedTime_dt'].tz_localize('UTC').isoformat()
                    }
                    # --- END NEW ---

                    cuis.cuis_entries.append(entry)

                save_cuis_to_file(cuis, config, logger)
                processed_count += 1
            except Exception as e:
                logger.error(f"Error processing session: {e}", exc_info=True)

        logger.info(f"Successfully processed and saved {processed_count} sessions.")
        ingestor_state[target_file] = current_metadata
        _save_ingestor_state(ingestor_state, config, logger)

    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
