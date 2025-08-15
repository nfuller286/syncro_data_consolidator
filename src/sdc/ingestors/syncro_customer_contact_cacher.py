# src/sdc/ingestors/syncro_customer_contact_cacher.py

# Standard library imports
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sdc.api_clients.syncro_gateway import SyncroGateway

def cache_syncro_data(config: Dict[str, Any], logger):
    """Main entry point to fetch and cache Syncro customer and contact data."""
    logger.info("Starting Syncro customer/contact caching process...")

    try:
        policy = config['processing_defaults']['syncro_cache_policy']
        expiry_hours = config['processing_defaults']['syncro_cache_expiry_hours']
        cache_folder = config['project_paths']['cache_folder']
    except KeyError as e:
        logger.error(f"Configuration key missing: {e}. Aborting caching process.")
        return

    customer_cache_path = os.path.join(cache_folder, 'syncro_customers_cache.json')

    run_fetch = True
    if policy == 'manual_only':
        if os.path.exists(customer_cache_path):
            logger.info("Cache policy is 'manual_only' and cache file exists. Skipping fetch.")
            run_fetch = False
        else:
            logger.info("Cache policy is 'manual_only' but no cache file found. Proceeding with fetch.")

    elif policy == 'if_older_than_hours':
        if os.path.exists(customer_cache_path):
            try:
                file_mod_time_utc = datetime.fromtimestamp(os.path.getmtime(customer_cache_path), tz=timezone.utc)
                expiry_delta = timedelta(hours=expiry_hours)
                if datetime.now(timezone.utc) - file_mod_time_utc < expiry_delta:
                    logger.info(f"Cache is fresh (less than {expiry_hours} hours old). Skipping fetch.")
                    run_fetch = False
                else:
                    logger.info("Cache is stale. Proceeding with fetch.")
            except Exception as e:
                logger.error(f"Could not check cache file timestamp: {e}. Proceeding with fetch.")
        else:
            logger.info("No cache file found. Proceeding with fetch.")

    elif policy != 'on_each_run':
        logger.warning(f"Unknown cache policy '{policy}'. Defaulting to 'on_each_run'.")

    if not run_fetch:
        return

    # Instantiate the gateway. It will raise an error if config is missing.
    try:
        gateway = SyncroGateway(config, logger)
    except KeyError:
        # The gateway's __init__ already logs the specific error and raises it.
        # We catch it here to abort the function gracefully.
        logger.critical("Aborting caching process due to gateway initialization failure.")
        return

    all_customers = gateway.fetch_all_customers()
    all_contacts = gateway.fetch_all_contacts()

    try:
        os.makedirs(cache_folder, exist_ok=True)
    except OSError as e:
        logger.error(f"Failed to create cache directory {cache_folder}: {e}")
        return

    if all_customers is not None:
        try:
            with open(customer_cache_path, 'w') as f:
                json.dump(all_customers, f, indent=4)
            logger.info(f"Successfully saved {len(all_customers)} customers to raw cache file: {customer_cache_path}")
        except IOError as e:
            logger.error(f"Failed to write customer cache file: {e}")
    else:
        logger.error("Customer fetching failed. Raw customer cache file will not be updated.")

    if all_contacts is not None:
        contact_cache_path = os.path.join(cache_folder, 'syncro_contacts_cache.json')
        try:
            with open(contact_cache_path, 'w') as f:
                json.dump(all_contacts, f, indent=4)
            logger.info(f"Successfully saved {len(all_contacts)} contacts to raw cache file: {contact_cache_path}")
        except IOError as e:
            logger.error(f"Failed to write contact cache file: {e}")
    else:
        logger.error("Contact fetching failed. Raw contact cache file will not be updated.")

    # --- NEW LOGIC: Create and save the lean customer cache ---
    if all_customers is not None and all_contacts is not None:
        logger.info("Creating lean customer cache from fetched data...")
        contacts_by_customer_id = defaultdict(list)
        for contact in all_contacts:
            if contact.get('customer_id') and contact.get('name') and contact.get('id'):
                contacts_by_customer_id[contact['customer_id']].append(
                    {'id': contact['id'], 'name': contact['name']}
                )

        lean_customers = []
        for customer in all_customers:
            customer_id = customer.get('id')
            if not customer_id or not customer.get('business_then_name'):
                continue
            
            lean_customer = {
                "id": customer_id,
                "business_name": customer.get('business_then_name'),
                "contacts": contacts_by_customer_id.get(customer_id, [])
            }
            lean_customers.append(lean_customer)

        lean_cache_path = os.path.join(cache_folder, 'lean_customer_cache.json')
        try:
            with open(lean_cache_path, 'w') as f:
                json.dump(lean_customers, f, indent=4)
            logger.info(f"Successfully saved {len(lean_customers)} customers to lean cache file: {lean_cache_path}")
        except IOError as e:
            logger.error(f"Failed to write lean customer cache file: {e}")
    else:
        logger.warning("Skipping lean cache creation because raw customer or contact data was not fetched.")

    logger.info("Syncro customer/contact caching process finished.")
