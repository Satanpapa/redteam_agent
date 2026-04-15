"""
Red Team Agent v2.0 - Core Package

Autonomous penetration testing agent with local LLM, world model,
and adaptive decision-making capabilities.
"""

__version__ = "2.0.0"
__author__ = "Senior Offensive Security Architect"

from .models import (
    AgentState,
    EngagementConfig,
    TargetInfo,
    Vulnerability,
    ActionResult,
    DecisionMetrics,
    ToolResult,
    MemoryEntry,
    WorldModelNode,
    WorldModelEdge,
)

__all__ = [
    "AgentState",
    "EngagementConfig",
    "TargetInfo",
    "Vulnerability",
    "ActionResult",
    "DecisionMetrics",
    "ToolResult",
    "MemoryEntry",
    "WorldModelNode",
    "WorldModelEdge",
]
