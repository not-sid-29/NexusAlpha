import sqlite3
import os
import logging
from contextlib import contextmanager
from typing import Generator

logger = logging.getLogger("nexus.memory.db")

class DatabaseManager:
    """
    Manages SQLite connections with WAL (Write-Ahead Logging) enabled.
    Ensures the "Harness Zero Waste" principle by enforcing strict schema access.
    """
    def __init__(self, db_path: str = "nexus_alpha.db"):
        self.db_path = db_path
        self._initialize_db()

    def _initialize_db(self):
        """
        Idempotent database initialization. Sets WAL mode immediately.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            logger.info(f"Database initialized at {self.db_path} in WAL mode.")
            
            # Unit 1.1 Schema setup
            self._create_tables(conn)
        finally:
            conn.close()

    def _create_tables(self, conn: sqlite3.Connection):
        """
        Defines the relational tables for users, sessions, and interactions.
        Namespace isolation is enforced via user_id and trace_id columns.
        """
        cursor = conn.cursor()
        
        # User Table: Basic profiles and styling prefs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT,
                preferences_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Session Table: Mirrors the FSM state registry
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                trace_id TEXT PRIMARY KEY,
                user_id TEXT,
                status TEXT,
                autonomy_mode TEXT,
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        """)

        # Interactions: Turn-by-turn history per session
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id TEXT,
                msg_type TEXT,
                source TEXT,
                target TEXT,
                payload_json TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(trace_id) REFERENCES sessions(trace_id)
            )
        """)
        
        conn.commit()

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Context manager for retrieving a connection. 
        Enforces WAL mode on every session.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            yield conn
        finally:
            conn.close()
