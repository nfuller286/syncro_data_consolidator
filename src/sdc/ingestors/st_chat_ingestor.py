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
from sdc.utils.date_utils import parse_datetime_utc

def _get_file_metadata(file_path: str) -> Dict[str, Any]:
    """Returns file size and modification time."""
    try:
        stat = os.stat(file_path)
        return {'size': stat.st_size, 'mtime': stat.st_mtime}
    except FileNotFoundError:
        return {}

def _load_ingestor_state(config: Dict[str, Any], logger) -> Dict[str, Any]:
    """Loads the ingestor state from a JSON file."""
    state_file_path = os.path.join(config['project_paths']['cache_folder'], 'st_chat_ingestor_file_state.json')
    try:
        with open(state_file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, TypeError):
        logger.info(f"SillyTavern Chat Ingestor state file not found or invalid at {state_file_path}. Starting fresh.")
        # Return the new, structured state
        return {"processed_files": {}, "seen_message_fingerprints": []}

def _save_ingestor_state(state: Dict[str, Any], config: Dict[str, Any], logger) -> None:
    """Saves the ingestor state to a JSON file."""
    state_file_path = os.path.join(config['project_paths']['cache_folder'], 'st_chat_ingestor_file_state.json')
    temp_file_path = state_file_path + ".tmp"
    try:
        os.makedirs(os.path.dirname(state_file_path), exist_ok=True)
        with open(temp_file_path, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=4)
        # Atomic rename to prevent state corruption if the process is interrupted
        os.replace(temp_file_path, state_file_path)
    except IOError as e:
        logger.error(f"Failed to save SillyTavern Chat Ingestor state to {state_file_path}: {e}")
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

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
    transforms them into CUIS format, and saves them.

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
    ingestor_state = _load_ingestor_state(config, logger)
    # Use a set for fast O(1) lookups of seen fingerprints
    seen_fingerprints_set = set(ingestor_state.get("seen_message_fingerprints", []))
    updated_state = False

    for filename in os.listdir(input_folder):
        if not filename.endswith('.jsonl'):
            continue

        file_path = os.path.join(input_folder, filename)
        current_metadata = _get_file_metadata(file_path)

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

            # --- Session Segmentation Logic ---
            sessions: List[List[Dict[str, Any]]] = []
            # Operate on the cleaned list of valid_messages
            current_session: List[Dict[str, Any]] = [valid_messages[0]]

            for i in range(1, len(valid_messages)):
                prev_date_str = valid_messages[i-1].get('send_date')
                curr_date_str = valid_messages[i].get('send_date')

                prev_msg_time = parse_datetime_utc(prev_date_str, config)
                curr_msg_time = parse_datetime_utc(curr_date_str, config)

                if not prev_msg_time or not curr_msg_time:
                    logger.warning(f"Skipping session gap check in {filename} due to invalid/missing timestamp.")
                    current_session.append(valid_messages[i])
                    continue

                if (curr_msg_time - prev_msg_time) > timedelta(minutes=session_gap_minutes):
                    sessions.append(current_session)
                    current_session = [valid_messages[i]]
                else:
                    current_session.append(valid_messages[i])
            
            sessions.append(current_session) # Add the last session

            logger.info(f"Segmented chat into {len(sessions)} sessions.")

            # --- Process each session into a V2 Session item ---
            session_errors = 0
            for i, session_messages in enumerate(sessions):
                try:
                    # Extract metadata for this session
                    character_name = metadata.get('character_name', 'Unknown Character')
                    user_name = metadata.get('user_name', 'User')
                    chat_id_hash = metadata.get('chat_metadata', {}).get('chat_id_hash', 'unknown_hash')
                    
                    start_time_utc = parse_datetime_utc(session_messages[0].get('send_date'), config) or UNDEFINED_TIMESTAMP
                    end_time_utc = parse_datetime_utc(session_messages[-1].get('send_date'), config) or UNDEFINED_TIMESTAMP

                    # Create a SessionSegment for each unique message
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

                    session_object = Session(
                        meta=SessionMeta(
                            session_id=str(uuid.uuid4()),
                            schema_version="2.0",
                            source_system="SillyTavern",
                            source_identifiers=[file_path],
                            processing_status="Complete", # No customer linking needed
                            ingestion_timestamp_utc=datetime.now(timezone.utc),
                            last_updated_timestamp_utc=datetime.now(timezone.utc)
                        ),
                        context=SessionContext(
                            # SillyTavern chats do not map to a customer/contact model.
                            # This information is available in the segments' author field and insights title.
                            customer_name=None,
                            contact_name=None,
                            links=[f"st_chat_id:{chat_id_hash}"], # Add the grouping link
                            customer_id=None,
                            contact_id=None
                        ),
                        insights=SessionInsights(
                            session_start_time_utc=start_time_utc,
                            session_end_time_utc=end_time_utc,
                            session_duration_minutes=int((end_time_utc - start_time_utc).total_seconds() / 60) if start_time_utc and end_time_utc else 0,
                            source_title=f"SillyTavern Chat with {character_name}",
                            llm_generated_title=None,
                            user_notes=""
                        ),
                        segments=segments
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
        _save_ingestor_state(ingestor_state, config, logger)
