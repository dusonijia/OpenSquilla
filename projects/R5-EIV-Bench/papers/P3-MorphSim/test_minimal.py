#!/usr/bin/env python3
"""
MorphSim最小化测试 - 快速验证核心功能
不依赖复杂环境，只测试导入和基本类功能
"""

import sys
import traceback

print("=" * 80)
print("MorphSim 最小化测试")
print("=" * 80)

# 测试1: 基础导入
print("\n[1/5] 测试基础导入...")
try:
    from morphsim.core.engine import MorphSimEngine, SimConfig, MorphState, MorphAction
    print("  ✅ engine模块导入成功")
except Exception as e:
    print(f"  ❌ engine导入失败: {e}")
    traceback.print_exc()
    sys.exit(1)

try:
    from morphsim.core.vehicle import MorphableVehicle, DeformableRegion, MorphMode
    print("  ✅ vehicle模块导入成功")
except Exception as e:
    print(f"  ❌ vehicle导入失败: {e}")
    traceback.print_exc()
    sys.exit(1)

try:
    from morphsim.scenarios.loader import ScenarioLoader
    print("  ✅ scenarios模块导入成功")
except Exception as e:
    print(f"  ❌ scenarios导入失败: {e}")
    traceback.print_exc()
    sys.exit(1)

# 测试2: 场景加载
print("\n[2/5] 测试场景加载...")
try:
    loader = ScenarioLoader()
    cats = loader.list_categories()
    scenarios = loader.list_scenarios()
    print(f"  ✅ 场景分类: {cats}")
    print(f"  ✅ 总场景数: {len(scenarios)}")
    print(f"  ✅ 场景列表: {scenarios[:5]}...")
except Exception as e:
    print(f"  ❌ 场景加载失败: {e}")
    traceback.print_exc()
    sys.exit(1)

# 测试3: 加载单个场景
print("\n[3/5] 测试A-01场景加载...")
try:
    spec = loader.get('A-01')
    print(f"  ✅ A-01名称: {spec.name}")
    print(f"  ✅ A-01难度: {spec.difficulty}")
    print(f"  ✅ A-01地形: {spec.terrain_type}")
    print(f"  ✅ A-01活跃参数: {spec.active_morph_params}")
except Exception as e:
    print(f"  ❌ A-01加载失败: {e}")
    traceback.print_exc()
    sys.exit(1)

# 测试4: 创建配置对象
print("\n[4/5] 测试配置对象...")
try:
    config = SimConfig(dt=0.01, n_substeps=10)
    print(f"  ✅ SimConfig创建成功: dt={config.dt}")
    state = MorphState()
    print(f"  ✅ MorphState创建成功")
    action = MorphAction()
    print(f"  ✅ MorphAction创建成功")
except Exception as e:
    print(f"  ❌ 配置对象创建失败: {e}")
    traceback.print_exc()
    sys.exit(1)

# 测试5: 创建车辆对象
print("\n[5/5] 测试车辆对象...")
try:
    vehicle = MorphableVehicle()
    print(f"  ✅ MorphableVehicle创建成功")
except Exception as e:
    print(f"  ❌ 车辆对象创建失败: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 80)
print("✅ 所有测试通过！MorphSim核心功能正常")
print("=" * 80)
print("\n下一步：在GPU服务器上运行真实仿真实验")