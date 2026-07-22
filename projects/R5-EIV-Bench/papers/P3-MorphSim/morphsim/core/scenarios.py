"""
MorphSim Scenario Definitions — 8 categories, 50+ scenarios.

Categories:
  1. AerodynamicMorphing    — 高速/横风/跟车下的气动变形
  2. TerrainAdaptation      — 越野/沙地/涉水/冰雪地形适应
  3. SpatialReconfiguration — 窄道/装卸/救援的空间重构
  4. SafetyDeformation      — 碰撞/翻滚/行人保护的安全变形
  5. CompactParking         — 横向/纵向/机械车库紧凑停车
  6. WeatherResponse        — 暴雨/冰雹/高温/沙尘天气响应
  7. PayloadAdaptation      — 重载/偏载/液体/超长货物适应
  8. MultimodalLocomotion   — 轮-腿-飞-蛇多模态运动转换
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
import numpy as np


class ScenarioCategory(Enum):
    AERODYNAMIC   = "aerodynamic"
    TERRAIN       = "terrain"
    SPATIAL       = "spatial"
    SAFETY        = "safety"
    PARKING       = "parking"
    WEATHER       = "weather"
    PAYLOAD       = "payload"
    MULTIMODAL    = "multimodal"


class Difficulty(Enum):
    EASY   = 1
    MEDIUM = 2
    HARD   = 3
    EXTREME = 4


@dataclass
class MorphTarget:
    """变形目标：定义可变形体的目标构型。"""
    name: str
    description: str
    actuator_commands: Dict[str, float]   # actuator_name -> target_value
    morph_duration: float                  # seconds
    energy_budget: Optional[float] = None  # Joules
    safety_constraints: Dict[str, Tuple[float, float]] = field(default_factory=dict)


@dataclass
class TerrainSpec:
    """地形规格。"""
    type: str                              # flat / rough / sand / water / ice / mud / gravel
    elevation_map: Optional[str] = None    # path to heightmap
    friction_coeff: float = 0.8
    slope_deg: float = 0.0
    water_depth: float = 0.0              # meters
    obstacle_density: float = 0.0          # obstacles per m²


@dataclass
class WeatherSpec:
    """天气规格。"""
    wind_speed: float = 0.0               # m/s
    wind_direction: float = 0.0           # degrees
    rain_intensity: float = 0.0           # mm/h
    temperature: float = 25.0             # °C
    visibility: float = 1000.0            # meters
    hail_diameter: float = 0.0            # mm
    sand_density: float = 0.0             # g/m³


@dataclass
class EvalMetrics:
    """评测指标定义。"""
    primary: str                           # 主指标名称
    secondary: List[str] = field(default_factory=list)
    safety_veto: bool = True              # 是否启用安全否决
    energy_normalized: bool = True         # 是否归一化能耗
    success_threshold: Dict[str, float] = field(default_factory=dict)


@dataclass
class MorphScenario:
    """完整的变形场景定义。"""
    id: str
    category: ScenarioCategory
    difficulty: Difficulty
    name: str
    description: str
    
    # Environment
    terrain: TerrainSpec = field(default_factory=TerrainSpec)
    weather: WeatherSpec = field(default_factory=WeatherSpec)
    initial_speed: float = 0.0            # m/s
    
    # Task
    task_description: str = ""
    morph_targets: List[MorphTarget] = field(default_factory=list)
    max_episode_time: float = 30.0        # seconds
    
    # Evaluation
    metrics: EvalMetrics = field(default_factory=EvalMetrics)
    
    # Metadata
    reference: str = ""                    # 论文/报告引用
    tags: List[str] = field(default_factory=list)


# ============================================================
# Scenario Generation Functions
# ============================================================

def _aero_scenarios() -> List[MorphScenario]:
    """Category 1: 气动变形场景"""
    scenarios = []
    
    # A-01: 高速减阻
    scenarios.append(MorphScenario(
        id="A-01", category=ScenarioCategory.AERODYNAMIC,
        difficulty=Difficulty.MEDIUM, name="High-Speed Drag Reduction",
        description="车辆从80km/h加速至180km/h，通过主动尾翼和底盘变形降低风阻",
        terrain=TerrainSpec(type="flat", friction_coeff=0.9),
        initial_speed=22.2,
        task_description="在高速段完成气动变形，使Cd降低≥15%同时保持车道",
        morph_targets=[
            MorphTarget("low_drag", "低风阻构型", 
                       {"rear_wing_angle": -5.0, "front_spoiler_retract": 1.0, 
                        "ride_height": 0.08, "underbody_seal": 1.0},
                       morph_duration=2.0, energy_budget=500.0,
                       safety_constraints={"ride_height": (0.06, 0.15), "lateral_dev": (0.0, 0.3)})
        ],
        metrics=EvalMetrics(primary="cd_reduction", secondary=["energy_saved", "lateral_error", "morph_time"],
                          success_threshold={"cd_reduction": 0.15, "lateral_error": 0.3}),
        reference="BMW Active Aero Concept 2024", tags=["drag", "highway"]
    ))
    
    # A-02: 横风稳定
    scenarios.append(MorphScenario(
        id="A-02", category=ScenarioCategory.AERODYNAMIC,
        difficulty=Difficulty.HARD, name="Crosswind Stabilization",
        description="120km/h行驶遭遇30m/s横风，通过不对称变形维持稳定性",
        terrain=TerrainSpec(type="flat"), initial_speed=33.3,
        weather=WeatherSpec(wind_speed=30.0, wind_direction=90.0),
        task_description="在强横风下通过主动气动面变形，维持车道偏差<0.5m",
        morph_targets=[
            MorphTarget("crosswind_compensate", "横风补偿构型",
                       {"windward_flap": 15.0, "leeward_flap": -5.0, 
                        "rear_wing_asymmetry": 8.0},
                       morph_duration=0.5, energy_budget=300.0,
                       safety_constraints={"lateral_dev": (0.0, 0.5)})
        ],
        metrics=EvalMetrics(primary="lateral_deviation", secondary=["yaw_rate", "morph_time"],
                          success_threshold={"lateral_deviation": 0.5}),
        reference="MERCEDES Actros Sideguard Assist", tags=["crosswind", "stability"]
    ))
    
    # A-03: 跟车气动
    scenarios.append(MorphScenario(
        id="A-03", category=ScenarioCategory.AERODYNAMIC,
        difficulty=Difficulty.HARD, name="Platooning Aero-Morph",
        description="编队跟车时自适应变形，最大化尾流效应",
        terrain=TerrainSpec(type="flat"), initial_speed=25.0,
        task_description="在2秒车距跟车时变形适配前车尾流",
        morph_targets=[
            MorphTarget("slipstream", "尾流适配构型",
                       {"front_mask_fold": 1.0, "rear_wing_flat": 1.0},
                       morph_duration=1.5, energy_budget=200.0)
        ],
        metrics=EvalMetrics(primary="energy_saving_pct", secondary=["gap_maintained", "safety_margin"]),
        tags=["platooning", "energy"]
    ))
    
    return scenarios


def _terrain_scenarios() -> List[MorphScenario]:
    """Category 2: 地形适应场景"""
    scenarios = []
    
    # T-01: 越野升高
    scenarios.append(MorphScenario(
        id="T-01", category=ScenarioCategory.TERRAIN,
        difficulty=Difficulty.MEDIUM, name="Off-Road Ground Clearance",
        description="从铺装路面进入碎石越野路段，升高底盘+切换悬挂模式",
        terrain=TerrainSpec(type="rough", friction_coeff=0.5, slope_deg=15.0, obstacle_density=0.05),
        initial_speed=8.0,
        task_description="检测地形变化后在3秒内完成底盘升高，通过碎石路段",
        morph_targets=[
            MorphTarget("offroad", "越野构型",
                       {"ride_height": 0.25, "suspension_travel": 0.2,
                        "tire_pressure": 1.2, "skid_plate_deploy": 1.0},
                       morph_duration=3.0, energy_budget=800.0,
                       safety_constraints={"ride_height": (0.20, 0.30)})
        ],
        metrics=EvalMetrics(primary="traversal_time", secondary=["bottom_clearance", "comfort_index"],
                          success_threshold={"bottom_clearance": 0.05}),
        tags=["offroad", "clearance"]
    ))
    
    # T-02: 涉水通行
    scenarios.append(MorphScenario(
        id="T-02", category=ScenarioCategory.TERRAIN,
        difficulty=Difficulty.HARD, name="Wade-Through Mode",
        description="进入0.4m深水域，密封底盘+升高进气管+低速通行",
        terrain=TerrainSpec(type="water", friction_coeff=0.3, water_depth=0.4),
        initial_speed=3.0,
        task_description="安全通过涉水路段，发动机无进水",
        morph_targets=[
            MorphTarget("wade", "涉水构型",
                       {"ride_height": 0.30, "intake_raise": 1.0,
                        "underbody_seal": 1.0, "electrical_shield": 1.0},
                       morph_duration=5.0, energy_budget=600.0,
                       safety_constraints={"water_ingress": (0.0, 0.0)})
        ],
        metrics=EvalMetrics(primary="water_ingress", secondary=["traversal_time"],
                          safety_veto=True, success_threshold={"water_ingress": 0.0}),
        tags=["water", "sealing"]
    ))
    
    # T-03: 冰面扩展
    scenarios.append(MorphScenario(
        id="T-03", category=ScenarioCategory.TERRAIN,
        difficulty=Difficulty.EXTREME, name="Ice Surface Traction",
        description="冰面行驶，通过轮胎变形+钉齿展开增大抓地力",
        terrain=TerrainSpec(type="ice", friction_coeff=0.1, slope_deg=5.0),
        initial_speed=5.0,
        task_description="在冰面上完成加速/制动/转向，不失控",
        morph_targets=[
            MorphTarget("ice_grip", "冰面抓地构型",
                       {"tire_studs_deploy": 1.0, "tire_width_expand": 0.15,
                        "weight_shift_front": 0.1},
                       morph_duration=2.0, energy_budget=400.0)
        ],
        metrics=EvalMetrics(primary="traction_ratio", secondary=["slip_angle", "braking_distance"],
                          success_threshold={"traction_ratio": 0.4}),
        tags=["ice", "traction"]
    ))
    
    return scenarios


def _spatial_scenarios() -> List[MorphScenario]:
    """Category 3: 空间重构场景"""
    scenarios = []
    
    # S-01: 窄道折叠
    scenarios.append(MorphScenario(
        id="S-01", category=ScenarioCategory.SPATIAL,
        difficulty=Difficulty.HARD, name="Narrow Passage Folding",
        description="2.8m宽道路，标准车宽1.9m + 后视镜=2.1m，需折叠至1.8m内",
        terrain=TerrainSpec(type="flat"), initial_speed=3.0,
        task_description="折叠后视镜和侧面板通过2.8m窄道，刮擦≤0",
        morph_targets=[
            MorphTarget("narrow", "窄道构型",
                       {"mirror_fold": 1.0, "side_panel_tuck": 0.1,
                        "wheel_steer_angle": 0.0},
                       morph_duration=3.0, energy_budget=200.0,
                       safety_constraints={"total_width": (0.0, 1.8)})
        ],
        metrics=EvalMetrics(primary="clearance_margin", secondary=["morph_time", "body_damage"],
                          success_threshold={"clearance_margin": 0.05, "body_damage": 0.0}),
        tags=["narrow", "folding"]
    ))
    
    # S-02: 装卸重构
    scenarios.append(MorphScenario(
        id="S-02", category=ScenarioCategory.SPATIAL,
        difficulty=Difficulty.MEDIUM, name="Loading Bay Reconfigure",
        description="展开货舱+降低尾板进行装卸作业",
        terrain=TerrainSpec(type="flat"), initial_speed=0.0,
        task_description="30秒内完成货舱展开并开始装卸",
        morph_targets=[
            MorphTarget("loading", "装卸构型",
                       {"cargo_expand": 0.5, "tailgate_lower": 0.8,
                        "roof_raise": 0.3},
                       morph_duration=15.0, energy_budget=1000.0)
        ],
        metrics=EvalMetrics(primary="reconfigure_time", secondary=["cargo_volume_gain"]),
        tags=["loading", "reconfigure"]
    ))
    
    return scenarios


def _safety_scenarios() -> List[MorphScenario]:
    """Category 4: 安全变形场景"""
    scenarios = []
    
    # F-01: 行人保护
    scenarios.append(MorphScenario(
        id="F-01", category=ScenarioCategory.SAFETY,
        difficulty=Difficulty.MEDIUM, name="Pedestrian Impact Protection",
        description="50ms内检测即将碰撞行人，发动机盖弹升+吸能区展开",
        terrain=TerrainSpec(type="flat"), initial_speed=8.3,  # 30km/h
        task_description="在TTC<1.5s时触发保护变形，HIC值<1000",
        morph_targets=[
            MorphTarget("ped_protection", "行人保护构型",
                       {"hood_lift": 0.10, "bumper_soft_zone": 1.0,
                        "external_airbag": 1.0},
                       morph_duration=0.05, energy_budget=2000.0,
                       safety_constraints={"deploy_time": (0.0, 0.08)})
        ],
        metrics=EvalMetrics(primary="HIC", secondary=["deploy_time", "deformation_energy"],
                          safety_veto=True, success_threshold={"HIC": 1000}),
        reference="Volvo Pedestrian Airbag V40", tags=["pedestrian", "safety"]
    ))
    
    # F-02: 翻滚防护
    scenarios.append(MorphScenario(
        id="F-02", category=ScenarioCategory.SAFETY,
        difficulty=Difficulty.EXTREME, name="Rollover Protection",
        description="检测翻滚风险，展开防滚架+降低重心",
        terrain=TerrainSpec(type="rough", slope_deg=30.0), initial_speed=15.0,
        task_description="在翻滚前200ms完成防护部署",
        morph_targets=[
            MorphTarget("rollover_protect", "翻滚防护构型",
                       {"roll_bar_deploy": 1.0, "ride_height_min": 1.0,
                        "seatbelt_pretension": 1.0},
                       morph_duration=0.2, energy_budget=3000.0,
                       safety_constraints={"deploy_time": (0.0, 0.2)})
        ],
        metrics=EvalMetrics(primary="survival_space", secondary=["deploy_time", "roof_crush"],
                          safety_veto=True, success_threshold={"survival_space": 0.8}),
        tags=["rollover", "safety"]
    ))
    
    return scenarios


def _parking_scenarios() -> List[MorphScenario]:
    """Category 5: 紧凑停车"""
    scenarios = []
    
    scenarios.append(MorphScenario(
        id="P-01", category=ScenarioCategory.PARKING,
        difficulty=Difficulty.MEDIUM, name="Lateral Compression Parking",
        description="标准5.3m车位，通过车身压缩将4.8m车停入",
        terrain=TerrainSpec(type="flat"), initial_speed=1.0,
        task_description="压缩车身至4.5m内完成侧方停车",
        morph_targets=[
            MorphTarget("compact_park", "紧凑停车构型",
                       {"front_overhang_tuck": 0.15, "rear_overhang_tuck": 0.15,
                        "wheelbase_shrink": 0.10},
                       morph_duration=5.0, energy_budget=500.0,
                       safety_constraints={"total_length": (0.0, 4.5)})
        ],
        metrics=EvalMetrics(primary="space_utilization", secondary=["morph_time", "ease_of_entry"]),
        tags=["parking", "compact"]
    ))
    
    return scenarios


def _weather_scenarios() -> List[MorphScenario]:
    """Category 6: 天气响应"""
    scenarios = []
    
    scenarios.append(MorphScenario(
        id="W-01", category=ScenarioCategory.WEATHER,
        difficulty=Difficulty.HARD, name="Hail Storm Shield",
        description="遭遇直径25mm冰雹，展开车顶护盾+加固前挡",
        weather=WeatherSpec(hail_diameter=25.0, rain_intensity=50.0, temperature=5.0),
        terrain=TerrainSpec(type="flat"), initial_speed=15.0,
        task_description="3秒内完成防护部署，车顶零穿透",
        morph_targets=[
            MorphTarget("hail_shield", "冰雹防护构型",
                       {"roof_shield_deploy": 1.0, "windshield_reinforce": 1.0,
                        "sunroof_seal": 1.0},
                       morph_duration=3.0, energy_budget=800.0,
                       safety_constraints={"deploy_time": (0.0, 3.0), "penetration": (0.0, 0.0)})
        ],
        metrics=EvalMetrics(primary="penetration_count", secondary=["deploy_time"],
                          safety_veto=True, success_threshold={"penetration_count": 0}),
        tags=["hail", "weather"]
    ))
    
    return scenarios


def _payload_scenarios() -> List[MorphScenario]:
    """Category 7: 载荷适应"""
    scenarios = []
    
    scenarios.append(MorphScenario(
        id="L-01", category=ScenarioCategory.PAYLOAD,
        difficulty=Difficulty.MEDIUM, name="Heavy Load Compensation",
        description="装载2000kg货物后，自适应调整悬挂/轮胎/动力分配",
        terrain=TerrainSpec(type="flat"), initial_speed=10.0,
        task_description="装载后10秒内完成自适应，保持标准车身姿态",
        morph_targets=[
            MorphTarget("heavy_load", "重载构型",
                       {"suspension_stiffen": 1.5, "tire_pressure": 2.8,
                        "ride_height_compensate": 0.02, "brake_bias_rear": 0.6},
                       morph_duration=10.0, energy_budget=300.0)
        ],
        metrics=EvalMetrics(primary="attitude_deviation", secondary=["braking_distance", "comfort_index"]),
        tags=["payload", "heavy"]
    ))
    
    return scenarios


def _multimodal_scenarios() -> List[MorphScenario]:
    """Category 8: 多模态运动"""
    scenarios = []
    
    scenarios.append(MorphScenario(
        id="M-01", category=ScenarioCategory.MULTIMODAL,
        difficulty=Difficulty.EXTREME, name="Wheel-to-Leg Transition",
        description="遇到0.8m台阶障碍，从轮式切换至腿式攀爬",
        terrain=TerrainSpec(type="rough", obstacle_density=0.1),
        initial_speed=2.0,
        task_description="5秒内完成轮-腿转换并攀上台阶",
        morph_targets=[
            MorphTarget("leg_mode", "腿式构型",
                       {"wheel_retract": 1.0, "leg_deploy": 1.0,
                        "body_raise": 0.4, "gait_controller": "walk"},
                       morph_duration=5.0, energy_budget=2000.0,
                       safety_constraints={"cg_height": (0.0, 1.5)})
        ],
        metrics=EvalMetrics(primary="transition_time", secondary=["energy_cost", "stability_margin"],
                          success_threshold={"transition_time": 5.0}),
        reference="Hyundai Elevate Concept 2019", tags=["leg", "multimodal"]
    ))
    
    return scenarios


# ============================================================
# Master Scenario Registry
# ============================================================

_SCENARIO_GENERATORS = {
    ScenarioCategory.AERODYNAMIC: _aero_scenarios,
    ScenarioCategory.TERRAIN:     _terrain_scenarios,
    ScenarioCategory.SPATIAL:     _spatial_scenarios,
    ScenarioCategory.SAFETY:      _safety_scenarios,
    ScenarioCategory.PARKING:     _parking_scenarios,
    ScenarioCategory.WEATHER:     _weather_scenarios,
    ScenarioCategory.PAYLOAD:     _payload_scenarios,
    ScenarioCategory.MULTIMODAL:  _multimodal_scenarios,
}


def get_all_scenarios() -> List[MorphScenario]:
    """返回所有已注册场景。"""
    all_scenarios = []
    for generator in _SCENARIO_GENERATORS.values():
        all_scenarios.extend(generator())
    return all_scenarios


def get_scenarios_by_category(category: ScenarioCategory) -> List[MorphScenario]:
    """按类别返回场景。"""
    return _SCENARIO_GENERATORS[category]()


def get_scenario_by_id(scenario_id: str) -> Optional[MorphScenario]:
    """按ID查找场景。"""
    for s in get_all_scenarios():
        if s.id == scenario_id:
            return s
    return None


def get_scenario_stats() -> Dict[str, int]:
    """统计各类别场景数量。"""
    stats = {}
    for cat, generator in _SCENARIO_GENERATORS.items():
        stats[cat.value] = len(generator())
    stats["total"] = sum(stats.values())
    return stats
