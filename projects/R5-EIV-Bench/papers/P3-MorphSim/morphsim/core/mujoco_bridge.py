"""
MorphSim — MuJoCo Bridge for Rigid Vehicle Dynamics
====================================================
Wraps MuJoCo as the rigid-body solver for the vehicle chassis,
suspension, and wheel dynamics. Provides the physics backbone
that the deformable (XPBD) layer couples into.

Architecture:
  MujocoBridge holds a MuJoCo model (MjModel) and data (MjData).
  The engine steps MuJoCo forward, then extracts body states
  (positions, velocities, forces) for the deformable solver
  and aerodynamic model to consume.

Key design:
  - MorphVehicle is built as a MuJoCo XML (MJCF) at runtime
  - Actuator commands from MorphSim map to MuJoCo actuators
  - Contact forces are extracted per-geom for coupling
  - Supports both position and torque control modes
"""

from __future__ import annotations

import enum
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    import mujoco
    from mujoco import MjModel, MjData
    HAS_MUJOCO = True
except ImportError:
    HAS_MUJOCO = False

try:
    import mujoco_py
    HAS_MUJOCO_PY = True
except ImportError:
    HAS_MUJOCO_PY = False


# ---------------------------------------------------------------------------
# Vehicle MJCF Builder
# ---------------------------------------------------------------------------

@dataclass
class ChassisParams:
    """Parameters for the vehicle chassis rigid body."""
    mass: float = 1500.0           # kg
    length: float = 4.8            # m
    width: float = 2.0             # m
    height: float = 1.4            # m
    com_height: float = 0.55       # centre of mass height
    wheelbase: float = 2.8         # m
    track_width: float = 1.6       # m
    wheel_radius: float = 0.35     # m
    wheel_mass: float = 25.0       # kg per wheel
    max_steer: float = 0.6         # rad (~34 deg)
    max_torque: float = 4000.0     # Nm per wheel
    max_brake: float = 12000.0     # N


class MorphVehicleMJCF:
    """Build a MuJoCo XML model for the morphing vehicle.

    The vehicle has:
      - Rigid chassis body
      - 4 wheel bodies with hinge joints (steer + drive)
      - Suspension via equality constraints (treated as spring-damper)
      - Morphing joint groups (for coupling with XPBD deformables):
          * roof_height   — prismatic, body z
          * body_width    — prismatic, body y
          * spoiler_angle — hinge, rear body
          * ground_clear  — prismatic, body z (ride height)
          * wheelbase_ext — prismatic, front axle x
    """

    def __init__(self, params: ChassisParams = ChassisParams()):
        self.params = params

    def build_xml(self) -> str:
        p = self.params
        return f"""<mujoco model="MorphVehicle">
  <option timestep="0.002" gravity="0 0 -9.81" integrator="RK4">
    <flag contact="enable" energy="enable"/>
  </option>

  <default>
    <joint damping="0.5" armature="0.1"/>
    <geom contype="1" conaffinity="1" friction="0.8 0.02 0.01"/>
    <motor ctrlrange="{{{{ctrl_range}}}}" ctrllimited="true"/>
  </default>

  <worldbody>
    <!-- Ground plane -->
    <geom name="ground" type="plane" size="100 100 0.1" rgba="0.4 0.4 0.4 1"
          contype="1" conaffinity="1"/>
    <light directional="true" pos="0 0 3" dir="0 0 -1"/>

    <!-- Vehicle chassis -->
    <body name="chassis" pos="0 0 {p.com_height + p.wheel_radius}">
      <freejoint name="chassis_free"/>
      <inertial pos="0 0 0" mass="{p.mass}"
                diaginertia="{p.mass*(p.height**2+p.width**2)/12:.1f}
                             {p.mass*(p.length**2+p.height**2)/12:.1f}
                             {p.mass*(p.length**2+p.width**2)/12:.1f}"/>
      <geom name="chassis_body" type="box"
            size="{p.length/2} {p.width/2} {p.height/2}" rgba="0.2 0.3 0.8 0.6"/>

      <!-- === Morphing Joints === -->
      <!-- Roof height: 0.8m → 1.3m -->
      <body name="roof" pos="0 0 {p.height/2}">
        <joint name="roof_height" type="slide" axis="0 0 1"
               range="0 0.5" damping="50"/>
        <geom name="roof_geom" type="box"
              size="{p.length*0.4} {p.width*0.45} 0.15" rgba="0.3 0.5 0.9 0.5"
              contype="1" conaffinity="1"/>
      </body>

      <!-- Body width morph: ±0.3m -->
      <body name="body_left" pos="0 {p.width/2} 0">
        <joint name="body_width_l" type="slide" axis="0 1 0"
               range="-0.3 0.0" damping="80"/>
        <geom name="side_l" type="box"
              size="{p.length*0.48} 0.05 {p.height*0.45}" rgba="0.2 0.3 0.8 0.4"/>
      </body>
      <body name="body_right" pos="0 {-p.width/2} 0">
        <joint name="body_width_r" type="slide" axis="0 1 0"
               range="0.0 0.3" damping="80"/>
        <geom name="side_r" type="box"
              size="{p.length*0.48} 0.05 {p.height*0.45}" rgba="0.2 0.3 0.8 0.4"/>
      </body>

      <!-- Spoiler angle: 0 → 60 deg -->
      <body name="spoiler" pos="{-p.length*0.45} 0 {p.height*0.3}">
        <joint name="spoiler_angle" type="hinge" axis="0 1 0"
               range="0 1.05" damping="20"/>
        <geom name="spoiler_geom" type="box"
              size="0.3 {p.width*0.4} 0.02" rgba="0.1 0.1 0.1 0.8"
              contype="0" conaffinity="0"/>
      </body>

      <!-- Ground clearance: ±0.15m -->
      <body name="undercarriage" pos="0 0 {-p.height/2}">
        <joint name="ground_clear" type="slide" axis="0 0 1"
               range="-0.15 0.15" damping="100"/>
        <geom name="under_geom" type="box"
              size="{p.length*0.45} {p.width*0.4} 0.05" rgba="0.5 0.5 0.5 0.3"
              contype="0" conaffinity="0"/>
      </body>

      <!-- === Front Axle (steerable) === -->
      <body name="front_axle" pos="{p.wheelbase/2} 0 0">
        <!-- Wheelbase extension morph -->
        <joint name="wheelbase_ext" type="slide" axis="1 0 0"
               range="0 0.4" damping="200"/>
        <body name="fl_wheel" pos="0 {p.track_width/2} {-p.com_height}">
          <joint name="fl_steer" type="hinge" axis="0 0 1" range="{-p.max_steer} {p.max_steer}"/>
          <joint name="fl_drive" type="hinge" axis="1 0 0"/>
          <geom name="fl" type="cylinder" size="{p.wheel_radius} 0.15"
                mass="{p.wheel_mass}" rgba="0.1 0.1 0.1 1"/>
        </body>
        <body name="fr_wheel" pos="0 {-p.track_width/2} {-p.com_height}">
          <joint name="fr_steer" type="hinge" axis="0 0 1" range="{-p.max_steer} {p.max_steer}"/>
          <joint name="fr_drive" type="hinge" axis="1 0 0"/>
          <geom name="fr" type="cylinder" size="{p.wheel_radius} 0.15"
                mass="{p.wheel_mass}" rgba="0.1 0.1 0.1 1"/>
        </body>
      </body>

      <!-- === Rear Axle === -->
      <body name="rear_axle" pos="{-p.wheelbase/2} 0 0">
        <body name="rl_wheel" pos="0 {p.track_width/2} {-p.com_height}">
          <joint name="rl_drive" type="hinge" axis="1 0 0"/>
          <geom name="rl" type="cylinder" size="{p.wheel_radius} 0.15"
                mass="{p.wheel_mass}" rgba="0.1 0.1 0.1 1"/>
        </body>
        <body name="rr_wheel" pos="0 {-p.track_width/2} {-p.com_height}">
          <joint name="rr_drive" type="hinge" axis="1 0 0"/>
          <geom name="rr" type="cylinder" size="{p.wheel_radius} 0.15"
                mass="{p.wheel_mass}" rgba="0.1 0.1 0.1 1"/>
        </body>
      </body>
    </body>
  </worldbody>

  <actuator>
    <!-- Drive torques -->
    <motor name="fl_torque" joint="fl_drive" gear="1" ctrlrange="{-p.max_torque} {p.max_torque}"/>
    <motor name="fr_torque" joint="fr_drive" gear="1" ctrlrange="{-p.max_torque} {p.max_torque}"/>
    <motor name="rl_torque" joint="rl_drive" gear="1" ctrlrange="{-p.max_torque} {p.max_torque}"/>
    <motor name="rr_torque" joint="rr_drive" gear="1" ctrlrange="{-p.max_torque} {p.max_torque}"/>
    <!-- Steering -->
    <motor name="fl_steer" joint="fl_steer" gear="1" ctrlrange="{-p.max_steer} {p.max_steer}"/>
    <motor name="fr_steer" joint="fr_steer" gear="1" ctrlrange="{-p.max_steer} {p.max_steer}"/>
    <!-- Brakes (velocity actuators on drive joints) -->
    <motor name="brake" gear="1" ctrlrange="0 {p.max_brake}"/>
    <!-- Morphing actuators -->
    <motor name="morph_roof"     joint="roof_height"   gear="1" ctrlrange="0 0.5"/>
    <motor name="morph_width_l"  joint="body_width_l"  gear="1" ctrlrange="-0.3 0"/>
    <motor name="morph_width_r"  joint="body_width_r"  gear="1" ctrlrange="0 0.3"/>
    <motor name="morph_spoiler"  joint="spoiler_angle" gear="1" ctrlrange="0 1.05"/>
    <motor name="morph_clear"    joint="ground_clear"  gear="1" ctrlrange="-0.15 0.15"/>
    <motor name="morph_wheelbase" joint="wheelbase_ext" gear="1" ctrlrange="0 0.4"/>
  </actuator>

  <sensor>
    <framepos name="chassis_pos" objtype="body" objname="chassis"/>
    <framequat name="chassis_quat" objtype="body" objname="chassis"/>
    <framelinvel name="chassis_vel" objtype="body" objname="chassis"/>
    <frameangvel name="chassis_omega" objtype="body" objname="chassis"/>
    <jointpos name="roof_pos"     joint="roof_height"/>
    <jointpos name="width_l_pos"  joint="body_width_l"/>
    <jointpos name="width_r_pos"  joint="body_width_r"/>
    <jointpos name="spoiler_pos"  joint="spoiler_angle"/>
    <jointpos name="clear_pos"    joint="ground_clear"/>
    <jointpos name="wb_pos"       joint="wheelbase_ext"/>
  </sensor>
</mujoco>"""


# ---------------------------------------------------------------------------
# MuJoCo Bridge
# ---------------------------------------------------------------------------

@dataclass
class MorphState:
    """Complete vehicle state extracted from MuJoCo."""
    # Chassis
    pos: np.ndarray          # (3,) world position
    quat: np.ndarray         # (4,) orientation quaternion
    vel: np.ndarray          # (3,) linear velocity
    omega: np.ndarray        # (3,) angular velocity
    # Morph joint positions
    roof_height: float
    body_width_l: float
    body_width_r: float
    spoiler_angle: float
    ground_clearance: float
    wheelbase_ext: float
    # Wheel speeds (rad/s)
    wheel_speeds: np.ndarray  # (4,) FL, FR, RL, RR
    # Contact forces
    contact_forces: Dict[str, np.ndarray]  # geom_name -> (3,) force

    @property
    def speed_kmh(self) -> float:
        return float(np.linalg.norm(self.vel) * 3.6)

    @property
    def effective_width(self) -> float:
        """Current body width including morph offset."""
        base = 2.0  # default chassis width
        return base + (self.body_width_r - self.body_width_l)

    @property
    def effective_height(self) -> float:
        """Current body height including roof morph."""
        base = 1.4
        return base + self.roof_height

    @property
    def effective_clearance(self) -> float:
        base = 0.2
        return base + self.ground_clearance


@dataclass
class MorphAction:
    """Control commands for the morphing vehicle."""
    # Drive
    drive_torque: np.ndarray = field(default_factory=lambda: np.zeros(4))  # FL FR RL RR
    steer_angle: np.ndarray = field(default_factory=lambda: np.zeros(2))   # FL FR
    brake: float = 0.0
    # Morph
    roof_target: Optional[float] = None       # 0..0.5
    width_target: Optional[float] = None      # -0.3..0 (left) / 0..0.3 (right)
    spoiler_target: Optional[float] = None    # 0..1.05 rad
    clearance_target: Optional[float] = None  # -0.15..0.15
    wheelbase_target: Optional[float] = None  # 0..0.4


class MujocoBridge:
    """MuJoCo physics bridge for MorphSim.

    Usage:
        bridge = MujocoBridge()
        bridge.reset()
        for step in range(1000):
            action = policy.compute(bridge.get_state())
            bridge.step(action)
            state = bridge.get_state()
    """

    # Actuator indices in MuJoCo model
    ACT_DRIVE = slice(0, 4)    # fl fr rl rr torque
    ACT_STEER = slice(4, 6)    # fl fr steer
    ACT_BRAKE = 6
    ACT_MORPH_ROOF = 7
    ACT_MORPH_WIDTH_L = 8
    ACT_MORPH_WIDTH_R = 9
    ACT_MORPH_SPOILER = 10
    ACT_MORPH_CLEAR = 11
    ACT_MORPH_WB = 12

    def __init__(self, vehicle_params: ChassisParams = ChassisParams()):
        if not HAS_MUJOCO and not HAS_MUJOCO_PY:
            raise ImportError(
                "MuJoCo not found. Install with: pip install mujoco  "
                "(requires MuJoCo 2.3+ with free license)"
            )
        self.vehicle_params = vehicle_params
        self._builder = MorphVehicleMJCF(vehicle_params)
        self._model: Optional[MjModel] = None
        self._data: Optional[MjData] = None

    def reset(self) -> MorphState:
        """Build model from MJCF and reset simulation."""
        xml = self._builder.build_xml()
        self._model = mujoco.MjModel.from_xml_string(xml)
        self._data = mujoco.MjData(self._model)
        mujoco.mj_forward(self._model, self._data)
        return self.get_state()

    def step(self, action: MorphAction, n_substeps: int = 5) -> MorphState:
        """Advance simulation by one control step.

        Args:
            action: Control commands.
            n_substeps: Number of physics substeps per control step.
                        At 0.002s timestep, 5 substeps = 10ms control rate (100 Hz).

        Returns:
            Updated vehicle state after stepping.
        """
        if self._data is None:
            raise RuntimeError("Call reset() before step()")

        # Apply drive torques
        ctrl = np.zeros(self._model.nu)
        ctrl[self.ACT_DRIVE] = action.drive_torque
        ctrl[self.ACT_STEER] = action.steer_angle
        ctrl[self.ACT_BRAKE] = action.brake

        # Apply morph targets (position control)
        if action.roof_target is not None:
            ctrl[self.ACT_MORPH_ROOF] = action.roof_target
        if action.width_target is not None:
            ctrl[self.ACT_MORPH_WIDTH_L] = -abs(action.width_target)
            ctrl[self.ACT_MORPH_WIDTH_R] = abs(action.width_target)
        if action.spoiler_target is not None:
            ctrl[self.ACT_MORPH_SPOILER] = action.spoiler_target
        if action.clearance_target is not None:
            ctrl[self.ACT_MORPH_CLEAR] = action.clearance_target
        if action.wheelbase_target is not None:
            ctrl[self.ACT_MORPH_WB] = action.wheelbase_target

        self._data.ctrl[:] = ctrl

        for _ in range(n_substeps):
            mujoco.mj_step(self._model, self._data)

        return self.get_state()

    def get_state(self) -> MorphState:
        """Extract full vehicle state from MuJoCo data."""
        d = self._data
        if d is None:
            raise RuntimeError("Call reset() first")

        # Sensor readings
        chassis_pos = d.sensordata[0:3].copy()
        chassis_quat = d.sensordata[3:7].copy()
        chassis_vel = d.sensordata[7:10].copy()
        chassis_omega = d.sensordata[10:13].copy()

        # Morph joint positions (from sensor data, offset by 13)
        morph_offset = 13
        roof_h = float(d.sensordata[morph_offset])
        width_l = float(d.sensordata[morph_offset + 1])
        width_r = float(d.sensordata[morph_offset + 2])
        spoiler = float(d.sensordata[morph_offset + 3])
        clearance = float(d.sensordata[morph_offset + 4])
        wb_ext = float(d.sensordata[morph_offset + 5])

        # Wheel angular velocities (from joint data)
        # Joint indices: fl_steer, fl_drive, fr_steer, fr_drive,
        #               rl_drive, rr_drive
        wheel_joints = [1, 3, 5, 6]  # drive joint qvel indices
        wheel_speeds = np.array([d.qvel[j] for j in wheel_joints])

        # Contact forces
        contact_forces = self._extract_contact_forces()

        return MorphState(
            pos=chassis_pos,
            quat=chassis_quat,
            vel=chassis_vel,
            omega=chassis_omega,
            roof_height=roof_h,
            body_width_l=width_l,
            body_width_r=width_r,
            spoiler_angle=spoiler,
            ground_clearance=clearance,
            wheelbase_ext=wb_ext,
            wheel_speeds=wheel_speeds,
            contact_forces=contact_forces,
        )

    def _extract_contact_forces(self) -> Dict[str, np.ndarray]:
        """Extract per-geom contact forces from MuJoCo contacts."""
        forces = {}
        d = self._data
        for i in range(d.ncon):
            contact = d.contact[i]
            geom1 = self._model.geom(contact.geom1).name
            geom2 = self._model.geom(contact.geom2).name
            # Force in contact frame
            c_array = np.zeros(6)
            mujoco.mj_contactForce(self._model, d, i, c_array)
            force = c_array[:3]  # normal + tangential
            name = f"{geom1}_{geom2}"
            forces[name] = force
        return forces

    def render_offscreen(self, width: int = 640, height: int = 480) -> np.ndarray:
        """Render current state to RGB array (offscreen)."""
        if self._model is None:
            raise RuntimeError("Call reset() first")
        renderer = mujoco.Renderer(self._model, height=height, width=width)
        renderer.update_scene(self._data)
        return renderer.render()

    @property
    def timestep(self) -> float:
        return self._model.opt.timestep if self._model else 0.002

    @property
    def control_freq(self) -> float:
        """Control frequency in Hz (assuming 5 substeps at 0.002s)."""
        return 1.0 / (self.timestep * 5)
