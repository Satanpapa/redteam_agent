"""MCDA + Monte Carlo + Pareto frontier decision engine."""

from __future__ import annotations

import logging
import random
import statistics
from dataclasses import dataclass


from .models import ActionCandidate, DecisionMetrics, DecisionResult, LearnedSignal

logger = logging.getLogger(__name__)


@dataclass
class DecisionConfig:
    monte_carlo_iterations: int = 200
    exploration_rate: float = 0.15
    adaptive_learning_rate: float = 0.2
    objective_weights: dict[str, float] | None = None


class DecisionEngine:
    def __init__(self, config: DecisionConfig) -> None:
        self.config = config
        self.weights = config.objective_weights or {
            "stealth": 0.25,
            "impact": 0.35,
            "speed": 0.2,
            "confidence": 0.2,
        }

    def _mcda(self, metrics: DecisionMetrics) -> float:
        return (
            self.weights["stealth"] * metrics.stealth
            + self.weights["impact"] * metrics.impact
            + self.weights["speed"] * metrics.speed
            + self.weights["confidence"] * metrics.confidence
        )

    def _simulate(self, base_score: float) -> tuple[float, float]:
        samples = [max(0.0, min(1.0, random.gauss(base_score, 0.08))) for _ in range(self.config.monte_carlo_iterations)]
        return float(statistics.fmean(samples)), float(statistics.pstdev(samples))

    def _pareto_rank(self, all_metrics: list[DecisionMetrics], idx: int) -> int:
        target = all_metrics[idx]
        dominated = 0
        for i, cand in enumerate(all_metrics):
            if i == idx:
                continue
            better_or_equal = (
                cand.stealth >= target.stealth
                and cand.impact >= target.impact
                and cand.speed >= target.speed
                and cand.confidence >= target.confidence
            )
            strictly_better = (
                cand.stealth > target.stealth
                or cand.impact > target.impact
                or cand.speed > target.speed
                or cand.confidence > target.confidence
            )
            if better_or_equal and strictly_better:
                dominated += 1
        return dominated + 1

    def decide(self, candidates: list[ActionCandidate]) -> DecisionResult:
        if not candidates:
            raise ValueError("No action candidates provided")

        metrics_list = [DecisionMetrics(**c.base_scores) for c in candidates]
        scored: list[tuple[ActionCandidate, float, float, float, int]] = []
        for i, candidate in enumerate(candidates):
            mcda = self._mcda(metrics_list[i])
            sim_mean, sim_std = self._simulate(mcda)
            pareto_rank = self._pareto_rank(metrics_list, i)
            adjusted = sim_mean - 0.02 * (pareto_rank - 1)
            scored.append((candidate, adjusted, sim_mean, sim_std, pareto_rank))

        if random.random() < self.config.exploration_rate:
            chosen = random.choice(scored)
            explanation = "Exploration branch selected due to epsilon-greedy strategy"
        else:
            chosen = max(scored, key=lambda x: x[1])
            explanation = "Selected by best adjusted MCDA + Monte Carlo estimate on Pareto frontier"

        candidate, weighted, mean, std, rank = chosen
        return DecisionResult(
            action_id=candidate.id,
            weighted_score=weighted,
            pareto_rank=rank,
            simulation_mean=mean,
            simulation_std=std,
            explanation=explanation,
        )

    def adapt_weights(self, signal: LearnedSignal) -> None:
        for key, delta in signal.weight_adjustments.items():
            if key in self.weights:
                self.weights[key] = max(0.05, self.weights[key] + self.config.adaptive_learning_rate * delta)
        total = statistics.fmean(self.weights.values()) * len(self.weights)
        for key in self.weights:
            self.weights[key] /= total
        logger.info("Decision weights adapted: %s", self.weights)
