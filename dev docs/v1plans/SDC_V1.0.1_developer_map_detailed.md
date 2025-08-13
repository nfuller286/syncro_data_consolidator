# SDC Developer's Map (Detailed)

## File Path: /a0/syncro_data_consolidator/src/sdc/ingestors/notes_json_ingestor.py

**Core Purpose:** Ingests data from a legacy `notes.json` file, transforms ticket and to-do entries into the CUIS format, and saves each as a separate file.

**Key Components (Classes/Functions):**

---

*   **Function Name:** `_get_file_metadata`
    *   **Purpose:** Retrieves the size and modification time of a file to check if it has changed since the last run.
    *   **Key Logic Steps:**
        *   1. Calls `os.stat()` on the provided `file_path` to get file status.
        *   2. Returns a dictionary containing the file size (`st_size`) and modification time (`st_mtime`).
        *   3. Catches `FileNotFoundError` and returns an empty dictionary if the file does not exist.
    *   **Primary Inputs:** '`file_path`: The string path to the file to inspect.'
    *   **Primary Output:** 'A dictionary with `size` and `mtime` keys, or an empty dictionary on error.'

---

*   **Function Name:** `_load_ingestor_state`
    *   **Purpose:** Loads a JSON state file that tracks which files have already been processed.
    *   **Key Logic Steps:**
        *   1. Constructs the full path to `ingestor_file_state.json` located in the configured cache folder.
        *   2. Opens and reads the file using `json.load()`.
        *   3. Returns the loaded data as a dictionary.
        *   4. If the file is not found or contains invalid JSON, it logs a message and returns an empty dictionary to start fresh.
    *   **Primary Inputs:** '`config`: the main application dictionary', '`logger`: the logger instance'.
    *   **Primary Output:** 'A dictionary containing the saved state, or an empty dictionary.'

---

*   **Function Name:** `_save_ingestor_state`
    *   **Purpose:** Saves the updated processing state to the `ingestor_file_state.json` file.
    *   **Key Logic Steps:**
        *   1. Constructs the full path to `ingestor_file_state.json`.
        *   2. Ensures the cache directory exists using `os.makedirs(..., exist_ok=True)`.
        *   3. Opens the file in write mode.
        *   4. Writes the provided `state` dictionary to the file as indented JSON.
    *   **Primary Inputs:** '`state`: a dictionary representing the current processing state', '`config`: the main application dictionary', '`logger`: the logger instance'.
    *   **Primary Output:** None (modifies files in-place).

---

*   **Function Name:** `ingest_notes`
    *   **Purpose:** Main orchestration function to read the `notes.json` file, process its contents, and save them as CUIS items.
    *   **Key Logic Steps:**
        *   1. Initializes the logger for this module.
        *   2. Gets the path for `notes.json` from the config.
        *   3. Calls `_get_file_metadata()` for the notes file and `_load_ingestor_state()` to get the last known state.
        *   4. Compares the current file metadata to the saved state. If they match, logs that the file is unchanged and exits.
        *   5. Loads the main `notes.json` file into a dictionary named `data`.
        *   6. Iterates through each `ticket` in the `data['tickets']` list.
        *   7. For each ticket, it creates a `CUISV1` object and maps fields from the JSON ticket to the CUIS model (e.g., `subject` -> `summary_title_or_subject`).
        *   8. It then iterates through nested `notes` and `to-do` items within the ticket, creating `CuisEntry` objects and appending them to the main CUIS item.
        *   9. Calls `save_cuis_to_file()` for the newly created CUIS item.
        *   10. Iterates through each `todo` in the root `data['toDoItems']` list, creating a separate CUIS item for each and saving it.
        *   11. After processing, if there were no errors, it updates the state with the current file's metadata and calls `_save_ingestor_state()`.
    *   **Primary Inputs:** '`config`: the main application dictionary'.
    *   **Primary Output:** None (modifies files in-place).

---

**Dependencies:**

*   **Internal:** `['sdc.models.cuis_v1', 'sdc.utils.cuis_handler', 'sdc.utils.date_utils', 'sdc.utils.sdc_logger']`
*   **External:** `['json', 'os', 'typing']`


## File Path: /a0/syncro_data_consolidator/src/sdc/ingestors/screenconnect_log_ingestor.py

**Core Purpose:** Ingests ScreenConnect session logs from a CSV file, consolidates related connection events into unified sessions, transforms them into CUIS format, and saves each session as a separate file.

**Key Components (Classes/Functions):**

---

*   **Function Name:** `_get_file_metadata`
    *   **Purpose:** Retrieves the size and modification time of a file to check if it has changed.
    *   **Key Logic Steps:**
        *   1. Calls `os.stat()` on the `file_path`.
        *   2. Returns a dictionary with `size` and `mtime`.
        *   3. Returns an empty dictionary if the file is not found.
    *   **Primary Inputs:** '`file_path`: The string path to the file.'
    *   **Primary Output:** 'A dictionary with file metadata or an empty dictionary.'

---

*   **Function Name:** `_load_ingestor_state`
    *   **Purpose:** Loads a JSON state file that tracks the metadata of the last processed log file.
    *   **Key Logic Steps:**
        *   1. Constructs the path to `screenconnect_log_ingestor_state.json` in the cache folder.
        *   2. Opens and parses the JSON file.
        *   3. Returns the loaded state as a dictionary, or an empty dictionary if the file doesn't exist or is invalid.
    *   **Primary Inputs:** '`config`: the main application dictionary', '`logger`: the logger instance'.
    *   **Primary Output:** 'A dictionary of the saved state, or an empty dictionary.'

---

*   **Function Name:** `_save_ingestor_state`
    *   **Purpose:** Saves the processing state to the `screenconnect_log_ingestor_state.json` file.
    *   **Key Logic Steps:**
        *   1. Constructs the path to the state file.
        *   2. Ensures the directory exists.
        *   3. Writes the provided `state` dictionary to the file as indented JSON.
    *   **Primary Inputs:** '`state`: a dictionary with the current processing state', '`config`: the main application dictionary', '`logger`: the logger instance'.
    *   **Primary Output:** None (modifies files in-place).

---

*   **Function Name:** `ingest_screenconnect`
    *   **Purpose:** Main orchestration function to read, clean, consolidate, and process ScreenConnect CSV logs.
    *   **Key Logic Steps:**
        *   1. Finds the first and oldest CSV file in the configured log directory.
        *   2. Loads the ingestor state and the CSV file's metadata to check if the file needs processing. If not, it exits.
        *   3. Reads the CSV into a pandas DataFrame.
        *   4. Cleans the data: converts time columns to datetime objects, drops rows with essential missing data.
        *   5. Sorts the DataFrame by customer (`SessionCustomProperty1`), user (`ParticipantName`), and connection time.
        *   6. **Consolidates Sessions:** Iterates through the sorted events, grouping them into a single logical "session" if they are for the same customer/user and the time gap between events is less than `SESSION_WINDOW_MINUTES` (30 minutes).
        *   7. Iterates through the consolidated `sessions` list.
        *   8. For each session, it creates a `CUISV1` object.
        *   9. Populates the CUIS object with session-level data (start/end times, duration, user, customer).
        *   10. Extracts and stores computer names and other details in `source_specific_details`.
        *   11. Iterates through the raw `events` within the session, creating a `CuisEntry` for each connection event.
        *   12. Calls `save_cuis_to_file()` for the new CUIS object.
        *   13. After processing all sessions, it updates and saves the ingestor state with the CSV file's metadata.
    *   **Primary Inputs:** '`config`: the main application dictionary'.
    *   **Primary Output:** None (modifies files in-place).

---

**Dependencies:**

*   **Internal:** `['sdc.models.cuis_v1', 'sdc.utils.cuis_handler', 'sdc.utils.date_utils', 'sdc.utils.sdc_logger']`
*   **External:** `['pandas', 'os', 'json', 'typing', 'datetime']`


## File Path: /a0/syncro_data_consolidator/src/sdc/ingestors/st_chat_ingestor.py

**Core Purpose:** Ingests SillyTavern `.jsonl` chat logs, segments the messages into distinct sessions based on time gaps, transforms each session into the CUIS format, and saves it as a separate file.

**Key Components (Classes/Functions):**

---

*   **Function Name:** `_get_file_metadata`
    *   **Purpose:** Retrieves the size and modification time of a file to check if it has changed.
    *   **Key Logic Steps:**
        *   1. Calls `os.stat()` on the `file_path`.
        *   2. Returns a dictionary with `size` and `mtime`.
        *   3. Returns an empty dictionary if the file is not found.
    *   **Primary Inputs:** '`file_path`: The string path to the file.'
    *   **Primary Output:** 'A dictionary with file metadata or an empty dictionary.'

---

*   **Function Name:** `_load_ingestor_state`
    *   **Purpose:** Loads a JSON state file that tracks the metadata of already processed `.jsonl` files.
    *   **Key Logic Steps:**
        *   1. Constructs the path to `st_chat_ingestor_file_state.json` in the cache folder.
        *   2. Opens and parses the JSON file.
        *   3. Returns the loaded state as a dictionary, or an empty dictionary if the file doesn't exist or is invalid.
    *   **Primary Inputs:** '`config`: the main application dictionary', '`logger`: the logger instance'.
    *   **Primary Output:** 'A dictionary of the saved state, or an empty dictionary.'

---

*   **Function Name:** `_save_ingestor_state`
    *   **Purpose:** Saves the processing state to the `st_chat_ingestor_file_state.json` file.
    *   **Key Logic Steps:**
        *   1. Constructs the path to the state file.
        *   2. Ensures the directory exists.
        *   3. Writes the provided `state` dictionary to the file as indented JSON.
    *   **Primary Inputs:** '`state`: a dictionary with the current processing state', '`config`: the main application dictionary', '`logger`: the logger instance'.
    *   **Primary Output:** None (modifies files in-place).

---

*   **Function Name:** `ingest_sillytavern_chats`
    *   **Purpose:** Main orchestration function to find, read, segment, and process SillyTavern chat logs.
    *   **Key Logic Steps:**
        *   1. Iterates through all files in the configured `sillytavern_chat_input_folder`.
        *   2. For each `.jsonl` file, it checks against the loaded state to see if the file is new or has been modified. Skips if unchanged.
        *   3. Reads the file, parsing the first line as metadata and subsequent lines as individual chat messages.
        *   4. Sorts all messages chronologically based on their `send_date` timestamp.
        *   5. **Segments Sessions:** Iterates through the sorted messages, starting a new session whenever the time between two consecutive messages exceeds the configured `session_gap_minutes`.
        *   6. Iterates through the list of `sessions`.
        *   7. For each session, it creates a `CUISV1` object.
        *   8. Populates the CUIS object with session-level data from the log's metadata (character name, user name) and the session's messages (start/end times).
        *   9. Iterates through the messages within the session, creating a `CuisEntry` for each message and adding it to the CUIS item.
        *   10. Stores the full, structured list of messages in `source_specific_details`.
        *   11. Calls `save_cuis_to_file()` for the new CUIS object.
        *   12. After a file is processed successfully (no errors in any session), its metadata is added to the state.
        *   13. After all files are processed, if the state was updated, it calls `_save_ingestor_state()`.
    *   **Primary Inputs:** '`config`: the main application dictionary', '`logger`: the logger instance'.
    *   **Primary Output:** None (modifies files in-place).

---

**Dependencies:**

*   **Internal:** `['sdc.models.cuis_v1', 'sdc.utils.cuis_handler', 'sdc.utils.date_utils']`
*   **External:** `['json', 'os', 'datetime', 'typing']`


## File Path: /a0/syncro_data_consolidator/src/sdc/ingestors/syncro_customer_contact_cacher.py

**Core Purpose:** Fetches all customer and contact data from the Syncro API, saves the raw data, and then creates a smaller, optimized 'lean' cache for efficient use by other modules.

**Key Components (Classes/Functions):**

---

*   **Function Name:** `_fetch_paginated_data`
    *   **Purpose:** A generic utility to retrieve all records from a paginated Syncro API endpoint.
    *   **Key Logic Steps:**
        *   1. Enters a `while` loop that continues as long as the current page is less than or equal to the max pages (initially 100).
        *   2. Makes a `requests.get()` call to the `endpoint_url` with the current page number as a parameter.
        *   3. Extracts the list of items from the response JSON (e.g., from the `data['customers']` key).
        *   4. Appends the retrieved items to the `all_items` list.
        *   5. Checks the response `meta` data for `total_pages` to know when to stop looping.
        *   6. If there are no more items on a page or the last page is reached, the loop breaks.
        *   7. Returns the complete list of `all_items`.
    *   **Primary Inputs:** '`endpoint_url`: The full URL for the API endpoint', '`headers`: Dictionary containing the authorization token', '`logger`: the logger instance'.
    *   **Primary Output:** 'A list of dictionaries, where each dictionary is an item from the API (e.g., a customer or contact), or `None` on failure.'

---

*   **Function Name:** `cache_syncro_data`
    *   **Purpose:** Main orchestration function to manage the caching process based on a configured policy.
    *   **Key Logic Steps:**
        *   1. Reads the cache policy (`manual_only`, `if_older_than_hours`, `on_each_run`) from the config.
        *   2. Based on the policy and the existence/age of the `syncro_customers_cache.json` file, it decides if a new fetch is needed (`run_fetch` flag).
        *   3. If `run_fetch` is `False`, the function exits early.
        *   4. If `run_fetch` is `True`, it retrieves the Syncro API key and base URL from config.
        *   5. Calls `_fetch_paginated_data` once for the `/customers` endpoint and once for the `/contacts` endpoint.
        *   6. Saves the complete, raw results to `syncro_customers_cache.json` and `syncro_contacts_cache.json`.
        *   7. **Creates Lean Cache:** If both fetches were successful, it initializes a `defaultdict(list)` to group contacts by customer ID.
        *   8. It iterates through all customers, creating a new 'lean' dictionary for each containing only `id`, `business_name`, and the list of `contacts` gathered in the previous step.
        *   9. Saves this new list of lean customer objects to `lean_customer_cache.json`.
    *   **Primary Inputs:** '`config`: the main application dictionary', '`logger`: the logger instance'.
    *   **Primary Output:** None (modifies files in-place).

---

**Dependencies:**

*   **Internal:** `[]` (This is a self-contained utility)
*   **External:** `['requests', 'json', 'os', 'time', 'collections', 'datetime', 'typing']`


## File Path: /a0/syncro_data_consolidator/src/sdc/ingestors/syncro_ticket_ingestor.py

**Core Purpose:** Ingests ticket data from the Syncro API (or a local test file), transforms each ticket and its comments into the CUIS format, and saves each ticket as a separate file.

**Key Components (Classes/Functions):**

---

*   **Function Name:** `_load_ingestor_state`
    *   **Purpose:** Loads a JSON state file that tracks the timestamp of the last successfully processed ticket from the API.
    *   **Key Logic Steps:**
        *   1. Constructs the path to `syncro_ticket_ingestor_state.json`.
        *   2. Opens and parses the JSON file.
        *   3. Returns the loaded state, or a default dictionary `{'files': {}, 'api': {}}` if the file doesn't exist or is invalid.
    *   **Primary Inputs:** '`config`: the main application dictionary', '`logger`: the logger instance'.
    *   **Primary Output:** 'A dictionary of the saved state.'

---

*   **Function Name:** `_save_ingestor_state`
    *   **Purpose:** Saves the processing state, including the latest ticket timestamp, to a JSON file.
    *   **Key Logic Steps:**
        *   1. Constructs the path to the state file.
        *   2. Writes the provided `state` dictionary to the file as indented JSON.
    *   **Primary Inputs:** '`state`: a dictionary with the current processing state', '`config`: the main application dictionary', '`logger`: the logger instance'.
    *   **Primary Output:** None (modifies files in-place).

---

*   **Function Name:** `_fetch_all_pages`
    *   **Purpose:** A generic utility to retrieve all tickets from the paginated Syncro `/tickets` API endpoint.
    *   **Key Logic Steps:**
        *   1. Enters a `while True` loop.
        *   2. Makes a `requests.get()` call to the API with the current page number and other parameters (like `since_updated_at`).
        *   3. Appends the retrieved tickets to the `all_tickets` list.
        *   4. Checks the response `meta` data for `total_pages` to know when to stop looping.
        *   5. Breaks the loop on error or when the last page is reached.
    *   **Primary Inputs:** '`base_url`: The API base URL', '`headers`: Dictionary with auth token', '`params`: Dictionary with query parameters', '`logger`: the logger instance'.
    *   **Primary Output:** 'A list of dictionaries, where each dictionary is a ticket from the API.'

---

*   **Function Name:** `ingest_syncro_tickets`
    *   **Purpose:** Main orchestration function to fetch Syncro tickets either from the live API or a local test file and process them.
    *   **Key Logic Steps:**
        *   1. Loads the ingestor state using `_load_ingestor_state()`.
        *   2. **Data Source Selection:** Checks if a `test_file_path` is defined in the config. 
        *   3. **If Test File:** It loads tickets from the specified JSON file. It uses file metadata to skip processing if the file is unchanged.
        *   4. **If API:** It constructs the API request. If a `last_updated_at` timestamp exists in the state, it adds it to the API params (`since_updated_at`) to fetch only new/updated tickets. Otherwise, it fetches tickets created in the last 180 days.
        *   5. Calls `_fetch_all_pages()` to get the ticket data.
        *   6. **Client-Side Filtering:** Performs an additional check to ensure it only processes tickets that are strictly newer than the timestamp saved in the state file.
        *   7. Iterates through the `tickets_data` list.
        *   8. For each ticket, it creates a `CUISV1` object and maps ticket fields to the CUIS model.
        *   9. It keeps track of the `latest_timestamp_this_run` to know what timestamp to save for the next run.
        *   10. It iterates through the `comments` on the ticket, creating a `CuisEntry` for each one and appending it to the main CUIS item. It also deduces the comment type (Email, SMS, Note).
        *   11. Calls `save_cuis_to_file()` for the new CUIS object.
        *   12. If the entire run was successful (no errors) and it was a live API run, it updates the state with `latest_timestamp_this_run` (plus one second) and calls `_save_ingestor_state()`.
    *   **Primary Inputs:** '`config`: the main application dictionary'.
    *   **Primary Output:** None (modifies files in-place).

---

**Dependencies:**

*   **Internal:** `['sdc.utils.sdc_logger', 'sdc.utils.cuis_handler', 'sdc.models.cuis_v1', 'sdc.utils.date_utils']`
*   **External:** `['requests', 'json', 'os', 'typing', 'datetime']`


## File Path: /a0/syncro_data_consolidator/src/sdc/models/cuis_v1.py

**Core Purpose:** Defines the Pydantic models for the Core Unified Information Structure (CUIS), which serves as the standardized data format for all information processed by the SDC.

**Key Components (Classes/Functions):**

---

*   **Class Name:** `SdcCore`
    *   **Purpose:** Contains all the internal metadata used by the SDC to track the CUIS item, such as its unique ID, source system, schema version, and processing status.
    *   **Key Logic Steps:** Not applicable (Data Model).
    *   **Primary Inputs:** Not applicable (Data Model).
    *   **Primary Output:** A Pydantic `BaseModel` instance.

---

*   **Class Name:** `CoreContent`
    *   **Purpose:** Holds the essential, normalized content of the item, like a summary title, the main body of text, and key timestamps (creation, start, end).
    *   **Key Logic Steps:** Not applicable (Data Model).
    *   **Primary Inputs:** Not applicable (Data Model).
    *   **Primary Output:** A Pydantic `BaseModel` instance.

---

*   **Class Name:** `EntitiesInvolved`
    *   **Purpose:** Stores information about people and companies related to the item, including fields for both 'guessed' names (from the raw source) and 'authoritative' names (after linking to a definitive source like the Syncro customer list).
    *   **Key Logic Steps:** Not applicable (Data Model).
    *   **Primary Inputs:** Not applicable (Data Model).
    *   **Primary Output:** A Pydantic `BaseModel` instance.

---

*   **Class Name:** `Categorization`
    *   **Purpose:** Contains fields used to classify the item, such as work type, billable status, and tags. It also includes fields for original status/priority from the source system.
    *   **Key Logic Steps:** Not applicable (Data Model).
    *   **Primary Inputs:** Not applicable (Data Model).
    *   **Primary Output:** A Pydantic `BaseModel` instance.

---

*   **Class Name:** `Link`
    *   **Purpose:** Defines the structure for representing a relationship between one CUIS item and another, or between a CUIS item and an external entity.
    *   **Key Logic Steps:** Not applicable (Data Model).
    *   **Primary Inputs:** Not applicable (Data Model).
    *   **Primary Output:** A Pydantic `BaseModel` instance.

---

*   **Class Name:** `CuisEntry`
    *   **Purpose:** Represents a sub-item within a larger CUIS record, such as a single ticket comment, a chat message, or a log entry. This allows a single CUIS item to represent a whole conversation or timeline.
    *   **Key Logic Steps:** Not applicable (Data Model).
    *   **Primary Inputs:** Not applicable (Data Model).
    *   **Primary Output:** A Pydantic `BaseModel` instance.

---

*   **Class Name:** `CUISV1`
    *   **Purpose:** The main, top-level root model that aggregates all the other components (`SdcCore`, `CoreContent`, `CuisEntry`, etc.) into a single, complete CUIS record.
    *   **Key Logic Steps:** Not applicable (Data Model).
    *   **Primary Inputs:** Not applicable (Data Model).
    *   **Primary Output:** A Pydantic `BaseModel` instance representing a complete, unified record.

---

**Dependencies:**

*   **Internal:** `[]`
*   **External:** `['pydantic', 'datetime', 'typing', 'uuid']`


## File Path: /a0/syncro_data_consolidator/src/sdc/processors/cuis_customer_linker.py

**Core Purpose:** Iterates through all newly created CUIS files and attempts to link them to an authoritative Syncro customer and contact from a local cache, using a multi-step process of exact, fuzzy, and LLM-based matching.

**Key Components (Classes/Functions):**

---

*   **Function Name:** `_find_winner_from_llm_response`
    *   **Purpose:** Parses the text response from an LLM to find which of the candidate names it selected.
    *   **Key Logic Steps:**
        *   1. Takes the raw text from the LLM response and the list of original candidates.
        *   2. Cleans and lowercases the LLM response.
        *   3. Iterates through the candidates and compares their name (whether from a dictionary key or a simple string) to the cleaned LLM response.
        *   4. If a match is found, it returns the original candidate object/string.
        *   5. If the LLM's response does not exactly match any candidate name, it logs an error and returns `None`.
    *   **Primary Inputs:** '`llm_response`: The raw text content from the LLM', '`candidates`: The list of candidate objects (dicts) or strings that were sent to the LLM', '`match_key`: The dictionary key to use for the name if candidates are dicts', '`logger`: the logger instance'.
    *   **Primary Output:** 'The winning candidate object/string from the original list, or `None`.'

---

*   **Function Name:** `link_customers_to_cuis`
    *   **Purpose:** Main orchestration function that drives the entire customer and contact linking process for all applicable CUIS files.
    *   **Key Logic Steps:**
        *   1. Loads the `lean_customer_cache.json` file using `cuis_handler.load_lean_customer_cache`. If this fails, the process aborts.
        *   2. Scans the CUIS output directory for all `.json` files.
        *   3. For each file, it loads the CUIS object.
        *   4. **Pre-linking Checks:** It first checks if the CUIS item should be skipped (e.g., status is not 'new', it's already linked, or it's from a non-linkable source like 'SillyTavern').
        *   5. **Customer Linking - Step 1 (Exact Match):** It checks for a single, case-insensitive exact match between the `syncro_customer_name_guessed` and a `business_name` in the customer cache.
        *   6. **Customer Linking - Step 2 (Fuzzy Match):** If no exact match, it uses `thefuzz.process.extract` to find the top 5 potential matches. It then applies rules to auto-select a winner if there's a single high-confidence match or one match is significantly better than the next.
        *   7. **Customer Linking - Step 3 (LLM Disambiguation):** If fuzzy matching is ambiguous, it formats a prompt with the candidate names and sends it to a 'lightweight' LLM. It then uses `_find_winner_from_llm_response` to parse the result.
        *   8. **If Customer Winner Found:** It populates the `syncro_customer_id_authoritative` and `syncro_customer_name_authoritative` fields.
        *   9. **Contact Linking:** It then repeats a similar multi-step logic (fuzzy match -> LLM) for the `syncro_contact_name_guessed`, but searches only within the `contacts` list of the winning customer.
        *   10. **Finalize:** It updates the CUIS item's processing status ('linked' or 'error') and last updated timestamp, then saves the file back to disk using `cuis_handler.save_cuis_to_file`.
    *   **Primary Inputs:** '`config`: the main application dictionary', '`logger`: the logger instance'.
    *   **Primary Output:** None (modifies files in-place).

---

**Dependencies:**

*   **Internal:** `['sdc.models.cuis_v1', 'sdc.utils']` (which implicitly includes `cuis_handler` and `llm_utils`)
*   **External:** `['thefuzz', 'os', 'json', 'datetime', 'typing']`


## File Path: /a0/syncro_data_consolidator/src/sdc/processors/cuis_embedding_generator.py

**Core Purpose:** This file is currently empty and appears to be a placeholder for a future processor that will generate vector embeddings for CUIS items.

**Key Components (Classes/Functions):**

*   None

---

**Dependencies:**

*   **Internal:** `[]`
*   **External:** `[]`


## File Path: /a0/syncro_data_consolidator/src/sdc/processors/cuis_llm_analyzer.py

**Core Purpose:** This file is currently empty and appears to be a placeholder for a future processor that will use a large language model to analyze and enrich CUIS items.

**Key Components (Classes/Functions):**

*   None

---

**Dependencies:**

*   **Internal:** `[]`
*   **External:** `[]`


## File Path: /a0/syncro_data_consolidator/src/sdc/run_sdc.py

**Core Purpose:** Acts as the main entry point and command-line interface (CLI) orchestrator for the entire SDC application, allowing users to run specific caches, ingestors, processors, or full pipelines.

**Key Components (Classes/Functions):**

---

*   **Function Name:** `main`
    *   **Purpose:** To initialize the application, parse user commands from the command line, and execute the corresponding sequence of operations.
    *   **Key Logic Steps:**
        *   1. Loads the application configuration by calling `load_config()`.
        *   2. Initializes the logger by calling `get_sdc_logger()`.
        *   3. Sets up the command-line argument parser (`argparse`) with four main sub-commands: `cache`, `ingest`, `process`, and `run`.
        *   4. Parses the arguments provided by the user when running the script.
        *   5. **`cache` command logic:** If the command is `cache` and the source is `syncro`, it calls `cache_syncro_data()`.
        *   6. **`ingest` command logic:** If the command is `ingest`, it calls the appropriate ingestor function(s) based on the `--source` argument (`syncro`, `sillytavern`, `notes`, `screenconnect`, or `all`).
        *   7. **`process` command logic:** If the command is `process`, it calls the appropriate processor function(s) based on the `--step` argument (`customer_linking` or `all`).
        *   8. **`run` command logic:** If the command is `run`, it executes a predefined sequence of functions. The `full` pipeline runs the Syncro cacher, all ingestors, and the customer linker in the correct order.
    *   **Primary Inputs:** None (reads command-line arguments from `sys.argv` via `argparse`).
    *   **Primary Output:** None (modifies files or calls other functions that do).

---

**Dependencies:**

*   **Internal:** `['sdc.utils.config_loader', 'sdc.utils.sdc_logger', 'sdc.ingestors.syncro_customer_contact_cacher', 'sdc.ingestors.notes_json_ingestor', 'sdc.ingestors.screenconnect_log_ingestor', 'sdc.ingestors.st_chat_ingestor', 'sdc.ingestors.syncro_ticket_ingestor', 'sdc.processors.cuis_customer_linker']`
*   **External:** `['argparse']`


## File Path: /a0/syncro_data_consolidator/src/sdc/utils/config_loader.py

**Core Purpose:** Finds, loads, parses, and caches the main `config.json` file, while also resolving path placeholders and applying environment variable overrides.

**Key Components (Classes/Functions):**

---

*   **Function Name:** `_resolve_placeholders_recursive`
    *   **Purpose:** To recursively search through the configuration dictionary and replace placeholder strings (e.g., `{{project_root}}`) with their actual values.
    *   **Key Logic Steps:**
        *   1. Iterates through the items in the input dictionary or list.
        *   2. If a value is a string, it uses a regular expression to find all `{{placeholder}}` instances.
        *   3. For each placeholder, it looks up the value in the `templates` dictionary and performs a replacement.
        *   4. If the dictionary key implies a path (contains 'folder' or 'path'), it normalizes the result with `os.path.normpath`.
        *   5. It calls itself recursively for any nested dictionaries or lists.
        *   6. The function runs in a loop in its parent to handle nested placeholders (e.g., a path that depends on the `project_root`).
    *   **Primary Inputs:** '`obj`: The dictionary or list to process', '`templates`: A dictionary mapping placeholder names to their string values'.
    *   **Primary Output:** 'A boolean indicating if any replacements were made during the pass.'

---

*   **Function Name:** `_find_and_load_config`
    *   **Purpose:** The main internal function that locates `config.json`, loads it, and orchestrates all processing.
    *   **Key Logic Steps:**
        *   1. **Find Project Root:** Traverses up the directory tree from the current file's location to find the `syncro_data_consolidator` directory, establishing it as the project root.
        *   2. **Load Config:** Loads the `config/config.json` file.
        *   3. **Resolve Placeholders:** Seeds a `templates` dictionary with the `project_root` path and then calls `_resolve_placeholders_recursive` in a loop to resolve all placeholders.
        *   4. **Apply Environment Overrides:** Uses `os.getenv()` to check for `SYNCRO_API_KEY` and `GOOGLE_API_KEY`. If they exist, their values overwrite the corresponding keys in the config dictionary.
    *   **Primary Inputs:** None.
    *   **Primary Output:** 'A dictionary containing the fully processed configuration, or `None` on failure.'

---

*   **Function Name:** `load_config`
    *   **Purpose:** The public-facing function that provides global, cached access to the application configuration.
    *   **Key Logic Steps:**
        *   1. Uses a global variable `_cached_config` to store the configuration.
        *   2. If `_cached_config` is `None` (i.e., on the first call), it calls `_find_and_load_config()` to load everything.
        *   3. On all subsequent calls, it immediately returns the `_cached_config` object without re-reading or re-processing the file.
    *   **Primary Inputs:** None.
    *   **Primary Output:** 'The cached configuration dictionary.'

---

**Dependencies:**

*   **Internal:** `[]`
*   **External:** `['json', 'os', 're', 'typing']`


## File Path: /a0/syncro_data_consolidator/src/sdc/utils/cuis_handler.py

**Core Purpose:** Provides essential utility functions for saving and loading CUIS objects to/from the filesystem, and for loading the specialized lean customer cache.

**Key Components (Classes/Functions):**

---

*   **Function Name:** `save_cuis_to_file`
    *   **Purpose:** To serialize a CUISV1 Pydantic object and write it to a JSON file.
    *   **Key Logic Steps:**
        *   1. Gets the output directory path from the `config`.
        *   2. Ensures the output directory exists using `os.makedirs(..., exist_ok=True)`.
        *   3. Creates a unique filename using the `sdc_cuis_id` from the object (e.g., `uuid.json`).
        *   4. Constructs the full file path.
        *   5. Opens the file in write mode and uses the Pydantic `.model_dump_json(indent=4)` method to write the object's data as a formatted JSON string.
    *   **Primary Inputs:** '`cuis_object`: The `CUISV1` Pydantic object to save', '`config`: the main application dictionary', '`logger`: the logger instance'.
    *   **Primary Output:** None (modifies files in-place).

---

*   **Function Name:** `load_cuis_from_file`
    *   **Purpose:** To load a single CUIS JSON file from the filesystem and parse it back into a CUISV1 Pydantic object.
    *   **Key Logic Steps:**
        *   1. Opens the specified `file_path` in read mode.
        *   2. Loads the raw data using `json.load()`.
        *   3. Validates the loaded data against the `CUISV1` model by calling `CUISV1.model_validate(data)`.
        *   4. Returns the resulting `CUISV1` object.
        *   5. Catches and logs errors for `FileNotFoundError`, `json.JSONDecodeError`, and any other exceptions, returning `None` in all error cases.
    *   **Primary Inputs:** '`file_path`: The full path to the CUIS JSON file', '`logger`: the logger instance'.
    *   **Primary Output:** 'A `CUISV1` Pydantic object, or `None` if loading or validation fails.'

---

*   **Function Name:** `load_lean_customer_cache`
    *   **Purpose:** To load the `lean_customer_cache.json` file, which is a pre-processed, lightweight list of customers and their contacts.
    *   **Key Logic Steps:**
        *   1. Constructs the full path to `lean_customer_cache.json` using the cache folder path from the `config`.
        *   2. Opens the file and loads its contents using `json.load()`.
        *   3. Returns the resulting list of customer dictionaries.
        *   4. Catches and logs errors if the file is not found or cannot be parsed, returning `None`.
    *   **Primary Inputs:** '`config`: the main application dictionary', '`logger`: the logger instance'.
    *   **Primary Output:** 'A list of customer dictionaries, or `None` on failure.'

---

**Dependencies:**

*   **Internal:** `['sdc.models.cuis_v1']`
*   **External:** `['os', 'json', 'typing']`


## File Path: /a0/syncro_data_consolidator/src/sdc/utils/date_utils.py

**Core Purpose:** Provides a robust, centralized function to parse various date string formats into standardized, timezone-aware UTC datetime objects.

**Key Components (Classes/Functions):**

---

*   **Function Name:** `parse_datetime_utc`
    *   **Purpose:** To flexibly parse a date string, correctly handle both timezone-naive and timezone-aware inputs, and return a standardized UTC datetime object.
    *   **Key Logic Steps:**
        *   1. Returns `None` immediately if the input `date_string` is empty.
        *   2. Uses the powerful `dateutil.parser.parse` function to convert the string into a Python datetime object.
        *   3. **Handles Naive Datetimes:** If the parsed object has no timezone info (`dt_object.tzinfo is None`), it assumes the time is UTC and attaches the UTC timezone.
        *   4. **Handles Aware Datetimes:** If the parsed object already has timezone info, it converts the object to the UTC timezone to ensure all outputs from this function are standardized.
        *   5. If parsing fails for any reason (e.g., invalid format), it catches the exception and returns `None`.
    *   **Primary Inputs:** '`date_string`: An optional string containing the date to be parsed', '`config`: the main application dictionary (used to initialize the logger)'.
    *   **Primary Output:** 'A timezone-aware `datetime` object in UTC, or `None` if the input is empty or parsing fails.'

---

**Dependencies:**

*   **Internal:** `['sdc.utils.sdc_logger']`
*   **External:** `['datetime', 'typing', 'dateutil.parser']`


## File Path: /a0/syncro_data_consolidator/src/sdc/utils/llm_utils.py

**Core Purpose:** Provides a factory function to create and configure specific LLM clients (e.g., for chat, for embeddings) from the `langchain_google_genai` library based on settings in the main config file.

**Key Components (Classes/Functions):**

---

*   **Function Name:** `get_llm_client`
    *   **Purpose:** To abstract away the details of LLM client instantiation, returning a ready-to-use client for a specific task ('capability').
    *   **Key Logic Steps:**
        *   1. Retrieves the `llm_config` block from the main application `config`.
        *   2. Determines the `active_provider` (e.g., 'google_gemini').
        *   3. Based on the provider, it retrieves the specific configuration block (e.g., `google_gemini`).
        *   4. It gets the API key from the provider's config.
        *   5. It looks up the specific model name to use based on the requested `capability` (e.g., the 'lightweight' capability might map to the 'gemini-pro' model).
        *   6. **If `capability` is 'embedding':** It instantiates and returns a `GoogleGenerativeAIEmbeddings` client.
        *   7. **Otherwise:** It instantiates and returns a `ChatGoogleGenerativeAI` client for conversational tasks.
        *   8. Returns `None` if any configuration is missing or an error occurs.
    *   **Primary Inputs:** '`capability`: A string like 'lightweight' or 'embedding' that maps to a model in the config', '`config`: the main application dictionary', '`logger`: the logger instance'.
    *   **Primary Output:** 'An instantiated `langchain_google_genai` client object, or `None` on failure.'

---

**Dependencies:**

*   **Internal:** `[]`
*   **External:** `['typing', 'langchain_google_genai']`


## File Path: /a0/syncro_data_consolidator/src/sdc/utils/sdc_logger.py

**Core Purpose:** Provides a standardized factory function to create and configure logger instances that can write to both a file and the terminal, based on settings in the config.

**Key Components (Classes/Functions):**

---

*   **Function Name:** `get_sdc_logger`
    *   **Purpose:** To provide a single, consistent way to get a logger instance anywhere in the application, ensuring that handlers are not duplicated.
    *   **Key Logic Steps:**
        *   1. Gets a logger instance with the specified `name` using `logging.getLogger(name)`.
        *   2. **Prevents Duplicate Handlers:** Checks if the logger already has handlers. If so, it returns the existing logger immediately to prevent adding more handlers on subsequent calls.
        *   3. Retrieves logging settings (`log_level`, `log_file_path`, `log_to_terminal`) from the `config` dictionary, using safe defaults.
        *   4. Sets the logger's main level (e.g., `INFO`, `DEBUG`).
        *   5. Creates a standard log message formatter.
        *   6. **File Handler:** If a `log_file_path` is configured, it ensures the directory exists, creates a `FileHandler`, sets the formatter, and adds it to the logger.
        *   7. **Terminal Handler:** If `log_to_terminal` is `True`, it creates a `StreamHandler`, sets the formatter, and adds it to the logger.
        *   8. Adds a `NullHandler` if no other handlers were configured, to prevent warnings.
    *   **Primary Inputs:** '`name`: The name for the logger, typically `__name__` from the calling module', '`config`: the main application dictionary'.
    *   **Primary Output:** 'A fully configured `logging.Logger` instance.'

---

**Dependencies:**

*   **Internal:** `[]`
*   **External:** `['logging', 'os', 'typing']`

