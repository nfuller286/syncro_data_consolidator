# -*- coding: utf-8 -*-
"""Ingestor for SillyTavern chat logs in .jsonl format."""

import json
import os
import uuid
import hashlib
from datetime import timedelta
from typing import Any, Dict, List

# --- V2 IMPORTS ---
from sdc.models.session_v2 import Session, SessionSegment, SessionMeta, SessionContext, SessionInsights
from sdc.utils.session_handler import save_session_to_file
# --- SHARED UTILS ---
from sdc.utils import file_ingestor_state_handler as state_handler
from sdc.utils.date_utils import parse_datetime_utc
from sdc.utils.file_utils import find_files_recursive
from sdc.utils import session_aggregator
from sdc.utils.constants import UNDEFINED_TIMESTAMP

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

def ingest_sillytavern_chats(config: Dict[str, Any], logger) -> None:
    """
    Loads SillyTavern .jsonl chat logs, segments them into sessions,
    transforms them into the V2 Session format, and saves them.

    Args:
        config: The application's configuration dictionary.
        logger: The SDC logger instance.
    """
    logger.info("Starting ingestion for source: SillyTavern")

    try:
        input_folder = config['project_paths']['sillytavern_chat_input_folder']
        session_gap_minutes = config['processing_defaults']['sillytavern_session_gap_minutes']
        # Check for recursive scan setting, defaulting to False if not present
        recursive_scan = config.get('processing_defaults', {}).get('recursive_sillytavern_scan', False)
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

    if recursive_scan:
        logger.info(f"Recursively scanning for SillyTavern chat logs in: {input_folder}")
        all_files = find_files_recursive(input_folder, '*.jsonl')
    else:
        logger.info(f"Scanning for SillyTavern chat logs in: {input_folder}")
        try:
            all_files = [
                os.path.join(input_folder, f)
                for f in os.listdir(input_folder)
                if f.endswith('.jsonl') and os.path.isfile(os.path.join(input_folder, f))
            ]
        except FileNotFoundError:
            logger.error(f"Input folder not found: {input_folder}")
            all_files = []

    logger.info(f"Found {len(all_files)} SillyTavern chat log files for processing.")

    for file_path in all_files:
        filename = os.path.basename(file_path)
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

            # 1. Convert all valid messages to SessionSegment objects
            all_segments = []
            for msg in valid_messages:
                all_segments.append(SessionSegment(
                    segment_id=str(uuid.uuid4()),
                    start_time_utc=parse_datetime_utc(msg.get('send_date'), config, default_on_error=UNDEFINED_TIMESTAMP),
                    end_time_utc=parse_datetime_utc(msg.get('send_date'), config, default_on_error=UNDEFINED_TIMESTAMP),
                    type="ChatMessage",
                    author=msg.get('name'),
                    content=msg.get('mes'),
                    metadata={"is_user": msg.get('is_user', False)}
                ))

            # 2. Group segments using the session aggregator
            grouped_sessions = session_aggregator.group_segments_by_time_gap_and_keys(
                segments=all_segments,
                time_gap=timedelta(minutes=session_gap_minutes)
                # No grouping keys needed for SillyTavern
            )
            logger.info(f"Segmented chat into {len(grouped_sessions)} sessions.")

            # 3. Transform each group into a Session object and save
            session_errors = 0
            for i, group in enumerate(grouped_sessions):
                try:
                    # Extract context from the file's metadata
                    character_name = metadata.get('character_name', 'Unknown Character')
                    chat_id_hash = metadata.get('chat_metadata', {}).get('chat_id_hash', 'unknown_hash')

                    session_object = session_aggregator.transform_grouped_segments_to_session(
                        segments=group,
                        source_system="SillyTavern",
                        source_identifiers=[file_path],
                        source_title=f"SillyTavern Chat with {character_name}",
                        processing_status="Complete",  # SillyTavern sessions don't need linking
                        links=[f"st_chat_id:{chat_id_hash}"]
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
