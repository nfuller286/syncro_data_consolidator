# -*- coding: utf-8 -*-
"""
This module links unprocessed CUIS items to authoritative Syncro customers and contacts.
"""

import os
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from thefuzz import fuzz, process

from sdc.models.cuis_v1 import CUISV1
from sdc.utils import cuis_handler, llm_utils

def _find_winner_from_llm_response(llm_response: str, candidates: List[Any], match_key: Optional[str], logger) -> Optional[Any]:
    """
    Finds the winning item from a list of candidates based on the LLM's response.
    Can handle lists of dictionaries (customers) or lists of strings (contacts).
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

def link_customers_to_cuis(config: Dict[str, Any], logger):
    """
    Iterates through CUIS files, links them to Syncro customers and contacts, and updates the files.
    """
    logger.info("Starting CUIS customer and contact linking process.")

    try:
        cuis_output_folder = config['project_paths']['cuis_items_output_folder']
        fuzzy_threshold = config['processing_defaults']['customer_linking_fuzzy_match_threshold']
    except KeyError as e:
        logger.critical(f"Configuration key missing: {e}. Aborting linking process.")
        return

    customer_cache = cuis_handler.load_lean_customer_cache(config, logger)
    if not customer_cache:
        logger.critical("Failed to load lean customer cache. Aborting linking process.")
        return

    logger.info(f"Successfully loaded {len(customer_cache)} customers from lean cache.")

    processed_files, linked_files, error_files, skipped_files = 0, 0, 0, 0
    linked_by_exact, linked_by_fuzzy, linked_by_llm = 0, 0, 0

    with os.scandir(cuis_output_folder) as it:
        for entry in it:
            if not (entry.name.endswith('.json') and entry.is_file()):
                continue
            
            processed_files += 1
            cuis = cuis_handler.load_cuis_from_file(entry.path, logger)
            if not cuis:
                error_files += 1
                continue
            
            # --- REVISED LOGIC: Handle different states before attempting to link ---

            # 1. Skip if already linked or not in a 'new' state
            if cuis.sdc_core.sdc_processing_status != 'new':
                skipped_files += 1
                continue

            # 2. Skip if it's pre-linked (e.g., from Syncro ingestor)
            if cuis.entities_involved.syncro_customer_id_authoritative:
                logger.info(f"CUIS {cuis.sdc_core.sdc_cuis_id} is pre-linked to customer ID {cuis.entities_involved.syncro_customer_id_authoritative}. Skipping.")
                cuis.sdc_core.sdc_processing_status = 'linked' # Mark as processed
                cuis_handler.save_cuis_to_file(cuis, config, logger)
                skipped_files += 1
                continue

            # 3. Skip sources that are not expected to have customers
            unlinkable_sources = ['SillyTavern']
            if cuis.sdc_core.sdc_source_system in unlinkable_sources:
                logger.info(f"Skipping customer linking for CUIS from non-linkable source: {cuis.sdc_core.sdc_source_system}")
                skipped_files += 1
                continue

            winner = None
            guessed_name = cuis.entities_involved.syncro_customer_name_guessed

            if not guessed_name:
                logger.warning(f"CUIS {cuis.sdc_core.sdc_cuis_id} has no guessed customer name. Setting to error.")
                cuis.sdc_core.sdc_processing_status = 'error'
                error_files += 1
                cuis_handler.save_cuis_to_file(cuis, config, logger)
                continue

            # --- Proceed with linking logic ---
            logger.info(f"Processing CUIS {cuis.sdc_core.sdc_cuis_id} for guessed name: '{guessed_name}'")
            
            # 1. Check for an exact match
            exact_matches = [c for c in customer_cache if c.get('business_name', '').lower() == guessed_name.lower()]
            if len(exact_matches) == 1:
                winner = exact_matches[0]
                logger.info(f"Found single exact match for '{guessed_name}': '{winner.get('business_name')}'")
                linked_by_exact += 1
            
            # 2. If no exact match, find best potential matches to analyze
            if not winner:
                # Create a dictionary of choices for efficient lookup
                choices = {c['business_name']: c for c in customer_cache if c.get('business_name')}
                # Use process.extract to find the top 5 candidates
                top_matches = process.extract(guessed_name, choices.keys(), limit=5, scorer=fuzz.token_set_ratio)

                # Filter out matches below a minimum viability score to avoid garbage candidates
                viable_matches = [m for m in top_matches if m[1] >= 60]

                if not viable_matches:
                    logger.warning(f"No plausible matches found for '{guessed_name}' (best score < 60).")
                else:
                    best_match_name, best_score = viable_matches[0]
                    
                    # Auto-link if we have a single, high-confidence match (above the config threshold)
                    if len(viable_matches) == 1 and best_score >= fuzzy_threshold:
                        winner = choices[best_match_name]
                        logger.info(f"Found single high-confidence fuzzy match for '{guessed_name}': '{best_match_name}' with score {best_score}.")
                        linked_by_fuzzy += 1
                    # Or if the best match is high-confidence and significantly better than the next
                    elif len(viable_matches) > 1 and best_score >= fuzzy_threshold and (best_score - viable_matches[1][1] > 10):
                        winner = choices[best_match_name]
                        logger.info(f"Found clear high-confidence fuzzy match for '{guessed_name}': '{best_match_name}' (score {best_score}) over next best (score {viable_matches[1][1]}).")
                        linked_by_fuzzy += 1
                    else:
                        # In all other ambiguous cases, use the LLM as a fallback
                        candidate_customers = [choices[m[0]] for m in viable_matches]
                        logger.info(f"Found {len(candidate_customers)} ambiguous matches for '{guessed_name}'. Attempting LLM disambiguation using 'lightweight' model.")
                        llm = llm_utils.get_llm_client('lightweight', config, logger)
                        if llm:
                            candidate_names = [c['business_name'] for c in candidate_customers]
                            prompt = f"""From the following list of company names:\n{json.dumps(candidate_names, indent=2)}\n\nWhich one is the most likely match for the name: "{guessed_name}"?\n\nPlease respond with only the single, best-matching company name from the list provided."""
                            logger.debug(f"LLM Disambiguation Prompt:\n{prompt}") # The method to call the LLM is now .invoke()
                            response = llm.invoke(prompt)
                            if isinstance(response.content, str):
                                winner = _find_winner_from_llm_response(response.content, candidate_customers, 'business_name', logger)
                                if winner:
                                    linked_by_llm += 1
                            else:
                                logger.warning(f"LLM returned a non-string response content for customer disambiguation: {response.content}")

            if winner:
                cuis.entities_involved.syncro_customer_id_authoritative = winner.get('id')
                cuis.entities_involved.syncro_customer_name_authoritative = winner.get('business_name')
                cuis.sdc_core.sdc_processing_status = 'linked'
                linked_files += 1
                logger.info(f"Successfully linked CUIS to customer '{winner.get('business_name')}'")
                
                # --- REFACTORED & ENHANCED CONTACT LINKING ---
                guessed_contact = cuis.entities_involved.syncro_contact_name_guessed
                known_contacts = winner.get('contacts', [])
                if guessed_contact and known_contacts:
                    logger.info(f"Attempting to link contact '{guessed_contact}' for customer '{winner.get('business_name')}'")
                    
                    # Use the same intelligent logic as customer linking
                    top_contact_matches = process.extract(guessed_contact, known_contacts, limit=3, scorer=fuzz.token_set_ratio)
                    viable_contact_matches = [m for m in top_contact_matches if m[1] >= 60]

                    contact_winner = None
                    if not viable_contact_matches:
                        logger.warning(f"No plausible contact match found for '{guessed_contact}'.")
                    elif len(viable_contact_matches) == 1 and viable_contact_matches[0][1] >= fuzzy_threshold:
                        contact_winner = viable_contact_matches[0][0]
                        logger.info(f"Found single high-confidence contact match: '{contact_winner}' with score {viable_contact_matches[0][1]}")
                    elif len(viable_contact_matches) > 1 and viable_contact_matches[0][1] >= fuzzy_threshold and (viable_contact_matches[0][1] - viable_contact_matches[1][1] > 10):
                        contact_winner = viable_contact_matches[0][0]
                        logger.info(f"Found clear high-confidence contact match: '{contact_winner}' (score {viable_contact_matches[0][1]}) over next best (score {viable_contact_matches[1][1]}).")
                    else:
                        # Fallback to LLM for ambiguous contacts
                        candidate_contacts = [m[0] for m in viable_contact_matches]
                        logger.info(f"Found {len(candidate_contacts)} ambiguous contact matches for '{guessed_contact}'. Attempting LLM disambiguation.")
                        llm = llm_utils.get_llm_client('lightweight', config, logger)
                        if llm:
                            prompt = f"""From the following list of contact names:\n{json.dumps(candidate_contacts, indent=2)}\n\nWhich one is the most likely match for the name: "{guessed_contact}"?\n\nPlease respond with only the single, best-matching name from the list provided."""
                            response = llm.invoke(prompt)
                            if isinstance(response.content, str):
                                contact_winner = _find_winner_from_llm_response(response.content, candidate_contacts, None, logger)
                            else:
                                logger.warning(f"LLM returned a non-string response content for contact disambiguation: {response.content}")

                    if contact_winner:
                        cuis.entities_involved.syncro_contact_name_authoritative = contact_winner
                        logger.info(f"Successfully linked contact to '{contact_winner}'.")
                    else:
                        logger.warning(f"Could not confidently link contact '{guessed_contact}'.")
                elif guessed_contact:
                    logger.warning(f"Contact linking skipped: Customer '{winner.get('business_name')}' has no contacts in cache.")
            else:
                logger.warning(f"Could not link CUIS {cuis.sdc_core.sdc_cuis_id} for guessed name '{guessed_name}'. Setting to error.")
                cuis.sdc_core.sdc_processing_status = 'error'
                error_files += 1

            cuis.sdc_core.sdc_last_updated_timestamp_utc = datetime.now(timezone.utc)
            cuis_handler.save_cuis_to_file(cuis, config, logger)

    summary_msg = (
        f"CUIS linking finished. Scanned: {processed_files}, "
        f"Linked: {linked_files} (Exact: {linked_by_exact}, Fuzzy: {linked_by_fuzzy}, LLM: {linked_by_llm}), "
        f"Errors: {error_files}, Skipped: {skipped_files}"
    )
    logger.info(summary_msg)
