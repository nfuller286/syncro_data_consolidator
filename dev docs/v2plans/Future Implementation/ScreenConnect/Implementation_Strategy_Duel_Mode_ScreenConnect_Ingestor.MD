# Implementation Strategy: Dual-Mode ScreenConnect Ingestor

This plan outlines how to refactor the ScreenConnect ingestor to support both API and CSV data sources, controllable via configuration.

## Phase 1: Configuration Update

To support dual modes, we will restructure the `config.json`. This provides clarity and separates the settings for each mode.

Modify `config.json` to create a new top-level `screenconnect_ingestor` block:

```json
{
    "project_paths": { ... },
    "logging": { ... },
    "syncro_api": { ... },

    "screenconnect_ingestor": {
      "active_mode": "api", 
      "api_config": {
        "base_url": "https://instance.screenconnect.com/App_Extensions/{extension_id}/Service.ashx/GetReport",
        "api_key_header_name": "Ctrlauthheader",
        "api_key_env_var": "SCREENCONNECT_API_KEY",
        "report_parameters": {
          "ReportType": "SessionConnection",
          "SelectFieldNames": [
            "SessionSessionID", "ProcessType", "SessionSessionType", "SessionName", "ParticipantName", 
            "ConnectedTime", "DisconnectedTime", "DurationSeconds", "ClientType", "NetworkAddress", 
            "SessionCustomProperty1", "SessionCustomProperty4", "SessionCustomProperty5"
          ],
		  [
  "ProcessType", "SessionSessionType", "SessionName", "ParticipantName", "ConnectedTime", "DisconnectedTime", "DurationSeconds", "ConnectionID", "SessionCustomProperty1", "SessionSessionID", "ClientType", "NetworkAddress", "SessionCustomProperty4", "SessionCustomProperty5"
          ]
          "static_filter_expression": "ProcessType = 'Host' AND ParticipantName = 'TechName'",
          "dynamic_date_filter_field": "ConnectedTime",
          "initial_ingest_days": 90,
          "item_limit": 200
        }
      },
      "csv_config": {
        "input_folder": "{ProjectData}/input/screenconnect_logs/",
        "file_pattern": "*.csv"
      }
    },

    "llm_config": { ... },
    "processing_defaults": { ... }
}