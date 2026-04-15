"""Decision engine with MCDA, Monte Carlo simulation and Pareto filtering."""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field

import numpy as np

from .models import AttackAction, DecisionScore

logger = logging.getLogger(__name__)


@dataclass
class DecisionEngineConfig:
    reward_weight: float = 0.35
    risk_weight: float = 0.25
    stealth_weight: float = 0.2
    cost_weight: float = 0.2
    monte_carlo_iterations: int = 300
    adaptive_learning_rate: float = 0.15
    exploration_bias: float = 0.1


@dataclass
class DecisionEngine:
    config: DecisionEngineConfig
    weights: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.weights:
            self.weights = {
                "reward": self.config.reward_weight,
                "risk": self.config.risk_weight,
                "stealth": self.config.stealth_weight,
                "cost": self.config.cost_weight,
            }
        self._normalize_weights()

    def select_action(self, actions: list[AttackAction]) -> tuple[AttackAction, list[DecisionScore]]:
        if not actions:
            raise ValueError("No actions provided to decision engine")

        pareto_ids = self._pareto_frontier(actions)
        scores = [self._score_action(a, a.action_id in pareto_ids) for a in actions]
        ranked = sorted(scores, key=lambda s: s.utility_score, reverse=True)
        if random.random() < self.config.exploration_bias and len(ranked) > 1:
            selected_score = random.choice(ranked[: min(3, len(ranked))])
            logger.info("Exploration selected action=%s", selected_score.action_id)
        else:
            selected_score = ranked[0]
        selected = next(action for action in actions if action.action_id == selected_score.action_id)
        return selected, ranked

    def adapt_weights(self, reward_signal: float, risk_signal: float, stealth_signal: float, cost_signal: float) -> dict[str, float]:
        gradient = {
            "reward": max(0.0, reward_signal),
            "risk": max(0.0, 1 - risk_signal),
            "stealth": max(0.0, stealth_signal),
            "cost": max(0.0, 1 - cost_signal),
        }
        lr = self.config.adaptive_learning_rate
        for key, value in gradient.items():
            self.weights[key] = (1 - lr) * self.weights[key] + lr * value
        self._normalize_weights()
        logger.info("Updated decision weights=%s", self.weights)
        return self.weights

    def _score_action(self, action: AttackAction, pareto_efficient: bool) -> DecisionScore:
        samples = self._simulate(action)
        expected = float(np.mean(samples))
        variance_penalty = float(np.var(samples))
        utility = expected - (0.2 * variance_penalty)
        if pareto_efficient:
            utility += 0.05
        return DecisionScore(
            action_id=action.action_id,
            utility_score=utility,
            variance_penalty=variance_penalty,
            pareto_efficient=pareto_efficient,
            weighted_breakdown={
                "reward": action.estimated_reward * self.weights["reward"],
                "risk": (1 - action.estimated_risk) * self.weights["risk"],
                "stealth": action.estimated_stealth * self.weights["stealth"],
                "cost": (1 - action.estimated_cost) * self.weights["cost"],
            },
        )

    def _simulate(self, action: AttackAction) -> list[float]:
        samples: list[float] = []
        for _ in range(self.config.monte_carlo_iterations):
            reward = np.clip(np.random.normal(action.estimated_reward, 0.08), 0, 1)
            risk = np.clip(np.random.normal(action.estimated_risk, 0.08), 0, 1)
            stealth = np.clip(np.random.normal(action.estimated_stealth, 0.08), 0, 1)
            cost = np.clip(np.random.normal(action.estimated_cost, 0.08), 0, 1)
            score = (
                reward * self.weights["reward"]
                + (1 - risk) * self.weights["risk"]
                + stealth * self.weights["stealth"]
                + (1 - cost) * self.weights["cost"]
            )
            samples.append(float(score))
        return samples

    @staticmethod
    def _pareto_frontier(actions: list[AttackAction]) -> set[str]:
        frontier: set[str] = set()
        for candidate in actions:
            dominated = False
            for other in actions:
                if candidate.action_id == other.action_id:
                    continue
                better_or_equal = (
                    other.estimated_reward >= candidate.estimated_reward
                    and other.estimated_stealth >= candidate.estimated_stealth
                    and other.estimated_risk <= candidate.estimated_risk
                    and other.estimated_cost <= candidate.estimated_cost
                )
                strictly_better = (
                    other.estimated_reward > candidate.estimated_reward
                    or other.estimated_stealth > candidate.estimated_stealth
                    or other.estimated_risk < candidate.estimated_risk
                    or other.estimated_cost < candidate.estimated_cost
                )
                if better_or_equal and strictly_better:
                    dominated = True
                    break
            if not dominated:
                frontier.add(candidate.action_id)
        return frontier

    def _normalize_weights(self) -> None:
        total = sum(self.weights.values())
        if total <= 0:
            raise ValueError("Decision weights sum must be positive")
        for key in self.weights:
            self.weights[key] /= total
