"""
Decision Engine for Red Team Agent v2.0

Implements Multi-Criteria Decision Analysis (MCDA), Monte Carlo simulation,
Pareto frontier analysis, and adaptive weight adjustment for intelligent
action selection during penetration testing engagements.
"""

from __future__ import annotations

import logging
import random
import statistics
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .models import ActionResult, DecisionMetrics

logger = logging.getLogger(__name__)


class DecisionEngine:
    """
    Advanced decision engine for autonomous red team operations.
    
    Features:
    - Multi-Criteria Decision Analysis (MCDA)
    - Monte Carlo simulation for outcome probability
    - Pareto frontier optimization
    - Adaptive weight adjustment based on historical performance
    """
    
    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        monte_carlo_iterations: int = 1000,
        confidence_level: float = 0.95,
        max_acceptable_risk: float = 0.7,
    ):
        """
        Initialize the decision engine.
        
        Args:
            weights: Dictionary of metric weights (must sum to 1.0)
            monte_carlo_iterations: Number of iterations for MC simulation
            confidence_level: Confidence level for MC confidence intervals
            max_acceptable_risk: Maximum acceptable risk threshold
        """
        # Default weights if not provided
        self.base_weights = weights or {
            "success_probability": 0.30,
            "impact": 0.25,
            "stealth": 0.20,
            "speed": 0.15,
            "resource_cost": 0.10,
        }
        
        # Normalize weights to sum to 1.0
        self._normalize_weights()
        
        self.current_weights = self.base_weights.copy()
        self.monte_carlo_iterations = monte_carlo_iterations
        self.confidence_level = confidence_level
        self.max_acceptable_risk = max_acceptable_risk
        
        # Historical data for adaptive learning
        self.action_history: List[Dict[str, Any]] = []
        self.weight_adjustments: List[Dict[str, float]] = []
        
        logger.info(
            f"DecisionEngine initialized with weights: {self.base_weights}"
        )
    
    def _normalize_weights(self) -> None:
        """Normalize weights to ensure they sum to 1.0."""
        total = sum(self.base_weights.values())
        if total > 0:
            self.base_weights = {
                k: v / total for k, v in self.base_weights.items()
            }
    
    def evaluate_action(
        self,
        action: Dict[str, Any],
        context: Dict[str, Any],
    ) -> DecisionMetrics:
        """
        Evaluate a single action using MCDA.
        
        Args:
            action: Action dictionary with parameters and metadata
            context: Current engagement context
            
        Returns:
            DecisionMetrics object with computed scores
        """
        metrics = DecisionMetrics()
        
        # Extract or estimate metrics from action
        metrics.success_probability = self._estimate_success_probability(
            action, context
        )
        metrics.impact = self._estimate_impact(action, context)
        metrics.stealth = self._estimate_stealth(action, context)
        metrics.speed = self._estimate_speed(action, context)
        metrics.resource_cost = self._estimate_resource_cost(action, context)
        metrics.risk = self._compute_risk(metrics)
        
        # Compute weighted score
        metrics.compute_weighted_score(self.current_weights)
        
        # Run Monte Carlo simulation
        self._run_monte_carlo_simulation(metrics, action, context)
        
        logger.debug(
            f"Evaluated action '{action.get('name', 'unknown')}': "
            f"score={metrics.weighted_score:.4f}, risk={metrics.risk:.4f}"
        )
        
        return metrics
    
    def _estimate_success_probability(
        self, action: Dict[str, Any], context: Dict[str, Any]
    ) -> float:
        """Estimate probability of action success."""
        base_prob = action.get("base_success_rate", 0.5)
        
        # Adjust based on historical performance
        action_name = action.get("name", "")
        historical = self._get_historical_performance(action_name)
        if historical["count"] > 0:
            historical_success = historical["successes"] / historical["count"]
            # Blend base probability with historical performance
            base_prob = (base_prob + historical_success) / 2
        
        # Adjust based on context
        target_complexity = context.get("target_complexity", 0.5)
        base_prob *= (1.0 - target_complexity * 0.3)
        
        return min(max(base_prob, 0.0), 1.0)
    
    def _estimate_impact(
        self, action: Dict[str, Any], context: Dict[str, Any]
    ) -> float:
        """Estimate potential impact of action."""
        impact_level = action.get("impact_level", "medium")
        impact_map = {
            "low": 0.25,
            "medium": 0.5,
            "high": 0.75,
            "critical": 1.0,
        }
        return impact_map.get(impact_level, 0.5)
    
    def _estimate_stealth(
        self, action: Dict[str, Any], context: Dict[str, Any]
    ) -> float:
        """Estimate stealth level of action (higher is better)."""
        noise_level = action.get("noise_level", "medium")
        stealth_map = {
            "low": 0.9,      # Low noise = high stealth
            "medium": 0.6,
            "high": 0.3,
            "very_high": 0.1,
        }
        return stealth_map.get(noise_level, 0.5)
    
    def _estimate_speed(
        self, action: Dict[str, Any], context: Dict[str, Any]
    ) -> float:
        """Estimate speed of action execution (higher is faster)."""
        estimated_duration = action.get("estimated_duration_seconds", 60)
        # Normalize: < 10s = 1.0, > 300s = 0.0
        speed = 1.0 - min(estimated_duration / 300, 1.0)
        return speed
    
    def _estimate_resource_cost(
        self, action: Dict[str, Any], context: Dict[str, Any]
    ) -> float:
        """Estimate resource cost of action (lower is better)."""
        cost_level = action.get("resource_cost_level", "medium")
        cost_map = {
            "low": 0.2,
            "medium": 0.5,
            "high": 0.8,
            "very_high": 1.0,
        }
        return cost_map.get(cost_level, 0.5)
    
    def _compute_risk(self, metrics: DecisionMetrics) -> float:
        """Compute overall risk score from metrics."""
        # Risk increases with lower stealth and higher resource cost
        stealth_risk = (1.0 - metrics.stealth) * 0.4
        cost_risk = metrics.resource_cost * 0.3
        failure_risk = (1.0 - metrics.success_probability) * 0.3
        
        return min(stealth_risk + cost_risk + failure_risk, 1.0)
    
    def _run_monte_carlo_simulation(
        self,
        metrics: DecisionMetrics,
        action: Dict[str, Any],
        context: Dict[str, Any],
    ) -> None:
        """
        Run Monte Carlo simulation to estimate outcome distribution.
        
        Args:
            metrics: DecisionMetrics object to update
            action: Action being evaluated
            context: Current context
        """
        samples = []
        
        for _ in range(self.monte_carlo_iterations):
            # Add noise to each metric
            noise_factor = 0.1  # 10% variability
            
            success_prob = max(
                0.0,
                min(
                    1.0,
                    metrics.success_probability
                    + random.gauss(0, noise_factor),
                )
            )
            
            impact = max(
                0.0,
                min(
                    1.0,
                    metrics.impact + random.gauss(0, noise_factor * 0.5)
                )
            )
            
            # Compute sample score
            sample_score = (
                success_prob * self.current_weights["success_probability"]
                + impact * self.current_weights["impact"]
            )
            
            samples.append(sample_score)
        
        # Compute statistics
        metrics.mc_mean = statistics.mean(samples)
        metrics.mc_std = statistics.stdev(samples) if len(samples) > 1 else 0.0
        
        # Compute confidence interval
        z_score = 1.96 if self.confidence_level == 0.95 else 1.645
        margin_of_error = z_score * metrics.mc_std / np.sqrt(self.monte_carlo_iterations)
        
        metrics.mc_confidence_interval = (
            max(0.0, metrics.mc_mean - margin_of_error),
            min(1.0, metrics.mc_mean + margin_of_error),
        )
    
    def select_best_action(
        self,
        available_actions: List[Dict[str, Any]],
        context: Dict[str, Any],
        use_pareto: bool = True,
    ) -> Tuple[Optional[Dict[str, Any]], List[DecisionMetrics]]:
        """
        Select the best action from available options.
        
        Args:
            available_actions: List of action dictionaries
            context: Current engagement context
            use_pareto: Whether to use Pareto optimization
            
        Returns:
            Tuple of (best_action, all_metrics)
        """
        if not available_actions:
            return None, []
        
        # Evaluate all actions
        action_metrics: List[Tuple[Dict[str, Any], DecisionMetrics]] = []
        
        for action in available_actions:
            metrics = self.evaluate_action(action, context)
            
            # Filter out high-risk actions
            if metrics.risk > self.max_acceptable_risk:
                logger.debug(
                    f"Action '{action.get('name')}' filtered due to high risk: "
                    f"{metrics.risk:.4f}"
                )
                continue
            
            action_metrics.append((action, metrics))
        
        if not action_metrics:
            logger.warning("All actions filtered due to high risk")
            return None, []
        
        # Apply Pareto optimization if enabled
        if use_pareto:
            pareto_optimal = self._find_pareto_frontier(action_metrics)
            
            # Mark Pareto optimal actions
            for action, metrics in action_metrics:
                metrics.pareto_optimal = any(
                    a is action for a, _ in pareto_optimal
                )
            
            # Select from Pareto frontier
            if pareto_optimal:
                best_action, best_metrics = max(
                    pareto_optimal,
                    key=lambda x: x[1].weighted_score
                )
            else:
                best_action, best_metrics = max(
                    action_metrics,
                    key=lambda x: x[1].weighted_score
                )
        else:
            best_action, best_metrics = max(
                action_metrics,
                key=lambda x: x[1].weighted_score
            )
        
        all_metrics = [m for _, m in action_metrics]
        
        logger.info(
            f"Selected action: '{best_action.get('name')}' "
            f"(score={best_metrics.weighted_score:.4f})"
        )
        
        return best_action, all_metrics
    
    def _find_pareto_frontier(
        self,
        action_metrics: List[Tuple[Dict[str, Any], DecisionMetrics]],
    ) -> List[Tuple[Dict[str, Any], DecisionMetrics]]:
        """
        Find Pareto-optimal actions.
        
        An action is Pareto-optimal if no other action dominates it
        across all objectives (success_probability, impact, stealth, speed).
        
        Args:
            action_metrics: List of (action, metrics) tuples
            
        Returns:
            List of Pareto-optimal (action, metrics) tuples
        """
        pareto_frontier = []
        
        for i, (action_i, metrics_i) in enumerate(action_metrics):
            dominated = False
            
            for j, (action_j, metrics_j) in enumerate(action_metrics):
                if i == j:
                    continue
                
                # Check if j dominates i
                dominates = (
                    metrics_j.success_probability >= metrics_i.success_probability
                    and metrics_j.impact >= metrics_i.impact
                    and metrics_j.stealth >= metrics_i.stealth
                    and metrics_j.speed >= metrics_i.speed
                    and (
                        metrics_j.success_probability > metrics_i.success_probability
                        or metrics_j.impact > metrics_i.impact
                        or metrics_j.stealth > metrics_i.stealth
                        or metrics_j.speed > metrics_i.speed
                    )
                )
                
                if dominates:
                    dominated = True
                    break
            
            if not dominated:
                pareto_frontier.append((action_i, metrics_i))
        
        logger.debug(f"Pareto frontier size: {len(pareto_frontier)}")
        return pareto_frontier
    
    def record_outcome(
        self,
        action: Dict[str, Any],
        result: ActionResult,
        context: Dict[str, Any],
    ) -> None:
        """
        Record action outcome for adaptive learning.
        
        Args:
            action: Action that was executed
            result: Result of action execution
            context: Context at time of execution
        """
        record = {
            "action_name": action.get("name"),
            "success": result.success,
            "metrics_prediction": {
                "success_probability": getattr(
                    context.get("predicted_metrics"), "success_probability", 0.5
                ),
            },
            "actual_outcome": result.status.value,
            "timestamp": result.completed_at,
        }
        
        self.action_history.append(record)
        
        # Adapt weights periodically
        if len(self.action_history) % 10 == 0:
            self._adapt_weights()
    
    def _adapt_weights(self) -> None:
        """Adapt weights based on historical performance."""
        if len(self.action_history) < 10:
            return
        
        # Analyze which metrics correlate with success
        successes = [r for r in self.action_history if r["success"]]
        
        if len(successes) < 5:
            return
        
        # Simple adaptation: increase weight of metrics that predict success well
        # This is a placeholder for more sophisticated ML-based adaptation
        adjustment = {}
        
        for metric in self.base_weights.keys():
            # Placeholder logic - in production, use correlation analysis
            adjustment[metric] = self.base_weights[metric] * (1.0 + random.uniform(-0.1, 0.1))
        
        # Re-normalize
        total = sum(adjustment.values())
        self.current_weights = {k: v / total for k, v in adjustment.items()}
        
        self.weight_adjustments.append(self.current_weights.copy())
        
        logger.info(f"Adapted weights: {self.current_weights}")
    
    def _get_historical_performance(
        self, action_name: str
    ) -> Dict[str, int]:
        """Get historical performance statistics for an action."""
        relevant = [
            r for r in self.action_history if r["action_name"] == action_name
        ]
        
        return {
            "count": len(relevant),
            "successes": sum(1 for r in relevant if r["success"]),
        }
    
    def get_decision_explanation(
        self,
        action: Dict[str, Any],
        metrics: DecisionMetrics,
    ) -> str:
        """
        Generate human-readable explanation for a decision.
        
        Args:
            action: Selected action
            metrics: Computed metrics
            
        Returns:
            Explanation string
        """
        explanation = [
            f"Action: {action.get('name', 'Unknown')}",
            f"Weighted Score: {metrics.weighted_score:.2%}",
            "",
            "Metric Breakdown:",
            f"  - Success Probability: {metrics.success_probability:.2%}",
            f"  - Impact: {metrics.impact:.2%}",
            f"  - Stealth: {metrics.stealth:.2%}",
            f"  - Speed: {metrics.speed:.2%}",
            f"  - Resource Cost: {metrics.resource_cost:.2%}",
            f"  - Risk: {metrics.risk:.2%}",
        ]
        
        if metrics.mc_confidence_interval:
            ci = metrics.mc_confidence_interval
            explanation.append(
                f"\nMonte Carlo: {metrics.mc_mean:.2%} "
                f"(95% CI: {ci[0]:.2%} - {ci[1]:.2%})"
            )
        
        if metrics.pareto_optimal:
            explanation.append("\n✓ Pareto-optimal solution")
        
        return "\n".join(explanation)
