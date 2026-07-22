#!/usr/bin/env python3
"""AutoDL API - 修正GET请求参数传递方式"""

import requests
import json
import time

API_TOKEN = os.environ.get("AUTODL_TOKEN", "")
INSTANCE_UUID = "pro-7841c5444592"
BASE_URL = "https://api.autodl.com"
HEADERS = {"Authorization": API_TOKEN}

def show(name, resp):
    print(f"\n{'='*60}")
    print(f"[{name}] 状态码: {resp.status_code}")
    try:
        data = resp.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return data
    except:
        print(f"原始: {resp.text[:500]}")
        return None

# 1. 获取实例状态 - GET + params
print("步骤1: 获取实例状态")
url = f"{BASE_URL}/api/v1/dev/instance/pro/status"
resp = requests.get(url, headers=HEADERS, params={"instance_uuid": INSTANCE_UUID})
status_data = show("实例状态", resp)

# 2. 获取实例详情 - GET + params
print("\n步骤2: 获取实例详情")
url = f"{BASE_URL}/api/v1/dev/instance/pro/snapshot"
resp = requests.get(url, headers=HEADERS, params={"instance_uuid": INSTANCE_UUID})
snapshot_data = show("实例详情", resp)

# 3. 判断状态，决定是否需要开机
current_status = None
if status_data and status_data.get("code") == "Success":
    current_status = status_data.get("data", "")

if snapshot_data and snapshot_data.get("code") == "Success":
    data = snapshot_data.get("data", {})
    current_status = data.get("status", current_status)

print(f"\n>>> 当前实例状态: {current_status}")

# 4. 如果不是running，尝试开机
if current_status and current_status != "running":
    print(f"\n步骤3: 实例状态为 '{current_status}'，尝试开机...")
    url = f"{BASE_URL}/api/v1/dev/instance/pro/power_on"
    resp = requests.post(url, headers=HEADERS, json={
        "instance_uuid": INSTANCE_UUID,
        "payload": "gpu",
        "start_command": "echo 'MorphSim ready'"
    })
    show("开机结果", resp)
    
    print("\n等待30秒...")
    time.sleep(30)
    
    # 重新查询
    url = f"{BASE_URL}/api/v1/dev/instance/pro/snapshot"
    resp = requests.get(url, headers=HEADERS, params={"instance_uuid": INSTANCE_UUID})
    snapshot_data = show("开机后详情", resp)
else:
    print("实例已在运行中或状态未知")

# 5. 输出SSH信息
if snapshot_data and snapshot_data.get("code") == "Success":
    data = snapshot_data.get("data", {})
    print("\n" + "="*60)
    print("SSH连接信息:")
    print(f"  命令: {data.get('ssh_command', 'N/A')}")
    print(f"  地址: {data.get('proxy_host', 'N/A')}")
    print(f"  端口: {data.get('ssh_port', 'N/A')}")
    print(f"  密码: {data.get('root_password', 'N/A')}")
    print(f"  JupyterLab: {data.get('jupyter_domain', 'N/A')}")
