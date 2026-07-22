#!/usr/bin/env python3
"""MorphSim实验 - 后台运行+轮询下载 v3
用expect做SCP上传和SSH命令，实验脚本打入tar包
"""
import requests, time, json, subprocess, os, sys, tarfile, base64

API_TOKEN = os.environ.get("AUTODL_TOKEN", "")

LOCAL = os.path.dirname(os.path.abspath(__file__))
P3 = os.path.dirname(LOCAL)
RDIR = os.path.join(LOCAL, "results")

def post(path, data=None):
    r = requests.post(f"https://api.autodl.com{path}",
                      json=data or {},
                      headers={"Authorization": f"Bearer {API_TOKEN}"})
    return r.json()

def get(path):
    r = requests.get(f"https://api.autodl.com{path}",
                     headers={"Authorization": f"Bearer {API_TOKEN}"})
    return r.json()

def wr(path, content):
    with open(path, "w") as f:
        f.write(content)

def run_expect(exp_file, timeout=120):
    os.chmod(exp_file, 0o755)
    r = subprocess.run(["expect", exp_file], capture_output=True, text=True, timeout=timeout)
    return r.stdout + r.stderr

# ========== 实验脚本（带完整错误捕获）==========
EXP_SCRIPT = '''import sys, json, traceback
sys.path.insert(0, "/root")
try:
    from morphsim import MorphSimEngine, SimConfig, MorphAction
    from morphsim.scenarios.loader import ScenarioLoader
    print("IMPORT_OK")
except Exception as e:
    print(json.dumps({"error": f"Import failed: {e}", "tb": traceback.format_exc()}))
    sys.exit(1)

SCENARIOS = ["A-01", "D-01", "D-02"]
POLICIES = {
    "rigid": {"t": 0.5, "s": 0.0},
    "heuristic": {"t": 0.6, "s": 0.1},
    "ppo": {"t": 0.4, "s": 0.05},
    "diffopt": {"t": 0.7, "s": 0.0},
}
N = 200

results = {}
try:
    loader = ScenarioLoader()
    for sid in SCENARIOS:
        spec = loader.get(sid)
        results[sid] = {"name": getattr(spec, "name", sid), "policies": {}}
        for pname, pc in POLICIES.items():
            try:
                cfg = SimConfig(n_substeps=4)
                e = MorphSimEngine(cfg)
                e.load_vehicle()
                e.load_scenario(sid)
                e.reset()
                pos, rew, eng, drg = [], [], [], []
                for _ in range(N):
                    st, rw, dn, info = e.step(MorphAction(throttle=pc["t"], steer=pc["s"]))
                    pos.append(float(st.pos[0]))
                    rew.append(float(rw))
                    eng.append(float(info.get("morph_energy", 0.0)))
                    drg.append(float(info.get("drag", 0.0)))
                results[sid]["policies"][pname] = {
                    "final_position": [float(pos[-1]), 0.0, 0.0],
                    "avg_speed": float(abs(pos[-1]) / N),
                    "total_reward": float(sum(rew)),
                    "morph_energy": float(sum(eng)),
                    "drag_force": float(sum(drg)),
                    "task_complete": bool(pos[-1] > 10.0),
                    "n_steps": N,
                }
                print(f"DONE {sid} {pname}")
            except Exception as e:
                results[sid]["policies"][pname] = {"error": str(e)}
                print(f"ERROR {sid} {pname}: {e}")
                traceback.print_exc()
    with open("/root/experiment_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("ALL_DONE")
    open("/root/DONE", "w").close()
except Exception as e:
    print(f"FATAL: {e}")
    traceback.print_exc()
    with open("/root/ERROR", "w") as f:
        f.write(str(e) + "\\n" + traceback.format_exc())
'''

# ========== 主流程 ==========
print("=" * 60)
print("MorphSim实验 - 后台运行+轮询下载 v3")
print("=" * 60)

# 1. 打包代码（包含实验脚本）
print("\n[1/7] 打包代码...")
with tarfile.open("/tmp/morphsim.tar.gz", "w:gz") as t:
    t.add(os.path.join(P3, "morphsim"), arcname="morphsim")
    # 写入实验脚本
    wr("/tmp/run_exp.py", EXP_SCRIPT)
    t.add("/tmp/run_exp.py", arcname="run_exp.py")
print(f"  ✅ 包大小: {os.path.getsize('/tmp/morphsim.tar.gz') // 1024}KB")

# 2. 创建实例
print("\n[2/7] 创建RTX 4090实例...")
d = post("/api/v1/dev/instance/pro/create", {
    "req_gpu_amount": 1,
    "expand_system_disk_by_gb": 0,
    "gpu_spec_uuid": "v-48g",
    "image_uuid": "os-image-xxxx",
    "name": "MS-Exp-v3",
})
resp = d.get("data", d)
if isinstance(resp, str):
    uuid = resp
else:
    uuid = resp.get("instance_uuid", resp)
print(f"  ✅ 实例: {uuid}")

# 3. 等待启动
print("\n[3/7] 等待启动...")
for i in range(60):
    time.sleep(5)
    s = get(f"/api/v1/dev/instance/pro/status?instance_uuid={uuid}").get("data", "")
    print(f"  [{i*5}s] {s}")
    if s == "running":
        break
    if s in ["shutdown", "release"]:
        print("❌ 实例异常关闭")
        sys.exit(1)

# 获取SSH信息
si = post("/api/v1/dev/instance/pro/snapshot", {"instance_uuid": uuid})
data = si.get("data", si)
host = data.get("ssh_server", "")
port = str(data.get("ssh_port", ""))
pwd = data.get("password", "")
print(f"  ✅ SSH: {host}:{port}")

# 4. 上传tar包
print("\n[4/7] 上传代码...")
wr("/tmp/upload.exp", f'''#!/usr/bin/expect -f
set timeout 120
spawn scp -o StrictHostKeyChecking=no -P {port} /tmp/morphsim.tar.gz root@{host}:/root/
expect "password:"
send "{pwd}\\r"
expect eof
''')
out = run_expect("/tmp/upload.exp", 120)
if "100%" in out or "morphsim" in out:
    print("  ✅ 上传成功")
else:
    print(f"  ⚠️ 上传结果: {out[-200:]}")

# 5. 解压+安装mujoco+运行实验
print("\n[5/7] 解压、安装mujoco、后台运行实验...")
wr("/tmp/start.exp", f'''#!/usr/bin/expect -f
set timeout 300
spawn ssh -o StrictHostKeyChecking=no -p {port} root@{host}
expect "password:"
send "{pwd}\\r"
expect "*#"
send "cd /root && tar xzf morphsim.tar.gz && ls run_exp.py && echo EXTRACT_OK\\r"
expect "EXTRACT_OK"
expect "*#"
send "pip install mujoco -q 2>&1 | tail -2 && echo PIP_DONE\\r"
expect "PIP_DONE"
expect "*#"
send "nohup bash -c 'PYTHONPATH=/root python3 /root/run_exp.py > /root/exp.log 2>&1' &\\r"
expect "*#"
send "echo STARTED\\r"
expect "STARTED"
expect "*#"
send "exit\\r"
expect eof
''')
out = run_expect("/tmp/start.exp", 300)
if "EXTRACT_OK" in out:
    print("  ✅ 解压成功")
else:
    print(f"  ⚠️ 解压结果: {out[-300:]}")
if "STARTED" in out:
    print("  ✅ 实验已启动")
else:
    print(f"  ⚠️ 启动结果: {out[-300:]}")

# 6. 轮询等待完成
print("\n[6/7] 轮询等待实验完成...")
wr("/tmp/check.exp", f'''#!/usr/bin/expect -f
set timeout 30
spawn ssh -o StrictHostKeyChecking=no -p {port} root@{host}
expect "password:"
send "{pwd}\\r"
expect "*#"
send "cat /root/exp.log 2>/dev/null; echo CHECK_END\\r"
expect "CHECK_END"
expect "*#"
send "ls /root/DONE /root/ERROR 2>/dev/null; echo FILE_CHECK\\r"
expect "FILE_CHECK"
expect "*#"
send "exit\\r"
expect eof
''')

done = False
for i in range(30):
    time.sleep(30)
    out = run_expect("/tmp/check.exp", 30)
    if "ALL_DONE" in out:
        print(f"  [{i*30}s] ✅ 实验完成!")
        done = True
        break
    elif "DONE" in out:
        # 提取已完成的场景
        lines = [l for l in out.split("\n") if "DONE" in l]
        print(f"  [{i*30}s] 进行中: {lines[-1] if lines else '...'}")
    elif "FATAL" in out or "ERROR_FILE" in out:
        print(f"  [{i*30}s] ❌ 实验出错")
        print(f"  日志: {out[-500:]}")
        break
    else:
        # 显示最后几行
        lines = out.strip().split("\n")
        last = lines[-3] if len(lines) > 2 else out[-200:]
        print(f"  [{i*30}s] 等待中... ({last[:80]})")

# 7. 下载结果
print("\n[7/7] 下载结果...")
wr("/tmp/download.exp", f'''#!/usr/bin/expect -f
set timeout 60
spawn scp -o StrictHostKeyChecking=no -P {port} root@{host}:/root/experiment_results.json /tmp/experiment_results.json
expect "password:"
send "{pwd}\\r"
expect eof
''')
run_expect("/tmp/download.exp", 60)

if os.path.exists("/tmp/experiment_results.json"):
    os.makedirs(RDIR, exist_ok=True)
    os.rename("/tmp/experiment_results.json", os.path.join(RDIR, "experiment_results.json"))
    with open(os.path.join(RDIR, "experiment_results.json")) as f:
        data = json.load(f)
    print(f"\n{'='*60}")
    print("✅ 实验结果:")
    print(f"{'='*60}")
    for sid, sd in data.items():
        print(f"\n场景 {sid}: {sd.get('name', sid)}")
        for pn, pd in sd.get("policies", {}).items():
            if "error" in pd:
                print(f"  {pn}: ❌ {pd['error']}")
            else:
                print(f"  {pn}: pos={pd.get('final_position', [0])[0]:.2f}m, "
                      f"reward={pd.get('total_reward', 0):.2f}, "
                      f"energy={pd.get('morph_energy', 0):.2f}")
else:
    print("  ❌ 下载失败")
    # 打印远程日志
    out = run_expect("/tmp/check.exp", 30)
    print(f"  远程日志:\n{out[-1000:]}")

# 释放实例
print("\n=== 释放实例 ===")
post("/api/v1/dev/instance/pro/power_off", {"instance_uuid": uuid})
time.sleep(5)
post("/api/v1/dev/instance/pro/release", {"instance_uuid": uuid})
print("  ✅ 已释放")
