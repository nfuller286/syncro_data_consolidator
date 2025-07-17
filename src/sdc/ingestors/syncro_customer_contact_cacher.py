# src/sdc/ingestors/syncro_customer_contact_cacher.py

# Standard library imports
import json
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

# Third-party imports
import requests


def _fetch_paginated_data(endpoint_url: str, headers: Dict[str, str], logger) -> Optional[List[Dict[str, Any]]]:
    """Fetches all items from a paginated Syncro API endpoint."""
    all_items = []
    data_key = endpoint_url.split('/')[-1].split('?')[0]
    page = 1
    max_pages = 100

    logger.info(f"Starting to fetch all {data_key} from {endpoint_url}...")

    while page <= max_pages:
        params = {'page': page}
        try:
            response = requests.get(endpoint_url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if data_key in data and data[data_key]:
                items_on_page = data[data_key]
                all_items.extend(items_on_page)
                logger.debug(f"Fetched page {page} for {data_key}, {len(items_on_page)} items. Total so far: {len(all_items)}")
            else:
                logger.info(f"No more {data_key} found on page {page}. Concluding fetch.")
                break

            if 'meta' in data and data['meta'].get('total_pages'):
                total_pages = data['meta']['total_pages']
                if page >= total_pages:
                    logger.info(f"Reached the last page ({page}/{total_pages}) for {data_key}.")
                    break
                max_pages = total_pages
            else:
                logger.warning(f"Pagination 'meta' data not found for {data_key}. Assuming single page and stopping.")
                break

            page += 1
            time.sleep(0.2)

        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed while fetching {data_key} page {page}: {e}")
            return None

    logger.info(f"Finished fetching {data_key}. Total retrieved: {len(all_items)}")
    return all_items

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

    try:
        api_key = config['syncro_api']['api_key']
        base_url = config['syncro_api']['base_url'].rstrip('/')
    except KeyError as e:
        logger.error(f"Syncro API configuration key missing: {e}. Aborting.")
        return

    if not api_key or not base_url:
        logger.error("Syncro API key or base URL is not configured. Aborting.")
        return

    headers = {'Authorization': f'Bearer {api_key}'}

    customers_url = f"{base_url}/customers"
    all_customers = _fetch_paginated_data(customers_url, headers, logger)

    contacts_url = f"{base_url}/contacts"
    all_contacts = _fetch_paginated_data(contacts_url, headers, logger)

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
            if contact.get('customer_id') and contact.get('name'):
                contacts_by_customer_id[contact['customer_id']].append(contact['name'])

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
