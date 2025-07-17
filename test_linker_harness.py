# -*- coding: utf-8 -*-
"""Integration test for the CUIS customer linker process."""

import sys
import os
import json
import shutil

# Add the 'src' directory to the Python path to resolve the module import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from sdc.models.cuis_v1 import CUISV1
from sdc.processors.cuis_customer_linker import link_customers_to_cuis
from sdc.utils.config_loader import load_config
from sdc.utils.sdc_logger import get_sdc_logger

def main():
    """Runs the integration test for the customer linker."""
    # --- 1. Setup ---
    print("--- Setting up test environment ---")
    config = load_config()
    if not config:
        print("FATAL: Could not load config.")
        return

    # Use a test-specific logger
    logger = get_sdc_logger('test_linker_harness', config)

    cache_folder = config['project_paths']['cache_folder']
    mock_lean_cache_path = os.path.join(cache_folder, 'lean_customer_cache.json')

    # a. Create mock lean customer cache file
    mock_customers = [
        {"id": 101, "business_name": "Sovita Chiropractic Stamford", "contacts": ["Dr. Sovita"]},
        {"id": 102, "business_name": "Sovita Chiropractic Hartford", "contacts": []}
    ]
    try:
        os.makedirs(cache_folder, exist_ok=True)
        with open(mock_lean_cache_path, 'w') as f:
            json.dump(mock_customers, f)
        print(f"Successfully created mock lean cache at: {mock_lean_cache_path}")
    except IOError as e:
        logger.error(f"Setup failed: Could not write mock cache file. {e}")
        return

    # b. Create mock CUIS items in memory
    # Scenario 1: Exact match
    exact_match_cuis = CUISV1()
    exact_match_cuis.entities_involved.syncro_customer_name_guessed = "Sovita Chiropractic Stamford"

    # Scenario 2: Fuzzy match (with typo)
    fuzzy_match_cuis = CUISV1()
    fuzzy_match_cuis.entities_involved.syncro_customer_name_guessed = "Sovita Chiropratic Hartford"

    # Scenario 3: No match
    no_match_cuis = CUISV1()
    no_match_cuis.entities_involved.syncro_customer_name_guessed = "Some Random Cafe"

    # Create a dummy CUIS output folder and save items to be processed
    cuis_output_folder = config['project_paths']['cuis_items_output_folder']
    if os.path.exists(cuis_output_folder):
        shutil.rmtree(cuis_output_folder)
    os.makedirs(cuis_output_folder, exist_ok=True)

    mock_cuis_list = [exact_match_cuis, fuzzy_match_cuis, no_match_cuis]
    for cuis_item in mock_cuis_list:
        file_path = os.path.join(cuis_output_folder, f"{cuis_item.sdc_core.sdc_cuis_id}.json")
        with open(file_path, 'w') as f:
            f.write(cuis_item.model_dump_json())
    print(f"Created {len(mock_cuis_list)} mock CUIS files in: {cuis_output_folder}")

    # --- 2. Execution ---
    print("\n--- Executing link_customers_to_cuis process ---")
    # The function reads from the folder, so we don't need to pass the list directly
    link_customers_to_cuis(config, logger)
    print("--- Execution finished ---")

    # --- 3. Verification ---
    print("\n--- Verifying results ---")
    try:
        # Load the processed items back from the files
        processed_exact = CUISV1.model_validate_json(open(os.path.join(cuis_output_folder, f"{exact_match_cuis.sdc_core.sdc_cuis_id}.json")).read())
        processed_fuzzy = CUISV1.model_validate_json(open(os.path.join(cuis_output_folder, f"{fuzzy_match_cuis.sdc_core.sdc_cuis_id}.json")).read())
        processed_none = CUISV1.model_validate_json(open(os.path.join(cuis_output_folder, f"{no_match_cuis.sdc_core.sdc_cuis_id}.json")).read())

        # a. Check exact match
        assert processed_exact.entities_involved.syncro_customer_id_authoritative == 101
        assert processed_exact.sdc_core.sdc_processing_status == 'linked'
        print("[PASS] Exact match linked correctly (ID: 101)")

        # b. Check fuzzy match
        assert processed_fuzzy.entities_involved.syncro_customer_id_authoritative == 102
        assert processed_fuzzy.sdc_core.sdc_processing_status == 'linked'
        print("[PASS] Fuzzy match linked correctly (ID: 102)")

        # c. Check no match
        assert processed_none.entities_involved.syncro_customer_id_authoritative is None
        assert processed_none.sdc_core.sdc_processing_status == 'error'
        print("[PASS] No match was correctly marked as an error")

        print("\n*** All assertions passed. Test successful! ***")

    except FileNotFoundError as e:
        logger.error(f"Verification failed: Could not find processed CUIS file. {e}")
    except (json.JSONDecodeError, AssertionError) as e:
        logger.error(f"Verification failed: {e}", exc_info=True)
    finally:
        # --- 4. Cleanup ---
        print("\n--- Cleaning up test environment ---")
        if os.path.exists(mock_lean_cache_path):
            os.remove(mock_lean_cache_path)
            print(f"Removed mock lean cache: {mock_lean_cache_path}")
        if os.path.exists(cuis_output_folder):
            shutil.rmtree(cuis_output_folder)
            print(f"Removed mock CUIS folder: {cuis_output_folder}")

if __name__ == '__main__':
    main()
