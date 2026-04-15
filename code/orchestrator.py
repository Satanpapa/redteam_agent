"""LangGraph orchestrator implementing closed-loop autonomous cycle."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from .decision_engine import DecisionEngine
from .memory import MemorySystem
from .models import ActionCandidate, AnalysisResult, LearnedSignal, PlannerState, RiskLevel, ToolCategory, WorldNode, NodeType
from .tool_layer import ToolLayer
from .world_model import WorldModel
from .llm_client import LLMClient

logger = logging.getLogger(__name__)


class GraphState(TypedDict):
    state: PlannerState


class RedTeamOrchestrator:
    def __init__(
        self,
        llm: LLMClient,
        decision_engine: DecisionEngine,
        tools: ToolLayer,
        memory: MemorySystem,
        world: WorldModel,
        max_cycles: int = 8,
    ) -> None:
        self.llm = llm
        self.decision_engine = decision_engine
        self.tools = tools
        self.memory = memory
        self.world = world
        self.max_cycles = max_cycles
        self.graph = self._build_graph()

    def _planner(self, payload: GraphState) -> GraphState:
        st = payload["state"]
        recent = self.memory.recent_events(limit=5)
        prompt = (
            "Generate 3 concise offensive actions as JSON list with id,title,command,rationale,"
            "expected_outcome,base_scores(stealth,impact,speed,confidence 0..1)."
            f"Objective: {st.objective}. Target: {st.target}. Recent: {json.dumps(recent)}"
        )
        try:
            raw = self.llm.complete(prompt)
            data = json.loads(raw)
            candidates = []
            for item in data[:3]:
                candidates.append(
                    ActionCandidate(
                        id=item["id"],
                        title=item["title"],
                        category=ToolCategory.RECON,
                        command=item["command"],
                        rationale=item["rationale"],
                        expected_outcome=item["expected_outcome"],
                        risk=RiskLevel.MEDIUM,
                        base_scores=item["base_scores"],
                    )
                )
        except Exception:
            candidates = [
                ActionCandidate(
                    id="nmap_service_scan",
                    title="Nmap service enumeration",
                    category=ToolCategory.RECON,
                    command=f"nmap -sV -Pn {st.target}",
                    rationale="Baseline enumeration",
                    expected_outcome="Open ports and services",
                    base_scores={"stealth": 0.4, "impact": 0.5, "speed": 0.8, "confidence": 0.8},
                )
            ]
        st.candidates = candidates
        st.history.append("planner")
        return {"state": st}

    def _decision(self, payload: GraphState) -> GraphState:
        st = payload["state"]
        st.decision = self.decision_engine.decide(st.candidates)
        st.selected_action = next(c for c in st.candidates if c.id == st.decision.action_id)
        st.history.append("decision")
        return {"state": st}

    def _executor(self, payload: GraphState) -> GraphState:
        st = payload["state"]
        assert st.selected_action
        st.execution = self.tools.run_local(st.selected_action.id, st.selected_action.command)
        self.memory.remember_event(datetime.now(timezone.utc).isoformat(), "executor", st.execution.model_dump(), st.selected_action.id)
        st.history.append("executor")
        return {"state": st}

    def _analyzer(self, payload: GraphState) -> GraphState:
        st = payload["state"]
        assert st.execution and st.selected_action
        parsed = self.tools.parse_nmap_summary(st.execution.stdout)
        discoveries = parsed.get("open_ports", [])
        for idx, item in enumerate(discoveries):
            node = WorldNode(node_id=f"{st.target}:{idx}", node_type=NodeType.SERVICE, properties=item)
            self.world.upsert_node(node)
        st.analysis = AnalysisResult(
            action_id=st.selected_action.id,
            discoveries=discoveries,
            confidence_delta=0.1 if discoveries else -0.05,
            notes="Analyzer parsed output and updated world model",
        )
        self.memory.remember_semantic(
            doc_id=f"analysis-{st.cycle}-{st.selected_action.id}",
            text=st.execution.stdout[:4000],
            metadata={"target": st.target, "action": st.selected_action.id},
        )
        st.history.append("analyzer")
        return {"state": st}

    def _learner(self, payload: GraphState) -> GraphState:
        st = payload["state"]
        assert st.analysis and st.decision
        reward = st.decision.weighted_score + st.analysis.confidence_delta
        signal = LearnedSignal(
            action_id=st.decision.action_id,
            reward=reward,
            weight_adjustments={
                "confidence": 0.05 if st.analysis.discoveries else -0.05,
                "speed": -0.02 if (st.execution and st.execution.exit_code != 0) else 0.01,
            },
            summary="Adaptive update from immediate tactical reward",
        )
        self.decision_engine.adapt_weights(signal)
        st.learning = signal
        st.cycle += 1
        st.halted = st.cycle >= self.max_cycles
        self.world.save()
        st.history.append("learner")
        return {"state": st}

    def _should_continue(self, payload: GraphState) -> str:
        return END if payload["state"].halted else "planner"

    def _build_graph(self):
        graph = StateGraph(GraphState)
        graph.add_node("planner", self._planner)
        graph.add_node("decision", self._decision)
        graph.add_node("executor", self._executor)
        graph.add_node("analyzer", self._analyzer)
        graph.add_node("learner", self._learner)
        graph.set_entry_point("planner")
        graph.add_edge("planner", "decision")
        graph.add_edge("decision", "executor")
        graph.add_edge("executor", "analyzer")
        graph.add_edge("analyzer", "learner")
        graph.add_conditional_edges("learner", self._should_continue)
        return graph.compile(checkpointer=MemorySaver())

    def run(self, objective: str, target: str, thread_id: str = "default") -> PlannerState:
        state = PlannerState(objective=objective, target=target)
        result = self.graph.invoke({"state": state}, config={"configurable": {"thread_id": thread_id}})
        return result["state"]
