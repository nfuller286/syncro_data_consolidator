
# -*- coding: utf-8 -*-
"""Ingestor for ScreenConnect session logs from CSV files."""

import pandas as pd
import os
import uuid
import datetime
from typing import Any, Dict, List, Optional

# --- V2 IMPORTS ---
from sdc.models.session_v2 import Session, SessionSegment, SessionMeta, SessionContext, SessionInsights
from sdc.utils.session_handler import save_session_to_file
# --- SHARED UTILS ---
from sdc.utils import file_ingestor_state_handler as state_handler
from sdc.utils import session_aggregator
from sdc.utils.constants import (
    UNDEFINED_TIMESTAMP, SCREENCONNECT_NAMESPACE_OID,
    SCREENCONNECT_QUERY_FIELDS,
)
from sdc.api_clients.screenconnect_gateway import ScreenConnectGateway
from sdc.utils.date_utils import parse_datetime_utc


# --- CONSTANTS ---
STATE_FILE_NAME = 'screenconnect_log_ingestor_state.json'
SESSION_WINDOW_MINUTES = 30

# =================================================================================
#  HELPER FUNCTIONS - PURE LOGIC
# =================================================================================

def _convert_raw_data_to_segments(raw_data: List[Dict], config: Dict[str, Any]) -> List[SessionSegment]:
    """Converts a list of raw connection records into SessionSegment objects."""
    all_segments = []
    for row in raw_data:
        # Use a deterministic UUID based on the ConnectionID
        segment_uuid = uuid.uuid5(SCREENCONNECT_NAMESPACE_OID, str(row.get('ConnectionID')))

        # Use the robust date utility to parse and convert to UTC
        connected_time_utc = parse_datetime_utc(row.get('ConnectedTime'), config) or UNDEFINED_TIMESTAMP
        disconnected_time_utc = parse_datetime_utc(row.get('DisconnectedTime'), config) or UNDEFINED_TIMESTAMP

        all_segments.append(SessionSegment(
            segment_id=str(segment_uuid),
            start_time_utc=connected_time_utc,
            end_time_utc=disconnected_time_utc,
            type="RemoteConnection",
            author=row.get('ParticipantName', 'Unknown'),
            content=f"Connected to machine: {row.get('SessionName', 'Unknown')}",
            metadata={
                "customer_name": row.get('SessionCustomProperty1'),  # For grouping
                "connection_id": row.get('ConnectionID'),            # Keep original for reference
                "process_type": row.get('ProcessType'),
                "session_type": row.get('SessionSessionType'),
                "duration_seconds": row.get('DurationSeconds'),
            }
        ))
    return all_segments


# =================================================================================
#  REFACTORED INGESTION FUNCTION
# =================================================================================
def ingest_screenconnect(config: Dict[str, Any], logger, **kwargs) -> None:
    """
    Loads ScreenConnect data from CSV or API, consolidates events into sessions,
    and transforms them into the V2 Session format.
    """
    # Extract dynamic args
    start_date: Optional[str] = kwargs.get('start_date')
    end_date: Optional[str] = kwargs.get('end_date')
    filters: List[str] = kwargs.get('filters', [])

    logger.info("Starting ScreenConnect ingestion...")

    sc_ingestor_config = config.get('screenconnect_ingestor', {})
    mode = sc_ingestor_config.get('mode', 'csv')  # Default to 'csv'

    raw_data: List[Dict] = []
    source_identifiers: List[str] = []
    
    # These will be populated differently depending on the mode
    ingestor_state: Dict[str, Any] = {}
    state_file_path: Optional[str] = None
    current_metadata: Optional[Dict[str, Any]] = None
    target_file: Optional[str] = None
    new_last_processed_utc: Optional[str] = None

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
            
            # --- Build dynamic filter expression ---
            all_filter_parts: List[str] = []

            # 1. Date filters: Always establish a start time.
            # Priority: Manual start_date > saved state > default 7 days ago.
            if start_date:
                try:
                    start_dt = datetime.datetime.strptime(start_date, '%Y-%m-%d').replace(tzinfo=datetime.timezone.utc)
                    all_filter_parts.append(f"ConnectedTime > '{start_dt.isoformat()}'")
                except ValueError:
                    logger.error(f"Invalid start date format: '{start_date}'. Use YYYY-MM-DD. Aborting.")
                    return
            else: # No manual start_date provided, use incremental logic.
                last_processed_utc = ingestor_state.get('last_processed_utc')
                if last_processed_utc:
                    all_filter_parts.append(f"ConnectedTime > '{last_processed_utc}'")
                else:
                    # Default to 7 days ago if no start_date and no saved state.
                    seven_days_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)
                    all_filter_parts.append(f"ConnectedTime > '{seven_days_ago.isoformat()}'")

            if end_date:
                try:
                    # Inclusive of end date’s full day
                    end_dt = datetime.datetime.strptime(end_date, '%Y-%m-%d').replace(tzinfo=datetime.timezone.utc) + datetime.timedelta(days=1)
                    all_filter_parts.append(f"ConnectedTime < '{end_dt.isoformat()}'")
                except ValueError:
                    logger.error(f"Invalid end date format: '{end_date}'. Use YYYY-MM-DD. Aborting.")
                    return

            # 2. Validated Key=Value filters from kwargs
            for f in filters:
                if not isinstance(f, str):
                    logger.warning(f"Ignoring non-string filter {f!r}. Expected 'Key=Value'.")
                    continue
                if '=' not in f:
                    logger.warning(f"Invalid filter '{f}'. Skipping. Use Key=Value.")
                    continue
                key, value = f.split('=', 1)
                if key not in SCREENCONNECT_QUERY_FIELDS:
                    logger.error(f"Invalid filter key '{key}'. Allowed keys: {sorted(SCREENCONNECT_QUERY_FIELDS)}")
                    continue
                safe_value = value.replace("'", "\\'")
                all_filter_parts.append(f"{key} = '{safe_value}'")

            if not all_filter_parts:
                logger.error("No valid filters constructed. Aborting to prevent full data dump.")
                return

            filter_expression = " AND ".join(all_filter_parts)
            
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
    all_segments = _convert_raw_data_to_segments(raw_data, config)

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
        
    # Only save state in API mode if we are doing an incremental run (no manual dates)
    elif mode == 'api' and new_last_processed_utc and not start_date and not end_date:
        logger.info("Updating API state with new last_processed_utc timestamp.")
        ingestor_state['last_processed_utc'] = new_last_processed_utc
        state_handler.save_state(ingestor_state, state_file_path, logger)
    elif mode == 'api' and (start_date or end_date):
        logger.warning("Manual date range provided. Skipping state update to protect incremental progress.")
