"""
MorphSim — 执行器模型模块
============================
定义可变形车辆的执行器：气动肌肉、形状记忆合金(SMA)、压电驱动器。
每个执行器类型有独立的动力学模型和约束接口。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np


class ActuatorType(Enum):
    PNEUMATIC = "pneumatic"       # 气动肌肉
    SMA = "sma"                   # 形状记忆合金
    PIEZO = "piezo"               # 压电驱动
    HYDRAULIC = "hydraulic"       # 液压驱动


@dataclass
class ActuatorState:
    """执行器状态"""
    activation: np.ndarray        # 激活度 [0, 1], shape (N,)
    force: np.ndarray             # 输出力, shape (N, 3)
    velocity: np.ndarray          # 收缩速度, shape (N, 3)
    energy_consumption: float     # 累计能耗 (J)
    temperature: Optional[np.ndarray] = None  # 温度(SMA用), shape (N,)


class PneumaticMuscle:
    """气动人工肌肉 (McKibben型)
    
    力-长度特性: F = P * (a * L^2 - b)
    - P: 气压 (Pa)
    - L: 当前长度 / 初始长度比
    - a, b: 几何参数
    """
    
    def __init__(self, n_actuators: int, params: Optional[dict] = None):
        p = params or {}
        self.n = n_actuators
        self.pressure = np.zeros(n_actuators)          # 当前气压
        self.max_pressure = p.get("max_pressure", 6e5)  # 6 bar
        self.a_coeff = p.get("a_coeff", 0.015)
        self.b_coeff = p.get("b_coeff", 0.01)
        self.length_ratio = np.ones(n_actuators)        # L/L0
        self.diameter = p.get("diameter", 0.02)         # 肌肉直径 (m)
        
    def compute_force(self, activation: np.ndarray) -> np.ndarray:
        """根据激活度计算输出力
        
        Args:
            activation: [0, 1] 激活度
        Returns:
            force: (N, 3) 力向量，沿肌肉方向
        """
        self.pressure = activation * self.max_pressure
        magnitude = self.pressure * (self.a_coeff * self.length_ratio**2 - self.b_coeff)
        magnitude = np.maximum(magnitude, 0.0)  # 只能拉不能推
        return magnitude  # 标量力，由Vehicle类分配方向
    
    def update_length(self, new_length_ratio: np.ndarray, dt: float) -> np.ndarray:
        """更新肌肉长度，返回收缩速度"""
        velocity = (new_length_ratio - self.length_ratio) / max(dt, 1e-6)
        self.length_ratio = np.clip(new_length_ratio, 0.6, 1.0)  # 最大收缩40%
        return velocity
    
    def energy_rate(self) -> np.ndarray:
        """能耗率 (W)"""
        # P*V_dot, 简化模型
        return self.pressure * self.diameter**2 * np.abs(self.length_ratio - 1.0) * 0.1


class ShapeMemoryAlloy:
    """形状记忆合金执行器
    
    使用Brinson本构模型的简化版本。
    马氏体体积分数 ξ 由温度和应力决定。
    """
    
    def __init__(self, n_actuators: int, params: Optional[dict] = None):
        p = params or {}
        self.n = n_actuators
        self.temperature = np.full(n_actuators, p.get("ambient_temp", 293.0))  # K
        self.xi = np.ones(n_actuators)  # 马氏体体积分数 [0,1]
        self.Ms = p.get("Ms", 340.0)    # 马氏体起始温度 (K)
        self.Mf = p.get("Mf", 320.0)    # 马氏体结束温度 (K)
        self.As = p.get("As", 360.0)    # 奥氏体起始温度 (K)
        self.Af = p.get("Af", 380.0)    # 奥氏体结束温度 (K)
        self.E_martensite = p.get("E_m", 28e9)   # 马氏体杨氏模量
        self.E_austenite = p.get("E_a", 75e9)    # 奥氏体杨氏模量
        self.max_strain = p.get("max_strain", 0.08)  # 最大可恢复应变 8%
        
    def compute_force(self, activation: np.ndarray, strain: np.ndarray) -> np.ndarray:
        """根据激活度（加热功率）和当前应变计算恢复力"""
        # 激活度映射到目标温度
        target_temp = 293.0 + activation * 200.0  # 最高加热到~500K
        
        # 更新马氏体体积分数
        self._update_xi(target_temp)
        
        # 有效杨氏模量
        E_eff = self.xi * self.E_martensite + (1 - self.xi) * self.E_austenite
        
        # 恢复力 = E_eff * (strain - transformation_strain)
        transformation_strain = self.xi * self.max_strain
        stress = E_eff * (strain - transformation_strain)
        return stress
    
    def _update_xi(self, target_temp: np.ndarray):
        """更新马氏体体积分数（简化Brinson模型）"""
        # 加热过程：ξ → 0 (奥氏体)
        heating = target_temp > self.As
        if np.any(heating):
            self.xi[heating] = np.clip(
                0.5 * np.cos(np.pi / (self.Af - self.As) * (target_temp[heating] - self.As)) + 0.5,
                0.0, self.xi[heating]
            )
        
        # 冷却过程：ξ → 1 (马氏体)
        cooling = target_temp < self.Ms
        if np.any(cooling):
            self.xi[cooling] = np.clip(
                0.5 * np.cos(np.pi / (self.Ms - self.Mf) * (target_temp[cooling] - self.Mf)) + 0.5,
                self.xi[cooling], 1.0
            )
        
        self.temperature = target_temp
    
    def energy_rate(self) -> np.ndarray:
        """SMA加热功耗"""
        # P = I^2 * R, 简化为与温差成正比
        return 50.0 * (self.temperature - 293.0) / 200.0  # 简化模型


class PiezoActuator:
    """压电驱动器
    
    适用于微米级精确定形，响应速度极快。
    应变-电压关系: ε = d33 * V / t
    """
    
    def __init__(self, n_actuators: int, params: Optional[dict] = None):
        p = params or {}
        self.n = n_actuators
        self.voltage = np.zeros(n_actuators)
        self.d33 = p.get("d33", 400e-12)      # 压电常数 (C/N)
        self.thickness = p.get("thickness", 1e-3)  # 层厚 (m)
        self.max_voltage = p.get("max_voltage", 200.0)
        self.capacitance = p.get("capacitance", 1e-6)  # 电容 (F)
        
    def compute_strain(self, activation: np.ndarray) -> np.ndarray:
        """根据激活度计算压电应变"""
        self.voltage = activation * self.max_voltage
        return self.d33 * self.voltage / self.thickness
    
    def energy_rate(self) -> np.ndarray:
        """压电驱动功耗（极低）"""
        return 0.5 * self.capacitance * self.voltage**2 * 1e3  # 简化


class ActuatorModel:
    """执行器模型统一接口
    
    管理车辆上所有执行器的创建、分组和协调。
    """
    
    def __init__(self, config: dict):
        self.actuators: dict[ActuatorType, object] = {}
        self.actuator_groups: dict[str, list[int]] = config.get("groups", {})
        
        for atype, aconf in config.get("actuators", {}).items():
            at = ActuatorType(atype)
            n = aconf["count"]
            params = aconf.get("params", {})
            if at == ActuatorType.PNEUMATIC:
                self.actuators[at] = PneumaticMuscle(n, params)
            elif at == ActuatorType.SMA:
                self.actuators[at] = ShapeMemoryAlloy(n, params)
            elif at == ActuatorType.PIEZO:
                self.actuators[at] = PiezoActuator(n, params)
            elif at == ActuatorType.HYDRAULIC:
                # TODO: 液压执行器
                pass
    
    def step(self, activation: dict[ActuatorType, np.ndarray], 
             dt: float) -> ActuatorState:
        """统一推进所有执行器"""
        all_forces = []
        all_activations = []
        total_energy = 0.0
        
        for atype, act in self.actuators.items():
            act_activation = activation.get(atype, np.zeros(act.n))
            all_activations.append(act_activation)
            
            if isinstance(act, PneumaticMuscle):
                force = act.compute_force(act_activation)
            elif isinstance(act, ShapeMemoryAlloy):
                strain = np.zeros(act.n)  # 由Vehicle提供
                force = act.compute_force(act_activation, strain)
            elif isinstance(act, PiezoActuator):
                force = act.compute_strain(act_activation)
            else:
                force = np.zeros(act.n)
            
            all_forces.append(force)
            total_energy += np.sum(act.energy_rate()) * dt
        
        return ActuatorState(
            activation=np.concatenate(all_activations),
            force=np.zeros((sum(a.n for a in self.actuators.values()), 3)),
            velocity=np.zeros(0),
            energy_consumption=total_energy,
        )
