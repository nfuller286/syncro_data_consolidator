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
    Loads an ingestor's state from a JSON file. If the file does not exist,
    it is created with the default state.

    Args:
        state_file_path: The full path to the state file.
        logger: The SDC logger instance.
        default_state: The state to return and save if the file is not found or invalid.
                       If None, an empty dictionary is used.

    Returns:
        The loaded state as a dictionary.
    """
    if default_state is None:
        default_state = {}
    try:
        with open(state_file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.info(f"State file not found at {state_file_path}. Creating it with default state.")
        save_state(default_state, state_file_path, logger)
        return default_state
    except (json.JSONDecodeError, TypeError):
        logger.warning(f"State file at {state_file_path} is invalid. Using default state.")
        return default_state

def verify_writability(state_file_path: str, logger) -> bool:
    """
    Verifies that the state file path is writable.

    This is a "fail-fast" check. It ensures that the directory exists and that
    a file can be created at the specified path before any main processing begins.

    Args:
        state_file_path: The full path to the state file.
        logger: The SDC logger instance.

    Returns:
        True if the path is writable, False otherwise.
    """
    try:
        # Ensure the parent directory exists
        os.makedirs(os.path.dirname(state_file_path), exist_ok=True)
        # Test writability by opening in append mode. This creates the file if it
        # doesn't exist without truncating it if it does.
        with open(state_file_path, 'a', encoding='utf-8'):
            pass
        return True
    except (IOError, PermissionError) as e:
        logger.error(
            f"State file path at {state_file_path} is not writable. "
            f"Aborting operation. Please check directory permissions. Error: {e}"
        )
        return False


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