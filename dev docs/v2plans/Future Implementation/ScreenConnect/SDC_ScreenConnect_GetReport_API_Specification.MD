# SDC ScreenConnect GetReport API Specification

This document details how the Syncro Data Consolidator (SDC) will interact with the ScreenConnect `GetReport` API endpoint.

## Endpoint Overview

The `GetReport` endpoint provides a way to retrieve structured report data from ScreenConnect by specifying a report type, desired fields, and filters.

-   **URL Structure**: `https://{domain}/App_Extensions/{extension_id}/Service.ashx/GetReport`
    -   **SDC Implementation**: `https://ctremote123.com/App_Extensions/2d558935-686a-4bd0-9991-07539f5fe749/Service.ashx/GetReport`
-   **HTTP Method**: `GET`
-   **Headers**:

| Header           | Value                          | Notes                                                            |
| ---------------- | ------------------------------ | ---------------------------------------------------------------- |
| `Content-Type`   | `application/json`             | Required to specify the format of the request body.              |
| `Ctrlauthheader` | `1234abcd` (example API key)   | The user-defined authentication token from the extension's UI.   |

## Request Body

The body of the `GET` request must be a JSON array containing a single dictionary object that defines the report parameters.

-   **Structure**:
    ```json
    [
      {
        "ReportType": "SessionConnection",
        "SelectFieldNames": [ "... field names ... " ],
        "FilterExpression": "...",
        "ItemLimit": 200
      }
    ]
    ```
-   **FilterExpression Syntax**:
    -   `FieldName = 'StringValue'`
    -   `FieldName = NumericValue`
    -   Use `AND` / `OR` in all caps for compound expressions.
-   **SDC Implementation Example**:
    ```json
    [
      {
        "ReportType": "SessionConnection",
        "SelectFieldNames": [
            "SessionSessionID", "ProcessType", "SessionSessionType", "SessionName", "ParticipantName", 
            "ConnectedTime", "DisconnectedTime", "DurationSeconds", "ClientType", "NetworkAddress", 
            "SessionCustomProperty1", "SessionCustomProperty4", "SessionCustomProperty5"
        ],
        "FilterExpression": "ProcessType = 'Host' AND ParticipantName = 'Nick' AND ConnectedTime > '2025-05-18T00:00:00Z'",
        "ItemLimit": 200
      }
    ]
    ```

## Response Payload

The API returns a JSON object containing two key-value pairs: `FieldNames` and `Items`.

-   **`FieldNames`**: An array of strings representing the column headers, in the order the data is returned.
-   **`Items`**: An array of sub-arrays. Each sub-array contains the field values for one record, in the same order as `FieldNames`.
-   **Implementation Requirement**: The ingestor script **must** process this response by "zipping" the `FieldNames` array with each sub-array in `Items` to create a standard list of dictionaries. This makes the data easy to work with (e.g., `item['SessionName']`).

-   **Example Response**:
    ```json
    {
      "FieldNames": [
        "SessionSessionID",
        "SessionName",
        "SessionCustomProperty1"
      ],
      "Items": [
        [
          "cf54cafc-cbdb-4c87-8dc1-23ca8adb7e4b",
          "Rachels-MacBook-Air-3",
          "Scranton Financial Group"
        ],
        [
          "4993416a-b9c0-435d-b6ec-be99c0e7fa99",
          "MacBookPro",
          "Capitol Chiropractic Center Hartford"
        ]
      ]
    }
    ```