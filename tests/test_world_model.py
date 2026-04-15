import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1] / "code"))

from pathlib import Path

from world_model import WorldModel


def test_world_model_persistence(tmp_path: Path):
    wm = WorldModel(str(tmp_path / "wm.db"), str(tmp_path / "wm.graphml"))
    wm.add_node("h1", "host", ip="10.0.0.1")
    wm.add_node("smb", "service", port=445)
    wm.add_edge("h1", "smb", "exposes")
    wm.persist_graph()
    assert (tmp_path / "wm.graphml").exists()
