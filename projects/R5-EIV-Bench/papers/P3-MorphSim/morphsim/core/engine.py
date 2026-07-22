"""
MorphSim Core Engine — Hybrid Rigid+Deformable Dynamics
========================================================

The main simulation loop orchestrates:
  1. Rigid body dynamics (chassis, wheels, suspension) via MuJoCo
  2. Deformable body dynamics (panels, soft structures) via XPBD
  3. Two-way coupling between rigid and deformable subsystems
  4. Sensor simulation at configurable frequency
  5. Policy stepping for morphology decisions

Time stepping:
  - Physics: 1kHz (dt=1ms)
  - Sensor: 10-50Hz (configurable)
  - Policy: 10Hz (100ms decision interval)

References:
  - MuJoCo: Todorov et al., 2012
  - XPBD: Macklin et al., 2016
  - Rigid-deformable coupling: Jiang et al., 2022
"""

from __future__ import annotations
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple
from enum import Enum
from morphsim.core.rigid_solver_mujoco import RigidSolverMuJoCo
from morphsim.core.xpbd_solver import XPBDSolver
from morphsim.core.coupling_solver import CouplingSolver


class PhysicsBackend(Enum):
    MUJOCO = "mujoco"
    PYBULLET = "pybullet"  # fallback


class DeformableMethod(Enum):
    XPBD = "xpbd"
    FEM = "fem"            # for higher fidelity, slower
    MASS_SPRING = "mass_spring"  # simplest


@dataclass
class SimConfig:
    """Simulation configuration."""
    dt: float = 0.001              # Physics timestep (s)
    n_substeps: int = 4            # Solver substeps per physics step
    gravity: np.ndarray = field(default_factory=lambda: np.array([0, 0, -9.81]))

    # Rigid body settings
    physics_backend: PhysicsBackend = PhysicsBackend.MUJOCO

    # Deformable body settings
    deformable_method: DeformableMethod = DeformableMethod.XPBD
    deformable_compliance: float = 1e-6  # XPBD compliance
    deformable_damping: float = 0.99

    # Coupling
    coupling_stiffness: float = 1e4
    coupling_damping: float = 1e2

    # Sensor rates
    camera_hz: float = 30.0
    lidar_hz: float = 10.0
    imu_hz: float = 100.0
    cabin_hz: float = 10.0

    # Policy
    policy_hz: float = 10.0

    # Rendering
    render: bool = False
    render_width: int = 1920
    render_height: int = 1080

    # Differentiable
    differentiable: bool = False   # Enable JAX tracing


@dataclass
class MorphState:
    """State of a morphing vehicle at a given timestep.

    Combines rigid body state + deformable body state + actuator state.
    """
    # Rigid body (6-DOF chassis)
    pos: np.ndarray           # (3,) position
    quat: np.ndarray          # (4,) orientation quaternion
    vel: np.ndarray           # (3,) linear velocity
    ang_vel: np.ndarray       # (3,) angular velocity

    # Wheels (4 wheels × [spin_speed, steer_angle, suspension_disp])
    wheel_states: np.ndarray  # (4, 3)

    # Deformable nodes (N_nodes × 3 positions + 3 velocities)
    deform_pos: np.ndarray    # (N, 3)
    deform_vel: np.ndarray    # (N, 3)

    # Actuator states
    actuator_positions: np.ndarray   # (N_actuators,) current positions
    actuator_velocities: np.ndarray  # (N_actuators,) current velocities

    # Morphology encoding (compact representation for policy)
    morphology_code: np.ndarray  # (morph_dim,)

    # Time
    time: float = 0.0

    def to_vector(self) -> np.ndarray:
        """Flatten to 1D vector for policy input."""
        return np.concatenate([
            self.pos, self.quat, self.vel, self.ang_vel,
            self.wheel_states.flatten(),
            self.deform_pos.flatten(),
            self.actuator_positions,
            self.morphology_code,
        ])


@dataclass
class MorphAction:
    """Action from morphology-aware policy.

    Combines driving actions + morphing actions.
    """
    # Driving
    throttle: float = 0.0     # [-1, 1]
    brake: float = 0.0        # [0, 1]
    steer: float = 0.0        # [-1, 1]

    # Morphing
    actuator_targets: Optional[np.ndarray] = None  # (N_actuators,) target positions

    # Mode selection (for discrete morphology modes)
    morph_mode: Optional[int] = None  # 0=normal, 1=aero, 2=offroad, 3=compact, ...

    def to_vector(self) -> np.ndarray:
        base = np.array([self.throttle, self.brake, self.steer])
        if self.actuator_targets is not None:
            return np.concatenate([base, self.actuator_targets])
        return base


class MorphSimEngine:
    """Main MorphSim simulation engine.

    Usage:
        config = SimConfig()
        engine = MorphSimEngine(config)
        vehicle = MorphSUV(engine)

        state = engine.reset(scenario="aero_highway")
        for step in range(max_steps):
            action = policy(state)
            state, reward, done, info = engine.step(action)
            if done:
                break
    """

    def __init__(self, config: SimConfig = SimConfig()):
        self.config = config
        self._rigid_solver = None
        self._deform_solver = None
        self._coupling_solver = None
        self._sensor_manager = None
        self._vehicle = None
        self._scenario = None
        self._state = None
        self._step_count = 0

    def load_vehicle(self, vehicle: 'BaseVehicle') -> None:
        """Load a vehicle model into the engine."""
        self._vehicle = vehicle
        self._rigid_solver = self._init_rigid_solver(vehicle)
        self._deform_solver = self._init_deform_solver(vehicle)
        self._coupling_solver = self._init_coupling(vehicle)

    def load_scenario(self, scenario_name: str) -> None:
        """Load a scenario by name from the scenario registry."""
        from morphsim.scenarios.loader import ScenarioLoader
        loader = ScenarioLoader()
        self._scenario = loader.get(scenario_name)

    def reset(self, scenario: Optional[str] = None) -> MorphState:
        """Reset simulation and return initial state."""
        if scenario:
            self.load_scenario(scenario)
        assert self._vehicle is not None, "Load a vehicle first"
        assert self._scenario is not None, "Load a scenario first"

        self._step_count = 0
        self._state = MorphState(
            pos=np.zeros(3),
            quat=np.array([1.0, 0.0, 0.0, 0.0]),
            vel=np.zeros(3),
            ang_vel=np.zeros(3),
            wheel_states=np.zeros((4, 3)),
            deform_pos=np.zeros((0, 3)),
            deform_vel=np.zeros((0, 3)),
            actuator_positions=np.zeros(12),
            actuator_velocities=np.zeros(12),
            morphology_code=np.zeros(12),
            time=0.0,
        )
        return self._state

    def step(self, action: MorphAction) -> Tuple[MorphState, float, bool, dict]:
        """Advance simulation by one policy step.

        One policy step = 1/policy_hz seconds of physics simulation.

        Returns:
            state: new MorphState
            reward: scalar reward
            done: episode termination flag
            info: auxiliary information dict
        """
        assert self._state is not None, "Call reset() first"

        physics_steps_per_policy = int(
            1.0 / (self.config.policy_hz * self.config.dt)
        )

        info = {"morph_energy": 0.0, "drag": 0.0, "safety": 1.0}

        for _ in range(physics_steps_per_policy):
            # 1. Apply driving actions to rigid solver
            self._rigid_solver.apply_action(action)

            # 2. Apply morphing actions to deformable solver
            if action.actuator_targets is not None:
                self._deform_solver.set_targets(action.actuator_targets)

            # 3. Rigid body step
            self._rigid_solver.step(self.config.dt)

            # 4. Deformable body step (XPBD)
            self._deform_solver.step(self.config.dt, self.config.n_substeps)

            # 5. Two-way coupling
            coupling_forces = self._coupling_solver.compute(
                self._rigid_solver.get_state(),
                self._deform_solver.get_state(),
            )
            # coupling_forces is (on_rigid, on_deformable)
            if isinstance(coupling_forces, tuple):
                self._rigid_solver.apply_coupling(coupling_forces[0])
                self._deform_solver.apply_coupling(coupling_forces[1])
            else:
                self._rigid_solver.apply_coupling(coupling_forces["on_rigid"])
                self._deform_solver.apply_coupling(coupling_forces["on_deform"])

            self._step_count += 1

        # Update composite state
        self._state = self._compose_state()

        # Compute reward and done
        # Placeholder: real reward computed when scenario evaluator is connected
        reward = 0.0
        done = self._step_count >= 100  # 100 steps per episode
        info["step"] = self._step_count

        return self._state, reward, done, info

    def _compose_state(self) -> MorphState:
        """Compose MorphState from rigid + deformable solver states."""
        rigid_state = self._rigid_solver.get_state()
        deform_state = self._deform_solver.get_state()

        return MorphState(
            pos=rigid_state["pos"],
            quat=rigid_state["quat"],
            vel=rigid_state["vel"],
            ang_vel=rigid_state["ang_vel"],
            wheel_states=rigid_state["wheels"],
            deform_pos=deform_state["positions"],
            deform_vel=deform_state["velocities"],
            actuator_positions=deform_state["actuator_pos"],
            actuator_velocities=deform_state["actuator_vel"],
            morphology_code=self._vehicle.encode_morphology() if hasattr(self._vehicle, 'encode_morphology') else np.zeros(12),
            time=self._step_count * self.config.dt,
        )

    def _init_rigid_solver(self, vehicle):
        """Initialize rigid body solver (MuJoCo backend)."""
        # Placeholder — will connect to MuJoCo Python API
        return RigidSolverMuJoCo(vehicle.rigid_model, self.config)

    def _init_deform_solver(self, vehicle):
        """Initialize deformable body solver (XPBD)."""
        return XPBDSolver(vehicle.deformable_model, self.config)

    def _init_coupling(self, vehicle):
        """Initialize rigid-deformable coupling."""
        return CouplingSolver(
            vehicle.coupling_interface,
            self.config.coupling_stiffness,
            self.config.coupling_damping,
        )

    def _init_coupling(self, vehicle):
        """Initialize rigid-deformable coupling."""
        return CouplingSolver(
            vehicle.coupling_interface,
            self.config.coupling_stiffness,
            self.config.coupling_damping,
        )
