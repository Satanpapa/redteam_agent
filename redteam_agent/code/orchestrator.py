"""LangGraph orchestrator implementing closed-loop autonomous red team workflow."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import yaml
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from .decision_engine import DecisionEngine, DecisionEngineConfig
from .docker_sandbox import DockerSandboxManager, SandboxConfig
from .llm_client import LLMClient
from .memory import MemoryManager
from .models import (
    ActionStatus,
    AgentState,
    AnalyzerOutput,
    AttackAction,
    LearningUpdate,
    PlannerInput,
    ToolExecutionRequest,
    WorldEdge,
    WorldNode,
)
from .tool_layer import MetasploitRPCConfig, ToolLayer
from .world_model import WorldModel

logger = logging.getLogger(__name__)


class RedTeamOrchestrator:
    def __init__(self, config_path: str = "config.yaml") -> None:
        self.config = self._load_config(config_path)
        self.llm = LLMClient(**self.config["llm"])
        self.world_model = WorldModel(self.config["world_model"]["graph_db_path"])
        self.memory = MemoryManager(
            tactical_db_path=self.config["memory"]["tactical_db_path"],
            vector_path=self.config["memory"]["vector_path"],
            vector_collection=self.config["memory"]["vector_collection"],
        )
        msf_cfg = MetasploitRPCConfig(**self.config["tooling"]["metasploit"])
        self.tool_layer = ToolLayer(workdir=self.config["app"]["default_workspace"], metasploit_config=msf_cfg)
        self.sandbox = DockerSandboxManager(SandboxConfig(**self.config["docker"]))
        self.decision_engine = DecisionEngine(DecisionEngineConfig(**self.config["decision_engine"]))
        self.graph = self._build_graph()

    @staticmethod
    def _load_config(path: str) -> dict[str, Any]:
        with Path(path).open("r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _build_graph(self):
        workflow = StateGraph(AgentState)
        workflow.add_node("planner", self._planner_node)
        workflow.add_node("decision", self._decision_node)
        workflow.add_node("executor", self._executor_node)
        workflow.add_node("analyzer", self._analyzer_node)
        workflow.add_node("learner", self._learner_node)

        workflow.set_entry_point("planner")
        workflow.add_edge("planner", "decision")
        workflow.add_edge("decision", "executor")
        workflow.add_edge("executor", "analyzer")
        workflow.add_edge("analyzer", "learner")
        workflow.add_conditional_edges("learner", self._should_continue, {"continue": "planner", "end": END})

        return workflow.compile(checkpointer=MemorySaver())

    def _planner_node(self, state: AgentState) -> AgentState:
        memory_context = self.memory.recall(state.objective, top_k=4)
        heuristics = self._heuristic_actions(state)
        prompt = [
            {"role": "system", "content": "You are a red team planner. Return JSON list of actions."},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "input": PlannerInput(objective=state.objective, scope=state.scope).model_dump(),
                        "memory": memory_context,
                        "heuristics": [a.model_dump() for a in heuristics],
                    }
                ),
            },
        ]
        try:
            response = self.llm.chat(prompt)
            raw_actions = json.loads(response)
            llm_actions = [AttackAction(**item) for item in raw_actions]
            state.current_plan = self._merge_actions(heuristics, llm_actions)
        except Exception as exc:  # fallback path
            logger.warning("Planner fallback due to error: %s", exc)
            state.current_plan = heuristics
        return state

    def _decision_node(self, state: AgentState) -> AgentState:
        selected, _scores = self.decision_engine.select_action(state.current_plan)
        state.selected_action = selected
        return state

    def _executor_node(self, state: AgentState) -> AgentState:
        if not state.selected_action:
            state.halt = True
            return state

        snapshot_tag = f"{state.run_id}-{state.iteration}"
        sandbox_name = f"rta-{state.run_id[:8]}"
        container_id = self.sandbox.create(sandbox_name)
        try:
            if state.selected_action.parameters.get("dangerous", False):
                self.sandbox.snapshot(container_id, snapshot_tag)

            req = ToolExecutionRequest(
                tool_name=state.selected_action.required_capability,
                command=state.selected_action.parameters.get("command", "echo"),
                args=state.selected_action.parameters.get("args", ["noop"]),
                timeout_seconds=self.config["tooling"]["command_timeout_sec"],
            )
            state.last_result = self.tool_layer.execute(req)
        finally:
            self.sandbox.remove(container_id, force=True)
        return state

    def _analyzer_node(self, state: AgentState) -> AgentState:
        result = state.last_result
        if not result:
            state.analysis = AnalyzerOutput(summary="No execution result", success_probability=0.0)
            return state

        summary = f"Action {result.tool_name} exited {result.exit_code}; findings={len(result.normalized_findings)}"
        nodes: list[WorldNode] = []
        edges: list[WorldEdge] = []
        for finding in result.normalized_findings:
            service = finding.get("service", {})
            host = service.get("host")
            port = service.get("port")
            if host and port:
                host_node = WorldNode(node_type="host", label=host, properties={"ip": host})
                svc_node = WorldNode(node_type="service", label=f"{host}:{port}", properties=service)
                nodes.extend([host_node, svc_node])
                edges.append(WorldEdge(src_id=host_node.node_id, dst_id=svc_node.node_id, relationship="exposes"))

        state.analysis = AnalyzerOutput(
            summary=summary,
            success_probability=1.0 if result.status == ActionStatus.SUCCESS else 0.2,
            lessons=["Prefer low-noise scans before exploitation."],
            extracted_nodes=nodes,
            extracted_edges=edges,
        )
        state.world_delta_nodes = nodes
        state.world_delta_edges = edges
        return state

    def _learner_node(self, state: AgentState) -> AgentState:
        state.iteration += 1
        if state.analysis:
            for node in state.analysis.extracted_nodes:
                self.world_model.upsert_node(node)
            for edge in state.analysis.extracted_edges:
                self.world_model.upsert_edge(edge)

            success = state.analysis.success_probability
            risk = state.selected_action.estimated_risk if state.selected_action else 0.5
            stealth = state.selected_action.estimated_stealth if state.selected_action else 0.5
            cost = state.selected_action.estimated_cost if state.selected_action else 0.5
            updated = self.decision_engine.adapt_weights(success, risk, stealth, cost)
            state.learning = LearningUpdate(updated_weights=updated, notes=state.analysis.lessons)
            self.memory.remember_context(state.analysis.summary, {"run_id": state.run_id, "iteration": state.iteration})
        if state.iteration >= state.max_iterations:
            state.halt = True
        return state

    def _should_continue(self, state: AgentState) -> str:
        return "end" if state.halt else "continue"

    def run(self, objective: str, scope: str, max_iterations: int = 5) -> AgentState:
        state = AgentState(objective=objective, scope=scope, max_iterations=max_iterations)
        final = self.graph.invoke(state)
        return AgentState.model_validate(final)

    def _heuristic_actions(self, state: AgentState) -> list[AttackAction]:
        target = state.scope.split(",")[0].strip()
        return [
            AttackAction(
                name="Stealth host discovery",
                objective=state.objective,
                rationale="Low-noise discovery step",
                required_capability="nmap",
                estimated_reward=0.45,
                estimated_risk=0.15,
                estimated_stealth=0.9,
                estimated_cost=0.2,
                parameters={"command": "nmap", "args": ["-sV", "-oG", "-", target]},
            ),
            AttackAction(
                name="Web vulnerability check",
                objective=state.objective,
                rationale="HTTP services often expose immediate footholds",
                required_capability="nikto",
                estimated_reward=0.6,
                estimated_risk=0.35,
                estimated_stealth=0.5,
                estimated_cost=0.4,
                parameters={"command": "nikto", "args": ["-h", target]},
            ),
        ]

    @staticmethod
    def _merge_actions(heuristics: list[AttackAction], llm_actions: list[AttackAction]) -> list[AttackAction]:
        unique: dict[str, AttackAction] = {a.name: a for a in heuristics}
        for action in llm_actions:
            unique[action.name] = action
        return list(unique.values())
