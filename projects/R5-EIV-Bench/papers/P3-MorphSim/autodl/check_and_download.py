#!/usr/bin/env python3
"""检查实例状态并下载结果"""
import requests, json, subprocess, os, sys

API_TOKEN = os.environ.get("AUTODL_TOKEN", "")
HEADERS = {"Authorization": API_TOKEN, "Content-Type": "application/json"}
BASE = "https://api.autodl.com"
RESULTS_DIR = "/Users/du/Library/Application Support/@opensquilla/desktop-electron/opensquilla/state/workspace/eiv-research/projects/R5-EIV-Bench/papers/P3-MorphSim/results"

# 查询实例
data = requests.post(f"{BASE}/api/v1/dev/instance/pro/list", headers=HEADERS, json={"page_index": 1, "page_size": 10}).json()
if data.get("code") != "Success":
    print(f"查询失败: {data}")
    sys.exit(1)

for inst in data["data"]["list"]:
    uuid = inst["uuid"]
    status = inst["status"]
    name = inst.get("name", "")
    print(f"UUID: {uuid} | 状态: {status} | 名称: {name}")
    
    if status == "running":
        # 获取SSH
        snap = requests.get(f"{BASE}/api/v1/dev/instance/pro/snapshot?instance_uuid={uuid}", headers=HEADERS).json()
        if snap.get("code") == "Success":
            d = snap["data"]
            host = d["proxy_host"]
            port = d["ssh_port"]
            pwd = d["root_password"]
            print(f"  SSH: {host}:{port}")
            
            # 尝试下载结果
            script = "#!/usr/bin/expect -f\n"
            script += "set timeout 60\n"
            script += f'spawn scp -o StrictHostKeyChecking=no -P {port} root@{host}:/root/experiment_results.json "{RESULTS_DIR}/"\n'
            script += 'expect "password:"\n'
            script += f'send "{pwd}\\r"\n'
            script += "expect eof\n"
            
            with open("/tmp/dl.exp", "w") as f:
                f.write(script)
            os.chmod("/tmp/dl.exp", 0o755)
            
            r = subprocess.run(["expect", "/tmp/dl.exp"], timeout=60, capture_output=True, text=True)
            print(f"  SCP输出: {r.stdout[-200:]}")
            
            result_file = os.path.join(RESULTS_DIR, "experiment_results.json")
            if os.path.exists(result_file):
                size = os.path.getsize(result_file)
                print(f"  ✅ 结果下载成功! ({size} bytes)")
                with open(result_file) as f:
                    data = json.load(f)
                for sid, sdata in data.items():
                    print(f"\n  场景 {sid}: {sdata['name']}")
                    for pn, pd in sdata["policies"].items():
                        print(f"    {pn:10s} | 距离={pd['total_distance']:.2f}m | 能耗={pd['total_energy']:.1f}")
            else:
                print("  ❌ 结果文件不存在")
            
            # 检查实验日志
            script2 = "#!/usr/bin/expect -f\n"
            script2 += "set timeout 30\n"
            script2 += f'spawn ssh -o StrictHostKeyChecking=no -p {port} root@{host}\n'
            script2 += 'expect "password:"\n'
            script2 += f'send "{pwd}\\r"\n'
            script2 += 'expect "*#"\n'
            script2 += 'send "cat /root/exp.log 2>/dev/null | tail -20\\r"\n'
            script2 += 'expect "*#"\n'
            script2 += 'send "exit\\r"\n'
            script2 += "expect eof\n"
            
            with open("/tmp/check_log.exp", "w") as f:
                f.write(script2)
            os.chmod("/tmp/check_log.exp", 0o755)
            
            r2 = subprocess.run(["expect", "/tmp/check_log.exp"], timeout=30, capture_output=True, text=True)
            print(f"\n  实验日志:\n{r2.stdout[-1000:]}")
            
            # 关机释放
            print("\n  关机释放...")
            requests.post(f"{BASE}/api/v1/dev/instance/pro/power_off", headers=HEADERS, json={"instance_uuid": uuid})
            import time; time.sleep(5)
            requests.post(f"{BASE}/api/v1/dev/instance/pro/release", headers=HEADERS, json={"instance_uuid": uuid})
            print("  ✅ 已释放")
