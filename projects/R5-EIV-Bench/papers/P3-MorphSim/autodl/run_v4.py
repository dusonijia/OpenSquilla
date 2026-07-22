#!/usr/bin/env python3
"""MorphSim 3场景实验 v4 - 直接SSH前台运行"""

import requests, time, json, subprocess, os, sys, tarfile

API_TOKEN = os.environ.get("AUTODL_TOKEN", "")
BASE = "https://api.autodl.com"
H = {"Authorization": API_TOKEN, "Content-Type": "application/json"}
LOCAL = "/Users/du/Library/Application Support/@opensquilla/desktop-electron/opensquilla/state/workspace/eiv-research/projects/R5-EIV-Bench/papers/P3-MorphSim"
RDIR = os.path.join(LOCAL, "results")
os.makedirs(RDIR, exist_ok=True)

def post(ep, body=None):
    return requests.post(f"{BASE}{ep}", headers=H, json=body or {}).json()
def get(ep):
    return requests.get(f"{BASE}{ep}", headers=H).json()
def wr(path, content):
    with open(path, "w") as f: f.write(content)
    os.chmod(path, 0o755)
def run_expect(path, t=300):
    r = subprocess.run(["expect", path], timeout=t, capture_output=True, text=True)
    return r.stdout + r.stderr

# 实验脚本 - 简化版，直接输出JSON到stdout
EXP = '''import json,sys,numpy as np
sys.path.insert(0,"/root")
from morphsim.core.engine import MorphSimEngine,SimConfig,MorphAction
from morphsim.core.vehicle import MorphableVehicle
from morphsim.scenarios.loader import ScenarioLoader
SC=["A-01","B-01","C-01"]
PO={"Rigid":{"t":0.5,"s":0.0},"Heuristic":{"t":0.5,"s":0.05},"PPO":{"t":0.6,"s":0.1},"DiffOpt":{"t":0.7,"s":0.0}}
N=200
R={}
L=ScenarioLoader()
for si in SC:
 sp=L.get(si)
 print(f"SCN {si}: {sp.name}")
 R[si]={"name":sp.name,"difficulty":sp.difficulty,"policies":{}}
 for pn,pc in PO.items():
  e=MorphSimEngine(SimConfig())
  e.load_vehicle(MorphableVehicle())
  e.load_scenario(si)
  e.reset()
  pos=[];rew=[];eng=[];drg=[]
  for _ in range(N):
   st,rw,dn,info=e.step(MorphAction(throttle=pc["t"],steer=pc["s"]))
   pos.append(st.pos.tolist());rew.append(float(rw));eng.append(info.get("morph_energy",0.0));drg.append(info.get("drag",0.0))
  fp=pos[-1]
  td=float(np.linalg.norm(np.array(fp)))
  te=float(np.sum(eng))
  ad=float(np.mean(drg))
  R[si]["policies"][pn]={"final_position":fp,"total_distance":td,"total_energy":te,"avg_drag":ad,"task_complete":td>5.0,"rewards_sample":rew[:10]}
  print(f"  {pn}: dist={td:.2f}m E={te:.1f}")
with open("/root/results.json","w") as f: json.dump(R,f,indent=2)
print("JSONSTART"+json.dumps(R)+"JSONEND")
'''

print("="*60)
print("MorphSim 3场景实验 v4")
print("="*60)

# 创建实例
print("\n[1/6] 创建实例...")
d=post("/api/v1/dev/instance/pro/create",{"req_gpu_amount":1,"expand_system_disk_by_gb":0,"gpu_spec_uuid":"v-48g","image_uuid":"base-image-l2t43iu6uk","cuda_v_from":113,"instance_name":"MS-v4"})
if d.get("code")!="Success": print(f"FAIL:{d}"); sys.exit(1)
uuid=d["data"]
if isinstance(uuid,dict): uuid=uuid.get("instance_uuid",uuid)
print(f"  UUID: {uuid}")

# 等待
print("\n[2/6] 等待启动...")
for i in range(60):
 time.sleep(5)
 s=get(f"/api/v1/dev/instance/pro/status?instance_uuid={uuid}").get("data","")
 print(f"  [{i*5}s] {s}")
 if s=="running": time.sleep(15); break
 if i==59: print("TIMEOUT"); sys.exit(1)

# SSH信息
snap=get(f"/api/v1/dev/instance/pro/snapshot?instance_uuid={uuid}")["data"]
host,port,pwd=snap["proxy_host"],snap["ssh_port"],snap["root_password"]
print(f"\n  SSH: {host}:{port}")

# 打包上传
print("\n[3/6] 上传代码...")
with tarfile.open("/tmp/morphsim.tar.gz","w:gz") as t: t.add(os.path.join(LOCAL,"morphsim"),arcname="morphsim")
with open("/tmp/run_exp.py","w") as f: f.write(EXP)
wr("/tmp/up.exp",f'''#!/usr/bin/expect -f
set timeout 120
spawn scp -o StrictHostKeyChecking=no -P {port} /tmp/morphsim.tar.gz root@{host}:/root/
expect "password:"; send "{pwd}\r"; expect eof
spawn scp -o StrictHostKeyChecking=no -P {port} /tmp/run_exp.py root@{host}:/root/
expect "password:"; send "{pwd}\r"; expect eof
''')
run_expect("/tmp/up.exp",60)
print("  完成")

# 运行实验（前台，直接捕获输出）
print("\n[4/6] 运行实验（前台）...")
wr("/tmp/run.exp",f'''#!/usr/bin/expect -f
set timeout 600
spawn ssh -o StrictHostKeyChecking=no -p {port} root@{host}
expect "password:"; send "{pwd}\r"
expect "*#"
send "cd /root && rm -rf morphsim && tar xzf morphsim.tar.gz\r"
expect "*#"
send "pip install mujoco -q 2>&1 | tail -3\r"
expect "*#"
send "PYTHONPATH=/root python3 /root/run_exp.py\r"
expect "*#"
send "exit\r"
expect eof
''')
out = run_expect("/tmp/run.exp",600)
# 保存完整输出到文件
with open(os.path.join(RDIR,"full_log.txt"),"w") as f: f.write(out)
print("  实验输出（最后3000字符）:")
print(out[-3000:])

# 下载结果
print("\n[5/6] 下载结果...")
# 先尝试从stdout提取JSON
if "JSONSTART" in out and "JSONEND" in out:
 js = out[out.find("JSONSTART")+len("JSONSTART"):out.find("JSONEND")]
 try:
  data = json.loads(js)
  rf = os.path.join(RDIR,"experiment_results.json")
  with open(rf,"w") as f: json.dump(data,f,indent=2,ensure_ascii=False)
  print(f"  ✅ 从stdout提取结果成功: {rf}")
 except: print("  ⚠️ stdout JSON解析失败，尝试SCP")

# SCP下载
wr("/tmp/dl.exp",f'''#!/usr/bin/expect -f
set timeout 60
spawn scp -o StrictHostKeyChecking=no -P {port} root@{host}:/root/results.json "{RDIR}/experiment_results.json"
expect "password:"; send "{pwd}\r"; expect eof
''')
run_expect("/tmp/dl.exp",60)

rf = os.path.join(RDIR,"experiment_results.json")
if os.path.exists(rf):
 with open(rf) as f: data=json.load(f)
 print("\n"+"="*60)
 print("✅ 实验完成！结果:")
 print("="*60)
 for sid,sd in data.items():
  print(f"\n场景 {sid}: {sd['name']}")
  for pn,pd in sd["policies"].items():
   print(f"  {pn:10s} | 距离={pd['total_distance']:.2f}m | 能耗={pd['total_energy']:.1f} | 完成={pd['task_complete']}")
else:
 print("❌ 结果未下载")

# 释放
print("\n[6/6] 释放实例...")
post("/api/v1/dev/instance/pro/power_off",{"instance_uuid":uuid})
time.sleep(5)
post("/api/v1/dev/instance/pro/release",{"instance_uuid":uuid})
print("  ✅ 已释放")