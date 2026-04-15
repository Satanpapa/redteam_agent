"""Core typed models for the offline red team agent."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, HttpUrl


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class NodeType(str, Enum):
    HOST = "host"
    SERVICE = "service"
    VULNERABILITY = "vulnerability"
    CREDENTIAL = "credential"
    ARTIFACT = "artifact"


class ActionStatus(str, Enum):
    PLANNED = "planned"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class WorldNode(BaseModel):
    node_id: str = Field(default_factory=lambda: str(uuid4()))
    node_type: NodeType
    label: str
    properties: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=0.7, ge=0, le=1)
    first_seen: datetime = Field(default_factory=utc_now)
    last_seen: datetime = Field(default_factory=utc_now)


class WorldEdge(BaseModel):
    src_id: str
    dst_id: str
    relationship: str
    properties: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=0.7, ge=0, le=1)
    observed_at: datetime = Field(default_factory=utc_now)


class ToolExecutionRequest(BaseModel):
    tool_name: str
    command: str
    args: list[str] = Field(default_factory=list)
    timeout_seconds: int = Field(default=120, ge=1)
    requires_snapshot: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolExecutionResult(BaseModel):
    tool_name: str
    command: str
    status: ActionStatus
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    duration_seconds: float = 0.0
    normalized_findings: list[dict[str, Any]] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)


class AttackAction(BaseModel):
    action_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    objective: str
    rationale: str
    required_capability: str
    estimated_reward: float = Field(default=0.5, ge=0, le=1)
    estimated_risk: float = Field(default=0.5, ge=0, le=1)
    estimated_stealth: float = Field(default=0.5, ge=0, le=1)
    estimated_cost: float = Field(default=0.5, ge=0, le=1)
    status: ActionStatus = ActionStatus.PLANNED
    dependencies: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)


class DecisionScore(BaseModel):
    action_id: str
    utility_score: float
    variance_penalty: float
    pareto_efficient: bool
    weighted_breakdown: dict[str, float]


class TacticalMemoryRecord(BaseModel):
    key: str
    category: Literal["host", "service", "credential", "objective", "artifact", "misc"]
    value: dict[str, Any]
    ttl_seconds: int | None = None
    created_at: datetime = Field(default_factory=utc_now)


class VectorMemoryRecord(BaseModel):
    doc_id: str = Field(default_factory=lambda: str(uuid4()))
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlannerInput(BaseModel):
    objective: str
    scope: str
    constraints: list[str] = Field(default_factory=list)
    target: str | None = None


class PlannerOutput(BaseModel):
    reasoning: str
    actions: list[AttackAction]
    generated_at: datetime = Field(default_factory=utc_now)


class AnalyzerOutput(BaseModel):
    summary: str
    success_probability: float = Field(ge=0, le=1)
    lessons: list[str] = Field(default_factory=list)
    extracted_nodes: list[WorldNode] = Field(default_factory=list)
    extracted_edges: list[WorldEdge] = Field(default_factory=list)


class LearningUpdate(BaseModel):
    updated_weights: dict[str, float]
    confidence_delta: float = 0.0
    notes: list[str] = Field(default_factory=list)


class AgentState(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    objective: str
    scope: str
    iteration: int = 0
    max_iterations: int = 12
    current_plan: list[AttackAction] = Field(default_factory=list)
    selected_action: AttackAction | None = None
    last_result: ToolExecutionResult | None = None
    analysis: AnalyzerOutput | None = None
    learning: LearningUpdate | None = None
    world_delta_nodes: list[WorldNode] = Field(default_factory=list)
    world_delta_edges: list[WorldEdge] = Field(default_factory=list)
    tactical_notes: list[str] = Field(default_factory=list)
    halt: bool = False


class ServiceFingerprint(BaseModel):
    host: str
    port: int
    service: str
    product: str | None = None
    version: str | None = None
    cpe: str | None = None


class CVEResult(BaseModel):
    cve_id: str
    cvss: float | None = None
    summary: str
    exploit_available: bool = False
    references: list[HttpUrl] | list[str] = Field(default_factory=list)
    affected_cpes: list[str] = Field(default_factory=list)


class ReportModel(BaseModel):
    run_id: str
    objective: str
    created_at: datetime = Field(default_factory=utc_now)
    key_findings: list[str] = Field(default_factory=list)
    actions_executed: list[AttackAction] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    risk: RiskLevel = RiskLevel.MEDIUM
