#!/usr/bin/env python3
"""AutoDL实验 - 完整流程：创建→SSH→Git clone→运行→下载"""

import requests, time, json, subprocess, os, sys, signal, atexit

# AutoDL配置
API_TOKEN = os.environ.get("AUTODL_TOKEN", "")
BASE = "https://api.autodl.com"
H = {"Authorization": f"Bearer {API_TOKEN}", "Content-Type": "application/json"}

# GitHub配置（用HTTPS避免SSH key问题）
GITHUB_REPO = "https://github.com/dusonijia/OpenSquilla.git"
GITHUB_TOKEN = os.environ.get("GH_TOKEN", "")

# 实例配置
GPU_UUID = "v-48g"  # RTX 4090
IMAGE_UUID = "os-image-3s56y2v5zq3"  # PyTorch 2.3镜像

instance_uuid = None

def post(path, data=None):
    return requests.post(f"{BASE}{path}", headers=H, json=data or {}).json()

def get(path):
    return requests.get(f"{BASE}{path}", headers=H).json()

def cleanup(signum=None, frame=None):
    """确保实例被释放"""
    global instance_uuid
    if instance_uuid:
        print("\n[清理] 释放实例...")
        post(f"/api/v1/dev/instance/pro/power_off", {"instance_uuid": instance_uuid})
        time.sleep(3)
        post(f"/api/v1/dev/instance/pro/release", {"instance_uuid": instance_uuid})
        print("  ✅ 已释放")

atexit.register(cleanup)
signal.signal(signal.SIGTERM, cleanup)
signal.signal(signal.SIGINT, cleanup)

def run_ssh_cmd(host, port, user, password, cmd, timeout=120):
    """直接用expect执行SSH命令"""
    exp_script = f'''#!/usr/bin/expect -f
set timeout {timeout}
spawn ssh -o StrictHostKeyChecking=no -p {port} {user}@{host}
expect "password:"; send "{password}\\r"
expect "*#"
send "{cmd}\\r"
expect "*#"
send "exit\\r"
expect eof
'''
    exp_file = "/tmp/ssh_cmd.exp"
    with open(exp_file, "w") as f:
        f.write(exp_script)
    os.chmod(exp_file, 0o755)
    
    result = subprocess.run(
        ["expect", exp_file],
        capture_output=True,
        text=True,
        timeout=timeout + 30
    )
    return result.stdout + result.stderr

# ========== 主流程 ==========
print("=" * 60)
print("MorphSim GPU实验 - 自动完整流程")
print("=" * 60)

# 1. 创建实例
print("\n[1/8] 创建RTX 4090实例...")
resp = post("/api/v1/dev/instance/pro/create", {
    "req_gpu_amount": 1,
    "expand_system_disk_by_gb": 0,
    "gpu_spec_uuid": GPU_UUID,
    "image_uuid": IMAGE_UUID,
})
if resp.get("code") != "Success":
    print(f"❌ 创建失败: {resp}")
    sys.exit(1)
instance_uuid = resp["data"].get("instance_uuid", resp["data"])
print(f"  ✅ UUID: {instance_uuid}")

# 2. 等待启动
print("\n[2/8] 等待实例启动...")
for i in range(60):
    time.sleep(5)
    status = get(f"/api/v1/dev/instance/pro/status?instance_uuid={instance_uuid}").get("data", "")
    print(f"  [{i*5}s] {status}")
    if status == "running":
        time.sleep(10)
        break
    if i == 59:
        print("❌ 启动超时")
        sys.exit(1)

# 3. 获取SSH信息
print("\n[3/8] 获取SSH信息...")
snap = get(f"/api/v1/dev/instance/pro/snapshot?instance_uuid={instance_uuid}")
if snap.get("code") != "Success":
    print(f"❌ 获取SSH信息失败: {snap}")
    sys.exit(1)
snap_data = snap.get("data", {})
host = snap_data.get("proxy_host", "")
port = snap_data.get("ssh_port", "")
password = snap_data.get("root_password", "")
print(f"  ✅ {host}:{port}")

# 4. 测试SSH连接
print("\n[4/8] 测试SSH连接...")
output = run_ssh_cmd(host, port, "root", password, "echo 'SSH_OK' && pwd")
if "SSH_OK" not in output:
    print(f"❌ SSH连接失败: {output[-500:]}")
    sys.exit(1)
print("  ✅ SSH连接成功")

# 5. 从GitHub clone代码
print("\n[5/8] 从GitHub clone代码...")
git_clone_cmd = f'cd /root && git clone https://{GITHUB_TOKEN}@github.com/dusonijia/OpenSquilla.git && echo "GIT_CLONE_OK"'
output = run_ssh_cmd(host, port, "root", password, git_clone_cmd, timeout=300)
if "GIT_CLONE_OK" not in output:
    print(f"❌ Git clone失败: {output[-1000:]}")
    sys.exit(1)
print("  ✅ 代码clone成功")

# 6. 安装mujoco并运行实验
print("\n[6/8] 安装mujoco并运行实验...")
run_cmd = f'''cd /root/OpenSquilla/projects/R5-EIV-Bench/papers/P3-MorphSim && \\
pip install mujoco -q && \\
PYTHONPATH=/root/OpenSquilla python3 -c "
import sys,json
sys.path.insert(0,'/root/OpenSquilla/projects/R5-EIV-Bench/papers/P3-MorphSim')
try:
    from morphsim import MorphSimEngine, SimConfig, MorphAction
    from morphsim.scenarios.loader import ScenarioLoader
    print('IMPORT_OK')
    
    config = SimConfig(dt=0.01, n_substeps=4)
    engine = MorphSimEngine(config)
    from morphsim import MorphableVehicle, MorphMode
    vehicle = MorphableVehicle(mode=MorphMode.STANDARD, wheelbase=2.8, track_width=1.6, mass=1500.0)
    engine.load_vehicle(vehicle)
    loader = ScenarioLoader()
    spec = loader.get('A-01')
    engine.load_scenario('A-01')
    engine.reset()
    
    pos = []
    for i in range(50):
        st,rw,dn,info = engine.step(MorphAction(throttle=0.6,steer=0.0))
        pos.append(float(st.pos[0]))
        if i%10==0: print(f'step {i}: pos={st.pos[0]:.3f}')
    
    result = {{'final_position': pos[-1], 'distance': sum(abs(pos[i]-pos[i-1]) for i in range(1,len(pos)))}}
    print('EXPERIMENT_OK')
    print(json.dumps(result))
except Exception as e:
    import traceback
    print(f'ERROR: {{e}}')
    print(traceback.format_exc())
    sys.exit(1)
"'''
output = run_ssh_cmd(host, port, "root", password, run_cmd, timeout=600)
print(f"  输出: {output[-500:]}")

# 7. 下载结果文件到本地
print("\n[7/8] 下载结果文件...")
results_dir = "/Users/du/Library/Application Support/@opensquilla/desktop-electron/opensquilla/state/workspace/eiv-research/projects/R5-EIV-Bench/papers/P3-MorphSim/results"
os.makedirs(results_dir, exist_ok=True)
output_file = os.path.join(results_dir, "auto_gpu_results.json")

with open(output_file, "w") as f:
    f.write(output)
print(f"  ✅ 结果保存到: {output_file}")

# 8. 解析并显示结果
print("\n[8/8] 实验结果:")
if "EXPERIMENT_OK" in output:
    try:
        start = output.find("{")
        end = output.rfind("}") + 1
        if start != -1 and end != -1:
            result_json = json.loads(output[start:end])
            print(f"  最终位置: {result_json.get('final_position', 0):.3f}m")
            print(f"  总距离: {result_json.get('distance', 0):.3f}m")
            print("  ✅ 实验成功！")
        else:
            print("  ⚠️  结果解析失败")
    except Exception as e:
        print(f"  ⚠️  JSON解析失败: {e}")
elif "ERROR:" in output:
    err_start = output.find("ERROR:")
    print(f"  ❌ 实验失败: {output[err_start:err_start+200]}")
else:
    print("  ❌ 未知错误")

# 自动释放
cleanup()
print("\n" + "=" * 60)
print("流程完成")
print("=" * 60)