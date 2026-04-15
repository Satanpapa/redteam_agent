import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1] / "code"))

from memory import MemoryConfig, MemorySystem


def test_tactical_memory_roundtrip(tmp_path):
    mem = MemorySystem(MemoryConfig(str(tmp_path / "chroma"), "test", str(tmp_path / "t.db")))
    mem.remember_tactical("k", {"x": 1}, ["tag"])
    rows = mem.recall_tactical("k")
    assert rows[0]["payload"]["x"] == 1
