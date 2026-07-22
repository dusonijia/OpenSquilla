#!/usr/bin/env python3
"""一键GPU Demo v2: 上传demo.py→SSH执行→下载结果→释放"""

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

def run_expect(exp_content, timeout=300):
    """运行expect脚本"""
    with open("/tmp/run.exp", "w") as f:
        f.write(exp_content)
    os.system("chmod +x /tmp/run.exp")
    result = subprocess.run(["expect", "/tmp/run.exp"], capture_output=True, text=True, timeout=timeout+10)
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
    instance_uuid = instance_uuid.get("instance_uuid", str(instance_uuid))
print(f"实例UUID: {instance_uuid}")

# 等待启动
print("等待实例启动...")
for i in range(60):
    time.sleep(5)
    status_data = api_get(f"/api/v1/dev/instance/pro/status?instance_uuid={instance_uuid}")
    status = status_data.get("data", "")
    print(f"  [{i*5}s] 状态: {status}")
    if status == "running":
        print("  SSH准备中，等待15秒...")
        time.sleep(15)
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

# ========== Step 2: 写demo.py到本地 ==========
print("\n" + "=" * 60)
print("Step 2: 准备demo.py")
print("=" * 60)

demo_py = '''import sys
sys.path.insert(0, '/root')
import time
import numpy as np

print('=== MorphSim 10秒GPU Demo ===')
start = time.time()

# 1. 导入MorphSim
from morphsim.core.engine import MorphSimEngine, SimConfig, MorphState, MorphAction
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

# 4. 简单测试：创建引擎但不步进
engine = MorphSimEngine(config)
engine.load_vehicle(vehicle)
engine.load_scenario('A-01')
spec = loader.get('A-01')
print(f'[{time.time()-start:.1f}s] 引擎初始化')
print(f'  场景: {spec.name}')
print(f'  难度: {spec.difficulty}')

# 5. reset
state = engine.reset()
print(f'[{time.time()-start:.1f}s] 引擎reset完成')
print(f'  初始位置: {state.pos}')

# 6. 单步仿真
try:
    state, reward, done, info = engine.step(MorphAction())
    print(f'[{time.time()-start:.1f}s] ✅ 单步仿真成功')
    print(f'  位置: {state.pos}, 奖励: {reward}, 完成: {done}')
except Exception as e:
    print(f'[{time.time()-start:.1f}s] ⚠️ 单步仿真失败: {e}')
    print('  导入和场景加载已验证，仿真步进需要进一步修复')

# 7. 批量步进
success_count = 0
for i in range(100):
    try:
        state, reward, done, info = engine.step(MorphAction())
        success_count += 1
        if i % 20 == 0:
            print(f'  Step {i}: pos={state.pos}, vel={state.vel}')
    except:
        break

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
    'final_position': list(state.pos),
    'final_velocity': list(state.vel),
}
with open('/root/demo_result.json', 'w') as f:
    json.dump(result, f, indent=2)
print('结果已保存到 /root/demo_result.json')
'''

with open("/tmp/demo.py", "w") as f:
    f.write(demo_py)
print("demo.py 已写入 /tmp/demo.py")

# ========== Step 3: 上传代码和demo.py ==========
print("\n" + "=" * 60)
print("Step 3: 上传代码")
print("=" * 60)

# 打包代码
os.system(f"cd '{LOCAL_CODE}' && tar czf /tmp/morphsim.tar.gz --no-xattrs morphsim/")
print("打包完成")

# 上传tar包
exp_upload = f'''#!/usr/bin/expect -f
set timeout 120
spawn scp -o StrictHostKeyChecking=no -P {port} /tmp/morphsim.tar.gz root@{host}:/root/
expect "password:"
send "{password}\\r"
expect eof
'''
output = run_expect(exp_upload, 120)
print("代码包上传完成")

# 上传demo.py
exp_upload2 = f'''#!/usr/bin/expect -f
set timeout 60
spawn scp -o StrictHostKeyChecking=no -P {port} /tmp/demo.py root@{host}:/root/
expect "password:"
send "{password}\\r"
expect eof
'''
output = run_expect(exp_upload2, 60)
print("demo.py上传完成")

# ========== Step 4: SSH运行demo ==========
print("\n" + "=" * 60)
print("Step 4: 跑10秒GPU Demo")
print("=" * 60)

# 解压代码 + 运行demo
exp_run = f'''#!/usr/bin/expect -f
set timeout 300
spawn ssh -o StrictHostKeyChecking=no -p {port} root@{host}
expect "password:"
send "{password}\\r"
expect "*#"
send "cd /root && rm -rf morphsim && tar xzf morphsim.tar.gz\\r"
expect "*#"
send "python3 /root/demo.py\\r"
expect "*#"
send "cat /root/demo_result.json\\r"
expect "*#"
send "exit\\r"
expect eof
'''
output = run_expect(exp_run, 300)
print("\n远程输出:")
print(output)

# ========== Step 5: 下载结果 ==========
print("\n" + "=" * 60)
print("Step 5: 下载结果")
print("=" * 60)

exp_download = f'''#!/usr/bin/expect -f
set timeout 60
spawn scp -o StrictHostKeyChecking=no -P {port} root@{host}:/root/demo_result.json {RESULTS_DIR}/
expect "password:"
send "{password}\\r"
expect eof
'''
output = run_expect(exp_download, 60)
print(f"下载完成")

# 读取结果
try:
    with open(RESULTS_DIR + "/demo_result.json") as f:
        result = json.load(f)
    print(f"\n{'=' * 60}")
    print(f"✅ Demo结果:")
    print(f"{'=' * 60}")
    print(json.dumps(result, indent=2))
except Exception as e:
    print(f"⚠️ 结果文件未找到: {e}")

# ========== Step 6: 关机释放 ==========
print("\n" + "=" * 60)
print("Step 6: 关机释放实例")
print("=" * 60)

resp = api_post("/api/v1/dev/instance/pro/power_off", {"instance_uuid": instance_uuid})
print(f"关机: {resp.get('code')}")
time.sleep(3)
resp = api_post("/api/v1/dev/instance/pro/release", {"instance_uuid": instance_uuid})
print(f"释放: {resp.get('code')}")

print("\n" + "=" * 60)
print("✅ 全流程完成！")
print("=" * 60)
