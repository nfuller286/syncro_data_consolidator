# -*- coding: utf-8 -*-
"""Ingestor for data from the legacy notes.json file format."""

import json
import os
from typing import Any, Dict

from sdc.models.cuis_v1 import CUISV1, CuisEntry
from sdc.utils.cuis_handler import save_cuis_to_file
from sdc.utils.date_utils import parse_datetime_utc
from sdc.utils.sdc_logger import get_sdc_logger

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

def ingest_notes(config: Dict[str, Any]) -> None:
    """
    Loads data from notes.json, transforms it into CUIS format, and saves it.
    """
    logger = get_sdc_logger(__name__, config)
    logger.info("Starting ingestion for source: NotesJSON")

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

    # Process tickets
    for ticket in data.get('tickets', []):
        try:
            ticket_number = ticket.get('ticketNumber')
            if not ticket_number:
                logger.warning("Skipping ticket with no ticketNumber.")
                failed_items += 1
                continue

            cuis_item = CUISV1()
            cuis_item.sdc_core.sdc_source_system = 'NotesJSON'
            cuis_item.sdc_core.sdc_source_sub_type = 'NotesJSON_Ticket'
            cuis_item.sdc_core.sdc_source_primary_id = str(ticket_number)
            cuis_item.sdc_core.sdc_source_file_path = notes_file_path

            cuis_item.core_content.summary_title_or_subject = ticket.get('subject')
            cuis_item.core_content.primary_text_content = ticket.get('initial_issue')
            cuis_item.core_content.creation_timestamp_utc = parse_datetime_utc(ticket.get('date'), config)

            cuis_item.entities_involved.syncro_customer_name_guessed = ticket.get('customer')
            if ticket.get('contact'):
                cuis_item.entities_involved.syncro_contact_name_guessed = ticket['contact']

            # --- ENHANCEMENT: Process sub-notes and to-dos ---
            for sub_note in ticket.get('notes', []):
                # Correctly parse structured note objects
                entry = CuisEntry(
                    entry_type_source="Note",
                    entry_body_text=sub_note.get('note'),
                    entry_order=sub_note.get('order'),
                    entry_timestamp_utc=parse_datetime_utc(sub_note.get('date'), config)
                )
                cuis_item.cuis_entries.append(entry)
            
            for sub_todo in ticket.get('to-do', []):
                # Correctly parse structured to-do objects, which have a 'task' key
                entry = CuisEntry(
                    entry_type_source="ToDo",
                    entry_body_text=f"To-Do: {sub_todo.get('task')}",
                    entry_order=sub_todo.get('order'),
                    entry_timestamp_utc=parse_datetime_utc(sub_todo.get('date'), config)
                )
                cuis_item.cuis_entries.append(entry)

            # --- Populate source_specific_details as per CUIS definition ---
            cuis_item.source_specific_details['notesjson_original_ticket_number'] = ticket.get('ticketNumber')
            cuis_item.source_specific_details['notesjson_original_status'] = ticket.get('status')
            cuis_item.source_specific_details['notesjson_original_priority'] = ticket.get('priority')


            save_cuis_to_file(cuis_item, config, logger)
            processed_items += 1

        except Exception as e:
            logger.error(f"Failed to process ticket {ticket.get('ticketNumber', 'N/A')}: {e}", exc_info=True)
            failed_items += 1

    # Process ToDo items
    for i, todo in enumerate(data.get('toDoItems', [])):
        try:
            cuis_item = CUISV1()
            cuis_item.sdc_core.sdc_source_system = 'NotesJSON'
            cuis_item.sdc_core.sdc_source_sub_type = 'NotesJSON_ToDo'
            cuis_item.sdc_core.sdc_source_primary_id = f"todo_{i}"
            cuis_item.sdc_core.sdc_source_file_path = notes_file_path
            
            # Correctly map fields from the root toDoItems
            cuis_item.core_content.summary_title_or_subject = todo.get('subject')
            cuis_item.core_content.primary_text_content = todo.get('task')
            cuis_item.core_content.creation_timestamp_utc = parse_datetime_utc(todo.get('date'), config)
            cuis_item.categorization.original_status_from_source = 'Completed' if todo.get('completed') else 'Open'

            cuis_item.entities_involved.syncro_customer_name_guessed = todo.get('customer')
            cuis_item.entities_involved.syncro_contact_name_guessed = todo.get('contact')

            save_cuis_to_file(cuis_item, config, logger)
            processed_items += 1

        except Exception as e:
            logger.error(f"Failed to process ToDo item at index {i}: {e}", exc_info=True)
            failed_items += 1

    logger.info(f"Finished NotesJSON ingestion. Total Success: {processed_items}, Total Failed: {failed_items}")
    
    # Update state only if processing was successful
    if failed_items == 0:
        ingestor_state[notes_file_path] = current_metadata
        _save_ingestor_state(ingestor_state, config, logger)
