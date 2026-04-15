"""
Memory System for Red Team Agent v2.0

Implements a two-level memory system:
- Vector Store (ChromaDB) for semantic search and long-term memory
- Tactical SQLite for short-term action sequences and context
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import chromadb
from chromadb.config import Settings

from .models import MemoryEntry, TacticalMemoryRecord

logger = logging.getLogger(__name__)


class VectorMemory:
    """
    Vector-based memory using ChromaDB for semantic search.
    
    Features:
    - Semantic similarity search
    - Importance-weighted retrieval
    - Recency decay
    - Persistent storage
    """
    
    def __init__(
        self,
        persist_directory: str = "./data/chroma",
        collection_name: str = "redteam_memory",
        embedding_dimensions: int = 768,
    ):
        """
        Initialize vector memory.
        
        Args:
            persist_directory: Directory for ChromaDB persistence
            collection_name: Name of the collection
            embedding_dimensions: Dimension of embeddings
        """
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB with persistent storage
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
            )
        )
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "Red Team Agent Memory"},
        )
        
        # In-memory cache for quick access
        self._cache: Dict[str, MemoryEntry] = {}
        
        logger.info(
            f"VectorMemory initialized: {persist_directory}/{collection_name}"
        )
    
    def add(
        self,
        content: str,
        entry_type: str = "observation",
        metadata: Optional[Dict[str, Any]] = None,
        importance: float = 0.5,
        embedding: Optional[List[float]] = None,
    ) -> str:
        """
        Add a memory entry.
        
        Args:
            content: Memory content text
            entry_type: Type of memory entry
            metadata: Additional metadata
            importance: Importance score (0-1)
            embedding: Pre-computed embedding (optional)
            
        Returns:
            Entry ID
        """
        entry_id = str(uuid4())
        
        # Generate embedding if not provided
        if embedding is None:
            embedding = self._generate_embedding(content)
        
        # Create memory entry
        entry = MemoryEntry(
            id=entry_id,
            entry_type=entry_type,  # type: ignore
            content=content,
            embedding=embedding,
            metadata=metadata or {},
            importance=importance,
        )
        
        # Add to ChromaDB
        self.collection.add(
            ids=[entry_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[{
                "entry_type": entry_type,
                "importance": importance,
                "created_at": entry.created_at.isoformat(),
                **(metadata or {}),
            }],
        )
        
        # Cache
        self._cache[entry_id] = entry
        
        logger.debug(f"Added memory entry: {entry_id} ({entry_type})")
        return entry_id
    
    def _generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text.
        
        Note: In production, use Ollama's nomic-embed-text model.
        This is a placeholder implementation.
        """
        # Placeholder: simple hash-based embedding
        # In production, call Ollama embedding API
        import hashlib
        
        # Create deterministic embedding based on text hash
        hash_bytes = hashlib.sha256(text.encode()).digest()
        
        # Convert to float vector (this is just a placeholder!)
        embedding = [
            (hash_bytes[i % len(hash_bytes)] / 255.0) * 2 - 1
            for i in range(768)
        ]
        
        return embedding
    
    def search(
        self,
        query: str,
        k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        min_importance: float = 0.0,
    ) -> List[MemoryEntry]:
        """
        Search for relevant memories.
        
        Args:
            query: Search query text
            k: Number of results to return
            filters: Metadata filters
            min_importance: Minimum importance threshold
            
        Returns:
            List of relevant memory entries
        """
        # Generate query embedding
        query_embedding = self._generate_embedding(query)
        
        # Build where filter
        where_filter = None
        if filters:
            where_filter = {"$and": []}
            for key, value in filters.items():
                where_filter["$and"].append({key: value})
        
        # Search
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )
        
        # Process results
        entries = []
        if results["ids"] and results["ids"][0]:
            for i, entry_id in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                
                # Apply importance filter
                if metadata.get("importance", 0) < min_importance:
                    continue
                
                entry = MemoryEntry(
                    id=entry_id,
                    entry_type=metadata.get("entry_type", "observation"),
                    content=results["documents"][0][i] if results["documents"] else "",
                    metadata={k: v for k, v in metadata.items() 
                             if k not in ["entry_type", "importance", "created_at"]},
                    importance=metadata.get("importance", 0.5),
                )
                
                # Update recency based on age
                age_days = (datetime.utcnow() - entry.created_at).days
                entry.recency = max(0.0, 1.0 - (age_days / 30))
                
                entries.append(entry)
        
        return entries
    
    def get_recent(
        self,
        k: int = 10,
        entry_type: Optional[str] = None,
    ) -> List[MemoryEntry]:
        """Get most recent memories."""
        filters = {}
        if entry_type:
            filters["entry_type"] = entry_type
        
        return self.search("", k=k, filters=filters)
    
    def delete(self, entry_id: str) -> bool:
        """Delete a memory entry."""
        try:
            self.collection.delete(ids=[entry_id])
            self._cache.pop(entry_id, None)
            logger.debug(f"Deleted memory entry: {entry_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete memory entry: {e}")
            return False
    
    def clear(self) -> None:
        """Clear all memories."""
        client = chromadb.PersistentClient(path=str(self.persist_directory))
        client.delete_collection(self.collection.name)
        self.collection = client.create_collection(
            name=self.collection.name,
            metadata={"description": "Red Team Agent Memory"},
        )
        self._cache.clear()
        logger.info("VectorMemory cleared")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get memory statistics."""
        return {
            "total_entries": self.collection.count(),
            "cache_size": len(self._cache),
        }


class TacticalMemory:
    """
    SQLite-based tactical memory for short-term context.
    
    Features:
    - Fast read/write for recent actions
    - Action sequence tracking
    - Context preservation
    - Automatic cleanup of old records
    """
    
    def __init__(
        self,
        db_path: str = "./data/tactical_memory.db",
        max_recent_actions: int = 100,
        retention_days: int = 30,
    ):
        """
        Initialize tactical memory.
        
        Args:
            db_path: Path to SQLite database
            max_recent_actions: Maximum recent actions to keep
            retention_days: Days to retain records
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.max_recent_actions = max_recent_actions
        self.retention_days = retention_days
        
        # Initialize database
        self._init_database()
        
        logger.info(f"TacticalMemory initialized: {db_path}")
    
    def _init_database(self) -> None:
        """Initialize SQLite database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS records (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                action_sequence TEXT,
                context TEXT,
                outcome TEXT,
                success INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_context (
                session_id TEXT PRIMARY KEY,
                current_target TEXT,
                current_phase TEXT,
                credentials TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session ON records(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON records(timestamp)")
        
        conn.commit()
        conn.close()
    
    def add_record(
        self,
        session_id: str,
        action_sequence: List[str],
        context: Dict[str, Any],
        outcome: Optional[str] = None,
        success: bool = False,
    ) -> str:
        """
        Add a tactical memory record.
        
        Args:
            session_id: Session identifier
            action_sequence: List of action names
            context: Context dictionary
            outcome: Outcome description
            success: Whether actions were successful
            
        Returns:
            Record ID
        """
        record_id = str(uuid4())
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            """INSERT INTO records 
            (id, session_id, action_sequence, context, outcome, success)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (
                record_id,
                session_id,
                json.dumps(action_sequence),
                json.dumps(context),
                outcome,
                1 if success else 0,
            )
        )
        
        conn.commit()
        conn.close()
        
        # Cleanup old records
        self._cleanup()
        
        logger.debug(f"Added tactical record: {record_id}")
        return record_id
    
    def get_session_records(
        self,
        session_id: str,
        limit: int = 50,
    ) -> List[TacticalMemoryRecord]:
        """
        Get records for a session.
        
        Args:
            session_id: Session identifier
            limit: Maximum number of records
            
        Returns:
            List of tactical memory records
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            """SELECT id, session_id, action_sequence, context, outcome, success, timestamp
            FROM records
            WHERE session_id = ?
            ORDER BY timestamp DESC
            LIMIT ?""",
            (session_id, limit),
        )
        
        records = []
        for row in cursor.fetchall():
            record = TacticalMemoryRecord(
                id=row[0],
                session_id=row[1],
                action_sequence=json.loads(row[2]) if row[2] else [],
                context=json.loads(row[3]) if row[3] else {},
                outcome=row[4],
                success=bool(row[5]),
                timestamp=datetime.fromisoformat(row[6]) if row[6] else datetime.utcnow(),
            )
            records.append(record)
        
        conn.close()
        return records
    
    def update_session_context(
        self,
        session_id: str,
        current_target: Optional[str] = None,
        current_phase: Optional[str] = None,
        credentials: Optional[List[Dict[str, str]]] = None,
    ) -> None:
        """Update session context."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            """INSERT OR REPLACE INTO session_context 
            (session_id, current_target, current_phase, credentials, last_updated)
            VALUES (?, ?, ?, ?, ?)""",
            (
                session_id,
                current_target,
                current_phase,
                json.dumps(credentials or []),
                datetime.utcnow().isoformat(),
            )
        )
        
        conn.commit()
        conn.close()
    
    def get_session_context(
        self,
        session_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get session context."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT current_target, current_phase, credentials FROM session_context WHERE session_id = ?",
            (session_id,),
        )
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "current_target": row[0],
                "current_phase": row[1],
                "credentials": json.loads(row[2]) if row[2] else [],
            }
        
        return None
    
    def _cleanup(self) -> None:
        """Clean up old records."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Delete old records
        cutoff = (datetime.utcnow() - timedelta(days=self.retention_days)).isoformat()
        cursor.execute("DELETE FROM records WHERE timestamp < ?", (cutoff,))
        
        # Keep only recent actions per session
        cursor.execute("""
            DELETE FROM records
            WHERE id NOT IN (
                SELECT id FROM (
                    SELECT id, ROW_NUMBER() OVER (PARTITION BY session_id ORDER BY timestamp DESC) as rn
                    FROM records
                ) WHERE rn <= ?
            )
        """, (self.max_recent_actions,))
        
        conn.commit()
        conn.close()
    
    def clear(self) -> None:
        """Clear all tactical memory."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM records")
        cursor.execute("DELETE FROM session_context")
        
        conn.commit()
        conn.close()
        
        logger.info("TacticalMemory cleared")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get tactical memory statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM records")
        record_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT session_id) FROM records")
        session_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "total_records": record_count,
            "total_sessions": session_count,
        }


class MemorySystem:
    """
    Unified memory system combining vector and tactical memory.
    
    Features:
    - Two-level memory architecture
    - Coordinated storage and retrieval
    - Importance-based prioritization
    """
    
    def __init__(
        self,
        vector_config: Optional[Dict[str, Any]] = None,
        tactical_config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize memory system.
        
        Args:
            vector_config: Configuration for vector memory
            tactical_config: Configuration for tactical memory
        """
        vector_config = vector_config or {
            "persist_directory": "./data/chroma",
            "collection_name": "redteam_memory",
        }
        
        tactical_config = tactical_config or {
            "db_path": "./data/tactical_memory.db",
        }
        
        self.vector_memory = VectorMemory(**vector_config)
        self.tactical_memory = TacticalMemory(**tactical_config)
        
        logger.info("MemorySystem initialized")
    
    def store(
        self,
        session_id: str,
        content: str,
        entry_type: str,
        action_sequence: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
        importance: float = 0.5,
    ) -> tuple[str, str]:
        """
        Store information in both memory systems.
        
        Args:
            session_id: Session identifier
            content: Content to store
            entry_type: Type of entry
            action_sequence: Optional action sequence
            context: Optional context
            importance: Importance score
            
        Returns:
            Tuple of (vector_entry_id, tactical_record_id)
        """
        # Store in vector memory
        vector_id = self.vector_memory.add(
            content=content,
            entry_type=entry_type,
            metadata={"session_id": session_id},
            importance=importance,
        )
        
        # Store in tactical memory
        tactical_id = ""
        if action_sequence:
            tactical_id = self.tactical_memory.add_record(
                session_id=session_id,
                action_sequence=action_sequence,
                context=context or {},
                outcome=content[:200] if content else None,
                success=entry_type != "error",
            )
        
        return vector_id, tactical_id
    
    def retrieve(
        self,
        query: str,
        session_id: Optional[str] = None,
        k: int = 5,
    ) -> List[MemoryEntry]:
        """
        Retrieve relevant memories.
        
        Args:
            query: Search query
            session_id: Optional session filter
            k: Number of results
            
        Returns:
            List of memory entries
        """
        filters = {}
        if session_id:
            filters["session_id"] = session_id
        
        return self.vector_memory.search(query, k=k, filters=filters)
    
    def get_context(self, session_id: str) -> Dict[str, Any]:
        """Get complete context for a session."""
        context = self.tactical_memory.get_session_context(session_id) or {}
        
        # Add recent memories
        recent = self.vector_memory.get_recent(k=10)
        context["recent_memories"] = [
            {"type": e.entry_type, "content": e.content}
            for e in recent
        ]
        
        return context
    
    def clear(self) -> None:
        """Clear all memory."""
        self.vector_memory.clear()
        self.tactical_memory.clear()
        logger.info("MemorySystem cleared")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get memory system statistics."""
        return {
            "vector_memory": self.vector_memory.get_statistics(),
            "tactical_memory": self.tactical_memory.get_statistics(),
        }
