# -*- coding: utf-8 -*-
"""Utility for handling CUIS objects, such as saving and loading them."""

import os
import json
from typing import Any, Dict, Optional, List

from sdc.models.cuis_v1 import CUISV1

def save_cuis_to_file(cuis_object: CUISV1, config: Dict[str, Any], logger) -> None:
    """
    Serializes a CUISV1 Pydantic object to a JSON file.

    Args:
        cuis_object: The CUISV1 object to save.
        config: The application's configuration dictionary.
        logger: The SDC logger instance.
    """
    try:
        output_dir = config['project_paths']['cuis_items_output_folder']
        os.makedirs(output_dir, exist_ok=True)
        # Use the sdc_cuis_id for a guaranteed unique filename
        filename = f"{cuis_object.sdc_core.sdc_cuis_id}.json"
        file_path = os.path.join(output_dir, filename)
        logger.info(f"Saving CUIS item to: {file_path}")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(cuis_object.model_dump_json(indent=4))
        logger.info(f"Successfully saved CUIS item {cuis_object.sdc_core.sdc_cuis_id}")
    except KeyError as e:
        logger.error(f"Configuration key error in save_cuis_to_file: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred in save_cuis_to_file for {cuis_object.sdc_core.sdc_cuis_id}: {e}")

def load_cuis_from_file(file_path: str, logger) -> Optional[CUISV1]:
    """
    Loads a single CUIS JSON file and parses it into a CUISV1 Pydantic object.

    Args:
        file_path: The full path to the CUIS JSON file.
        logger: The SDC logger instance for logging.

    Returns:
        A CUISV1 object if loading and parsing are successful, otherwise None.
    """
    try:
        logger.debug(f"Attempting to load CUIS file: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        cuis_object = CUISV1.model_validate(data)
        logger.debug(f"Successfully loaded and validated CUIS file: {file_path}")
        return cuis_object
    except FileNotFoundError:
        logger.error(f"CUIS file not found at: {file_path}")
        return None
    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON from CUIS file: {file_path}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while loading CUIS file {file_path}: {e}")
        return None

def load_lean_customer_cache(config: dict, logger) -> Optional[list]:
    """
    Loads the lean customer cache file created by the cacher.

    This function's only job is to load the pre-processed lean cache file.

    Args:
        config: The application's configuration dictionary.
        logger: The SDC logger instance.

    Returns:
        A list of customer dictionaries, or None on failure.
    """
    try:
        cache_folder = config['project_paths']['cache_folder']
        lean_cache_path = os.path.join(cache_folder, 'lean_customer_cache.json')
        
        logger.info(f"Loading lean customer cache from: {lean_cache_path}")
        with open(lean_cache_path, 'r', encoding='utf-8') as f:
            lean_cache = json.load(f)
        
        logger.info(f"Successfully loaded {len(lean_cache)} customers from lean cache.")
        return lean_cache

    except FileNotFoundError:
        logger.error(f"Lean customer cache file not found at: {lean_cache_path}. Run the cacher first.")
        return None
    except (IOError, json.JSONDecodeError) as e:
        logger.error(f"Failed to read or parse lean customer cache: {e}")
        return None
    except KeyError as e:
        logger.error(f"Configuration key error while loading lean cache: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while loading lean cache: {e}")
        return None
