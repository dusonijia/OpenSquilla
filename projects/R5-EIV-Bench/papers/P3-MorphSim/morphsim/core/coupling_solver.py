"""Two-way rigid-deformable coupling solver."""
import numpy as np


class CouplingSolver:
    """Two-way rigid-deformable coupling.

    Methods:
      - Spring-based attachment points
      - Penalty-based collision
      - Constraint-based (for extreme deformations)
    """

    def __init__(self, coupling_interface, stiffness, damping):
        """Initialize coupling solver."""
        self.interface = coupling_interface
        self.stiffness = stiffness
        self.damping = damping

        # Extract mount points from interface
        self.mount_points = []
        if "mount_points" in coupling_interface:
            for name, pos in coupling_interface["mount_points"].items():
                self.mount_points.append(np.array(pos))

        # Region attachment points
        self.regions = coupling_interface.get("regions", [])

    def compute(self, rigid_state, deform_state):
        """Compute coupling forces between rigid and deformable.

        Returns:
            forces_on_rigid: (6,) array [fx,fy,fz,tx,ty,tz]
            forces_on_deformable: (N,3) array
        """
        forces_on_rigid = np.zeros(6)
        forces_on_deformable = np.zeros_like(deform_state["positions"])

        # Spring-based coupling at mount points
        for i, mount_pos in enumerate(self.mount_points):
            # Find nearest deformable node
            deform_positions = deform_state["positions"]
            distances = np.linalg.norm(deform_positions - mount_pos, axis=1)
            nearest_idx = np.argmin(distances)

            if distances[nearest_idx] < 0.5:  # Within coupling range
                # Spring force
                deform_node_pos = deform_positions[nearest_idx]
                rigid_pos = rigid_state["pos"]

                # Compute spring force
                spring_vec = deform_node_pos - rigid_pos
                spring_force = -self.stiffness * spring_vec - self.damping * deform_state["velocities"][nearest_idx]

                # Apply equal and opposite forces
                forces_on_deformable[nearest_idx] += spring_force
                forces_on_rigid[0:3] -= spring_force  # Force on rigid body
                forces_on_rigid[3:6] += np.cross(mount_pos - rigid_pos, spring_force)  # Torque

        # Collision detection (simplified ground plane)
        for i, pos in enumerate(deform_state["positions"]):
            if pos[2] < 0:  # Below ground
                # Penalty force upward
                penetration = -pos[2]
                collision_force = np.array([0, 0, self.stiffness * penetration])
                forces_on_deformable[i] += collision_force

        return forces_on_rigid, forces_on_deformable