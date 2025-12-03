import sqlite3
import json
import logging
from sdc.models.session_v2 import Session, SessionSegment

class SessionDatabaseManager:
    """
    Manages the SQLite database for session and segment data.
    """

    def __init__(self, db_path: str, logger: logging.Logger):
        """
        Initializes the SessionDatabaseManager.

        :param db_path: Path to the SQLite database file.
        :param logger: Logger instance.
        """
        self.db_path = db_path
        self.logger = logger
        self.conn = sqlite3.connect(db_path)
        self.conn.execute('PRAGMA foreign_keys = ON;')
        self.logger.info(f"Connected to database at {db_path}")

    def init_schema(self):
        """
        Initializes the database schema by creating the 'sessions' and 'segments' tables if they don't exist.
        """
        try:
            with self.conn:
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id TEXT PRIMARY KEY,
                        customer_name TEXT,
                        start_time TEXT,
                        end_time TEXT,
                        source_system TEXT,
                        processing_status TEXT,
                        processing_log TEXT,
                        links_data TEXT,
                        generated_summaries TEXT,
                        llm_results TEXT,
                        full_json_backup TEXT
                    )
                """)
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS segments (
                        segment_id TEXT PRIMARY KEY,
                        session_id TEXT,
                        start_time TEXT,
                        author TEXT,
                        type TEXT,
                        content TEXT,
                        metadata TEXT,
                        FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                    )
                """)
                self.logger.info("Database schema initialized successfully.")
        except sqlite3.Error as e:
            self.logger.error(f"Error initializing database schema: {e}")
            raise

    def upsert_session(self, session: Session):
        """
        Inserts or updates a session and its segments in the database.
        This is an 'upsert' operation: it first deletes the existing session (and its
        cascading segments) and then inserts the new data.

        :param session: The Session object to upsert.
        """
        try:
            # Pydantic v2 uses model_dump_json(), v1 uses json().
            if hasattr(session, 'model_dump_json'):
                full_json_backup = session.model_dump_json()
            else:
                full_json_backup = session.json()

            session_data = (
                session.meta.session_id,
                session.context.customer_name,
                session.insights.session_start_time_utc.isoformat(),
                session.insights.session_end_time_utc.isoformat(),
                session.meta.source_system,
                session.meta.processing_status,
                json.dumps(session.meta.processing_log),
                json.dumps(session.context.links),
                json.dumps(session.insights.generated_summaries),
                json.dumps(session.insights.structured_llm_results),
                full_json_backup
            )

            segments_data = []
            for segment in session.segments:
                segments_data.append((
                    segment.segment_id,
                    session.meta.session_id,
                    segment.start_time_utc.isoformat(),
                    segment.author,
                    segment.type,
                    segment.content,
                    json.dumps(segment.metadata)
                ))

            with self.conn:
                # The 'with' block ensures atomicity (commit/rollback)
                cursor = self.conn.cursor()

                # Clean up existing records first
                cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session.meta.session_id,))

                # Insert the main session record
                cursor.execute("""
                    INSERT INTO sessions (
                        session_id, customer_name, start_time, end_time, source_system,
                        processing_status, processing_log, links_data, generated_summaries,
                        llm_results, full_json_backup
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, session_data)

                # Bulk insert all segment records
                if segments_data:
                    cursor.executemany("""
                        INSERT INTO segments (
                            segment_id, session_id, start_time, author, type, content, metadata
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, segments_data)
            
            self.logger.info(f"Successfully upserted session_id: {session.meta.session_id} with {len(segments_data)} segments.")

        except sqlite3.Error as e:
            self.logger.error(f"Database error during upsert for session_id {session.meta.session_id}: {e}")
            raise
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during upsert for session_id {session.meta.session_id}: {e}")
            raise

    def close(self):
        """
        Closes the database connection.
        """
        if self.conn:
            self.conn.close()
            self.logger.info("Database connection closed.")