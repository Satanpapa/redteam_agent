"""Tests for Memory System module."""

import pytest
from code.memory import VectorMemory, TacticalMemory, MemorySystem


class TestVectorMemory:
    """Test cases for VectorMemory."""

    def test_initialization(self, tmp_path):
        """Test vector memory initializes correctly."""
        vm = VectorMemory(persist_directory=str(tmp_path / "chroma"))
        assert vm.collection is not None

    def test_add_entry(self, tmp_path):
        """Test adding memory entries."""
        vm = VectorMemory(persist_directory=str(tmp_path / "chroma"))
        
        entry_id = vm.add(
            content="Test observation",
            entry_type="observation",
            importance=0.8,
        )
        
        assert entry_id is not None
        assert vm.collection.count() == 1

    def test_search(self, tmp_path):
        """Test searching memories."""
        vm = VectorMemory(persist_directory=str(tmp_path / "chroma"))
        
        vm.add(content="Network scan results", entry_type="finding")
        vm.add(content="Web vulnerability found", entry_type="vulnerability")
        
        results = vm.search("network", k=5)
        
        assert len(results) > 0

    def test_get_recent(self, tmp_path):
        """Test retrieving recent memories."""
        vm = VectorMemory(persist_directory=str(tmp_path / "chroma"))
        
        vm.add(content="First entry", entry_type="observation")
        vm.add(content="Second entry", entry_type="action")
        
        recent = vm.get_recent(k=5)
        
        assert len(recent) == 2


class TestTacticalMemory:
    """Test cases for TacticalMemory."""

    def test_initialization(self, tmp_path):
        """Test tactical memory initializes correctly."""
        tm = TacticalMemory(db_path=str(tmp_path / "tactical.db"))
        assert tm.db_path.exists()

    def test_add_record(self, tmp_path):
        """Test adding tactical records."""
        tm = TacticalMemory(db_path=str(tmp_path / "tactical.db"))
        
        record_id = tm.add_record(
            session_id="test-session",
            action_sequence=["scan", "exploit"],
            context={"target": "192.168.1.1"},
            success=True,
        )
        
        assert record_id is not None

    def test_get_session_records(self, tmp_path):
        """Test retrieving session records."""
        tm = TacticalMemory(db_path=str(tmp_path / "tactical.db"))
        
        tm.add_record("session1", ["action1"], {}, success=True)
        tm.add_record("session1", ["action2"], {}, success=False)
        
        records = tm.get_session_records("session1")
        
        assert len(records) == 2

    def test_update_session_context(self, tmp_path):
        """Test updating session context."""
        tm = TacticalMemory(db_path=str(tmp_path / "tactical.db"))
        
        tm.update_session_context(
            session_id="test",
            current_target="192.168.1.1",
            current_phase="exploitation",
        )
        
        context = tm.get_session_context("test")
        
        assert context is not None
        assert context["current_target"] == "192.168.1.1"


class TestMemorySystem:
    """Test cases for integrated MemorySystem."""

    def test_initialization(self, tmp_path):
        """Test memory system initializes correctly."""
        ms = MemorySystem(
            vector_config={"persist_directory": str(tmp_path / "chroma")},
            tactical_config={"db_path": str(tmp_path / "tactical.db")},
        )
        
        assert ms.vector_memory is not None
        assert ms.tactical_memory is not None

    def test_store(self, tmp_path):
        """Test storing in both memory systems."""
        ms = MemorySystem(
            vector_config={"persist_directory": str(tmp_path / "chroma")},
            tactical_config={"db_path": str(tmp_path / "tactical.db")},
        )
        
        vector_id, tactical_id = ms.store(
            session_id="test",
            content="Test content",
            entry_type="observation",
            action_sequence=["scan"],
        )
        
        assert vector_id is not None

    def test_retrieve(self, tmp_path):
        """Test retrieving memories."""
        ms = MemorySystem(
            vector_config={"persist_directory": str(tmp_path / "chroma")},
            tactical_config={"db_path": str(tmp_path / "tactical.db")},
        )
        
        ms.store("session1", "Important finding", "finding")
        
        results = ms.retrieve("finding", k=5)
        
        assert len(results) > 0

    def test_get_statistics(self, tmp_path):
        """Test getting memory statistics."""
        ms = MemorySystem(
            vector_config={"persist_directory": str(tmp_path / "chroma")},
            tactical_config={"db_path": str(tmp_path / "tactical.db")},
        )
        
        stats = ms.get_statistics()
        
        assert "vector_memory" in stats
        assert "tactical_memory" in stats
