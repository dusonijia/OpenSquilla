"""
MorphSim — Baseline Policies
============================
4类基线策略用于对比实验
"""

from __future__ import annotations
import numpy as np
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class PolicyOutput:
    """策略输出"""
    actions: Dict[str, float]   # actuator_name -> target_value
    info: Dict[str, Any]


class FixedPolicy:
    """固定策略 — 不触发任何变形，保持默认形态"""
    
    def __init__(self, vehicle):
        self.vehicle = vehicle
        self.default_actions = {
            name: act.default_pos 
            for name, act in vehicle.actuators.items()
        }
    
    def __call__(self, obs: Dict[str, Any]) -> PolicyOutput:
        return PolicyOutput(actions=self.default_actions.copy(), info={"policy": "fixed"})


class RuleBasedPolicy:
    """规则策略 — 基于车辆动力学直觉的手工规则"""
    
    def __init__(self, vehicle):
        self.vehicle = vehicle
    
    def __call__(self, obs: Dict[str, Any]) -> PolicyOutput:
        actions = {}
        speed = obs.get("speed", 0.0)
        terrain = obs.get("terrain_type", "flat")
        lateral_acc = obs.get("lateral_acceleration", 0.0)
        heading_error = obs.get("heading_error", 0.0)
        
        for name, act in self.vehicle.actuators.items():
            # 高速 → 气动优化（降低底盘、收拢后视镜）
            if "chassis_height" in name:
                actions[name] = 0.3 if speed > 30.0 else act.default_pos
            elif "mirror_fold" in name:
                actions[name] = 0.9 if speed > 40.0 else 0.0
            # 越野 → 升高底盘、展开轮胎
            elif "chassis" in name and terrain in ("mud", "gravel", "rock"):
                actions[name] = 0.8
            elif "tire_width" in name and terrain in ("mud", "sand"):
                actions[name] = 0.9
            # 急弯 → 主动侧倾补偿
            elif "active_roll" in name:
                actions[name] = np.clip(-lateral_acc * 0.3, -1.0, 1.0)
            # 泊车 → 紧凑形态
            elif "body_compress" in name:
                actions[name] = 0.0  # default
            else:
                actions[name] = act.default_pos
        
        return PolicyOutput(actions=actions, info={"policy": "rule_based"})


class PDPolicy:
    """PD控制器策略 — 跟踪参考轨迹的PD控制 + 变形触发"""
    
    def __init__(self, vehicle, kp: float = 1.0, kd: float = 0.1):
        self.vehicle = vehicle
        self.kp = kp
        self.kd = kd
        self._prev_error = 0.0
    
    def __call__(self, obs: Dict[str, Any]) -> PolicyOutput:
        actions = {}
        heading_error = obs.get("heading_error", 0.0)
        d_error = heading_error - self._prev_error
        self._prev_error = heading_error
        
        steer = np.clip(self.kp * heading_error + self.kd * d_error, -1.0, 1.0)
        speed = obs.get("speed", 0.0)
        
        for name, act in self.vehicle.actuators.items():
            if "steering" in name:
                actions[name] = steer
            elif "chassis_height" in name:
                actions[name] = 0.3 if speed > 30.0 else act.default_pos
            elif "active_roll" in name:
                actions[name] = np.clip(-obs.get("lateral_acceleration", 0.0) * 0.2, -1, 1)
            else:
                actions[name] = act.default_pos
        
        return PolicyOutput(actions=actions, info={"policy": "pd"})


class RLBasedPolicy:
    """强化学习策略 — PPO/SAC训练（接口占位，训练后加载权重）"""
    
    def __init__(self, vehicle, checkpoint_path: Optional[str] = None):
        self.vehicle = vehicle
        self.checkpoint_path = checkpoint_path
        self._model = None
    
    def load(self, checkpoint_path: str):
        """加载训练好的RL模型"""
        # TODO: 实现PPO/SAC模型加载
        import pickle
        with open(checkpoint_path, "rb") as f:
            self._model = pickle.load(f)
    
    def __call__(self, obs: Dict[str, Any]) -> PolicyOutput:
        if self._model is None:
            # 未加载模型时退化为固定策略
            actions = {name: act.default_pos for name, act in self.vehicle.actuators.items()}
            return PolicyOutput(actions=actions, info={"policy": "rl_fallback"})
        
        # TODO: 实现RL推理
        obs_vec = self._obs_to_vec(obs)
        action_vec = self._model.predict(obs_vec)
        actions = self._vec_to_actions(action_vec)
        return PolicyOutput(actions=actions, info={"policy": "rl"})
    
    def _obs_to_vec(self, obs: Dict) -> np.ndarray:
        """将观测字典转为向量"""
        keys = sorted(obs.keys())
        return np.array([obs.get(k, 0.0) for k in keys], dtype=np.float32)
    
    def _vec_to_actions(self, vec: np.ndarray) -> Dict[str, float]:
        """将动作向量转为执行器字典"""
        actions = {}
        for i, (name, act) in enumerate(sorted(self.vehicle.actuators.items())):
            if i < len(vec):
                actions[name] = np.clip(vec[i], act.pos_min, act.pos_max)
            else:
                actions[name] = act.default_pos
        return actions
