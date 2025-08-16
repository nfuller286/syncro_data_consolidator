# Syncro Data Consolidator

**A modular data pipeline that consolidates events from multiple support platforms, links them to customers, breaks up and combines billable work into sessions, then uses an LLM to process, summarize and categorize the work.**

## Overview

The Syncro Data Consolidator (SDC) is a Python-based tool designed to create a unified view of work performed across various systems like **Syncro RMM**, ScreenConnect, and other data sources. It ingests, **standardizes, and normalizes** raw data from diverse formats—including API calls, JSON, CSV, and JSONL files—into a structured canonical data model called a "Session" format. This uses a customizable way to interact within the backend of various LLM providers, offering increased security, privacy and **transparency** over popular chat agent frameworks. 

A key strength of this project is its intelligent, cost-effective approach to data processing. To link sessions to the correct customer, it employs a **local-first strategy**, using high-accuracy fuzzy matching before falling back on an LLM for only the most ambiguous cases. This dramatically reduces API costs and processing time.

The architecture is highly **modular and optimized for cost-efficiency**. This design provides granular control over operational costs, allowing powerful models to be used for complex tasks while leveraging lighter, faster models for simpler ones.

## Features

*   **Multi-Source Ingestion:** Processes data from a wide variety of sources and formats, including **Syncro RMM tickets (via API), ScreenConnect logs (CSV), legacy notes (JSON), and chat logs (JSONL).**
*   **Robust Chat Deduplication:** The SillyTavern ingestor uses a hashing mechanism to create a unique fingerprint for every message. This prevents the re-ingestion of duplicate messages across different chat files, snapshots, or branches, ensuring data integrity.
*   **Modular & Extensible Architecture:** Components are decoupled, making it easy to add new data sources or processing steps. The LLM API handler, for example, is self-contained, allowing for easy adaptation to any **chat completion** source, whether it's a comprehensive framework like **LangChain** or a direct, vendor-specific API.
*   **Intelligent Customer Linking:** Uses a sophisticated, local-first cascade logic:
    1.  **Exact Match:** First, it looks for a perfect name match.
    2.  **Fuzzy Match:** If no exact match exists, it applies a fuzzy matching algorithm to find the closest 3 names, selecting the top candidate only if its confidence score is clearly higher than the next best options.
    3.  **AI Fallback:** Only for truly ambiguous cases does it make a call to an LLM, minimizing cost and latency.
*   **Cost-Optimized AI Analysis:** Leverages a configurable LLM (e.g., Google Gemini, local models) and allows you to assign different models to different tasks based on complexity. Use a cheap, fast model for simple categorization and a more powerful model for nuanced summarization.
*   **Stateful Processing:** Remembers which files and data have already been processed to avoid redundant work on subsequent runs.
*   **Centralized Logging:** All operations are logged, providing transparency and a clear audit trail for every processing step.
*   **Command-Line Interface:** Provides clear commands to run the entire pipeline or specific parts, such as ingesting new data or running analysis.

## Architecture

The project follows a multi-stage ETL (Extract, Transform, Load) pipeline. Raw data is ingested, converted into a standard format, enriched with customer information, and finally processed by an AI model.

```mermaid
%%{init: {
  "theme": "default",
  "securityLevel": "loose",
  "flowchart": { "htmlLabels": true }
}}%%
graph TD

  %% =======================================================
  %% Row 1 — Sources, Ingestion, Normalization & Matching
  %% (kept in a single row using direction LR)
  %% =======================================================
  subgraph "Sources & Pipelines"
    direction LR

    %% 1. Network Source (Far Left)
    subgraph "Network Source"
      S1[Syncro API]
    end

    %% 2. File Sources (Inputs)
    subgraph "A: File Sources (Inputs)"
      direction LR
      S2[ScreenConnect CSVs]
      S3[SillyTavern JSONL]
      S4[Legacy Notes JSON]
    end

    %% 3. Pipelines (Ordered as requested)
    subgraph "B: Pipelines"
      direction LR
      CC1(Customer Cacher)
      I1(Ticket Ingestor)
      I2(ScreenConnect Log Ingestor)
      I3(ST Chat Ingestor)
      I4(Notes Json Ingestor)
    end

    %% 4. Supporting cache file
    F2["fa:fa-file-alt Customer Cache File"]

    %% 5. Session Normalization & Customer Matching
    subgraph "C:           Session Normalization"
      direction LR
      N1["fa:fa-folder Sessions Raw"]
      P1(session_customer_linker)
    end
  end

  %% =======================================================
  %% Row 2 — Linked Sessions + LLM Prompting loop (below)
  %% =======================================================
  subgraph "Linked Sessions & LLM Prompting"
    direction LR

    %% Final output & working store (enhanced in place)
    L0["fa:fa-folder Linked Sessions<br/>(Final Output & Enhanced In-Place)"]

    %% External LLM sits to the LEFT of the prompting section
    subgraph "External Service"
      direction LR
      LLM[LLM API]
    end

    %% Prompting & Analysis (Analyzer first)
    subgraph "D: LLM Prompting"
      direction LR
      P2(session_llm_analyzer)
      G1(generate_prompts_and_model)
    end
  end

  %% =========================
  %% Flows
  %% =========================

  %% 1. Customer Caching Flow (Syncro API -> Cacher -> Cache File)
  S1 --> CC1
  CC1 ==> F2

  %% 2. Main Ingestion Flow (Sources -> Ingestors)
  S1 --> I1
  S2 --> I2
  S3 --> I3
  S4 --> I4

  %% 3. Ingestors write to the "Sessions Raw" folder
  I1 ==> N1
  I2 ==> N1
  I3 ==> N1
  I4 ==> N1

  %% 4. The Linker reads from "Sessions Raw" and the "Customer Cache"
  N1 --> P1
  F2 -. Reads Customers .-> P1

  %% 5. The Linker produces the final "Linked Sessions" output for Row 1
  P1 ==> L0

  %% Analyzer-driven prompting & LLM loop (LLM is outside, to the left of D)
  L0 --> P2
  P2 --> G1
  G1 -. Sends Request .-> LLM
  LLM --> P2
  P2 ==> L0 
  ```


## Project Structure

```
syncro_data_consolidator/
├── requirements.txt
├── config/              # Configuration files
├── data/                # All dynamic data: inputs, outputs, logs, cache
└── src/
    └── sdc/
        ├── run_sdc.py   # Main entry point and CLI
        ├── api_clients/ # Connectors for external APIs (e.g., Syncro)
        ├── ingestors/   # Scripts to read and standardize source data
        ├── llm/         # LLM prompt templates and API client logic
        ├── models/      # Pydantic data models (session_v2.py)
        ├── processors/  # Scripts for enrichment (linking, AI analysis)
        └── utils/       # Shared helper functions
```

## Installation & Setup

This project uses Conda for environment management.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/nfuller286/syncro_data_consolidator.git
    cd syncro_data_consolidator
    ```

2.  **Create and activate the Conda environment:**
    ```bash
    conda create --name sdc python=3.10
    conda activate sdc
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure the application:**
    *   Copy `config/sampleconfig.json` to `config/config.json`.
    *   Edit `config/config.json` to add your Syncro RMM API credentials, LLM API keys, and adjust paths if necessary.
    *   Review `config/llm_configs.json`.
    * **Note:** To run with sample data, copy the "data" folder from "sample_data\data" into the project root directory.

## Usage

> **Important:** All commands should be run from the `src/` directory. This project is designed as a Python package, and running it from `src/` ensures that module imports like `from sdc.utils import ...` resolve correctly.

### Quick Start

The easiest way to run the entire pipeline is to use the `run` command. This will cache fresh Syncro RMM data, ingest all sources, and link customers.

```bash
# Navigate to the src directory first
cd src

# Run the full pipeline
python -m sdc.run_sdc run --pipeline full
```

After the `full` pipeline runs, you can perform AI analysis on the linked sessions:

```bash
# Generate titles for all linked sessions
python -m sdc.run_sdc process --step llm_title

# Generate summaries for all linked sessions
python -m sdc.run_sdc process --step llm_summary
```

### Command-Line Interface (CLI)

*   **Run a full pipeline:**
    *   `run --pipeline full`: Caches data, ingests all sources, links customers.
    *   `run --pipeline ingest_only`: Runs all ingestors without caching or linking.

*   **Run a specific ingestor:**
    *   `ingest --source <name>`: Sources: `syncro`, `screenconnect`, `notes`, `sillytavern`, `all`.
    *   Example: `python -m sdc.run_sdc ingest --source screenconnect`

*   **Run a specific processing step:**
    *   `process --step <name>`: Steps: `customer_linking`, `llm_title`, `llm_summary`, `all`.
    *   Example: `python -m sdc.run_sdc process --step customer_linking`

*   **Manage Caches:**
    *   `cache --source syncro`: Forces a refresh of the Syncro RMM customer data.

## Future Enhancements

*   **Work Item Grouping:** Implement a new processor to group related `Session` objects into a single "Work Item." This would consolidate billable events from different sources (e.g., a ticket, a remote session, and a follow-up note) into one structured entity, which can then be exported for invoicing or reporting.
*   **Data Redaction Module:** Add an optional processing step to automatically find and redact PII (Personally Identifiable Information) before data is sent to an external LLM, enhancing privacy.
*   **Test Suite:** Implement a full test suite with `pytest` to ensure reliability and simplify future development.
