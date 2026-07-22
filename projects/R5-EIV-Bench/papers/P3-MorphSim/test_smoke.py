# MorphSim — Quick Smoke Test
# Validates that the core engine can instantiate, step, and compute metrics
# Run: python test_smoke.py

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from morphsim import MorphSimEngine, MorphVehicleConfig, MorphScenario
from morphsim.core.scenarios import AERO_MORPH, TERRAIN_ADAPT, COMPACT_PARK

def test_engine_instantiation():
    config = MorphVehicleConfig()
    engine = MorphSimEngine(config, headless=True)
    print("✅ Engine instantiated")
    return engine

def test_scenario_run(engine, scenario: MorphScenario, steps=100):
    state = engine.reset(scenario)
    total_reward = 0.0
    for i in range(steps):
        action = engine.get_default_action()  # zero morph
        state = engine.step(action)
        total_reward += state.reward
        if state.done:
            print(f"  Episode ended at step {i}")
            break
    print(f"✅ {scenario.name}: {steps} steps, reward={total_reward:.4f}")
    return total_reward

def test_differentiable_gradient():
    """Test that differentiable pipeline can compute gradients."""
    try:
        from morphsim.core.differentiable import DifferentiableMorphLayer
        import numpy as np
        layer = DifferentiableMorphLayer(n_actuators=12, latent_dim=8)
        latent = np.random.randn(1, 8).astype(np.float32)
        actuator_cmds, info = layer.forward(latent)
        grad = layer.backward(np.ones_like(actuator_cmds))
        print(f"✅ Differentiable layer: latent→actuator shape={actuator_cmds.shape}, grad shape={grad.shape}")
    except ImportError as e:
        print(f"⚠️  Differentiable layer skipped (missing dep): {e}")

def main():
    print("=" * 60)
    print("MorphSim Smoke Test")
    print("=" * 60)

    # 1. Engine instantiation
    engine = test_engine_instantiation()

    # 2. Run scenarios
    print("\n--- Scenario Tests ---")
    test_scenario_run(engine, AERO_MORPH, steps=50)
    test_scenario_run(engine, TERRAIN_ADAPT, steps=50)
    test_scenario_run(engine, COMPACT_PARK, steps=50)

    # 3. Differentiable pipeline
    print("\n--- Differentiable Pipeline ---")
    test_differentiable_gradient()

    print("\n" + "=" * 60)
    print("All smoke tests passed! 🎉")
    print("Next: implement real physics backend (MuJoCo/Isaac Gym)")
    print("=" * 60)

if __name__ == "__main__":
    main()
