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
    To recursively search through the configuration dictionary and replace
    placeholder strings (e.g., `{{project_root}}`) with their actual values.
    """
    made_replacement = False
    
    # --- START OF FIX ---
    # Handle dictionaries and lists separately to resolve type ambiguity
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, str):
                new_value = value
                for placeholder, replacement in templates.items():
                    if f"{{{{{placeholder}}}}}" in new_value:
                        new_value = new_value.replace(f"{{{{{placeholder}}}}}", replacement)
                        made_replacement = True
                
                if new_value != value:
                    if 'folder' in key or 'path' in key:
                        obj[key] = os.path.normpath(new_value)
                    else:
                        obj[key] = new_value
            
            elif isinstance(value, (dict, list)):
                if _resolve_placeholders_recursive(value, templates):
                    made_replacement = True

    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, str):
                new_item = item
                for placeholder, replacement in templates.items():
                    if f"{{{{{placeholder}}}}}" in new_item:
                        new_item = new_item.replace(f"{{{{{placeholder}}}}}", replacement)
                        made_replacement = True
                
                if new_item != item:
                    obj[i] = new_item # No path normalization needed for list items by default
            
            elif isinstance(item, (dict, list)):
                if _resolve_placeholders_recursive(item, templates):
                    made_replacement = True
    # --- END OF FIX ---
            
    return made_replacement

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

        # --- Load and merge all LLM-related configurations ---
        llm_configs_path = os.path.join(project_root, "config", "llm_configs.json")
        if os.path.exists(llm_configs_path):
            with open(llm_configs_path, 'r', encoding='utf-8') as f:
                llm_configs = json.load(f)
                config['llm_configs'] = llm_configs
        else:
            print(f"WARNING: LLM configs file not found at {llm_configs_path}. LLM functionality will be limited.")
            config['llm_configs'] = {}

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
