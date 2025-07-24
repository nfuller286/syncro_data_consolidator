# -*- coding: utf-8 -*-
"""
Utility for handling V2 Session objects, such as saving and loading them.
This is the V2 equivalent of the cuis_handler.py.
"""

import os
import json
from typing import Any, Dict, Optional

# Import the new V2 Session model
from sdc.models.session_v2 import Session

def save_session_to_file(session_object: Session, config: Dict[str, Any], logger) -> None:
    """
    Serializes a Session Pydantic object to a JSON file.

    Args:
        session_object: The Session object to save.
        config: The application's configuration dictionary.
        logger: The SDC logger instance.
    """
    try:
        # Use the new config key for the V2 output folder
        output_dir = config['project_paths']['sessions_output_folder']
        os.makedirs(output_dir, exist_ok=True)
        
        # Use the session_id from the meta block for a unique filename
        filename = f"{session_object.meta.session_id}.json"
        file_path = os.path.join(output_dir, filename)
        
        logger.info(f"Saving Session item to: {file_path}")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(session_object.model_dump_json(indent=4))
        
        logger.info(f"Successfully saved Session item {session_object.meta.session_id}")

    except KeyError as e:
        logger.error(f"Configuration key error in save_session_to_file: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred in save_session_to_file for {session_object.meta.session_id}: {e}")

def load_session_from_file(file_path: str, logger) -> Optional[Session]:
    """
    Loads a single Session JSON file and parses it into a Session Pydantic object.

    Args:
        file_path: The full path to the Session JSON file.
        logger: The SDC logger instance for logging.

    Returns:
        A Session object if loading and parsing are successful, otherwise None.
    """
    try:
        logger.debug(f"Attempting to load Session file: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Validate the data against the new Session model
        session_object = Session.model_validate(data)
        
        logger.debug(f"Successfully loaded and validated Session file: {file_path}")
        return session_object

    except FileNotFoundError:
        logger.error(f"Session file not found at: {file_path}")
        return None
    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON from Session file: {file_path}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while loading Session file {file_path}: {e}")
        return None