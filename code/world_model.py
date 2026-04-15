"""World model using NetworkX and SQLite persistence."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

import networkx as nx

logger = logging.getLogger(__name__)


class WorldModel:
    def __init__(self, sqlite_path: str, graphml_path: str):
        self.sqlite_path = Path(sqlite_path)
        self.graphml_path = Path(graphml_path)
        self.graph = nx.MultiDiGraph()
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self.graphml_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS nodes (
                    id TEXT PRIMARY KEY,
                    type TEXT,
                    attributes TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS edges (
                    edge_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT,
                    target TEXT,
                    relation TEXT,
                    attributes TEXT
                )
                """
            )

    def add_node(self, node_id: str, node_type: str, **attributes: Any) -> None:
        self.graph.add_node(node_id, type=node_type, **attributes)
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO nodes (id, type, attributes) VALUES (?, ?, ?)",
                (node_id, node_type, json.dumps(attributes)),
            )

    def add_edge(self, source: str, target: str, relation: str, **attributes: Any) -> None:
        self.graph.add_edge(source, target, relation=relation, **attributes)
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute(
                "INSERT INTO edges (source, target, relation, attributes) VALUES (?, ?, ?, ?)",
                (source, target, relation, json.dumps(attributes)),
            )

    def neighbors(self, node_id: str) -> list[str]:
        return list(self.graph.neighbors(node_id))

    def persist_graph(self) -> None:
        nx.write_graphml(self.graph, self.graphml_path)
        logger.info("World model persisted to %s", self.graphml_path)

    def load_from_db(self) -> None:
        self.graph.clear()
        with sqlite3.connect(self.sqlite_path) as conn:
            node_rows = conn.execute("SELECT id, type, attributes FROM nodes").fetchall()
            edge_rows = conn.execute("SELECT source, target, relation, attributes FROM edges").fetchall()

        for node_id, node_type, attributes in node_rows:
            attrs = json.loads(attributes or "{}")
            self.graph.add_node(node_id, type=node_type, **attrs)
        for source, target, relation, attributes in edge_rows:
            attrs = json.loads(attributes or "{}")
            self.graph.add_edge(source, target, relation=relation, **attrs)
        logger.info("World model loaded from SQLite with %d nodes", self.graph.number_of_nodes())
