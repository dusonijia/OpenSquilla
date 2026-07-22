#!/usr/bin/env python3
"""AutoDL实例状态检查脚本"""

import requests
import json

# 你的Token
API_TOKEN = os.environ.get("AUTODL_TOKEN", "")

# AutoDL API地址
BASE_URL = "https://api.autodl.com"
HEADERS = {"Authorization": API_TOKEN}

print("=" * 80)
print("AutoDL 实例状态查询")
print("=" * 80)

# 查询所有实例
print("\n[1] 查询所有实例...")
url = f"{BASE_URL}/api/v1/dev/instance/pro/list"
response = requests.get(url, headers=HEADERS)

print(f"状态码: {response.status_code}")
print(f"响应内容: {response.text}")

try:
    result = response.json()
    if result.get("code") == "Success":
        instances = result.get("data", {}).get("instances", [])
        
        if instances:
            print(f"\n✅ 找到 {len(instances)} 个实例:\n")
            
            for i, inst in enumerate(instances, 1):
                name = inst.get("instance_name", "未知")
                status = inst.get("status", "未知")
                gpu = inst.get("gpu_spec_display_name", "未知")
                uuid = inst.get("uuid", "未知")
                created_at = inst.get("created_at", "未知")
                
                print(f"实例 {i}:")
                print(f"  名称: {name}")
                print(f"  状态: {status}")
                print(f"  GPU: {gpu}")
                print(f"  UUID: {uuid}")
                print(f"  创建时间: {created_at}")
                print()
                
                # 获取SSH信息（如果运行中）
                if status == "running":
                    print(f"  正在获取SSH信息...")
                    ssh_url = f"{BASE_URL}/api/v1/dev/instance/pro/ssh_info?uuid={uuid}"
                    ssh_resp = requests.get(ssh_url, headers=HEADERS)
                    
                    if ssh_resp.status_code == 200:
                        ssh_data = ssh_resp.json()
                        if ssh_data.get("code") == "Success":
                            ssh_info = ssh_data.get("data", {})
                            print(f"  SSH地址: {ssh_info.get('host', 'N/A')}")
                            print(f"  SSH端口: {ssh_info.get('port', 'N/A')}")
                            print(f"  SSH用户: {ssh_info.get('user', 'N/A')}")
                            print(f"  SSH密码: {ssh_info.get('password', 'N/A')}")
                    print()
        else:
            print("❌ 没有找到任何实例")
            print("\n可能原因:")
            print("1. 创建实例失败")
            print("2. 实例已被手动释放")
            print("3. API权限不足")
            print("4. Token已失效")
    else:
        print(f"❌ 查询失败: {result.get('msg', '未知错误')}")
        
except Exception as e:
    print(f"❌ 解析响应失败: {e}")
    print(f"\n原始响应: {response.text}")

print("=" * 80)