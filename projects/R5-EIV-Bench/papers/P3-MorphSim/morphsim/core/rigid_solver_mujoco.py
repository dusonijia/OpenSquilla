"""Rigid body dynamics using MuJoCo."""
import numpy as np
import mujoco


class RigidSolverMuJoCo:
    """MuJoCo-based rigid body dynamics solver for chassis + wheels + suspension."""

    def __init__(self, rigid_model, config):
        """Initialize MuJoCo from vehicle rigid model."""
        self.config = config
        self._build_model(rigid_model)

    def _build_model(self, rigid_model):
        """Build minimal MuJoCo XML for vehicle dynamics."""
        mass = rigid_model.get('mass', 1500.0)
        wheelbase = rigid_model.get('wheelbase', 2.8)
        track = rigid_model.get('track_width', 1.6)
        length = rigid_model.get('length', 4.7)
        width = rigid_model.get('width', 1.9)
        height = rigid_model.get('height', 1.7)
        cg = rigid_model.get('cg_height', 0.55)

        xml = f"""
        <mujoco>
            <option timestep="{self.config.dt}"/>
            <default>
                <joint limited="true" damping="2.0" stiffness="0.5"/>
                <geom contype="1" conaffinity="1"/>
            </default>
            <worldbody>
                <geom name="ground" type="plane" size="100 100 0.1"/>
                <body name="chassis" pos="0 0 {cg + 0.35}">
                    <inertial mass="{mass}" pos="0 0 0"
                               diaginertia="{mass*(length**2+height**2)/12} {mass*(width**2+height**2)/12} {mass*(length**2+width**2)/12}"/>
                    <geom type="box" size="{length/2} {width/2} {height/2}" rgba="0.2 0.3 0.5 1"/>
                    <joint name="chassis_joint" type="free"/>
                    <body name="wheel_fl" pos="{wheelbase/2} {track/2} -0.2">
                        <inertial mass="20" pos="0 0 0" diaginertia="0.5 0.5 0.5"/>
                        <geom type="cylinder" size="0.35 0.1" rgba="0.1 0.1 0.1 1"/>
                        <joint name="wheel_fl_axle" type="hinge" axis="0 1 0" range="-1e10 1e10"/>
                        <joint name="wheel_fl_steer" type="hinge" axis="0 0 1" range="-0.5 0.5"/>
                    </body>
                    <body name="wheel_fr" pos="{wheelbase/2} {-track/2} -0.2">
                        <inertial mass="20" pos="0 0 0" diaginertia="0.5 0.5 0.5"/>
                        <geom type="cylinder" size="0.35 0.1" rgba="0.1 0.1 0.1 1"/>
                        <joint name="wheel_fr_axle" type="hinge" axis="0 1 0" range="-1e10 1e10"/>
                        <joint name="wheel_fr_steer" type="hinge" axis="0 0 1" range="-0.5 0.5"/>
                    </body>
                    <body name="wheel_rl" pos="-{wheelbase/2} {track/2} -0.2">
                        <inertial mass="20" pos="0 0 0" diaginertia="0.5 0.5 0.5"/>
                        <geom type="cylinder" size="0.35 0.1" rgba="0.1 0.1 0.1 1"/>
                        <joint name="wheel_rl_axle" type="hinge" axis="0 1 0" range="-1e10 1e10"/>
                    </body>
                    <body name="wheel_rr" pos="-{wheelbase/2} {-track/2} -0.2">
                        <inertial mass="20" pos="0 0 0" diaginertia="0.5 0.5 0.5"/>
                        <geom type="cylinder" size="0.35 0.1" rgba="0.1 0.1 0.1 1"/>
                        <joint name="wheel_rr_axle" type="hinge" axis="0 1 0" range="-1e10 1e10"/>
                    </body>
                </body>
            </worldbody>
            <actuator>
                <motor name="motor_fl" joint="wheel_fl_axle" gear="100"/>
                <motor name="motor_fr" joint="wheel_fr_axle" gear="100"/>
                <motor name="motor_rl" joint="wheel_rl_axle" gear="100"/>
                <motor name="motor_rr" joint="wheel_rr_axle" gear="100"/>
                <position name="steer_fl" joint="wheel_fl_steer" kp="1000"/>
                <position name="steer_fr" joint="wheel_fr_steer" kp="1000"/>
            </actuator>
        </mujoco>
        """
        self.model = mujoco.MjModel.from_xml_string(xml)
        self.data = mujoco.MjData(self.model)

    def apply_action(self, action):
        """Apply throttle/brake/steer controls."""
        # Map to MuJoCo actuators
        throttle = max(0, action.throttle)  # [-1,1] -> [0,1]
        brake = max(0, -action.throttle) if action.throttle < 0 else action.brake
        steer = action.steer  # [-1,1]

        # Apply to motors (throttle - brake)
        motor_force = max(-500, min(500, (throttle - brake) * 500))  # Limited force
        self.data.ctrl[0] = motor_force  # front left
        self.data.ctrl[1] = motor_force  # front right
        self.data.ctrl[2] = motor_force  # rear left
        self.data.ctrl[3] = motor_force  # rear right

        # Apply steering
        self.data.ctrl[4] = steer * 0.5  # front left
        self.data.ctrl[5] = steer * 0.5  # front right

    def step(self, dt):
        """Step MuJoCo physics with stability check."""
        mujoco.mj_step(self.model, self.data, nstep=self.config.n_substeps)
        # Check for NaN and reset if unstable
        if np.any(np.isnan(self.data.qpos)) or np.any(np.isnan(self.data.qvel)):
            mujoco.mj_resetData(self.model, self.data)

    def get_state(self):
        """Extract rigid body state."""
        pos = self.data.qpos[0:3].copy()
        vel = self.data.qvel[0:3].copy()
        # Replace NaN with zeros
        pos = np.nan_to_num(pos, nan=0.0)
        vel = np.nan_to_num(vel, nan=0.0)
        return {
            "pos": pos,
            "quat": self.data.qpos[3:7].copy(),
            "vel": vel,
            "ang_vel": np.nan_to_num(self.data.qvel[3:6].copy(), nan=0.0),
            "wheels": self._get_wheel_states(),
        }

    def _get_wheel_states(self):
        """Extract wheel states [spin_speed, steer_angle, suspension_disp]."""
        wheel_states = np.zeros((4, 3))
        wheel_names = ["wheel_fl", "wheel_fr", "wheel_rl", "wheel_rr"]
        for i, name in enumerate(wheel_names):
            jid = self.model.joint(name + "_axle").id
            wheel_states[i, 0] = self.data.qvel[jid]  # spin speed
        return wheel_states

    def apply_coupling(self, forces):
        """Apply coupling forces from deformable solver."""
        # Apply external force to chassis body
        self.data.xfrc_applied[0, 0:3] = forces[0:3]  # force
        self.data.xfrc_applied[0, 3:6] = forces[3:6]  # torque