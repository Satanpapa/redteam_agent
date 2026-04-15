"""Tests for Decision Engine module."""

import pytest
from code.decision_engine import DecisionEngine
from code.models import DecisionMetrics


class TestDecisionEngine:
    """Test cases for DecisionEngine."""

    def test_initialization(self):
        """Test engine initializes with default weights."""
        engine = DecisionEngine()
        assert engine.base_weights is not None
        assert abs(sum(engine.base_weights.values()) - 1.0) < 0.001

    def test_weight_normalization(self):
        """Test that weights are normalized to sum to 1.0."""
        custom_weights = {
            "success_probability": 0.5,
            "impact": 0.3,
            "stealth": 0.2,
        }
        engine = DecisionEngine(weights=custom_weights)
        assert abs(sum(engine.base_weights.values()) - 1.0) < 0.001

    def test_evaluate_action(self):
        """Test action evaluation returns valid metrics."""
        engine = DecisionEngine()
        action = {
            "name": "test_scan",
            "base_success_rate": 0.8,
            "impact_level": "high",
            "noise_level": "low",
        }
        context = {"target_complexity": 0.3}
        
        metrics = engine.evaluate_action(action, context)
        
        assert isinstance(metrics, DecisionMetrics)
        assert 0.0 <= metrics.success_probability <= 1.0
        assert 0.0 <= metrics.impact <= 1.0
        assert 0.0 <= metrics.stealth <= 1.0
        assert 0.0 <= metrics.risk <= 1.0

    def test_select_best_action(self):
        """Test best action selection from multiple options."""
        engine = DecisionEngine()
        actions = [
            {"name": "action1", "base_success_rate": 0.9, "impact_level": "medium"},
            {"name": "action2", "base_success_rate": 0.5, "impact_level": "low"},
            {"name": "action3", "base_success_rate": 0.7, "impact_level": "high"},
        ]
        context = {}
        
        best_action, all_metrics = engine.select_best_action(actions, context)
        
        assert best_action is not None
        assert len(all_metrics) > 0

    def test_high_risk_filtering(self):
        """Test that high-risk actions are filtered."""
        engine = DecisionEngine(max_acceptable_risk=0.3)
        action = {
            "name": "risky_action",
            "base_success_rate": 0.3,
            "noise_level": "very_high",
        }
        context = {}
        
        metrics = engine.evaluate_action(action, context)
        
        # High noise should result in low stealth and higher risk
        assert metrics.risk > 0.3 or metrics.success_probability < 0.5

    def test_monte_carlo_simulation(self):
        """Test Monte Carlo simulation produces valid statistics."""
        engine = DecisionEngine(monte_carlo_iterations=100)
        action = {"name": "test", "base_success_rate": 0.7}
        context = {}
        
        metrics = engine.evaluate_action(action, context)
        
        assert metrics.mc_mean is not None
        assert metrics.mc_std is not None
        assert metrics.mc_confidence_interval is not None

    def test_record_outcome(self):
        """Test outcome recording for adaptive learning."""
        from code.models import ActionResult, ActionStatus
        
        engine = DecisionEngine()
        action = {"name": "test_action"}
        result = ActionResult(
            action_name="test",
            tool_name="test",
            status=ActionStatus.SUCCESS,
        )
        
        engine.record_outcome(action, result, {})
        
        assert len(engine.action_history) == 1

    def test_get_decision_explanation(self):
        """Test decision explanation generation."""
        engine = DecisionEngine()
        action = {"name": "explained_action"}
        metrics = DecisionMetrics(
            success_probability=0.8,
            impact=0.7,
            stealth=0.6,
        )
        
        explanation = engine.get_decision_explanation(action, metrics)
        
        assert "explained_action" in explanation
        assert "Weighted Score" in explanation
