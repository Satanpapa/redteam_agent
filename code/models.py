"""Core data models for the autonomous red-team agent."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ActionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ActionCandidate(BaseModel):
    id: str
    name: str
    description: str
    command: str
    technique: str = Field(description="MITRE ATT&CK technique id")
    risk: RiskLevel = RiskLevel.MEDIUM
    estimated_seconds: int = 60
    success_probability: float = Field(default=0.5, ge=0.0, le=1.0)
    stealth_score: float = Field(default=0.5, ge=0.0, le=1.0)
    impact_score: float = Field(default=0.5, ge=0.0, le=1.0)
    reversibility_score: float = Field(default=0.7, ge=0.0, le=1.0)
    evidence_value_score: float = Field(default=0.5, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ActionResult(BaseModel):
    action_id: str
    status: ActionStatus
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: datetime = Field(default_factory=datetime.utcnow)
    artifacts: list[str] = Field(default_factory=list)
    normalized: dict[str, Any] = Field(default_factory=dict)


class DecisionOutcome(BaseModel):
    selected_action: ActionCandidate
    pareto_frontier: list[ActionCandidate]
    scores: dict[str, float]
    rationale: str


class Finding(BaseModel):
    id: str
    title: str
    severity: RiskLevel
    host: str
    port: int | None = None
    cve: str | None = None
    description: str
    evidence: list[str] = Field(default_factory=list)


class TacticalMemoryItem(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    key: str
    value: dict[str, Any]
    tags: list[str] = Field(default_factory=list)


class AgentState(BaseModel):
    run_id: str
    objective: str
    current_phase: str = "planning"
    history: list[ActionResult] = Field(default_factory=list)
    candidates: list[ActionCandidate] = Field(default_factory=list)
    selected_action: ActionCandidate | None = None
    last_result: ActionResult | None = None
    findings: list[Finding] = Field(default_factory=list)
    insights: list[str] = Field(default_factory=list)
    halted: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("objective")
    @classmethod
    def non_empty_objective(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("objective must not be empty")
        return value
