"""Persistent world model based on NetworkX and SQLite."""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

import networkx as nx

from .models import WorldEdge, WorldNode

logger = logging.getLogger(__name__)


class WorldModel:
    """Maintains a graph of discovered entities and relationships."""

    def __init__(self, sqlite_path: str) -> None:
        self.sqlite_path = Path(sqlite_path)
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self.graph = nx.DiGraph()
        self._init_schema()
        self.load()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.sqlite_path)

    def _init_schema(self) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS nodes (
                    node_id TEXT PRIMARY KEY,
                    node_type TEXT NOT NULL,
                    properties TEXT NOT NULL,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS edges (
                    src TEXT NOT NULL,
                    dst TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    properties TEXT NOT NULL,
                    PRIMARY KEY (src, dst, relation)
                )
                """
            )

    def upsert_node(self, node: WorldNode) -> None:
        self.graph.add_node(node.node_id, **node.model_dump())

    def upsert_edge(self, edge: WorldEdge) -> None:
        self.graph.add_edge(edge.src, edge.dst, **edge.model_dump())

    def save(self) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute("DELETE FROM nodes")
            conn.execute("DELETE FROM edges")
            for node_id, attrs in self.graph.nodes(data=True):
                conn.execute(
                    "INSERT INTO nodes VALUES (?, ?, ?, ?, ?)",
                    (
                        node_id,
                        attrs.get("node_type"),
                        json.dumps(attrs.get("properties", {})),
                        str(attrs.get("first_seen")),
                        str(attrs.get("last_seen")),
                    ),
                )
            for src, dst, attrs in self.graph.edges(data=True):
                conn.execute(
                    "INSERT INTO edges VALUES (?, ?, ?, ?, ?)",
                    (
                        src,
                        dst,
                        attrs.get("relation"),
                        float(attrs.get("confidence", 0.5)),
                        json.dumps(attrs.get("properties", {})),
                    ),
                )
        logger.info("World model saved (%s nodes, %s edges)", self.graph.number_of_nodes(), self.graph.number_of_edges())

    def load(self) -> None:
        if not self.sqlite_path.exists():
            return
        with closing(self._connect()) as conn:
            for row in conn.execute("SELECT node_id, node_type, properties, first_seen, last_seen FROM nodes"):
                node_id, node_type, properties, first_seen, last_seen = row
                self.graph.add_node(
                    node_id,
                    node_id=node_id,
                    node_type=node_type,
                    properties=json.loads(properties),
                    first_seen=first_seen,
                    last_seen=last_seen,
                )
            for row in conn.execute("SELECT src, dst, relation, confidence, properties FROM edges"):
                src, dst, relation, confidence, properties = row
                self.graph.add_edge(
                    src,
                    dst,
                    src=src,
                    dst=dst,
                    relation=relation,
                    confidence=confidence,
                    properties=json.loads(properties),
                )

    def neighborhood(self, node_id: str, hops: int = 1) -> list[str]:
        if node_id not in self.graph:
            return []
        neighbors = nx.single_source_shortest_path_length(self.graph.to_undirected(), node_id, cutoff=hops)
        return [n for n in neighbors if n != node_id]

    def as_dict(self) -> dict[str, Any]:
        return {
            "nodes": [attrs for _, attrs in self.graph.nodes(data=True)],
            "edges": [attrs for _, _, attrs in self.graph.edges(data=True)],
        }
