# MorphScenario-50 详细场景规格

> 8类50+标准化评测场景
> 用于ICRA 2027论文P3-MorphSim

---

## 场景标准化格式

```yaml
Scenario_ID: <CATEGORY>_<ID>
Name: <场景名称>
Difficulty: Easy / Medium / Hard / Extreme
Duration: <仿真时长(秒)>

Terrain:
  type: <flat/hill/offroad/curved/slope>
  parameters:
    friction: <摩擦系数>
    roughness: <粗糙度>
    obstacles: <障碍物列表>

Wind:
  speed: <风速(m/s)>
  direction: <风向角度>
  turbulence: <湍流强度>

Task:
  goal: <目标描述>
  success_condition: <成功条件>
  constraints: <约束列表>

Morph_Constraints:
  allowed_morph: <允许的变形类别>
  max_deformation: <最大变形量>
  energy_budget: <能耗预算>

Metrics:
  primary: <主评测指标>
  secondary: <次级指标>
  baseline: <刚性车辆基线值>
```

---

## Category A: 气动变形
**目标：通过主动形状调整优化空气动力学效率**

### A-01: 高速巡航减阻
- **Difficulty**: Medium
- **Duration**: 30s
- **Terrain**: flat highway, friction=0.8
- **Wind**: headwind 15 m/s, turbulence=0.2
- **Task**: 维持25 m/s速度，最小化能量消耗
- **Morph**: ground_clearance, spoiler_angle, roof_angle
- **Metrics**: drag_coefficient, energy_consumption
- **Baseline**: Cd=0.28, Energy=1.0

### A-02: 侧风稳定性
- **Difficulty**: Hard
- **Duration**: 20s
- **Wind**: crosswind 20 m/s, direction=90°, turbulence=0.4
- **Task**: 保持车道偏离 <0.5m
- **Morph**: ground_clearance, side_cam_angle, spoiler_angle
- **Metrics**: lateral_deviation, roll_angle
- **Baseline**: dev=1.2m, roll=4.5°

### A-03: 尾随气流利用
- **Difficulty**: Medium
- **Duration**: 40s
- **Task**: 紧随前车3-5m，最小化能耗
- **Morph**: front_bumper_shaping, rear_diffuser
- **Metrics**: drafting_efficiency, safe_distance
- **Baseline**: drag=0.95

### A-04: 爬坡气动优化
- **Difficulty**: Medium
- **Terrain**: uphill 10%, friction=0.7
- **Task**: 以20 m/s爬升，最小化动力需求
- **Morph**: ground_clearance, roof_slope, rear_spoiler
- **Metrics**: power_output, drag_coefficient
- **Baseline**: power=85 kW

### A-05: 主动进气栅控制
- **Difficulty**: Easy
- **Duration**: 25s
- **Task**: 根据速度和温度调整进气开口
- **Morph**: grille_opening_ratio
- **Metrics**: cooling_efficiency, drag_coefficient
- **Baseline**: drag=0.32, cooling=0.85

### A-06: 湍流减振
- **Difficulty**: Hard
- **Wind**: highly turbulent (turbulence=0.6), random gusts
- **Task**: 保持垂直加速度 <1.5 m/s²
- **Morph**: suspension_stiffness, damping, body_shape
- **Metrics**: vertical_acceleration, ride_comfort
- **Baseline**: accel=2.8 m/s²

### A-07: 超高速突破（250 km/h+）
- **Difficulty**: Extreme
- **Task**: 稳定维持70 m/s
- **Morph**: full_aero_package (ground_clearance, wings, underbody)
- **Metrics**: stability_margin, lift_coefficient
- **Baseline**: unstable at >60 m/s

---

## Category B: 地形适应
**目标：通过形态调整适应不同路面条件**

### B-01: 越野通过性
- **Difficulty**: Medium
- **Terrain**: offroad, friction=0.5, roughness=0.3
- **Obstacles**: rocks (0.2-0.5m), ruts
- **Task**: 穿越500m越野路段
- **Morph**: ground_clearance, suspension_travel, wheel_base
- **Metrics**: traversal_time, ground_contact
- **Baseline**: time=180s, slip=0.25

### B-02: 障碍物攀爬
- **Difficulty**: Hard
- **Obstacles**: 0.6m vertical step
- **Task**: 翻越垂直台阶
- **Morph**: ground_clearance, suspension_articulation, front_overhang
- **Metrics**: success_rate, impact_force
- **Baseline**: success=0.4

### B-03: 泥地脱困
- **Difficulty**: Hard
- **Terrain**: mud, friction=0.3
- **Task**: 从陷入中脱困
- **Morph**: wheel_rip_spread, ground_clearance, tire_pressure
- **Metrics**: escape_time, wheel_slip
- **Baseline**: fail

### B-04: 沙地穿越
- **Difficulty**: Medium
- **Terrain**: sand, friction=0.4, sinkage_risk=high
- **Task**: 穿越300m沙地
- **Morph**: ground_clearance, wheel_width, tire_surface_area
- **Metrics**: sinkage_depth, energy_efficiency
- **Baseline**: sinkage=0.15m

### B-05: 冰雪路面
- **Difficulty**: Medium
- **Terrain**: ice, friction=0.15
- **Task**: 保持20 m/s速度，无打滑
- **Morph**: ground_clearance, studded_tires, weight_distribution
- **Metrics**: traction_coefficient, lateral_stability
- **Baseline**: traction=0.18

### B-06: 崎岖山路
- **Difficulty**: Extreme
- **Terrain**: mountain, friction=0.6, irregular_surface
- **Task**: 穿越1km山路，最小化车身损伤
- **Morph**: suspension_articulation, body_rigidity, ground_clearance
- **Metrics**: structural_damage, traversal_time
- **Baseline**: damage=0.3, time=420s

### B-07: 涉水通过
- **Difficulty**: Medium
- **Terrain**: water_depth=0.8m, flow_velocity=1.5 m/s
- **Task**: 横渡河流
- **Morph**: ground_clearance, water_sealing, intake_height
- **Metrics**: water_intake_risk, traversal_success
- **Baseline**: water_intake_risk=0.7

---

## Category C: 空间重构
**目标：改变车辆几何形态适应空间需求**

### C-01: 紧凑停车
- **Difficulty**: Medium
- **Task**: 停入2.8m × 5.0m车位
- **Morph**: body_length, body_width, mirror_fold
- **Metrics**: parking_success, fit_score
- **Baseline**: fail (length too long)

### C-02: 货物装载扩容
- **Difficulty**: Easy
- **Task**: 最大化载货空间
- **Morph**: rear_overhang, roof_height, cargo_expansion
- **Metrics**: cargo_volume, loading_efficiency
- **Baseline**: volume=1.2 m³

### C-03: 座舱模式切换
- **Difficulty**: Medium
- **Task**: 行驶模式→办公模式→休息模式
- **Morph**: seat_reconfig, dashboard_fold, interior_layout
- **Metrics**: transition_time, mode_stability
- **Baseline**: no transition possible

### C-04: 窄道通行
- **Difficulty**: Hard
- **Obstacles**: 2.2m width tunnel
- **Task**: 通过狭窄通道
- **Morph**: body_width, mirror_fold, camera_retract
- **Metrics**: clearance_margin, collision_risk
- **Baseline**: collision_risk=0.6

### C-05: 车辆折叠
- **Difficulty**: Extreme
- **Task**: 从5.0m长缩短至3.0m
- **Morph**: multi_fold_joints, chassis_split
- **Metrics**: fold_success_rate, structural_integrity
- **Baseline**: no folding mechanism

### C-06: 展开工作空间
- **Difficulty**: Medium
- **Task**: 从行驶状态展开为工作台
- **Morph**: side_panels, roof_extension, cargo_floor
- **Metrics**: workspace_area, setup_time
- **Baseline**: area=2.5 m²

### C-07: 低高度穿越
- **Difficulty**: Hard
- **Obstacles**: 1.6m height clearance
- **Task**: 通过低矮通道
- **Morph**: roof_height, antenna_retract, window_seal
- **Metrics**: vertical_clearance, structural_stress
- **Baseline**: fail (height too tall)

---

## Category D: 安全变形
**目标：通过形态调整提升安全性**

### D-01: 碰撞吸能
- **Difficulty**: Medium
- **Task**: 正面碰撞（50 km/h），最小化乘员受伤
- **Morph**: crumple_zone_activation, seat_preload, steering_retract
- **Metrics**: deceleration_g, injury_index
- **Baseline**: injury_index=0.85

### D-02: 侧碰保护
- **Difficulty**: Hard
- **Task**: 侧向碰撞（40 km/h），保护乘员
- **Morph**: side_structure_stiffening, door_reinforcement, seat_shift
- **Metrics**: intrusion_distance, injury_risk
- **Baseline**: intrusion=0.35m

### D-03: 翻车防护
- **Difficulty**: Extreme
- **Task**: 防止翻车或降低翻车伤害
- **Morph**: center_of_gravity, roll_stiffness, active_anti_roll
- **Metrics**: roll_over_risk, roof_crush_resistance
- **Baseline**: roll_over_risk=0.3

### D-04: 行人保护
- **Difficulty**: Medium
- **Task**: 30 km/h碰撞行人，最小化伤害
- **Morph**: hood_softening, bumper_pop, windshield_angle
- **Metrics**: pedestrian_injury_score
- **Baseline**: injury=0.7

### D-05: 紧急制动距离缩短
- **Difficulty**: Easy
- **Task**: 100 km/h→0 最短制动距离
- **Morph**: air_brake, downforce_increase, weight_shift
- **Metrics**: braking_distance, stability
- **Baseline**: distance=42m

### D-06: 溜坡阻尼
- **Difficulty**: Medium
- **Terrain**: downhill 15%, friction=0.6
- **Task**: 防止溜坡
- **Morph**: wheel_rip_spread, ground_clearance, suspension_lock
- **Metrics**: slip_ratio, stopping_distance
- **Baseline**: slip=0.2

---

## Category E: 紧凑/多功能
**目标：小空间多功能利用**

### E-01: 横向停车辅助
- **Difficulty**: Medium
- **Task**: 横向泊入狭窄车位
- **Morph**: wheels_4ws, body_length, steering_angle
- **Metrics**: parking_success, time
- **Baseline**: fail

### E-02: 旋转掉头
- **Difficulty**: Hard
- **Task**: 有限空间内完成掉头
- **Morph**: wheels_4ws_zero_turn, body_rotation
- **Metrics**: turn_radius, time
- **Baseline**: radius=6.0m

### E-03: 对角泊车
- **Difficulty**: Hard
- **Task**: 斜角泊入车位
- **Morph**: steering_4ws, body_length, rear_steering
- **Metrics**: approach_angle, success_rate
- **Baseline**: fail

### E-04: 阶梯攀爬
- **Difficulty**: Hard
- **Obstacles**: 0.3m step, 10 steps
- **Task**: 攀爬楼梯
- **Morph**: wheel-leg_conversion, step_height_adjustment
- **Metrics**: climb_success, time
- **Baseline**: fail

### E-05: 驻车空间压缩
- **Difficulty**: Medium
- **Task**: 停车后压缩占用空间
- **Morph**: wheel_fold, body_compression, roof_retract
- **Metrics**: footprint_reduction, compression_time
- **Baseline**: reduction=0

---

## Category F: 天气响应
**目标：根据天气自动调整形态**

### F-01: 防雨模式
- **Difficulty**: Easy
- **Weather**: heavy_rain
- **Task**: 优化排水和视线
- **Morph**: windshield_angle, door_seal, wiper_path
- **Metrics**: water_intrusion, visibility
- **Baseline**: visibility=0.6

### F-02: 防雪模式
- **Difficulty**: Medium
- **Weather**: snow_accumulation
- **Task**: 防止积雪影响
- **Morph**: heated_surface, roof_slope, grille_heater
- **Metrics**: snow_accumulation, energy_consumption
- **Baseline**: accumulation=5cm

### F-03: 防风模式
- **Difficulty**: Medium
- **Weather**: strong_wind (gusts 30 m/s)
- **Task**: 保持稳定
- **Morph**: ground_clearance, side_panel_angle, spoiler_adjust
- **Metrics**: lateral_displacement, stability_margin
- **Baseline**: displacement=1.5m

### F-04: 防雾模式
- **Difficulty**: Easy
- **Weather**: fog
- **Task**: 优化内外空气流通
- **Morph**: ventilation_pattern, defrost_zone, window_tint
- **Metrics**: defog_time, visibility
- **Baseline**: time=180s

### F-05: 高温模式
- **Difficulty**: Medium
- **Weather**: 40°C ambient
- **Task**: 最小化舱内温度
- **Morph**: sunroof_vent, reflective_surface, heat_insulation
- **Metrics**: cabin_temperature, energy_efficiency
- **Baseline**: temp=45°C

---

## Category G: 载荷适应
**目标：根据载重动态调整**

### G-01: 重载模式
- **Difficulty**: Medium
- **Payload**: 1500 kg
- **Task**: 安全承载，稳定行驶
- **Morph**: suspension_stiffness, ground_clearance, tire_pressure
- **Metrics**: suspension_deflection, energy_efficiency
- **Baseline**: deflection=120mm

### G-02: 偏载平衡
- **Difficulty**: Hard
- **Payload**: 不均匀分布（70%在后轴）
- **Task**: 保持平衡
- **Morph**: active_suspension, weight_shift, stiffness_distribution
- **Metrics**: lateral_stability, cornering_stiffness
- **Baseline**: instability_warning

### G-03: 拖挂模式
- **Difficulty**: Medium
- **Task**: 拖拽2000 kg trailer
- **Morph**: hitch_reinforcement, rear_suspension_stiffness, steering_assist
- **Metrics**: trailer_sway, braking_distance
- **Baseline**: sway=0.15m

### G-04: 长货承载
- **Difficulty**: Hard
- **Payload**: 6m 长货物
- **Task**: 安全运输长货
- **Morph**: rear_extension, cargo_restraint, suspension_compliance
- **Metrics**: cargo_stability, vehicle_stability
- **Baseline**: fail

### G-05: 液体载荷
- **Difficulty**: Medium
- **Payload**: 800L 水/燃料
- **Task**: 抑制液体晃动
- **Morph**: baffles, tank_geometry, suspension_damping
- **Metrics**: liquid_sloshing, vehicle_stability
- **Baseline**: sloshing=0.3m

---

## Category H: 多模态运动
**目标：融合多种运动模式**

### H-01: 轮腿转换
- **Difficulty**: Extreme
- **Task**: 轮式高速→腿式越障→轮式巡航
- **Morph**: wheel_leg_mechanism, body_articulation, drive_train_switch
- **Metrics**: transition_time, energy_efficiency
- **Baseline**: no conversion

### H-02: 水陆两栖
- **Difficulty**: Extreme
- **Task**: 陆地行驶→水上航行→陆地
- **Morph**: buoyancy_adjustment, propeller_deploy, wheel_retract
- **Metrics**: transition_success, dual_mode_speed
- **Baseline**: no amphibious

### H-03: 垂直爬行
- **Difficulty**: Extreme
- **Task**: 攀爬垂直墙面
- **Morph**: suction_cups, wheel_conversion, body_anchoring
- **Metrics**: climb_speed, wall_adhesion
- **Baseline**: fail

### H-04: 跳跃能力
- **Difficulty**: Extreme
- **Task**: 跳越2m壕沟
- **Morph**: spring_mechanism, body_recoil, landing_absorption
- **Metrics**: jump_distance, landing_stability
- **Baseline**: jump_distance=0m

### H-05: 飞行辅助
- **Difficulty**: Extreme
- **Task**: 低空飞行过渡（<5m，10s）
- **Morph**: wing_deploy, lift_generation, flight_control
- **Metrics**: flight_duration, transition_smoothness
- **Baseline**: no flight

### H-06: 轨道调整
- **Difficulty**: Medium
- **Task**: 四轮转向实现蟹行/原地旋转
- **Morph**: steering_4ws, tire_angle_independent, wheel_sync
- **Metrics**: maneuverability, energy_efficiency
- **Baseline**: no 4WS

---

## 场景统计

| 类别 | 场景数 | 难度分布 | 主要形态维度 |
|------|--------|----------|--------------|
| A 气动变形 | 7 | M/M/M/H/M/H/E | 9,11,12,5,6 |
| B 地形适应 | 7 | M/H/H/M/M/E/M | 1,7,8,10,12 |
| C 空间重构 | 7 | M/E/M/H/E/M/H | 2,3,4,11 |
| D 安全变形 | 6 | M/H/E/M/M/M | 1,5,7,8 |
| E 紧凑多功能 | 5 | M/H/H/H/M | 1,2,3,5 |
| F 天气响应 | 5 | E/M/M/M/M | 5,6,11,12 |
| G 载荷适应 | 5 | M/H/M/H/M | 7,8,9,12 |
| H 多模态 | 6 | E×5, M×1 | All |
| **总计** | **50** | Easy:8, Med:19, Hard:14, Ext:9 | - |

---

## 评测协议

### 评分标准
每个场景运行20次，取平均：
- **任务完成度** (0-1): 是否达成目标
- **形态适应度** (0-1): 形态调整合理性
- **能耗效率** (0-1): 能耗/性能比
- **安全合规** (0-1): 约束满足率
- **综合得分** = 加权和 (具体权重视场景而定)

### 基线对比
每种策略（刚性、启发式、PPO、可微优化）在所有50场景运行，统计：
- 平均综合得分
- 难度分层表现
- 形态维度分析
- 能耗-性能权衡曲线

### 论文Figure规划
- **Fig.1**: 8类场景示意图
- **Fig.2**: 混合刚-柔仿真架构
- **Fig.3**: 形态空间（12维参数可视化）
- **Fig.4**: 4种策略对比（得分雷达图）
- **Fig.5**: 气动/地形两个代表性场景案例
- **Table I**: 50场景完整参数表
- **Table II**: 基线对比定量结果