# -*- coding: utf-8 -*-
"""
This module uses an LLM to analyze and enrich V2 Session items.
It uses a configuration-driven approach to build prompts dynamically from session data.
"""

import os
from datetime import datetime, timezone
from typing import Any, Dict

from sdc.models.session_v2 import Session
from sdc.utils import session_handler
from sdc.llm import chat_api, prompts

def run_llm_analysis(config: Dict[str, Any], logger, analysis_type: str):
    """
    Iterates through Session files, uses an LLM to generate insights, and updates the files.

    Args:
        config: The application's configuration dictionary.
        logger: The SDC logger instance.
        analysis_type: The type of analysis to perform (e.g., 'title', 'summary').
    """
    analysis_configs = config.get('llm_configs', {}).get('analysis_tasks', {})
    analysis_config = analysis_configs.get(analysis_type)
    if not analysis_config:
        logger.critical(f"Invalid analysis type '{analysis_type}' passed to LLM analyzer. Aborting.")
        return

    output_target = analysis_config.get('output_target')
    if not output_target or 'type' not in output_target or 'key' not in output_target:
        logger.critical(f"Analysis config for '{analysis_type}' is missing a valid 'output_target'. Aborting.")
        return

    try:
        sessions_output_folder = config['project_paths']['sessions_output_folder']
    except KeyError as e:
        logger.critical(f"Configuration key missing: {e}. Aborting LLM analysis for '{analysis_type}'.")
        return

    logger.info(f"Starting V2 Session LLM analysis process for type: '{analysis_type}'.")

    processed_files, analyzed_files, error_files, skipped_files = 0, 0, 0, 0
    PROCESSOR_NAME = analysis_config.get('processor_name', f"session_llm_analyzer_{analysis_type}")

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
                skipped_files += 1
                continue

            # 3. Implement Source System Filtering
            applicable_source_systems = analysis_config.get('applicable_source_systems')
            if applicable_source_systems and session.meta.source_system not in applicable_source_systems:
                skipped_files += 1
                continue

            logger.info(f"Analyzing session {session.meta.session_id} for {analysis_type}...")

            chat_client = chat_api.get_chat_client(analysis_config['capability'], config, logger)
            if not chat_client:
                logger.error("Could not get LLM client. Skipping analysis for this session.")
                error_files += 1
                continue

            prompt_messages = prompts.build_prompt_messages(
                prompt_key=analysis_config['prompt_key'],
                config=config,
                logger=logger,
                session=session
            )

            if prompt_messages:
                response_content = chat_client.invoke(prompt_messages).content
                if isinstance(response_content, str) and response_content.strip():
                    clean_response = response_content.strip().strip('"')

                    # Implement Flexible Output Saving
                    target_type = output_target['type']
                    target_key = output_target['key']

                    if target_type == "comprehensive_json":
                        try:
                            # The response itself is a JSON string
                            parsed_json = json.loads(clean_response)
                            # Populate multiple fields from the single response
                            if 'title' in parsed_json:
                                session.insights.structured_llm_results['title'] = parsed_json['title']
                            if 'category' in parsed_json:
                                session.insights.structured_llm_results['category'] = parsed_json['category']
                            # Save the full JSON blob to its own summary key
                            session.insights.generated_summaries[target_key] = clean_response

                        except json.JSONDecodeError:
                            logger.error(f"Failed to parse JSON response for '{analysis_type}' on session {session.meta.session_id}. Response was: {clean_response}")
                            error_files += 1
                            continue

                    elif target_type == 'structured_llm_results':
                        session.insights.structured_llm_results[target_key] = clean_response
                    elif target_type == 'generated_summaries':
                        session.insights.generated_summaries[target_key] = clean_response
                    else:
                        logger.warning(f"Unknown output_target type '{target_type}' for analysis '{analysis_type}'. Result not saved.")
                        error_files += 1
                        continue

                    session.meta.processing_log.append(PROCESSOR_NAME)
                    session.meta.last_updated_timestamp_utc = datetime.now(timezone.utc)
                    session_handler.save_session_to_file(session, config, logger)
                    analyzed_files += 1
                    logger.info(f"Generated '{analysis_type}' for {session.meta.session_id} and saved to {target_type}.{target_key}")
            else:
                error_files += 1
                continue

    logger.info(f"LLM analysis for '{analysis_type}' finished. Scanned: {processed_files}, Analyzed: {analyzed_files}, Errors: {error_files}, Skipped: {skipped_files}")