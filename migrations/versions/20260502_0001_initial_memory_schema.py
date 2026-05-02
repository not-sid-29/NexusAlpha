"""initial memory schema

Revision ID: 20260502_0001
Revises:
Create Date: 2026-05-02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260502_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.Text(), primary_key=True),
        sa.Column("username", sa.Text(), nullable=True),
        sa.Column("preferences_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "sessions",
        sa.Column("trace_id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), sa.ForeignKey("users.user_id"), nullable=True),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("autonomy_mode", sa.Text(), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "interactions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "trace_id",
            sa.Text(),
            sa.ForeignKey("sessions.trace_id"),
            nullable=True,
        ),
        sa.Column("msg_type", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("target", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "graph_nodes",
        sa.Column("node_id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("node_type", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("attributes_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
    )
    op.create_index("idx_graph_nodes_user", "graph_nodes", ["user_id"])
    op.create_index("idx_graph_nodes_type", "graph_nodes", ["user_id", "node_type"])
    op.create_index(
        "idx_graph_nodes_user_type_label",
        "graph_nodes",
        ["user_id", "node_type", "label"],
        unique=True,
    )

    op.create_table(
        "graph_edges",
        sa.Column("edge_id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column(
            "source_id",
            sa.Text(),
            sa.ForeignKey("graph_nodes.node_id"),
            nullable=False,
        ),
        sa.Column(
            "target_id",
            sa.Text(),
            sa.ForeignKey("graph_nodes.node_id"),
            nullable=False,
        ),
        sa.Column("edge_type", sa.Text(), nullable=False),
        sa.Column("weight", sa.Float(), server_default=sa.text("1.0")),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
    )
    op.create_index("idx_graph_edges_user", "graph_edges", ["user_id"])
    op.create_index("idx_graph_edges_source", "graph_edges", ["source_id"])


def downgrade() -> None:
    op.drop_index("idx_graph_edges_source", table_name="graph_edges")
    op.drop_index("idx_graph_edges_user", table_name="graph_edges")
    op.drop_table("graph_edges")

    op.drop_index("idx_graph_nodes_user_type_label", table_name="graph_nodes")
    op.drop_index("idx_graph_nodes_type", table_name="graph_nodes")
    op.drop_index("idx_graph_nodes_user", table_name="graph_nodes")
    op.drop_table("graph_nodes")

    op.drop_table("interactions")
    op.drop_table("sessions")
    op.drop_table("users")
