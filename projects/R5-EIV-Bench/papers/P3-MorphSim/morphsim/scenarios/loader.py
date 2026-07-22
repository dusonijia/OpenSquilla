"""MorphScenario-50 YAML-based scenario loader and runner.

Loads scenario specs from YAML/JSON, instantiates MorphSimEngine,
runs evaluations with baseline policies, and produces standardized results.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any

import numpy as np


# ──────────────────────────────────────────────────────────
# Scenario spec data structures
# ──────────────────────────────────────────────────────────

@dataclass
class TerrainSpec:
    type: str = "flat"               # flat, rough, slope, mud, sand, ice, gravel, water, stairs
    friction_coeff: float = 0.8
    roughness: float = 0.0           # 0-1
    slope_deg: float = 0.0
    obstacle_height: float = 0.0     # m
    water_depth: float = 0.0         # m
    deformability: float = 0.0       # 0=rigid, 1=soft sand/mud


@dataclass
class WindSpec:
    speed: float = 0.0               # m/s
    direction_deg: float = 0.0       # 0=headwind, 90=crosswind
    turbulence_intensity: float = 0.0 # 0-1


@dataclass
class TaskSpec:
    type: str = "drive"              # drive, park, climb, avoid, carry, swim
    target_speed: float = 20.0       # m/s
    target_distance: float = 1000.0  # m
    success_threshold: float = 0.9
    max_time: float = 60.0           # s
    waypoints: List[List[float]] = field(default_factory=list)


@dataclass
class MorphConstraints:
    allowed_morph_types: List[str] = field(default_factory=lambda: ["all"])
    max_deformation_rate: float = 0.1    # m/s
    max_energy_budget: float = 1000.0    # J
    safe_morph_zones: List[List[float]] = field(default_factory=list)  # speed ranges


@dataclass
class ScenarioSpec:
    """Complete specification for a single MorphScenario."""
    scenario_id: str = ""
    name: str = ""
    category: str = ""
    difficulty: str = "medium"        # easy, medium, hard, extreme
    duration_s: float = 30.0
    terrain: TerrainSpec = field(default_factory=TerrainSpec)
    wind: WindSpec = field(default_factory=WindSpec)
    task: TaskSpec = field(default_factory=TaskSpec)
    morph_constraints: MorphConstraints = field(default_factory=MorphConstraints)
    # Active morph params (indices into 12-dim shape vector)
    active_params: List[int] = field(default_factory=list)
    # Metric weights for scoring
    metric_weights: Dict[str, float] = field(default_factory=dict)
    # Rigid baseline values (pre-computed)
    rigid_baseline: Dict[str, float] = field(default_factory=dict)


# ──────────────────────────────────────────────────────────
# Scenario definitions: A-01, A-02, A-03, B-01, B-02, C-01
# ──────────────────────────────────────────────────────────

def _build_scenario_registry() -> Dict[str, ScenarioSpec]:
    """Build the full MorphScenario-50 registry."""
    regs = {}

    # ── A: Aerodynamic Morphing ──────────────────────────

    regs["A-01"] = ScenarioSpec(
        scenario_id="A-01", name="高速减阻", category="aerodynamic",
        difficulty="medium", duration_s=30.0,
        terrain=TerrainSpec(type="flat", friction_coeff=0.85, roughness=0.02),
        wind=WindSpec(speed=0.0, direction_deg=0.0, turbulence_intensity=0.05),
        task=TaskSpec(type="drive", target_speed=33.3, target_distance=1000.0,
                      success_threshold=0.9, max_time=30.0),
        morph_constraints=MorphConstraints(
            allowed_morph_types=["aerodynamic"],
            max_deformation_rate=0.05, max_energy_budget=500.0,
            safe_morph_zones=[[0, 10], [25, 40]]
        ),
        active_params=[1, 5, 8, 9],  # body_length, wheel_base, roof_angle, spoiler_angle
        metric_weights={
            "drag_coefficient": 0.35, "fuel_efficiency": 0.25,
            "speed_maintenance": 0.20, "ride_comfort": 0.10,
            "energy_cost": 0.10
        },
        rigid_baseline={"drag_coefficient": 0.32, "fuel_efficiency": 7.2,
                        "speed_maintenance": 0.85, "ride_comfort": 0.78}
    )

    regs["A-02"] = ScenarioSpec(
        scenario_id="A-02", name="侧风稳定", category="aerodynamic",
        difficulty="medium", duration_s=25.0,
        terrain=TerrainSpec(type="flat", friction_coeff=0.85),
        wind=WindSpec(speed=15.0, direction_deg=90.0, turbulence_intensity=0.3),
        task=TaskSpec(type="drive", target_speed=25.0, target_distance=800.0,
                      success_threshold=0.85, max_time=32.0),
        morph_constraints=MorphConstraints(
            allowed_morph_types=["aerodynamic", "suspension"],
            max_deformation_rate=0.08, max_energy_budget=600.0,
            safe_morph_zones=[[0, 35]]
        ),
        active_params=[3, 8, 10, 11],  # body_height, roof_angle, side_cam, susp_stiff
        metric_weights={
            "lateral_stability": 0.35, "drag_coefficient": 0.20,
            "path_deviation": 0.25, "ride_comfort": 0.20
        },
        rigid_baseline={"lateral_stability": 0.62, "drag_coefficient": 0.35,
                        "path_deviation": 0.45, "ride_comfort": 0.55}
    )

    regs["A-03"] = ScenarioSpec(
        scenario_id="A-03", name="尾随降阻(车队)", category="aerodynamic",
        difficulty="hard", duration_s=40.0,
        terrain=TerrainSpec(type="flat", friction_coeff=0.85),
        wind=WindSpec(speed=0.0, turbulence_intensity=0.02),
        task=TaskSpec(type="drive", target_speed=28.0, target_distance=1200.0,
                      success_threshold=0.88, max_time=43.0),
        morph_constraints=MorphConstraints(
            allowed_morph_types=["aerodynamic"],
            max_deformation_rate=0.05, max_energy_budget=400.0,
            safe_morph_zones=[[20, 40]]
        ),
        active_params=[4, 5, 8, 9],  # overhang_front, overhang_rear, roof_angle, spoiler
        metric_weights={
            "drag_coefficient": 0.30, "following_distance_safety": 0.30,
            "fuel_efficiency": 0.25, "ride_comfort": 0.15
        },
        rigid_baseline={"drag_coefficient": 0.28, "following_distance_safety": 0.90,
                        "fuel_efficiency": 8.1, "ride_comfort": 0.75}
    )

    # ── B: Terrain Adaptation ────────────────────────────

    regs["B-01"] = ScenarioSpec(
        scenario_id="B-01", name="越野地形通过", category="terrain",
        difficulty="hard", duration_s=45.0,
        terrain=TerrainSpec(type="rough", friction_coeff=0.55, roughness=0.7,
                           obstacle_height=0.25, deformability=0.3),
        wind=WindSpec(speed=0.0),
        task=TaskSpec(type="climb", target_speed=8.0, target_distance=200.0,
                      success_threshold=0.85, max_time=45.0),
        morph_constraints=MorphConstraints(
            allowed_morph_types=["suspension", "chassis"],
            max_deformation_rate=0.15, max_energy_budget=800.0,
            safe_morph_zones=[[0, 15]]
        ),
        active_params=[0, 5, 7, 10, 11],  # ground_clearance, overhang_front, overhang_rear, susp, track
        metric_weights={
            "terrain_completion_rate": 0.30, "avg_speed": 0.20,
            "stability_margin": 0.25, "energy_cost": 0.15,
            "body_damage": 0.10
        },
        rigid_baseline={"terrain_completion_rate": 0.45, "avg_speed": 4.2,
                        "stability_margin": 0.35, "body_damage": 0.65}
    )

    regs["B-02"] = ScenarioSpec(
        scenario_id="B-02", name="30°坡道攀爬", category="terrain",
        difficulty="hard", duration_s=35.0,
        terrain=TerrainSpec(type="slope", friction_coeff=0.6, slope_deg=30.0),
        wind=WindSpec(speed=5.0, direction_deg=0.0),
        task=TaskSpec(type="climb", target_speed=5.0, target_distance=80.0,
                      success_threshold=0.80, max_time=35.0),
        morph_constraints=MorphConstraints(
            allowed_morph_types=["suspension", "chassis", "aerodynamic"],
            max_deformation_rate=0.12, max_energy_budget=1200.0,
            safe_morph_zones=[[0, 10]]
        ),
        active_params=[0, 4, 5, 10, 11],  # clearance, overhangs, susp, track
        metric_weights={
            "climb_success": 0.35, "slip_ratio": 0.25,
            "energy_cost": 0.20, "stability_margin": 0.20
        },
        rigid_baseline={"climb_success": 0.40, "slip_ratio": 0.55,
                        "energy_cost": 850.0, "stability_margin": 0.30}
    )

    regs["B-03"] = ScenarioSpec(
        scenario_id="B-03", name="泥地脱困", category="terrain",
        difficulty="hard", duration_s=50.0,
        terrain=TerrainSpec(type="mud", friction_coeff=0.25, roughness=0.4,
                           deformability=0.8),
        wind=WindSpec(speed=0.0),
        task=TaskSpec(type="drive", target_speed=3.0, target_distance=50.0,
                      success_threshold=0.75, max_time=50.0),
        morph_constraints=MorphConstraints(
            allowed_morph_types=["suspension", "chassis", "wheel"],
            max_deformation_rate=0.10, max_energy_budget=1500.0,
            safe_morph_zones=[[0, 5]]
        ),
        active_params=[0, 7, 10, 11],
        metric_weights={
            "escape_success": 0.40, "time_to_escape": 0.25,
            "energy_cost": 0.20, "stuck_duration": 0.15
        },
        rigid_baseline={"escape_success": 0.25, "time_to_escape": 42.0,
                        "stuck_duration": 28.0}
    )

    # ── C: Space Reconfiguration ─────────────────────────

    regs["C-01"] = ScenarioSpec(
        scenario_id="C-01", name="窄道侧向压缩通过", category="spatial",
        difficulty="medium", duration_s=20.0,
        terrain=TerrainSpec(type="flat", friction_coeff=0.85),
        wind=WindSpec(speed=0.0),
        task=TaskSpec(type="drive", target_speed=5.0, target_distance=30.0,
                      success_threshold=0.90, max_time=20.0),
        morph_constraints=MorphConstraints(
            allowed_morph_types=["body_compression"],
            max_deformation_rate=0.08, max_energy_budget=300.0,
            safe_morph_zones=[[0, 8]]
        ),
        active_params=[2, 4, 10],  # body_width, overhang, side_cam_angle
        metric_weights={
            "passage_completion": 0.35, "min_clearance": 0.25,
            "energy_cost": 0.20, "speed_maintenance": 0.20
        },
        rigid_baseline={"passage_completion": 0.30, "min_clearance": -0.05,
                        "speed_maintenance": 0.20}
    )

    regs["C-02"] = ScenarioSpec(
        scenario_id="C-02", name="低矮限高通过", category="spatial",
        difficulty="hard", duration_s=18.0,
        terrain=TerrainSpec(type="flat", friction_coeff=0.85),
        wind=WindSpec(speed=0.0),
        task=TaskSpec(type="drive", target_speed=8.0, target_distance=25.0,
                      success_threshold=0.88, max_time=18.0),
        morph_constraints=MorphConstraints(
            allowed_morph_types=["body_compression", "suspension"],
            max_deformation_rate=0.06, max_energy_budget=250.0,
            safe_morph_zones=[[0, 12]]
        ),
        active_params=[0, 3, 8],  # ground_clearance, body_height, roof_angle
        metric_weights={
            "clearance_achievement": 0.40, "speed_maintenance": 0.25,
            "energy_cost": 0.20, "ride_comfort": 0.15
        },
        rigid_baseline={"clearance_achievement": 0.35, "speed_maintenance": 0.15,
                        "ride_comfort": 0.60}
    )

    # ── D: Safety Morphing ───────────────────────────────

    regs["D-01"] = ScenarioSpec(
        scenario_id="D-01", name="前方碰撞吸能变形", category="safety",
        difficulty="extreme", duration_s=5.0,
        terrain=TerrainSpec(type="flat", friction_coeff=0.85),
        wind=WindSpec(speed=0.0),
        task=TaskSpec(type="avoid", target_speed=15.0, target_distance=5.0,
                      success_threshold=0.70, max_time=2.0),
        morph_constraints=MorphConstraints(
            allowed_morph_types=["crumple", "suspension"],
            max_deformation_rate=0.50, max_energy_budget=2000.0,
            safe_morph_zones=[]
        ),
        active_params=[4, 5, 6, 8],  # overhangs, roof, body_length
        metric_weights={
            "occupant_safety": 0.45, "deceleration_peak": 0.25,
            "survival_space": 0.20, "energy_absorbed": 0.10
        },
        rigid_baseline={"occupant_safety": 0.55, "deceleration_peak": 45.0,
                        "survival_space": 0.40}
    )

    # ── E: Compact Multi-function ────────────────────────

    regs["E-01"] = ScenarioSpec(
        scenario_id="E-01", name="紧凑侧方停车", category="compact",
        difficulty="hard", duration_s=25.0,
        terrain=TerrainSpec(type="flat", friction_coeff=0.85),
        wind=WindSpec(speed=0.0),
        task=TaskSpec(type="park", target_speed=2.0, target_distance=5.0,
                      success_threshold=0.85, max_time=25.0),
        morph_constraints=MorphConstraints(
            allowed_morph_types=["body_compression"],
            max_deformation_rate=0.06, max_energy_budget=200.0,
            safe_morph_zones=[[0, 3]]
        ),
        active_params=[2, 3, 4, 6],  # width, height, overhangs
        metric_weights={
            "parking_success": 0.40, "space_efficiency": 0.30,
            "time_to_park": 0.15, "energy_cost": 0.15
        },
        rigid_baseline={"parking_success": 0.35, "space_efficiency": 0.50,
                        "time_to_park": 22.0}
    )

    # ── F: Weather Response ──────────────────────────────

    regs["F-01"] = ScenarioSpec(
        scenario_id="F-01", name="暴雨防侧滑", category="weather",
        difficulty="extreme", duration_s=30.0,
        terrain=TerrainSpec(type="flat", friction_coeff=0.35, roughness=0.1,
                           water_depth=0.03),
        wind=WindSpec(speed=10.0, direction_deg=45.0, turbulence_intensity=0.4),
        task=TaskSpec(type="drive", target_speed=20.0, target_distance=600.0,
                      success_threshold=0.80, max_time=30.0),
        morph_constraints=MorphConstraints(
            allowed_morph_types=["suspension", "aerodynamic"],
            max_deformation_rate=0.08, max_energy_budget=500.0,
            safe_morph_zones=[[0, 25]]
        ),
        active_params=[0, 10, 11, 8],  # clearance, susp, track, roof
        metric_weights={
            "hydroplaning_resistance": 0.30, "lateral_stability": 0.25,
            "speed_maintenance": 0.25, "visibility": 0.20
        },
        rigid_baseline={"hydroplaning_resistance": 0.40, "lateral_stability": 0.42,
                        "speed_maintenance": 0.50}
    )

    # ── G: Payload Adaptation ────────────────────────────

    regs["G-01"] = ScenarioSpec(
        scenario_id="G-01", name="重载2T底盘调平", category="payload",
        difficulty="medium", duration_s=20.0,
        terrain=TerrainSpec(type="flat", friction_coeff=0.80),
        wind=WindSpec(speed=0.0),
        task=TaskSpec(type="carry", target_speed=15.0, target_distance=400.0,
                      success_threshold=0.88, max_time=27.0),
        morph_constraints=MorphConstraints(
            allowed_morph_types=["suspension", "chassis"],
            max_deformation_rate=0.10, max_energy_budget=600.0,
            safe_morph_zones=[[0, 20]]
        ),
        active_params=[0, 7, 10, 11],  # clearance, overhang_rear, susp, track
        metric_weights={
            "ride_height_maintenance": 0.30, "stability_margin": 0.25,
            "ride_comfort": 0.25, "energy_cost": 0.20
        },
        rigid_baseline={"ride_height_maintenance": 0.45, "stability_margin": 0.40,
                        "ride_comfort": 0.35}
    )

    # ── H: Multi-modal Locomotion ────────────────────────

    regs["H-01"] = ScenarioSpec(
        scenario_id="H-01", name="轮腿混合越障", category="multimodal",
        difficulty="extreme", duration_s=40.0,
        terrain=TerrainSpec(type="rough", friction_coeff=0.50, roughness=0.8,
                           obstacle_height=0.50),
        wind=WindSpec(speed=0.0),
        task=TaskSpec(type="climb", target_speed=3.0, target_distance=50.0,
                      success_threshold=0.70, max_time=40.0),
        morph_constraints=MorphConstraints(
            allowed_morph_types=["suspension", "chassis", "wheel", "leg"],
            max_deformation_rate=0.20, max_energy_budget=2000.0,
            safe_morph_zones=[[0, 5]]
        ),
        active_params=[0, 1, 5, 7, 10, 11],  # clearance, length, overhangs, susp, track
        metric_weights={
            "obstacle_completion": 0.35, "mode_transition_smoothness": 0.25,
            "energy_cost": 0.20, "stability_margin": 0.20
        },
        rigid_baseline={"obstacle_completion": 0.20, "mode_transition_smoothness": 0.0,
                        "energy_cost": 1800.0, "stability_margin": 0.15}
    )

    return regs


# ──────────────────────────────────────────────────────────
# Scenario Loader
# ──────────────────────────────────────────────────────────

class ScenarioLoader:
    """Load and manage MorphScenario-50 specifications."""

    _registry: Dict[str, ScenarioSpec] = {}

    def __init__(self, custom_path: Optional[str] = None):
        self._registry = _build_scenario_registry()
        if custom_path:
            self._load_custom(custom_path)

    def _load_custom(self, path: str):
        """Load custom scenario specs from JSON/YAML file."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Custom scenarios not found: {path}")
        with open(p) as f:
            data = json.load(f) if p.suffix == ".json" else self._parse_yaml(f)
        for sid, spec_data in data.items():
            terrain = TerrainSpec(**spec_data.get("terrain", {}))
            wind = WindSpec(**spec_data.get("wind", {}))
            task = TaskSpec(**spec_data.get("task", {}))
            morph = MorphConstraints(**spec_data.get("morph_constraints", {}))
            self._registry[sid] = ScenarioSpec(
                scenario_id=sid,
                name=spec_data.get("name", sid),
                category=spec_data.get("category", "custom"),
                difficulty=spec_data.get("difficulty", "medium"),
                duration_s=spec_data.get("duration_s", 30.0),
                terrain=terrain, wind=wind, task=task,
                morph_constraints=morph,
                active_params=spec_data.get("active_params", []),
                metric_weights=spec_data.get("metric_weights", {}),
                rigid_baseline=spec_data.get("rigid_baseline", {}),
            )

    def get(self, scenario_id: str) -> ScenarioSpec:
        if scenario_id not in self._registry:
            raise KeyError(f"Scenario {scenario_id} not found. "
                          f"Available: {list(self._registry.keys())}")
        return self._registry[scenario_id]

    def list_scenarios(self, category: Optional[str] = None) -> List[str]:
        ids = list(self._registry.keys())
        if category:
            ids = [sid for sid in ids
                   if self._registry[sid].category == category]
        return ids

    def list_categories(self) -> Dict[str, int]:
        cats = {}
        for spec in self._registry.values():
            cats[spec.category] = cats.get(spec.category, 0) + 1
        return cats

    def to_json(self, path: str):
        """Export all specs to JSON."""
        data = {sid: asdict(spec) for sid, spec in self._registry.items()}
        with open(path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def __len__(self):
        return len(self._registry)

    def __repr__(self):
        cats = self.list_categories()
        return f"ScenarioLoader({len(self)} scenarios: {cats})"


# ──────────────────────────────────────────────────────────
# Scenario Runner (integration with MorphSimEngine)
# ──────────────────────────────────────────────────────────

class ScenarioRunner:
    """Run a scenario spec against a policy and collect metrics."""

    def __init__(self, engine_config: Optional[Dict] = None):
        self.engine_config = engine_config or {}

    def run_single(
        self,
        spec: ScenarioSpec,
        policy,  # Any policy with .act(obs) -> action
        seed: int = 42,
        render: bool = False,
    ) -> Dict[str, Any]:
        """Run one episode of a scenario.

        Returns dict with metrics, morph_history, and metadata.
        """
        np.random.seed(seed)

        # Build env from spec (placeholder — connects to MorphSimEngine)
        env_state = self._init_env(spec)

        obs = env_state["observation"]
        total_reward = 0.0
        morph_history = []
        metrics = {k: 0.0 for k in spec.metric_weights}
        step = 0
        done = False
        info = {}

        while not done and step < int(spec.duration_s / 0.02):
            action = policy.act(obs)
            env_state = self._step_env(env_state, action, spec)
            obs = env_state["observation"]
            done = env_state["done"]
            info = env_state.get("info", {})

            morph_history.append(env_state.get("morph_params", []).copy())
            total_reward += env_state.get("reward", 0.0)
            step += 1

        # Compute final metrics from info
        results = {
            "scenario_id": spec.scenario_id,
            "scenario_name": spec.name,
            "category": spec.category,
            "difficulty": spec.difficulty,
            "total_steps": step,
            "total_reward": total_reward,
            "done": done,
            "morph_history": morph_history,
            "metrics": info.get("metrics", metrics),
            "seed": seed,
        }
        return results

    def run_benchmark(
        self,
        spec: ScenarioSpec,
        policies: Dict[str, Any],
        n_runs: int = 20,
    ) -> Dict[str, Dict[str, Any]]:
        """Run multiple policies on a scenario, n_runs each.

        Returns {policy_name: {mean_metrics, std_metrics, all_results}}.
        """
        all_results = {}
        for pname, policy in policies.items():
            runs = []
            for i in range(n_runs):
                result = self.run_single(spec, policy, seed=42 + i)
                runs.append(result)

            # Aggregate metrics
            metric_keys = list(spec.metric_weights.keys())
            agg = {}
            for mk in metric_keys:
                vals = [r["metrics"].get(mk, 0.0) for r in runs]
                agg[f"{mk}_mean"] = float(np.mean(vals))
                agg[f"{mk}_std"] = float(np.std(vals))

            agg["completion_rate"] = sum(1 for r in runs if r["done"]) / n_runs
            agg["mean_reward"] = float(np.mean([r["total_reward"] for r in runs]))

            all_results[pname] = {
                "mean_metrics": agg,
                "all_runs": runs,
            }
        return all_results

    def _init_env(self, spec: ScenarioSpec) -> Dict:
        """Initialize simulation environment from spec (placeholder)."""
        return {
            "observation": np.zeros(64),  # placeholder obs
            "done": False,
            "morph_params": np.zeros(12),
            "info": {},
        }

    def _step_env(self, state: Dict, action: np.ndarray, spec: ScenarioSpec) -> Dict:
        """Step the environment (placeholder — connects to MorphSimEngine)."""
        # In production: engine.step(action)
        new_state = state.copy()
        new_state["observation"] = np.random.randn(64) * 0.01
        new_state["morph_params"] = action[:12] if len(action) >= 12 else np.zeros(12)
        new_state["reward"] = 0.0
        new_state["done"] = False
        return new_state


# ──────────────────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────────────────

def main():
    """Quick demo: load scenarios and print registry."""
    loader = ScenarioLoader()
    print(f"MorphScenario Registry: {loader}")
    print(f"\nCategories: {loader.list_categories()}")
    print(f"\n--- A-01: 高速减阻 ---")
    spec = loader.get("A-01")
    print(f"  Terrain: {spec.terrain}")
    print(f"  Wind: {spec.wind}")
    print(f"  Task: {spec.task}")
    print(f"  Morph constraints: {spec.morph_constraints}")
    print(f"  Active params: {spec.active_params}")
    print(f"  Metric weights: {spec.metric_weights}")
    print(f"  Rigid baseline: {spec.rigid_baseline}")

    # Export to JSON
    out_path = Path(__file__).parent / "scenario_registry.json"
    loader.to_json(str(out_path))
    print(f"\n✅ Exported to {out_path}")

    # Quick run demo
    from morphsim.baselines.policies import RigidBaselinePolicy
    runner = ScenarioRunner()
    policy = RigidBaselinePolicy()
    result = runner.run_single(spec, policy, seed=42)
    print(f"\n--- A-01 Rigid Baseline Run ---")
    print(f"  Steps: {result['total_steps']}, Done: {result['done']}")


if __name__ == "__main__":
    main()
