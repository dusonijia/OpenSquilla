#!/usr/bin/env python3
"""快速测试XPBDSolver（不依赖MuJoCo）"""

import requests
import time
import subprocess
import tarfile

API_TOKEN = os.environ.get("AUTODL_TOKEN", "")

def api_get(path):
    return requests.get(f"https://api.autodl.com{path}", headers={"Authorization": API_TOKEN}).json()

def api_post(path, body):
    return requests.post(f"https://api.autodl.com{path}", headers={"Authorization": API_TOKEN, "Content-Type": "application/json"}, json=body).json()

print("=== 创建RTX 4090实例 ===")
inst = api_post("/api/v1/dev/instance/pro/create", {
    "req_gpu_amount": 1,
    "expand_system_disk_by_gb": 0,
    "gpu_spec_uuid": "v-48g",
    "image_uuid": "base-image-l2t43iu6uk",
    "cuda_v_from": 113,
    "instance_name": "MorphSim-XPBD-Test"
})
if inst.get('code') != 'Success':
    print(f"创建失败: {inst}")
    exit(1)

uuid = inst['data'] if isinstance(inst['data'], str) else inst['data'].get('instance_uuid', inst['data'])
print(f"UUID: {uuid}")

print("\n=== 等待启动 ===")
for i in range(30):
    time.sleep(5)
    st = api_get(f"/api/v1/dev/instance/pro/status?instance_uuid={uuid}").get("data", "")
    print(f"[{i*5}s] {st}")
    if st == "running":
        time.sleep(15)
        break

snap = api_get(f"/api/v1/dev/instance/pro/snapshot?instance_uuid={uuid}")
ssh_host = snap['data']['proxy_host']
ssh_port = snap['data']['ssh_port']
ssh_pwd = snap['data']['root_password']
print(f"SSH: {ssh_host}:{ssh_port}")

print("\n=== 上传代码 ===")
subprocess.run(f'cd /tmp && tar czf morphsim.tar.gz -C /Users/du/Library/Application\ Support/@opensquilla/desktop-electron/opensquilla/state/workspace/eiv-research/projects/R5-EIV-Bench/papers/P3-MorphSim morphsim', shell=True)
subprocess.run(f'scp -P {ssh_port} /tmp/morphsim.tar.gz root@{ssh_host}:/root/', shell=True)

print("\n=== 跑XPBD测试 ===")
script = '''#!/usr/bin/env python3
import numpy as np
from morphsim.core.xpbd_solver import XPBDSolver

print("XPBD求解器测试")
print("="*40)

# 初始化求解器
solver = XPBDSolver([], type("Config")().__dict__)

# 初始化网格
solver.initialize_tetrahedral_mesh([2, 3, 2], 1.0)
print(f"网格节点: {len(solver.positions)} 个")

# 构建距离约束
solver.build_distance_constraints(stiffness=1000.0)
print(f"距离约束: {len(solver.constraints)} 个")

# 模拟10步
for i in range(10):
    solver.step(dt=0.01, substeps=4)
    if i % 5 == 0:
        print(f"Step {i}: max_disp = {np.max(np.abs(solver.positions - solver.rest_positions)):.4f}")

print("\\n=== XPBD测试完成 ===")
print("关键指标:")
print(f"  节点数: {len(solver.positions)}")
print(f"  约束数: {len(solver.constraints)}")
print(f"  速度范围: [{np.min(solver.velocities):.4f}, {np.max(solver.velocities):.4f}]")
'''

# 写入临时文件并上传
with open('/tmp/test_xpbd.py', 'w') as f:
    f.write(script)
subprocess.run(f'scp -P {ssh_port} /tmp/test_xpbd.py root@{ssh_host}:/root/', shell=True)

# SSH执行
result = subprocess.run(f'ssh -p {ssh_port} root@{ssh_host} "PYTHONPATH=/root python3 /root/test_xpbd.py"', shell=True, capture_output=True, text=True, input=ssh_pwd+'\n')
print("\n远程输出:")
print(result.stdout)
if result.stderr:
    print("错误:")
    print(result.stderr[-500:])

print("\n=== 释放实例 ===")
api_post("/api/v1/dev/instance/pro/power_off", {"instance_uuid": uuid})
time.sleep(2)
api_post("/api/v1/dev/instance/pro/release", {"instance_uuid": uuid})
print("✅ 已释放")