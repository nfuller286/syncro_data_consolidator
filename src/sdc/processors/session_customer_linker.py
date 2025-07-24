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
from sdc.utils import session_handler, llm_utils, cuis_handler # Still need cuis_handler for the lean cache

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
    customer_cache = cuis_handler.load_lean_customer_cache(config, logger)
    if not customer_cache:
        logger.critical("Failed to load lean customer cache. Aborting linking process.")
        return

    logger.info(f"Successfully loaded {len(customer_cache)} customers from lean cache.")

    processed_files, linked_files, error_files, skipped_files = 0, 0, 0, 0
    linked_by_exact, linked_by_fuzzy, linked_by_llm = 0, 0, 0

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
                
                # Step 1: Exact Match
                exact_matches = [c for c in customer_cache if c.get('business_name', '').lower() == guessed_name.lower()]
                if len(exact_matches) == 1:
                    winner = exact_matches[0]
                    logger.info(f"Found single exact match: '{winner.get('business_name')}'")
                    linked_by_exact += 1
                
                # Step 2: Fuzzy Match and LLM Disambiguation
                if not winner:
                    choices = {c['business_name']: c for c in customer_cache if c.get('business_name')}
                    top_matches = process.extract(guessed_name, choices.keys(), limit=5, scorer=fuzz.token_set_ratio)
                    viable_matches = [m for m in top_matches if m[1] >= 60]

                    if not viable_matches:
                        logger.warning(f"No plausible matches found for '{guessed_name}' (best score < 60).")
                    else:
                        best_match_name, best_score = viable_matches[0]
                        
                        if len(viable_matches) == 1 and best_score >= fuzzy_threshold:
                            winner = choices[best_match_name]
                            logger.info(f"Found single high-confidence fuzzy match: '{best_match_name}' with score {best_score}.")
                            linked_by_fuzzy += 1
                        elif len(viable_matches) > 1 and best_score >= fuzzy_threshold and (best_score - viable_matches[1][1] > 10):
                            winner = choices[best_match_name]
                            logger.info(f"Found clear high-confidence fuzzy match: '{best_match_name}' (score {best_score}) over next best (score {viable_matches[1][1]}).")
                            linked_by_fuzzy += 1
                        else:
                            candidate_customers = [choices[m[0]] for m in viable_matches]
                            logger.info(f"Found {len(candidate_customers)} ambiguous matches for '{guessed_name}'. Attempting LLM disambiguation.")
                            llm = llm_utils.get_llm_client('lightweight', config, logger)
                            if llm:
                                candidate_names = [c['business_name'] for c in candidate_customers]
                                prompt = f"""From the following list of company names:\n{json.dumps(candidate_names, indent=2)}\n\nWhich one is the most likely match for the name: "{guessed_name}"?\n\nPlease respond with only the single, best-matching company name from the list provided."""
                                response = llm.invoke(prompt)
                                if isinstance(response.content, str):
                                    winner = _find_winner_from_llm_response(response.content, candidate_customers, 'business_name', logger)
                                    if winner:
                                        linked_by_llm += 1
                
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
                        contact_choices = {c['name']: c for c in known_contacts if c.get('name')}
                        top_contact_matches = process.extract(guessed_contact, contact_choices.keys(), limit=3, scorer=fuzz.token_set_ratio)
                        viable_contact_matches = [m for m in top_contact_matches if m[1] >= 60]

                        contact_winner_obj = None
                        if not viable_contact_matches:
                            logger.warning(f"No plausible contact match found for '{guessed_contact}'.")
                        elif len(viable_contact_matches) == 1 and viable_contact_matches[0][1] >= fuzzy_threshold:
                            contact_winner_obj = contact_choices[viable_contact_matches[0][0]]
                            logger.info(f"Found single high-confidence contact match: '{contact_winner_obj['name']}' with score {viable_contact_matches[0][1]}")
                        elif len(viable_contact_matches) > 1 and viable_contact_matches[0][1] >= fuzzy_threshold and (viable_contact_matches[0][1] - viable_contact_matches[1][1] > 10):
                            contact_winner_obj = contact_choices[viable_contact_matches[0][0]]
                            logger.info(f"Found clear high-confidence contact match: '{contact_winner_obj['name']}' (score {viable_contact_matches[0][1]}) over next best (score {viable_contact_matches[1][1]}).")
                        else:
                            candidate_contact_dicts = [contact_choices[m[0]] for m in viable_contact_matches]
                            logger.info(f"Found {len(candidate_contact_dicts)} ambiguous contact matches for '{guessed_contact}'. Attempting LLM disambiguation.")
                            llm = llm_utils.get_llm_client('lightweight', config, logger)
                            if llm:
                                candidate_contact_names = [c['name'] for c in candidate_contact_dicts]
                                prompt = f"""From the following list of contact names:\n{json.dumps(candidate_contact_names, indent=2)}\n\nWhich one is the most likely match for the name: "{guessed_contact}"?\n\nPlease respond with only the single, best-matching name from the list provided."""
                                response = llm.invoke(prompt)
                                if isinstance(response.content, str):
                                    contact_winner_obj = _find_winner_from_llm_response(response.content, candidate_contact_dicts, 'name', logger)
                        
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
        f"Linked: {linked_files} (Exact: {linked_by_exact}, Fuzzy: {linked_by_fuzzy}, LLM: {linked_by_llm}), "
        f"Errors: {error_files}, Skipped: {skipped_files}"
    )
    logger.info(summary_msg)