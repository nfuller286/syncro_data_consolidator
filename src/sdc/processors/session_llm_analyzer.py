# -*- coding: utf-8 -*-
"""
This module uses an LLM to analyze and enrich V2 Session items.
For example, it can generate a concise title based on the session's content.
"""

import os
from datetime import datetime, timezone
from typing import Any, Dict

from sdc.models.session_v2 import Session
from sdc.utils import session_handler, llm_utils


def analyze_sessions_with_llm(config: Dict[str, Any], logger):
    """
    Iterates through Session files, uses an LLM to generate insights, and updates the files.
    """
    logger.info("Starting V2 Session LLM analysis process.")

    try:
        sessions_output_folder = config['project_paths']['sessions_output_folder']
    except KeyError as e:
        logger.critical(f"Configuration key missing: {e}. Aborting LLM analysis.")
        return

    processed_files, analyzed_files, error_files, skipped_files = 0, 0, 0, 0
    
    # This is a placeholder for the version of this processor.
    PROCESSOR_NAME = "session_llm_analyzer_v1.0"

    with os.scandir(sessions_output_folder) as it:
        for entry in it:
            if not (entry.name.endswith('.json') and entry.is_file()):
                continue
            
            processed_files += 1
            session = session_handler.load_session_from_file(entry.path, logger)
            if not session:
                error_files += 1
                continue

            # 1. Skip if this processor has already run on this session
            if PROCESSOR_NAME in session.meta.processing_log:
                skipped_files += 1
                continue

            # 2. Skip if the session is in a state we don't want to analyze (e.g., needs linking)
            if session.meta.processing_status not in ['Linked', 'Complete', 'Reviewed']:
                logger.debug(f"Skipping session {session.meta.session_id} with status '{session.meta.processing_status}'.")
                skipped_files += 1
                continue

            logger.info(f"Analyzing session {session.meta.session_id}...")
            
            # --- LLM Analysis Logic ---
            # Example: Generate a concise title
            # You can build more complex logic here to summarize, categorize, etc.
            llm = llm_utils.get_llm_client('lightweight', config, logger)
            if not llm:
                logger.error("Could not get LLM client. Skipping analysis for this session.")
                error_files += 1
                continue

            # Create a simple representation of the content for the prompt
            content_for_prompt = "\n".join([f"{s.author}: {s.content}" for s in session.segments if s.content])
            prompt = f"Based on the following conversation, create a very short, concise title (less than 10 words) that summarizes the main topic.\n\n---\n{content_for_prompt}\n---\n\nTitle:"
            
            response = llm.invoke(prompt)
            if isinstance(response.content, str) and response.content.strip():
                session.insights.llm_generated_title = response.content.strip().strip('"')
                session.meta.processing_log.append(PROCESSOR_NAME)
                session.meta.last_updated_timestamp_utc = datetime.now(timezone.utc)
                session_handler.save_session_to_file(session, config, logger)
                analyzed_files += 1
                logger.info(f"Generated title for {session.meta.session_id}: '{session.insights.llm_generated_title}'")

    logger.info(f"LLM analysis finished. Scanned: {processed_files}, Analyzed: {analyzed_files}, Errors: {error_files}, Skipped: {skipped_files}")