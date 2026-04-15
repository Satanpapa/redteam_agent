"""
LangGraph Orchestrator for Red Team Agent v2.0

Implements the autonomous agent workflow using LangGraph StateGraph
with checkpointing and memory management.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict, Annotated
from uuid import uuid4

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .models import AgentState, ActionResult, EngagementConfig
from .decision_engine import DecisionEngine
from .world_model import WorldModel
from .memory import MemorySystem
from .tool_layer import ToolExecutor
from .llm_client import OllamaClient, LLMOrchestrator

logger = logging.getLogger(__name__)


class RedTeamGraph(TypedDict):
    """State graph schema for LangGraph."""
    agent_state: AgentState
    messages: Annotated[List[Dict[str, Any]], "append"]
    iteration: int


class RedTeamOrchestrator:
    """
    Main orchestrator for autonomous red team operations.
    
    Implements complete feedback loop:
    Planner -> Decision Engine -> Executor -> Analyzer -> Learner -> Planner
    """
    
    def __init__(
        self,
        config_path: str = "./config.yaml",
        ollama_base_url: str = "http://localhost:11434/v1",
        ollama_model: str = "qwen2.5-coder:32b",
    ):
        """Initialize the orchestrator."""
        self.config_path = config_path
        
        # Initialize components
        self.llm_client = OllamaClient(
            base_url=ollama_base_url,
            model=ollama_model,
        )
        
        self.llm_orchestrator = LLMOrchestrator(self.llm_client)
        self.decision_engine = DecisionEngine()
        self.world_model = WorldModel()
        self.memory_system = MemorySystem()
        self.tool_executor = ToolExecutor()
        
        # Build LangGraph
        self.graph = self._build_graph()
        
        logger.info("RedTeamOrchestrator initialized")
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state machine."""
        workflow = StateGraph(RedTeamGraph)
        
        # Add nodes
        workflow.add_node("planner", self.planner_node)
        workflow.add_node("decision", self.decision_node)
        workflow.add_node("executor", self.executor_node)
        workflow.add_node("analyzer", self.analyzer_node)
        workflow.add_node("learner", self.learner_node)
        
        # Define edges
        workflow.set_entry_point("planner")
        workflow.add_edge("planner", "decision")
        workflow.add_edge("decision", "executor")
        workflow.add_edge("executor", "analyzer")
        workflow.add_edge("analyzer", "learner")
        
        # Conditional edge from learner back to planner or end
        workflow.add_conditional_edges(
            "learner",
            self._should_continue,
            {
                "continue": "planner",
                "end": END,
            }
        )
        
        # Add checkpointing
        memory = MemorySaver()
        app = workflow.compile(checkpointer=memory)
        
        return app
    
    def planner_node(self, state: RedTeamGraph) -> Dict[str, Any]:
        """Plan next action based on current state."""
        logger.info("Planner node executing")
        
        agent_state = state["agent_state"]
        
        # Use LLM to plan next action
        planned_action = self.llm_orchestrator.plan_next_action(
            current_state={
                "discovered_targets": [t.model_dump() for t in agent_state.discovered_targets],
                "vulnerabilities": [v.model_dump() for v in agent_state.vulnerabilities],
                "current_phase": agent_state.current_phase,
            },
            action_history=[a.model_dump() for a in agent_state.action_history[-10:]],
        )
        
        # Update available actions
        agent_state.available_actions = [planned_action]
        agent_state.selected_action = planned_action
        
        # Add message
        state["messages"].append({
            "role": "system",
            "content": f"Planned action: {planned_action.get('name')}",
        })
        
        return {
            "agent_state": agent_state,
            "messages": state["messages"],
            "iteration": state["iteration"] + 1,
        }
    
    def decision_node(self, state: RedTeamGraph) -> Dict[str, Any]:
        """Evaluate and select best action."""
        logger.info("Decision node executing")
        
        agent_state = state["agent_state"]
        
        if not agent_state.available_actions:
            return {"agent_state": agent_state, "messages": state["messages"], "iteration": state["iteration"]}
        
        # Evaluate action with decision engine
        action = agent_state.available_actions[0]
        context = {
            "target_complexity": len(agent_state.discovered_targets),
            "predicted_metrics": None,
        }
        
        metrics = self.decision_engine.evaluate_action(action, context)
        agent_state.decision_metrics = metrics
        
        # Check if action should proceed
        if metrics.risk > self.decision_engine.max_acceptable_risk:
            state["messages"].append({
                "role": "system",
                "content": f"Action blocked due to high risk: {metrics.risk:.2f}",
            })
            agent_state.selected_action = None
        
        return {
            "agent_state": agent_state,
            "messages": state["messages"],
            "iteration": state["iteration"],
        }
    
    def executor_node(self, state: RedTeamGraph) -> Dict[str, Any]:
        """Execute selected action."""
        logger.info("Executor node executing")
        
        agent_state = state["agent_state"]
        
        if not agent_state.selected_action:
            return {"agent_state": agent_state, "messages": state["messages"], "iteration": state["iteration"]}
        
        action = agent_state.selected_action
        tool_name = action.get("tool", "unknown")
        params = action.get("params", {})
        
        # Execute tool
        import asyncio
        result = asyncio.run(self.tool_executor.execute(tool_name, params))
        
        # Update state
        agent_state.add_action_result(result)
        
        # Update world model
        if result.normalized_data.get("targets"):
            for target_data in result.normalized_data["targets"]:
                target = TargetInfo(**target_data)
                self.world_model.add_target(target)
        
        state["messages"].append({
            "role": "system",
            "content": f"Executed {tool_name}: {result.status.value}",
        })
        
        return {
            "agent_state": agent_state,
            "messages": state["messages"],
            "iteration": state["iteration"],
        }
    
    def analyzer_node(self, state: RedTeamGraph) -> Dict[str, Any]:
        """Analyze execution results."""
        logger.info("Analyzer node executing")
        
        agent_state = state["agent_state"]
        
        if not agent_state.action_history:
            return {"agent_state": agent_state, "messages": state["messages"], "iteration": state["iteration"]}
        
        last_result = agent_state.action_history[-1]
        
        # Analyze results with LLM
        if last_result.output:
            analysis = self.llm_orchestrator.analyze_results(
                tool_output=last_result.output,
                tool_name=last_result.tool_name,
                context={"phase": agent_state.current_phase},
            )
            
            # Store in memory
            self.memory_system.store(
                session_id=agent_state.engagement_id,
                content=analysis.get("analysis", ""),
                entry_type="finding",
                importance=0.7,
            )
        
        return {
            "agent_state": agent_state,
            "messages": state["messages"],
            "iteration": state["iteration"],
        }
    
    def learner_node(self, state: RedTeamGraph) -> Dict[str, Any]:
        """Learn from execution and adapt."""
        logger.info("Learner node executing")
        
        agent_state = state["agent_state"]
        
        # Record outcome in decision engine
        if agent_state.selected_action and agent_state.action_history:
            self.decision_engine.record_outcome(
                action=agent_state.selected_action,
                result=agent_state.action_history[-1],
                context={},
            )
        
        # Adapt weights periodically
        if agent_state.iteration_count % 10 == 0:
            agent_state.adapted_weights = self.decision_engine.current_weights
        
        # Store lesson
        if agent_state.action_history[-1].success:
            agent_state.lessons_learned.append(
                f"Iteration {agent_state.iteration_count}: {agent_state.selected_action.get('tool')} succeeded"
            )
        
        return {
            "agent_state": agent_state,
            "messages": state["messages"],
            "iteration": state["iteration"],
        }
    
    def _should_continue(self, state: RedTeamGraph) -> str:
        """Determine if execution should continue."""
        agent_state = state["agent_state"]
        
        # Check termination conditions
        if not agent_state.can_continue():
            return "end"
        
        if state["iteration"] >= agent_state.max_iterations:
            return "end"
        
        if agent_state.status != "running":
            return "end"
        
        return "continue"
    
    async def run_async(
        self,
        engagement_config: EngagementConfig,
    ) -> AgentState:
        """Run the agent asynchronously."""
        initial_state = AgentState(
            engagement_config=engagement_config,
            status="running",
            started_at=datetime.utcnow(),
        )
        
        graph_state: RedTeamGraph = {
            "agent_state": initial_state,
            "messages": [],
            "iteration": 0,
        }
        
        # Run graph
        config = {"configurable": {"thread_id": str(uuid4())}}
        
        async for event in self.graph.astream(graph_state, config=config):
            logger.debug(f"Graph event: {list(event.keys())}")
        
        return graph_state["agent_state"]
    
    def run(
        self,
        engagement_config: EngagementConfig,
    ) -> AgentState:
        """Run the agent synchronously."""
        import asyncio
        return asyncio.run(self.run_async(engagement_config))
    
    def resume(
        self,
        thread_id: str,
    ) -> AgentState:
        """Resume execution from checkpoint."""
        config = {"configurable": {"thread_id": thread_id}}
        
        # Get last state
        last_state = self.graph.get_state(config)
        
        if last_state.values:
            # Continue execution
            for event in self.graph.stream(None, config=config):
                logger.debug(f"Resumed event: {event}")
            
            return last_state.values.get("agent_state", AgentState())
        
        return AgentState()
