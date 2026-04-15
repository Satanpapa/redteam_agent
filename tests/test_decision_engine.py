import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1] / "code"))

from decision_engine import DecisionConfig, DecisionEngine
from models import ActionCandidate, RiskLevel


def test_decision_selects_from_candidates():
    engine = DecisionEngine(DecisionConfig(monte_carlo_iterations=10))
    c1 = ActionCandidate(id="1", name="a", description="", command="x", technique="T1", risk=RiskLevel.LOW)
    c2 = ActionCandidate(id="2", name="b", description="", command="x", technique="T2", risk=RiskLevel.LOW, success_probability=0.9)
    out = engine.select_action([c1, c2])
    assert out.selected_action.id in {"1", "2"}
    assert out.pareto_frontier
