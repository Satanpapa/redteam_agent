"""Two-level memory: vector retrieval + tactical SQLite store."""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from pathlib import Path
from typing import Any

import chromadb
from chromadb.api.models.Collection import Collection

from .models import TacticalMemoryRecord, VectorMemoryRecord

logger = logging.getLogger(__name__)


class TacticalMemory:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tactical_memory (
                    key TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    value TEXT NOT NULL,
                    ttl_seconds INTEGER,
                    created_at TEXT NOT NULL
                )
                """
            )

    def put(self, record: TacticalMemoryRecord) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO tactical_memory (key, category, value, ttl_seconds, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    category=excluded.category,
                    value=excluded.value,
                    ttl_seconds=excluded.ttl_seconds,
                    created_at=excluded.created_at
                """,
                (record.key, record.category, json.dumps(record.value), record.ttl_seconds, record.created_at.isoformat()),
            )

    def get(self, key: str) -> dict[str, Any] | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT value FROM tactical_memory WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def query_category(self, category: str, limit: int = 25) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT key, value FROM tactical_memory WHERE category = ? ORDER BY created_at DESC LIMIT ?",
                (category, limit),
            ).fetchall()
        return [{"key": key, "value": json.loads(value)} for key, value in rows]


class VectorMemory:
    def __init__(self, path: str, collection_name: str) -> None:
        Path(path).mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=path)
        self.collection: Collection = self.client.get_or_create_collection(name=collection_name)

    def add(self, record: VectorMemoryRecord, embedding: list[float] | None = None) -> None:
        kwargs: dict[str, Any] = {
            "ids": [record.doc_id],
            "documents": [record.text],
            "metadatas": [record.metadata],
        }
        if embedding is not None:
            kwargs["embeddings"] = [embedding]
        self.collection.add(**kwargs)

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        result = self.collection.query(query_texts=[query], n_results=top_k)
        docs = result.get("documents", [[]])[0]
        metas = result.get("metadatas", [[]])[0]
        ids = result.get("ids", [[]])[0]
        distances = result.get("distances", [[]])[0] if result.get("distances") else [None] * len(docs)
        output = []
        for i, doc in enumerate(docs):
            output.append(
                {
                    "id": ids[i] if i < len(ids) else str(uuid.uuid4()),
                    "document": doc,
                    "metadata": metas[i] if i < len(metas) else {},
                    "distance": distances[i] if i < len(distances) else None,
                }
            )
        return output


class MemoryManager:
    def __init__(self, tactical_db_path: str, vector_path: str, vector_collection: str) -> None:
        self.tactical = TacticalMemory(tactical_db_path)
        self.vector = VectorMemory(vector_path, vector_collection)

    def remember_fact(self, key: str, category: str, fact: dict[str, Any]) -> None:
        record = TacticalMemoryRecord(key=key, category=category, value=fact)
        self.tactical.put(record)

    def remember_context(self, text: str, metadata: dict[str, Any]) -> str:
        record = VectorMemoryRecord(text=text, metadata=metadata)
        self.vector.add(record)
        return record.doc_id

    def recall(self, query: str, top_k: int = 5) -> dict[str, Any]:
        return {
            "semantic": self.vector.search(query, top_k=top_k),
            "hosts": self.tactical.query_category("host", limit=top_k),
            "services": self.tactical.query_category("service", limit=top_k),
            "credentials": self.tactical.query_category("credential", limit=top_k),
        }
