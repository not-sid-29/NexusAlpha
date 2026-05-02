"""Database URL helpers shared by runtime and Alembic."""

from __future__ import annotations

import os

from sqlalchemy import URL


def build_database_url() -> str:
    """Return DATABASE_URL or construct one from the project's DB_* env vars."""
    explicit_url = os.getenv("DATABASE_URL")
    if explicit_url:
        return explicit_url

    host = os.getenv("DB_HOST")
    if not host:
        sqlite_path = os.getenv("SQLITE_DB_PATH", "nexus_alpha.db")
        return f"sqlite:///{sqlite_path}"

    query = {"sslmode": os.getenv("DB_SSLMODE", "require")}
    return URL.create(
        "postgresql+psycopg",
        username=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        host=host,
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "postgres"),
        query=query,
    ).render_as_string(hide_password=False)
