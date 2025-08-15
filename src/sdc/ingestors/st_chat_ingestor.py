# -*- coding: utf-8 -*-
"""Ingestor for SillyTavern chat logs in .jsonl format."""

import json
import os
import uuid
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

# --- V2 IMPORTS ---
from sdc.models.session_v2 import Session, SessionSegment, SessionMeta, SessionContext, SessionInsights
from sdc.utils.session_handler import save_session_to_file
# --- SHARED UTILS ---
from sdc.utils import file_ingestor_state_handler as state_handler
from sdc.utils.date_utils import parse_datetime_utc

# --- CONSTANTS ---
STATE_FILE_NAME = 'st_chat_ingestor_file_state.json'

# =================================================================================
#  HELPER FUNCTIONS - PURE LOGIC
# =================================================================================
def _calculate_message_fingerprint(message: Dict[str, Any]) -> str:
    """Creates a unique, deterministic hash for a message."""
    # Use the most stable fields to create the fingerprint
    timestamp = message.get('send_date', '')
    author = message.get('name', '')
    content = message.get('mes', '')
    
    # Concatenate and encode for hashing
    fingerprint_str = f"{timestamp}|{author}|{content}".encode('utf-8')
    return hashlib.sha256(fingerprint_str).hexdigest()

def _segment_chat_into_sessions(valid_messages: List[Dict[str, Any]], session_gap_minutes: int, config: Dict[str, Any], logger) -> List[List[Dict[str, Any]]]:
    """Segments a list of chat messages into separate sessions based on time gaps."""
    if not valid_messages:
        return []

    sessions: List[List[Dict[str, Any]]] = []
    current_session: List[Dict[str, Any]] = [valid_messages[0]]

    for i in range(1, len(valid_messages)):
        prev_date_str = valid_messages[i - 1].get('send_date')
        curr_date_str = valid_messages[i].get('send_date')

        prev_msg_time = parse_datetime_utc(prev_date_str, config)
        curr_msg_time = parse_datetime_utc(curr_date_str, config)

        if not prev_msg_time or not curr_msg_time:
            logger.warning(f"Skipping session gap check due to invalid/missing timestamp.")
            current_session.append(valid_messages[i])
            continue

        if (curr_msg_time - prev_msg_time) > timedelta(minutes=session_gap_minutes):
            sessions.append(current_session)
            current_session = [valid_messages[i]]
        else:
            current_session.append(valid_messages[i])

    sessions.append(current_session)  # Add the last session
    return sessions

def _transform_group_to_session_object(
    session_messages: List[Dict[str, Any]],
    metadata: Dict[str, Any],
    file_path: str,
    config: Dict[str, Any],
    UNDEFINED_TIMESTAMP: datetime
) -> Session:
    """Transforms a group of chat messages into a single V2 Session object."""
    character_name = metadata.get('character_name', 'Unknown Character')
    chat_id_hash = metadata.get('chat_metadata', {}).get('chat_id_hash', 'unknown_hash')
    
    start_time_utc = parse_datetime_utc(session_messages[0].get('send_date'), config) or UNDEFINED_TIMESTAMP
    end_time_utc = parse_datetime_utc(session_messages[-1].get('send_date'), config) or UNDEFINED_TIMESTAMP

    segments = [
        SessionSegment(
            segment_id=str(uuid.uuid4()),
            start_time_utc=parse_datetime_utc(msg.get('send_date'), config) or UNDEFINED_TIMESTAMP,
            end_time_utc=parse_datetime_utc(msg.get('send_date'), config) or UNDEFINED_TIMESTAMP,
            type="ChatMessage",
            author=msg.get('name'),
            content=msg.get('mes'),
            metadata={"is_user": msg.get('is_user', False)}
        ) for msg in session_messages
    ]

    return Session(
        meta=SessionMeta(
            session_id=str(uuid.uuid4()), schema_version="2.0", source_system="SillyTavern",
            source_identifiers=[file_path], processing_status="Complete",
            ingestion_timestamp_utc=datetime.now(timezone.utc),
            last_updated_timestamp_utc=datetime.now(timezone.utc)
        ),
        context=SessionContext(
            customer_name=None, contact_name=None, links=[f"st_chat_id:{chat_id_hash}"],
            customer_id=None, contact_id=None
        ),
        insights=SessionInsights(
            session_start_time_utc=start_time_utc, session_end_time_utc=end_time_utc,
            session_duration_minutes=int((end_time_utc - start_time_utc).total_seconds() / 60) if start_time_utc and end_time_utc else 0,
            source_title=f"SillyTavern Chat with {character_name}",
            llm_generated_title=None, llm_generated_category=None, user_notes=""
        ),
        segments=segments
    )

def ingest_sillytavern_chats(config: Dict[str, Any], logger) -> None:
    """
    Loads SillyTavern .jsonl chat logs, segments them into sessions,
    transforms them into the V2 Session format, and saves them.

    Args:
        config: The application's configuration dictionary.
        logger: The SDC logger instance.
    """
    logger.info("Starting ingestion for source: SillyTavern")

    # Define a placeholder for items with no valid timestamp.
    UNDEFINED_TIMESTAMP = datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    try:
        input_folder = config['project_paths']['sillytavern_chat_input_folder']
        session_gap_minutes = config['processing_defaults']['sillytavern_session_gap_minutes']
    except KeyError as e:
        logger.critical(f"Configuration key missing: {e}. Aborting SillyTavern ingestion.")
        return

    processed_files, total_sessions_created = 0, 0
    state_file_path = os.path.join(config['project_paths']['cache_folder'], STATE_FILE_NAME)
    # This ingestor requires a specific default state structure.
    default_state = {"processed_files": {}, "seen_message_fingerprints": []}
    ingestor_state = state_handler.load_state(state_file_path, logger, default_state=default_state)
    # Use a set for fast O(1) lookups of seen fingerprints
    seen_fingerprints_set = set(ingestor_state.get("seen_message_fingerprints", []))
    updated_state = False

    for filename in os.listdir(input_folder):
        if not filename.endswith('.jsonl'):
            continue

        file_path = os.path.join(input_folder, filename)
        current_metadata = state_handler.get_file_metadata(file_path)

        # Check against the 'processed_files' key in the new state structure
        if file_path in ingestor_state.get("processed_files", {}) and ingestor_state["processed_files"][file_path] == current_metadata:
            logger.info(f"SillyTavern chat file '{filename}' unchanged. Skipping re-ingestion.")
            processed_files += 1 # Count as processed, but skipped
            continue

        logger.info(f"Processing SillyTavern log file: {file_path}")
        processed_files += 1

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            if not lines:
                logger.warning(f"File {filename} is empty. Skipping.")
                continue

            # --- Message Deduplication Logic ---
            metadata = json.loads(lines[0])
            raw_messages = [json.loads(line) for line in lines[1:]]
            
            valid_messages = []
            for msg in raw_messages:
                fingerprint = _calculate_message_fingerprint(msg)
                if fingerprint not in seen_fingerprints_set:
                    valid_messages.append(msg)
                    seen_fingerprints_set.add(fingerprint)
            
            if not valid_messages:
                logger.warning(f"File {filename} has metadata but no messages. Skipping.")
                continue

            logger.info(f"Found {len(valid_messages)} new, unique messages in {filename} (out of {len(raw_messages)} total).")

            # Sort the unique messages chronologically
            valid_messages.sort(key=lambda m: parse_datetime_utc(m.get('send_date'), config)
                                              or datetime.min.replace(tzinfo=timezone.utc))

            # 1. Call the segmentation helper
            sessions = _segment_chat_into_sessions(valid_messages, session_gap_minutes, config, logger)
            logger.info(f"Segmented chat into {len(sessions)} sessions.")

            # 2. Loop and call the transformation helper
            session_errors = 0
            for i, session_messages in enumerate(sessions):
                try:
                    session_object = _transform_group_to_session_object(
                        session_messages=session_messages,
                        metadata=metadata,
                        file_path=file_path,
                        config=config,
                        UNDEFINED_TIMESTAMP=UNDEFINED_TIMESTAMP
                    )
                    save_session_to_file(session_object, config, logger)
                    total_sessions_created += 1
                except Exception as e:
                    logger.error(f"Failed to process session {i} from file {filename}: {e}", exc_info=True)
                    session_errors += 1
            
            # If all sessions from this file were processed without errors, update state
            if session_errors == 0:
                ingestor_state["processed_files"][file_path] = current_metadata
                updated_state = True

        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from {filename}: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred processing {filename}: {e}", exc_info=True)

    logger.info(f"Finished SillyTavern ingestion. Processed {processed_files} files, created {total_sessions_created} Session items.")
    
    if updated_state:
        # Convert the set back to a list for JSON serialization
        ingestor_state["seen_message_fingerprints"] = sorted(list(seen_fingerprints_set))
        state_handler.save_state(ingestor_state, state_file_path, logger)
