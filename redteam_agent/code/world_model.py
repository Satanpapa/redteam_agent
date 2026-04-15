"""
World Model for Red Team Agent v2.0

Implements a persistent graph-based world model using NetworkX and SQLite
for tracking targets, vulnerabilities, attack paths, and relationships
during penetration testing engagements.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import uuid4

import networkx as nx

from .models import EdgeType, NodeType, TargetInfo, Vulnerability, WorldModelEdge, WorldModelNode

logger = logging.getLogger(__name__)


class WorldModel:
    """
    Persistent graph-based world model for red team operations.
    
    Features:
    - NetworkX graph for in-memory operations
    - SQLite persistence for long-term storage
    - Automatic checkpointing
    - Query capabilities for attack path analysis
    """
    
    def __init__(self, db_path: str = "./data/world_model.db"):
        """
        Initialize the world model.
        
        Args:
            db_path: Path to SQLite database for persistence
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # In-memory graph
        self.graph = nx.MultiDiGraph()
        
        # Node and edge caches
        self._node_cache: Dict[str, WorldModelNode] = {}
        self._edge_cache: Dict[str, WorldModelEdge] = {}
        
        # Initialize database
        self._init_database()
        
        # Load existing graph from database
        self._load_from_database()
        
        logger.info(f"WorldModel initialized with database: {db_path}")
    
    def _init_database(self) -> None:
        """Initialize SQLite database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY,
                node_type TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                properties TEXT,
                metadata TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS edges (
                id TEXT PRIMARY KEY,
                source_node_id TEXT NOT NULL,
                target_node_id TEXT NOT NULL,
                edge_type TEXT NOT NULL,
                properties TEXT,
                created_at TIMESTAMP,
                FOREIGN KEY (source_node_id) REFERENCES nodes(id),
                FOREIGN KEY (target_node_id) REFERENCES nodes(id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                node_count INTEGER,
                edge_count INTEGER,
                description TEXT
            )
        """)
        
        # Create indexes for faster queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(node_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(edge_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_node_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_node_id)")
        
        conn.commit()
        conn.close()
    
    def _load_from_database(self) -> None:
        """Load graph from SQLite database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Load nodes
        cursor.execute("SELECT * FROM nodes")
        for row in cursor.fetchall():
            node = WorldModelNode(
                id=row[0],
                node_type=NodeType(row[1]),
                name=row[2],
                description=row[3],
                properties=json.loads(row[4]) if row[4] else {},
                metadata=json.loads(row[5]) if row[5] else {},
                created_at=datetime.fromisoformat(row[6]) if row[6] else datetime.utcnow(),
                updated_at=datetime.fromisoformat(row[7]) if row[7] else datetime.utcnow(),
            )
            self._node_cache[node.id] = node
            self.graph.add_node(node.id, **node.model_dump())
        
        # Load edges
        cursor.execute("SELECT * FROM edges")
        for row in cursor.fetchall():
            edge = WorldModelEdge(
                id=row[0],
                source_node_id=row[1],
                target_node_id=row[2],
                edge_type=EdgeType(row[3]),
                properties=json.loads(row[4]) if row[4] else {},
                created_at=datetime.fromisoformat(row[5]) if row[5] else datetime.utcnow(),
            )
            self._edge_cache[edge.id] = edge
            self.graph.add_edge(
                edge.source_node_id,
                edge.target_node_id,
                key=edge.id,
                **edge.model_dump()
            )
        
        conn.close()
        logger.info(f"Loaded {self.graph.number_of_nodes()} nodes and "
                   f"{self.graph.number_of_edges()} edges from database")
    
    def _save_to_database(self) -> None:
        """Save current graph state to SQLite database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Clear existing data
        cursor.execute("DELETE FROM edges")
        cursor.execute("DELETE FROM nodes")
        
        # Save nodes
        for node_id, data in self.graph.nodes(data=True):
            if node_id in self._node_cache:
                node = self._node_cache[node_id]
            else:
                node = WorldModelNode(**data)
                self._node_cache[node_id] = node
            
            cursor.execute(
                """INSERT INTO nodes 
                (id, node_type, name, description, properties, metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    node.id,
                    node.node_type.value if hasattr(node.node_type, 'value') else node.node_type,
                    node.name,
                    node.description,
                    json.dumps(node.properties),
                    json.dumps(node.metadata),
                    node.created_at.isoformat(),
                    node.updated_at.isoformat(),
                )
            )
        
        # Save edges
        for u, v, key, data in self.graph.edges(keys=True, data=True):
            if key in self._edge_cache:
                edge = self._edge_cache[key]
            else:
                edge = WorldModelEdge(
                    id=key,
                    source_node_id=u,
                    target_node_id=v,
                    edge_type=data.get('edge_type', EdgeType.CONNECTED_TO),
                    properties=data.get('properties', {}),
                )
                self._edge_cache[key] = edge
            
            cursor.execute(
                """INSERT INTO edges 
                (id, source_node_id, target_node_id, edge_type, properties, created_at)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    edge.id,
                    edge.source_node_id,
                    edge.target_node_id,
                    edge.edge_type.value if hasattr(edge.edge_type, 'value') else edge.edge_type,
                    json.dumps(edge.properties),
                    edge.created_at.isoformat(),
                )
            )
        
        # Record checkpoint
        cursor.execute(
            "INSERT INTO checkpoints (node_count, edge_count) VALUES (?, ?)",
            (self.graph.number_of_nodes(), self.graph.number_of_edges())
        )
        
        conn.commit()
        conn.close()
    
    def add_node(
        self,
        node_type: NodeType,
        name: str,
        description: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Add a node to the world model.
        
        Args:
            node_type: Type of the node
            name: Node name
            description: Optional description
            properties: Node properties
            metadata: Additional metadata
            
        Returns:
            Node ID
        """
        node_id = str(uuid4())
        node = WorldModelNode(
            id=node_id,
            node_type=node_type,
            name=name,
            description=description,
            properties=properties or {},
            metadata=metadata or {},
        )
        
        self._node_cache[node_id] = node
        self.graph.add_node(node_id, **node.model_dump())
        
        logger.debug(f"Added node: {node_type}.{name} ({node_id})")
        return node_id
    
    def add_edge(
        self,
        source_node_id: str,
        target_node_id: str,
        edge_type: EdgeType,
        properties: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Add an edge between two nodes.
        
        Args:
            source_node_id: Source node ID
            target_node_id: Target node ID
            edge_type: Type of relationship
            properties: Edge properties
            
        Returns:
            Edge ID
        """
        edge_id = str(uuid4())
        edge = WorldModelEdge(
            id=edge_id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            edge_type=edge_type,
            properties=properties or {},
        )
        
        self._edge_cache[edge_id] = edge
        self.graph.add_edge(
            source_node_id,
            target_node_id,
            key=edge_id,
            **edge.model_dump()
        )
        
        logger.debug(f"Added edge: {source_node_id} -> {target_node_id} ({edge_type})")
        return edge_id
    
    def add_target(self, target: TargetInfo) -> str:
        """
        Add a target to the world model.
        
        Args:
            target: TargetInfo object
            
        Returns:
            Node ID of the target
        """
        node_id = self.add_node(
            node_type=NodeType.TARGET,
            name=target.address,
            description=f"Target: {target.hostname or target.address}",
            properties={
                "address": target.address,
                "port": target.port,
                "protocol": target.protocol,
                "os": target.os,
                "hostname": target.hostname,
            },
            metadata={"target_id": target.id},
        )
        
        # Add services as child nodes
        for service in target.services:
            service_node_id = self.add_node(
                node_type=NodeType.SERVICE,
                name=f"{service.service_name or 'unknown'}:{service.port}",
                description=f"Service on port {service.port}",
                properties=service.model_dump(),
            )
            self.add_edge(
                node_id,
                service_node_id,
                EdgeType.HOSTS,
                {"port": service.port}
            )
            
            # Add vulnerabilities if present
            for vuln in target.vulnerabilities:
                vuln_node_id = self._add_vulnerability(vuln)
                self.add_edge(
                    service_node_id,
                    vuln_node_id,
                    EdgeType.HAS_VULNERABILITY,
                )
        
        return node_id
    
    def _add_vulnerability(self, vuln: Vulnerability) -> str:
        """Add a vulnerability node."""
        return self.add_node(
            node_type=NodeType.VULNERABILITY,
            name=vuln.cve_id or vuln.name,
            description=vuln.description,
            properties={
                "cve_id": vuln.cve_id,
                "severity": vuln.severity.value,
                "cvss_score": vuln.cvss_score,
                "exploit_available": vuln.exploit_available,
            },
            metadata={"vuln_id": vuln.id},
        )
    
    def find_attack_paths(
        self,
        source_node_id: Optional[str] = None,
        target_node_id: Optional[str] = None,
        max_depth: int = 5,
    ) -> List[List[str]]:
        """
        Find attack paths in the world model.
        
        Args:
            source_node_id: Starting node (optional)
            target_node_id: Target node (optional)
            max_depth: Maximum path length
            
        Returns:
            List of paths (each path is a list of node IDs)
        """
        paths = []
        
        if source_node_id and target_node_id:
            # Find all simple paths between specific nodes
            try:
                for path in nx.all_simple_paths(
                    self.graph,
                    source=source_node_id,
                    target=target_node_id,
                    cutoff=max_depth,
                ):
                    paths.append(path)
            except nx.NetworkXNoPath:
                pass
        else:
            # Find all paths from TARGET nodes to VULNERABILITY nodes
            target_nodes = [
                n for n, d in self.graph.nodes(data=True)
                if d.get('node_type') == NodeType.TARGET
            ]
            vuln_nodes = [
                n for n, d in self.graph.nodes(data=True)
                if d.get('node_type') == NodeType.VULNERABILITY
            ]
            
            for source in target_nodes:
                for target in vuln_nodes:
                    try:
                        for path in nx.all_simple_paths(
                            self.graph,
                            source=source,
                            target=target,
                            cutoff=max_depth,
                        ):
                            paths.append(path)
                    except nx.NetworkXNoPath:
                        pass
        
        return paths
    
    def get_neighbors(
        self,
        node_id: str,
        edge_type: Optional[EdgeType] = None,
        direction: str = "both",
    ) -> List[str]:
        """
        Get neighboring nodes.
        
        Args:
            node_id: Node ID
            edge_type: Filter by edge type (optional)
            direction: 'incoming', 'outgoing', or 'both'
            
        Returns:
            List of neighbor node IDs
        """
        neighbors = set()
        
        if direction in ["outgoing", "both"]:
            for _, target, key, data in self.graph.out_edges(node_id, keys=True, data=True):
                if edge_type is None or data.get('edge_type') == edge_type:
                    neighbors.add(target)
        
        if direction in ["incoming", "both"]:
            for source, _, key, data in self.graph.in_edges(node_id, keys=True, data=True):
                if edge_type is None or data.get('edge_type') == edge_type:
                    neighbors.add(source)
        
        return list(neighbors)
    
    def query_nodes(
        self,
        node_type: Optional[NodeType] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[WorldModelNode]:
        """
        Query nodes by type and properties.
        
        Args:
            node_type: Filter by node type
            filters: Property filters
            
        Returns:
            List of matching nodes
        """
        results = []
        
        for node_id, data in self.graph.nodes(data=True):
            # Filter by type
            if node_type and data.get('node_type') != node_type:
                continue
            
            # Apply property filters
            if filters:
                match = True
                properties = data.get('properties', {})
                for key, value in filters.items():
                    if properties.get(key) != value:
                        match = False
                        break
                if not match:
                    continue
            
            # Get cached node or create from data
            if node_id in self._node_cache:
                node = self._node_cache[node_id]
            else:
                node = WorldModelNode(**data)
                self._node_cache[node_id] = node
            
            results.append(node)
        
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get world model statistics."""
        node_types = {}
        edge_types = {}
        
        for _, data in self.graph.nodes(data=True):
            nt = data.get('node_type', 'unknown')
            node_types[nt] = node_types.get(nt, 0) + 1
        
        for _, _, data in self.graph.edges(data=True):
            et = data.get('edge_type', 'unknown')
            edge_types[et] = edge_types.get(et, 0) + 1
        
        return {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "node_types": node_types,
            "edge_types": edge_types,
            "density": nx.density(self.graph),
            "connected_components": nx.number_weakly_connected_components(self.graph)
            if self.graph.number_of_nodes() > 0 else 0,
        }
    
    def checkpoint(self, description: Optional[str] = None) -> None:
        """Create a checkpoint in the database."""
        self._save_to_database()
        logger.info(f"WorldModel checkpoint created: {description}")
    
    def export_graph(self, format: str = "json") -> str:
        """
        Export the graph to a string format.
        
        Args:
            format: Export format ('json' or 'graphml')
            
        Returns:
            Exported graph as string
        """
        if format == "json":
            data = nx.node_link_data(self.graph)
            return json.dumps(data, indent=2, default=str)
        elif format == "graphml":
            return nx.write_graphml(self.graph, None)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def clear(self) -> None:
        """Clear the world model."""
        self.graph.clear()
        self._node_cache.clear()
        self._edge_cache.clear()
        self._save_to_database()
        logger.info("WorldModel cleared")
