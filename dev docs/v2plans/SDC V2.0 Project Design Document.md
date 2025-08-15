# Syncro Data Consolidator (SDC) V2.0 - Project Design Document

**Version:** 2.0 (Final)
**Date:** YYYY-MM-DD
**Project Owner:** Nick


---

### **1. Project Overview (Phase 1)**

**1.1. Project Title:**
Syncro Data Consolidator (SDC) V2.0

**1.2. Core Purpose (V2.0 Philosophy):**
SDC V2.0 will evolve from a simple data ingestor into a **Decision Support Tool for Invoicing**. Its primary purpose is to ingest raw activity logs from multiple sources, intelligently group them into logical blocks of work, and present a clear, consolidated timeline to Nick. This enables confident and efficient manual invoicing for complex projects by answering the question, "What work did I actually do, and when?"

**1.3. SDC V2.0 Objective Statement:**
SDC V2.0 will implement a two-tiered data model (`Session` and `Work Item`) and a two-stage merge pipeline.
*   **Stage 1** will process raw source data (e.g., ScreenConnect logs) into discrete `Session` objects, merging closely related raw events (`Segments`) based on a configurable time gap. `Sessions` will be persisted as JSON files with stable, deterministic IDs to allow for a "Smart Update" process that preserves manual edits (like notes or project links).
*   **Stage 2** will merge `Session` objects from all sources into `Work Item` objects, representing continuous blocks of labor.
*   The V2.0 MVP will be focused on a single, high-priority project, defined by a set of `active_project_tags` in `config.json`, streamlining the workflow for immediate use.

**1.4. SDC V2.0 Primary Workflow:**
1.  **Configuration Loading:** The system loads `config.json`, paying special attention to new parameters: `active_project_tags`, `segment_to_session_merge_gap_minutes`, and `work_item_merge_gap_minutes`.
2.  **Ingestion & Session Creation (Stage 1 Merge):**

    *   Ingestor modules process raw source files (e.g., ScreenConnect CSVs, SillyTavern JSONL).
    *   Raw events are grouped into `Segments`.
    *   `Segments` from the same source that are within the `segment_to_session_merge_gap_minutes` are merged into a single `Session` object.

3.  **Persistence with Smart Update:**

    *   A deterministic `session_id` is generated for the `Session` (using source filename, start/end times).
    *   The system checks if a `Session.json` file with this ID already exists.
    *   **If yes:** It loads the existing file, updates the automated fields from the new data, but **preserves** manually-edited fields (`user_notes`, `context.links`, `processing_status`).
    *   **If no:** It saves the new `Session` object as a new file.

4.  **Work Item Creation (Stage 2 Merge):**

    *   A separate process loads all `Session` files.
    *   It sorts all `Sessions` by start time.
    *   It merges any `Sessions` (regardless of source) that fall within the `work_item_merge_gap_minutes` into a single `Work Item` object.
    *   The `Work Item` inherits a combined list of all links from its component `Sessions` into a `calculated_links` field for easy review.
    *   `Work Items` are persisted as JSON files.

5.  **Reporting:**

    *   A `Report Generator` module can be run (e.g., `"SDC: Report on active project"`).
    *   It uses the `active_project_tags` from the config to find all relevant `Sessions`, identifies their parent `Work Items`, and generates a summary of all labor for that project.


---

### **2. User Interfaces & Interactions (Phase 2)**

**2.1. Interaction Model (V2.0):**
*   **Primary Interface:** CLI-driven scripts and a master orchestrator (`run_sdc.py`).
*   **Core Interaction Pattern:** **Declarative Grouping**. Nick interacts by editing the "source of truth" data in `Session.json` files (e.g., adding a project link or a note). The system then re-runs its grouping logic to automatically reflect these changes in the final `Work Items`. Manual creation of `Work Items` is not required.
*   **New Commands (Conceptual):**
    *   `"SDC: Run full V2.0 pipeline"`
    *   `"SDC: Report on active project"`


---

### **3. Settings and Configuration (Phase 3)**

**3.1. New `config.json` Parameters:**
*   **`active_project_tags`**: (array of strings) A list of keywords (e.g., `"Project: ClientX Firewall"`, `"Ticket: 12345"`) that define the single, high-priority project for the V2.0 MVP. The report generator will use this by default.
    *   *Default:* `[]`
*   **`segment_to_session_merge_gap_minutes`**: (integer) The maximum time gap in minutes between two raw events (`Segments`) from the *same source* for them to be considered part of the same `Session`.
    *   *Default:* `30`
*   **`work_item_merge_gap_minutes`**: (integer) The maximum time gap in minutes between two `Sessions` (from *any source*) for them to be considered part of the same `Work Item`.
    *   *Default:* `45`


---

### **4. Technical Considerations and Architecture (Phase 4)**

**4.1. V2.0 Data Models (Updated Examples):**

**`Session` Model Example:**
```json
{
  "meta": {
    "session_id": "sha256-a1b2c3d4...",
    "schema_version": "2.0",
    "source_system": "ScreenConnect",
    "source_identifiers": ["screenconnect_log_2025-05.csv"],
    "processing_status": "Reviewed",
    "ingestion_timestamp_utc": "2025-05-20T10:00:00Z",
    "last_updated_timestamp_utc": "2025-05-20T14:30:00Z"
  },
  "context": {
    "customer_id": 12345,
    "customer_name": "Client X Inc.",
    "contact_id": 67890,
    "contact_name": "Jane Doe",
    "links": ["Project: ClientX Firewall Upgrade", "Ticket: 12345"]
  },
  "insights": {
    "session_start_time_utc": "2025-05-19T11:00:00Z",
    "session_end_time_utc": "2025-05-19T11:55:00Z",
    "session_duration_minutes": 55,
    "llm_generated_title": null,
    "user_notes": "Checked firewall rules, confirmed port 443 is open for new web server. User tested and confirmed access."
  },
  "segments": [
    {
      "segment_id": "seg-uuid-1",
      "start_time_utc": "2025-05-19T11:00:00Z",
      "end_time_utc": "2025-05-19T11:25:00Z",
      "type": "RemoteConnection",
      "metadata": {"computer_name": "CLIENTX-WEB01"}
    },
    {
      "segment_id": "seg-uuid-2",
      "start_time_utc": "2025-05-19T11:40:00Z",
      "end_time_utc": "2025-05-19T11:55:00Z",
      "type": "RemoteConnection",
      "metadata": {"computer_name": "CLIENTX-DC01"}
    }
  ]
}
```

**`Work Item` Model Example:**
```json
{
  "work_item_id": "wi-uuid-abc-123",
  "schema_version": "2.0",
  "customer_id": 12345,
  "component_session_ids": [
    "sha256-a1b2c3d4...",
    "sha256-e5f6g7h8..."
  ],
  "calculated_insights": {
    "work_item_start_time_utc": "2025-05-19T11:00:00Z",
    "work_item_end_time_utc": "2025-05-19T12:30:00Z",
    "total_duration_minutes": 90,
    "llm_combined_summary": null
  },
  "calculated_links": [
    "Project: ClientX Firewall Upgrade",
    "Ticket: 12345"
  ]
}
```


---

### **5. Scope, MVP, and Testing (Phase 5)**

**5.1. SDC V2.0 MVP Definition:**

*   **IN SCOPE:**
    *   Implementation of the `Session` and `Work Item` data models.
    *   The full two-stage merge pipeline (`Segment`->`Session`, `Session`->`Work Item`).
    *   Deterministic `session_id` generation.
    *   "Smart Update" logic to preserve manual edits in `Session.json` files.
    *   Persistence of all data models as local JSON files.
    *   A simple `Report Generator` focused on the `active_project_tags` from the config file.
    *   All necessary configuration parameters in `config.json`.

*   **EXPLICITLY OUT OF SCOPE FOR V2.0:**
    *   Implementation of an SQLite database backend.
    *   A web-based user interface.
    *   Dynamic management or reporting on multiple projects simultaneously (beyond changing the config).
    *   Any new, advanced LLM analysis.

**5.2. SDC V2.0 Success Criteria:**
1.  Raw logs from multiple sources are correctly aggregated into `Session` files based on the `segment_to_session_merge_gap_minutes` setting.
2.  `Session` files from multiple sources are correctly aggregated into `Work Item` files based on the `work_item_merge_gap_minutes` setting.
3.  Manually adding a note or link to a `Session.json` file is preserved after the ingestor is run again.
4.  The "active project" report accurately finds all relevant `Work Items` and calculates a correct total duration.
