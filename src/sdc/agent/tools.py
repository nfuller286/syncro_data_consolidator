# src/sdc/agent/tools.py
from typing import Type
from langchain.tools import Tool
from pydantic import BaseModel, Field

from sdc.api_clients.syncro_gateway import SyncroGateway
from sdc.api_clients.screenconnect_gateway import ScreenConnectGateway
from sdc.ingestors.syncro_ticket_ingestor import ingest_syncro_tickets
from sdc.ingestors.st_chat_ingestor import ingest_sillytavern_chats
from sdc.ingestors.notes_json_ingestor import ingest_notes
from sdc.ingestors.screenconnect_log_ingestor import ingest_screenconnect
from sdc.utils.config_loader import load_config
from sdc.utils.sdc_logger import get_sdc_logger

class IngestDataToolArgs(BaseModel):
    source: str = Field(description="The data source to ingest. Must be one of 'syncro', 'sillytavern', 'notes', 'screenconnect'.")
    dry_run: bool = Field(description="If True, will not perform the ingestion and instead return a confirmation message. Defaults to True.", default=True)

def get_tools():
    """Initializes and returns a list of tools for the agent."""
    
    config = load_config()
    if not config:
        raise ValueError("Failed to load configuration.")

    logger = get_sdc_logger(__name__, config)

    syncro_gateway = SyncroGateway(config, logger)
    
    sc_config = config.get('screenconnect_api', {})
    screenconnect_gateway = ScreenConnectGateway(
        base_url=sc_config.get('base_url'),
        extension_id=sc_config.get('extension_id'),
        api_key=sc_config.get('api_key')
    )

    tools = [
        Tool(
            name="fetch_syncro_tickets",
            func=lambda since_updated_at=None, created_after=None: syncro_gateway.fetch_tickets(since_updated_at=since_updated_at, created_after=created_after),
            description="Fetches tickets from Syncro. Can filter by 'since_updated_at' or 'created_after' using YYYY-MM-DDTHH:MM:SSZ format. Use this to get recent tickets or tickets created after a certain date."
        ),
        Tool(
            name="fetch_all_syncro_customers",
            func=lambda: syncro_gateway.fetch_all_customers(),
            description="Fetches all customer data from Syncro. Use this to get a list of all customers."
        ),
        Tool(
            name="fetch_screenconnect_connections",
            func=lambda filter_expression: screenconnect_gateway.fetch_connections(filter_expression),
            description=(
                "Fetches connection data from ScreenConnect based on a filter expression. "
                "The filter expression is a string that follows the ScreenConnect filter syntax. "
                "Example: `GuestMachineName LIKE 'PC-123'` or `Time > '2025-01-20'` "
                "Use this to find specific ScreenConnect sessions."
            )
        ),
        Tool(
            name="semantic_search_sessions",
            func=lambda query: _semantic_search(query, config, logger),
            description=(
                "Performs a semantic search over the content of all indexed sessions (tickets, chats, remote sessions). "
                "Use this to find sessions related to a specific topic, error, or user request. "
                "Input should be a descriptive query string. "
                "Example: 'sessions related to network connectivity issues' or 'user having problems with printers'."
            )
        ),
        Tool(
            name="ingest_data",
            func=_run_ingestion,
            description="Runs the ingestion process for a specified data source. This is a local operation that processes files.",
            args_schema=IngestDataToolArgs
        )
    ]
    
    return tools

def _run_ingestion(source: str, dry_run: bool = True):
    """Helper function to run a specified ingestion module."""
    config = load_config()
    logger = get_sdc_logger(__name__, config)

    ingest_map = {
        'syncro': ingest_syncro_tickets,
        'sillytavern': ingest_sillytavern_chats,
        'notes': ingest_notes,
        'screenconnect': ingest_screenconnect
    }

    ingest_function = ingest_map.get(source.lower())

    if not ingest_function:
        return f"Error: Invalid source '{source}'. Must be one of {list(ingest_map.keys())}."

    if dry_run:
        return f"Dry run: Would ingest data from '{source}'. To execute, run again with dry_run=False."

    try:
        ingest_function(config, logger)
        return f"Successfully ingested data from '{source}'."
    except Exception as e:
        logger.error(f"Ingestion from source '{source}' failed: {e}", exc_info=True)
        return f"Ingestion from source '{source}' failed with error: {e}"

def _semantic_search(query: str, config, logger):
    """Helper function to perform semantic search."""
    from sdc.utils.vector_store_manager import VectorStoreManager
    from sdc.llm.embedding_api import get_embedding_client

    embedding_client = get_embedding_client(config, logger)
    if not embedding_client:
        return "Failed to initialize embedding client."

    vsm = VectorStoreManager('sessions', embedding_client, config, logger)
    if not vsm.load_index():
        return "Failed to load the search index. The index may not have been created yet."

    results = vsm.search(query, k=5, threshold=0.5)
    
    if not results:
        return "No relevant sessions found."

    return _format_search_results(results)


def _format_search_results(results):
    """Formats search results into a readable string."""
    formatted = "Found relevant sessions:\n"
    for doc, score in results:
        formatted += f"- Session ID: {doc.metadata.get('session_id', 'N/A')}\n"
        formatted += f"  Relevance Score: {score:.4f}\n"
        formatted += f"  Content Snippet: {doc.page_content[:200]}...\n\n"
    return formatted
