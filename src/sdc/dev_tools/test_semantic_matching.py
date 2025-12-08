# -*- coding: utf-8 -*-
"""
Developer playground for testing semantic vs. fuzzy customer matching.
"""

import sys
import os
import logging
from thefuzz import process

# --- Setup sys.path to find the 'sdc' module ---
# This allows running the script from the project root directory.
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# --- Imports from your project ---
try:
    from sdc.utils.config_loader import load_config
    from sdc.utils.cache_utils import load_lean_customer_cache
    from sdc.llm.embedding_api import get_embedding_client
    from sdc.utils.vector_store_manager import VectorStoreManager
except ImportError as e:
    print(f"Failed to import project modules. Ensure you are running this from the project root directory.")
    print(f"Error: {e}")
    sys.exit(1)

# --- Basic Logger Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """
    Main execution function for the playground.
    """
    logger.info("---" + "Starting Semantic Matching Playground" + "---")

    # 1. Load Config, Logger, and Embedding Client
    config = load_config()
    if not config:
        logger.error("Configuration failed to load. Exiting.")
        return

    embedding_client = get_embedding_client(config, logger)
    if not embedding_client:
        logger.error("Failed to create embedding client. Exiting.")
        return

    # 2. Load lean_customer_cache
    logger.info("Loading lean customer cache...")
    customer_data = load_lean_customer_cache(config, logger)
    if not customer_data:
        logger.error("Failed to load customer cache. Make sure it has been generated first.")
        return

    # 3. Initialize VectorStoreManager
    manager = VectorStoreManager(
        index_name="test_customers_with_contacts",
        embedding_client=embedding_client,
        config=config,
        logger=logger
    )

    # 4. Extract texts and metadatas
    # We assume the customer dict contains a 'business_name' key.
    texts = []
    for customer in customer_data:
        # 1. Get Business Name
        biz_name = customer.get('business_name', 'Unknown')

        # 2. Get List of Contact Names
        contacts = customer.get('contacts', [])
        contact_names = [contact['name'] for contact in contacts if contact.get('name')]

        # 3. Join them into a single descriptive string
        # Format: "Company: {Name}. People: {Name, Name, Name}."
        contact_str = ", ".join(contact_names)
        rich_text = f"Company: {biz_name}. People: {contact_str}."

        texts.append(rich_text)
    
    metadatas = customer_data
    
    # Also create a simple mapping for TheFuzz
    fuzzy_choices = {customer.get('business_name', ''): customer.get('id') for customer in customer_data}

    # 5. First Run Check: Load or Create Index
    if not manager.load_index():
        logger.info("No existing index found. Generating new embeddings (this may take a moment)...")
        manager.create_index(texts, metadatas)
        if not manager.db:
            logger.error("Failed to create the index. Exiting.")
            return

    logger.info("---" + "Index is ready. Starting interactive search." + "---")
    logger.info("Enter a customer name to search, or type 'exit' or 'quit' to end.")

    # 6. Interactive Loop
    try:
        while True:
            query = input("\nSearch for customer: ")
            if query.lower() in ['exit', 'quit']:
                break
            if not query:
                continue

            # Run Semantic Search
            semantic_results = manager.search(query, k=5, threshold=0.5) # Using a threshold to filter poor matches

            # Run Fuzzy Search for comparison
            fuzzy_results = process.extract(query, fuzzy_choices.keys(), limit=5)

            # Print results table
            print("-" * 140)
            print(f"{ 'Semantic Score':<20} | { 'Fuzzy Score':<15} | { 'Matched Text':<100}")
            print("-" * 140)

            # Create a combined list for easier display
            # This is a simplification; a real implementation might merge results more intelligently
            
            # Display semantic results
            if semantic_results:
                for doc, score in semantic_results:
                    name = doc.page_content
                    # Find the corresponding fuzzy score for the business name from metadata
                    business_name = doc.metadata.get('business_name', '')
                    fuzzy_score = next((fr[1] for fr in fuzzy_results if fr[0] == business_name), 'N/A')
                    score_str = f"{score:.4f}"
                    print(f"{score_str:<20} | {str(fuzzy_score):<15} | {name[:100]:<100}")
            else:
                print("No semantic results found above the threshold.")

            print("-" * 80)

    except KeyboardInterrupt:
        print("\nExiting playground.")
    finally:
        logger.info("---" + "Playground finished." + "---")


if __name__ == "__main__":
    main()
