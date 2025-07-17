# -*- coding: utf-8 -*-
"""Ingestor for SillyTavern chat logs in .jsonl format."""

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from sdc.models.cuis_v1 import CUISV1, CuisEntry
from sdc.utils.cuis_handler import save_cuis_to_file
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
    except (FileNotFoundError, json.JSONDecodeError):
        logger.info(f"SillyTavern Chat Ingestor state file not found or invalid at {state_file_path}. Starting fresh.")
        return {}

def _save_ingestor_state(state: Dict[str, Any], config: Dict[str, Any], logger) -> None:
    """Saves the ingestor state to a JSON file."""
    state_file_path = os.path.join(config['project_paths']['cache_folder'], 'st_chat_ingestor_file_state.json')
    try:
        os.makedirs(os.path.dirname(state_file_path), exist_ok=True)
        with open(state_file_path, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=4)
    except IOError as e:
        logger.error(f"Failed to save SillyTavern Chat Ingestor state to {state_file_path}: {e}")

def ingest_sillytavern_chats(config: Dict[str, Any], logger) -> None:
    """
    Loads SillyTavern .jsonl chat logs, segments them into sessions,
    transforms them into CUIS format, and saves them.

    Args:
        config: The application's configuration dictionary.
        logger: The SDC logger instance.
    """
    logger.info("Starting ingestion for source: SillyTavern")

    try:
        input_folder = config['project_paths']['sillytavern_chat_input_folder']
        session_gap_minutes = config['processing_defaults']['sillytavern_session_gap_minutes']
    except KeyError as e:
        logger.critical(f"Configuration key missing: {e}. Aborting SillyTavern ingestion.")
        return

    processed_files, total_sessions_created = 0, 0
    ingestor_state = _load_ingestor_state(config, logger)
    updated_state = False

    for filename in os.listdir(input_folder):
        if not filename.endswith('.jsonl'):
            continue

        file_path = os.path.join(input_folder, filename)
        current_metadata = _get_file_metadata(file_path)

        if file_path in ingestor_state and ingestor_state[file_path] == current_metadata:
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

            metadata = json.loads(lines[0])
            messages = [json.loads(line) for line in lines[1:]]
            # Sort messages chronologically using the robust date parser.
            # This prevents incorrect sorting based on string representation.
            # On failure, it defaults to the earliest possible time to sort them first.
            messages.sort(key=lambda m: parse_datetime_utc(m.get('send_date'), config)
                                        or datetime.min.replace(tzinfo=timezone.utc))

            if not messages:
                logger.warning(f"File {filename} has metadata but no messages. Skipping.")
                continue

            # --- Session Segmentation Logic ---
            sessions: List[List[Dict[str, Any]]] = []
            current_session: List[Dict[str, Any]] = [messages[0]]

            for i in range(1, len(messages)):
                prev_date_str = messages[i-1].get('send_date')
                curr_date_str = messages[i].get('send_date')

                prev_msg_time = parse_datetime_utc(prev_date_str, config)
                curr_msg_time = parse_datetime_utc(curr_date_str, config)

                if not prev_msg_time or not curr_msg_time:
                    logger.warning(f"Skipping session gap check in {filename} due to invalid/missing timestamp near message {i+1}.")
                    current_session.append(messages[i])
                    continue

                if (curr_msg_time - prev_msg_time) > timedelta(minutes=session_gap_minutes):
                    sessions.append(current_session)
                    current_session = [messages[i]]
                else:
                    current_session.append(messages[i])
            
            sessions.append(current_session) # Add the last session

            logger.info(f"Segmented chat into {len(sessions)} sessions.")

            # --- Process each session into a CUIS item ---
            session_errors = 0
            for i, session_messages in enumerate(sessions):
                try:
                    cuis = CUISV1()
                    chat_id_hash = metadata.get('chat_id_hash', 'unknown_hash')
                    character_name = metadata.get('character_name', 'Unknown Character')
                    user_name = metadata.get('user_name', 'User')

                    start_time_utc = parse_datetime_utc(session_messages[0].get('send_date'), config)
                    first_msg_date = start_time_utc.strftime('%Y-%m-%d') if start_time_utc else "Unknown Date"

                    # Populate sdc_core
                    cuis.sdc_core.sdc_source_system = 'SillyTavern'
                    cuis.sdc_core.sdc_source_sub_type = 'SillyTavern_Session'
                    start_ts_id = int(start_time_utc.timestamp()) if start_time_utc else "unknown"
                    cuis.sdc_core.sdc_source_primary_id = f"{chat_id_hash}-{start_ts_id}"
                    cuis.sdc_core.sdc_source_file_path = file_path

                    # Parse create_date from metadata, aligning with other ingestors
                    create_date_str = metadata.get('create_date')
                    if create_date_str:
                        # Sanitize the non-standard format "2025-04-30@14h40m31s"
                        sanitized_date_str = create_date_str.replace('@', 'T').replace('h', ':').replace('m', ':').replace('s', '')
                        cuis.core_content.creation_timestamp_utc = parse_datetime_utc(sanitized_date_str, config)

                    # Populate core_content
                    cuis.core_content.summary_title_or_subject = f"ST Session with {character_name} on {first_msg_date}"
                    cuis.core_content.start_timestamp_utc = start_time_utc
                    cuis.core_content.end_timestamp_utc = parse_datetime_utc(session_messages[-1].get('send_date'), config)

                    # Process each message into a CuisEntry for consistency with other conversational ingestors
                    for msg in session_messages:
                        entry = CuisEntry(
                            entry_timestamp_utc=parse_datetime_utc(msg.get('send_date'), config),
                            entry_author_name_source=msg.get('name'),
                            entry_body_text=msg.get('mes')
                        )
                        cuis.cuis_entries.append(entry)

                    # Populate source_specific_details
                    # Adhere to the structure defined in CUIS V1.0 Definition.MD
                    cuis.source_specific_details['sillytavern_character_name'] = character_name
                    cuis.source_specific_details['sillytavern_user_name'] = user_name
                    cuis.source_specific_details['sillytavern_main_chat_source_file'] = metadata.get('chat_metadata', {}).get('main_chat')
                    
                    structured_messages = []
                    for msg in session_messages:
                        structured_messages.append({
                            "message_text": msg.get('mes'),
                            "sender_name": msg.get('name'),
                            "is_user_message": msg.get('is_user', False),
                            "message_timestamp_utc": parse_datetime_utc(msg.get('send_date'), config)
                        })
                    cuis.source_specific_details['sillytavern_session_messages'] = structured_messages

                    save_cuis_to_file(cuis, config, logger)
                    total_sessions_created += 1
                except Exception as e:
                    logger.error(f"Failed to process session {i} from file {filename}: {e}", exc_info=True)
                    session_errors += 1
            
            # If all sessions from this file were processed without errors, update state
            if session_errors == 0:
                ingestor_state[file_path] = current_metadata
                updated_state = True

        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from {filename}: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred processing {filename}: {e}", exc_info=True)

    logger.info(f"Finished SillyTavern ingestion. Processed {processed_files} files, created {total_sessions_created} CUIS items.")
    
    if updated_state:
        _save_ingestor_state(ingestor_state, config, logger)
