Syncro Data Consolidator (SDC) V1.0 - Project Design Document
Version: 1.1 (Updated)
Date: May 17, 2025 (Date of this compilation)
Project Owner: Nick
Table of Contents:
1.    Project Overview (Phase 1)
1.1. Project Title
1.2. Core Purpose
1.3. SDC V1.0 Objective Statement
1.4. SDC V1.0 Primary Workflow
2.    User Interfaces, System Interactions, & Broader Functionality (Phase 2)
2.1. Interaction Model (V1.0)
2.2. Key Interface Elements (V1.0)
2.3. Key Post-V1.0 Additional Features
3.    Settings and Configuration (Phase 3)
3.1. Central Configuration File (config.json)
3.2. Key Configuration Parameters, Defaults, and Impacts
4.    Technical Considerations and Architecture (Phase 4)
4.1. Data Requirements (Inputs, Outputs, Internal State)
4.2. Event Handling and Integrations (V1.0)
4.3. External Dependencies (V1.0)
4.4. Constraints and Assumptions (V1.0)
4.5. Preliminary Technical Outline (V1.0)
4.5.1. Key Modules/Components
4.5.2. Component Interaction
4.5.3. Code Module Structure
5.    Scope, MVP, and Testing (Phase 5)
5.1. SDC V1.0 MVP Definition (In Scope / Out of Scope)
5.2. SDC V1.0 Success Criteria
5.3. SDC V1.0 Testing Strategies
________________________________________
1. Project Overview (Phase 1)
1.1. Project Title:
Syncro Data Consolidator (SDC)
1.2. Core Purpose:
The SDC project aims to develop an intelligent, iterative system that captures, processes, and consolidates Nick's work-related data from diverse sources. The primary objective is to accurately and efficiently get this information into Nick's RMM (Syncro), ensuring it serves as the comprehensive and reliable central repository for client work, billing information, and operational history. The system is designed to aid Nick by reducing manual data entry, preventing missed information or duplicate work, improving data quality, streamlining documentation, ensuring accurate billing, and ultimately providing data-driven insights to aid in work planning and prioritization.
1.3. SDC V1.0 Objective Statement:
SDC V1.0 will be a suite of Python scripts/modules, orchestrated by Agent Zero or a master CLI script (run_sdc.py). SDC V1.0 will ingest data from key sources (SillyTavern raw chat files, Syncro RMM tickets, custom notes.json files, and ScreenConnect remote access logs), transform this data into a standardized Core Unified Information Structure (CUIS V1.0), and store these CUIS items as JSON files. V1.0 will implement a robust Syncro customer/contact caching mechanism, perform customer linking to CUIS items using fuzzy matching and a targeted LLM call for disambiguation, and include a standalone test script for basic LLM utility functions (e.g., summaries, keywords, embeddings) to prove the pipeline. LLM processing is not part of the main V1.0 data flow beyond the customer disambiguation task. The system will be highly configurable via a central config.json file.
SDC V1.0 will be a suite of Python scripts/modules, orchestrated by Agent Zero or a master CLI script (run_sdc.py). SDC V1.0 will ingest data from key sources (SillyTavern raw chat files, Syncro RMM tickets, custom notes.json files, and ScreenConnect remote access logs), transform this data into a standardized Core Unified Information Structure (CUIS V1.0), and store these CUIS items as JSON files. V1.0 will implement a robust Syncro customer/contact caching mechanism and perform intelligent entity linking using a multi-stage process that combines exact matching, high-confidence fuzzy matching, and a sophisticated LLM-based fallback for ambiguous cases. A standalone test script will be available to prove the LLM utility pipeline. LLM processing is not part of the main V1.0 data flow beyond the entity linking task. The system will be highly configurable via a central config.json file.
1.4. SDC V1.0 Primary Workflow:
* Trigger: User-initiated (Nick via Agent Zero commands or direct CLI execution of run_sdc.py).
* Sequence:
1. Configuration Loading: SDC modules load settings from config.json.
2. Syncro Customer/Contact Caching (Optional, based on policy): The `syncro_customer_contact_cacher.py` module fetches customer/contact data from the Syncro API and saves it to local JSON cache files.
3. Data Ingestion & Initial CUIS Creation (by dedicated ingestor modules):
* SillyTavern Raw Chat Files (`st_chat_ingestor.py`): Scans specified directories for SillyTavern JSONL files. Implements change detection (path, OS last modified, file size, message count). Identifies "ChatUserInputSessions" based on configured time gaps. Transforms each session into a CUIS V1.0 item.
* Syncro RMM Tickets (`syncro_ticket_ingestor.py`): Fetches new or updated tickets from the Syncro API (using updated_at for refresh). Transforms raw Syncro ticket JSON (including nested comments with deduced types) into CUIS V1.0 format.
* Custom notes.json Files (`notes_json_ingestor.py`): Processes the notes.json file specified in config.json. Transforms its "tickets" and "toDoItems" arrays into CUIS V1.0 items. (V1.0 Idempotency: Process once, or replace derived CUIS items if re-run).
* ScreenConnect Remote Access Logs (`screenconnect_log_ingestor.py`): Processes the first alphabetically sorted ScreenConnect CSV log file from the configured input directory. Transforms each row into a CUIS V1.0 item.
4. CUIS Enrichment & Processing:
* Customer & Contact Linking (`cuis_customer_linker.py`): Processes CUIS items using a multi-stage strategy. For a guessed name, it first attempts an exact match. If none is found, it uses fuzzy matching to find a pool of the most likely candidates. It then analyzes this pool: if a single candidate is found with a score above the configured `customer_linking_fuzzy_match_threshold` and is significantly better than the next-best match, it is linked automatically. In all other ambiguous cases (e.g., multiple close matches, or a single match below the confidence threshold), it uses the `lightweight` LLM as a fallback to make the final decision. This same logic is applied to both customer and contact linking.
5. Persistence: CUIS items are saved as individual JSON files by `cuis_handler.py`. The local Syncro cache is also persisted as JSON files.
6. LLM Utility Test (Standalone): A separate test script verifies basic `llm_utils.py` functionality (connectivity, sample summarization/embedding) using config.json settings.
7. Logging: Centralized logging via `sdc_logger.py`.
8. Feedback: Agent Zero provides summary feedback after orchestrated runs; detailed logs are available.
9. Error Handling: Log and skip problematic items/files after a retry if applicable.
2. User Interfaces, System Interactions, & Broader Functionality (Phase 2)
2.1. Interaction Model (V1.0):
* Hybrid Model: Primarily CLI-driven (individual Python scripts, run_sdc.py).
* Orchestration: Via an AI Assistant (Agent Zero) which acts as a higher-level command interface, or direct execution of run_sdc.py.
* Process Type: Functions as a background process when initiated.
* GUI: No Graphical User Interface (GUI) for V1.0.
* Scheduling: No automated scheduling features for V1.0.
2.2. Key Interface Elements (V1.0):
* Agent Zero Chat Commands (Conceptual):
* Examples: "SDC: Run full V1.0 pipeline", "SDC: Ingest SillyTavern chat files".
* Command Line Interface (CLI) Arguments:
* For run_sdc.py (Master Orchestrator): Sub-commands/flags for various SDC pipelines or individual modules (e.g., ingest --source sillytavern, process --step customer_linking).
* For Individual SDC Module Scripts: Arguments for config path, input/output specifiers, behavioral flags (e.g., --force-refresh), logging controls.
* API Endpoints (Consumed by SDC):
* Syncro RMM API:
* Customers: /api/v1/customers (list), potentially /api/v1/customers/{id} (detail, if list view insufficient).
* Contacts: Contact info often from customer data; /api/v1/contacts (list) if needed.
* Tickets: /api/v1/tickets (list, filtered), /api/v1/tickets/{id} (detail, comments).
* LLM APIs (e.g., Google Gemini - for V1.0 test script & customer disambiguation):
* Endpoints for text generation (e.g., gemini-1.5-pro-latest:generateContent).
* Endpoints for embedding generation (e.g., models/text-embedding-004:embedContent).
* (Awareness of potential model endpoint naming differences, e.g. models/ prefix).
* File-Based Interfaces:
* Input: config.json, source data files (SillyTavern .jsonl, ScreenConnect .csv, notes.json).
* Output: CUIS items (individual .json files), Syncro customer/contact cache .json files, SDC processing log files (text).
2.3. Key Post-V1.0 Additional Features (Summary):
* Advanced correlation/duplicate detection using embeddings.
* Automated task generation from CUIS items (with initial human-in-the-loop review).
* Direct write-back/updates to Syncro RMM (with initial human-in-the-loop review).
* Timeline views and advanced reporting.
* Ingestion from more sources (e.g., Email, Voicemail Transcripts).
* SQLite or other database for CUIS persistence.
* More sophisticated LLM analysis modules integrated into the main pipeline.
* Enhanced Billing Assistant (unbilled work ID; phased invoice sending reminders/actions).
3. Settings and Configuration (Phase 3)
3.1. Central Configuration File (config.json):
SDC V1.0 behavior is primarily controlled by a `config.json` file located at `/a0/syncro_data_consolidator/config/config.json`. This file is loaded by an intelligent loader (`config_loader.py`) that dynamically finds the project root, making the application portable and allowing for a hierarchical path structure.

3.2. Key Configuration Parameters, Defaults, and Impacts:
*   **`project_paths`**: Defines all file I/O locations. It uses a hierarchical, multi-pass placeholder system. The loader first dynamically determines `{{project_root}}` and then resolves other placeholders (e.g., `{{data_folder}}`, `{{input_folder}}`) to construct the final, absolute paths used by the application.
    *   `notes_json`: (string) Full path to the `notes.json` file.
    *   `screenconnect_logs`: (string) Path to the directory containing ScreenConnect CSV logs.
    *   `sillytavern_chat_input_folder`: (string) Path to the directory containing SillyTavern chat logs.
    *   `cuis_items_output_folder`: (string) Path to the directory where final CUIS JSON files will be saved.
    *   `reports_output_folder`: (string) Path to the directory for future reporting outputs.
    *   `cache_folder`: (string) Path to the directory for storing cache files (e.g., Syncro customer data).
    *   *Impact*: Determines all file I/O locations, making the application configurable and portable.

*   **`logging`**: A dedicated object to centralize all logging configuration.
    *   `log_file_path`: (string) The full path to the log file (e.g., using `{{logs_folder}}/sdc.log`).
    *   `log_level`: (string, e.g., "INFO", "DEBUG") The minimum level of messages to log.
    *   `log_to_terminal`: (boolean) If true, logs will also be printed to the console.
    *   *Impact*: Controls the verbosity, destination, and format of all application logs.

*   **`syncro_api`**:
    *   `base_url`: (string, e.g., "https://bespokeit.syncromsp.com/api/v1") The base URL for the Syncro API.
    *   `api_key`: (string, default: "") API key for Syncro. Prioritizes `SYNCRO_API_KEY` environment variable if set.
    *   `tickets_endpoint`: (string, default: "/tickets") The specific endpoint for fetching tickets.
    *   `test_file_path`: (string, optional) Path to a local JSON file to use as mock ticket data for testing.
    *   *Impact*: Essential for all Syncro API connectivity.

*   **`llm_config`**:
    *   `active_provider`: (string, e.g., "google_gemini") Selects the LLM backend to use.
    *   `google_gemini`: (object) Contains `api_key` (prioritizes `GOOGLE_API_KEY` env var) and a `models` object mapping roles like "complex" and "embedding" to specific model names.
  *   `local_llm`: (object) Contains `base_url`, optional `api_key`, and a `models` mapping for a local LLM server. The `models` object maps roles like "complex", "lightweight", and "embedding".
    *   `default_llm_params`: (object, e.g., `{"temperature": 0.7, "max_tokens": 2048}`) Affects LLM response characteristics.
    *   *Impact*: Governs all LLM interactions.

*   **`processing_defaults`**:
    *   `recursive_sillytavern_scan`: (boolean, default: true) Scan ST subdirectories.
    *   `syncro_cache_policy`: (string, enum: "on_each_run", "if_older_than_hours", "manual_only", default: "if_older_than_hours") Syncro cache refresh strategy.
    *   `syncro_cache_expiry_hours`: (integer, default: 24) Used with "if_older_than_hours".
    *   `internal_work_customer_id`: (integer, default: 0) ID for non-client work.
    *   `sillytavern_session_gap_minutes`: (integer, default: 60) Defines ST session breaks.
    *   `customer_linking_fuzzy_match_threshold`: (integer, default: 85, range 0-100) Minimum score for fuzzy customer name matching.
    *   `notes_json_filename`: (string, default: "notes.json") Specific filename for notes.json ingestor.
    *   *Impact*: Controls specific behaviors of processing modules.

4. Technical Considerations and Architecture (Phase 4)
4.1. Data Requirements (Inputs, Outputs, Internal State):
* Inputs:
* SillyTavern Chat Files (JSONL files)
* Syncro RMM Tickets (JSON via API)
* Custom notes.json Files (JSON file)
* ScreenConnect Logs (CSV file - first alphabetical)
* Syncro RMM Customers & Contacts (JSON via API, for caching)
* config.json file
* Outputs:
* CUIS Items (Individual JSON files, based on CUIS V1.0 Pydantic model)
* Syncro Customer/Contact Cache Files (JSON files)
* SDC Log Files (Text files)
* Agent Zero Summary Feedback (Conceptual text output)
* Internal State Data (V1.0):
* Processed File Tracking (for idempotency of file-based ingestors, e.g., JSON file in cache storing path, mod time, size, message count for ST chat files).
* In-memory Python objects during processing.
4.2. Event Handling and Integrations (V1.0):
* Event Handling: Primarily user-command-driven (A0 or CLI). Internal "events" are sequential completion of module tasks or error occurrences, managed by the orchestrator. No real-time file watchers or webhooks.
* Key Integrations:
* Syncro RMM API (Outbound REST for data reads).
* LLM Provider API (e.g., Google Gemini - Outbound REST for V1.0 test script & customer disambiguation).
* File System (Reading source files, config.json; writing CUIS, cache, logs).
* Agent Zero (Orchestration interface; SDC scripts as callable "instruments").
* Python Environment & Libraries.
4.3. External Dependencies (V1.0):
* APIs & Services: Syncro RMM API, Google Gemini API (or other LLM), Optional Local LLM Server.
* Python Libraries: requests (implicit), argparse, thefuzz, python-dateutil, pydantic, langchain (and provider-specific e.g., langchain-google-genai), standard library modules (json, csv, os, logging, etc.).
* External Tools/Environments: Agent Zero, Python 3.x.
* Hardware: Standard computer.
4.4. Constraints and Assumptions (V1.0):
* User Factors (Nick's ADHD/Bipolar 2): Design prioritizes manageable tasks, clear feedback, robust error handling, clear orchestration, manageable V1.0 scope.
* Development Skillset: Modular Python scripts with A0 assistance; simplicity and reusability favored.
* Agent Zero Role: Key development assistant and V1.0 orchestrator; its limitations (context, file handling, token use) considered.
* V1.0 Scope Limits: Focus on ingestion, CUIS creation, customer linking, minimal LLM test. Advanced features deferred.
* Data Storage/Volume (V1.0): JSON file-based storage for CUIS/cache assumed manageable.
* API Rate Limits: Design aims to be mindful (caching, minimal V1.0 LLM use).
* Environment: Python 3.x with installable libraries.
* Offline Use: Not fully offline; internet needed for API calls.
* Data Quality: Assumes reasonable source data consistency; robust error handling for common issues.
* Performance (V1.0): Batch processing, "reasonable" time. Real-time/interactive performance not primary.
* Security: API key/credential security in environment is user's responsibility.
* Single User Focus: Designed for Nick's specific workflow.
4.5. Preliminary Technical Outline (V1.0):
  **4.5.1. Key Modules/Components (Python modules within the `sdc` package):**
     *   **Core (`sdc.run_sdc`):**
         1.  `run_sdc.py` (Master CLI script and orchestrator)
     *   **Utilities (`sdc.utils`):**
         2.  `config_loader.py`
         3.  `cuis_handler.py` (Handles CUIS I/O, uses `sdc.models.cuis_v1`)
         4.  `llm_utils.py` (For V1.0 test script & customer disambiguation)
         5.  `sdc_logger.py`
         6.  `date_utils.py`
     *   **Models (`sdc.models`):**
         7.  `cuis_v1.py` (Pydantic model for CUIS V1.0)
     *   **Data Ingestors (`sdc.ingestors`):**
         8.  `syncro_customer_contact_cacher.py`
         9.  `st_chat_ingestor.py` (SillyTavern)
         10. `syncro_ticket_ingestor.py` (Syncro Tickets)
         11. `notes_json_ingestor.py` (Custom Notes)
         12. `screenconnect_log_ingestor.py` (ScreenConnect)
     *   **Data Processors (`sdc.processors`):**
         13. `cuis_customer_linker.py`
         14. `cuis_llm_analyzer.py` (Placeholder/conceptual for V1.0; LLM use is minimal)
         15. `cuis_embedding_generator.py` (Placeholder/conceptual for V1.0)

  **4.5.2. Component Interaction (V1.0):**
     *   Primarily sequential, orchestrated by `sdc.run_sdc.py` (or A0).
     *   Configuration data is loaded and processed by `sdc.utils.config_loader`, which dynamically finds the project root and resolves all path placeholders into absolute paths before the configuration object is used by any other module.
     *   Primary data (CUIS items, Syncro cache) managed via `sdc.utils.cuis_handler` and file system persistence.
     *   Utility modules imported and called directly by other modules within the `sdc` package as needed (e.g., `from sdc.utils import sdc_logger`).
     *   Control flow via sequential execution, return values/exceptions, and logging.
     *   No complex event buses or message queues.

  **4.5.3. Code Module Structure (Directory Layout):**
     ```
     /a0/syncro_data_consolidator/  <-- Project Root
     |-- src/
     |   |-- sdc/  <-- Main Python package
     |   |   |-- __init__.py
     |   |   |-- run_sdc.py
     |   |   |-- utils/
     |   |   |   |-- __init__.py
     |   |   |   |-- config_loader.py
     |   |   |   |-- cuis_handler.py
     |   |   |   |-- llm_utils.py
     |   |   |   |-- sdc_logger.py
     |   |   |   |-- date_utils.py
     |   |   |-- ingestors/
     |   |   |   |-- __init__.py
     |   |   |   |-- syncro_customer_contact_cacher.py
     |   |   |   |-- syncro_ticket_ingestor.py
     |   |   |   |-- st_chat_ingestor.py
     |   |   |   |-- notes_json_ingestor.py
     |   |   |   |-- screenconnect_log_ingestor.py
     |   |   |-- processors/
     |   |   |   |-- __init__.py
     |   |   |   |-- cuis_customer_linker.py
     |   |   |   |-- cuis_llm_analyzer.py  # Placeholder
     |   |   |   |-- cuis_embedding_generator.py  # Placeholder
     |   |   |-- models/
     |   |       |-- __init__.py
     |   |       |-- cuis_v1.py  # Pydantic model for CUIS
     |-- config/
     |   |-- config.json
     |-- data/  <-- Corresponds to PDD's 'ProjectData', {{data_folder}} in config.json
     |   |-- input/
     |   |   |-- sillytavern_chat/
     |   |   |-- notes_json/
     |   |   |-- screenconnect_logs/
     |   |-- output/
     |   |   |-- cuis_items/
     |   |   |-- reports/
     |   |-- cache/
     |   |-- logs/
     |   |-- temp/
     |-- tests/
     |   |-- __init__.py
     |   |-- test_llm_connectivity.py
     |   |-- unit/
     |   |-- integration/
     |-- docs/
     |   |-- CUIS_V1_Definition.md
     |   |-- SDC_V1_Project_Design_Document.md (this file)
     |-- .gitignore
     |-- requirements.txt
     |-- README.md
     ```
     *Note: All directories within the `sdc` package (e.g., `utils`, `ingestors`, `processors`) must contain an `__init__.py` file, which can be empty, to be treated as proper Python packages.*

5. Scope, MVP, and Testing (Phase 5)
5.1. SDC V1.0 MVP Definition:
* Core Goal: Reliably ingest data from SillyTavern, Syncro Tickets, notes.json, ScreenConnect logs; transform to CUIS V1.0; perform essential customer linking; store results as JSON files; all configurable and orchestrated.
* Key In-Scope Features: Configuration system, core utilities (CUIS handling, logging, date parsing), Syncro customer/contact caching, all four data ingestors, customer linking (with fuzzy match and targeted LLM disambiguation), standalone LLM utility test script, `run_sdc.py` orchestrator, Agent Zero compatibility.
* Explicitly Out-of-Scope for V1.0: Full-scale/main-pipeline LLM analysis/embedding, advanced correlation/duplicate detection, automated task generation, direct Syncro write-back, advanced reporting/timelines, ingestion from more sources (email, voicemail), database persistence for CUIS, GUI, automated scheduling.
5.2. SDC V1.0 Success Criteria:
1. Reliable data ingestion from all four V1.0 sources.
2. Accurate transformation to valid CUIS V1.0 JSON files with correct field mapping and date parsing.
3. Effective Syncro customer/contact caching and policy adherence.
4. Functional customer linking with correct ID population.
5. Operable configuration system (config.json, env var fallbacks).
6. Successful execution of the standalone LLM test script verifying basic LLM utility functions.
7. Successful orchestration of V1.0 pipelines by `run_sdc.py` and A0 compatibility.
8. Useful logging and graceful error handling for common issues.
5.3. SDC V1.0 Testing Strategies:
1. Unit Testing (Automated): For individual functions/logic (e.g., date parsing, fuzzy match scoring, Pydantic validation).
2. Module-Level / Integration Testing (Semi-Automated/Manual): End-to-end testing of individual ingestor/processor modules with sample inputs/mock APIs.
3. End-to-End Pipeline Testing (Manual): Testing complete workflows via `run_sdc.py` or A0 with sample/real data.
4. Manual Verification & User Acceptance Testing (UAT) (By Nick): Review of CUIS outputs, linked data, logs against real-world data and expectations for accuracy and utility.
5. LLM Test Script Execution: Specific execution of the standalone LLM test.
