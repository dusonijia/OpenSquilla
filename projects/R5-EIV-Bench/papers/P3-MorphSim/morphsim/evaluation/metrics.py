"""MorphSim evaluation and metrics for EIV-Bench A-dimension."""
from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class MorphMetrics:
    """Metrics for a single morph-adaptation episode."""
    # Performance
    task_success: bool = False
    task_reward: float = 0.0
    completion_time: float = 0.0

    # Efficiency
    energy_consumed: float = 0.0           # Joules
    morph_energy: float = 0.0              # Energy spent on shape change
    locomotion_energy: float = 0.0         # Energy spent on locomotion
    energy_efficiency: float = 0.0         # task_reward / energy_consumed

    # Morph quality
    morph_smoothness: float = 0.0          # 1.0 = perfectly smooth transition
    morph_count: int = 0                   # Number of morph actions taken
    avg_morph_amplitude: float = 0.0       # Average shape change magnitude
    max_deformation: float = 0.0           # Peak deformation ratio

    # Safety
    collision_count: int = 0
    stability_margin: float = 0.0          # Min distance to tip-over
    tip_over_event: bool = False
    self_intersection: bool = False

    # Aerodynamics (when applicable)
    drag_coefficient: float = 0.0
    downforce_coefficient: float = 0.0
    lift_to_drag: float = 0.0

    # Comparisons
    rigid_baseline_reward: float = 0.0     # Same task with rigid body
    improvement_over_rigid: float = 0.0    # (reward - rigid) / |rigid|


@dataclass
class BenchmarkResult:
    """Aggregated benchmark result across scenarios."""
    scenario_name: str = ""
    scenario_category: str = ""            # One of 8 categories
    num_episodes: int = 0
    success_rate: float = 0.0
    avg_reward: float = 0.0
    avg_energy_efficiency: float = 0.0
    avg_morph_smoothness: float = 0.0
    avg_improvement_over_rigid: float = 0.0
    safety_violation_rate: float = 0.0
    per_episode_metrics: List[MorphMetrics] = field(default_factory=list)


class MorphEvaluator:
    """Evaluate morph-adaptive policies across EIV-Bench A-scenarios."""

    # Safety thresholds — any violation = episode failure
    MAX_DEFORMATION_RATIO = 0.6        # Shape can't change more than 60%
    MAX_MORPH_RATE = 2.0               # rad/s for hinge joints
    MAX_ENERGY_BUDGET = 1e5            # Joules
    MIN_STABILITY_MARGIN = 0.05        # meters from tip-over

    def __init__(self, safety_veto: bool = True):
        """
        Args:
            safety_veto: If True, any safety violation resets reward to 0
                         (EIV-Bench safety veto mechanism).
        """
        self.safety_veto = safety_veto

    def compute_episode_metrics(
        self,
        rewards: List[float],
        morph_actions: List[np.ndarray],
        energy_log: List[Dict],
        collision_flags: List[bool],
        stability_log: List[float],
        aero_log: Optional[List[Dict]] = None,
        rigid_baseline_reward: float = 0.0,
        dt: float = 0.02,
    ) -> MorphMetrics:
        """Compute all metrics for a single episode."""
        m = MorphMetrics()

        # Task performance
        m.task_reward = sum(rewards)
        m.task_success = rewards[-1] > 0 if rewards else False
        m.completion_time = len(rewards) * dt

        # Energy
        if energy_log:
            m.morph_energy = sum(e.get("morph_energy", 0) for e in energy_log)
            m.locomotion_energy = sum(e.get("loco_energy", 0) for e in energy_log)
            m.energy_consumed = m.morph_energy + m.locomotion_energy
            m.energy_efficiency = (
                m.task_reward / m.energy_consumed
                if m.energy_consumed > 0 else 0.0
            )

        # Morph quality
        if morph_actions:
            m.morph_count = sum(1 for a in morph_actions if np.linalg.norm(a) > 1e-6)
            diffs = [np.linalg.norm(morph_actions[i] - morph_actions[i-1])
                     for i in range(1, len(morph_actions))]
            m.morph_smoothness = 1.0 / (1.0 + np.mean(diffs)) if diffs else 1.0
            amps = [np.linalg.norm(a) for a in morph_actions]
            m.avg_morph_amplitude = np.mean(amps) if amps else 0.0
            m.max_deformation = max(amps) if amps else 0.0

        # Safety
        m.collision_count = sum(collision_flags)
        m.stability_margin = min(stability_log) if stability_log else 0.0
        m.tip_over_event = m.stability_margin < self.MIN_STABILITY_MARGIN
        m.self_intersection = m.max_deformation > self.MAX_DEFORMATION_RATIO

        # Aerodynamics
        if aero_log:
            m.drag_coefficient = np.mean([a.get("Cd", 0) for a in aero_log])
            m.downforce_coefficient = np.mean([a.get("Cl", 0) for a in aero_log])
            m.lift_to_drag = (
                m.downforce_coefficient / m.drag_coefficient
                if m.drag_coefficient > 0 else 0.0
            )

        # Comparison
        m.rigid_baseline_reward = rigid_baseline_reward
        if rigid_baseline_reward != 0:
            m.improvement_over_rigid = (
                (m.task_reward - rigid_baseline_reward) / abs(rigid_baseline_reward)
            )

        # Safety veto
        if self.safety_veto and self._has_safety_violation(m):
            m.task_reward = 0.0
            m.task_success = False

        return m

    def _has_safety_violation(self, m: MorphMetrics) -> bool:
        return (
            m.tip_over_event
            or m.self_intersection
            or m.collision_count > 0
        )

    def aggregate_benchmark(
        self,
        scenario_name: str,
        scenario_category: str,
        episode_metrics: List[MorphMetrics],
    ) -> BenchmarkResult:
        """Aggregate per-episode metrics into a benchmark result."""
        if not episode_metrics:
            return BenchmarkResult(
                scenario_name=scenario_name,
                scenario_category=scenario_category,
            )

        br = BenchmarkResult(
            scenario_name=scenario_name,
            scenario_category=scenario_category,
            num_episodes=len(episode_metrics),
            per_episode_metrics=episode_metrics,
        )
        n = len(episode_metrics)
        br.success_rate = sum(m.task_success for m in episode_metrics) / n
        br.avg_reward = np.mean([m.task_reward for m in episode_metrics])
        br.avg_energy_efficiency = np.mean([m.energy_efficiency for m in episode_metrics])
        br.avg_morph_smoothness = np.mean([m.morph_smoothness for m in episode_metrics])
        br.avg_improvement_over_rigid = np.mean(
            [m.improvement_over_rigid for m in episode_metrics]
        )
        br.safety_violation_rate = sum(
            self._has_safety_violation(m) for m in episode_metrics
        ) / n

        return br

    @staticmethod
    def format_leaderboard(results: List[BenchmarkResult]) -> str:
        """Format results as a leaderboard table."""
        lines = [
            f"{'Scenario':<30} {'Cat':<8} {'SR':>5} {'Reward':>8} "
            f"{'Eff':>6} {'Impr%':>7} {'Safe%':>6}",
            "-" * 75,
        ]
        for r in results:
            lines.append(
                f"{r.scenario_name:<30} {r.scenario_category:<8} "
                f"{r.success_rate:>5.2f} {r.avg_reward:>8.2f} "
                f"{r.avg_energy_efficiency:>6.3f} "
                f"{r.avg_improvement_over_rigid*100:>6.1f}% "
                f"{(1-r.safety_violation_rate)*100:>5.1f}%"
            )
        return "\n".join(lines)
