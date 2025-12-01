# -*- coding: utf-8 -*-
"""
Manager for handling FAISS vector stores, including creation, loading, and searching.
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple

# Assuming faiss-cpu and langchain are installed.
# FAISS is now in langchain_community
try:
    from langchain_community.vectorstores.faiss import FAISS
    from langchain_core.documents import Document
except ImportError:
    # Handle the case where the library might be in a different location or not installed.
    # This provides a fallback for different versions of langchain.
    try:
        from langchain.vectorstores.faiss import FAISS
        from langchain.docstore.document import Document
    except ImportError:
        # If neither works, it's likely not installed. The calling code's logger should handle this.
        FAISS = None
        Document = None

class VectorStoreManager:
    """Encapsulates FAISS index operations."""

    def __init__(self, index_name: str, embedding_client: Any, config: Dict[str, Any], logger):
        """
        Initializes the VectorStoreManager.

        Args:
            index_name (str): The name of the index, used as a sub-folder.
            embedding_client: The client for generating embeddings (e.g., HuggingFaceEmbeddings).
            config (Dict[str, Any]): The application configuration.
            logger: The logger instance.
        """
        self.index_name = index_name
        self.embedding_client = embedding_client
        self.config = config
        self.logger = logger

        base_storage_path = self.config.get('embedding_config', {}).get('base_storage_path', './cache/embeddings')
        self.storage_path = os.path.join(base_storage_path, self.index_name)
        
        self.db = None
        self.logger.info(f"VectorStoreManager initialized for index '{self.index_name}' at '{self.storage_path}'")

    def _sanitize_metadata(self, metadata_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Ensures all metadata values are simple types (str, int, float).
        Converts None to empty string "".
        
        Args:
            metadata_list (List[Dict[str, Any]]): A list of metadata dictionaries.

        Returns:
            List[Dict[str, Any]]: The sanitized list of metadata dictionaries.
        """
        sanitized_list = []
        for metadata in metadata_list:
            sanitized_metadata = {}
            for key, value in metadata.items():
                if isinstance(value, (str, int, float)):
                    sanitized_metadata[key] = value
                elif value is None:
                    sanitized_metadata[key] = ""
                else:
                    # Convert other types to string as a fallback.
                    self.logger.debug(f"Metadata value for key '{key}' of type {type(value)} converted to string.")
                    sanitized_metadata[key] = str(value)
            sanitized_list.append(sanitized_metadata)
        return sanitized_list

    def create_index(self, texts: List[str], metadatas: List[Dict[str, Any]]):
        """
        Creates a new FAISS index from texts and metadatas, then saves it.
        Also saves the raw texts to a JSON file for inspection.

        Args:
            texts (List[str]): The documents to index.
            metadatas (List[Dict[str, Any]]): The metadata associated with each document.
        """
        if not FAISS:
            self.logger.error("FAISS or Langchain is not installed. Cannot create index.")
            return

        self.logger.info(f"Creating new index for '{self.index_name}' with {len(texts)} documents.")
        
        # 1. Sanitize metadata
        sanitized_metadatas = self._sanitize_metadata(metadatas)
        
        try:
            # 2. Use FAISS.from_texts
            self.logger.info("Generating embeddings and creating FAISS index...")
            self.db = FAISS.from_texts(texts=texts, embedding=self.embedding_client, metadatas=sanitized_metadatas)
            
            # 3. Save to disk immediately
            Path(self.storage_path).mkdir(parents=True, exist_ok=True)
            self.db.save_local(self.storage_path)
            self.logger.info(f"Index successfully created and saved to '{self.storage_path}'")

            # 4. Save the texts to a JSON file for inspection
            json_path = os.path.join(self.storage_path, "embedded_texts.json")
            try:
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(texts, f, indent=4, ensure_ascii=False)
                self.logger.info(f"Saved the {len(texts)} embedded texts for inspection to '{json_path}'")
            except Exception as e:
                self.logger.error(f"Failed to save embedded texts to JSON: {e}")

        except Exception as e:
            self.logger.error(f"Failed to create and save index: {e}", exc_info=True)
            self.db = None

    def load_index(self):
        """
        Loads an existing FAISS index from disk.
        """
        if not FAISS:
            self.logger.error("FAISS or Langchain is not installed. Cannot load index.")
            return False

        if not os.path.exists(self.storage_path):
            self.logger.warning(f"Index path not found: '{self.storage_path}'. Cannot load index.")
            return False
            
        self.logger.info(f"Loading index '{self.index_name}' from '{self.storage_path}'...")
        try:
            self.db = FAISS.load_local(
                self.storage_path, 
                self.embedding_client, 
                allow_dangerous_deserialization=True
            )
            self.logger.info("Index loaded successfully.")
            return True
        except Exception as e:
            self.logger.error(f"Failed to load index: {e}", exc_info=True)
            self.db = None
            return False

    def search(self, query: str, k: int = 5, threshold: float = 0.0) -> List[Tuple[Document, float]]:
        """
        Performs a similarity search with relevance scores and filters by a threshold.

        Args:
            query (str): The query text.
            k (int): The number of results to return.
            threshold (float): The minimum relevance score (0.0 to 1.0) to include.

        Returns:
            List[Tuple[Document, float]]: A list of (Document, relevance_score) tuples.
        """
        if not self.db:
            self.logger.error("Index not loaded. Cannot perform search.")
            return []

        self.logger.info(f"Performing search for query: '{query[:50]}...' with k={k}, threshold={threshold}")
        try:
            # Use similarity_search_with_relevance_scores to get normalized scores.
            results_with_scores = self.db.similarity_search_with_relevance_scores(query, k=k)
            
            # Filter results based on the threshold. A higher score is better.
            filtered_results = [
                (doc, score) for doc, score in results_with_scores if score >= threshold
            ]
            
            self.logger.info(f"Found {len(results_with_scores)} initial results, {len(filtered_results)} after filtering.")
            return filtered_results

        except Exception as e:
            self.logger.error(f"Search failed: {e}", exc_info=True)
            return []

