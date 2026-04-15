import pytest

pytest.importorskip("pydantic")
pytest.importorskip("networkx")

from rtcode.models import NodeType, WorldEdge, WorldNode
from rtcode.world_model import WorldModel


def test_world_model_persistence(tmp_path):
    db = tmp_path / "world.db"
    wm = WorldModel(str(db))
    n1 = WorldNode(node_type=NodeType.HOST, label="10.0.0.1")
    n2 = WorldNode(node_type=NodeType.SERVICE, label="10.0.0.1:80")
    wm.upsert_node(n1)
    wm.upsert_node(n2)
    wm.upsert_edge(WorldEdge(src_id=n1.node_id, dst_id=n2.node_id, relationship="exposes"))

    wm2 = WorldModel(str(db))
    assert wm2.graph.number_of_nodes() == 2
    assert wm2.graph.number_of_edges() == 1
