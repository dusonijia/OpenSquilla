"""XPBD deformable body solver."""
import numpy as np


class XPBDSolver:
    """XPBD (eXtended Position-Based Dynamics) deformable body solver.

    Implements Macklin et al. 2016 for real-time deformable simulation.
    """

    def __init__(self, deformable_model, config):
        """Initialize XPBD solver from deformable regions."""
        self.config = config
        self._deformable_model = deformable_model
        self._constraints = []
        self._actuator_targets = np.zeros(12)
        self._initialize_mesh()

    def _initialize_mesh(self):
        """Initialize tetrahedral mesh and constraints."""
        # For quick implementation, create a simple box mesh
        num_nodes = 27  # 3x3x3 grid
        self.positions = np.zeros((num_nodes, 3))
        self.velocities = np.zeros((num_nodes, 3))
        self.masses = np.ones(num_nodes) * 1.0  # kg

        # Create 3x3x3 grid
        for i in range(3):
            for j in range(3):
                for k in range(3):
                    idx = i * 9 + j * 3 + k
                    self.positions[idx] = np.array([
                        (i - 1) * 0.5,  # x
                        (j - 1) * 0.5,  # y
                        (k - 1) * 0.3,  # z
                    ])

        # Create distance constraints (structural edges)
        for i in range(num_nodes):
            for j in range(i + 1, num_nodes):
                dist = np.linalg.norm(self.positions[i] - self.positions[j])
                if dist < 0.8:  # Only connect nearby nodes
                    self._constraints.append({
                        "type": "distance",
                        "i": i,
                        "j": j,
                        "rest_length": dist,
                        "compliance": self.config.deformable_compliance,
                    })

    def set_targets(self, targets):
        """Set actuator target positions."""
        self._actuator_targets = targets

    def step(self, dt, substeps):
        """XPBD substep loop."""
        dt_sub = dt / substeps

        for _ in range(substeps):
            self._predict_positions(dt_sub)
            self._solve_constraints(dt_sub)
            self._update_velocities(dt_sub)

    def _predict_positions(self, dt):
        """Predict positions using explicit Euler."""
        # Apply gravity and external forces
        gravity = self.config.gravity
        for i in range(len(self.positions)):
            self.velocities[i] += gravity * dt

        # Predict new positions
        self.positions += self.velocities * dt

    def _solve_constraints(self, dt):
        """Solve all XPBD constraints iteratively."""
        num_iterations = 5
        for _ in range(num_iterations):
            for constraint in self._constraints:
                if constraint["type"] == "distance":
                    self._solve_distance_constraint(constraint, dt)

            # Apply actuator targets
            self._apply_actuator_constraints(dt)

    def _solve_distance_constraint(self, constraint, dt):
        """Solve distance constraint using XPBD."""
        i, j = constraint["i"], constraint["j"]
        p1, p2 = self.positions[i], self.positions[j]
        m1, m2 = self.masses[i], self.masses[j]

        # Current distance
        diff = p1 - p2
        current_length = np.linalg.norm(diff)

        if current_length < 1e-6:
            return

        # Correction direction
        direction = diff / current_length

        # XPBD lambda computation
        alpha = constraint["compliance"] / (dt ** 2)
        w1 = 1.0 / m1
        w2 = 1.0 / m2
        w = w1 + w2 + alpha

        lambda_val = -(current_length - constraint["rest_length"]) / w

        # Apply correction
        correction = lambda_val * direction
        self.positions[i] += w1 * correction
        self.positions[j] -= w2 * correction

    def _apply_actuator_constraints(self, dt):
        """Apply actuator target constraints."""
        # Simple implementation: constrain top nodes to target positions
        num_actuators = min(len(self._actuator_targets), 12)
        for i in range(num_actuators):
            # Apply to top layer nodes (indices 18-26)
            node_idx = 18 + (i % 9)
            if node_idx < len(self.positions):
                # Soft constraint: move toward target
                target_pos = self.positions[node_idx].copy()
                target_pos[2] = self._actuator_targets[i] * 0.3  # Scale to reasonable range

                diff = target_pos - self.positions[node_idx]
                self.positions[node_idx] += diff * 0.1  # Soft coupling

    def get_state(self):
        """Extract deformable body state."""
        return {
            "positions": self.positions.copy(),
            "velocities": self.velocities.copy(),
            "actuator_pos": self._actuator_targets.copy(),
            "actuator_vel": np.zeros(12),  # Placeholder
        }

    def _update_velocities(self, dt):
        """Update velocities from position changes (XPBD velocity update)."""
        if not hasattr(self, '_old_positions'):
            self._old_positions = self.positions.copy()
        self.velocities = (self.positions - self._old_positions) / dt
        self._old_positions = self.positions.copy()
        # Clamp velocities for stability
        max_vel = 10.0
        norms = np.linalg.norm(self.velocities, axis=1)
        mask = norms > max_vel
        if np.any(mask):
            self.velocities[mask] = self.velocities[mask] / norms[mask, None] * max_vel

    def apply_coupling(self, forces):
        """Apply coupling forces from rigid solver."""
        # Apply forces to bottom nodes
        for i in range(min(9, len(self.positions))):
            self.velocities[i] += forces[i % len(forces)] / self.masses[i]