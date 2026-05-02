"""Nexus Memory — User Graph (NetworkX + SQLite persistence)."""

from __future__ import annotations
import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

import networkx as nx

from memory.db_manager import DatabaseManager
from memory.models import (
    EdgeType,
    GraphEdge,
    GraphNode,
    GraphQueryResult,
    GraphStats,
    NodeType,
)

logger = logging.getLogger("nexus.memory.graph")


class UserGraph:
    """
    Per-user semantic knowledge graph. NetworkX in-memory graph backed by SQLite.

    Grows across sessions — corrections, preferences, concepts, error patterns
    all accumulate as nodes/edges. ContextManager queries this for P2 slot.
    This is the product moat; everything else is scaffolding.
    """

    def __init__(self, user_id: str, db_manager: DatabaseManager):
        self.user_id = user_id
        self.db = db_manager
        self._graph: nx.DiGraph = nx.DiGraph()
        self._loaded = False

    # ------------------------------------------------------------------
    # Core graph operations
    # ------------------------------------------------------------------

    def add_node(
        self,
        node_type: NodeType,
        label: str,
        attributes: Optional[Dict[str, Any]] = None,
        node_id: Optional[str] = None,
    ) -> str:
        """Add a node. Returns node_id. Deduplicates by (user_id, node_type, label)."""
        existing_id = self._find_node_by_label(node_type, label)
        if existing_id:
            self.update_node(existing_id, attributes or {})
            return existing_id

        nid = node_id or f"{node_type.value.lower()}_{uuid.uuid4().hex[:12]}"
        now = int(time.time())
        node = GraphNode(
            node_id=nid,
            user_id=self.user_id,
            node_type=node_type,
            label=label,
            attributes=attributes or {},
            created_at=now,
            updated_at=now,
        )
        self._graph.add_node(
            nid,
            user_id=self.user_id,
            node_type=node_type.value,
            label=label,
            attributes=attributes or {},
            created_at=now,
            updated_at=now,
        )
        self._persist_node(node)
        logger.debug("[GRAPH] Added node %s (%s) '%s'", nid, node_type.value, label)
        return nid

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType,
        weight: float = 1.0,
    ) -> str:
        """Add a directed edge. Increments weight if edge already exists."""
        if not (self._graph.has_node(source_id) and self._graph.has_node(target_id)):
            raise ValueError(
                f"Both nodes must exist before adding edge: {source_id} → {target_id}"
            )

        if self._graph.has_edge(source_id, target_id):
            existing_data = self._graph[source_id][target_id]
            if existing_data.get("edge_type") == edge_type.value:
                new_weight = existing_data.get("weight", 1.0) + weight
                self._graph[source_id][target_id]["weight"] = new_weight
                self._update_edge_weight(source_id, target_id, edge_type, new_weight)
                return existing_data["edge_id"]

        eid = f"edge_{uuid.uuid4().hex[:12]}"
        now = int(time.time())
        edge = GraphEdge(
            edge_id=eid,
            user_id=self.user_id,
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            weight=weight,
            created_at=now,
        )
        self._graph.add_edge(
            source_id,
            target_id,
            edge_id=eid,
            edge_type=edge_type.value,
            weight=weight,
            created_at=now,
        )
        self._persist_edge(edge)
        logger.debug("[GRAPH] Edge %s -[%s]-> %s", source_id, edge_type.value, target_id)
        return eid

    def update_node(self, node_id: str, attributes: Dict[str, Any]) -> None:
        """Merge new attributes into existing node."""
        if not self._graph.has_node(node_id):
            raise KeyError(f"Node not found: {node_id}")
        current = self._graph.nodes[node_id].get("attributes", {})
        merged = {**current, **attributes}
        self._graph.nodes[node_id]["attributes"] = merged
        self._graph.nodes[node_id]["updated_at"] = int(time.time())
        self._update_node_in_db(node_id, merged)

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        if not self._graph.has_node(node_id):
            return None
        return dict(self._graph.nodes[node_id])

    def get_neighbors(
        self, node_id: str, edge_type: Optional[EdgeType] = None
    ) -> List[Dict[str, Any]]:
        """Return neighbor nodes, optionally filtered by edge type."""
        if not self._graph.has_node(node_id):
            return []
        results = []
        for neighbor_id in self._graph.successors(node_id):
            edge_data = self._graph[node_id][neighbor_id]
            if edge_type and edge_data.get("edge_type") != edge_type.value:
                continue
            node_data = dict(self._graph.nodes[neighbor_id])
            node_data["node_id"] = neighbor_id
            node_data["edge_weight"] = edge_data.get("weight", 1.0)
            results.append(node_data)
        return results

    # ------------------------------------------------------------------
    # Query interface — used by ContextManager for P2 slot
    # ------------------------------------------------------------------

    def query_preferences(self) -> List[Dict[str, Any]]:
        """All Preference nodes for this user, sorted by reference weight."""
        return self._query_nodes_by_type(NodeType.PREFERENCE)

    def query_domain_knowledge(self, topic: str) -> List[Dict[str, Any]]:
        """Concept nodes whose label contains the topic string (case-insensitive)."""
        nodes = self._query_nodes_by_type(NodeType.CONCEPT)
        topic_lower = topic.lower()
        return [n for n in nodes if topic_lower in n.get("label", "").lower()]

    def query_corrections(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Most recent Correction nodes — what the user fixed."""
        nodes = self._query_nodes_by_type(NodeType.CORRECTION)
        nodes.sort(key=lambda n: n.get("updated_at", 0), reverse=True)
        return nodes[:limit]

    def query_active_goals(self) -> List[Dict[str, Any]]:
        """Goal nodes with status=active."""
        nodes = self._query_nodes_by_type(NodeType.GOAL)
        return [
            n
            for n in nodes
            if n.get("attributes", {}).get("status") == "active"
        ]

    def query_error_patterns(self, limit: int = 15) -> List[Dict[str, Any]]:
        """Error nodes sorted by occurrence count (most recurring first)."""
        nodes = self._query_nodes_by_type(NodeType.ERROR)
        nodes.sort(
            key=lambda n: n.get("attributes", {}).get("occurrence_count", 0),
            reverse=True,
        )
        return nodes[:limit]

    def get_stats(self) -> GraphStats:
        by_type: Dict[str, int] = {}
        for _, data in self._graph.nodes(data=True):
            t = data.get("node_type", "Unknown")
            by_type[t] = by_type.get(t, 0) + 1
        last_update = max(
            (data.get("updated_at", 0) for _, data in self._graph.nodes(data=True)),
            default=None,
        )
        return GraphStats(
            total_nodes=self._graph.number_of_nodes(),
            total_edges=self._graph.number_of_edges(),
            nodes_by_type=by_type,
            last_updated=last_update,
        )

    # ------------------------------------------------------------------
    # Convenience builders — agents call these directly
    # ------------------------------------------------------------------

    def record_preference(self, category: str, value: str, confidence: float = 1.0) -> str:
        """Upsert a user preference (coding style, output format, etc.)."""
        label = f"{category}:{value}"
        nid = self.add_node(
            NodeType.PREFERENCE,
            label,
            {"category": category, "value": value, "confidence": confidence},
        )
        return nid

    def record_correction(
        self, original: str, corrected: str, context: str = "", trace_id: str = ""
    ) -> str:
        """Record something the user corrected. Strongest learning signal."""
        label = f"correction:{uuid.uuid4().hex[:8]}"
        nid = self.add_node(
            NodeType.CORRECTION,
            label,
            {
                "original": original,
                "corrected": corrected,
                "context": context,
                "trace_id": trace_id,
            },
        )
        return nid

    def record_concept(self, topic: str, summary: str = "", source: str = "") -> str:
        """Record a concept or domain knowledge node encountered in a session."""
        nid = self.add_node(
            NodeType.CONCEPT,
            topic,
            {"summary": summary, "source": source},
        )
        return nid

    def record_error(self, error_type: str, description: str, fix: str = "") -> str:
        """Record an error pattern. Increments occurrence_count on repeat."""
        nid = self.add_node(NodeType.ERROR, error_type, {})
        current = self._graph.nodes[nid].get("attributes", {})
        count = current.get("occurrence_count", 0) + 1
        self.update_node(
            nid,
            {
                "description": description,
                "last_fix": fix,
                "occurrence_count": count,
            },
        )
        return nid

    def record_goal(self, goal_id: str, objective: str, status: str = "active") -> str:
        """Upsert a GoalSession reference node."""
        nid = self.add_node(
            NodeType.GOAL,
            f"goal:{goal_id}",
            {"goal_id": goal_id, "objective": objective, "status": status},
            node_id=f"goal_{goal_id}",
        )
        return nid

    # ------------------------------------------------------------------
    # Persistence — serialize NetworkX ↔ SQLite
    # ------------------------------------------------------------------

    def save(self) -> None:
        """Flush the in-memory graph to SQLite. Called at session end by MemoryScribe."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            now = int(time.time())

            for node_id, data in self._graph.nodes(data=True):
                cursor.execute(
                    """
                    INSERT INTO graph_nodes
                        (node_id, user_id, node_type, label, attributes_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(node_id) DO UPDATE SET
                        attributes_json = excluded.attributes_json,
                        updated_at = excluded.updated_at
                    """,
                    (
                        node_id,
                        self.user_id,
                        data.get("node_type", "Unknown"),
                        data.get("label", node_id),
                        json.dumps(data.get("attributes", {})),
                        data.get("created_at", now),
                        data.get("updated_at", now),
                    ),
                )

            for source_id, target_id, edge_data in self._graph.edges(data=True):
                eid = edge_data.get("edge_id", f"edge_{uuid.uuid4().hex[:12]}")
                edge_insert = """
                    INSERT INTO graph_edges
                        (edge_id, user_id, source_id, target_id, edge_type, weight, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(edge_id) DO NOTHING
                    """
                if self.db.backend == "sqlite":
                    edge_insert = """
                    INSERT OR IGNORE INTO graph_edges
                        (edge_id, user_id, source_id, target_id, edge_type, weight, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """
                cursor.execute(
                    edge_insert,
                    (
                        eid,
                        self.user_id,
                        source_id,
                        target_id,
                        edge_data.get("edge_type", EdgeType.RELATED_TO.value),
                        edge_data.get("weight", 1.0),
                        edge_data.get("created_at", now),
                    ),
                )

            conn.commit()
        logger.info(
            "[GRAPH] Saved %d nodes, %d edges for user %s",
            self._graph.number_of_nodes(),
            self._graph.number_of_edges(),
            self.user_id,
        )

    def load(self) -> None:
        """Reconstruct NetworkX graph from SQLite for this user."""
        self._graph = nx.DiGraph()
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM graph_nodes WHERE user_id = ?", (self.user_id,)
            )
            for row in cursor.fetchall():
                self._graph.add_node(
                    row["node_id"],
                    user_id=row["user_id"],
                    node_type=row["node_type"],
                    label=row["label"],
                    attributes=json.loads(row["attributes_json"] or "{}"),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )

            cursor.execute(
                "SELECT * FROM graph_edges WHERE user_id = ?", (self.user_id,)
            )
            for row in cursor.fetchall():
                self._graph.add_edge(
                    row["source_id"],
                    row["target_id"],
                    edge_id=row["edge_id"],
                    edge_type=row["edge_type"],
                    weight=row["weight"],
                    created_at=row["created_at"],
                )

        self._loaded = True
        logger.info(
            "[GRAPH] Loaded %d nodes, %d edges for user %s",
            self._graph.number_of_nodes(),
            self._graph.number_of_edges(),
            self.user_id,
        )

    def export_json(self) -> Dict[str, Any]:
        """Serialize full graph for the /user/graph API endpoint."""
        nodes = []
        for nid, data in self._graph.nodes(data=True):
            nodes.append({"node_id": nid, **data})
        edges = []
        for src, tgt, edata in self._graph.edges(data=True):
            edges.append({"source": src, "target": tgt, **edata})
        return {
            "user_id": self.user_id,
            "stats": self.get_stats().model_dump(),
            "nodes": nodes,
            "edges": edges,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_node_by_label(self, node_type: NodeType, label: str) -> Optional[str]:
        for nid, data in self._graph.nodes(data=True):
            if (
                data.get("node_type") == node_type.value
                and data.get("label") == label
                and data.get("user_id") == self.user_id
            ):
                return nid
        return None

    def _query_nodes_by_type(self, node_type: NodeType) -> List[Dict[str, Any]]:
        results = []
        for nid, data in self._graph.nodes(data=True):
            if (
                data.get("node_type") == node_type.value
                and data.get("user_id") == self.user_id
            ):
                results.append({"node_id": nid, **data})
        return results

    def _persist_node(self, node: GraphNode) -> None:
        with self.db.get_connection() as conn:
            query = """
                INSERT INTO graph_nodes
                    (node_id, user_id, node_type, label, attributes_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(node_id) DO NOTHING
                """
            if self.db.backend == "sqlite":
                query = """
                INSERT OR IGNORE INTO graph_nodes
                    (node_id, user_id, node_type, label, attributes_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """
            conn.execute(
                query,
                (
                    node.node_id,
                    node.user_id,
                    node.node_type.value,
                    node.label,
                    json.dumps(node.attributes),
                    node.created_at,
                    node.updated_at,
                ),
            )
            conn.commit()

    def _persist_edge(self, edge: GraphEdge) -> None:
        with self.db.get_connection() as conn:
            query = """
                INSERT INTO graph_edges
                    (edge_id, user_id, source_id, target_id, edge_type, weight, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(edge_id) DO NOTHING
                """
            if self.db.backend == "sqlite":
                query = """
                INSERT OR IGNORE INTO graph_edges
                    (edge_id, user_id, source_id, target_id, edge_type, weight, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """
            conn.execute(
                query,
                (
                    edge.edge_id,
                    edge.user_id,
                    edge.source_id,
                    edge.target_id,
                    edge.edge_type.value,
                    edge.weight,
                    edge.created_at,
                ),
            )
            conn.commit()

    def _update_node_in_db(self, node_id: str, attributes: Dict[str, Any]) -> None:
        now = int(time.time())
        with self.db.get_connection() as conn:
            conn.execute(
                """
                UPDATE graph_nodes
                SET attributes_json = ?, updated_at = ?
                WHERE node_id = ?
                """,
                (json.dumps(attributes), now, node_id),
            )
            conn.commit()

    def _update_edge_weight(
        self, source_id: str, target_id: str, edge_type: EdgeType, new_weight: float
    ) -> None:
        with self.db.get_connection() as conn:
            conn.execute(
                """
                UPDATE graph_edges SET weight = ?
                WHERE source_id = ? AND target_id = ? AND edge_type = ?
                """,
                (new_weight, source_id, target_id, edge_type.value),
            )
            conn.commit()
