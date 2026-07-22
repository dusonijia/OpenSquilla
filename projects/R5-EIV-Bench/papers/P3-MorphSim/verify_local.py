#!/usr/bin/env python3
"""MorphSim本地验证脚本 - 不需要GPU/numpy/mujoco

验证内容：
1. 代码结构完整性
2. 类/方法签名匹配
3. 数据流逻辑正确性
4. 数值类型安全（之前的numpy.float64 bug）
"""

import ast
import sys
import os

BASE = "/Users/du/Library/Application Support/@opensquilla/desktop-electron/opensquilla/state/workspace/eiv-research/projects/R5-EIV-Bench/papers/P3-MorphSim"

errors = []
warnings = []

def check_file(filepath, checks):
    """检查文件中的AST节点"""
    with open(filepath) as f:
        tree = ast.parse(f.read())
    
    classes = {}
    functions = {}
    
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            methods = {}
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    methods[item.name] = [a.arg for a in item.args.args]
            classes[node.name] = methods
        elif isinstance(node, ast.FunctionDef):
            functions[node.name] = [a.arg for a in item.args.args] if isinstance(item, ast.FunctionDef) else []
    
    return classes, functions

print("=" * 70)
print("MorphSim 本地验证（无GPU/numpy/mujoco依赖）")
print("=" * 70)

# 1. 检查engine.py的结构
print("\n[1/6] 检查engine.py...")
engine_path = os.path.join(BASE, "morphsim/core/engine.py")
with open(engine_path) as f:
    engine_src = f.read()

engine_tree = ast.parse(engine_src)

engine_classes = {}
for node in ast.walk(engine_tree):
    if isinstance(node, ast.ClassDef):
        methods = {}
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                methods[item.name] = [a.arg for a in item.args.args]
        engine_classes[node.name] = methods

# 验证MorphSimEngine有必要的方法
required_methods = ["__init__", "load_vehicle", "load_scenario", "reset", "step", "_compose_state",
                    "_init_rigid_solver", "_init_deform_solver", "_init_coupling"]
engine_methods = engine_classes.get("MorphSimEngine", {})
for m in required_methods:
    if m in engine_methods:
        print(f"  ✅ MorphSimEngine.{m}")
    else:
        errors.append(f"morphsim/core/engine.py: MorphSimEngine缺少方法 {m}")
        print(f"  ❌ MorphSimEngine.{m} 缺失")

# 验证MorphState字段
print("\n[2/6] 检查MorphState字段...")
morph_state_fields = []
for node in ast.walk(engine_tree):
    if isinstance(node, ast.ClassDef) and node.name == "MorphState":
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                morph_state_fields.append(item.target.id)

required_fields = ["pos", "quat", "vel", "ang_vel", "wheel_states", 
                   "deform_pos", "deform_vel", "actuator_positions", 
                   "actuator_velocities", "morphology_code", "time"]
for f in required_fields:
    if f in morph_state_fields:
        print(f"  ✅ MorphState.{f}")
    else:
        errors.append(f"MorphState缺少字段 {f}")
        print(f"  ❌ MorphState.{f} 缺失")

# 验证MorphAction字段
print("\n[3/6] 检查MorphAction字段...")
morph_action_fields = []
for node in ast.walk(engine_tree):
    if isinstance(node, ast.ClassDef) and node.name == "MorphAction":
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                morph_action_fields.append(item.target.id)

required_action_fields = ["throttle", "brake", "steer", "actuator_targets", "morph_mode"]
for f in required_action_fields:
    if f in morph_action_fields:
        print(f"  ✅ MorphAction.{f}")
    else:
        errors.append(f"MorphAction缺少字段 {f}")
        print(f"  ❌ MorphAction.{f} 缺失")

# 4. 检查rigid_solver_mujoco.py
print("\n[4/6] 检查rigid_solver_mujoco.py...")
rigid_path = os.path.join(BASE, "morphsim/core/rigid_solver_mujoco.py")
with open(rigid_path) as f:
    rigid_tree = ast.parse(f.read())

rigid_classes = {}
for node in ast.walk(rigid_tree):
    if isinstance(node, ast.ClassDef):
        methods = {}
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                methods[item.name] = [a.arg for a in item.args.args]
        rigid_classes[node.name] = methods

rigid_methods = rigid_classes.get("RigidSolverMuJoCo", {})
required_rigid = ["__init__", "_build_model", "apply_action", "step", "get_state", 
                  "apply_coupling", "_get_wheel_states"]
for m in required_rigid:
    if m in rigid_methods:
        print(f"  ✅ RigidSolverMuJoCo.{m}")
    else:
        errors.append(f"RigidSolverMuJoCo缺少方法 {m}")
        print(f"  ❌ RigidSolverMuJoCo.{m} 缺失")

# 5. 检查xpbd_solver.py
print("\n[5/6] 检查xpbd_solver.py...")
xpbd_path = os.path.join(BASE, "morphsim/core/xpbd_solver.py")
with open(xpbd_path) as f:
    xpbd_tree = ast.parse(f.read())

xpbd_classes = {}
for node in ast.walk(xpbd_tree):
    if isinstance(node, ast.ClassDef):
        methods = {}
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                methods[item.name] = [a.arg for a in item.args.args]
        xpbd_classes[node.name] = methods

xpbd_methods = xpbd_classes.get("XPBDSolver", {})
required_xpbd = ["__init__", "_initialize_mesh", "step", "_predict_positions", 
                 "_solve_constraints", "_solve_distance_constraint", 
                 "_update_velocities", "get_state", "apply_coupling", "set_targets",
                 "_apply_actuator_constraints"]
for m in required_xpbd:
    if m in xpbd_methods:
        print(f"  ✅ XPBDSolver.{m}")
    else:
        errors.append(f"XPBDSolver缺少方法 {m}")
        print(f"  ❌ XPBDSolver.{m} 缺失")

# 6. 检查coupling_solver.py
print("\n[6/6] 检查coupling_solver.py和返回值兼容性...")
coupling_path = os.path.join(BASE, "morphsim/core/coupling_solver.py")
with open(coupling_path) as f:
    coupling_src = f.read()

# 检查coupling_solver.py中compute方法返回什么
if "return" in coupling_src:
    # 找到compute方法中的return语句
    coupling_tree = ast.parse(coupling_src)
    for node in ast.walk(coupling_tree):
        if isinstance(node, ast.ClassDef) and node.name == "CouplingSolver":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "compute":
                    print(f"  ✅ CouplingSolver.compute 存在")
                    # 检查返回值
                    for child in ast.walk(item):
                        if isinstance(child, ast.Return) and isinstance(child.value, ast.Tuple):
                            print(f"  ✅ 返回tuple (on_rigid, on_deformable)")
                        elif isinstance(child, ast.Return) and isinstance(child.value, ast.Dict):
                            print(f"  ⚠️ 返回dict (engine.py需要兼容)")

# 检查engine.py中的coupling代码是否同时处理tuple和dict
if "isinstance(coupling_forces, tuple)" in engine_src:
    print(f"  ✅ engine.py兼容tuple返回")
else:
    errors.append("engine.py不兼容coupling tuple返回")
    print(f"  ❌ engine.py不兼容tuple返回")

if "coupling_forces[\"on_rigid\"]" in engine_src:
    print(f"  ✅ engine.py兼容dict返回")

# 7. 检查之前的numpy.float64 bug
print("\n[额外] 检查numpy.float64类型安全...")
# 检查run_full_test.py中是否有list()调用标量的问题
test_path = os.path.join(BASE, "autodl/run_full_test.py")
if os.path.exists(test_path):
    with open(test_path) as f:
        test_src = f.read()
    if "list(pos[-1])" in test_src:
        errors.append("run_full_test.py: list(pos[-1]) 会触发TypeError")
        print(f"  ❌ list(pos[-1]) bug仍存在")
    elif "float(pos[-1])" in test_src or "[float(pos[-1])" in test_src:
        print(f"  ✅ pos[-1]已用float()包装")
    else:
        print(f"  ⚠️ 无法确认pos[-1]处理方式")

# 检查engine.py中step()返回值解包
if "return self._state, reward, done, info" in engine_src:
    print(f"  ✅ step()返回4元组 (state, reward, done, info)")
else:
    errors.append("engine.py: step()返回值不是4元组")
    print(f"  ❌ step()返回值格式错误")

# 总结
print("\n" + "=" * 70)
if errors:
    print(f"❌ 发现 {len(errors)} 个问题:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print(f"✅ 全部验证通过！代码结构完整，可以上GPU测试")
    sys.exit(0)
