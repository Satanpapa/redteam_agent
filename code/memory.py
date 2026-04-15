"""Two-tier memory: Chroma vector memory + tactical SQLite."""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

import chromadb

logger = logging.getLogger(__name__)


class MemorySystem:
    def __init__(self, chroma_path: str, sqlite_path: str, collection_name: str = "redteam_experiences") -> None:
        Path(chroma_path).mkdir(parents=True, exist_ok=True)
        Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=chroma_path)
        self.collection = self.client.get_or_create_collection(collection_name)
        self.sqlite_path = sqlite_path
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.sqlite_path)

    def _init_schema(self) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tactical_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    action_id TEXT,
                    payload TEXT NOT NULL
                )
                """
            )

    def remember_event(self, ts: str, phase: str, payload: dict[str, Any], action_id: str | None = None) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO tactical_events (ts, phase, action_id, payload) VALUES (?, ?, ?, ?)",
                (ts, phase, action_id, json.dumps(payload)),
            )

    def recent_events(self, limit: int = 20) -> list[dict[str, Any]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT ts, phase, action_id, payload FROM tactical_events ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [
            {"ts": ts, "phase": phase, "action_id": action_id, "payload": json.loads(payload)}
            for ts, phase, action_id, payload in rows
        ]

    def remember_semantic(self, doc_id: str, text: str, metadata: dict[str, Any]) -> None:
        self.collection.upsert(ids=[doc_id], documents=[text], metadatas=[metadata])

    def recall_semantic(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        result = self.collection.query(query_texts=[query], n_results=top_k)
        docs = result.get("documents", [[]])[0]
        metas = result.get("metadatas", [[]])[0]
        ids = result.get("ids", [[]])[0]
        return [{"id": ids[i], "text": docs[i], "metadata": metas[i]} for i in range(len(ids))]
