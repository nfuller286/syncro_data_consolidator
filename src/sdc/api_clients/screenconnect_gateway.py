import requests
from typing import List, Dict, Any

from sdc.utils.constants import SCREENCONNECT_DEFAULT_API_LIMIT, SCREENCONNECT_QUERY_FIELDS

class ScreenConnectGateway:
    """
    A gateway for interacting with the ScreenConnect/Control API using the GetReport method.
    """
    def __init__(self, base_url: str, extension_id: str, api_key: str):
        """
        Initializes the ScreenConnectGateway.

        :param base_url: The base URL of the ScreenConnect instance (e.g., https://instance.screenconnect.com).
        :param extension_id: The ID of the 'GetReport' extension.
        :param api_key: The API key for authentication.
        """
        self.url = f'{base_url.rstrip("/")}/App_Extensions/{extension_id}/Service.ashx/GetReport'
        self.headers = {
            'Content-Type': 'application/json',
            'Ctrlauthheader': api_key
        }

    def fetch_connections(self, filter_expression: str) -> List[Dict[str, Any]]:
        """
        Fetches connection data from the ScreenConnect API based on a filter expression.

        :param filter_expression: The filter to apply to the query.
        :return: A list of dictionaries, where each dictionary represents a connection.
        """
        payload = [
            {
                "ReportType": "SessionConnection",
                "SelectFieldNames": SCREENCONNECT_QUERY_FIELDS,
                "FilterExpression": filter_expression,
                "ItemLimit": SCREENCONNECT_DEFAULT_API_LIMIT
            }
        ]

        try:
            # The API uses a GET request but expects a JSON body
            response = requests.get(self.url, headers=self.headers, json=payload)
            response.raise_for_status()

            data = response.json()
            
            field_names = data.get('FieldNames')
            items = data.get('Items')

            if not field_names or not items:
                print("Warning: API response did not contain 'FieldNames' or 'Items'.")
                return []

            return [dict(zip(field_names, item)) for item in items]

        except requests.exceptions.RequestException as e:
            print(f"Error fetching data from ScreenConnect API: {e}")
            # Optionally, inspect the response content if available
            if e.response is not None:
                print(f"Response Status: {e.response.status_code}")
                print(f"Response Text: {e.response.text}")
            return []
        except (ValueError, KeyError) as e:
            print(f"Error parsing ScreenConnect API response: {e}")
            return []

