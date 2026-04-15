import pytest

pytest.importorskip("numpy")
pytest.importorskip("pydantic")

from rtcode.decision_engine import DecisionEngine, DecisionEngineConfig
from rtcode.models import AttackAction


def test_select_action_returns_member():
    engine = DecisionEngine(DecisionEngineConfig(monte_carlo_iterations=20))
    actions = [
        AttackAction(name="a", objective="o", rationale="r", required_capability="nmap", estimated_reward=0.8),
        AttackAction(name="b", objective="o", rationale="r", required_capability="nikto", estimated_reward=0.2),
    ]
    selected, scores = engine.select_action(actions)
    assert selected.action_id in {a.action_id for a in actions}
    assert len(scores) == 2
