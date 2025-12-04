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

CHUNK_TARGET_SIZE = 1000  # Soft limit: Try to break here at a segment boundary
CHUNK_MAX_SIZE = 4000     # Hard limit: Must break here (splitting the segment)

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
        self.logger.info(f"Connected to database at {db_path}")
        self.embedding_client = get_embedding_client(config, self.logger)
        if not self.embedding_client:
            raise ValueError("Failed to initialize embedding client.")

    def _process_segments_into_chunks(self, rows):
        """
        Processes database rows into text chunks with associated segment IDs.
        - Accumulates segments into a buffer.
        - Flushes buffer when it exceeds CHUNK_TARGET_SIZE.
        - Splits individual segments that exceed CHUNK_MAX_SIZE.
        """
        final_chunks = []
        current_buffer_text = ""
        current_buffer_ids = []

        def flush_buffer():
            nonlocal current_buffer_text, current_buffer_ids
            if current_buffer_text:
                final_chunks.append({'text': current_buffer_text.strip(), 'ids': list(current_buffer_ids)})
                current_buffer_text = ""
                current_buffer_ids = []

        for content, metadata_str, segment_id in rows:
            metadata = json.loads(metadata_str) if metadata_str else {}
            # Determine prefix
            is_local = metadata.get("is_user") is True or metadata.get("author") == "local_author"
            prefix = "\nUser: " if is_local else "\nAssistant: "

            seg_text = prefix + (content or "")

            # --- MONSTER SEGMENT HANDLING ---
            if len(seg_text) > CHUNK_MAX_SIZE:
                flush_buffer() # Clear any pending small segments first

                remaining_text = seg_text
                while len(remaining_text) > 0:
                    # If what's left fits, take it all
                    if len(remaining_text) <= CHUNK_MAX_SIZE:
                        final_chunks.append({'text': remaining_text.strip(), 'ids': [segment_id]})
                        break

                    # Attempt to find a semantic split point
                    slice_candidate = remaining_text[:CHUNK_MAX_SIZE]
                    last_newline = slice_candidate.rfind('\n')
                    last_space = slice_candidate.rfind(' ')

                    split_pos = last_newline if last_newline != -1 else last_space

                    # CRITICAL FIX: Ensure forward progress.
                    # If split_pos is -1 (not found) OR 0 (start of string), force hard cut.
                    if split_pos <= 0:
                        split_pos = CHUNK_MAX_SIZE

                    chunk_text = remaining_text[:split_pos]
                    final_chunks.append({'text': chunk_text.strip(), 'ids': [segment_id]})

                    # Advance the text
                    remaining_text = remaining_text[split_pos:]
                continue

            # --- STANDARD ACCUMULATION ---
            if len(current_buffer_text) + len(seg_text) > CHUNK_TARGET_SIZE:
                flush_buffer()

            current_buffer_text += seg_text
            current_buffer_ids.append(segment_id)

        flush_buffer() # Final flush
        return final_chunks

    def get_session_vectors(self, session_id):
        """Computes the embedding centroid and chunk vectors for a session."""
        cursor = self.conn.execute(
            "SELECT content, metadata, segment_id FROM segments WHERE session_id = ? ORDER BY start_time ASC",
            (session_id,)
        )
        rows = cursor.fetchall()
        if not rows:
            self.logger.warning(f"Session {session_id} has no segments. Skipping.")
            return None

        chunks_data = self._process_segments_into_chunks(rows)
        chunk_texts = [c['text'] for c in chunks_data]
        if not chunk_texts:
            self.logger.warning(f"No text chunks were generated for session {session_id}.")
            return None

        try:
            chunk_vectors = self.embedding_client.embed_documents(chunk_texts)
            if not chunk_vectors:
                return None
            
            centroid_vector = np.mean(chunk_vectors, axis=0)
            return {
                "session_id": session_id,
                "centroid_vector": centroid_vector,
                "chunk_vectors": chunk_vectors,
                "chunk_texts": chunk_texts,
                "chunk_metadata": [c['ids'] for c in chunks_data]
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
            chunks = data['chunk_vectors']
            
            score_centroid = cosine_similarity(query_vector, centroid)
            
            chunk_scores = [cosine_similarity(query_vector, chunk) for chunk in chunks]
            score_chunk_max = max(chunk_scores) if chunk_scores else 0
            
            results.append({
                "session_id": session_id,
                "score_centroid": score_centroid,
                "score_chunk_max": score_chunk_max,
                "data": data 
            })
            
        results.sort(key=lambda x: x['score_chunk_max'], reverse=True)
        
        # 2. Inner Loop: Validation & Navigation
        while True:
            # Just print the table headers and rows here
            print("\n" + "-"*80)
            print(f"{'#':<3} | {'ID':<38} | {'Centroid Score':<16} | {'MaxChunk Score':<16} | {'Delta'}")
            print("-" * 80)
            
            for i, res in enumerate(results):
                delta = res['score_chunk_max'] - res['score_centroid']
                delta_str = f"{delta:+.2f}"
                
                print(f"{i+1:<3} | {res['session_id']:<38} | {res['score_centroid']:<16.4f} | {res['score_chunk_max']:<16.4f} | {delta_str}")
            print("-" * 80 + "\n")

            # 3. Input Decision
            selection = input("Select row # to inspect, or 'n' for new search: ")
            if selection.lower() == 'n':
                break # Breaks Inner Loop, goes back to Get Query

            try:
                index = int(selection) - 1
                if 0 <= index < len(results):
                    inspector_view(results[index]['data'], query_vector)
                    input("\nPress Enter to return to results...")
                    # DO NOT break here. Let Inner Loop repeat.
                else:
                    print("Invalid row number.")
            except ValueError:
                print("Invalid input. Please enter a number or 'n'.")

def inspector_view(session_data, query_vector):
    """
    Displays a detailed 'heatmap' of chunk scores for a selected session and shows the most relevant passage.
    """
    print(f"\n--- Inspector for Session: {session_data['session_id']} ---")
    
    chunk_vectors = session_data['chunk_vectors']
    chunk_texts = session_data['chunk_texts']
    chunk_metadata = session_data.get('chunk_metadata', [])

    scores = [cosine_similarity(query_vector, vec) for vec in chunk_vectors]
    
    highest_score = -1
    highest_scoring_chunk_index = -1
    
    for i, score in enumerate(scores):
        bar_length = int(score * 20)
        bar = '[' + '█' * bar_length + ' ' * (20 - bar_length) + ']'
        print(f"Chunk {i+1:<2}: {bar} {score:.4f}")
        if score > highest_score:
            highest_score = score
            highest_scoring_chunk_index = i
            
    if highest_scoring_chunk_index != -1:
        print("\nMost Relevant Passage:")
        print("-" * 25)
        print(chunk_texts[highest_scoring_chunk_index])
        if chunk_metadata and highest_scoring_chunk_index < len(chunk_metadata):
            print(f"Segments included: {chunk_metadata[highest_scoring_chunk_index]}")
        print("-" * 25)
    
    print("-" * 50 + "\n")

def main():
    """Main application logic."""
    config = load_config()
    logger = get_sdc_logger(__name__, config)
    
    vectorizer = None
    try:
        vectorizer = SessionVectorizer(config, logger)
    except (ValueError, KeyError) as e:
        logger.critical(f"Initialization failed: {e}")
        return

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
        except (EOFError, KeyboardInterrupt):
            logger.info("Exiting.")
            return

    logger.info(f"Fetching latest {num_sessions} sessions to compute vectors...")
    try:
        cursor = vectorizer.conn.execute(f"SELECT session_id FROM sessions ORDER BY start_time DESC LIMIT {num_sessions}")
        session_ids = [row[0] for row in cursor.fetchall()]
        
        session_vectors_data = {}
        for i, session_id in enumerate(session_ids):
            print(f"\rProcessing session {i+1}/{len(session_ids)}: {session_id}...", end="", flush=True)
            session_vectors_data[session_id] = vectorizer.get_session_vectors(session_id)
        print("\nVector computation complete.")

        run_interactive_search(session_vectors_data, vectorizer)

    except sqlite3.Error as e:
        logger.error(f"A database error occurred: {e}")
    except (EOFError, KeyboardInterrupt):
        logger.info("\nShutdown requested.")
    finally:
        if vectorizer:
            vectorizer.close()
            logger.info("Database connection closed. Exiting.")

if __name__ == "__main__":
    main()
