# Project: Syncro Data Consolidator (SDC)

This document provides a comprehensive overview of the Syncro Data Consolidator (SDC), a project I designed to serve as a powerful, automated data pipeline. It addresses the common challenge of having valuable data siloed across different platforms by ingesting, standardizing, and enriching information from multiple sources into a unified, queryable format.

## High-Level Overview

The Syncro Data Consolidator is a Python-based ETL (Extract, Transform, Load) pipeline. Its primary function is to pull data from various sources relevant to my operations, including:

*   **SyncroMSP API**: For ticketing and customer data.
*   **ScreenConnect Logs**: For remote session information (CSV).
*   **SillyTavern Chat Logs**: For conversational data (JSONL).
*   **Structured JSON Notes**: A custom legacy format for notes and to-dos.

The system processes this disparate data, transforming it into a standardized `Session` model. This model acts as a "source of truth," where each object represents a distinct activity, like a ticket, a remote session, or a chat conversation.

A key feature of this project is its integration with Large Language Models (LLMs) through a flexible `langchain`-based utility. This allows for advanced data enrichment, such as generating titles, summarizing content, and assisting in linking data to the correct customers. The entire pipeline is designed to be highly configurable and portable, managed through a central `config.json` file.

## Data Flow and Architecture

The project follows a logical ETL pattern, orchestrated by a main execution script. The flow can be visualized as follows:

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

**The process unfolds in these stages:**

1.  **Initiation & Configuration**: The pipeline is started by running `run_sdc.py`. The first step is loading the `config.json` file, which defines all paths, API keys, and processing rules.
2.  **Caching (Optional but Recommended)**: The `syncro_customer_contact_cacher` can be run to fetch all customer and contact data from the Syncro API. This data is cached locally to speed up the linking process and reduce API calls.
3.  **Ingestion (Extract & Transform)**: Each `ingestor` module is responsible for a specific data source. It reads the raw data, transforms it into the standardized `Session` Pydantic model, and saves it as a unique JSON file in the output directory. Each ingestor tracks its state to avoid reprocessing files that haven't changed.
4.  **Processing (Enrichment)**: Once raw sessions are created, the `processor` modules run:
    *   `session_customer_linker`: This processor iterates through unprocessed `Session` files. It uses the cached Syncro data to link each session to an official customer and contact. It employs a waterfall logic of exact matching, fuzzy string matching, and finally, LLM-based analysis to find the correct link.
    *   `session_llm_analyzer`: This processor further enriches the data by sending the content of a session to an LLM to generate a concise, descriptive title or other insights.
5.  **Final Output**: The result is a folder of clean, enriched, and standardized JSON files. Each file represents a single, context-aware event, ready for analysis, reporting, or further processing.

## Core Components

The project's codebase is intentionally modular to promote maintainability and scalability. It is broken down into four key areas: `models`, `ingestors`, `processors`, and `utils`.

### Data Models (`sdc/models`)

The heart of the application is the `Session` data model, defined in `session_v2.py` using Pydantic. This ensures that all data, regardless of origin, conforms to a single, predictable structure.

*   **`Session`**: The top-level object representing a complete, continuous activity from a single source. It is composed of the following sub-models:
    *   **`SessionMeta`**: Contains system-level metadata for tracking, such as a unique `session_id`, the `source_system`, processing status, and timestamps.
    *   **`SessionContext`**: Holds the business context, most importantly the `customer_id` and `contact_id` that link the session to an entity in Syncro.
    *   **`SessionInsights`**: Stores data derived from analysis, such as calculated duration, `llm_generated_title`, summaries, and a field for manual user notes.
    *   **`SessionSegment`**: A list of these represents the raw events that make up the session (e.g., each chat message, each ticket comment).

### Ingestors (`sdc/ingestors`)

These modules are responsible for the "Extract" and "Transform" parts of the ETL pipeline.

*   **`syncro_ticket_ingestor`**: Fetches tickets and their comments from the Syncro API.
*   **`screenconnect_log_ingestor`**: Parses CSV logs from ScreenConnect to reconstruct remote sessions.
*   **`st_chat_ingestor`**: Processes `.jsonl` chat logs from SillyTavern, segmenting conversations into logical sessions.
*   **`notes_json_ingestor`**: Handles the one-time ingestion of data from a legacy `notes.json` file.
*   **`syncro_customer_contact_cacher`**: Fetches and caches customer/contact data from Syncro to be used by other parts of the system.

### Processors (`sdc/processors`)

These modules handle the "Enrichment" phase, adding value to the standardized `Session` objects.

*   **`session_customer_linker`**: The crucial module that connects session data to the correct Syncro customer, using a multi-step matching strategy for accuracy.
*   **`session_llm_analyzer`**: Leverages an LLM to perform content analysis, such as generating a clean title for a ticket or session based on its content.

### Utilities (`sdc/utils`)

This directory contains helper modules that provide common functionality across the project.

*   **`config_loader.py`**: A robust utility that loads the `config.json` file, resolves path placeholders (e.g., `{{project_root}}`), and can override keys with environment variables for better security.
*   **`llm_utils.py`**: A factory for creating LLM clients. It reads the configuration to determine which provider to use (e.g., Google Gemini, a local LLM) and abstracts away the instantiation logic.
*   **`session_handler.py`**: Provides simple functions to save and load `Session` objects to and from JSON files.
*   **`sdc_logger.py`**: A standardized logger configuration utility.

## Configuration

The entire project is controlled by the `config.json` file. I designed it this way to avoid hardcoding paths, credentials, or parameters, making the project portable and easy to reconfigure. Key sections include:

*   **`project_paths`**: Defines all file and directory locations.
*   **`logging`**: Controls log level and output (file and/or terminal).
*   **`syncro_api`**: Contains the base URL and API key for the SyncroMSP API.
*   **`llm_config`**: Allows switching between different LLM providers (`google_gemini`, `local_llm`) and specifies models for different tasks (e.g., complex vs. simple).
*   **`processing_defaults`**: Sets thresholds and behaviors, like the fuzzy matching score for customer linking and cache expiry times.

## How to Run

The application is executed through a single entry point, which provides a command-line interface for running different parts of the pipeline.

```bash
# Navigate to the source directory
cd /a0/syncro_data_consolidator/src

# Example: Run all ingestion steps
python -m sdc.run_sdc ingest-all

# Example: Run the customer linking and LLM analysis processors
python -m sdc.run_sdc process-all

# Example: Run a specific ingestor
python -m sdc.run_sdc ingest-syncro
```

The `run_sdc.py` script uses `argparse` to interpret these commands and orchestrate the calls to the appropriate modules.

## Self-Analysis and Future Enhancements

In building this project, I've identified several strengths and areas for future improvement.

*   **Architectural Strength**: The modular design with a clear separation of concerns is a major advantage. The standardized `Session` model is the cornerstone of this architecture, allowing new data sources or processing steps to be added with minimal impact on the rest of the system.

*   **Security**: A critical consideration is the handling of API keys. My `config_loader` is already built to prioritize loading secrets from environment variables over the `config.json` file. The next step is to fully adopt this practice and remove all secrets from the configuration file to prevent them from ever being committed to version control.

*   **Performance**: The `notes_json_ingestor` currently loads the entire file into memory. For very large legacy files, this could become a bottleneck. A future enhancement would be to refactor this ingestor to use a streaming JSON parser (like `ijson`) to process the file incrementally, reducing memory consumption.

*   **Robustness**: To prevent potential race conditions if multiple instances were run simultaneously, a global file-based locking mechanism could be implemented. This would ensure that only one process can read from and write to the session files at any given time, guaranteeing data integrity.
