# -*- coding: utf-8 -*-
"""
A developer tool for experimenting with semantic analysis of session data.
"""

import os
import sys
import sqlite3
import json
import numpy as np

# --- Setup sys.path to find the 'sdc' module ---
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# --- Imports from your project ---
try:
    from sdc.utils.config_loader import load_config
    from sdc.utils.sdc_logger import get_sdc_logger
    from sdc.llm.embedding_api import get_embedding_client
except ImportError as e:
    print(f"Failed to import project modules. Ensure this script is run from the project root. Error: {e}")
    sys.exit(1)

TARGET_SIZE = 1000
MAX_SIZE = 4000

def cosine_similarity(v1, v2):
    """Computes the cosine similarity between two vectors."""
    if v1 is None or v2 is None:
        return 0
    dot_product = np.dot(v1, v2)
    norm_v1 = np.linalg.norm(v1)
    norm_v2 = np.linalg.norm(v2)
    if norm_v1 == 0 or norm_v2 == 0:
        return 0
    return dot_product / (norm_v1 * norm_v2)

class SessionVectorizer:
    """
    Handles fetching session data from SQLite and computing embedding centroids.
    """
    def __init__(self, config, logger):
        self.logger = logger
        db_path = config['project_paths']['database_file']
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.logger.info(f"Connected to database at {db_path}")
        self.embedding_client = get_embedding_client(config, self.logger)
        if not self.embedding_client:
            raise ValueError("Failed to initialize embedding client.")

    def _create_chunks_for_session(self, session_id):
        """Creates text chunks for a session using 'smart boundary' logic."""
        cursor = self.conn.execute(
            "SELECT segment_id, content, metadata FROM segments WHERE session_id = ? ORDER BY start_time ASC",
            (session_id,)
        )
        segments = cursor.fetchall()
        
        chunks = []
        current_buffer = ""
        current_segment_ids = []

        def finalize_chunk(buffer, segment_ids):
            if buffer.strip():
                chunks.append({
                    "text": buffer.strip(),
                    "segment_ids": list(segment_ids)
                })

        for segment in segments:
            segment_id, content, metadata_str = segment['segment_id'], segment['content'], segment['metadata']
            metadata = json.loads(metadata_str) if metadata_str else {}
            
            prefix = "\nUser: " if metadata.get("is_user") or metadata.get("author") == "local_author" else "\nAssistant: "
            segment_text = prefix + (content or "")

            # Overflow protection for single large segments
            while len(segment_text) > MAX_SIZE:
                split_pos = segment_text.rfind('\n', 0, MAX_SIZE)
                if split_pos == -1:  # No newline found, hard split
                    split_pos = MAX_SIZE
                
                finalize_chunk(segment_text[:split_pos], [segment_id])
                segment_text = segment_text[split_pos:]

            # Boundary check
            if len(current_buffer) + len(segment_text) > TARGET_SIZE and current_buffer:
                finalize_chunk(current_buffer, current_segment_ids)
                current_buffer = ""
                current_segment_ids = []

            current_buffer += segment_text
            current_segment_ids.append(segment_id)

        finalize_chunk(current_buffer, current_segment_ids)
        return chunks

    def get_session_vectors(self, session_id):
        """Computes the embedding centroid and chunk vectors for a session."""
        chunks_data = self._create_chunks_for_session(session_id)
        if not chunks_data:
            self.logger.warning(f"Session {session_id} has no text content. Skipping.")
            return None

        chunk_texts = [chunk['text'] for chunk in chunks_data]
        
        try:
            chunk_vectors = self.embedding_client.embed_documents(chunk_texts)
            if not chunk_vectors:
                return None
            
            for i, vector in enumerate(chunk_vectors):
                chunks_data[i]['vector'] = vector

            centroid_vector = np.mean(chunk_vectors, axis=0)
            
            return {
                "session_id": session_id,
                "centroid_vector": centroid_vector,
                "chunk_data": chunks_data
            }
        except Exception as e:
            self.logger.error(f"Failed to embed chunks for session {session_id}: {e}")
            return None

    def close(self):
        self.conn.close()

def run_interactive_search(session_vectors_data, vectorizer):
    """Performs interactive search and compares centroid vs. chunk scores."""
    print("\n--- Interactive Search ---")
    while True:
        query = input("Enter search query (or 'q' to quit): ")
        if query.lower() == 'q':
            break
        if not query:
            continue
            
        query_vector = np.array(vectorizer.embedding_client.embed_query(query))
        
        results = []
        for session_id, data in session_vectors_data.items():
            if data is None:
                continue

            centroid = data['centroid_vector']
            chunk_scores = [cosine_similarity(query_vector, chunk['vector']) for chunk in data['chunk_data']]
            score_chunk_max = max(chunk_scores) if chunk_scores else 0
            
            results.append({
                "session_id": session_id,
                "score_centroid": cosine_similarity(query_vector, centroid),
                "score_chunk_max": score_chunk_max,
                "data": data 
            })
            
        results.sort(key=lambda x: x['score_chunk_max'], reverse=True)
        
        print("\n" + "-"*80)
        print(f"{'#':<3} | {'ID':<38} | {'Centroid Score':<16} | {'MaxChunk Score':<16} | {'Delta'}")
        print("-" * 80)
        
        for i, res in enumerate(results):
            delta = res['score_chunk_max'] - res['score_centroid']
            print(f"{i+1:<3} | {res['session_id']:<38} | {res['score_centroid']:<16.4f} | {res['score_chunk_max']:<16.4f} | {delta:+.2f}")
        print("-" * 80 + "\n")

        while True:
            selection = input("Select row # to inspect (or enter to search again): ")
            if not selection:
                break
            try:
                index = int(selection) - 1
                if 0 <= index < len(results):
                    inspector_view(results[index]['data'], query_vector)
                    break 
                else:
                    print("Invalid row number.")
            except ValueError:
                print("Invalid input. Please enter a number or press Enter.")


def inspector_view(session_data, query_vector):
    """
    Displays a detailed 'heatmap' of chunk scores for a selected session and shows the most relevant passage.
    """
    print(f"\n--- Inspector for Session: {session_data['session_id']} ---")
    
    chunk_data = session_data['chunk_data']
    scores = [cosine_similarity(query_vector, chunk['vector']) for chunk in chunk_data]
    
    highest_score = -1
    highest_scoring_chunk_index = -1
    
    for i, score in enumerate(scores):
        bar_length = int(score * 20)
        bar = '█' * bar_length + ' ' * (20 - bar_length)
        print(f"Chunk {i+1:<2}: [{bar}] {score:.4f}")
        if score > highest_score:
            highest_score = score
            highest_scoring_chunk_index = i
            
    if highest_scoring_chunk_index != -1:
        print("\nMost Relevant Passage:")
        print("-" * 25)
        print(chunk_data[highest_scoring_chunk_index]['text'])
        print("\nContributing Segments:", chunk_data[highest_scoring_chunk_index]['segment_ids'])
        print("-" * 25)
    
    print("-" * 50 + "\n")


def main():
    """Main application logic."""
    config = load_config()
    logger = get_sdc_logger(__name__, config)
    
    try:
        vectorizer = SessionVectorizer(config, logger)
    except (ValueError, KeyError) as e:
        logger.critical(f"Initialization failed: {e}")
        return

    # --- Startup ---
    while True:
        try:
            num_sessions_str = input("How many recent sessions to load? [Default: 20]: ")
            if not num_sessions_str:
                num_sessions = 20
                break
            num_sessions = int(num_sessions_str)
            if num_sessions > 0:
                break
            else:
                print("Please enter a positive number.")
        except ValueError:
            print("Invalid input. Please enter a number.")

    # --- Loading Data ---
    logger.info(f"Fetching latest {num_sessions} sessions to compute vectors...")
    try:
        cursor = vectorizer.conn.execute(f"SELECT session_id FROM sessions ORDER BY start_time DESC LIMIT {num_sessions}")
        session_ids = [row[0] for row in cursor.fetchall()]
        
        session_vectors_data = {}
        for i, session_id in enumerate(session_ids):
            print(f"Processing session {i+1}/{len(session_ids)}: {session_id}") # Progress bar
            session_vectors_data[session_id] = vectorizer.get_session_vectors(session_id)
        
        logger.info("Vector computation complete.")

        # --- Main Loop ---
        run_interactive_search(session_vectors_data, vectorizer)

    except sqlite3.Error as e:
        logger.error(f"A database error occurred: {e}")
    finally:
        if 'vectorizer' in locals() and vectorizer:
            vectorizer.close()
            logger.info("Database connection closed. Exiting.")

if __name__ == "__main__":
    main()
