# -*- coding: utf-8 -*-
"""
Utility for loading and parsing the project's configuration file.
"""

import json
import os
import re
from typing import Dict, Any, Optional, Union, List

_cached_config: Optional[Dict[str, Any]] = None

def _resolve_placeholders_recursive(obj: Union[Dict, List], templates: Dict[str, str]) -> bool:
    """
    Recursively traverses a dictionary or list to resolve placeholders.

    Args:
        obj: The dictionary or list to process.
        templates: A dictionary of placeholder keys and their resolved values.

    Returns:
        True if any placeholder was resolved in this pass, otherwise False.
    """
    unresolved_found_in_pass = False
    iterator = obj.items() if isinstance(obj, dict) else enumerate(obj)

    for key, value in iterator:
        if isinstance(value, str):
            placeholders = re.findall(r'{{(\w+)}}', value)
            if not placeholders:
                continue

            for placeholder in placeholders:
                if placeholder in templates:
                    # Replace and normalize path if it's a path placeholder
                    replacement = str(templates[placeholder])
                    new_value = value.replace(f'{{{{{placeholder}}}}}', replacement)
                    if 'folder' in key or 'path' in key:
                        obj[key] = os.path.normpath(new_value)
                    else:
                        obj[key] = new_value
                    unresolved_found_in_pass = True
        
        elif isinstance(value, dict):
            if _resolve_placeholders_recursive(value, templates):
                unresolved_found_in_pass = True
        
        elif isinstance(value, list):
            if _resolve_placeholders_recursive(value, templates):
                unresolved_found_in_pass = True
                
    return unresolved_found_in_pass

def _find_and_load_config() -> Optional[Dict[str, Any]]:
    """
    Finds, loads, and processes the configuration file.
    """
    try:
        project_root = None
        current_dir = os.path.dirname(os.path.abspath(__file__))
        for _ in range(5):
            if os.path.basename(current_dir) == 'syncro_data_consolidator':
                project_root = current_dir
                break
            parent_dir = os.path.dirname(current_dir)
            if parent_dir == current_dir: break
            current_dir = parent_dir

        if not project_root:
            print("FATAL ERROR: Could not find project root 'syncro_data_consolidator'.")
            return None

        config_path = os.path.join(project_root, "config", "config.json")
        if not os.path.exists(config_path):
            print(f"FATAL ERROR: Config file not found at {config_path}")
            return None

        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # --- REVISED PLACEHOLDER RESOLUTION ---
        # 1. Seed the templates with the project root.
        templates = config.get('project_paths', {})
        templates['project_root'] = project_root

        # 2. Multi-pass resolution to handle nested placeholders.
        for _ in range(5): # Limit iterations to prevent infinite loops
            if not _resolve_placeholders_recursive(config, templates):
                break # Exit if a full pass makes no changes

        # 3. Apply environment variable overrides
        syncro_api_key = os.getenv('SYNCRO_API_KEY')
        if syncro_api_key:
            config.setdefault('syncro_api', {})['api_key'] = syncro_api_key

        google_api_key = os.getenv('GOOGLE_API_KEY')
        if google_api_key:
            config.setdefault('llm_config', {}).setdefault('google_gemini', {})['api_key'] = google_api_key

        return config

    except Exception as e:
        print(f"An unexpected fatal error occurred during configuration loading: {e}")
        return None

def load_config() -> Optional[Dict[str, Any]]:
    """
    Public function to get the application configuration.
    """
    global _cached_config
    if _cached_config is None:
        _cached_config = _find_and_load_config()
    return _cached_config
