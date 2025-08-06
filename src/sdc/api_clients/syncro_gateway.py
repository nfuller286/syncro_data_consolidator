# -*- coding: utf-8 -*-
"""A gateway class for all interactions with the Syncro API."""

import requests
import time
import json
from typing import Dict, List, Optional, Any

class SyncroGateway:
    """Centralizes all Syncro API interaction logic."""
    def __init__(self, config: Dict, logger):
        self.logger = logger
        try:
            api_config = config['syncro_api']
            self.base_url = api_config['base_url'].rstrip('/')
            self.headers = {'Authorization': f"Bearer {api_config['api_key']}"}
        except KeyError as e:
            self.logger.error(f"SyncroGateway init failed: Missing key {e} in syncro_api config.")
            raise  # Re-raise the exception to stop execution if config is bad

    def _fetch_paginated_data(self, endpoint_url: str, params: Optional[Dict[str, Any]] = None) -> Optional[List[Dict[str, Any]]]:
        """Fetches all items from a paginated Syncro API endpoint."""
        all_items = []
        data_key = endpoint_url.split('/')[-1].split('?')[0]
        page = 1
        max_pages = 100  # Safety limit

        self.logger.info(f"Starting to fetch all {data_key} from {endpoint_url} with params: {params}")

        while page <= max_pages:
            request_params = params.copy() if params else {}
            request_params['page'] = page
            try:
                response = requests.get(endpoint_url, headers=self.headers, params=request_params, timeout=30)
                response.raise_for_status()
                data = response.json()

                if data_key in data and data[data_key]:
                    items_on_page = data[data_key]
                    all_items.extend(items_on_page)
                    self.logger.debug(f"Fetched page {page} for {data_key}, {len(items_on_page)} items. Total so far: {len(all_items)}.")
                else:
                    self.logger.info(f"No more {data_key} found on page {page}. Concluding fetch.")
                    break

                if 'meta' in data and data['meta'].get('total_pages'):
                    total_pages = data['meta']['total_pages']
                    if page >= total_pages:
                        self.logger.info(f"Reached the last page ({page}/{total_pages}) for {data_key}.")
                        break
                    # Update max_pages to the actual total if available
                    max_pages = total_pages
                else:
                    # This handles cases where the API doesn't return pagination meta,
                    # which can happen for single-page results.
                    self.logger.warning(f"Pagination 'meta' data not found for {data_key}. Assuming single page and stopping.")
                    break

                page += 1
                time.sleep(0.2)  # Be a good API citizen

            except requests.exceptions.RequestException as e:
                self.logger.error(f"API request failed while fetching {data_key} page {page}: {e}")
                return None
            except json.JSONDecodeError as e:
                self.logger.error(f"Error decoding JSON from page {page} for {data_key}: {e}")
                return None  # Stop processing on bad JSON

        self.logger.info(f"Finished fetching {data_key}. Total retrieved: {len(all_items)}")
        return all_items

    def fetch_all_customers(self) -> Optional[List[Dict[str, Any]]]:
        """Fetches all customers from the Syncro API."""
        self.logger.info("[AUDIT] SyncroGateway requesting all customers.")
        url = f"{self.base_url}/customers"
        return self._fetch_paginated_data(url)

    def fetch_all_contacts(self) -> Optional[List[Dict[str, Any]]]:
        """Fetches all contacts from the Syncro API."""
        self.logger.info("[AUDIT] SyncroGateway requesting all contacts.")
        url = f"{self.base_url}/contacts"
        return self._fetch_paginated_data(url)

    def fetch_tickets(self, since_updated_at: Optional[str] = None, created_after: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """Fetches tickets, optionally filtering by an update or creation timestamp."""
        self.logger.info(f"[AUDIT] SyncroGateway requesting tickets. since_updated_at={since_updated_at}, created_after={created_after}")
        url = f"{self.base_url}/tickets"
        params = {}
        if since_updated_at:
            params['since_updated_at'] = since_updated_at
        if created_after:
            params['created_after'] = created_after

        return self._fetch_paginated_data(url, params=params if params else None)