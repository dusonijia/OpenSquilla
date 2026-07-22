"""MorphSim Vehicle Model — Morphable vehicle with rigid + deformable components."""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np


class MorphMode(Enum):
    """Vehicle morphology modes."""
    STANDARD = "standard"           # Default configuration
    AERO_DYNAMIC = "aero"           # Low-drag aerodynamic shape
    OFFROAD = "offroad"             # High ground clearance, wide stance
    COMPACT = "compact"             # Reduced footprint for parking
    SAFETY = "safety"               # Crumple zones engaged, impact absorption
    AMPHIBIOUS = "amphibious"       # Water traversal mode
    CARGO = "cargo"                 # Extended cargo capacity
    WEATHER = "weather"             # Snow/rain adaptation


@dataclass
class DeformableRegion:
    """A deformable region of the vehicle body.
    
    Attributes:
        name: Region identifier (e.g., "front_bumper", "roof_panel")
        vertices: Nx3 array of vertex positions in body frame
        faces: Mx3 array of triangle face indices
        rest_positions: Nx3 original vertex positions
        material: Material properties (Young's modulus, Poisson ratio, density)
        actuator_id: Linked actuator for active deformation
        max_deformation: Maximum allowed deformation (meters)
        min_deformation: Minimum allowed deformation (compression)
    """
    name: str
    vertices: np.ndarray
    faces: np.ndarray
    rest_positions: np.ndarray
    material: Dict = field(default_factory=lambda: {
        "youngs_modulus": 2.0e9,    # Pa (steel-like baseline)
        "poisson_ratio": 0.3,
        "density": 7800.0,          # kg/m³
        "damping": 0.05,            # Rayleigh damping coefficient
    })
    actuator_id: Optional[str] = None
    max_deformation: float = 0.15   # 15cm max
    min_deformation: float = -0.10  # 10cm compression

    @property
    def n_vertices(self) -> int:
        return self.vertices.shape[0]

    @property
    def n_faces(self) -> int:
        return self.faces.shape[0]

    def compute_strain(self) -> np.ndarray:
        """Compute Green-Lagrange strain from current vs rest positions."""
        displacement = self.vertices - self.rest_positions
        # Simplified per-vertex strain magnitude
        strain = np.linalg.norm(displacement, axis=1) / (np.linalg.norm(
            self.rest_positions - self.rest_positions.mean(axis=0), axis=1
        ) + 1e-8)
        return strain

    def compute_stress(self) -> np.ndarray:
        """Compute von Mises stress from strain using material model."""
        strain = self.compute_strain()
        E = self.material["youngs_modulus"]
        nu = self.material["poisson_ratio"]
        # Simplified linear elastic: σ = E * ε / (1 - ν²)
        stress = E * strain / (1 - nu ** 2)
        return stress


@dataclass
class MorphableVehicle:
    """Complete morphable vehicle model with rigid chassis + deformable regions.
    
    The vehicle consists of:
    - A rigid chassis (main body, powertrain)
    - Multiple deformable regions (body panels, bumpers, suspension)
    - Active actuators that drive morphological changes
    - Sensor mounts that must be tracked through deformations
    
    Vehicle parameters reference a mid-size SUV:
    - Mass: ~1800 kg
    - Length: 4.7m, Width: 1.9m, Height: 1.7m
    - Wheelbase: 2.8m
    """
    # --- Vehicle identity ---
    name: str = "MorphVehicle-SUV"
    vehicle_class: str = "midsize_suv"
    
    # --- Rigid body parameters ---
    mass: float = 1800.0              # kg
    wheelbase: float = 2.8            # m
    track_width: float = 1.6          # m
    length: float = 4.7               # m
    width: float = 1.9                # m
    height: float = 1.7               # m
    cg_height: float = 0.55           # Center of gravity height (m)
    
    # --- Deformable regions ---
    regions: Dict[str, DeformableRegion] = field(default_factory=dict)
    
    # --- Current morphological state ---
    current_mode: MorphMode = MorphMode.STANDARD
    mode_blend_weights: Dict[MorphMode, float] = field(default_factory=lambda: {
        MorphMode.STANDARD: 1.0
    })
    
    # --- Sensor mounts (tracked through deformation) ---
    sensor_mounts: Dict[str, np.ndarray] = field(default_factory=dict)
    
    # --- Performance constraints ---
    max_transition_time: float = 5.0   # seconds for full mode transition
    max_power_consumption: float = 500  # watts for actuation
    
    @property
    def rigid_model(self):
        """Return rigid body model parameters for the solver."""
        return {
            "mass": 1500.0,
            "wheelbase": self.wheelbase,
            "track_width": self.track_width,
            "length": self.length,
            "width": self.width,
            "height": self.height,
            "cg_height": self.cg_height,
        }
    
    @property
    def deformable_model(self):
        """Return deformable regions for the XPBD solver."""
        return list(self.regions.values())
    
    @property
    def coupling_interface(self):
        """Return coupling interface between rigid and deformable."""
        return {
            "mount_points": {name: pos.tolist() for name, pos in self.sensor_mounts.items()},
            "regions": list(self.regions.keys()),
        }
    
    def add_region(self, region: DeformableRegion) -> None:
        """Add a deformable region to the vehicle."""
        self.regions[region.name] = region
    
    def add_sensor_mount(self, name: str, position: np.ndarray, 
                         attached_region: Optional[str] = None) -> None:
        """Register a sensor mount point.
        
        Args:
            name: Sensor identifier
            position: 3D position in body frame
            attached_region: If set, this sensor moves with the deformable region
        """
        self.sensor_mounts[name] = position
    
    def set_morph_mode(self, mode: MorphMode, blend: float = 1.0) -> None:
        """Set vehicle morphological mode with optional blending.
        
        Args:
            mode: Target morphological mode
            blend: Blend factor (0.0 = no change, 1.0 = full transition)
        """
        if blend >= 1.0:
            self.mode_blend_weights = {mode: 1.0}
            self.current_mode = mode
        else:
            # Blend between current and target mode
            remaining = 1.0 - blend
            new_weights = {}
            for m, w in self.mode_blend_weights.items():
                new_weights[m] = w * remaining
            new_weights[mode] = new_weights.get(mode, 0.0) + blend
            self.mode_blend_weights = new_weights
            self.current_mode = max(new_weights, key=new_weights.get)
    
    def get_deformed_mesh(self, region_name: str) -> Tuple[np.ndarray, np.ndarray]:
        """Get current deformed mesh for a region.
        
        Returns:
            Tuple of (vertices, faces) arrays
        """
        region = self.regions[region_name]
        return region.vertices.copy(), region.faces.copy()
    
    def compute_aero_properties(self) -> Dict[str, float]:
        """Compute aerodynamic properties based on current morphology.
        
        Returns:
            Dictionary with Cd, Cl, frontal_area, downforce
        """
        # Base values for standard SUV
        base_cd = 0.32
        base_cl = 0.15
        base_area = self.width * self.height * 0.85  # Frontal area with taper
        
        mode_factors = {
            MorphMode.STANDARD: (1.0, 1.0, 1.0),
            MorphMode.AERO_DYNAMIC: (0.70, 0.50, 0.90),   # 30% Cd reduction
            MorphMode.OFFROAD: (1.25, 0.80, 1.15),        # More drag
            MorphMode.COMPACT: (0.95, 0.90, 0.75),        # Less area
            MorphMode.SAFETY: (1.05, 0.60, 1.10),         # Slight drag increase
            MorphMode.WEATHER: (1.15, 1.20, 1.05),        # Spoiler effect
        }
        
        # Blend across active modes
        cd_factor = 0.0
        cl_factor = 0.0
        area_factor = 0.0
        for mode, weight in self.mode_blend_weights.items():
            cd_f, cl_f, area_f = mode_factors.get(mode, (1.0, 1.0, 1.0))
            cd_factor += cd_f * weight
            cl_factor += cl_f * weight
            area_factor += area_f * weight
        
        return {
            "Cd": base_cd * cd_factor,
            "Cl": base_cl * cl_factor,
            "frontal_area_m2": base_area * area_factor,
            "downforce_N": 0.5 * 1.225 * base_area * area_factor * base_cl * cl_factor * 30**2,
        }
    
    def compute_ground_clearance(self) -> float:
        """Compute current ground clearance based on morphology."""
        base_clearance = 0.20  # 200mm standard
        mode_deltas = {
            MorphMode.STANDARD: 0.0,
            MorphMode.AERO_DYNAMIC: -0.05,    # Lowered
            MorphMode.OFFROAD: +0.08,         # Raised
            MorphMode.COMPACT: -0.02,
            MorphMode.SAFETY: +0.02,
            MorphMode.WEATHER: +0.03,
        }
        delta = sum(
            mode_deltas.get(m, 0.0) * w 
            for m, w in self.mode_blend_weights.items()
        )
        return base_clearance + delta
    
    def get_state_vector(self) -> np.ndarray:
        """Serialize vehicle state for simulation input.
        
        Returns:
            State vector: [mode_weights(8), region_deformations(N*3), ...]
        """
        mode_vec = np.zeros(len(MorphMode))
        for mode, weight in self.mode_blend_weights.items():
            mode_vec[mode.value == [m.value for m in MorphMode]] = weight
        
        deformations = []
        for region in self.regions.values():
            deformations.append(
                (region.vertices - region.rest_positions).flatten()
            )
        
        return np.concatenate([mode_vec] + deformations)


def create_default_vehicle() -> MorphableVehicle:
    """Create a default morphable SUV with standard deformable regions.
    
    Regions:
    - front_bumper: Active crash structure + aero lip
    - rear_bumper: Active diffuser + crash structure
    - roof_panel: Adjustable height and camber
    - side_skirts: Ground-effect panels
    - hood: Active aero hood with vent flaps
    - underbody: Adjustable diffuser panels
    """
    vehicle = MorphableVehicle(name="MorphVehicle-SUV-Default")
    
    # --- Front bumper ---
    n_verts = 64
    front_verts = np.random.randn(n_verts, 3) * 0.05 + np.array([2.35, 0, 0.4])
    front_faces = _generate_sphere_faces(n_verts)
    vehicle.add_region(DeformableRegion(
        name="front_bumper",
        vertices=front_verts.copy(),
        faces=front_faces,
        rest_positions=front_verts.copy(),
        material={"youngs_modulus": 5.0e8, "poisson_ratio": 0.35, "density": 1200, "damping": 0.08},
        actuator_id="front_actuator",
        max_deformation=0.12,
        min_deformation=-0.08,
    ))
    
    # --- Rear bumper ---
    rear_verts = np.random.randn(n_verts, 3) * 0.05 + np.array([-2.35, 0, 0.4])
    rear_faces = _generate_sphere_faces(n_verts)
    vehicle.add_region(DeformableRegion(
        name="rear_bumper",
        vertices=rear_verts.copy(),
        faces=rear_faces,
        rest_positions=rear_verts.copy(),
        material={"youngs_modulus": 5.0e8, "poisson_ratio": 0.35, "density": 1200, "damping": 0.08},
        actuator_id="rear_actuator",
        max_deformation=0.10,
        min_deformation=-0.06,
    ))
    
    # --- Roof panel ---
    n_roof = 100
    roof_verts = np.random.randn(n_roof, 3) * 0.03 + np.array([0, 0, 1.5])
    roof_faces = _generate_sphere_faces(n_roof)
    vehicle.add_region(DeformableRegion(
        name="roof_panel",
        vertices=roof_verts.copy(),
        faces=roof_faces,
        rest_positions=roof_verts.copy(),
        material={"youngs_modulus": 2.0e9, "poisson_ratio": 0.30, "density": 7800, "damping": 0.05},
        actuator_id="roof_actuator",
        max_deformation=0.15,
        min_deformation=-0.10,
    ))
    
    # --- Sensor mounts ---
    vehicle.add_sensor_mount("lidar_front", np.array([2.35, 0, 1.40]), "front_bumper")
    vehicle.add_sensor_mount("lidar_roof", np.array([0, 0, 1.75]), "roof_panel")
    vehicle.add_sensor_mount("camera_front", np.array([2.40, 0, 1.20]), "front_bumper")
    vehicle.add_sensor_mount("radar_front", np.array([2.38, 0, 0.50]), "front_bumper")
    vehicle.add_sensor_mount("imu", np.array([0, 0, 0.55]))  # Rigid chassis
    
    return vehicle


def _generate_sphere_faces(n_verts: int) -> np.ndarray:
    """Generate simplified triangle faces for a point cloud.
    
    This is a placeholder — real mesh generation would use
    Delaunay triangulation or parametric surface meshing.
    """
    import itertools
    # Simple fan triangulation from centroid
    n = n_verts
    faces = []
    for i in range(1, n - 1):
        faces.append([0, i, i + 1])
    return np.array(faces, dtype=np.int32)
