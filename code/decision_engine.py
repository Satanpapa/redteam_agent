"""MCDA + Monte Carlo decision engine with adaptive weights and Pareto frontier."""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass

import numpy as np

from models import ActionCandidate, ActionResult, ActionStatus, DecisionOutcome

logger = logging.getLogger(__name__)


@dataclass
class DecisionConfig:
    monte_carlo_iterations: int = 200
    learning_rate: float = 0.08
    weights: dict[str, float] | None = None


class DecisionEngine:
    def __init__(self, config: DecisionConfig):
        self.config = config
        self.weights = config.weights or {
            "success_probability": 0.30,
            "stealth": 0.20,
            "impact": 0.20,
            "speed": 0.10,
            "reversibility": 0.10,
            "evidence_value": 0.10,
        }

    def select_action(self, candidates: list[ActionCandidate]) -> DecisionOutcome:
        if not candidates:
            raise ValueError("No candidate actions provided.")

        frontier = self.pareto_frontier(candidates)
        scores = {c.id: self.score_with_monte_carlo(c) for c in frontier}
        selected = max(frontier, key=lambda c: scores[c.id])
        rationale = f"Selected {selected.name} with score {scores[selected.id]:.3f}; frontier={len(frontier)}"
        logger.info(rationale)
        return DecisionOutcome(selected_action=selected, pareto_frontier=frontier, scores=scores, rationale=rationale)

    def score_with_monte_carlo(self, action: ActionCandidate) -> float:
        samples = []
        for _ in range(self.config.monte_carlo_iterations):
            success = np.clip(np.random.normal(action.success_probability, 0.12), 0, 1)
            stealth = np.clip(np.random.normal(action.stealth_score, 0.1), 0, 1)
            impact = np.clip(np.random.normal(action.impact_score, 0.13), 0, 1)
            speed = np.clip(1.0 - min(action.estimated_seconds / 600.0, 1.0), 0, 1)
            reversibility = np.clip(np.random.normal(action.reversibility_score, 0.08), 0, 1)
            evidence = np.clip(np.random.normal(action.evidence_value_score, 0.1), 0, 1)
            samples.append(
                success * self.weights["success_probability"]
                + stealth * self.weights["stealth"]
                + impact * self.weights["impact"]
                + speed * self.weights["speed"]
                + reversibility * self.weights["reversibility"]
                + evidence * self.weights["evidence_value"]
            )
        return float(np.mean(samples) + random.uniform(-0.01, 0.01))

    def update_weights(self, action: ActionCandidate, result: ActionResult) -> None:
        reward = 1.0 if result.status == ActionStatus.SUCCESS else -0.5
        reward += min(max(len(result.normalized) / 10.0, 0), 0.5)
        self.weights["success_probability"] = self._bounded(
            self.weights["success_probability"] + reward * self.config.learning_rate * 0.05
        )
        self.weights["stealth"] = self._bounded(
            self.weights["stealth"] + (action.stealth_score - 0.5) * self.config.learning_rate * 0.02
        )
        self._normalize_weights()
        logger.debug("Updated adaptive weights: %s", self.weights)

    def pareto_frontier(self, candidates: list[ActionCandidate]) -> list[ActionCandidate]:
        frontier: list[ActionCandidate] = []
        for c in candidates:
            dominated = False
            for other in candidates:
                if other.id == c.id:
                    continue
                if self._dominates(other, c):
                    dominated = True
                    break
            if not dominated:
                frontier.append(c)
        return frontier

    def _dominates(self, a: ActionCandidate, b: ActionCandidate) -> bool:
        a_vec = (a.success_probability, a.stealth_score, a.impact_score, -a.estimated_seconds)
        b_vec = (b.success_probability, b.stealth_score, b.impact_score, -b.estimated_seconds)
        ge_all = all(x >= y for x, y in zip(a_vec, b_vec))
        gt_any = any(x > y for x, y in zip(a_vec, b_vec))
        return ge_all and gt_any

    @staticmethod
    def _bounded(value: float) -> float:
        return max(0.01, min(0.8, value))

    def _normalize_weights(self) -> None:
        total = sum(self.weights.values())
        for k in self.weights:
            self.weights[k] = self.weights[k] / total
