### SDC Quick Start Guide


Follow these steps to run the SDC application.


**Step 1: Navigate to the Project Directory**


Change your current directory to the root of the SDC project.


```bash
cd /a0/syncro_data_consolidator
```


**Step 2: Install Dependencies**


Install all required libraries using the `requirements.txt` file.


```bash
pip install -r requirements.txt
```


**Step 3: Run the Application**


To ensure Python can find the application modules, you must first change into the `src` directory. From there, you can execute the program. The example below runs the complete end-to-end pipeline.


```bash
cd src && python -m sdc.run_sdc run --pipeline full
```


---


### Command Reference


Use the following commands from within the `src` directory.


| Command | Purpose | Arguments & Options | Example |
| :--- | :--- | :--- | :--- |
| **`cache`** | Fetches and caches data from external sources. | `--source [syncro]` | `python -m sdc.run_sdc cache --source syncro` |
| **`ingest`** | Runs a specific data ingestor or all of them. | `--source [notes | screenconnect | sillytavern | syncro | all]` | `python -m sdc.run_sdc ingest --source screenconnect` |
| **`process`**| Runs a processing step on generated CUIS files. | `--step [customer_linking | all]` | `python -m sdc.run_sdc process --step customer_linking` |
| **`run`** | Executes a full, predefined pipeline. | `--pipeline [full]` | `python -m sdc.run_sdc run --pipeline full`