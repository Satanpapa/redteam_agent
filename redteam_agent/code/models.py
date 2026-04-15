"""
Pydantic models for Red Team Agent v2.0

Comprehensive data models for agent state, engagements, targets,
vulnerabilities, decisions, and memory management.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class RiskLevel(str, Enum):
    """Risk classification levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ActionStatus(str, Enum):
    """Status of an executed action."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"


class NodeType(str, Enum):
    """Types of nodes in the world model graph."""
    TARGET = "target"
    HOST = "host"
    SERVICE = "service"
    VULNERABILITY = "vulnerability"
    CREDENTIAL = "credential"
    FILE = "file"
    NETWORK = "network"
    ACTION = "action"
    FINDING = "finding"


class EdgeType(str, Enum):
    """Types of edges in the world model graph."""
    HOSTS = "hosts"
    RUNS_ON = "runs_on"
    HAS_VULNERABILITY = "has_vulnerability"
    EXPLOITS = "exploits"
    LEADS_TO = "leads_to"
    CONNECTED_TO = "connected_to"
    CONTAINS = "contains"
    ACCESSED_VIA = "accessed_via"
    DEPENDS_ON = "depends_on"


class EngagementScope(str, Enum):
    """Scope of penetration testing engagement."""
    INTERNAL = "internal"
    EXTERNAL = "external"
    HYBRID = "hybrid"
    ISOLATED = "isolated"


class ToolType(str, Enum):
    """Categories of security tools."""
    RECONNAISSANCE = "reconnaissance"
    SCANNING = "scanning"
    ENUMERATION = "enumeration"
    EXPLOITATION = "exploitation"
    POST_EXPLOITATION = "post_exploitation"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    LATERAL_MOVEMENT = "lateral_movement"
    CREDENTIAL_ACCESS = "credential_access"
    DATA_EXFILTRATION = "data_exfiltration"
    FORENSICS = "forensics"


# ============================================================================
# Core Models
# ============================================================================

class TargetInfo(BaseModel):
    """Information about a target system."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    address: str = Field(..., description="IP address or hostname")
    port: Optional[int] = Field(None, ge=1, le=65535)
    protocol: Literal["tcp", "udp", "http", "https", "ssh", "ftp", "smb"] = "tcp"
    os: Optional[str] = None
    mac_address: Optional[str] = None
    hostname: Optional[str] = None
    services: List[ServiceInfo] = Field(default_factory=list)
    vulnerabilities: List[Vulnerability] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_schema_extra = {
            "example": {
                "address": "192.168.1.100",
                "port": 445,
                "protocol": "smb",
                "os": "Windows Server 2019",
                "hostname": "DC01",
            }
        }


class ServiceInfo(BaseModel):
    """Information about a network service."""
    
    port: int = Field(..., ge=1, le=65535)
    protocol: str = "tcp"
    state: Literal["open", "closed", "filtered"] = "open"
    service_name: Optional[str] = None
    product: Optional[str] = None
    version: Optional[str] = None
    extra_info: Optional[str] = None
    banner: Optional[str] = None
    scripts: List[Dict[str, Any]] = Field(default_factory=list)


class Vulnerability(BaseModel):
    """Vulnerability information with CVE support."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    cve_id: Optional[str] = Field(None, pattern=r"^CVE-\d{4}-\d+$")
    name: str
    description: str
    severity: RiskLevel = RiskLevel.MEDIUM
    cvss_score: Optional[float] = Field(None, ge=0.0, le=10.0)
    cvss_vector: Optional[str] = None
    affected_service: Optional[str] = None
    affected_version: Optional[str] = None
    exploit_available: bool = False
    exploit_maturity: Literal["unproven", "proof-of-concept", "functional", "high"] = "unproven"
    patch_available: bool = False
    references: List[str] = Field(default_factory=list)
    discovered_at: datetime = Field(default_factory=datetime.utcnow)
    verified: bool = False
    
    @field_validator("cvss_score")
    @classmethod
    def validate_cvss(cls, v: Optional[float]) -> Optional[float]:
        if v is not None:
            return round(v, 1)
        return v


class ActionResult(BaseModel):
    """Result of an executed action/tool."""
    
    action_id: str = Field(default_factory=lambda: str(uuid4()))
    action_name: str
    tool_name: str
    status: ActionStatus = ActionStatus.PENDING
    input_params: Dict[str, Any] = Field(default_factory=dict)
    output: Optional[str] = None
    error_message: Optional[str] = None
    normalized_data: Dict[str, Any] = Field(default_factory=dict)
    enriched_data: Dict[str, Any] = Field(default_factory=dict)
    execution_time_ms: Optional[float] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    risk_level: RiskLevel = RiskLevel.LOW
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    
    @property
    def success(self) -> bool:
        return self.status == ActionStatus.SUCCESS
    
    @property
    def duration_seconds(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class DecisionMetrics(BaseModel):
    """Metrics for decision evaluation."""
    
    success_probability: float = Field(0.5, ge=0.0, le=1.0)
    impact: float = Field(0.5, ge=0.0, le=1.0)
    stealth: float = Field(0.5, ge=0.0, le=1.0)
    speed: float = Field(0.5, ge=0.0, le=1.0)
    resource_cost: float = Field(0.5, ge=0.0, le=1.0)
    risk: float = Field(0.5, ge=0.0, le=1.0)
    
    # Monte Carlo simulation results
    mc_mean: Optional[float] = None
    mc_std: Optional[float] = None
    mc_confidence_interval: Optional[tuple[float, float]] = None
    
    # Computed score
    weighted_score: float = Field(0.0, ge=0.0, le=1.0)
    pareto_optimal: bool = False
    
    def compute_weighted_score(self, weights: Dict[str, float]) -> float:
        """Compute weighted score from metrics."""
        total = 0.0
        weight_sum = 0.0
        
        for key, weight in weights.items():
            if hasattr(self, key):
                value = getattr(self, key)
                # Invert resource_cost and risk (lower is better)
                if key in ["resource_cost", "risk"]:
                    value = 1.0 - value
                total += value * weight
                weight_sum += weight
        
        self.weighted_score = round(total / weight_sum if weight_sum > 0 else 0.0, 4)
        return self.weighted_score


class ToolResult(BaseModel):
    """Standardized tool execution result."""
    
    tool_name: str
    command: str
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    raw_output: Optional[bytes] = None
    parsed_output: Dict[str, Any] = Field(default_factory=dict)
    execution_time_ms: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# World Model Models
# ============================================================================

class WorldModelNode(BaseModel):
    """Node in the world model graph."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    node_type: NodeType
    name: str
    description: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        use_enum_values = True


class WorldModelEdge(BaseModel):
    """Edge in the world model graph."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    source_node_id: str
    target_node_id: str
    edge_type: EdgeType
    properties: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        use_enum_values = True


# ============================================================================
# Memory Models
# ============================================================================

class MemoryEntry(BaseModel):
    """Entry in the memory system."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    entry_type: Literal["observation", "action", "finding", "decision", "lesson"]
    content: str
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    importance: float = Field(0.5, ge=0.0, le=1.0)
    recency: float = Field(1.0, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    accessed_at: Optional[datetime] = None
    access_count: int = 0
    
    @property
    def relevance_score(self) -> float:
        """Compute relevance score based on importance and recency."""
        return (self.importance * 0.7) + (self.recency * 0.3)


class TacticalMemoryRecord(BaseModel):
    """Record in tactical SQLite memory."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    action_sequence: List[str] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)
    outcome: Optional[str] = None
    success: bool = False
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# Agent State & Configuration
# ============================================================================

class EngagementConfig(BaseModel):
    """Configuration for a penetration testing engagement."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    scope: EngagementScope = EngagementScope.INTERNAL
    targets: List[TargetInfo] = Field(default_factory=list)
    allowed_tools: List[ToolType] = Field(default_factory=list)
    excluded_tools: List[str] = Field(default_factory=list)
    rules_of_engagement: Dict[str, Any] = Field(default_factory=dict)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    max_depth: int = 5
    timeout_hours: int = 24
    auto_report: bool = True
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Internal Network Assessment",
                "scope": "internal",
                "max_depth": 5,
                "timeout_hours": 24,
            }
        }


class AgentState(BaseModel):
    """Complete state of the Red Team Agent."""
    
    # Engagement info
    engagement_id: str = Field(default_factory=lambda: str(uuid4()))
    engagement_config: Optional[EngagementConfig] = None
    
    # Current context
    current_target: Optional[TargetInfo] = None
    current_phase: Literal[
        "initialization",
        "reconnaissance",
        "scanning",
        "enumeration",
        "exploitation",
        "post_exploitation",
        "reporting",
        "completed"
    ] = "initialization"
    
    # Execution state
    iteration_count: int = 0
    max_iterations: int = 100
    action_history: List[ActionResult] = Field(default_factory=list)
    pending_actions: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Knowledge base
    discovered_targets: List[TargetInfo] = Field(default_factory=list)
    vulnerabilities: List[Vulnerability] = Field(default_factory=list)
    credentials: List[Dict[str, str]] = Field(default_factory=list)
    
    # Decision context
    available_actions: List[Dict[str, Any]] = Field(default_factory=list)
    selected_action: Optional[Dict[str, Any]] = None
    decision_metrics: Optional[DecisionMetrics] = None
    
    # Learning state
    lessons_learned: List[str] = Field(default_factory=list)
    adapted_weights: Dict[str, float] = Field(default_factory=dict)
    
    # Status
    status: Literal["idle", "running", "paused", "error", "completed"] = "idle"
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    
    # Messages for LangGraph
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    
    def add_action_result(self, result: ActionResult) -> None:
        """Add an action result to history."""
        self.action_history.append(result)
        self.last_updated = datetime.utcnow()
        
        # Update vulnerabilities if found
        if result.normalized_data.get("vulnerabilities"):
            for vuln_data in result.normalized_data["vulnerabilities"]:
                vuln = Vulnerability(**vuln_data)
                if vuln not in self.vulnerabilities:
                    self.vulnerabilities.append(vuln)
        
        # Update discovered targets
        if result.normalized_data.get("targets"):
            for target_data in result.normalized_data["targets"]:
                target = TargetInfo(**target_data)
                if target not in self.discovered_targets:
                    self.discovered_targets.append(target)
    
    def can_continue(self) -> bool:
        """Check if agent can continue execution."""
        if self.status != "running":
            return False
        if self.iteration_count >= self.max_iterations:
            return False
        if self.error_message:
            return False
        return True
    
    def increment_iteration(self) -> None:
        """Increment iteration counter."""
        self.iteration_count += 1
        self.last_updated = datetime.utcnow()


# ============================================================================
# LLM Message Models
# ============================================================================

class LLMMessage(BaseModel):
    """Message for LLM communication."""
    
    role: Literal["system", "user", "assistant"]
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class LLMResponse(BaseModel):
    """Response from LLM."""
    
    content: str
    model: str
    usage: Dict[str, int] = Field(default_factory=dict)
    finish_reason: Optional[str] = None
    latency_ms: Optional[float] = None


# ============================================================================
# Docker Sandbox Models
# ============================================================================

class ContainerConfig(BaseModel):
    """Configuration for Docker container."""
    
    image: str = "kalilinux/kali-rolling:latest"
    name: Optional[str] = None
    network_mode: str = "bridge"
    volumes: List[Dict[str, Any]] = Field(default_factory=list)
    environment: Dict[str, str] = Field(default_factory=dict)
    command: Optional[List[str]] = None
    working_dir: Optional[str] = None
    user: Optional[str] = None
    
    # Resource limits
    cpu_count: Optional[float] = None
    memory_limit: Optional[str] = None
    pids_limit: Optional[int] = None
    
    # Security
    privileged: bool = False
    cap_add: List[str] = Field(default_factory=list)
    cap_drop: List[str] = Field(default_factory=list)


class SnapshotInfo(BaseModel):
    """Information about a container snapshot."""
    
    snapshot_id: str = Field(default_factory=lambda: str(uuid4()))
    container_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    description: Optional[str] = None
    size_bytes: Optional[int] = None
