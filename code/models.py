"""Core Pydantic domain models for Red Team Agent."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, IPvAnyAddress, field_validator


class NodeType(str, Enum):
    HOST = "host"
    SERVICE = "service"
    VULNERABILITY = "vulnerability"
    CREDENTIAL = "credential"
    ARTIFACT = "artifact"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ToolCategory(str, Enum):
    RECON = "recon"
    EXPLOIT = "exploit"
    POST = "post"
    LATERAL = "lateral"


class ActionCandidate(BaseModel):
    id: str
    title: str
    category: ToolCategory
    command: str
    rationale: str
    prerequisites: list[str] = Field(default_factory=list)
    expected_outcome: str
    risk: RiskLevel = RiskLevel.MEDIUM
    base_scores: dict[str, float] = Field(default_factory=dict)


class DecisionMetrics(BaseModel):
    stealth: float = Field(ge=0.0, le=1.0)
    impact: float = Field(ge=0.0, le=1.0)
    speed: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class DecisionResult(BaseModel):
    action_id: str
    weighted_score: float
    pareto_rank: int
    simulation_mean: float
    simulation_std: float
    explanation: str


class ExecutionResult(BaseModel):
    action_id: str
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    telemetry: dict[str, Any] = Field(default_factory=dict)


class AnalysisResult(BaseModel):
    action_id: str
    discoveries: list[dict[str, Any]] = Field(default_factory=list)
    confidence_delta: float = 0.0
    risk_delta: float = 0.0
    notes: str = ""


class LearnedSignal(BaseModel):
    action_id: str
    reward: float
    weight_adjustments: dict[str, float]
    summary: str


class WorldNode(BaseModel):
    node_id: str
    node_type: NodeType
    properties: dict[str, Any] = Field(default_factory=dict)
    first_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WorldEdge(BaseModel):
    src: str
    dst: str
    relation: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    properties: dict[str, Any] = Field(default_factory=dict)


class PlannerState(BaseModel):
    objective: str
    target: str
    cycle: int = 0
    candidates: list[ActionCandidate] = Field(default_factory=list)
    selected_action: ActionCandidate | None = None
    decision: DecisionResult | None = None
    execution: ExecutionResult | None = None
    analysis: AnalysisResult | None = None
    learning: LearnedSignal | None = None
    halted: bool = False
    history: list[str] = Field(default_factory=list)


class MsfRpcConfig(BaseModel):
    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 55553
    ssl: bool = False
    user: str = "msf"
    password: str = "msf"
    uri: str = "/api/"


class ScanTarget(BaseModel):
    target: str

    @field_validator("target")
    @classmethod
    def validate_target(cls, value: str) -> str:
        try:
            IPvAnyAddress(value)
            return value
        except Exception:
            if "/" in value:
                return value
            raise ValueError("target must be IP or CIDR")
