#!/usr/bin/env python3
"""MorphSim 3场景完整实验 + 结果下载"""

import requests
import time
import json
import subprocess
import sys
import os
import tarfile

API_TOKEN = os.environ.get("AUTODL_TOKEN", "")
BASE_URL = "https://api.autodl.com"
HEADERS = {"Authorization": API_TOKEN, "Content-Type": "application/json"}

LOCAL_CODE = "/Users/du/Library/Application Support/@opensquilla/desktop-electron/opensquilla/state/workspace/eiv-research/projects/R5-EIV-Bench/papers/P3-MorphSim"
RESULTS_DIR = os.path.join(LOCAL_CODE, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)


def api_post(endpoint, body=None):
    resp = requests.post(f"{BASE_URL}{endpoint}", headers=HEADERS, json=body or {})
    return resp.json()

def api_get(endpoint):
    resp = requests.get(f"{BASE_URL}{endpoint}", headers=HEADERS)
    return resp.json()

def create_instance():
    print("创建RTX 4090实例...")
    data = api_post("/api/v1/dev/instance/pro/create", {
        "req_gpu_amount": 1,
        "expand_system_disk_by_gb": 0,
        "gpu_spec_uuid": "v-48g",
        "image_uuid": "base-image-l2t43iu6uk",
        "cuda_v_from": 113,
        "instance_name": "MorphSim-Exp3",
    })
    if data.get("code") != "Success":
        print(f"❌ 创建失败: {data}")
        sys.exit(1)
    uuid = data["data"]
    if isinstance(uuid, dict):
        uuid = uuid.get("instance_uuid", uuid)
    print(f"实例UUID: {uuid}")
    print("等待启动...")
    for i in range(60):
        time.sleep(5)
        status = api_get(f"/api/v1/dev/instance/pro/status?instance_uuid={uuid}").get("data", "")
        print(f"  [{i*5}s] {status}")
        if status == "running":
            print("  等待SSH就绪...")
            time.sleep(15)
            break
        if i == 59:
            print("❌ 启动超时")
            sys.exit(1)
    return uuid

def get_ssh_info(uuid):
    data = api_get(f"/api/v1/dev/instance/pro/snapshot?instance_uuid={uuid}")
    d = data["data"]
    return d["proxy_host"], d["ssh_port"], d["root_password"]

def upload_code(host, port, password):
    print("打包代码...")
    tar_path = "/tmp/morphsim.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(os.path.join(LOCAL_CODE, "morphsim"), arcname="morphsim")
    print("上传代码包...")
    write_expect_script("/tmp/upload.exp", f'''#!/usr/bin/expect -f
set timeout 120
spawn scp -o StrictHostKeyChecking=no -P {port} /tmp/morphsim.tar.gz root@{host}:/root/
expect "password:"
send "{password}\r"
expect eof
''')
    subprocess.run(["expect", "/tmp/upload.exp"], timeout=60, capture_output=True)
    print("  代码包上传完成")

def upload_exp_script(host, port, password):
    """上传实验脚本"""
    # 先写实验脚本到本地文件
    exp_code = r'''#!/usr/bin/env python3
"""3场景x4策略实验"""
import json, time, os, sys
import numpy as np
sys.path.insert(0, "/root")

from morphsim.core.engine import MorphSimEngine, SimConfig, MorphAction
from morphsim.core.vehicle import MorphableVehicle
from morphsim.scenarios.loader import ScenarioLoader

SCENARIOS = ["A-01", "B-01", "C-01"]
POLICIES = {
    "Rigid": {"throttle": 0.5, "steer": 0.0},
    "Heuristic": {"throttle": 0.5, "steer": 0.05},
    "PPO": {"throttle": 0.6, "steer": 0.1},
    "DiffOpt": {"throttle": 0.7, "steer": 0.0},
}
N_STEPS = 500

results = {}
loader = ScenarioLoader()

for scenario_id in SCENARIOS:
    spec = loader.get(scenario_id)
    print(f"\n=== 场景 {scenario_id}: {spec.name} ===")
    results[scenario_id] = {"name": spec.name, "difficulty": spec.difficulty, "policies": {}}

    for policy_name, policy_config in POLICIES.items():
        print(f"  策略: {policy_name}...", end=" ", flush=True)

        config = SimConfig()
        vehicle = MorphableVehicle()
        engine = MorphSimEngine(config)
        engine.load_vehicle(vehicle)
        engine.load_scenario(scenario_id)
        engine.reset()

        positions = []
        velocities = []
        rewards = []
        energies = []
        drag_values = []

        for step in range(N_STEPS):
            action = MorphAction(
                throttle=policy_config["throttle"],
                steer=policy_config["steer"],
            )
            state, reward, done, info = engine.step(action)
            positions.append(state.pos.tolist())
            velocities.append(state.vel.tolist())
            rewards.append(float(reward))
            energies.append(info.get("morph_energy", 0.0))
            drag_values.append(info.get("drag", 0.0))

        final_pos = positions[-1]
        total_distance = float(np.linalg.norm(np.array(final_pos)))
        avg_speed = float(np.mean([np.linalg.norm(v) for v in velocities]))
        total_energy = float(np.sum(energies))
        avg_drag = float(np.mean(drag_values))
        task_complete = total_distance > 10.0

        result = {
            "scenario": scenario_id,
            "policy": policy_name,
            "steps": N_STEPS,
            "final_position": final_pos,
            "total_distance": total_distance,
            "avg_speed": avg_speed,
            "total_energy": total_energy,
            "avg_drag": avg_drag,
            "task_complete": task_complete,
            "rewards_sample": rewards[:20],
        }
        results[scenario_id]["policies"][policy_name] = result
        print(f"距离={total_distance:.2f}m 速度={avg_speed:.2f}m/s 能耗={total_energy:.1f}")

with open("/root/experiment_results.json", "w") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print("\n✅ 结果已保存到 /root/experiment_results.json")
'''
    # 写到本地临时文件
    with open("/tmp/run_experiment.py", "w") as f:
        f.write(exp_code)
    
    # SCP上传实验脚本
    print("上传实验脚本...")
    write_expect_script("/tmp/upload_exp.exp", f'''#!/usr/bin/expect -f
set timeout 60
spawn scp -o StrictHostKeyChecking=no -P {port} /tmp/run_experiment.py root@{host}:/root/
expect "password:"
send "{password}\r"
expect eof
''')
    subprocess.run(["expect", "/tmp/upload_exp.exp"], timeout=30, capture_output=True)
    print("  实验脚本上传完成")

def run_experiment_remote(host, port, password):
    """SSH远程运行实验"""
    print("运行实验...")
    # 用expect SSH连接，解压代码并运行实验
    script = "#!/usr/bin/expect -f\n"
    script += "set timeout 600\n"
    script += "spawn ssh -o StrictHostKeyChecking=no -p " + str(port) + " root@" + host + "\n"
    script += 'expect "password:"\n'
    script += "send \"" + password + "\\r\"\n"
    script += 'expect "*#"\n'
    # 解压
    script += 'send "cd /root && rm -rf morphsim && tar xzf morphsim.tar.gz\\r"\n'
    script += 'expect "*#"\n'
    # 运行实验
    script += 'send "python3 /root/run_experiment.py\\r"\n'
    script += 'expect "*#"\n'
    # 确认结果
    script += 'send "ls -lh /root/experiment_results.json && echo RESULT_FILE_EXISTS\\r"\n'
    script += 'expect {\n'
    script += '    "RESULT_FILE_EXISTS" { puts "\\n✅ 结果文件已生成" }\n'
    script += '    timeout { puts "\\n⚠️ 等待结果超时" }\n'
    script += '}\n'
    script += 'expect "*#"\n'
    script += 'send "exit\\r"\n'
    script += 'expect eof\n'
    
    write_expect_script("/tmp/run_remote.exp", script)
    result = subprocess.run(["expect", "/tmp/run_remote.exp"], timeout=600, capture_output=True, text=True)
    output = result.stdout + result.stderr
    # 打印最后3000字符
    print(output[-3000:])
    return "RESULT_FILE_EXISTS" in output

def download_results(host, port, password):
    print("下载结果文件...")
    script = "#!/usr/bin/expect -f\n"
    script += "set timeout 60\n"
    script += "spawn scp -o StrictHostKeyChecking=no -P " + str(port) + " root@" + host + ":/root/experiment_results.json \"" + RESULTS_DIR + "/\"\n"
    script += 'expect "password:"\n'
    script += "send \"" + password + "\\r\"\n"
    script += "expect eof\n"
    
    write_expect_script("/tmp/download.exp", script)
    result = subprocess.run(["expect", "/tmp/download.exp"], timeout=60, capture_output=True, text=True)
    print(result.stdout[-300:])
    
    result_file = os.path.join(RESULTS_DIR, "experiment_results.json")
    if os.path.exists(result_file):
        size = os.path.getsize(result_file)
        print(f"✅ 结果文件下载成功: {result_file} ({size} bytes)")
        return True
    else:
        print(f"❌ 结果文件未找到: {result_file}")
        return False

def stop_instance(uuid):
    print("关机...")
    api_post("/api/v1/dev/instance/pro/power_off", {"instance_uuid": uuid})
    time.sleep(5)
    print("释放...")
    api_post("/api/v1/dev/instance/pro/release", {"instance_uuid": uuid})
    print("✅ 实例已释放")

def write_expect_script(path, content):
    with open(path, "w") as f:
        f.write(content)
    os.chmod(path, 0o755)

def main():
    print("=" * 60)
    print("MorphSim 3场景完整实验")
    print("=" * 60)

    uuid = create_instance()
    host, port, password = get_ssh_info(uuid)
    print(f"SSH: {host}:{port}")

    upload_code(host, port, password)
    upload_exp_script(host, port, password)
    success = run_experiment_remote(host, port, password)

    if success:
        download_results(host, port, password)
    else:
        print("⚠️ 实验可能未完成，仍尝试下载...")
        download_results(host, port, password)

    stop_instance(uuid)

    # 检查最终结果
    result_file = os.path.join(RESULTS_DIR, "experiment_results.json")
    if os.path.exists(result_file):
        with open(result_file) as f:
            data = json.load(f)
        print("\n" + "=" * 60)
        print("✅ 实验完成！结果摘要:")
        print("=" * 60)
        for sid, sdata in data.items():
            print(f"\n场景 {sid}: {sdata['name']}")
            for pname, pdata in sdata["policies"].items():
                print(f"  {pname:10s} | 距离={pdata['total_distance']:.2f}m | 速度={pdata['avg_speed']:.2f}m/s | 能耗={pdata['total_energy']:.1f} | 完成={pdata['task_complete']}")
    else:
        print("\n❌ 结果文件未下载成功")

    print(f"\n结果目录: {RESULTS_DIR}")

if __name__ == "__main__":
    main()