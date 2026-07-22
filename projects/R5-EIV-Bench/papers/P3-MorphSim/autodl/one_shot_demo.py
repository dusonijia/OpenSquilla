#!/usr/bin/env python3
"""一键GPU Demo: 创建实例→上传→跑10秒demo→下载→释放"""

import requests
import subprocess
import time
import json
import os
import sys

API_TOKEN = os.environ.get("AUTODL_TOKEN", "")
BASE = "https://api.autodl.com"
HEADERS = {"Authorization": API_TOKEN, "Content-Type": "application/json"}
LOCAL_CODE = "/Users/du/Library/Application Support/@opensquilla/desktop-electron/opensquilla/state/workspace/eiv-research/projects/R5-EIV-Bench/papers/P3-MorphSim"
RESULTS_DIR = LOCAL_CODE + "/results"

os.makedirs(RESULTS_DIR, exist_ok=True)

def api_post(path, body=None):
    resp = requests.post(f"{BASE}{path}", headers=HEADERS, json=body or {}, timeout=30)
    return resp.json()

def api_get(path):
    resp = requests.get(f"{BASE}{path}", headers=HEADERS, timeout=30)
    return resp.json()

def ssh_cmd(host, port, password, command, timeout=120):
    """用expect执行SSH命令"""
    exp_script = f'''#!/usr/bin/expect -f
set timeout {timeout}
spawn ssh -o StrictHostKeyChecking=no -p {port} root@{host} "{command}"
expect "password:"
send "{password}\r"
expect eof
'''
    with open("/tmp/ssh_cmd.exp", "w") as f:
        f.write(exp_script)
    os.system("chmod +x /tmp/ssh_cmd.exp")
    result = subprocess.run(["expect", "/tmp/ssh_cmd.exp"], capture_output=True, text=True, timeout=timeout+10)
    return result.stdout + result.stderr

def scp_upload(host, port, password, local, remote, timeout=120):
    """用expect执行SCP上传"""
    exp_script = f'''#!/usr/bin/expect -f
set timeout {timeout}
spawn scp -o StrictHostKeyChecking=no -P {port} {local} root@{host}:{remote}
expect "password:"
send "{password}\r"
expect eof
'''
    with open("/tmp/scp_upload.exp", "w") as f:
        f.write(exp_script)
    os.system("chmod +x /tmp/scp_upload.exp")
    result = subprocess.run(["expect", "/tmp/scp_upload.exp"], capture_output=True, text=True, timeout=timeout+10)
    return result.stdout + result.stderr

def scp_download(host, port, password, remote, local, timeout=60):
    """用expect执行SCP下载"""
    exp_script = f'''#!/usr/bin/expect -f
set timeout {timeout}
spawn scp -o StrictHostKeyChecking=no -P {port} root@{host}:{remote} {local}
expect "password:"
send "{password}\r"
expect eof
'''
    with open("/tmp/scp_download.exp", "w") as f:
        f.write(exp_script)
    os.system("chmod +x /tmp/scp_download.exp")
    result = subprocess.run(["expect", "/tmp/scp_download.exp"], capture_output=True, text=True, timeout=timeout+10)
    return result.stdout + result.stderr

# ========== Step 1: 创建实例 ==========
print("=" * 60)
print("Step 1: 创建RTX 4090实例")
print("=" * 60)

body = {
    "req_gpu_amount": 1,
    "expand_system_disk_by_gb": 0,
    "gpu_spec_uuid": "v-48g",
    "image_uuid": "base-image-l2t43iu6uk",
    "cuda_v_from": 113,
    "instance_name": "MorphSim-Demo",
}
data = api_post("/api/v1/dev/instance/pro/create", body)
print(f"创建结果: {data.get('code')}")

if data.get("code") != "Success":
    print(f"❌ 创建失败: {data.get('msg')}")
    sys.exit(1)

instance_uuid = data["data"]
if isinstance(instance_uuid, dict):
    instance_uuid = instance_uuid.get("instance_uuid", instance_uuid)
print(f"实例UUID: {instance_uuid}")

# 等待启动
print("等待实例启动...")
for i in range(60):
    time.sleep(5)
    status_data = api_get(f"/api/v1/dev/instance/pro/status?instance_uuid={instance_uuid}")
    status = status_data.get("data", "")
    print(f"  [{i*5}s] 状态: {status}")
    if status == "running":
        break
    if i == 59:
        print("❌ 启动超时")
        sys.exit(1)

# 获取SSH信息
snap = api_get(f"/api/v1/dev/instance/pro/snapshot?instance_uuid={instance_uuid}").get("data", {})
host = snap.get("proxy_host", "")
port = snap.get("ssh_port", "")
password = snap.get("root_password", "")
print(f"\nSSH: ssh -p {port} root@{host}")
print(f"密码: {password}")

# ========== Step 2: 上传代码 ==========
print("\n" + "=" * 60)
print("Step 2: 打包并上传代码")
print("=" * 60)

# 打包
os.system(f"cd '{LOCAL_CODE}' && tar czf /tmp/morphsim.tar.gz --no-xattrs morphsim/")
print("打包完成")

# 上传
print("上传中...")
output = scp_upload(host, port, password, "/tmp/morphsim.tar.gz", "/root/")
print("上传完成")

# ========== Step 3: 跑10秒demo ==========
print("\n" + "=" * 60)
print("Step 3: 跑10秒GPU Demo")
print("=" * 60)

# 写demo脚本到远程
demo_code = """cat > /root/demo.py << 'DEMO_EOF'
import sys
sys.path.insert(0, '/root')
import time
import numpy as np

print('=== MorphSim 10秒GPU Demo ===')
start = time.time()

# 1. 导入MorphSim
from morphsim.core.engine import MorphSimEngine, SimConfig
from morphsim.core.vehicle import MorphableVehicle, MorphMode
from morphsim.scenarios.loader import ScenarioLoader
print(f'[{time.time()-start:.1f}s] MorphSim导入成功')

# 2. 加载场景
loader = ScenarioLoader()
scenarios = loader.list_scenarios()
print(f'[{time.time()-start:.1f}s] 场景数: {len(scenarios)}')
print(f'  场景: {scenarios}')

# 3. 创建车辆和配置
config = SimConfig(dt=0.01, n_substeps=4)
vehicle = MorphableVehicle()
print(f'[{time.time()-start:.1f}s] 车辆配置完成')

# 4. 运行100步仿真
engine = MorphSimEngine(config)
spec = loader.get('A-01')
print(f'[{time.time()-start:.1f}s] 引擎初始化')
print(f'  场景: {spec.name}')
print(f'  难度: {spec.difficulty}')

# 5. 仿真步进
for i in range(100):
    state = engine.step(np.zeros(12))
    if i % 20 == 0:
        print(f'  Step {i}: pos={state.position}, vel={state.velocity}')

elapsed = time.time() - start
print(f'\\n=== Demo完成! 耗时{elapsed:.1f}s ===')
print(f'仿真100步, dt=0.01, 总模拟时间: 1.0s')
print(f'实际/模拟比: {elapsed:.1f}x realtime')

# 保存结果
import json
result = {
    'scenario': 'A-01',
    'steps': 100,
    'wall_time': elapsed,
    'sim_time': 1.0,
    'final_position': list(state.position),
    'final_velocity': list(state.velocity),
}
with open('/root/demo_result.json', 'w') as f:
    json.dump(result, f, indent=2)
print('结果已保存到 /root/demo_result.json')
DEMO_EOF
"""

# 解压+写demo脚本+运行
remote_cmd = f"cd /root && rm -rf morphsim && tar xzf morphsim.tar.gz && {demo_code} && python3 /root/demo.py 2>&1"
print("远程执行中...")
output = ssh_cmd(host, port, password, remote_cmd, timeout=300)
print("\n远程输出:")
print(output)

# ========== Step 4: 下载结果 ==========
print("\n" + "=" * 60)
print("Step 4: 下载结果")
print("=" * 60)

output = scp_download(host, port, password, "/root/demo_result.json", RESULTS_DIR + "/")
print(f"下载完成: {output}")

# 读取结果
try:
    with open(RESULTS_DIR + "/demo_result.json") as f:
        result = json.load(f)
    print(f"\n结果: {json.dumps(result, indent=2)}")
except:
    print("⚠️ 结果文件未找到")

# ========== Step 5: 关机释放 ==========
print("\n" + "=" * 60)
print("Step 5: 关机释放实例")
print("=" * 60)

# 关机
resp = api_post("/api/v1/dev/instance/pro/power_off", {"instance_uuid": instance_uuid})
print(f"关机: {resp.get('code')}")

time.sleep(3)

# 释放
resp = api_post("/api/v1/dev/instance/pro/release", {"instance_uuid": instance_uuid})
print(f"释放: {resp.get('code')}")

print("\n" + "=" * 60)
print("✅ 全流程完成！")
print("=" * 60)
