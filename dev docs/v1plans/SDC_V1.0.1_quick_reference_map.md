# SDC Developer's Map

## File Path: /a0/syncro_data_consolidator/src/sdc/ingestors/notes_json_ingestor.py

**Core Purpose:** Ingestor for data from the legacy notes.json file format.

**Key Components (Classes/Functions):**

*   **Function:** `_get_file_metadata`
    *   **Purpose:** Returns file size and modification time.
    *   **Key Inputs:** ['file_path']
    *   **Outputs:** Not specified

*   **Function:** `_load_ingestor_state`
    *   **Purpose:** Loads the ingestor state from a JSON file.
    *   **Key Inputs:** ['config', 'logger']
    *   **Outputs:** Not specified

*   **Function:** `_save_ingestor_state`
    *   **Purpose:** Saves the ingestor state to a JSON file.
    *   **Key Inputs:** ['state', 'config', 'logger']
    *   **Outputs:** Not specified

*   **Function:** `ingest_notes`
    *   **Purpose:** Loads data from notes.json, transforms it into CUIS format, and saves it.
    *   **Key Inputs:** ['config']
    *   **Outputs:** Not specified

**Dependencies:**

*   **Internal:** ['sdc.utils.sdc_logger', 'sdc.utils.cuis_handler', 'sdc.models.cuis_v1', 'sdc.utils.date_utils']
*   **External:** ['typing', 'os', 'json']

---

## File Path: /a0/syncro_data_consolidator/src/sdc/ingestors/screenconnect_log_ingestor.py

**Core Purpose:** No module docstring found.

**Key Components (Classes/Functions):**

*   **Function:** `_get_file_metadata`
    *   **Purpose:** No function docstring found.
    *   **Key Inputs:** ['file_path']
    *   **Outputs:** Not specified

*   **Function:** `_load_ingestor_state`
    *   **Purpose:** No function docstring found.
    *   **Key Inputs:** ['config', 'logger']
    *   **Outputs:** Not specified

*   **Function:** `_save_ingestor_state`
    *   **Purpose:** No function docstring found.
    *   **Key Inputs:** ['state', 'config', 'logger']
    *   **Outputs:** Not specified

*   **Function:** `ingest_screenconnect`
    *   **Purpose:** No function docstring found.
    *   **Key Inputs:** ['config']
    *   **Outputs:** Not specified

**Dependencies:**

*   **Internal:** ['sdc.utils.sdc_logger', 'sdc.utils.cuis_handler', 'sdc.models.cuis_v1', 'sdc.utils.date_utils']
*   **External:** ['os', 'pandas', 'json', 'typing', 'datetime']

---

## File Path: /a0/syncro_data_consolidator/src/sdc/ingestors/st_chat_ingestor.py

**Core Purpose:** Ingestor for SillyTavern chat logs in .jsonl format.

**Key Components (Classes/Functions):**

*   **Function:** `_get_file_metadata`
    *   **Purpose:** Returns file size and modification time.
    *   **Key Inputs:** ['file_path']
    *   **Outputs:** Not specified

*   **Function:** `_load_ingestor_state`
    *   **Purpose:** Loads the ingestor state from a JSON file.
    *   **Key Inputs:** ['config', 'logger']
    *   **Outputs:** Not specified

*   **Function:** `_save_ingestor_state`
    *   **Purpose:** Saves the ingestor state to a JSON file.
    *   **Key Inputs:** ['state', 'config', 'logger']
    *   **Outputs:** Not specified

*   **Function:** `ingest_sillytavern_chats`
    *   **Purpose:** Loads SillyTavern .jsonl chat logs, segments them into sessions,
transforms them into CUIS format, and saves them.

Args:
    config: The application's configuration dictionary.
    logger: The SDC logger instance.
    *   **Key Inputs:** ['config', 'logger']
    *   **Outputs:** Not specified

**Dependencies:**

*   **Internal:** ['sdc.utils.cuis_handler', 'sdc.models.cuis_v1', 'sdc.utils.date_utils']
*   **External:** ['datetime', 'typing', 'os', 'json']

---

## File Path: /a0/syncro_data_consolidator/src/sdc/ingestors/syncro_customer_contact_cacher.py

**Core Purpose:** No module docstring found.

**Key Components (Classes/Functions):**

*   **Function:** `_fetch_paginated_data`
    *   **Purpose:** Fetches all items from a paginated Syncro API endpoint.
    *   **Key Inputs:** ['endpoint_url', 'headers', 'logger']
    *   **Outputs:** Not specified

*   **Function:** `cache_syncro_data`
    *   **Purpose:** Main entry point to fetch and cache Syncro customer and contact data.
    *   **Key Inputs:** ['config', 'logger']
    *   **Outputs:** Not specified

**Dependencies:**

*   **Internal:** []
*   **External:** ['os', 'time', 'collections', 'json', 'typing', 'requests', 'datetime']

---

## File Path: /a0/syncro_data_consolidator/src/sdc/ingestors/syncro_ticket_ingestor.py

**Core Purpose:** No module docstring found.

**Key Components (Classes/Functions):**

*   **Function:** `_get_file_metadata`
    *   **Purpose:** No function docstring found.
    *   **Key Inputs:** ['file_path']
    *   **Outputs:** Not specified

*   **Function:** `_load_ingestor_state`
    *   **Purpose:** No function docstring found.
    *   **Key Inputs:** ['config', 'logger']
    *   **Outputs:** Not specified

*   **Function:** `_save_ingestor_state`
    *   **Purpose:** No function docstring found.
    *   **Key Inputs:** ['state', 'config', 'logger']
    *   **Outputs:** Not specified

*   **Function:** `_fetch_all_pages`
    *   **Purpose:** No function docstring found.
    *   **Key Inputs:** ['base_url', 'headers', 'params', 'logger']
    *   **Outputs:** list

*   **Function:** `ingest_syncro_tickets`
    *   **Purpose:** No function docstring found.
    *   **Key Inputs:** ['config']
    *   **Outputs:** Not specified

**Dependencies:**

*   **Internal:** ['sdc.utils.cuis_handler', 'sdc.models.cuis_v1', 'sdc.utils.date_utils', 'sdc.utils.sdc_logger']
*   **External:** ['os', 'json', 'typing', 'requests', 'datetime']

---

## File Path: /a0/syncro_data_consolidator/src/sdc/models/cuis_v1.py

**Core Purpose:** Pydantic model for the Core Unified Information Structure (CUIS) V1.0.

This file defines the complete data structure for a CUIS item, which is used
by the Syncro Data Consolidator (SDC) to represent normalized information
from various sources.

**Key Components (Classes/Functions):**

*   **Class:** `SdcCore`
    *   **Purpose:** Metadata used by SDC for internal tracking and management.

*   **Class:** `CoreContent`
    *   **Purpose:** Normalized essential content derived from the source.

*   **Class:** `EntitiesInvolved`
    *   **Purpose:** Information about customers, contacts, assignees, and other actors.

*   **Class:** `Categorization`
    *   **Purpose:** Fields related to classifying the CUIS item.

*   **Class:** `Link`
    *   **Purpose:** Represents relationships to other CUIS items or external entities.

*   **Class:** `CuisEntry`
    *   **Purpose:** Represents sub-items like ticket comments or individual messages.

*   **Class:** `CUISV1`
    *   **Purpose:** Root model for the Core Unified Information Structure (CUIS) V1.0.

**Dependencies:**

*   **Internal:** []
*   **External:** ['typing', 'datetime', 'uuid', 'pydantic']

---

## File Path: /a0/syncro_data_consolidator/src/sdc/processors/cuis_customer_linker.py

**Core Purpose:** This module links unprocessed CUIS items to authoritative Syncro customers and contacts.

**Key Components (Classes/Functions):**

*   **Function:** `_find_winner_from_llm_response`
    *   **Purpose:** Finds the winning item from a list of candidates based on the LLM's response.
Can handle lists of dictionaries (customers) or lists of strings (contacts).
    *   **Key Inputs:** ['llm_response', 'candidates', 'match_key', 'logger']
    *   **Outputs:** Not specified

*   **Function:** `link_customers_to_cuis`
    *   **Purpose:** Iterates through CUIS files, links them to Syncro customers and contacts, and updates the files.
    *   **Key Inputs:** ['config', 'logger']
    *   **Outputs:** Not specified

**Dependencies:**

*   **Internal:** ['sdc.utils', 'sdc.models.cuis_v1']
*   **External:** ['os', 'json', 'typing', 'thefuzz', 'datetime']

---

## File Path: /a0/syncro_data_consolidator/src/sdc/processors/cuis_embedding_generator.py

**Core Purpose:** No module docstring found.

**Key Components (Classes/Functions):**

**Dependencies:**

*   **Internal:** []
*   **External:** []

---

## File Path: /a0/syncro_data_consolidator/src/sdc/processors/cuis_llm_analyzer.py

**Core Purpose:** No module docstring found.

**Key Components (Classes/Functions):**

**Dependencies:**

*   **Internal:** []
*   **External:** []

---

## File Path: /a0/syncro_data_consolidator/src/sdc/run_sdc.py

**Core Purpose:** Master orchestrator for the Syncro Data Consolidator (SDC) project.

**Key Components (Classes/Functions):**

*   **Function:** `main`
    *   **Purpose:** Main entry point for the SDC application.
    *   **Key Inputs:** []
    *   **Outputs:** Not specified

**Dependencies:**

*   **Internal:** ['sdc.utils.config_loader', 'sdc.ingestors.syncro_ticket_ingestor', 'sdc.ingestors.syncro_customer_contact_cacher', 'sdc.ingestors.notes_json_ingestor', 'sdc.ingestors.screenconnect_log_ingestor', 'sdc.utils.sdc_logger', 'sdc.ingestors.st_chat_ingestor', 'sdc.processors.cuis_customer_linker']
*   **External:** ['argparse']

---

## File Path: /a0/syncro_data_consolidator/src/sdc/utils/config_loader.py

**Core Purpose:** Utility for loading and parsing the project's configuration file.

**Key Components (Classes/Functions):**

*   **Function:** `_resolve_placeholders_recursive`
    *   **Purpose:** Recursively traverses a dictionary or list to resolve placeholders.

Args:
    obj: The dictionary or list to process.
    templates: A dictionary of placeholder keys and their resolved values.

Returns:
    True if any placeholder was resolved in this pass, otherwise False.
    *   **Key Inputs:** ['obj', 'templates']
    *   **Outputs:** bool

*   **Function:** `_find_and_load_config`
    *   **Purpose:** Finds, loads, and processes the configuration file.
    *   **Key Inputs:** []
    *   **Outputs:** Not specified

*   **Function:** `load_config`
    *   **Purpose:** Public function to get the application configuration.
    *   **Key Inputs:** []
    *   **Outputs:** Not specified

**Dependencies:**

*   **Internal:** []
*   **External:** ['typing', 'os', 're', 'json']

---

## File Path: /a0/syncro_data_consolidator/src/sdc/utils/cuis_handler.py

**Core Purpose:** Utility for handling CUIS objects, such as saving and loading them.

**Key Components (Classes/Functions):**

*   **Function:** `save_cuis_to_file`
    *   **Purpose:** Serializes a CUISV1 Pydantic object to a JSON file.

Args:
    cuis_object: The CUISV1 object to save.
    config: The application's configuration dictionary.
    logger: The SDC logger instance.
    *   **Key Inputs:** ['cuis_object', 'config', 'logger']
    *   **Outputs:** Not specified

*   **Function:** `load_cuis_from_file`
    *   **Purpose:** Loads a single CUIS JSON file and parses it into a CUISV1 Pydantic object.

Args:
    file_path: The full path to the CUIS JSON file.
    logger: The SDC logger instance for logging.

Returns:
    A CUISV1 object if loading and parsing are successful, otherwise None.
    *   **Key Inputs:** ['file_path', 'logger']
    *   **Outputs:** Not specified

*   **Function:** `load_lean_customer_cache`
    *   **Purpose:** Loads the lean customer cache file created by the cacher.

This function's only job is to load the pre-processed lean cache file.

Args:
    config: The application's configuration dictionary.
    logger: The SDC logger instance.

Returns:
    A list of customer dictionaries, or None on failure.
    *   **Key Inputs:** ['config', 'logger']
    *   **Outputs:** Not specified

**Dependencies:**

*   **Internal:** ['sdc.models.cuis_v1']
*   **External:** ['typing', 'os', 'json']

---

## File Path: /a0/syncro_data_consolidator/src/sdc/utils/date_utils.py

**Core Purpose:** Utility functions for parsing and handling dates and times.

**Key Components (Classes/Functions):**

*   **Function:** `parse_datetime_utc`
    *   **Purpose:** Parses a date string into a timezone-aware datetime object in UTC.

This function handles various common formats and ensures the final
datetime object is consistently in UTC.

Args:
    date_string: The string representation of the date to parse.
    config: The application's configuration dictionary for logging.

Returns:
    A timezone-aware datetime object in UTC, or None if parsing fails
    or the input string is empty.
    *   **Key Inputs:** ['date_string', 'config']
    *   **Outputs:** Not specified

**Dependencies:**

*   **Internal:** ['sdc.utils.sdc_logger']
*   **External:** ['typing', 'datetime', 'dateutil.parser']

---

## File Path: /a0/syncro_data_consolidator/src/sdc/utils/llm_utils.py

**Core Purpose:** No module docstring found.

**Key Components (Classes/Functions):**

*   **Function:** `get_llm_client`
    *   **Purpose:** Factory function to create and return an LLM client based on configuration.

Args:
    capability (str): The desired LLM capability (e.g., 'complex', 'embedding').
    config (dict): The main SDC configuration dictionary.
    logger: The SDC logger instance.

Returns:
    Optional[Union[ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings]]:
        An instantiated LLM client or None if an error occurs or capability is not found.
    *   **Key Inputs:** ['capability', 'config', 'logger']
    *   **Outputs:** Not specified

**Dependencies:**

*   **Internal:** []
*   **External:** ['typing', 'langchain_google_genai']

---

## File Path: /a0/syncro_data_consolidator/src/sdc/utils/sdc_logger.py

**Core Purpose:** Standardized logging utility for the SDC project.

**Key Components (Classes/Functions):**

*   **Function:** `get_sdc_logger`
    *   **Purpose:** Configures and returns a logger instance based on application config.

This function sets up a logger with handlers for file and/or terminal
output based on the provided configuration dictionary. It ensures that
handlers are not added multiple times to the same logger instance.

Args:
    name: The name for the logger, typically __name__ from the calling module.
    config: The application's configuration dictionary, expected to contain
            a 'logging' section.

Returns:
    A configured logging.Logger instance.
    *   **Key Inputs:** ['name', 'config']
    *   **Outputs:** Not specified

**Dependencies:**

*   **Internal:** []
*   **External:** ['typing', 'logging', 'os']

---

