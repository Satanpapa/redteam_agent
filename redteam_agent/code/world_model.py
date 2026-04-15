"""World model backed by NetworkX with SQLite persistence."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

import networkx as nx

from .models import WorldEdge, WorldNode

logger = logging.getLogger(__name__)


class WorldModel:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.graph = nx.MultiDiGraph()
        self._init_db()
        self._load_from_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS nodes (
                    node_id TEXT PRIMARY KEY,
                    node_type TEXT NOT NULL,
                    label TEXT NOT NULL,
                    properties TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS edges (
                    src_id TEXT NOT NULL,
                    dst_id TEXT NOT NULL,
                    relationship TEXT NOT NULL,
                    properties TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    observed_at TEXT NOT NULL,
                    PRIMARY KEY (src_id, dst_id, relationship)
                )
                """
            )

    def _load_from_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            node_rows = conn.execute("SELECT * FROM nodes").fetchall()
            edge_rows = conn.execute("SELECT * FROM edges").fetchall()

        for row in node_rows:
            node = WorldNode(
                node_id=row[0],
                node_type=row[1],
                label=row[2],
                properties=json.loads(row[3]),
                confidence=row[4],
                first_seen=row[5],
                last_seen=row[6],
            )
            self.graph.add_node(node.node_id, **node.model_dump())

        for row in edge_rows:
            edge = WorldEdge(
                src_id=row[0],
                dst_id=row[1],
                relationship=row[2],
                properties=json.loads(row[3]),
                confidence=row[4],
                observed_at=row[5],
            )
            self.graph.add_edge(edge.src_id, edge.dst_id, key=edge.relationship, **edge.model_dump())

        logger.info("WorldModel loaded: %s nodes, %s edges", self.graph.number_of_nodes(), self.graph.number_of_edges())

    def upsert_node(self, node: WorldNode) -> None:
        self.graph.add_node(node.node_id, **node.model_dump())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO nodes (node_id, node_type, label, properties, confidence, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(node_id) DO UPDATE SET
                    node_type=excluded.node_type,
                    label=excluded.label,
                    properties=excluded.properties,
                    confidence=excluded.confidence,
                    last_seen=excluded.last_seen
                """,
                (
                    node.node_id,
                    node.node_type.value if hasattr(node.node_type, "value") else str(node.node_type),
                    node.label,
                    json.dumps(node.properties),
                    node.confidence,
                    node.first_seen.isoformat(),
                    node.last_seen.isoformat(),
                ),
            )

    def upsert_edge(self, edge: WorldEdge) -> None:
        self.graph.add_edge(edge.src_id, edge.dst_id, key=edge.relationship, **edge.model_dump())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO edges (src_id, dst_id, relationship, properties, confidence, observed_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(src_id, dst_id, relationship) DO UPDATE SET
                    properties=excluded.properties,
                    confidence=excluded.confidence,
                    observed_at=excluded.observed_at
                """,
                (
                    edge.src_id,
                    edge.dst_id,
                    edge.relationship,
                    json.dumps(edge.properties),
                    edge.confidence,
                    edge.observed_at.isoformat(),
                ),
            )

    def query_neighbors(self, node_id: str) -> list[dict[str, Any]]:
        if node_id not in self.graph:
            return []
        neighbors: list[dict[str, Any]] = []
        for neighbor in self.graph.neighbors(node_id):
            neighbors.append(self.graph.nodes[neighbor])
        return neighbors

    def shortest_path(self, src_id: str, dst_id: str) -> list[str]:
        if src_id not in self.graph or dst_id not in self.graph:
            return []
        try:
            return nx.shortest_path(self.graph, source=src_id, target=dst_id)
        except nx.NetworkXNoPath:
            return []

    def snapshot(self) -> dict[str, Any]:
        return {
            "node_count": self.graph.number_of_nodes(),
            "edge_count": self.graph.number_of_edges(),
            "nodes": [data for _, data in self.graph.nodes(data=True)],
            "edges": [data for _, _, _, data in self.graph.edges(keys=True, data=True)],
        }
