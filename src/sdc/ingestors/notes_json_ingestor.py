# -*- coding: utf-8 -*-
"""Ingestor for data from the legacy notes.json file format."""

import json
import os
import uuid
from typing import Any, Dict

# --- V2 IMPORTS ---
# Import the new Session models and the new session handler
from sdc.models.session_v2 import Session, SessionSegment, SessionMeta, SessionContext, SessionInsights
from sdc.utils.session_handler import save_session_to_file
# --- SHARED UTILS ---
from sdc.utils import file_ingestor_state_handler as state_handler
from sdc.utils.date_utils import parse_datetime_utc
from sdc.utils.session_builder import build_session
from sdc.utils.sdc_logger import get_sdc_logger
from sdc.utils.constants import UNDEFINED_TIMESTAMP

# --- CONSTANTS ---
STATE_FILE_NAME = 'notes_json_ingestor_state.json'

# =================================================================================
#  HELPER FUNCTIONS - PURE LOGIC
# =================================================================================

def _transform_ticket_to_session(
    ticket: Dict[str, Any],
    index: int,
    notes_file_path: str,
    config: Dict[str, Any],
    logger
) -> Session:
    """Transforms a single ticket dictionary into a V2 Session object."""
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

    return build_session(
        segments=segments,
        source_system="notes.json",
        source_identifiers=[notes_file_path, f"/tickets/{index}"],
        customer_name=ticket.get('customer'),
        contact_name=ticket.get('contact'),
        source_title=ticket.get('subject')
        # processing_status defaults to "Needs Linking", which is correct here
    )

def _transform_todo_to_session(
    todo: Dict[str, Any],
    index: int,
    notes_file_path: str,
    config: Dict[str, Any],
    logger
) -> Session:
    """Transforms a single standalone ToDo dictionary into a V2 Session object."""
    raw_todo_date = todo.get('date')
    todo_creation_time = parse_datetime_utc(raw_todo_date, config) or UNDEFINED_TIMESTAMP
    
    segments = [SessionSegment(
        segment_id=str(uuid.uuid4()), start_time_utc=todo_creation_time, end_time_utc=todo_creation_time,
        type="StandaloneToDo", author=todo.get('contact'), content=todo.get('task'),
        metadata={'completed': todo.get('completed')}
    )]

    return build_session(
        segments=segments,
        source_system="notes.json",
        source_identifiers=[notes_file_path, f"/toDoItems/{index}"],
        customer_name=todo.get('customer'),
        contact_name=todo.get('contact'),
        source_title=todo.get('subject')
        # processing_status defaults to "Needs Linking", which is correct here
    )

# =================================================================================
#  REFACTORED INGESTION FUNCTION
# =================================================================================
def ingest_notes(config: Dict[str, Any], logger) -> None:
    """
    Loads data from notes.json, transforms it into the V2 Session format, and saves it.
    """
    logger.info("Starting ingestion for source: NotesJSON")

    notes_file_path = config['project_paths']['notes_json']
    state_file_path = os.path.join(config['project_paths']['cache_folder'], STATE_FILE_NAME)
    current_metadata = state_handler.get_file_metadata(notes_file_path)
    ingestor_state = state_handler.load_state(state_file_path, logger)

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
            session_object = _transform_ticket_to_session(ticket, index, notes_file_path, config, logger)
            save_session_to_file(session_object, config, logger)
            processed_items += 1
        except Exception as e:
            logger.error(f"Failed to process ticket {ticket.get('ticketNumber', 'N/A')}: {e}", exc_info=True)
            failed_items += 1

    # --- Process standalone ToDo items ---
    for index, todo in enumerate(data.get('toDoItems', [])):
        try:
            session_object = _transform_todo_to_session(todo, index, notes_file_path, config, logger)
            save_session_to_file(session_object, config, logger)
            processed_items += 1
        except Exception as e:
            logger.error(f"Failed to process ToDo item at index {index}: {e}", exc_info=True)
            failed_items += 1

    logger.info(f"Finished NotesJSON ingestion. Total Success: {processed_items}, Total Failed: {failed_items}")
    
    # Update state only if all items were processed successfully
    if failed_items == 0 and current_metadata:
        ingestor_state[notes_file_path] = current_metadata
        state_handler.save_state(ingestor_state, state_file_path, logger)