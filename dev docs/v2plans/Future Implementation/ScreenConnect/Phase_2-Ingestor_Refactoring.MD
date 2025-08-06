Phase 2: Ingestor Refactoring
The ingestor module must be updated to handle the dual-mode logic. Rename the relevant file to be mode-agnostic: src/sdc/ingestors/screenconnect_ingestor.py.

This file will have one public function and three private helper functions:

ingest_screenconnect_data() (Public):

This function acts as a dispatcher.
It reads config.screenconnect_ingestor.active_mode.
If active_mode is "api", it calls _ingest_from_api(config).
If active_mode is "csv", it calls _ingest_from_csv(config).
If the mode is invalid, it logs an error and exits.
_ingest_from_api(config) (Private):

Contains all the logic for API ingestion.
It will iterate through response.json()['Items'] and use Python's zip() function to combine FieldNames with each item sub-array, creating a dictionary for each record.
For each created dictionary, it calls _map_record_to_cuis() to perform the transformation.
_ingest_from_csv(config) (Private):

Contains the logic for reading CSV files from the specified folder.
It should use Python's csv.DictReader which automatically turns each row into a dictionary.
For each row (dictionary), it calls _map_record_to_cuis() to perform the transformation.
_map_record_to_cuis(record: dict) (Private, SHARED):

This is the core of the new architecture. This single function will be called by both the API and CSV ingestion paths.
It takes one argument: a dictionary (record) representing a single ScreenConnect session.
It contains all the mapping logic defined in the Data Dictionary (e.g., mapping record['SessionName'] to summary_title_or_subject, handling SessionCustomProperty5, etc.).
It returns a fully populated CuisV1 object, ensuring consistent transformation logic regardless of the data source.