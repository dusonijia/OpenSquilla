#!/usr/bin/env python3
"""快速测试XPBDSolver（无密钥验证）"""

import requests
import time
import subprocess
import tarfile

API_TOKEN = os.environ.get("AUTODL_TOKEN", "")

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
uuid = inst['data'] if isinstance(inst['data'], str) else inst['data'].get('instance_uuid', inst['data'])
print(f"UUID: {uuid}")

print("\n=== 等待启动 ===")
for i in range(30):
    time.sleep(5)
    resp = requests.get(f"https://api.autodl.com/api/v1/dev/instance/pro/status?instance_uuid={uuid}", headers={"Authorization": API_TOKEN})
    st = resp.json().get("data", "")
    if st == "running":
        time.sleep(15)
        break

snap = requests.get(f"https://api.autodl.com/api/v1/dev/instance/pro/snapshot?instance_uuid={uuid}", headers={"Authorization": API_TOKEN}).json()['data']
ssh_host = snap['proxy_host']
ssh_port = snap['ssh_port']
ssh_pwd = snap['root_password']

print("\n=== 上传代码 ===")
subprocess.run(f'cd /tmp && tar czf morphsim.tar.gz -C "/Users/du/Library/Application Support/@opensquilla/desktop-electron/opensquilla/state/workspace/eiv-research/projects/R5-EIV-Bench/papers/P3-MorphSim" morphsim', shell=True, check=True)
subprocess.run(f'ssh-keyscan -H {ssh_host} -p {ssh_port} >> ~/.ssh/known_hosts 2>/dev/null', shell=True)
subprocess.run(f'scp -o StrictHostKeyChecking=no -P {ssh_port} /tmp/morphsim.tar.gz root@{ssh_host}:/root/', shell=True, check=True)

print("\n=== 跑XPBD测试 ===")
script = '''#!/usr/bin/env python3
import numpy as np
from morphsim.core.xpbd_solver import XPBDSolver
print("XPBD测试")
solver = XPBDSolver([], type("C")().__dict__)
solver.initialize_tetrahedral_mesh([2,3,2], 1.0)
solver.build_distance_constraints(1000.0)
print(f"网格: {len(solver.positions)}节点, {len(solver.constraints)}约束")
for i in range(10):
    solver.step(0.01, 4)
    if i%5==0: print(f"Step {i}: max_disp={np.max(np.abs(solver.positions-solver.rest_positions)):.4f}")
print("✅ XPBD完成")
'''

with open('/tmp/test_xpbd.py', 'w') as f:
    f.write(script)
subprocess.run(f'scp -o StrictHostKeyChecking=no -P {ssh_port} /tmp/test_xpbd.py root@{ssh_host}:/root/', shell=True, check=True)
proc = subprocess.Popen(f'ssh -o StrictHostKeyChecking=no -p {ssh_port} root@{ssh_host}', shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
proc.stdin.write(ssh_pwd+'\n')
proc.stdin.write('PYTHONPATH=/root python3 /root/test_xpbd.py\n')
stdout, stderr = proc.communicate(timeout=120)
print("\n输出:", stdout[-3000:])
if stderr: print("错误:", stderr[-500:])

print("\n=== 释放 ===")
api_post("/api/v1/dev/instance/pro/power_off", {"instance_uuid": uuid})
time.sleep(2)
api_post("/api/v1/dev/instance/pro/release", {"instance_uuid": uuid})
print("✅ 完成")