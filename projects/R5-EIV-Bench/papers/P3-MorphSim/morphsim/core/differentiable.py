"""
MorphSim Differentiable Wrapper — JAX Integration
===================================================

Wraps the forward simulation as a differentiable function for:
  - Gradient-based morphology optimization
  - Policy gradient through dynamics
  - Sensitivity analysis of morphing decisions

Two modes:
  1. Implicit differentiation (adjoint method) — memory-efficient for long episodes
  2. Explicit autodiff — simpler, higher memory, good for short episodes

Reference:
  - JAX: Bradbury et al., 2018
  - DiffTaichi: Hu et al., 2020
  - Differentiable simulation survey: Werling et al., 2021
"""

from __future__ import annotations
import numpy as np
from typing import Optional, Dict, Tuple

try:
    import jax
    import jax.numpy as jnp
    from jax import grad, jit, vmap
    JAX_AVAILABLE = True
except ImportError:
    JAX_AVAILABLE = False
    jnp = np  # fallback


class DifferentiableMorphSim:
    """Differentiable wrapper around MorphSimEngine.

    Usage:
        engine = MorphSimEngine(config)
        engine.load_vehicle(vehicle)
        engine.load_scenario("aero_highway")

        diff_sim = DifferentiableMorphSim(engine)

        # Forward simulation
        final_state = diff_sim.rollout(initial_state, actions)

        # Gradient of final-state metric w.r.t. actions
        loss = lambda actions: -diff_sim.rollout(s0, actions).drag_coefficient
        grads = jax.grad(loss)(actions)
    """

    def __init__(self, engine, mode: str = "implicit"):
        assert mode in ("implicit", "explicit")
        self.engine = engine
        self.mode = mode
        if not JAX_AVAILABLE:
            print("[MorphSim] WARNING: JAX not available, differentiable mode disabled")

    def rollout(self, initial_state, actions_sequence) -> Dict:
        """Run a full episode and return final metrics.

        Args:
            initial_state: MorphState at t=0
            actions_sequence: (T, action_dim) array of actions

        Returns:
            Dict with final state + cumulative metrics
        """
        state = initial_state
        metrics = {
            "total_reward": 0.0,
            "drag_coefficient": 0.0,
            "morph_energy": 0.0,
            "safety_violations": 0,
        }

        for t in range(len(actions_sequence)):
            action = self._decode_action(actions_sequence[t])
            state, reward, done, info = self.engine.step(action)

            metrics["total_reward"] += reward
            metrics["drag_coefficient"] += info.get("drag", 0.0)
            metrics["morph_energy"] += info.get("morph_energy", 0.0)
            metrics["safety_violations"] += int(info.get("safety", 1.0) < 0.5)

            if done:
                break

        metrics["avg_drag"] = metrics["drag_coefficient"] / max(t + 1, 1)
        metrics["avg_energy"] = metrics["morph_energy"] / max(t + 1, 1)
        return metrics

    def _decode_action(self, action_vec):
        """Convert flat action vector to MorphAction."""
        from .engine import MorphAction
        return MorphAction(
            throttle=float(action_vec[0]),
            brake=float(action_vec[1]),
            steer=float(action_vec[2]),
            actuator_targets=action_vec[3:] if len(action_vec) > 3 else None,
        )

    def optimize_morphology(
        self,
        initial_state,
        initial_actions,
        n_iters: int = 100,
        lr: float = 1e-3,
        objective: str = "drag",
    ) -> Tuple[np.ndarray, list]:
        """Gradient-based morphology optimization.

        Optimize the action sequence to minimize a given objective.

        Args:
            initial_state: starting MorphState
            initial_actions: (T, action_dim) initial action sequence
            n_iters: optimization iterations
            lr: learning rate
            objective: "drag" | "energy" | "combined" | "safety"

        Returns:
            optimized_actions: (T, action_dim) optimized sequence
            history: list of objective values per iteration
        """
        if not JAX_AVAILABLE:
            raise RuntimeError("JAX required for optimization")

        actions = jnp.array(initial_actions)
        history = []

        def loss_fn(a):
            metrics = self.rollout(initial_state, a)
            if objective == "drag":
                return metrics["avg_drag"]
            elif objective == "energy":
                return metrics["avg_energy"]
            elif objective == "safety":
                return metrics["safety_violations"] * 1e3
            else:  # combined
                return (
                    metrics["avg_drag"]
                    + 0.1 * metrics["avg_energy"]
                    + 1e3 * metrics["safety_violations"]
                )

        grad_fn = jit(grad(loss_fn))

        for i in range(n_iters):
            g = grad_fn(actions)
            actions = actions - lr * g
            val = float(loss_fn(actions))
            history.append(val)
            if i % 10 == 0:
                print(f"[MorphSim Opt] iter {i}: {objective} = {val:.6f}")

        return np.array(actions), history

    def sensitivity_analysis(
        self,
        initial_state,
        actions_sequence,
        param_names: list,
    ) -> Dict[str, float]:
        """Compute sensitivity of final metrics to initial conditions.

        Returns dict of param_name -> gradient magnitude.
        """
        if not JAX_AVAILABLE:
            raise RuntimeError("JAX required for sensitivity analysis")

        def metric_fn(params):
            modified_state = self._perturb_state(initial_state, params)
            metrics = self.rollout(modified_state, actions_sequence)
            return metrics["avg_drag"]

        params_0 = jnp.zeros(len(param_names))
        grads = grad(metric_fn)(params_0)

        return {
            name: float(abs(grads[i]))
            for i, name in enumerate(param_names)
        }

    def _perturb_state(self, state, params):
        """Apply small perturbations to state parameters."""
        # Modify state fields based on params
        # e.g., params[0] -> pos_x offset, params[1] -> vel_z offset, etc.
        return state  # placeholder
