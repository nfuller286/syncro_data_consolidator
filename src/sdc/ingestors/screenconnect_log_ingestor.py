# -*- coding: utf-8 -*-
"""Ingestor for ScreenConnect session logs from CSV files."""

import pandas as pd
import os
import json
import uuid 
import datetime
from typing import Any, Dict
from datetime import timedelta

# --- V2 IMPORTS ---
from sdc.models.session_v2 import Session, SessionSegment, SessionMeta, SessionContext, SessionInsights
from sdc.utils.session_handler import save_session_to_file
# --- SHARED UTILS ---
from sdc.utils import file_ingestor_state_handler as state_handler
from sdc.utils.sdc_logger import get_sdc_logger

# --- CONSTANTS ---
STATE_FILE_NAME = 'screenconnect_log_ingestor_state.json'
UNDEFINED_TIMESTAMP = datetime.datetime(1970, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
SESSION_WINDOW_MINUTES = 30

# =================================================================================
#  HELPER FUNCTIONS - PURE LOGIC
# =================================================================================

def _consolidate_events(df: pd.DataFrame) -> list[list[dict]]:
    """
    Groups individual event rows from a DataFrame into consolidated sessions.

    A new session is started when the customer, participant, or time gap between
    events exceeds a defined threshold.

    Args:
        df: A pre-sorted and cleaned DataFrame of ScreenConnect events.

    Returns:
        A list of sessions, where each session is a list of event dictionaries.
    """
    if df.empty:
        return []

    sessions = []
    current_session_events = [df.iloc[0].to_dict()]
    session_customer = df.iloc[0]['SessionCustomProperty1']
    session_participant = df.iloc[0]['ParticipantName']
    session_end_time = df.iloc[0]['DisconnectedTime_dt']

    # Iterate over rows as dictionaries for cleaner access
    for _, row_dict in df.iloc[1:].to_dict('index').items():
        time_gap_exceeded = (row_dict['ConnectedTime_dt'] - session_end_time) > timedelta(minutes=SESSION_WINDOW_MINUTES)
        
        # Condition to start a new session
        if row_dict['SessionCustomProperty1'] != session_customer or row_dict['ParticipantName'] != session_participant or time_gap_exceeded:
            # Finalize and append the previous session
            sessions.append(current_session_events)
            
            # Start a new session, resetting state with the current event's data
            current_session_events = [row_dict]
            session_customer = row_dict['SessionCustomProperty1']
            session_participant = row_dict['ParticipantName']
            session_end_time = row_dict['DisconnectedTime_dt']
        else:
            # Continue the current session
            current_session_events.append(row_dict)
            session_end_time = max(session_end_time, row_dict['DisconnectedTime_dt'])

    if current_session_events:
        sessions.append(current_session_events)
    
    return sessions

def _transform_group_to_session(event_group: list[dict], target_file: str) -> Session:
    """Transforms a group of events into a single V2 Session object."""
    session_start_time = min(e['ConnectedTime_dt'] for e in event_group)
    session_end_time = max(e['DisconnectedTime_dt'] for e in event_group)
    customer_name = event_group[0]['SessionCustomProperty1']
    participant_name = event_group[0]['ParticipantName']

    segments = []
    source_row_indices = []
    for event in event_group:
        segments.append(SessionSegment(
            segment_id=str(uuid.uuid4()),
            start_time_utc=event['ConnectedTime_dt'],
            end_time_utc=event['DisconnectedTime_dt'],
            type="RemoteConnection",
            author=event['ParticipantName'],
            content=f"Connected to machine: {event.get('SessionName', 'Unknown')}",
            metadata={
                "connection_id": event.get('ConnectionID'), "process_type": event.get('ProcessType'),
                "session_type": event.get('SessionSessionType'), "duration_seconds": event.get('DurationSeconds')
            }
        ))
        source_row_indices.append(str(event['original_row_index']))

    return Session(
        meta=SessionMeta(
            session_id=str(uuid.uuid4()), schema_version="2.0", source_system="ScreenConnect",
            source_identifiers=[target_file, f"rows/{','.join(source_row_indices)}"],
            processing_status="Needs Linking",
            ingestion_timestamp_utc=datetime.datetime.now(datetime.timezone.utc),
            last_updated_timestamp_utc=datetime.datetime.now(datetime.timezone.utc)
        ),
        context=SessionContext(
            customer_name=customer_name, contact_name=None, customer_id=None, contact_id=None
        ),
        insights=SessionInsights(
            session_start_time_utc=session_start_time, session_end_time_utc=session_end_time,
            session_duration_minutes=int((session_end_time - session_start_time).total_seconds() / 60),
            source_title=f"ScreenConnect Session for {participant_name}",
            llm_generated_category=None, llm_generated_title=None, user_notes=""
        ),
        segments=segments
    )

# =================================================================================
#  REFACTORED INGESTION FUNCTION
# =================================================================================
def ingest_screenconnect(config: Dict[str, Any], logger) -> None:
    """
    Loads ScreenConnect CSV logs, consolidates events into sessions,
    and transforms them into the V2 Session format.
    """
    logger.info("Starting ScreenConnect ingestion...")

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

    state_file_path = os.path.join(config['project_paths']['cache_folder'], STATE_FILE_NAME)
    ingestor_state = state_handler.load_state(state_file_path, logger)
    current_metadata = state_handler.get_file_metadata(target_file)

    if ingestor_state.get(target_file) == current_metadata:
        logger.info(f"File '{target_file}' unchanged. Skipping.")
        return

    try:
        df = pd.read_csv(target_file)
        logger.info(f"Loaded {len(df)} events from {target_file}")

        # --- Data Cleaning and Preparation ---
        # Coerce invalid date strings into NaT (Not a Time)
        df['ConnectedTime_dt'] = pd.to_datetime(df['ConnectedTime'], errors='coerce')
        df['DisconnectedTime_dt'] = pd.to_datetime(df['DisconnectedTime'], errors='coerce')

        # Drop rows that are missing essential grouping info, but keep rows with bad timestamps
        df.dropna(subset=['ParticipantName', 'SessionCustomProperty1'], inplace=True)

        # Localize valid timestamps to UTC and fill any NaT values with our placeholder
        df['ConnectedTime_dt'] = df['ConnectedTime_dt'].dt.tz_localize('UTC').fillna(UNDEFINED_TIMESTAMP)
        df['DisconnectedTime_dt'] = df['DisconnectedTime_dt'].dt.tz_localize('UTC').fillna(UNDEFINED_TIMESTAMP)

        df.sort_values(by=['SessionCustomProperty1', 'ParticipantName', 'ConnectedTime_dt'], inplace=True)
        df.reset_index(inplace=True)
        df.rename(columns={'index': 'original_row_index'}, inplace=True)


        if df.empty:
            logger.info("DataFrame is empty after cleaning. No sessions to process.")
            return
        
        # 1. Call the consolidation helper
        consolidated_sessions = _consolidate_events(df)
        logger.info(f"Grouped {len(df)} events into {len(consolidated_sessions)} consolidated sessions.")

        # 2. Loop and call the transformation helper
        processed_count = 0
        failed_count = 0
        for group in consolidated_sessions:
            try:
                session_object = _transform_group_to_session(group, target_file)
                save_session_to_file(session_object, config, logger)
                processed_count += 1
            except Exception as e:
                # Ensure group is not empty before trying to access it for logging
                start_time_for_log = group[0].get('ConnectedTime_dt', 'Unknown Time') if group else 'Unknown Time'
                logger.error(f"Error processing session group starting at {start_time_for_log}: {e}", exc_info=True)
                failed_count += 1

        logger.info(f"Finished ScreenConnect ingestion. Total Success: {processed_count}, Total Failed: {failed_count}")
        
        # --- Final state saving ---
        if failed_count == 0:
            ingestor_state[target_file] = current_metadata
            state_handler.save_state(ingestor_state, state_file_path, logger)

    except Exception as e:
        logger.error(f"A critical error occurred during ScreenConnect ingestion: {e}", exc_info=True)