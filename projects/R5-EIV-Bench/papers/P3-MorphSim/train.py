#!/usr/bin/env python3
"""
MorphSim End-to-End Training & Evaluation Pipeline
===================================================
Usage:
    python train.py --scenario aero_morph --policy ppo --steps 500000
    python train.py --scenario all --policy sac --eval-only
    python train.py --scenario terrain_adapt --policy diff_opt --steps 200
"""

import argparse
import json
import os
import time
from pathlib import Path

import numpy as np

from morphsim.core.engine import MorphSimEngine, SimulationConfig
from morphsim.core.scenarios import MorphScenarioRegistry
from morphsim.baselines.policies import (
    RandomPolicy, RuleBasedPolicy, PPOPolicy, SACPolicy, DiffOptPolicy
)
from morphsim.evaluation.metrics import MorphSimEvaluator


POLICY_MAP = {
    "random": RandomPolicy,
    "rule": RuleBasedPolicy,
    "ppo": PPOPolicy,
    "sac": SACPolicy,
    "diff_opt": DiffOptPolicy,
}


def parse_args():
    parser = argparse.ArgumentParser(description="MorphSim Training Pipeline")
    parser.add_argument("--scenario", type=str, default="aero_morph",
                        help="Scenario name or 'all' for all scenarios")
    parser.add_argument("--policy", type=str, default="ppo",
                        choices=list(POLICY_MAP.keys()))
    parser.add_argument("--steps", type=int, default=500000,
                        help="Training steps (ignored for diff_opt)")
    parser.add_argument("--eval-only", action="store_true",
                        help="Skip training, run evaluation only")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--save-dir", type=str, default="./checkpoints")
    parser.add_argument("--log-interval", type=int, default=1000)
    parser.add_argument("--eval-episodes", type=int, default=20)
    return parser.parse_args()


def train_single_scenario(scenario_name: str, policy_cls, args) -> dict:
    """Train on a single scenario and return metrics."""
    print(f"\n{'='*60}")
    print(f"  Scenario: {scenario_name} | Policy: {policy_cls.__name__}")
    print(f"{'='*60}")

    # Create engine with scenario
    config = SimulationConfig(seed=args.seed)
    engine = MorphSimEngine(config)
    scenario = MorphScenarioRegistry.create(scenario_name, seed=args.seed)
    engine.load_scenario(scenario)
    policy = policy_cls(engine.action_dim, engine.obs_dim)

    # Training loop
    obs = engine.reset()
    episode_rewards = []
    episode_reward = 0.0
    episode_count = 0
    best_reward = -float("inf")
    start_time = time.time()

    for step in range(1, args.steps + 1):
        action = policy.act(obs)
        obs, reward, done, info = engine.step(action)
        episode_reward += reward

        # Policy update
        if hasattr(policy, "update"):
            policy.store_transition(obs, action, reward, done)
            if step % 4 == 0:
                policy.update()

        if done:
            episode_rewards.append(episode_reward)
            episode_count += 1
            if episode_reward > best_reward:
                best_reward = episode_reward
            episode_reward = 0.0
            obs = engine.reset()

        if step % args.log_interval == 0:
            recent = episode_rewards[-100:] if episode_rewards else [0]
            elapsed = time.time() - start_time
            fps = step / elapsed if elapsed > 0 else 0
            print(f"  Step {step:>7d} | Episodes: {episode_count} | "
                  f"Avg100: {np.mean(recent):>8.2f} | Best: {best_reward:>8.2f} | "
                  f"FPS: {fps:>6.0f}")

    elapsed = time.time() - start_time
    print(f"\n  Training complete: {episode_count} episodes in {elapsed:.1f}s")

    # Save checkpoint
    save_path = Path(args.save_dir) / scenario_name
    save_path.mkdir(parents=True, exist_ok=True)
    if hasattr(policy, "save"):
        policy.save(save_path / "policy.pt")

    return {
        "scenario": scenario_name,
        "policy": policy_cls.__name__,
        "episodes": episode_count,
        "best_reward": best_reward,
        "avg_reward_100": float(np.mean(episode_rewards[-100:])) if episode_rewards else 0,
        "total_steps": args.steps,
        "elapsed_s": elapsed,
    }


def evaluate_scenario(scenario_name: str, policy_cls, args) -> dict:
    """Evaluate policy on scenario."""
    config = SimulationConfig(seed=args.seed + 1000)
    engine = MorphSimEngine(config)
    scenario = MorphScenarioRegistry.create(scenario_name, seed=args.seed + 1000)
    engine.load_scenario(scenario)
    policy = policy_cls(engine.action_dim, engine.obs_dim)

    # Load checkpoint if available
    ckpt_path = Path(args.save_dir) / scenario_name / "policy.pt"
    if ckpt_path.exists() and hasattr(policy, "load"):
        policy.load(ckpt_path)

    evaluator = MorphSimEvaluator()
    all_metrics = []

    for ep in range(args.eval_episodes):
        obs = engine.reset()
        done = False
        ep_data = {"observations": [], "actions": [], "rewards": []}

        while not done:
            action = policy.act(obs, deterministic=True) \
                if hasattr(policy, "act") else policy.act(obs)
            obs, reward, done, info = engine.step(action)
            ep_data["observations"].append(obs)
            ep_data["actions"].append(action)
            ep_data["rewards"].append(reward)

        ep_metrics = evaluator.evaluate_episode(ep_data, info)
        all_metrics.append(ep_metrics)

    # Aggregate
    agg = {}
    for key in all_metrics[0]:
        vals = [m[key] for m in all_metrics]
        agg[f"{key}_mean"] = float(np.mean(vals))
        agg[f"{key}_std"] = float(np.std(vals))
        agg[f"{key}_min"] = float(np.min(vals))
        agg[f"{key}_max"] = float(np.max(vals))

    agg["scenario"] = scenario_name
    agg["policy"] = policy_cls.__name__
    agg["eval_episodes"] = args.eval_episodes
    return agg


def main():
    args = parse_args()

    if args.scenario == "all":
        scenarios = MorphScenarioRegistry.list_scenarios()
    else:
        scenarios = [args.scenario]

    policy_cls = POLICY_MAP[args.policy]
    results = []

    for scenario_name in scenarios:
        if not args.eval_only:
            train_result = train_single_scenario(scenario_name, policy_cls, args)
            results.append(train_result)

        eval_result = evaluate_scenario(scenario_name, policy_cls, args)
        results.append(eval_result)

    # Save results
    out_path = Path(args.save_dir) / "results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")

    # Print summary table
    print(f"\n{'='*80}")
    print(f"  SUMMARY")
    print(f"{'='*80}")
    print(f"{'Scenario':<20} {'Policy':<15} {'Best Reward':>12} {'Avg Reward':>12}")
    print(f"{'-'*20} {'-'*15} {'-'*12} {'-'*12}")
    for r in results:
        if "best_reward" in r:
            print(f"{r['scenario']:<20} {r['policy']:<15} "
                  f"{r['best_reward']:>12.2f} {r.get('avg_reward_100', 0):>12.2f}")


if __name__ == "__main__":
    main()
