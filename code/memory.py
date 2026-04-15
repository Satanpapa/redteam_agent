"""Two-layer memory: Vector memory + tactical SQLite memory."""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import chromadb

logger = logging.getLogger(__name__)


@dataclass
class MemoryConfig:
    persist_dir: str
    collection_name: str
    tactical_db_path: str


class MemorySystem:
    def __init__(self, config: MemoryConfig):
        self.config = config
        Path(config.persist_dir).mkdir(parents=True, exist_ok=True)
        Path(config.tactical_db_path).parent.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=config.persist_dir)
        self.collection = self.client.get_or_create_collection(name=config.collection_name)
        self._init_tactical_db()

    def _init_tactical_db(self) -> None:
        with sqlite3.connect(self.config.tactical_db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tactical_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    memory_key TEXT,
                    payload TEXT,
                    tags TEXT
                )
                """
            )

    def remember_vector(self, item_id: str, text: str, metadata: dict[str, Any] | None = None) -> None:
        self.collection.upsert(
            ids=[item_id],
            documents=[text],
            metadatas=[metadata or {}],
        )

    def recall_vector(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        result = self.collection.query(query_texts=[query], n_results=top_k)
        ids = result.get("ids", [[]])[0]
        docs = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        return [{"id": i, "document": d, "metadata": m} for i, d, m in zip(ids, docs, metadatas)]

    def remember_tactical(self, key: str, payload: dict[str, Any], tags: list[str] | None = None) -> None:
        with sqlite3.connect(self.config.tactical_db_path) as conn:
            conn.execute(
                "INSERT INTO tactical_memory (timestamp, memory_key, payload, tags) VALUES (?, ?, ?, ?)",
                (
                    datetime.utcnow().isoformat(),
                    key,
                    json.dumps(payload),
                    json.dumps(tags or []),
                ),
            )

    def recall_tactical(self, key: str, limit: int = 10) -> list[dict[str, Any]]:
        with sqlite3.connect(self.config.tactical_db_path) as conn:
            rows = conn.execute(
                "SELECT timestamp, memory_key, payload, tags FROM tactical_memory WHERE memory_key=? ORDER BY id DESC LIMIT ?",
                (key, limit),
            ).fetchall()
        return [
            {
                "timestamp": row[0],
                "key": row[1],
                "payload": json.loads(row[2]),
                "tags": json.loads(row[3]),
            }
            for row in rows
        ]
