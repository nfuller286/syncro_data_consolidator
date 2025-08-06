# SDC ScreenConnect GetReport API Specification

This document details how the Syncro Data Consolidator (SDC) will interact with the ScreenConnect `GetReport` API endpoint.

## Endpoint Overview

The `GetReport` endpoint provides a way to retrieve structured report data from ScreenConnect by specifying a report type, desired fields, and filters.

-   **URL Structure**: `https://{domain}/App_Extensions/{extension_id}/Service.ashx/GetReport`
    -   **SDC Implementation**: `https://instance.screenconnect.com/App_Extensions/{extension_id}/Service.ashx/GetReport`
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
        "FilterExpression": "ProcessType = 'Host' AND ParticipantName = 'TechName' AND ConnectedTime > '2025-05-18T00:00:00Z'",
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
          "a1b2c3d4-e5f6-47a8-9b0c-1d2e3f4a5b6c",
          "USER-Laptop-1",
          "Example Business Group"
        ],
        [
          "f6e5d4c3-b2a1-48d7-8c9b-0a1b2c3d4e5f",
          "Workstation-02",
          "Sample Client LLC"
        ]
      ]
    }
    ```