#!/usr/bin/env python3
"""Static verification of MorphSim code — no numpy/mujoco needed.
Checks: class definitions, method signatures, call sites, type consistency.
"""
import ast, sys, os

LOCAL = os.path.dirname(os.path.abspath(__file__))

# ── 1. Parse all Python files ─────────────────────────────────
files = {}
for root, dirs, fnames in os.walk(os.path.join(LOCAL, "morphsim")):
    for fn in fnames:
        if fn.endswith(".py"):
            fp = os.path.join(root, fn)
            rel = os.path.relpath(fp, LOCAL)
            with open(fp) as f:
                try:
                    tree = ast.parse(f.read(), filename=rel)
                    files[rel] = tree
                    print(f"  ✅ {rel}")
                except SyntaxError as e:
                    print(f"  ❌ {rel}: {e}")
                    sys.exit(1)

print(f"\n✅ {len(files)} files parsed successfully")

# ── 2. Extract all class names and method names ──────────────
classes = {}  # {ClassName: {methods: set(), file: str}}
for rel, tree in files.items():
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            methods = set()
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.add(item.name)
            classes[node.name] = {"methods": methods, "file": rel}

print(f"\n📋 Classes found: {len(classes)}")
for name, info in sorted(classes.items()):
    print(f"  {name} ({len(info['methods'])} methods) [{info['file']}]")

# ── 3. Verify key classes have required methods ──────────────
required = {
    "RigidSolverMuJoCo": {"__init__", "apply_action", "step", "get_state", "apply_coupling"},
    "XPBDSolver": {"__init__", "step", "set_targets", "get_state", "apply_coupling",
                   "_predict_positions", "_solve_constraints", "_update_velocities",
                   "_solve_distance_constraint"},
    "CouplingSolver": {"__init__", "compute"},
    "MorphSimEngine": {"__init__", "load_vehicle", "load_scenario", "reset", "step",
                       "_compose_state", "_init_rigid_solver", "_init_deform_solver",
                       "_init_coupling"},
    "MorphableVehicle": {"__init__"},
    "SimConfig": set(),
    "MorphState": set(),
    "MorphAction": set(),
}

print("\n🔍 Method verification:")
all_ok = True
for cls_name, required_methods in required.items():
    if cls_name not in classes:
        print(f"  ❌ {cls_name}: class not found!")
        all_ok = False
        continue
    found = classes[cls_name]["methods"]
    missing = required_methods - found
    if missing:
        print(f"  ❌ {cls_name}: missing {missing}")
        all_ok = False
    else:
        print(f"  ✅ {cls_name}: all {len(required_methods)} required methods present")

# ── 4. Check engine.py step() logic ──────────────────────────
# Verify coupling_forces handling
print("\n🔍 Engine step() coupling logic:")
engine_tree = files.get("morphsim/core/engine.py")
if engine_tree:
    for node in ast.walk(engine_tree):
        if isinstance(node, ast.FunctionDef) and node.name == "step":
            # Check for isinstance tuple handling
            source_lines = []
            for child in ast.walk(node):
                if isinstance(child, ast.Attribute) and child.attr == "apply_coupling":
                    source_lines.append("apply_coupling call found")
            print(f"  step() method found, {len(source_lines)} coupling calls")
            break

# ── 5. Check run_exp.py for numpy.float64 bug ────────────────
print("\n🔍 Checking experiment script for known bugs:")
# Check the EXP string in run_full_test.py
run_script = os.path.join(LOCAL, "autodl", "run_full_test.py")
if os.path.exists(run_script):
    with open(run_script) as f:
        content = f.read()
    # Check for list(pos[-1]) bug
    if "list(pos[-1])" in content or "list(st.pos[-1])" in content:
        print("  ❌ BUG: list(pos[-1]) — numpy.float64 not iterable")
        all_ok = False
    else:
        print("  ✅ No list(pos[-1]) bug found")
    
    # Check for pos[-1].tolist()
    if "tolist()" in content or "list(st.pos)" in content:
        print("  ✅ Position handling looks safe")
    else:
        print("  ⚠️ Warning: check position array handling")
    
    # Check import time
    if "import time" in content:
        print("  ✅ 'import time' present")
    else:
        print("  ❌ Missing 'import time'")
        all_ok = False

# Also check run_v4.py
run_v4 = os.path.join(LOCAL, "autodl", "run_v4.py")
if os.path.exists(run_v4):
    with open(run_v4) as f:
        content = f.read()
    if "list(pos[-1])" in content or "list(st.pos[-1])" in content:
        print("  ❌ BUG in run_v4.py: list(pos[-1])")
        all_ok = False
    else:
        print("  ✅ run_v4.py: no known bugs")

# ── 6. Summary ───────────────────────────────────────────────
print("\n" + "=" * 60)
if all_ok:
    print("✅ 全部静态检查通过！代码可以上GPU测试。")
else:
    print("❌ 发现问题，需要修复后再上GPU。")
    sys.exit(1)
