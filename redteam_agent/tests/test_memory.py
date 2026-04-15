import pytest

pytest.importorskip("chromadb")

from rtcode.memory import MemoryManager


def test_memory_manager_roundtrip(tmp_path):
    mm = MemoryManager(
        tactical_db_path=str(tmp_path / "tactical.db"),
        vector_path=str(tmp_path / "chroma"),
        vector_collection="test",
    )
    mm.remember_fact("host1", "host", {"ip": "10.0.0.10"})
    assert mm.tactical.get("host1") == {"ip": "10.0.0.10"}

    doc_id = mm.remember_context("ssh open on 10.0.0.10", {"source": "test"})
    assert doc_id
    result = mm.recall("ssh", top_k=1)
    assert "semantic" in result
