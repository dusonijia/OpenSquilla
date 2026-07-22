#!/usr/bin/env python3
"""AutoDL 完整API操作 - 按官方文档修正"""

import requests
import json
import time

API_TOKEN = os.environ.get("AUTODL_TOKEN", "")
INSTANCE_UUID = "pro-7841c5444592"
BASE_URL = "https://api.autodl.com"
HEADERS = {"Authorization": API_TOKEN, "Content-Type": "application/json"}

def print_response(name, response):
    print(f"\n{'='*60}")
    print(f"[{name}]")
    print(f"状态码: {response.status_code}")
    try:
        data = response.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return data
    except:
        print(f"原始响应: {response.text[:500]}")
        return None

# 1. 获取实例状态 (GET)
print("\n" + "="*60)
print("步骤1: 获取实例状态 (GET /status)")
url = f"{BASE_URL}/api/v1/dev/instance/pro/status"
body = {"instance_uuid": INSTANCE_UUID}
resp = requests.get(url, headers=HEADERS, json=body)
status_data = print_response("实例状态", resp)

# 2. 获取实例详情/SSH信息 (GET)
print("\n" + "="*60)
print("步骤2: 获取实例详情 (GET /snapshot)")
url = f"{BASE_URL}/api/v1/dev/instance/pro/snapshot"
resp = requests.get(url, headers=HEADERS, json=body)
snapshot_data = print_response("实例详情", resp)

# 3. 如果状态不是running，尝试开机
if status_data and status_data.get("code") == "Success":
    current_status = status_data.get("data", "")
    print(f"\n当前状态: {current_status}")
    
    if current_status != "running":
        print("\n步骤3: 实例未运行，尝试开机...")
        url = f"{BASE_URL}/api/v1/dev/instance/pro/power_on"
        power_body = {
            "instance_uuid": INSTANCE_UUID,
            "payload": "gpu",
            "start_command": "echo 'MorphSim instance powered on'"
        }
        resp = requests.post(url, headers=HEADERS, json=power_body)
        power_data = print_response("开机结果", resp)
        
        # 等待开机
        print("\n等待实例启动（30秒）...")
        time.sleep(30)
        
        # 重新查询状态
        url = f"{BASE_URL}/api/v1/dev/instance/pro/status"
        resp = requests.get(url, headers=HEADERS, json=body)
        status_data = print_response("开机后状态", resp)
        
        # 重新获取详情
        url = f"{BASE_URL}/api/v1/dev/instance/pro/snapshot"
        resp = requests.get(url, headers=HEADERS, json=body)
        snapshot_data = print_response("开机后详情", resp)
    else:
        print("实例已经在运行中！")

# 4. 输出SSH连接信息
if snapshot_data and snapshot_data.get("code") == "Success":
    data = snapshot_data.get("data", {})
    print("\n" + "="*60)
    print("SSH连接信息:")
    print(f"  地址: {data.get('proxy_host', 'N/A')}")
    print(f"  端口: {data.get('ssh_port', 'N/A')}")
    print(f"  密码: {data.get('root_password', 'N/A')}")
    print(f"  SSH命令: {data.get('ssh_command', 'N/A')}")
    print(f"  JupyterLab: {data.get('jupyter_domain', 'N/A')}")
