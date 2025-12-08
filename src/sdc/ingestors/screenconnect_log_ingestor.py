# -*- coding: utf-8 -*-
"""Ingestor for ScreenConnect session logs from CSV files."""

import pandas as pd
import os
import json
import uuid
import datetime
from typing import Any, Dict, List

# --- V2 IMPORTS ---
from sdc.models.session_v2 import Session, SessionSegment, SessionMeta, SessionContext, SessionInsights
from sdc.utils.session_handler import save_session_to_file
# --- SHARED UTILS ---
from sdc.utils import file_ingestor_state_handler as state_handler
from sdc.utils import session_aggregator
from sdc.utils.sdc_logger import get_sdc_logger
from sdc.utils.constants import UNDEFINED_TIMESTAMP, SCREENCONNECT_NAMESPACE_OID
from sdc.api_clients.screenconnect_gateway import ScreenConnectGateway


# --- CONSTANTS ---
STATE_FILE_NAME = 'screenconnect_log_ingestor_state.json'
SESSION_WINDOW_MINUTES = 30

# =================================================================================
#  HELPER FUNCTIONS - PURE LOGIC
# =================================================================================

def _convert_raw_data_to_segments(raw_data: List[Dict]) -> List[SessionSegment]:
    """Converts a list of raw connection records into SessionSegment objects."""
    all_segments = []
    for row in raw_data:
        # Use a deterministic UUID based on the ConnectionID
        segment_uuid = uuid.uuid5(SCREENCONNECT_NAMESPACE_OID, str(row.get('ConnectionID')))

        # Coerce invalid date strings into NaT (Not a Time), then to our undefined timestamp
        connected_time = pd.to_datetime(row.get('ConnectedTime'), errors='coerce')
        disconnected_time = pd.to_datetime(row.get('DisconnectedTime'), errors='coerce')

        connected_time_utc = connected_time.tz_localize('UTC') if pd.notna(connected_time) else UNDEFINED_TIMESTAMP
        disconnected_time_utc = disconnected_time.tz_localize('UTC') if pd.notna(disconnected_time) else UNDEFINED_TIMESTAMP

        all_segments.append(SessionSegment(
            segment_id=str(segment_uuid),
            start_time_utc=connected_time_utc,
            end_time_utc=disconnected_time_utc,
            type="RemoteConnection",
            author=row.get('ParticipantName', 'Unknown'),
            content=f"Connected to machine: {row.get('SessionName', 'Unknown')}",
            metadata={
                "customer_name": row.get('SessionCustomProperty1'), # For grouping
                "connection_id": row.get('ConnectionID'), # Keep original for reference
                "process_type": row.get('ProcessType'),
                "session_type": row.get('SessionSessionType'),
                "duration_seconds": row.get('DurationSeconds')
            }
        ))
    return all_segments


# =================================================================================
#  REFACTORED INGESTION FUNCTION
# =================================================================================
def ingest_screenconnect(config: Dict[str, Any], logger) -> None:
    """
    Loads ScreenConnect data from CSV or API, consolidates events into sessions,
    and transforms them into the V2 Session format.
    """
    logger.info("Starting ScreenConnect ingestion...")

    sc_ingestor_config = config.get('screenconnect_ingestor', {})
    mode = sc_ingestor_config.get('mode', 'csv') # Default to 'csv'

    raw_data = []
    source_identifiers = []
    
    # These will be populated differently depending on the mode
    ingestor_state = None
    state_file_path = None
    current_metadata = None
    target_file = None
    new_last_processed_utc = None

    try:
        if mode == 'csv':
            log_dir = config['project_paths']['screenconnect_logs']
            state_file_path = os.path.join(config['project_paths']['cache_folder'], STATE_FILE_NAME)
            
            try:
                csv_files = sorted([f for f in os.listdir(log_dir) if f.endswith('.csv')])
                if not csv_files:
                    logger.warning(f"No CSV files found in {log_dir}")
                    return
                target_file = os.path.join(log_dir, csv_files[0])
                source_identifiers = [target_file]
            except FileNotFoundError:
                logger.error(f"Log directory not found: {log_dir}")
                return

            ingestor_state = state_handler.load_state(state_file_path, logger)
            current_metadata = state_handler.get_file_metadata(target_file)

            if ingestor_state.get(target_file) == current_metadata:
                logger.info(f"File '{target_file}' unchanged. Skipping.")
                return
            
            df = pd.read_csv(target_file)
            df.dropna(subset=['ParticipantName', 'SessionCustomProperty1'], inplace=True)
            raw_data = df.to_dict('records')
            logger.info(f"Loaded {len(raw_data)} events from {target_file}")

        elif mode == 'api':
            api_config = sc_ingestor_config.get('api_config', {})
            state_file_path = os.path.join(config['project_paths']['cache_folder'], 'screenconnect_ingestor_api_state.json')
            source_identifiers = [f"ScreenConnect API @ {api_config.get('base_url')}"]
            
            ingestor_state = state_handler.load_state(state_file_path, logger)
            last_processed_utc = ingestor_state.get('last_processed_utc')
            
            if last_processed_utc:
                filter_expression = f"ConnectedTime > '{last_processed_utc}'"
            else:
                # If no state exists, fetch records from the last 7 days as a safe default
                seven_days_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)
                filter_expression = f"ConnectedTime > '{seven_days_ago.isoformat()}'"
            
            logger.info(f"Fetching ScreenConnect data with filter: {filter_expression}")
            
            gateway = ScreenConnectGateway(
                base_url=api_config.get('base_url'),
                extension_id=api_config.get('extension_id'),
                api_key=api_config.get('api_key')
            )
            raw_data = gateway.fetch_connections(filter_expression)
            
            if raw_data:
                # Find the latest ConnectedTime in the new data to update the state
                latest_record = max(raw_data, key=lambda x: pd.to_datetime(x.get('ConnectedTime', '')))
                new_last_processed_utc = pd.to_datetime(latest_record.get('ConnectedTime')).isoformat()
                logger.info(f"Fetched {len(raw_data)} new records from API.")

    except Exception as e:
        logger.error(f"Failed to retrieve data in '{mode}' mode: {e}", exc_info=True)
        return

    if not raw_data:
        logger.info("No new raw data to process.")
        return

    # 1. Convert all raw data (from whatever source) to SessionSegment objects
    all_segments = _convert_raw_data_to_segments(raw_data)

    # 2. Group segments using the session aggregator
    grouped_sessions = session_aggregator.group_segments_by_time_gap_and_keys(
        segments=all_segments,
        time_gap=datetime.timedelta(minutes=SESSION_WINDOW_MINUTES),
        grouping_keys=['customer_name', 'author']
    )
    logger.info(f"Grouped {len(all_segments)} events into {len(grouped_sessions)} consolidated sessions.")

    # 3. Transform each group into a Session object and save
    processed_count = 0
    failed_count = 0
    for group in grouped_sessions:
        try:
            first_segment = group[0]
            session_object = session_aggregator.transform_grouped_segments_to_session(
                segments=group,
                source_system="ScreenConnect",
                source_identifiers=source_identifiers,
                customer_name=first_segment.metadata.get('customer_name'),
                source_title=f"ScreenConnect Session for {first_segment.author}"
            )
            save_session_to_file(session_object, config, logger)
            processed_count += 1
        except Exception as e:
            start_time_for_log = group[0].start_time_utc if group else 'Unknown Time'
            logger.error(f"Error processing session group starting at {start_time_for_log}: {e}", exc_info=True)
            failed_count += 1

    logger.info(f"Finished ScreenConnect ingestion. Total Success: {processed_count}, Total Failed: {failed_count}")

    # --- Final state saving ---
    if failed_count > 0:
        logger.warning("Errors occurred during processing. State will not be updated to ensure data is re-processed on next run.")
        return

    if mode == 'csv' and target_file:
        ingestor_state[target_file] = current_metadata
        state_handler.save_state(ingestor_state, state_file_path, logger)
        
    elif mode == 'api' and new_last_processed_utc:
        ingestor_state['last_processed_utc'] = new_last_processed_utc
        state_handler.save_state(ingestor_state, state_file_path, logger)