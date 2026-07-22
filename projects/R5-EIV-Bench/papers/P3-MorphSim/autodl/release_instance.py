#!/usr/bin/env python3
"""立即释放AutoDL实例停止计费"""

import requests

API_TOKEN = os.environ.get("AUTODL_TOKEN", "")
INSTANCE_UUID = "pro-7841c5444592"
BASE_URL = "https://api.autodl.com"

print("=" * 80)
print("⚠️  立即释放实例停止计费")
print("=" * 80)

url = f"{BASE_URL}/api/v1/dev/instance/pro/stop"
body = {"instance_uuid": INSTANCE_UUID}
headers = {"Authorization": API_TOKEN, "Content-Type": "application/json"}

response = requests.post(url, headers=headers, json=body)

print(f"状态码: {response.status_code}")
print(f"响应内容: {response.text}")

import json
try:
    data = response.json()
    print(f"\n解析结果:")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    
    if data.get("code") == "Success":
        print("\n✅ 实例已释放，计费停止")
    else:
        print(f"\n❌ 释放失败: {data.get('msg')}")
except:
    print("\n（响应不是JSON格式）")

# 再次查询确认状态
print("\n" + "=" * 80)
print("查询最终状态...")
print("=" * 80)
url2 = f"{BASE_URL}/api/v1/dev/instance/pro/status?instance_uuid={INSTANCE_UUID}"
response2 = requests.get(url2, headers=headers)
print(f"状态查询: {response2.text}")