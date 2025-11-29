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
from sdc.utils import session_aggregator
from sdc.utils.sdc_logger import get_sdc_logger
from sdc.utils.constants import UNDEFINED_TIMESTAMP

# --- CONSTANTS ---
STATE_FILE_NAME = 'screenconnect_log_ingestor_state.json'
SESSION_WINDOW_MINUTES = 30

# =================================================================================
#  HELPER FUNCTIONS - PURE LOGIC
# =================================================================================

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
        
        # 1. Convert all DataFrame rows to SessionSegment objects
        all_segments = []
        for _, row in df.iterrows():
            all_segments.append(SessionSegment(
                segment_id=str(uuid.uuid4()),
                start_time_utc=row['ConnectedTime_dt'],
                end_time_utc=row['DisconnectedTime_dt'],
                type="RemoteConnection",
                author=row['ParticipantName'],
                content=f"Connected to machine: {row.get('SessionName', 'Unknown')}",
                metadata={
                    "customer_name": row['SessionCustomProperty1'], # For grouping
                    "original_row_index": row['original_row_index'], # For source identifiers
                    "connection_id": row.get('ConnectionID'),
                    "process_type": row.get('ProcessType'),
                    "session_type": row.get('SessionSessionType'),
                    "duration_seconds": row.get('DurationSeconds')
                }
            ))

        # 2. Group segments using the session aggregator
        grouped_sessions = session_aggregator.group_segments_by_time_gap_and_keys(
            segments=all_segments,
            time_gap=timedelta(minutes=SESSION_WINDOW_MINUTES),
            grouping_keys=['customer_name', 'author']
        )
        logger.info(f"Grouped {len(all_segments)} events into {len(grouped_sessions)} consolidated sessions.")

        # 3. Transform each group into a Session object and save
        processed_count = 0
        failed_count = 0
        for group in grouped_sessions:
            try:
                first_segment = group[0]
                source_row_indices = [str(s.metadata['original_row_index']) for s in group]
                session_object = session_aggregator.transform_grouped_segments_to_session(
                    segments=group,
                    source_system="ScreenConnect",
                    source_identifiers=[target_file, f"rows/{','.join(source_row_indices)}"],
                    customer_name=first_segment.metadata.get('customer_name'),
                    source_title=f"ScreenConnect Session for {first_segment.author}"
                )
                save_session_to_file(session_object, config, logger)
                processed_count += 1
            except Exception as e:
                # Ensure group is not empty before trying to access it for logging
                start_time_for_log = group[0].start_time_utc if group else 'Unknown Time'
                logger.error(f"Error processing session group starting at {start_time_for_log}: {e}", exc_info=True)
                failed_count += 1

        logger.info(f"Finished ScreenConnect ingestion. Total Success: {processed_count}, Total Failed: {failed_count}")
        
        # --- Final state saving ---
        if failed_count == 0:
            ingestor_state[target_file] = current_metadata
            state_handler.save_state(ingestor_state, state_file_path, logger)

    except Exception as e:
        logger.error(f"A critical error occurred during ScreenConnect ingestion: {e}", exc_info=True)