"""MorphSim: A Differentiable Simulation Framework for Adaptive Morphology Vehicles.

Part of R5 EIV-Bench — Embodied Intelligent Vehicle Evaluation Benchmark.
"""

from morphsim.core.engine import MorphSimEngine, SimConfig
from morphsim.core.vehicle import MorphableVehicle, DeformableRegion, MorphMode
from morphsim.core.scenarios import MorphScenario, ScenarioCategory, Difficulty
from morphsim.core.actuators import ActuatorType, PneumaticMuscle, ShapeMemoryAlloy, PiezoActuator
from morphsim.core.differentiable import DifferentiableMorphSim
from morphsim.core.mujoco_bridge import MujocoBridge, MorphVehicleMJCF, ChassisParams
from morphsim.core.xpbd_solver import XPBDSolver

__version__ = "0.1.0"
__all__ = [
    "MorphSimEngine",
    "SimConfig",
    "MorphableVehicle",
    "DeformableRegion",
    "MorphMode",
    "MorphScenario",
    "ScenarioCategory",
    "Difficulty",
    "ActuatorType",
    "PneumaticMuscle",
    "ShapeMemoryAlloy",
    "PiezoActuator",
    "DifferentiableMorphSim",
    "MujocoBridge",
    "MorphVehicleMJCF",
    "ChassisParams",
    "XPBDSolver",
]
