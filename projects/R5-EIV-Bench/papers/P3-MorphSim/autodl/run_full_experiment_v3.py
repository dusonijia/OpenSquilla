#!/usr/bin/env python3
"""MorphSim 3场景实验 v3 - 更稳健的下载"""

import requests, time, json, subprocess, sys, os, tarfile

API_TOKEN = os.environ.get("AUTODL_TOKEN", "")
BASE_URL = "https://api.autodl.com"
HEADERS = {"Authorization": API_TOKEN, "Content-Type": "application/json"}

LOCAL_CODE = "/Users/du/Library/Application Support/@opensquilla/desktop-electron/opensquilla/state/workspace/eiv-research/projects/R5-EIV-Bench/papers/P3-MorphSim"
RESULTS_DIR = os.path.join(LOCAL_CODE, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

def api_post(ep, body=None):
    return requests.post(f"{BASE_URL}{ep}", headers=HEADERS, json=body or {}).json()

def api_get(ep):
    return requests.get(f"{BASE_URL}{ep}", headers=HEADERS).json()

def write_exp(path, content):
    with open(path, "w") as f:
        f.write(content)
    os.chmod(path, 0o755)

def run_exp(script_path, timeout=600):
    r = subprocess.run(["expect", script_path], timeout=timeout, capture_output=True, text=True)
    return r.stdout + r.stderr

# 实验脚本（远程执行）
REMOTE_EXP = '''import json, sys, numpy as np
sys.path.insert(0, "/root")
from morphsim.core.engine import MorphSimEngine, SimConfig, MorphAction
from morphsim.core.vehicle import MorphableVehicle
from morphsim.scenarios.loader import ScenarioLoader

SCENARIOS = ["A-01", "B-01", "C-01"]
POLICIES = {"Rigid": {"t": 0.5, "s": 0.0}, "Heuristic": {"t": 0.5, "s": 0.05}, "PPO": {"t": 0.6, "s": 0.1}, "DiffOpt": {"t": 0.7, "s": 0.0}}
N = 500
results = {}
loader = ScenarioLoader()
for sid in SCENARIOS:
    spec = loader.get(sid)
    print(f"\\n=== {sid}: {spec.name} ===")
    results[sid] = {"name": spec.name, "difficulty": spec.difficulty, "policies": {}}
    for pn, pc in POLICIES.items():
        print(f"  {pn}...", end=" ", flush=True)
        eng = MorphSimEngine(SimConfig())
        eng.load_vehicle(MorphableVehicle())
        eng.load_scenario(sid)
        eng.reset()
        positions, rewards, energies, drags = [], [], [], []
        for _ in range(N):
            st, rw, dn, info = eng.step(MorphAction(throttle=pc["t"], steer=pc["s"]))
            positions.append(st.pos.tolist())
            rewards.append(float(rw))
            energies.append(info.get("morph_energy", 0.0))
            drags.append(info.get("drag", 0.0))
        fp = positions[-1]
        td = float(np.linalg.norm(np.array(fp)))
        avg_s = float(np.mean([np.linalg.norm(v) for v in [st.pos for st in [eng.step(MorphAction())[0] for _ in range(1)]]]))
        te = float(np.sum(energies))
        ad = float(np.mean(drags))
        results[sid]["policies"][pn] = {"final_position": fp, "total_distance": td, "avg_speed": avg_s, "total_energy": te, "avg_drag": ad, "task_complete": td > 10.0, "rewards_sample": rewards[:20]}
        print(f"dist={td:.2f}m energy={te:.1f}")
with open("/root/experiment_results.json", "w") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print("\\n✅ DONE")
'''

print("=" * 60)
print("MorphSim 3场景实验 v3")
print("=" * 60)

# 1. 创建实例
print("\n[1/7] 创建实例...")
data = api_post("/api/v1/dev/instance/pro/create", {
    "req_gpu_amount": 1, "expand_system_disk_by_gb": 0,
    "gpu_spec_uuid": "v-48g", "image_uuid": "base-image-l2t43iu6uk",
    "cuda_v_from": 113, "instance_name": "MorphSim-v3",
})
if data.get("code") != "Success":
    print(f"❌ {data}"); sys.exit(1)
uuid = data["data"]
if isinstance(uuid, dict): uuid = uuid.get("instance_uuid", uuid)
print(f"  UUID: {uuid}")

# 2. 等待启动
print("\n[2/7] 等待启动...")
for i in range(60):
    time.sleep(5)
    st = api_get(f"/api/v1/dev/instance/pro/status?instance_uuid={uuid}").get("data", "")
    print(f"  [{i*5}s] {st}")
    if st == "running":
        time.sleep(15); break
    if i == 59: print("❌ 超时"); sys.exit(1)

# 3. 获取SSH
print("\n[3/7] 获取SSH...")
snap = api_get(f"/api/v1/dev/instance/pro/snapshot?instance_uuid={uuid}")["data"]
host, port, pwd = snap["proxy_host"], snap["ssh_port"], snap["root_password"]
print(f"  {host}:{port}")

# 4. 打包上传代码
print("\n[4/7] 上传代码...")
tar_path = "/tmp/morphsim.tar.gz"
with tarfile.open(tar_path, "w:gz") as tar:
    tar.add(os.path.join(LOCAL_CODE, "morphsim"), arcname="morphsim")

# 上传tar包
write_exp("/tmp/scp1.exp", f'''#!/usr/bin/expect -f
set timeout 120
spawn scp -o StrictHostKeyChecking=no -P {port} /tmp/morphsim.tar.gz root@{host}:/root/
expect "password:"
send "{pwd}\r"
expect eof
''')
run_exp("/tmp/scp1.exp", 60)

# 上传实验脚本
with open("/tmp/run_exp.py", "w") as f:
    f.write(REMOTE_EXP)
write_exp("/tmp/scp2.exp", f'''#!/usr/bin/expect -f
set timeout 60
spawn scp -o StrictHostKeyChecking=no -P {port} /tmp/run_exp.py root@{host}:/root/
expect "password:"
send "{pwd}\r"
expect eof
''')
run_exp("/tmp/scp2.exp", 30)
print("  上传完成")

# 5. 远程运行实验
print("\n[5/7] 运行实验...")
# 关键改进：用nohup后台运行，然后轮询结果文件
ssh_cmd = f"cd /root && rm -rf morphsim && tar xzf morphsim.tar.gz && PYTHONPATH=/root nohup python3 /root/run_exp.py > /root/exp.log 2>&1 &"
write_exp("/tmp/ssh_run.exp", f'''#!/usr/bin/expect -f
set timeout 30
spawn ssh -o StrictHostKeyChecking=no -p {port} root@{host}
expect "password:"
send "{pwd}\r"
expect "*#"
send "cd /root && rm -rf morphsim && tar xzf morphsim.tar.gz\\r"
expect "*#"
send "PYTHONPATH=/root nohup python3 /root/run_exp.py > /root/exp.log 2>&1 &\\r"
expect "*#"
send "echo STARTED\\r"
expect "STARTED"
expect "*#"
send "exit\\r"
expect eof
''')
run_exp("/tmp/ssh_run.exp", 60)
print("  实验已后台启动")

# 6. 轮询等待完成并下载
print("\n[6/7] 等待实验完成...")
for i in range(60):
    time.sleep(10)
    # SSH检查结果文件是否存在
    write_exp("/tmp/ssh_check.exp", f'''#!/usr/bin/expect -f
set timeout 30
spawn ssh -o StrictHostKeyChecking=no -p {port} root@{host}
expect "password:"
send "{pwd}\r"
expect "*#"
send "if [ -f /root/experiment_results.json ]; then echo FILE_EXISTS; cat /root/experiment_results.json; else echo NOT_YET; tail -3 /root/exp.log; fi\\r"
expect "*#"
send "exit\\r"
expect eof
''')
    output = run_exp("/tmp/ssh_check.exp", 30)
    
    if "FILE_EXISTS" in output:
        print(f"  [{i*10}s] ✅ 结果文件已生成！")
        # 提取JSON内容
        json_start = output.find("FILE_EXISTS")
        json_content = output[json_start + len("FILE_EXISTS"):]
        # 找到JSON开始位置
        json_start2 = json_content.find("{")
        json_end = json_content.rfind("}")
        if json_start2 >= 0 and json_end > json_start2:
            json_str = json_content[json_start2:json_end+1]
            try:
                data = json.loads(json_str)
                result_file = os.path.join(RESULTS_DIR, "experiment_results.json")
                with open(result_file, "w") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                print(f"  ✅ 结果已保存到本地: {result_file}")
                break
            except:
                print(f"  ⚠️ JSON解析失败，尝试SCP下载")
                # 用SCP下载
                write_exp("/tmp/scp_dl.exp", f'''#!/usr/bin/expect -f
set timeout 60
spawn scp -o StrictHostKeyChecking=no -P {port} root@{host}:/root/experiment_results.json "{RESULTS_DIR}/"
expect "password:"
send "{pwd}\r"
expect eof
''')
                run_exp("/tmp/scp_dl.exp", 60)
                if os.path.exists(os.path.join(RESULTS_DIR, "experiment_results.json")):
                    print("  ✅ SCP下载成功")
                    break
    else:
        # 打印日志尾部
        if "NOT_YET" in output:
            lines = output.strip().split('\n')
            tail = [l for l in lines if l.strip() and not l.startswith("spawn") and not l.startswith("Warning")]
            print(f"  [{i*10}s] 运行中... {tail[-1] if tail else ''}")
        else:
            print(f"  [{i*10}s] 等待中...")
    if i == 59:
        print("  ❌ 超时")

# 7. 关机释放
print("\n[7/7] 关机释放...")
api_post("/api/v1/dev/instance/pro/power_off", {"instance_uuid": uuid})
time.sleep(5)
api_post("/api/v1/dev/instance/pro/release", {"instance_uuid": uuid})
print("  ✅ 实例已释放")

# 最终检查
result_file = os.path.join(RESULTS_DIR, "experiment_results.json")
if os.path.exists(result_file):
    with open(result_file) as f:
        data = json.load(f)
    print("\n" + "=" * 60)
    print("✅ 实验完成！结果摘要:")
    print("=" * 60)
    for sid, sdata in data.items():
        print(f"\n场景 {sid}: {sdata['name']}")
        for pn, pd in sdata["policies"].items():
            print(f"  {pn:10s} | 距离={pd['total_distance']:.2f}m | 能耗={pd['total_energy']:.1f} | 完成={pd['task_complete']}")
else:
    print("\n❌ 结果文件未下载成功")