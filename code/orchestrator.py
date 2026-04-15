"""LangGraph orchestrator implementing closed-loop autonomous red-team workflow."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import yaml
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from decision_engine import DecisionConfig, DecisionEngine
from docker_sandbox import DockerSandboxManager, SandboxConfig
from llm_client import LLMConfig, OllamaClient
from memory import MemoryConfig, MemorySystem
from models import ActionCandidate, ActionResult, ActionStatus, AgentState, RiskLevel
from tool_layer import ToolLayer
from world_model import WorldModel

logger = logging.getLogger(__name__)


class RedTeamOrchestrator:
    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        dec_cfg = cfg["decision_engine"]
        self.decision_engine = DecisionEngine(
            DecisionConfig(
                monte_carlo_iterations=dec_cfg["monte_carlo_iterations"],
                learning_rate=dec_cfg["adaptive_learning_rate"],
                weights=dec_cfg["criteria_weights"],
            )
        )

        self.llm = OllamaClient(LLMConfig(**cfg["llm"]))
        self.world_model = WorldModel(**cfg["world_model"])
        self.memory = MemorySystem(
            MemoryConfig(
                persist_dir=cfg["memory"]["vector_store"]["persist_dir"],
                collection_name=cfg["memory"]["vector_store"]["collection"],
                tactical_db_path=cfg["memory"]["tactical_sqlite_path"],
            )
        )
        self.sandbox = DockerSandboxManager(SandboxConfig(**cfg["docker"]))
        self.tools = ToolLayer()
        self.graph = self._build_graph()

    def _planner_node(self, state: AgentState) -> AgentState:
        prompt = (
            f"Objective: {state.objective}\n"
            "Generate up to 4 next actions as JSON array with keys: id,name,description,command,technique,risk,"
            "estimated_seconds,success_probability,stealth_score,impact_score,reversibility_score,evidence_value_score"
        )
        llm_output = self.llm.plan(prompt)
        try:
            parsed = json.loads(llm_output)
            candidates = [ActionCandidate(**a) for a in parsed]
        except Exception:
            candidates = [
                ActionCandidate(
                    id="heuristic_nmap",
                    name="Stealth TCP scan",
                    description="Run targeted nmap scan",
                    command="nmap -sV -Pn 192.168.56.101 -oX /artifacts/nmap.xml",
                    technique="T1046",
                    risk=RiskLevel.LOW,
                    estimated_seconds=90,
                    success_probability=0.8,
                    stealth_score=0.7,
                    impact_score=0.5,
                )
            ]
        state.candidates = candidates
        state.current_phase = "decision"
        return state

    def _decision_node(self, state: AgentState) -> AgentState:
        outcome = self.decision_engine.select_action(state.candidates)
        state.selected_action = outcome.selected_action
        state.insights.append(outcome.rationale)
        state.current_phase = "execution"
        return state

    def _executor_node(self, state: AgentState) -> AgentState:
        if not state.selected_action:
            state.halted = True
            return state
        action = state.selected_action
        container = self.sandbox.create_container(name=f"rt-{uuid.uuid4().hex[:8]}")
        snapshot = self.sandbox.snapshot(container, f"pre-{action.id}")
        try:
            raw = self.sandbox.exec(container, action.command)
            status = ActionStatus.SUCCESS if raw["exit_code"] == 0 else ActionStatus.FAILED
            normalized = self.tools.normalize_tool_output("nmap", raw["stdout"])
            enriched = self.tools.enrich(normalized)
            result = ActionResult(
                action_id=action.id,
                status=status,
                stdout=raw["stdout"],
                stderr=raw["stderr"],
                exit_code=raw["exit_code"],
                normalized=enriched,
                artifacts=["/artifacts/nmap.xml"],
            )
            state.last_result = result
            state.history.append(result)
        except Exception as exc:
            self.sandbox.restore(snapshot, f"rt-restore-{uuid.uuid4().hex[:8]}")
            state.last_result = ActionResult(action_id=action.id, status=ActionStatus.FAILED, stderr=str(exc), exit_code=1)
            state.history.append(state.last_result)
        finally:
            self.sandbox.stop_remove(container)
        state.current_phase = "analysis"
        return state

    def _analyzer_node(self, state: AgentState) -> AgentState:
        if not state.last_result:
            state.halted = True
            return state
        prompt = f"Analyze action result and provide concise lessons: {state.last_result.model_dump_json()}"
        analysis = self.llm.analyze(prompt)
        state.insights.append(analysis)
        state.current_phase = "learning"
        return state

    def _learner_node(self, state: AgentState) -> AgentState:
        if state.selected_action and state.last_result:
            self.decision_engine.update_weights(state.selected_action, state.last_result)
            self.memory.remember_tactical(
                key="action_result",
                payload={"action": state.selected_action.model_dump(), "result": state.last_result.model_dump()},
                tags=[state.current_phase],
            )
            self.memory.remember_vector(
                item_id=f"{state.run_id}-{len(state.history)}",
                text="\n".join(state.insights[-2:]),
                metadata={"objective": state.objective},
            )
        self.world_model.persist_graph()
        state.current_phase = "planning"
        state.halted = len(state.history) >= 5
        return state

    def _route(self, state: AgentState) -> str:
        return END if state.halted else "planner"

    def _build_graph(self):
        builder = StateGraph(AgentState)
        builder.add_node("planner", self._planner_node)
        builder.add_node("decision", self._decision_node)
        builder.add_node("executor", self._executor_node)
        builder.add_node("analyzer", self._analyzer_node)
        builder.add_node("learner", self._learner_node)

        builder.add_edge(START, "planner")
        builder.add_edge("planner", "decision")
        builder.add_edge("decision", "executor")
        builder.add_edge("executor", "analyzer")
        builder.add_edge("analyzer", "learner")
        builder.add_conditional_edges("learner", self._route)

        return builder.compile(checkpointer=MemorySaver())

    def run(self, objective: str, thread_id: str | None = None) -> AgentState:
        init_state = AgentState(run_id=thread_id or uuid.uuid4().hex, objective=objective)
        config: dict[str, Any] = {"configurable": {"thread_id": init_state.run_id}}
        final_state = self.graph.invoke(init_state, config=config)
        return final_state
