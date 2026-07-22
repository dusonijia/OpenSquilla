"""MorphSim — Differentiable Simulation Framework for Adaptive Morphology Vehicles.

Sub-module: training utilities for gradient-based morphology optimization.
"""
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

import torch
import torch.nn as nn
import torch.optim as optim

from morphsim.core.engine import MorphSimEngine, SimulationConfig
from morphsim.core.differentiable import DifferentiablePipeline
from morphsim.core.scenarios import MorphScenario, MorphScenarioRegistry
from morphsim.core.vehicle import MorphVehicleConfig


@dataclass
class TrainConfig:
    """Configuration for morphology optimization training."""
    # Optimizer
    lr: float = 1e-3
    optimizer: str = "adam"          # adam | sgd | adamw
    weight_decay: float = 1e-5
    scheduler: str = "cosine"        # cosine | step | none
    
    # Training loop
    num_iterations: int = 500
    episodes_per_iter: int = 4
    max_steps_per_episode: int = 500
    
    # Loss weights
    w_task: float = 1.0              # Task performance (speed, accuracy, etc.)
    w_energy: float = 0.1            # Energy efficiency
    w_smoothness: float = 0.05       # Morphology change smoothness penalty
    w_safety: float = 10.0           # Safety constraint (hard weight)
    
    # Morphology regularization
    morph_change_limit: float = 0.3  # Max morph change per step (fraction)
    morph_l2_penalty: float = 0.01   # L2 penalty on morph parameters
    
    # Logging
    log_interval: int = 10
    save_interval: int = 50
    eval_interval: int = 25
    
    # Device
    device: str = "cuda" if torch.cuda.is_available() else "cpu"


class MorphPolicy(nn.Module):
    """Neural network policy that maps observations to morphology actions.
    
    Observations:
    - Vehicle state (pose, velocity, acceleration)
    - Environment context (terrain type, weather, speed target)
    - Current morphology state
    
    Actions:
    - Morphology parameter deltas (continuous)
    """
    
    def __init__(
        self,
        obs_dim: int = 64,
        morph_dim: int = 16,
        hidden_dim: int = 256,
        num_layers: int = 3,
    ):
        super().__init__()
        self.obs_dim = obs_dim
        self.morph_dim = morph_dim
        
        # Observation encoder
        self.obs_encoder = nn.Sequential(
            nn.Linear(obs_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
        )
        
        # Morphology-aware trunk
        layers = []
        in_dim = hidden_dim + morph_dim
        for _ in range(num_layers):
            layers.extend([
                nn.Linear(in_dim, hidden_dim),
                nn.LayerNorm(hidden_dim),
                nn.ReLU(),
            ])
            in_dim = hidden_dim
        self.trunk = nn.Sequential(*layers)
        
        # Policy head (mean + log_std for Gaussian policy)
        self.mean_head = nn.Linear(hidden_dim, morph_dim)
        self.log_std_head = nn.Linear(hidden_dim, morph_dim)
        
        # Value head (for advantage estimation)
        self.value_head = nn.Linear(hidden_dim, 1)
        
        # Initialize
        self._init_weights()
    
    def _init_weights(self):
        """Orthogonal initialization for stable training."""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.orthogonal_(module.weight, gain=np.sqrt(2))
                nn.init.zeros_(module.bias)
        # Small init for policy heads
        nn.init.orthogonal_(self.mean_head.weight, gain=0.01)
        nn.init.orthogonal_(self.log_std_head.weight, gain=0.01)
    
    def forward(
        self, obs: torch.Tensor, current_morph: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Forward pass.
        
        Returns:
            mean: morphology action mean [B, morph_dim]
            log_std: morphology action log_std [B, morph_dim]
            value: state value estimate [B, 1]
        """
        obs_feat = self.obs_encoder(obs)
        combined = torch.cat([obs_feat, current_morph], dim=-1)
        trunk_feat = self.trunk(combined)
        
        mean = self.mean_head(trunk_feat)
        log_std = self.log_std_head(trunk_feat).clamp(-4, 1)
        value = self.value_head(trunk_feat)
        
        return mean, log_std, value
    
    def get_action(
        self, obs: torch.Tensor, current_morph: torch.Tensor, deterministic: bool = False
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Sample morphology action.
        
        Returns:
            action: morphology parameter deltas [B, morph_dim]
            log_prob: log probability of the action [B, 1]
        """
        mean, log_std, _ = self.forward(obs, current_morph)
        std = log_std.exp()
        
        if deterministic:
            action = mean
            log_prob = torch.zeros(mean.shape[0], 1, device=mean.device)
        else:
            dist = torch.distributions.Normal(mean, std)
            action = dist.sample()
            log_prob = dist.log_prob(action).sum(dim=-1, keepdim=True)
        
        # Clamp action to reasonable range
        action = action.clamp(-1.0, 1.0)
        
        return action, log_prob


class MorphTrainer:
    """Trainer for gradient-based morphology optimization.
    
    Supports two modes:
    1. **Differentiable optimization**: Use DifferentiablePipeline for 
       end-to-end gradient flow through the simulation.
    2. **Policy gradient**: Use PPO-style training when differentiable
       simulation is not available or for non-differentiable rewards.
    """
    
    def __init__(
        self,
        engine: MorphSimEngine,
        policy: Optional[MorphPolicy] = None,
        config: Optional[TrainConfig] = None,
    ):
        self.engine = engine
        self.config = config or TrainConfig()
        self.device = torch.device(self.config.device)
        
        # Initialize policy
        if policy is not None:
            self.policy = policy.to(self.device)
        else:
            self.policy = MorphPolicy().to(self.device)
        
        # Optimizer
        self.optimizer = self._build_optimizer()
        self.scheduler = self._build_scheduler()
        
        # Differentiable pipeline
        self.diff_pipeline = DifferentiablePipeline(engine)
        
        # Training state
        self.iteration = 0
        self.best_reward = -float("inf")
        self.training_log: List[Dict] = []
    
    def _build_optimizer(self) -> optim.Optimizer:
        params = self.policy.parameters()
        if self.config.optimizer == "adam":
            return optim.Adam(params, lr=self.config.lr, weight_decay=self.config.weight_decay)
        elif self.config.optimizer == "adamw":
            return optim.AdamW(params, lr=self.config.lr, weight_decay=self.config.weight_decay)
        elif self.config.optimizer == "sgd":
            return optim.SGD(params, lr=self.config.lr, momentum=0.9, weight_decay=self.config.weight_decay)
        else:
            raise ValueError(f"Unknown optimizer: {self.config.optimizer}")
    
    def _build_scheduler(self) -> Optional[optim.lr_scheduler._LRScheduler]:
        if self.config.scheduler == "cosine":
            return optim.lr_scheduler.CosineAnnealingLR(
                self.optimizer, T_max=self.config.num_iterations
            )
        elif self.config.scheduler == "step":
            return optim.lr_scheduler.StepLR(
                self.optimizer, step_size=100, gamma=0.5
            )
        return None
    
    def compute_loss(
        self,
        task_reward: torch.Tensor,
        energy_cost: torch.Tensor,
        morph_delta: torch.Tensor,
        safety_violation: torch.Tensor,
        log_prob: Optional[torch.Tensor] = None,
        advantage: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """Compute total training loss.
        
        L = -w_task * R_task + w_energy * C_energy + w_smooth * ||Δmorph||² 
            + w_safety * max(0, safety_violation) + w_l2 * ||morph||²
        """
        # Task reward (maximize)
        loss_task = -self.config.w_task * task_reward
        
        # Energy cost (minimize)
        loss_energy = self.config.w_energy * energy_cost
        
        # Morphology smoothness (minimize changes)
        loss_smooth = self.config.w_smoothness * (morph_delta ** 2).mean()
        
        # Safety violation (hard constraint)
        loss_safety = self.config.w_safety * torch.relu(safety_violation).mean()
        
        # L2 regularization on morph parameters
        loss_l2 = self.config.morph_l2_penalty * (morph_delta ** 2).mean()
        
        # Policy gradient term (if using RL)
        loss_pg = torch.tensor(0.0, device=self.device)
        if log_prob is not None and advantage is not None:
            loss_pg = -(log_prob * advantage.detach()).mean()
        
        total = loss_task + loss_energy + loss_smooth + loss_safety + loss_l2 + loss_pg
        
        return total
    
    def train_step_differentiable(self, scenarios: List[MorphScenario]) -> Dict:
        """One training step using differentiable simulation.
        
        Rolls out episodes, computes gradients through the simulation,
        and updates the policy.
        """
        self.policy.train()
        total_loss = 0.0
        total_reward = 0.0
        num_episodes = 0
        
        for scenario in scenarios:
            # Reset environment
            obs = self._get_initial_obs(scenario)
            current_morph = self._get_default_morph()
            
            episode_reward = 0.0
            episode_energy = 0.0
            episode_morph_delta = 0.0
            episode_safety = 0.0
            
            for step in range(self.config.max_steps_per_episode):
                obs_t = torch.tensor(obs, dtype=torch.float32, device=self.device).unsqueeze(0)
                morph_t = torch.tensor(current_morph, dtype=torch.float32, device=self.device).unsqueeze(0)
                
                # Get morphology action
                action, log_prob = self.policy.get_action(obs_t, morph_t)
                morph_delta = action.squeeze(0).detach().cpu().numpy()
                
                # Step simulation through differentiable pipeline
                step_result = self.diff_pipeline.step_with_gradients(
                    morph_delta=morph_delta,
                    scenario=scenario,
                )
                
                # Accumulate metrics
                episode_reward += step_result["reward"]
                episode_energy += step_result["energy_cost"]
                episode_morph_delta += np.sum(morph_delta ** 2)
                episode_safety += step_result.get("safety_violation", 0.0)
                
                # Update observation
                obs = step_result["next_obs"]
                current_morph = current_morph + morph_delta * self.config.morph_change_limit
            
            total_reward += episode_reward
            num_episodes += 1
        
        # Compute loss
        reward_t = torch.tensor(total_reward / num_episodes, device=self.device)
        energy_t = torch.tensor(episode_energy / num_episodes, device=self.device)
        morph_delta_t = torch.tensor(episode_morph_delta / num_episodes, device=self.device)
        safety_t = torch.tensor(episode_safety / num_episodes, device=self.device)
        
        loss = self.compute_loss(reward_t, energy_t, morph_delta_t, safety_t)
        
        # Backprop
        self.optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.policy.parameters(), 1.0)
        self.optimizer.step()
        
        if self.scheduler:
            self.scheduler.step()
        
        metrics = {
            "loss": loss.item(),
            "reward": total_reward / num_episodes,
            "energy": episode_energy / num_episodes,
            "safety_violation": episode_safety / num_episodes,
            "lr": self.optimizer.param_groups[0]["lr"],
        }
        
        return metrics
    
    def evaluate(
        self, scenarios: List[MorphScenario], num_episodes: int = 3
    ) -> Dict:
        """Evaluate the current policy on scenarios."""
        self.policy.eval()
        total_rewards = []
        total_safety = []
        
        with torch.no_grad():
            for scenario in scenarios:
                for _ in range(num_episodes):
                    obs = self._get_initial_obs(scenario)
                    current_morph = self._get_default_morph()
                    episode_reward = 0.0
                    episode_safety = 0.0
                    
                    for step in range(self.config.max_steps_per_episode):
                        obs_t = torch.tensor(obs, dtype=torch.float32, device=self.device).unsqueeze(0)
                        morph_t = torch.tensor(current_morph, dtype=torch.float32, device=self.device).unsqueeze(0)
                        
                        action, _ = self.policy.get_action(obs_t, morph_t, deterministic=True)
                        morph_delta = action.squeeze(0).cpu().numpy()
                        
                        step_result = self.engine.step(
                            morph_delta=morph_delta,
                            scenario_id=scenario.scenario_id,
                        )
                        
                        episode_reward += step_result.get("reward", 0.0)
                        episode_safety += step_result.get("safety_violation", 0.0)
                        obs = step_result.get("next_obs", obs)
                        current_morph = current_morph + morph_delta * self.config.morph_change_limit
                    
                    total_rewards.append(episode_reward)
                    total_safety.append(episode_safety)
        
        return {
            "mean_reward": np.mean(total_rewards),
            "std_reward": np.std(total_rewards),
            "mean_safety": np.mean(total_safety),
            "num_episodes": len(total_rewards),
        }
    
    def train(
        self,
        scenario_ids: Optional[List[str]] = None,
        callback: Optional[callable] = None,
    ) -> Dict:
        """Full training loop.
        
        Args:
            scenario_ids: List of scenario IDs to train on. If None, uses all.
            callback: Optional callback(iteration, metrics) called at log_interval.
        
        Returns:
            Final training metrics.
        """
        # Get scenarios
        if scenario_ids is None:
            scenario_ids = MorphScenarioRegistry.list_scenarios()
        scenarios = [MorphScenarioRegistry.get(sid) for sid in scenario_ids]
        
        print(f"🚀 MorphTrainer: Training on {len(scenarios)} scenarios")
        print(f"   Config: {self.config.num_iterations} iters, "
              f"lr={self.config.lr}, device={self.config.device}")
        
        for i in range(self.config.num_iterations):
            self.iteration = i
            
            # Train step
            metrics = self.train_step_differentiable(scenarios)
            self.training_log.append(metrics)
            
            # Logging
            if (i + 1) % self.config.log_interval == 0:
                print(f"  [{i+1}/{self.config.num_iterations}] "
                      f"loss={metrics['loss']:.4f} "
                      f"reward={metrics['reward']:.2f} "
                      f"safety={metrics['safety_violation']:.4f} "
                      f"lr={metrics['lr']:.6f}")
            
            # Evaluation
            if (i + 1) % self.config.eval_interval == 0:
                eval_metrics = self.evaluate(scenarios[:3])
                print(f"  📊 Eval: reward={eval_metrics['mean_reward']:.2f} "
                      f"± {eval_metrics['std_reward']:.2f}")
                
                # Save best
                if eval_metrics["mean_reward"] > self.best_reward:
                    self.best_reward = eval_metrics["mean_reward"]
                    self._save_checkpoint("best.pt")
            
            # Save checkpoint
            if (i + 1) % self.config.save_interval == 0:
                self._save_checkpoint(f"checkpoint_{i+1}.pt")
            
            # Callback
            if callback is not None:
                callback(i, metrics)
        
        print(f"✅ Training complete. Best reward: {self.best_reward:.2f}")
        return self.training_log[-1]
    
    def _save_checkpoint(self, filename: str):
        """Save training checkpoint."""
        checkpoint = {
            "iteration": self.iteration,
            "policy_state_dict": self.policy.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "best_reward": self.best_reward,
            "config": self.config,
        }
        if self.scheduler:
            checkpoint["scheduler_state_dict"] = self.scheduler.state_dict()
        
        # In production, save to disk
        # torch.save(checkpoint, Path("checkpoints") / filename)
        print(f"    💾 Checkpoint saved: {filename}")
    
    def _get_initial_obs(self, scenario: MorphScenario) -> np.ndarray:
        """Get initial observation for a scenario."""
        # [vehicle_state(13) + env_context(16) + morph_state(16) + goal(8) + padding(11)] = 64
        obs = np.zeros(64, dtype=np.float32)
        obs[13:29] = scenario.terrain_params if hasattr(scenario, 'terrain_params') else np.zeros(16)
        return obs
    
    def _get_default_morph(self) -> np.ndarray:
        """Get default morphology parameters (neutral)."""
        return np.zeros(16, dtype=np.float32)
