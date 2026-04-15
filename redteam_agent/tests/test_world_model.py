"""Tests for World Model module."""

import pytest
from code.world_model import WorldModel
from code.models import NodeType, EdgeType, TargetInfo


class TestWorldModel:
    """Test cases for WorldModel."""

    def test_initialization(self, tmp_path):
        """Test world model initializes correctly."""
        db_path = tmp_path / "test.db"
        wm = WorldModel(db_path=str(db_path))
        
        assert wm.graph is not None
        assert db_path.exists()

    def test_add_node(self, tmp_path):
        """Test adding nodes to the graph."""
        wm = WorldModel(db_path=str(tmp_path / "test.db"))
        
        node_id = wm.add_node(
            node_type=NodeType.TARGET,
            name="192.168.1.100",
            description="Test target",
        )
        
        assert node_id is not None
        assert wm.graph.has_node(node_id)

    def test_add_edge(self, tmp_path):
        """Test adding edges between nodes."""
        wm = WorldModel(db_path=str(tmp_path / "test.db"))
        
        node1 = wm.add_node(NodeType.TARGET, "target1")
        node2 = wm.add_node(NodeType.SERVICE, "service1")
        edge_id = wm.add_edge(node1, node2, EdgeType.HOSTS)
        
        assert edge_id is not None
        assert wm.graph.has_edge(node1, node2)

    def test_add_target(self, tmp_path):
        """Test adding a complete target with services."""
        wm = WorldModel(db_path=str(tmp_path / "test.db"))
        
        target = TargetInfo(
            address="192.168.1.100",
            hostname="testhost",
            os="Linux",
        )
        
        node_id = wm.add_target(target)
        
        assert node_id is not None
        stats = wm.get_statistics()
        assert stats["total_nodes"] >= 1

    def test_query_nodes(self, tmp_path):
        """Test querying nodes by type."""
        wm = WorldModel(db_path=str(tmp_path / "test.db"))
        
        wm.add_node(NodeType.TARGET, "target1")
        wm.add_node(NodeType.TARGET, "target2")
        wm.add_node(NodeType.SERVICE, "service1")
        
        targets = wm.query_nodes(node_type=NodeType.TARGET)
        
        assert len(targets) == 2

    def test_find_attack_paths(self, tmp_path):
        """Test attack path finding."""
        wm = WorldModel(db_path=str(tmp_path / "test.db"))
        
        target = wm.add_node(NodeType.TARGET, "target")
        service = wm.add_node(NodeType.SERVICE, "service")
        vuln = wm.add_node(NodeType.VULNERABILITY, "CVE-2021-1234")
        
        wm.add_edge(target, service, EdgeType.HOSTS)
        wm.add_edge(service, vuln, EdgeType.HAS_VULNERABILITY)
        
        paths = wm.find_attack_paths(target, vuln)
        
        assert len(paths) > 0

    def test_get_neighbors(self, tmp_path):
        """Test getting neighboring nodes."""
        wm = WorldModel(db_path=str(tmp_path / "test.db"))
        
        node1 = wm.add_node(NodeType.TARGET, "target")
        node2 = wm.add_node(NodeType.SERVICE, "service")
        wm.add_edge(node1, node2, EdgeType.HOSTS)
        
        neighbors = wm.get_neighbors(node1)
        
        assert node2 in neighbors

    def test_checkpoint(self, tmp_path):
        """Test checkpointing saves state."""
        db_path = tmp_path / "test.db"
        wm = WorldModel(db_path=str(db_path))
        
        wm.add_node(NodeType.TARGET, "target1")
        wm.checkpoint("Test checkpoint")
        
        # Verify data persists
        wm2 = WorldModel(db_path=str(db_path))
        assert wm2.graph.number_of_nodes() == 1

    def test_export_graph(self, tmp_path):
        """Test graph export functionality."""
        wm = WorldModel(db_path=str(tmp_path / "test.db"))
        
        wm.add_node(NodeType.TARGET, "target1")
        
        json_export = wm.export_graph(format="json")
        
        assert "nodes" in json_export
        assert "links" in json_export

    def test_clear(self, tmp_path):
        """Test clearing the world model."""
        wm = WorldModel(db_path=str(tmp_path / "test.db"))
        
        wm.add_node(NodeType.TARGET, "target1")
        wm.clear()
        
        assert wm.graph.number_of_nodes() == 0
