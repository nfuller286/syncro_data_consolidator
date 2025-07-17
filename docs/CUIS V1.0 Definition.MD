# Core Unified Information Structure (CUIS) - V1.0 Definition

This document outlines the structure and key fields for the Core Unified Information Structure (CUIS) Version 1.0, designed for the Syncro Data Consolidator (SDC) project.

## Root Object Structure

A CUIS V1.0 item is a JSON object with the following top-level keys:

```json
{
  "sdc_core": {},
  "core_content": {},
  "entities_involved": {},
  "categorization": {},
  "links": [],
  "cuis_entries": [],
  "source_specific_details": {},
  "custom_fields": {}
}
```

---

### 1. `sdc_core` (Object)
*Purpose: Metadata used by SDC for internal tracking and management of the CUIS item.*

| Field Name                      | Data Type | Description                                                                 | Example / Notes                                     |
|---------------------------------|-----------|-----------------------------------------------------------------------------|-----------------------------------------------------|
| `sdc_cuis_id`                   | String (UUID) | Unique SDC-generated UUID for this CUIS item.                             | e.g., "f47ac10b-58cc-4372-a567-0e02b2c3d479"         |
| `sdc_version`                   | String    | Version of the SDC system that generated/updated this item.                 | e.g., "1.0.0"                                       |
| `sdc_cuis_schema_version`       | String    | Version of the CUIS schema this item conforms to.                           | "1.0"                                               |
| `sdc_source_system`             | String    | The original system from which the data was ingested.                       | "SillyTavern", "SyncroRMM", "NotesJSON", "ScreenConnect" |
| `sdc_source_sub_type`           | String    | More specific type within the source system.                                | "SillyTavern_Session", "Syncro_Ticket", "NotesJSON_Ticket", "NotesJSON_ToDo", "ScreenConnect_Event" |
| `sdc_source_primary_id`         | String    | Primary unique identifier from the source system, if available.             | e.g., Syncro Ticket ID, ST chat_id_hash + session index |
| `sdc_source_file_path`          | String    | Path to the original source file, if applicable.                            | e.g., "/path/to/sillytavern_input/chat_session_abc.jsonl"              |
| `sdc_ingestion_timestamp_utc`   | String (ISO 8601) | ISO 8601 UTC timestamp when SDC first ingested this data.                   | "2023-10-27T10:00:00Z"                              |
| `sdc_last_updated_timestamp_utc`| String (ISO 8601) | ISO 8601 UTC timestamp when SDC last updated this CUIS item.                | "2023-10-27T10:05:00Z"                              |
| `sdc_processing_status`         | String    | Current processing status within SDC.                                       | "new", "linked", "analyzed", "error"                |
| `sdc_content_embedding_model_name`| String  | Name of the LLM model used to generate `sdc_content_embedding` (if any).    | e.g., "models/text-embedding-004" (Post V1.0 focus) |
| `sdc_content_embedding`         | Array     | Vector embedding of the core content (if generated).                        | [0.1, 0.2, ...] (Post V1.0 focus)                   |
| `sdc_data_source_agent_override`| String    | Identifier for the agent/user SDC attributes this record to, if overriding source. | e.g., "Nick_SDC_System"                          |


---

### 2. `core_content` (Object)
*Purpose: Normalized essential content derived from the source, intended for quick review and general processing.*

| Field Name                      | Data Type | Description                                                                 | Example / Notes                                     |
|---------------------------------|-----------|-----------------------------------------------------------------------------|-----------------------------------------------------|
| `summary_title_or_subject`      | String    | A concise title or subject line for the CUIS item. Derived or generated.    | e.g., "ST Session: Discussing API issue for ClientX" |
| `primary_text_content`          | String    | The main body of text associated with this item (e.g., combined notes, core message). |                                                     |
| `creation_timestamp_utc`        | String (ISO 8601) | ISO 8601 UTC timestamp representing the original creation time of the source event. | "2023-10-27T09:55:00Z"                              |
| `start_timestamp_utc`           | String (ISO 8601) | ISO 8601 UTC timestamp for the start of the activity/event, if applicable.  | "2023-10-27T09:55:00Z"                              |
| `end_timestamp_utc`             | String (ISO 8601) | ISO 8601 UTC timestamp for the end of the activity/event, if applicable.    | "2023-10-27T10:00:00Z"                              |
| `source_data_updated_at_timestamp_utc` | String (ISO 8601) | ISO 8601 UTC timestamp from the source system indicating its last update. | e.g., Syncro Ticket `updated_at`                      |
| `duration_seconds`              | Integer   | Duration of the event in seconds, if applicable.                            | e.g., ScreenConnect session duration                |


---

### 3. `entities_involved` (Object)
*Purpose: Information about customers, contacts, assignees, and other actors related to this CUIS item.*

| Field Name                               | Data Type | Description                                                                 | Example / Notes                                     |
|------------------------------------------|-----------|-----------------------------------------------------------------------------|-----------------------------------------------------|
| `syncro_customer_id_guessed`             | String    | Customer ID guessed by SDC before authoritative linking (e.g., from text).  |                                                     |
| `syncro_customer_name_guessed`           | String    | Customer name guessed by SDC before authoritative linking.                  |                                                     |
| `syncro_customer_id_authoritative`       | Integer   | Authoritative Syncro Customer ID after linking.                             | e.g., 12345                                         |
| `syncro_customer_name_authoritative`     | String    | Authoritative Syncro Customer Name after linking.                           | e.g., "Client X Inc."                               |
| `syncro_contact_id_guessed`              | String    | Contact ID guessed by SDC.                                                  |                                                     |
| `syncro_contact_name_guessed`            | String    | Contact name guessed by SDC.                                                |                                                     |
| `syncro_contact_id_authoritative`        | Integer   | Authoritative Syncro Contact ID after linking.                              | e.g., 67890                                         |
| `syncro_contact_name_authoritative`      | String    | Authoritative Syncro Contact Name after linking.                            | e.g., "Jane Doe"                                    |
| `primary_actor_user_id_source`           | Integer   | User ID of the primary actor from the source system (e.g., Syncro tech ID). | e.g., 176303                                        |
| `primary_actor_user_name_source`         | String    | User name of the primary actor from the source system.                      |                                                     |
| `primary_actor_user_id_authoritative`    | String    | Standardized/Authoritative User ID (e.g., Nick's Syncro ID).                |                                                     |
| `primary_actor_user_name_authoritative`  | String    | Standardized/Authoritative User Name.                                       |                                                     |
| `other_involved_entities`                | Array     | Array of objects for other entities (e.g., `{ "type": "device", "name": "SERVER01" }`). | (Flexible for future use)                       |


---

### 4. `categorization` (Object)
*Purpose: Fields related to classifying the CUIS item.*

| Field Name                      | Data Type | Description                                                                 | Example / Notes                                     |
|---------------------------------|-----------|-----------------------------------------------------------------------------|-----------------------------------------------------|
| `work_type_guessed`             | String    | Type of work guessed by SDC (e.g., "Support", "Consulting", "Internal").    |                                                     |
| `work_type_authoritative`       | String    | Confirmed type of work.                                                     |                                                     |
| `billable_status_guessed`       | String    | Guessed billable status ("Billable", "NonBillable", "Unknown").             |                                                     |
| `billable_status_authoritative` | String    | Confirmed billable status.                                                  |                                                     |
| `original_status_from_source`   | String    | Status as it appeared in the source system (e.g., Syncro ticket status).    | e.g., "Open", "Resolved"                            |
| `original_priority_from_source` | String    | Priority as it appeared in the source system.                               | e.g., "High", "Medium"                              |
| `tags_keywords_generated`       | Array     | Array of strings (tags/keywords generated by LLM or rules).                 | ["api", "syncro", "billing"] (Post V1.0 focus for LLM generation) |
| `tags_keywords_manual`          | Array     | Array of strings (tags/keywords manually added).                            |                                                     |


---

### 5. `links` (Array of Objects)
*Purpose: Represents relationships to other CUIS items or external entities.*

| Field Name                      | Data Type | Description                                                                 | Example / Notes                                     |
|---------------------------------|-----------|-----------------------------------------------------------------------------|-----------------------------------------------------|
| `target_cuis_id`                | String    | `sdc_cuis_id` of the linked CUIS item (if linking to another CUIS item).    |                                                     |
| `target_external_system`        | String    | Name of the external system if linking to an external entity.               | e.g., "SyncroRMM"                                   |
| `target_external_id`            | String    | ID of the entity in the external system.                                    | e.g., Syncro Ticket ID                              |
| `link_type`                     | String    | Type of relationship.                                                       | "related_to", "duplicate_of", "derived_from", "contains_info_for", "parent_ticket", "child_ticket" |
| `link_description`              | String    | Optional description of the link.                                           |                                                     |
| `link_timestamp_utc`            | String (ISO 8601) | ISO 8601 UTC timestamp when the link was established by SDC.                | "2023-10-27T10:10:00Z"                              |


---

### 6. `cuis_entries` (Array of Objects)
*Purpose: For sub-items like Syncro ticket comments, `notes.json` sub-notes/todos, or individual messages within a SillyTavern session if not placed in `source_specific_details`.*
*Each object in the array represents a single entry.*

| Field Name                      | Data Type | Description                                                                 | Example / Notes                                     |
|---------------------------------|-----------|-----------------------------------------------------------------------------|-----------------------------------------------------|
| `entry_id_source`               | String    | Unique ID of this sub-entry from the source system (e.g., Syncro comment ID). |                                                     |
| `entry_timestamp_utc`           | String (ISO 8601) | ISO 8601 UTC timestamp for this specific entry.                             | "2023-10-27T09:58:00Z"                              |
| `entry_author_name_source`      | String    | Author name from the source for this entry.                                 |                                                     |
| `entry_author_id_source`        | String    | Author ID from the source for this entry.                                   |                                                     |
| `entry_body_text`               | String    | The main text content of this sub-entry.                                    |                                                     |
| `entry_type_source`             | String    | Original type from source (e.g., "Comment", "Note", "ToDo").                |                                                     |
| `entry_type_deduced`            | String    | Type deduced by SDC (e.g., Syncro comment "Email", "Private Note").         |                                                     |
| `entry_metadata_source`         | Object    | Key-value pairs of additional metadata from the source for this entry.      | e.g., Syncro comment `subject`, `hidden`, `tech`    |
| `entry_order`                   | Integer   | Original order if specified in source (e.g., `notes.json` `order` field).   |                                                     |


---

### 7. `source_specific_details` (Object)
*Purpose: A flexible object to store rich, raw, or uniquely structured data from the original source system that doesn't fit neatly into other CUIS fields but is valuable to retain. The structure of this object will vary depending on `sdc_core.sdc_source_system`.*

*   **For `sdc_source_system: "SillyTavern"`:**
    *   `sillytavern_main_chat_source_file`: (String) from `chat_metadata.main_chat`.
    *   `sillytavern_character_name`: (String) from metadata.
    *   `sillytavern_user_name`: (String) from metadata.
    *   `sillytavern_session_messages`: (Array of Objects) Each object represents a message from the session:
        *   `message_text`: (String) `mes` field.
        *   `sender_name`: (String) `name` field.
        *   `is_user_message`: (Boolean) `is_user` field.
        *   `is_system_message`: (Boolean) `is_system` field.
        *   `message_timestamp_utc`: (String) Parsed `send_date`.
        *   `extracted_code_blocks`: (Array of Strings, optional) Code blocks from message.
*   **For `sdc_source_system: "SyncroRMM"` (Ticket):**
    *   `syncro_problem_type`: (String)
    *   `syncro_ticket_type`: (String)
    *   `syncro_raw_status`: (String)
    *   `syncro_raw_priority`: (String)
    *   `syncro_assigned_user_details`: (Object) e.g., `{ "id": "...", "full_name": "...", "email": "..." }`
    *   *(Other specific Syncro fields deemed useful but not in main CUIS sections)*
*   **For `sdc_source_system: "NotesJSON"`:**
    *   `notesjson_original_ticket_number`: (String) `ticketNumber` field.
    *   `notesjson_original_status`: (String) `status` field.
    *   `notesjson_original_priority`: (String) `priority` field.
*   **For `sdc_source_system: "ScreenConnect"`:**
    *   `screenconnect_session_name`: (String) `SessionName` (computer name).
    *   `screenconnect_client_type`: (String) `ClientType`.
    *   `screenconnect_raw_custom_property_1`: (String) `SessionCustomProperty1`.
    *   *(Other specific ScreenConnect fields)*


---

### 8. `custom_fields` (Object)
*Purpose: For ad-hoc user extensions or fields added during specific SDC processing runs that don't fit the standard CUIS schema. Key-value pairs.*

| Key                             | Data Type | Description                                                                 |
|---------------------------------|-----------|-----------------------------------------------------------------------------|
| (User-defined string)           | Any       | Value associated with the custom key.                                       |