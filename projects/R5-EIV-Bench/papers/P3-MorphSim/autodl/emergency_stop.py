#!/usr/bin/env python3
"""尝试多种停止实例的API接口"""

import requests

API_TOKEN = os.environ.get("AUTODL_TOKEN", "")
INSTANCE_UUID = "pro-7841c5444592"
BASE_URL = "https://api.autodl.com"
headers = {"Authorization": API_TOKEN, "Content-Type": "application/json"}
body = {"instance_uuid": INSTANCE_UUID}

print("=" * 80)
print("尝试不同的停止实例接口...")
print("=" * 80)

# 尝试不同的endpoint
endpoints = [
    "/api/v1/dev/instance/pro/terminate",
    "/api/v1/dev/instance/pro/stop",
    "/api/v1/dev/instance/pro/shutdown",
    "/api/v1/dev/instance/pro/power_off",
    "/api/v1/dev/instance/pro/release",
    "/api/v1/dev/instance/pro/delete",
]

for endpoint in endpoints:
    url = f"{BASE_URL}{endpoint}"
    print(f"\n尝试: {endpoint}")
    try:
        response = requests.post(url, headers=headers, json=body, timeout=5)
        print(f"  状态码: {response.status_code}")
        
        if response.status_code != 404:
            print(f"  响应: {response.text[:200]}")
            if response.status_code == 200:
                print(f"  ✅ 成功！")
                break
        else:
            print(f"  ❌ 404")
    except Exception as e:
        print(f"  ❌ 错误: {e}")

print("\n" + "=" * 80)
print("如果没有成功的接口，请立即：")
print("1. 在AutoDL网页端手动停止实例")
print("2. 或者联系AutoDL客服强制停止")
print("=" * 80)