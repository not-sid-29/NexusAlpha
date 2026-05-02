"""SQLAlchemy ORM models for NexusAlpha relational memory."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Float, ForeignKey, Text, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(Text, primary_key=True)
    username: Mapped[str | None] = mapped_column(Text)
    preferences_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("CURRENT_TIMESTAMP")
    )


class Session(Base):
    __tablename__ = "sessions"

    trace_id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"))
    status: Mapped[str | None] = mapped_column(Text)
    autonomy_mode: Mapped[str | None] = mapped_column(Text)
    start_time: Mapped[datetime] = mapped_column(
        server_default=text("CURRENT_TIMESTAMP")
    )
    end_time: Mapped[datetime | None]


class Interaction(Base):
    __tablename__ = "interactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trace_id: Mapped[str | None] = mapped_column(ForeignKey("sessions.trace_id"))
    msg_type: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(Text)
    target: Mapped[str | None] = mapped_column(Text)
    payload_json: Mapped[str | None] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(server_default=text("CURRENT_TIMESTAMP"))


class GraphNode(Base):
    __tablename__ = "graph_nodes"

    node_id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    node_type: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    attributes_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


class GraphEdge(Base):
    __tablename__ = "graph_edges"

    edge_id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("graph_nodes.node_id"))
    target_id: Mapped[str] = mapped_column(ForeignKey("graph_nodes.node_id"))
    edge_type: Mapped[str] = mapped_column(Text, nullable=False)
    weight: Mapped[float] = mapped_column(Float, server_default=text("1.0"))
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
