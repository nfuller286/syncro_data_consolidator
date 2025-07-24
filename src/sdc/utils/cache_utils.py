# -*- coding: utf-8 -*-
"""Utility for handling loading of cached data files."""

import os
import json
from typing import Any, Dict, List, Optional


def load_lean_customer_cache(config: Dict[str, Any], logger) -> Optional[List[Dict[str, Any]]]:
    """
    Loads the lean_customer_cache.json file.

    This file is a pre-processed, lightweight list of customers and their contacts,
    created by the syncro_customer_contact_cacher.

    Args:
        config: The application's configuration dictionary.
        logger: The SDC logger instance.

    Returns:
        A list of customer dictionaries, or None on failure.
    """
    cache_file_path = os.path.join(config['project_paths']['cache_folder'], 'lean_customer_cache.json')
    try:
        with open(cache_file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load or parse lean customer cache from {cache_file_path}: {e}")
        return None