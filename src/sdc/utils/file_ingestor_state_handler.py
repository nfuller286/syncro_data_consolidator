# -*- coding: utf-8 -*-
"""
Centralized utility for handling the state of file-based ingestors.
Manages loading, saving, and checking metadata for files to prevent re-processing.
"""

import os
import json
from typing import Any, Dict, Optional

def get_file_metadata(file_path: str) -> Dict[str, Any]:
    """Returns file size and modification time."""
    try:
        stat = os.stat(file_path)
        return {'size': stat.st_size, 'mtime': stat.st_mtime}
    except FileNotFoundError:
        return {}

def load_state(state_file_path: str, logger, default_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Loads an ingestor's state from a JSON file.

    Args:
        state_file_path: The full path to the state file.
        logger: The SDC logger instance.
        default_state: The state to return if the file is not found or invalid.
                       If None, an empty dictionary is returned.

    Returns:
        The loaded state as a dictionary.
    """
    if default_state is None:
        default_state = {}
    try:
        with open(state_file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, TypeError):
        logger.info(f"State file not found or invalid at {state_file_path}. Using default state.")
        return default_state

def save_state(state: Dict[str, Any], state_file_path: str, logger) -> None:
    """Saves the ingestor state to a JSON file using an atomic write operation."""
    temp_file_path = state_file_path + ".tmp"
    try:
        os.makedirs(os.path.dirname(state_file_path), exist_ok=True)
        with open(temp_file_path, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=4)
        os.replace(temp_file_path, state_file_path)
    except IOError as e:
        logger.error(f"Failed to save state to {state_file_path}: {e}")
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)