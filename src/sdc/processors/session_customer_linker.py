# -*- coding: utf-8 -*-
"""
This module links unprocessed V2 Session items to authoritative Syncro customers and contacts.
This is the V2 equivalent of cuis_customer_linker.py.
"""

import os
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from thefuzz import fuzz, process

# --- V2 IMPORTS ---
from sdc.models.session_v2 import Session
from sdc.utils import session_handler, cache_utils
from sdc.llm import chat_api, prompts

# --- HELPER FUNCTION (UNCHANGED) ---
# This function is generic and does not need to be modified.
def _find_winner_from_llm_response(llm_response: str, candidates: List[Any], match_key: Optional[str], logger) -> Optional[Any]:
    """
    Finds the winning item from a list of candidates based on the LLM's response.
    """
    llm_winner_name = llm_response.strip().lower()
    for candidate in candidates:
        candidate_name = ""
        if isinstance(candidate, dict) and match_key:
            candidate_name = candidate.get(match_key, '').strip().lower()
        elif isinstance(candidate, str):
            candidate_name = candidate.strip().lower()

        if candidate_name == llm_winner_name:
            logger.info(f"LLM successfully disambiguated and selected: '{llm_response.strip()}'")
            return candidate

    candidate_names_for_log = [c.get(match_key) if isinstance(c, dict) else c for c in candidates]
    logger.error(f"LLM response '{llm_response.strip()}' did not match any of the provided candidate names. Candidates were: {candidate_names_for_log}")
    return None

def _find_best_match(
    guessed_name: str,
    candidates: List[Dict[str, Any]],
    match_key: str,
    item_type: str,
    config: Dict[str, Any],
    logger
) -> Optional[Dict[str, Any]]:
    """
    Finds the best candidate match for a guessed name using exact, fuzzy, and LLM-based logic.
    """
    winner = None
    fuzzy_threshold = config['processing_defaults']['customer_linking_fuzzy_match_threshold']

    # Step 1: Exact Match
    exact_matches = [c for c in candidates if c.get(match_key, '').lower() == guessed_name.lower()]
    if len(exact_matches) == 1:
        winner = exact_matches[0]
        logger.info(f"Found single exact match for {item_type} '{guessed_name}': '{winner.get(match_key)}'")
        return winner

    # Step 2: Fuzzy Match and LLM Disambiguation
    choices = {c[match_key]: c for c in candidates if c.get(match_key)}
    if not choices:
        logger.warning(f"No candidates with a '{match_key}' to match against for {item_type} '{guessed_name}'.")
        return None

    top_matches = process.extract(guessed_name, choices.keys(), limit=5, scorer=fuzz.token_set_ratio)
    viable_matches = [m for m in top_matches if m[1] >= 60]

    if not viable_matches:
        logger.warning(f"No plausible {item_type} matches found for '{guessed_name}' (best score < 60).")
        return None

    best_match_name, best_score = viable_matches[0]

    if len(viable_matches) == 1 and best_score >= fuzzy_threshold:
        winner = choices[best_match_name]
        logger.info(f"Found single high-confidence fuzzy match for {item_type} '{guessed_name}': '{best_match_name}' with score {best_score}.")
    elif len(viable_matches) > 1 and best_score >= fuzzy_threshold and (best_score - viable_matches[1][1] > 10):
        winner = choices[best_match_name]
        logger.info(f"Found clear high-confidence fuzzy match for {item_type} '{guessed_name}': '{best_match_name}' (score {best_score}) over next best (score {viable_matches[1][1]}).")
    else:
        # Ambiguous case, requires LLM
        candidate_dicts = [choices[m[0]] for m in viable_matches]
        logger.info(f"Found {len(candidate_dicts)} ambiguous {item_type} matches for '{guessed_name}'. Attempting LLM disambiguation.")
        chat_client = chat_api.get_chat_client('lightweight', config, logger)
        if chat_client:
            candidate_names = [c[match_key] for c in candidate_dicts]
            prompt_messages = prompts.build_prompt_messages(
                prompt_key='data_linking.disambiguation', config=config, logger=logger,
                item_type=item_type, guessed_name=guessed_name, candidate_names=candidate_names
            )
            if prompt_messages:
                response = chat_client.invoke(prompt_messages)
                if isinstance(response.content, str):
                    winner = _find_winner_from_llm_response(response.content, candidate_dicts, match_key, logger)
    return winner

# =================================================================================
#  REFACTORED MAIN LINKER FUNCTION
# =================================================================================
def link_customers_to_sessions(config: Dict[str, Any], logger):
    """
    Iterates through Session files, links them to Syncro customers and contacts, and updates the files.
    """
    logger.info("Starting V2 Session customer and contact linking process.")

    try:
        # CHANGED: Point to the new sessions output folder
        sessions_output_folder = config['project_paths']['sessions_output_folder']
        fuzzy_threshold = config['processing_defaults']['customer_linking_fuzzy_match_threshold']
    except KeyError as e:
        logger.critical(f"Configuration key missing: {e}. Aborting linking process.")
        return

    # NOTE: The lean customer cache is generic and can be reused without changes.
    customer_cache = cache_utils.load_lean_customer_cache(config, logger)
    if not customer_cache:
        logger.critical("Failed to load lean customer cache. Aborting linking process.")
        return

    logger.info(f"Successfully loaded {len(customer_cache)} customers from lean cache.")

    processed_files, linked_files, error_files, skipped_files = 0, 0, 0, 0

    # In-memory cache for this run to avoid re-processing the same names.
    # This is especially useful for sources like ScreenConnect with repeated, non-standard names.
    customer_link_cache: Dict[str, Optional[Dict[str, Any]]] = {}
    contact_link_cache: Dict[tuple[str, str], Optional[Dict[str, Any]]] = {}

    with os.scandir(sessions_output_folder) as it:
        for entry in it:
            if not (entry.name.endswith('.json') and entry.is_file()):
                continue
            
            processed_files += 1
            # CHANGED: Load a Session object using the new handler
            session = session_handler.load_session_from_file(entry.path, logger)
            if not session:
                error_files += 1
                continue
            
            # --- REVISED LOGIC FOR V2 MODEL ---

            # 1. Skip if not in the 'Needs Linking' state
            # CHANGED: Path to processing status field
            if session.meta.processing_status != 'Needs Linking':
                logger.info(f"Skipping session {session.meta.session_id} because its status is '{session.meta.processing_status}' (not 'Needs Linking').")
                skipped_files += 1
                continue

            # 2. Skip sources that are not expected to have customers
            unlinkable_sources = ['SillyTavern'] # This list can be expanded
            if session.meta.source_system in unlinkable_sources:
                logger.info(f"Skipping customer linking for Session from non-linkable source: {session.meta.source_system}")
                skipped_files += 1
                continue

            winner = None
            # CHANGED: Path to guessed customer name
            guessed_name = session.context.customer_name

            if not guessed_name:
                logger.warning(f"Session {session.meta.session_id} has no guessed customer name. Setting to error.")
                session.meta.processing_status = 'error'
                error_files += 1
                session_handler.save_session_to_file(session, config, logger)
                continue

            # --- Customer Linking with Caching ---
            if guessed_name in customer_link_cache:
                winner = customer_link_cache[guessed_name]
                if winner:
                    logger.info(f"Using cached link for customer '{guessed_name}' -> '{winner.get('business_name', 'N/A')}'")
                else:
                    logger.info(f"Using cached result for customer '{guessed_name}': No link found.")
            else:
                logger.info(f"Processing Session {session.meta.session_id} for new guessed name: '{guessed_name}'")
                winner = _find_best_match(
                    guessed_name=guessed_name,
                    candidates=customer_cache,
                    match_key='business_name',
                    item_type='company',
                    config=config,
                    logger=logger
                )

                # Cache the result (even if it's None) to prevent re-processing
                customer_link_cache[guessed_name] = winner

            if winner:
                # CHANGED: Update the Session object's context
                session.context.customer_id = winner.get('id')
                session.context.customer_name = winner.get('business_name') # Overwrite with authoritative name
                session.meta.processing_status = 'Linked' # Use new status
                linked_files += 1
                logger.info(f"Successfully linked Session to customer '{winner.get('business_name')}'")
                
                # --- Contact Linking (Adapted for Session model) ---
                guessed_contact = session.context.contact_name
                known_contacts = winner.get('contacts', [])
                authoritative_customer_name = winner.get('business_name', 'Unknown Customer')

                if guessed_contact and known_contacts and authoritative_customer_name:
                    contact_cache_key = (authoritative_customer_name, guessed_contact)
                    
                    if contact_cache_key in contact_link_cache:
                        contact_winner_obj = contact_link_cache[contact_cache_key]
                        if contact_winner_obj:
                            logger.info(f"Using cached link for contact '{guessed_contact}' -> '{contact_winner_obj.get('name', 'N/A')}'")
                        else:
                            logger.info(f"Using cached result for contact '{guessed_contact}': No link found.")
                    else:
                        logger.info(f"Attempting to link new contact '{guessed_contact}' for customer '{authoritative_customer_name}'")
                        contact_winner_obj = _find_best_match(
                            guessed_name=guessed_contact,
                            candidates=known_contacts,
                            match_key='name',
                            item_type='contact',
                            config=config,
                            logger=logger
                        )

                        # Cache the contact linking result
                        contact_link_cache[contact_cache_key] = contact_winner_obj

                    # This block runs for both cached and new results
                    if contact_winner_obj:
                        session.context.contact_id = contact_winner_obj.get('id')
                        session.context.contact_name = contact_winner_obj.get('name')
                        logger.info(f"Successfully linked contact to '{contact_winner_obj['name']}' (ID: {contact_winner_obj.get('id')}).")

                elif guessed_contact:
                    logger.warning(f"Contact linking skipped: Customer '{authoritative_customer_name}' has no contacts in cache.")

            else:
                logger.warning(f"Could not link Session {session.meta.session_id} for guessed name '{guessed_name}'. Setting to error.")
                session.meta.processing_status = 'error'
                error_files += 1

            # CHANGED: Update the Session's last_updated timestamp
            session.meta.last_updated_timestamp_utc = datetime.now(timezone.utc)
            # CHANGED: Save the Session object using the new handler
            session_handler.save_session_to_file(session, config, logger)

    summary_msg = (
        f"Session linking finished. Scanned: {processed_files}, "
        f"Linked: {linked_files}, "
        f"Errors: {error_files}, Skipped: {skipped_files}"
    )
    logger.info(summary_msg)