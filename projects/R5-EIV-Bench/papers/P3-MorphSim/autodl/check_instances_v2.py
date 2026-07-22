#!/usr/bin/env python3
"""AutoDL实例状态检查脚本 v2 (修正版)"""

import requests
import json

# 你的Token
API_TOKEN = os.environ.get("AUTODL_TOKEN", "")

# AutoDL API地址
BASE_URL = "https://api.autodl.com"
HEADERS = {"Authorization": API_TOKEN, "Content-Type": "application/json"}

print("=" * 80)
print("AutoDL 实例状态查询 v2")
print("=" * 80)

# 查询所有实例（注意：文档说是POST）
print("\n[1] 查询实例列表...")
url = f"{BASE_URL}/api/v1/dev/instance/pro/list"
body = {"page_index": 1, "page_size": 10}

response = requests.post(url, headers=HEADERS, json=body)

print(f"状态码: {response.status_code}")
print(f"响应内容: {response.text}")

try:
    result = response.json()
    if result.get("code") == "Success":
        data = result.get("data", {})
        instances = data.get("list", [])
        total = data.get("result_total", 0)
        
        print(f"\n总共有 {total} 个实例")
        print(f"当前显示 {len(instances)} 个实例:\n")
        
        if instances:
            for i, inst in enumerate(instances, 1):
                name = inst.get("name", "未知")
                status = inst.get("status", "未知")
                uuid = inst.get("uuid", "未知")
                gpu_spec = inst.get("gpu_spec_uuid", "未知")
                region = inst.get("region_name", "未知")
                created_at = inst.get("created_at", "未知")
                
                print(f"实例 {i}:")
                print(f"  名称: {name}")
                print(f"  状态: {status}")
                print(f"  区域: {region}")
                print(f"  GPU规格: {gpu_spec}")
                print(f"  UUID: {uuid}")
                print(f"  创建时间: {created_at}")
                
                # 如果运行中，获取SSH信息
                if status == "running":
                    print(f"\n  获取SSH详情...")
                    snapshot_url = f"{BASE_URL}/api/v1/dev/instance/pro/snapshot"
                    snapshot_body = {"instance_uuid": uuid}
                    snapshot_resp = requests.post(snapshot_url, headers=HEADERS, json=snapshot_body)
                    
                    if snapshot_resp.status_code == 200:
                        snapshot_data = snapshot_resp.json()
                        if snapshot_data.get("code") == "Success":
                            snapshot = snapshot_data.get("data", {})
                            print(f"  SSH地址: {snapshot.get('proxy_host', 'N/A')}")
                            print(f"  SSH端口: {snapshot.get('ssh_port', 'N/A')}")
                            print(f"  SSH密码: {snapshot.get('root_password', 'N/A')}")
                            print(f"  SSH命令: {snapshot.get('ssh_command', 'N/A')}")
                            print(f"  Jupyter地址: {snapshot.get('jupyter_domain', 'N/A')}")
                    print()
                else:
                    print()
    else:
        print(f"❌ 查询失败: {result.get('msg', '未知错误')}")
        print(f"错误代码: {result.get('code', '未知')}")
        
except Exception as e:
    print(f"❌ 解析响应失败: {e}")
    print(f"\n原始响应: {response.text}")

print("=" * 80)