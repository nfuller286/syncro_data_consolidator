# -*- coding: utf-8 -*-
"""Ingestor for data from the legacy notes.json file format."""

import json
import os
import uuid
import datetime
from typing import Any, Dict

# --- V2 IMPORTS ---
# Import the new Session models and the new session handler
from sdc.models.session_v2 import Session, SessionSegment, SessionMeta, SessionContext, SessionInsights
from sdc.utils.session_handler import save_session_to_file
# --- SHARED UTILS ---
from sdc.utils.date_utils import parse_datetime_utc
from sdc.utils.sdc_logger import get_sdc_logger

# Note: The helper functions below do not need to change as they manage the input file state, not the output format.
def _get_file_metadata(file_path: str) -> Dict[str, Any]:
    """Returns file size and modification time."""
    try:
        stat = os.stat(file_path)
        return {'size': stat.st_size, 'mtime': stat.st_mtime}
    except FileNotFoundError:
        return {}

def _load_ingestor_state(config: Dict[str, Any], logger) -> Dict[str, Any]:
    """Loads the ingestor state from a JSON file."""
    state_file_path = os.path.join(config['project_paths']['cache_folder'], 'ingestor_file_state.json')
    try:
        with open(state_file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logger.info(f"Ingestor state file not found or invalid at {state_file_path}. Starting fresh.")
        return {}

def _save_ingestor_state(state: Dict[str, Any], config: Dict[str, Any], logger) -> None:
    """Saves the ingestor state to a JSON file."""
    state_file_path = os.path.join(config['project_paths']['cache_folder'], 'ingestor_file_state.json')
    try:
        os.makedirs(os.path.dirname(state_file_path), exist_ok=True)
        with open(state_file_path, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=4)
    except IOError as e:
        logger.error(f"Failed to save ingestor state to {state_file_path}: {e}")

# =================================================================================
#  REFACTORED INGESTION FUNCTION
# =================================================================================
def ingest_notes(config: Dict[str, Any]) -> None:
    """
    Loads data from notes.json, transforms it into the V2 Session format, and saves it.
    """
    logger = get_sdc_logger(__name__, config)
    logger.info("Starting ingestion for source: NotesJSON")

    # Define a placeholder for items with no valid timestamp, ensuring orphaned work is captured for review.
    UNDEFINED_TIMESTAMP = datetime.datetime(1970, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)

    notes_file_path = config['project_paths']['notes_json']
    current_metadata = _get_file_metadata(notes_file_path)
    ingestor_state = _load_ingestor_state(config, logger)

    if notes_file_path in ingestor_state and ingestor_state[notes_file_path] == current_metadata:
        logger.info(f"NotesJSON file '{notes_file_path}' unchanged. Skipping re-ingestion.")
        return

    try:
        with open(notes_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (FileNotFoundError, KeyError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load or parse notes.json: {e}", exc_info=True)
        return

    processed_items = 0
    failed_items = 0

    # --- Process tickets ---
    for index, ticket in enumerate(data.get('tickets', [])):
        try:
            ticket_number = ticket.get('ticketNumber')
            if not ticket_number:
                logger.warning("Skipping ticket with no ticketNumber.")
                failed_items += 1
                continue

            segments = []
            raw_ticket_date = ticket.get('date')
            ticket_creation_time = parse_datetime_utc(raw_ticket_date, config)
            if not ticket_creation_time:
                logger.warning(
                    f"Ticket {ticket.get('ticketNumber', 'N/A')} has missing/invalid date ('{raw_ticket_date}'). "
                    f"Using placeholder timestamp: {UNDEFINED_TIMESTAMP.isoformat()}"
                )
                ticket_creation_time = UNDEFINED_TIMESTAMP

            
            # Create a segment for the initial issue description
            if ticket.get('initial_issue'):
                segments.append(SessionSegment(
                    segment_id=str(uuid.uuid4()),
                    start_time_utc=ticket_creation_time,
                    end_time_utc=ticket_creation_time,
                    type="TicketInitialIssue",
                    author=ticket.get('contact'),
                    content=ticket.get('initial_issue'),
                    metadata={}
                ))

            # Create segments for each sub-note
            for sub_note in ticket.get('notes', []):
                # If a sub-note has no time, fall back to the ticket's creation time.
                # This is safe because ticket_creation_time is now guaranteed to be a datetime object.
                note_time = parse_datetime_utc(sub_note.get('date'), config) or ticket_creation_time
                segments.append(SessionSegment(
                    segment_id=str(uuid.uuid4()),
                    start_time_utc=note_time,
                    end_time_utc=note_time,
                    type="TicketNote",
                    author=sub_note.get('user', ticket.get('contact')),
                    content=sub_note.get('note'),
                    metadata={'order': sub_note.get('order')}
                ))
            
            # Create segments for each to-do item within the ticket
            for sub_todo in ticket.get('to-do', []):
                # If a sub-todo has no time, fall back to the ticket's creation time.
                # This is safe because ticket_creation_time is now guaranteed to be a datetime object.
                todo_time = parse_datetime_utc(sub_todo.get('date'), config) or ticket_creation_time
                segments.append(SessionSegment(
                    segment_id=str(uuid.uuid4()),
                    start_time_utc=todo_time,
                    end_time_utc=todo_time,
                    type="TicketToDo",
                    author=sub_todo.get('user', ticket.get('contact')),
                    content=f"To-Do: {sub_todo.get('task')}",
                    metadata={'order': sub_todo.get('order'), 'completed': sub_todo.get('completed')}
                ))

            # Assemble the final Session object for the ticket
            session_object = Session(
                meta=SessionMeta(
                    session_id=str(uuid.uuid4()),
                    schema_version="2.0",
                    source_system="notes.json",
                    source_identifiers=[notes_file_path, f"/tickets/{index}"],
                    processing_status="Needs Linking",
                    ingestion_timestamp_utc=datetime.datetime.now(datetime.timezone.utc),
                    last_updated_timestamp_utc=datetime.datetime.now(datetime.timezone.utc)
                ),
                context=SessionContext(
                    customer_name=ticket.get('customer'),
                    contact_name=ticket.get('contact'),
                    # Explicitly set fields that will be populated by the linker
                    customer_id=None,
                    contact_id=None
                ),
                insights=SessionInsights(
                    session_start_time_utc=ticket_creation_time,
                    session_end_time_utc=ticket_creation_time, # Duration is 0 for these items
                    session_duration_minutes=0,
                    source_title=ticket.get('subject'),
                    # Explicitly set fields that will be populated by other processors
                    llm_generated_title=None,
                    user_notes=""
                ),
                segments=segments
            )
            
            save_session_to_file(session_object, config, logger)
            processed_items += 1

        except Exception as e:
            logger.error(f"Failed to process ticket {ticket.get('ticketNumber', 'N/A')}: {e}", exc_info=True)
            failed_items += 1

    # --- Process standalone ToDo items ---
    for i, todo in enumerate(data.get('toDoItems', [])):
        try:
            raw_todo_date = todo.get('date')
            todo_creation_time = parse_datetime_utc(raw_todo_date, config)
            if not todo_creation_time:
                logger.warning(
                    f"Standalone ToDo item at index {i} has missing/invalid date ('{raw_todo_date}'). "
                    f"Using placeholder timestamp: {UNDEFINED_TIMESTAMP.isoformat()}"
                )
                todo_creation_time = UNDEFINED_TIMESTAMP
            
            # For a standalone ToDo, the task itself is the only segment
            segments = [SessionSegment(
                segment_id=str(uuid.uuid4()),
                start_time_utc=todo_creation_time,
                end_time_utc=todo_creation_time,
                type="StandaloneToDo",
                author=todo.get('contact'),
                content=todo.get('task'),
                metadata={'completed': todo.get('completed')}
            )]

            session_object = Session(
                meta=SessionMeta(
                    session_id=str(uuid.uuid4()),
                    schema_version="2.0",
                    source_system="notes.json",
                    source_identifiers=[notes_file_path, f"/toDoItems/{i}"],
                    processing_status="Needs Linking",
                    ingestion_timestamp_utc=datetime.datetime.now(datetime.timezone.utc),
                    last_updated_timestamp_utc=datetime.datetime.now(datetime.timezone.utc)
                ),
                context=SessionContext(
                    customer_name=todo.get('customer'),
                    contact_name=todo.get('contact'),
                    # Explicitly set fields that will be populated by the linker
                    customer_id=None,
                    contact_id=None
                ),
                insights=SessionInsights(
                    session_start_time_utc=todo_creation_time,
                    session_end_time_utc=todo_creation_time,
                    session_duration_minutes=0,
                    source_title=todo.get('subject'),
                    # Explicitly set fields that will be populated by other processors
                    llm_generated_title=None,
                    user_notes=""
                ),
                segments=segments
            )
            
            save_session_to_file(session_object, config, logger)
            processed_items += 1

        except Exception as e:
            logger.error(f"Failed to process ToDo item at index {i}: {e}", exc_info=True)
            failed_items += 1

    logger.info(f"Finished NotesJSON ingestion. Total Success: {processed_items}, Total Failed: {failed_items}")
    
    # Update state only if all items were processed successfully
    if failed_items == 0 and current_metadata:
        ingestor_state[notes_file_path] = current_metadata
        _save_ingestor_state(ingestor_state, config, logger)