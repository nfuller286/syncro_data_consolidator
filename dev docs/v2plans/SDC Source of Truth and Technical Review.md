# Project: syncro_data_consolidator - Source of Truth & Technical Review

## 1. High-Level Overview
The `syncro_data_consolidator` project is an automated data processing pipeline designed to ingest information from various sources, including the SyncroMSP API, ScreenConnect logs, SillyTavern chat logs, and structured JSON notes. It consolidates this disparate data, linking related items and structuring them into unified formats like Customer-related Unified Items (CUIs) and user sessions. The system leverages Large Language Models (LLMs), with configurable providers (Google Gemini, local instances), for advanced data analysis. The project is built to be highly configurable, managing its own data paths, logging, API credentials, and data processing defaults like caching policies and matching thresholds.

## 2. Configuration (`config.json`)
The `config.json` file is the central configuration hub for the application, defining file paths, logging behavior, API credentials, LLM settings, and processing parameters.

### `project_paths`
This section defines all the key directory and file paths used by the application. It uses a template system (e.g., `{{project_root}}`) to build absolute paths from a root directory, making the project portable.
*   **`data_folder`**: The main folder for all application data.
*   **`input_folder` / `output_folder`**: Subdirectories for raw input data and processed output files.
*   **`logs_folder`**: Contains application log files.
*   **Specific Paths**: Defines exact locations for various inputs (notes, logs) and outputs (CUIs, sessions, reports).
*   **`cache_folder`**: Location for storing cached data to speed up subsequent runs.

### `logging`
Controls the application's logging behavior.
*   **`log_file_path`**: The full path to the log file, using the `logs_folder` variable.
*   **`log_level`**: Sets the logging verbosity (e.g., `INFO`).
*   **`log_to_terminal`**: A boolean (`true`) to enable or disable printing logs directly to the console.

### `syncro_api`
Contains credentials and endpoints for interacting with the SyncroMSP API.
*   **`base_url`**: The root URL for the Syncro API.
*   **`api_key`**: The authentication key for API access. **Note: This key is visible and should be secured.**
*   **`tickets_endpoint`**: The specific API path for retrieving tickets.

### `llm_config`
Manages the configuration for Large Language Models.
*   **`active_provider`**: Specifies which LLM provider to use (`google_gemini` or `local_llm`).
*   **`google_gemini` / `local_llm`**: Each object contains the provider-specific `api_key`, `base_url` (for local), and a mapping of `models` for different task complexities (e.g., `complex`, `general`, `embedding`).
*   **`default_llm_params`**: Sets default parameters like `temperature` and `max_tokens` for LLM requests.

### `processing_defaults`
Defines default behaviors and thresholds for the data processing logic.
*   **`recursive_sillytavern_scan`**: A boolean (`true`) to scan subdirectories for SillyTavern chats.
*   **`syncro_cache_policy`**: Determines when to use cached Syncro data (`if_older_than_hours`).
*   **`syncro_cache_expiry_hours`**: The cache lifetime in hours (`24`).
*   **`customer_linking_fuzzy_match_threshold`**: The similarity score (`95`) required for fuzzy matching to link customers.
*   **`notes_json_filename`**: The expected filename for JSON notes (`notes.json`).

## 3. Core Components & Data Structures
*   **Component: `notes_json_ingestor`**
    *   **File:** `/a0/syncro_data_consolidator/src/sdc/ingestors/notes_json_ingestor.py`
    *   **Purpose:** Ingests data from a legacy `notes.json` file, transforms it into the V2 Session data model, and saves each processed item as a separate session file.
    *   **Key Functions/Methods:**
        *   `_get_file_metadata(file_path: str) -> Dict[str, Any]`: Retrieves the size and modification time for a given file to check if it has changed.
        *   `_load_ingestor_state(config: Dict[str, Any], logger) -> Dict[str, Any]`: Loads the last known state of the ingestor, such as file metadata, from a state file in the cache folder.
        *   `_save_ingestor_state(state: Dict[str, Any], config: Dict[str, Any], logger) -> None`: Saves the current state of the ingestor to a JSON file in the cache folder.
        *   `ingest_notes(config: Dict[str, Any]) -> None`: The main function that orchestrates the ingestion process. It reads tickets and standalone to-do items from `notes.json`, converts them into `Session` objects, and saves them using the `save_session_to_file` utility.
    *   **Attributes/Fields (if it is a data model):**
        *   Not applicable.
*   **Component: `screenconnect_log_ingestor`**
    *   **File:** `/a0/syncro_data_consolidator/src/sdc/ingestors/screenconnect_log_ingestor.py`
    *   **Purpose:** Ingests and processes ScreenConnect session logs from CSV files, transforming them into a structured V2 Session format.
    *   **Key Functions/Methods:**
        *   `_get_file_metadata(file_path: str) -> Dict[str, Any]`: Returns the size and modification time for a given file.
        *   `_load_ingestor_state(config: Dict[str, Any], logger) -> Dict[str, Any]`: Loads the last known processing state of the ingestor from a JSON file to prevent reprocessing unchanged files.
        *   `_save_ingestor_state(state: Dict[str, Any], config: Dict[str, Any], logger) -> None`: Saves the current processing state to a JSON file.
        *   `ingest_screenconnect(config: Dict[str, Any]) -> None`: The main function that loads ScreenConnect CSV logs, cleans the data, consolidates related log entries into distinct user sessions, and transforms each session into the V2 Session data model before saving it.
    *   **Attributes/Fields (if it is a data model):**
        *   Not applicable; this is a processing module, not a data model.
*   **Component: `st_chat_ingestor`**
    *   **File:** `/a0/syncro_data_consolidator/src/sdc/ingestors/st_chat_ingestor.py`
    *   **Purpose:** Ingestor for SillyTavern chat logs in .jsonl format.
    *   **Key Functions/Methods:**
        *   `_get_file_metadata(file_path: str) -> Dict[str, Any]`: Returns file size and modification time.
        *   `_load_ingestor_state(config: Dict[str, Any], logger) -> Dict[str, Any]`: Loads the ingestor state from a JSON file, creating a new state if the file doesn't exist or is invalid.
        *   `_save_ingestor_state(state: Dict[str, Any], config: Dict[str, Any], logger) -> None`: Saves the ingestor state to a JSON file atomically to prevent data corruption.
        *   `_calculate_message_fingerprint(message: Dict[str, Any]) -> str`: Creates a unique, deterministic SHA256 hash for a message based on its timestamp, author, and content.
        *   `ingest_sillytavern_chats(config: Dict[str, Any], logger) -> None`: Loads SillyTavern .jsonl chat logs, deduplicates messages, segments them into sessions based on time gaps, transforms them into the V2 Session format, and saves them as individual JSON files.
    *   **Attributes/Fields (if it is a data model):**
        *   Not applicable; this module contains processing functions, not a data model.
*   **Component: `syncro_customer_contact_cacher`**
    *   **File:** `/a0/syncro_data_consolidator/src/sdc/ingestors/syncro_customer_contact_cacher.py`
    *   **Purpose:** Fetches and caches customer and contact data from a paginated Syncro API based on a defined caching policy.
    *   **Key Functions/Methods:**
        *   `_fetch_paginated_data(endpoint_url: str, headers: Dict[str, str], logger) -> Optional[List[Dict[str, Any]]]`: Iteratively fetches all records from a paginated Syncro API endpoint until all pages are retrieved.
        *   `cache_syncro_data(config: Dict[str, Any], logger) -> None`: Orchestrates the data caching process by checking the cache policy, fetching customer and contact data if necessary, and saving both raw and lean versions of the data to local JSON files.
    *   **Attributes/Fields (if it is a data model):**
        *   Not applicable; this file contains procedural logic, not a data model class.
*   **Component: `syncro_ticket_ingestor`**
    *   **File:** `/a0/syncro_data_consolidator/src/sdc/ingestors/syncro_ticket_ingestor.py`
    *   **Purpose:** Ingests ticket data from the Syncro API or a local test file, transforms it into a structured `Session` object, and saves the result.
    *   **Key Functions/Methods:**
        *   `_get_file_metadata(file_path: str) -> Dict[str, Any]`: Retrieves file metadata (size and modification time) for a given file path.
        *   `_load_ingestor_state(config: Dict[str, Any], logger) -> Dict[str, Any]`: Loads the last saved state of the ingestor from a JSON file to resume from where it left off.
        *   `_save_ingestor_state(state: Dict[str, Any], config: Dict[str, Any], logger) -> None`: Atomically saves the current state of the ingestor to a JSON file.
        *   `_fetch_all_pages(base_url: str, headers: Dict[str, str], params: Dict[str, Any], logger) -> list`: Fetches all paginated ticket results from the Syncro API endpoint.
        *   `ingest_syncro_tickets(config: Dict[str, Any]) -> None`: Orchestrates the entire ingestion process, including fetching data, transforming tickets and their comments into `Session` and `SessionSegment` objects, and saving them.
    *   **Attributes/Fields (if it is a data model):**
        *   Not applicable; this file defines a data ingestion process, not a data model.
*   **Component: `session_v2.py` (Module)**
    *   **File:** `/a0/syncro_data_consolidator/src/sdc/models/session_v2.py`
    *   **Purpose:** Defines the Pydantic data models for structuring a consolidated session, including its metadata, context, insights, and individual event segments.

*   **Component: `SessionSegment`**
    *   **File:** `/a0/syncro_data_consolidator/src/sdc/models/session_v2.py`
    *   **Purpose:** Represents the smallest possible unit of raw data, one atomic event.
    *   **Key Functions/Methods:**
        *   Not applicable (Pydantic data model).
    *   **Attributes/Fields (if it is a data model):**
        *   `segment_id` (`str`): A unique ID for this specific event.
        *   `start_time_utc` (`datetime.datetime`): The start time of the event in UTC.
        *   `end_time_utc` (`datetime.datetime`): The end time of the event in UTC.
        *   `type` (`str`): The kind of event, e.g., 'ChatMessage', 'RemoteConnection', 'TicketComment'.
        *   `author` (`Optional[str]`): Who or what created the event.
        *   `content` (`Optional[str]`): The text content of the event, if any.
        *   `metadata` (`Dict`): A flexible bucket for any other source-specific raw data relevant to this specific segment.

*   **Component: `SessionMeta`**
    *   **File:** `/a0/syncro_data_consolidator/src/sdc/models/session_v2.py`
    *   **Purpose:** Contains metadata about the Session record itself, used for system tracking.
    *   **Key Functions/Methods:**
        *   Not applicable (Pydantic data model).
    *   **Attributes/Fields (if it is a data model):**
        *   `session_id` (`str`): A unique, deterministic hash of core data identifying this session.
        *   `schema_version` (`str`): The version of this model, e.g., '2.0'.
        *   `source_system` (`str`): The system the data came from, e.g., 'ScreenConnect', 'SyncroTicket'.
        *   `source_identifiers` (`List[str]`): The specific source filename(s) or API IDs.
        *   `processing_status` (`str`): The workflow state, e.g., 'Needs Linking', 'Linked', 'Reviewed'.
        *   `processing_log` (`List[str]`): A log of processing steps applied to this session, e.g., 'customer_linker_v2.1'.
        *   `ingestion_timestamp_utc` (`datetime.datetime`): The timestamp when the session was ingested.
        *   `last_updated_timestamp_utc` (`datetime.datetime`): The timestamp when the session was last updated.

*   **Component: `SessionContext`**
    *   **File:** `/a0/syncro_data_consolidator/src/sdc/models/session_v2.py`
    *   **Purpose:** Contains information linking the Session to business entities like customers and projects.
    *   **Key Functions/Methods:**
        *   Not applicable (Pydantic data model).
    *   **Attributes/Fields (if it is a data model):**
        *   `customer_id` (`Optional[int]`): The authoritative Syncro customer ID, populated by the linker.
        *   `customer_name` (`Optional[str]`): The guessed name from the source, or the authoritative name after linking.
        *   `contact_id` (`Optional[int]`): The authoritative Syncro contact ID, populated by the linker.
        *   `contact_name` (`Optional[str]`): The guessed name from the source, or the authoritative name after linking.
        *   `links` (`List[str]`): A list of user-added keywords for project grouping.

*   **Component: `SessionInsights`**
    *   **File:** `/a0/syncro_data_consolidator/src/sdc/models/session_v2.py`
    *   **Purpose:** Contains calculated or generated information derived from the session's content.
    *   **Key Functions/Methods:**
        *   Not applicable (Pydantic data model).
    *   **Attributes/Fields (if it is a data model):**
        *   `session_start_time_utc` (`datetime.datetime`): The calculated start time of the entire session.
        *   `session_end_time_utc` (`datetime.datetime`): The calculated end time of the entire session.
        *   `session_duration_minutes` (`int`): The calculated duration of the session in minutes.
        *   `source_title` (`Optional[str]`): The title as it appeared in the source system (e.g., ticket subject).
        *   `llm_generated_title` (`Optional[str]`): A placeholder for a future AI-generated title.
        *   `generated_summaries` (`Dict[str, str]`): A flexible dictionary for multiple summary types (e.g., 'invoice', 'detailed').
        *   `user_notes` (`str`): A dedicated field for your manual notes and summaries.

*   **Component: `Session`**
    *   **File:** `/a0/syncro_data_consolidator/src/sdc/models/session_v2.py`
    *   **Purpose:** A complete, standardized record of a single, continuous activity from one source.
    *   **Key Functions/Methods:**
        *   Not applicable (Pydantic data model).
    *   **Attributes/Fields (if it is a data model):**
        *   `meta` (`SessionMeta`): Contains all metadata for the session.
        *   `context` (`SessionContext`): Contains the business context links for the session.
        *   `insights` (`SessionInsights`): Contains calculated insights and summaries for the session.
        *   `segments` (`List[SessionSegment]`): A list of all the individual event segments that make up the session.
*   **Component: `session_embedding_generator.py`**
    *   **File:** `/a0/syncro_data_consolidator/src/sdc/processors/session_embedding_generator.py`
    *   **Purpose:** The file is empty and contains no code, so its purpose cannot be determined.
    *   **Key Functions/Methods:**
        *   None: The file is empty and contains no functions.
    *   **Attributes/Fields (if it is a data model):**
        *   None: The file is empty and does not define a data model.
*   **Component: `session_customer_linker`**
    *   **File:** `/a0/syncro_data_consolidator/src/sdc/processors/session_customer_linker.py`
    *   **Purpose:** This module links unprocessed V2 Session items to authoritative Syncro customers and contacts.
    *   **Key Functions/Methods:**
        *   `_find_winner_from_llm_response(llm_response: str, candidates: List[Any], match_key: Optional[str], logger) -> Optional[Any]`: Finds the winning item from a list of candidates based on the LLM's string response by matching it against a specified key in the candidate objects.
        *   `link_customers_to_sessions(config: Dict[str, Any], logger) -> None`: Iterates through unprocessed Session JSON files, attempts to link them to Syncro customers and contacts using exact, fuzzy, and LLM-based matching, and updates the session files with the results.
    *   **Attributes/Fields (if it is a data model):**
        *   Not applicable (This is a processor module, not a data model).
*   **Component: `session_llm_analyzer`**
    *   **File:** `/a0/syncro_data_consolidator/src/sdc/processors/session_llm_analyzer.py`
    *   **Purpose:** This module uses a Large Language Model (LLM) to analyze, enrich, and generate insights for V2 Session data.
    *   **Key Functions/Methods:**
        *   `analyze_sessions_with_llm(config: Dict[str, Any], logger) -> None`: Iterates through session files, uses an LLM to generate insights (like a concise title), and updates the session files with the new information. It skips sessions that have already been processed or are not in a suitable state for analysis.
    *   **Attributes/Fields (if it is a data model):**
        *   Not applicable (this is a processing module, not a data model).
*   **Component: `run_sdc`**
    *   **File:** `/a0/syncro_data_consolidator/src/sdc/run_sdc.py`
    *   **Purpose:** Master orchestrator for the Syncro Data Consolidator (SDC) project, providing a command-line interface to run various data pipelines.
    *   **Key Functions/Methods:**
        *   `main() -> None`: Serves as the main entry point for the application, handling configuration, command-line argument parsing, and executing the requested data ingestion, processing, or caching commands.
    *   **Attributes/Fields (if it is a data model):**
        *   Not applicable (This is an executable script, not a data model).
*   **Component: `cache_utils`**
    *   **File:** `/a0/syncro_data_consolidator/src/sdc/utils/cache_utils.py`
    *   **Purpose:** A utility for handling the loading of cached data files.
    *   **Key Functions/Methods:**
        *   `load_lean_customer_cache(config: Dict[str, Any], logger) -> Optional[List[Dict[str, Any]]]`: Loads the `lean_customer_cache.json` file, which is a pre-processed, lightweight list of customers and their contacts. It takes the application config and a logger as input and returns a list of customer dictionaries or None if the file cannot be loaded or parsed.
    *   **Attributes/Fields (if it is a data model):**
        *   Not applicable (This is a utility module, not a data model).
*   **Component: `config_loader`**
    *   **File:** `/a0/syncro_data_consolidator/src/sdc/utils/config_loader.py`
    *   **Purpose:** A utility for loading, parsing, and caching the project's `config.json` file, with support for placeholder resolution and environment variable overrides.
    *   **Key Functions/Methods:**
        *   `load_config() -> Optional[Dict[str, Any]]`: Serves as the main public entry point to retrieve the application configuration. It uses a global cache to ensure the configuration is loaded only once.
        *   `_find_and_load_config() -> Optional[Dict[str, Any]]`: A private function that locates the project root, reads the `config.json` file, resolves nested placeholders, and applies environment variable overrides for API keys.
        *   `_resolve_placeholders_recursive(obj: Union[Dict, List], templates: Dict[str, str]) -> bool`: A private helper function that recursively traverses a dictionary or list to replace placeholder strings (e.g., `{{project_root}}`) with their corresponding values from a templates dictionary.
    *   **Attributes/Fields (if it is a data model):**
        *   Not applicable (This is a utility module, not a data model).
*   **Component: `date_utils`**
    *   **File:** `/a0/syncro_data_consolidator/src/sdc/utils/date_utils.py`
    *   **Purpose:** Provides utility functions for parsing and handling dates and times.
    *   **Key Functions/Methods:**
        *   `parse_datetime_utc(date_string: Optional[str], config: Dict[str, Any]) -> Optional[datetime]`: Parses a date string from various formats into a standardized, timezone-aware datetime object in UTC, returning `None` if parsing fails.
    *   **Attributes/Fields (if it is a data model):**
        *   Not applicable (this is a utility module).
*   **Component: `llm_utils`**
    *   **File:** `/a0/syncro_data_consolidator/src/sdc/utils/llm_utils.py`
    *   **Purpose:** A factory module to instantiate and configure Language Model (LLM) clients based on specified capabilities and application settings.
    *   **Key Functions/Methods:**
        *   `get_llm_client(capability: str, config: dict, logger: any) -> Optional[Union[ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings]]`: Creates an LLM client for a given capability ('lightweight', 'complex', or 'embedding'). It reads the active provider and model details from the configuration, instantiates the appropriate client (e.g., `ChatGoogleGenerativeAI` for chat, `GoogleGenerativeAIEmbeddings` for embeddings), and returns it. Returns `None` if configuration is missing or an error occurs.
    *   **Attributes/Fields (if it is a data model):**
        *   Not applicable (This is a utility module).
*   **Component: `sdc_logger`**
    *   **File:** `/a0/syncro_data_consolidator/src/sdc/utils/sdc_logger.py`
    *   **Purpose:** A standardized logging utility that configures and provides logger instances for the SDC project.
    *   **Key Functions/Methods:**
        *   `get_sdc_logger(name: str, config: Dict[str, Any]) -> logging.Logger`: Configures and returns a logger instance based on the application config, setting up file and/or terminal handlers as specified.
    *   **Attributes/Fields (if it is a data model):**
        *   Not applicable (this is a utility module).
*   **Component: `session_handler`**
    *   **File:** `/a0/syncro_data_consolidator/src/sdc/utils/session_handler.py`
    *   **Purpose:** A utility module for serializing (saving) and deserializing (loading) Session V2 objects to and from JSON files.
    *   **Key Functions/Methods:**
        *   `save_session_to_file(session_object: Session, config: Dict[str, Any], logger: Any) -> None`: Serializes a Pydantic `Session` object into a JSON file, creating a descriptive filename based on the session's metadata.
        *   `load_session_from_file(file_path: str, logger: Any) -> Optional[Session]`: Loads a single Session JSON file from the given path and parses it into a Pydantic `Session` object, returning `None` if an error occurs.
    *   **Attributes/Fields (if it is a data model):**
        *   Not applicable (this is a utility module for handling session data).

## 4. End-to-End Data Flow
The data flow follows a classic Extract, Transform, Load (ETL) pattern, orchestrated by the main execution script.

1.  **Initiation:** The process begins when a user executes `run_sdc.py` with specific command-line arguments (e.g., `ingest-all`, `process-all`).

2.  **Configuration & Caching:** The `config_loader` utility reads `config.json` to set up all necessary paths and parameters. If required by the cache policy, the `syncro_customer_contact_cacher` is run first to fetch the latest customer and contact data from the Syncro API and store it locally.

3.  **Ingestion:** The script calls one or more `ingestor` modules:
    *   `notes_json_ingestor`, `screenconnect_log_ingestor`, `st_chat_ingestor`, and `syncro_ticket_ingestor` each read data from their respective sources (JSON files, CSV logs, Syncro API).
    *   Each ingestor transforms its raw data into the standardized `Session` object structure defined in `models/session_v2.py`.
    *   The `session_handler` utility is then used to serialize each `Session` object and save it as a distinct JSON file in the output directory.

4.  **Processing & Enrichment:** After ingestion, the `processor` modules are run:
    *   The `session_customer_linker` iterates through the newly created Session files. It loads the cached customer data (via `cache_utils`) and uses a combination of exact, fuzzy, and LLM-based matching to link each session to an authoritative customer and contact. It then updates the Session file with this new context.
    *   The `session_llm_analyzer` performs further enrichment, using `llm_utils` to generate insights like a concise title for the session and updating the file again.

5.  **Output:** The final result is a collection of enriched Session JSON files in the output folder, each representing a standardized, context-aware record of a specific activity.

## 5. Execution Entry Point
The single entry point for the entire application is the `main()` function within the `src/sdc/run_sdc.py` script. This script uses Python's `argparse` library to interpret command-line arguments, which determine which specific ingestion or processing functions are executed. It is responsible for loading the configuration, setting up the logger, and orchestrating the calls to the various ingestor and processor modules.

---

## 6. Open Questions for the Developer
*   **Regarding `session_embedding_generator.py`:** This file is currently empty. What is its intended future functionality? Is it a placeholder for a vector-based similarity search feature?
*   **Regarding `session_customer_linker.py`:** The fuzzy matching threshold is set to a high value of 95. Was this value determined through testing to optimize the balance between precision and recall, or is it a conservative starting point?
*   **Regarding `syncro_customer_contact_cacher.py`:** How does the `_fetch_paginated_data` function handle transient network errors or non-successful HTTP status codes (e.g., 429 Too Many Requests, 5xx Server Errors) from the Syncro API? Are there retry mechanisms or error logging in place for failed API calls?

## 7. Potential Enhancements & Concerns
*   **Critical Concern (Security):** The `config.json` file contains hardcoded API keys for both Syncro and Google Gemini. These secrets should be removed from the configuration file and loaded from environment variables or a dedicated secret management service to prevent them from being accidentally committed to version control. The `config_loader.py` utility already has some support for this that should be fully utilized.
*   **Enhancement (Performance):** The `notes_json_ingestor` reads the entire `notes.json` file into memory. If this legacy file could potentially become very large, consider refactoring to use a streaming JSON parser (like `ijson`) to process it incrementally. This would significantly reduce memory consumption.
*   **Enhancement (Robustness):** While many ingestors use a state-tracking mechanism, consider adding a global lock file or a more robust process management system to prevent multiple instances of `run_sdc.py` from running concurrently and causing race conditions when reading and writing session files.
*   **Positive Note (Maintainability):** The project exhibits a clean architecture with a clear separation of concerns into `ingestors`, `processors`, `models`, and `utils`. This design, along with the standardized `Session` data model, makes the system highly modular and easier to maintain and extend.
