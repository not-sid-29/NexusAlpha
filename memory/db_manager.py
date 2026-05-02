import os
import logging
import sqlite3
from contextlib import contextmanager
from typing import Any, Generator, Optional

from memory.database_url import build_database_url

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover - optional Postgres dependency
    psycopg = None
    dict_row = None

logger = logging.getLogger("nexus.memory.db")


class _CursorAdapter:
    """Normalizes sqlite-style placeholders for SQLite and psycopg cursors."""

    def __init__(self, cursor: Any, backend: str):
        self._cursor = cursor
        self._backend = backend

    def execute(self, query: str, params: tuple = ()):
        if self._backend == "postgres":
            query = query.replace("?", "%s")
        return self._cursor.execute(query, params)

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def __getattr__(self, name: str):
        return getattr(self._cursor, name)


class _ConnectionAdapter:
    """Small DB-API adapter so the rest of memory code stays backend-agnostic."""

    def __init__(self, conn: Any, backend: str):
        self._conn = conn
        self._backend = backend

    def execute(self, query: str, params: tuple = ()):
        if self._backend == "postgres":
            query = query.replace("?", "%s")
        return self._conn.execute(query, params)

    def cursor(self):
        return _CursorAdapter(self._conn.cursor(), self._backend)

    def commit(self):
        return self._conn.commit()

    def close(self):
        return self._conn.close()

    def __getattr__(self, name: str):
        return getattr(self._conn, name)


class DatabaseManager:
    """
    Manages the relational memory store.

    SQLite remains supported for local-first development/tests. Supabase/Postgres
    is selected by passing backend="postgres" or by using from_env() with DB_HOST.
    """

    def __init__(
        self,
        db_path: str = "nexus_alpha.db",
        backend: str = "sqlite",
        postgres_dsn: Optional[str] = None,
        auto_create_schema: bool = True,
    ):
        self.db_path = db_path
        self.backend = backend
        self.postgres_dsn = postgres_dsn
        self.auto_create_schema = auto_create_schema
        if self.auto_create_schema:
            self._initialize_db()

    @classmethod
    def from_env(cls) -> "DatabaseManager":
        """Build a manager from .env-style variables, preferring Supabase if present."""
        host = os.getenv("DB_HOST")
        database_url = build_database_url()
        if host or database_url.startswith("postgres"):
            psycopg_url = database_url.replace("postgresql+psycopg://", "postgresql://")
            return cls(
                backend="postgres",
                postgres_dsn=psycopg_url,
                auto_create_schema=False,
            )
        return cls(db_path=os.getenv("SQLITE_DB_PATH", "nexus_alpha.db"))

    def _initialize_db(self):
        """
        Idempotent database initialization.
        """
        conn = self._connect_raw()
        try:
            if self.backend == "sqlite":
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA synchronous=NORMAL;")
                logger.info("SQLite database initialized at %s in WAL mode.", self.db_path)
            else:
                logger.info("Postgres database initialized for Nexus memory store.")

            self._create_tables(conn)
        finally:
            conn.close()

    def _connect_raw(self):
        if self.backend == "postgres":
            if psycopg is None:
                raise RuntimeError(
                    "Postgres backend requires psycopg. Install requirements.txt first."
                )
            if not self.postgres_dsn:
                raise ValueError("postgres_dsn is required for Postgres backend")
            return psycopg.connect(self.postgres_dsn, row_factory=dict_row)

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _create_tables(self, conn: Any):
        """
        Defines the relational tables for users, sessions, and interactions.
        Namespace isolation is enforced via user_id and trace_id columns.
        """
        cursor = conn.cursor()
        if self.backend == "postgres":
            self._create_postgres_tables(cursor)
        else:
            self._create_sqlite_tables(cursor)
        conn.commit()

    def _create_sqlite_tables(self, cursor: sqlite3.Cursor):
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

        # Graph nodes: persistent user knowledge graph
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS graph_nodes (
                node_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                node_type TEXT NOT NULL,
                label TEXT NOT NULL,
                attributes_json TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_graph_nodes_user
            ON graph_nodes(user_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_graph_nodes_type
            ON graph_nodes(user_id, node_type)
        """)

        # Graph edges: relationships between nodes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS graph_edges (
                edge_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                edge_type TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                created_at INTEGER NOT NULL,
                FOREIGN KEY(source_id) REFERENCES graph_nodes(node_id),
                FOREIGN KEY(target_id) REFERENCES graph_nodes(node_id)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_graph_edges_user
            ON graph_edges(user_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_graph_edges_source
            ON graph_edges(source_id)
        """)

    def _create_postgres_tables(self, cursor: Any):
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT,
                preferences_json TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                trace_id TEXT PRIMARY KEY,
                user_id TEXT,
                status TEXT,
                autonomy_mode TEXT,
                start_time TIMESTAMPTZ DEFAULT NOW(),
                end_time TIMESTAMPTZ,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                trace_id TEXT,
                msg_type TEXT,
                source TEXT,
                target TEXT,
                payload_json TEXT,
                timestamp TIMESTAMPTZ DEFAULT NOW(),
                FOREIGN KEY(trace_id) REFERENCES sessions(trace_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS graph_nodes (
                node_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                node_type TEXT NOT NULL,
                label TEXT NOT NULL,
                attributes_json TEXT,
                created_at BIGINT NOT NULL,
                updated_at BIGINT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_graph_nodes_user_type_label
            ON graph_nodes(user_id, node_type, label)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_graph_nodes_user
            ON graph_nodes(user_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_graph_nodes_type
            ON graph_nodes(user_id, node_type)
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS graph_edges (
                edge_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                source_id TEXT NOT NULL REFERENCES graph_nodes(node_id),
                target_id TEXT NOT NULL REFERENCES graph_nodes(node_id),
                edge_type TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                created_at BIGINT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_graph_edges_user
            ON graph_edges(user_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_graph_edges_source
            ON graph_edges(source_id)
        """)

    @contextmanager
    def get_connection(self) -> Generator[Any, None, None]:
        """
        Context manager for retrieving a connection. 
        Enforces WAL mode on every SQLite session.
        """
        raw_conn = self._connect_raw()
        conn = _ConnectionAdapter(raw_conn, self.backend)
        try:
            if self.backend == "sqlite":
                conn.execute("PRAGMA journal_mode=WAL;")
            yield conn
        finally:
            conn.close()
