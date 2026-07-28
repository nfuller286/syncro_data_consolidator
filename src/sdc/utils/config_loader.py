# -*- coding: utf-8 -*-
"""
Utility for loading and parsing the project's configuration file.
"""

import os
import re
from typing import Dict, Any, Optional, Union, List

import yaml

_cached_config: Optional[Dict[str, Any]] = None

def load_yaml_config(path: str) -> Dict[str, Any]:
    """Loads and parses a YAML config file, returning {} for an empty file."""
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}

def resolve_placeholders(obj: Union[Dict, List], templates: Dict[str, str]) -> bool:
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
                if resolve_placeholders(value, templates):
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
                if resolve_placeholders(item, templates):
                    made_replacement = True
    # --- END OF FIX ---

    return made_replacement

def resolve_project_paths(project_root: str, project_paths: Dict[str, Any]) -> Dict[str, Any]:
    """
    Seeds `project_paths` with `project_root` and resolves `{{...}}`
    placeholders within it in place (multi-pass, since some paths reference
    other paths, e.g. input_folder references data_folder). Returns the same
    dict, for use both as the resolved project_paths section and as the
    template source for resolving placeholders elsewhere in a config.
    """
    project_paths['project_root'] = project_root
    for _ in range(5):  # Limit iterations to prevent infinite loops
        if not resolve_placeholders(project_paths, project_paths):
            break
    return project_paths

def _find_and_load_config() -> Optional[Dict[str, Any]]:
    """
    Finds, loads, and processes the configuration file.
    """
    try:
        project_root = None
        current_dir = os.path.dirname(os.path.abspath(__file__))
        for _ in range(5):  # Traverse up to 5 levels
            config_path_to_check = os.path.join(current_dir, 'config', 'config.yaml')
            sample_config_path_to_check = os.path.join(current_dir, 'config', 'sampleconfig.yaml')

            if os.path.isfile(config_path_to_check) or os.path.isfile(sample_config_path_to_check):
                project_root = current_dir
                break

            parent_dir = os.path.dirname(current_dir)
            if parent_dir == current_dir:  # Reached root of filesystem
                break
            current_dir = parent_dir

        if not project_root:
            print("FATAL ERROR: Could not find project root. Searched for 'config/config.yaml' or 'config/sampleconfig.yaml'.")
            return None

        config_path = os.path.join(project_root, "config", "config.yaml")
        if not os.path.exists(config_path):
            print(f"FATAL ERROR: Config file not found at {config_path}")
            return None

        config = load_yaml_config(config_path)

        # --- REVISED PLACEHOLDER RESOLUTION ---
        # Resolved before llm_configs is merged in below, so this pass can
        # never see (and can never mangle) the single-brace prompt templates
        # that live in llm_configs.yaml.
        templates = resolve_project_paths(project_root, config.get('project_paths', {}))
        config['project_paths'] = templates
        for _ in range(5): # Limit iterations to prevent infinite loops
            if not resolve_placeholders(config, templates):
                break # Exit if a full pass makes no changes

        # --- Load and merge all LLM-related configurations ---
        llm_configs_path = os.path.join(project_root, "config", "llm_configs.yaml")
        if os.path.exists(llm_configs_path):
            config['llm_configs'] = load_yaml_config(llm_configs_path)
        else:
            print(f"WARNING: LLM configs file not found at {llm_configs_path}. LLM functionality will be limited.")
            config['llm_configs'] = {}

        # --- Apply environment variable overrides
        syncro_api_key = os.getenv('SYNCRO_API_KEY')
        if syncro_api_key:
            config.setdefault('syncro_api', {})['api_key'] = syncro_api_key

        google_api_key = os.getenv('GOOGLE_API_KEY')
        if google_api_key:
            config.setdefault('llm_provider_config', {}).setdefault('google_gemini', {})['api_key'] = google_api_key

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

def get_config_value(config: Dict[str, Any], key_path: str, default: Any = None) -> Any:
    """
    Safely retrieves a nested value from a dictionary using a dot-separated path.

    Args:
        config: The configuration dictionary to search.
        key_path: A dot-separated string representing the nested key (e.g., 'parent.child.key').
        default: The value to return if the key is not found.

    Returns:
        The value found at the specified path, or the default value.
    """
    keys = key_path.split('.')
    value = config
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default
    return value
