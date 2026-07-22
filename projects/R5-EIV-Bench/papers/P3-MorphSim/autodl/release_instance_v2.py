#!/usr/bin/env python3
"""按照官方文档释放实例"""

import requests

API_TOKEN = os.environ.get("AUTODL_TOKEN", "")
INSTANCE_UUID = "pro-7841c5444592"

# 释放实例（文档明确要求先关机再释放）
url = "https://api.autodl.com/api/v1/dev/instance/pro/release"
body = {"instance_uuid": INSTANCE_UUID}
headers = {"Authorization": API_TOKEN, "Content-Type": "application/json"}

print("释放实例...")
response = requests.post(url, headers=headers, json=body)
print(f"状态码: {response.status_code}")
print(f"响应: {response.text}")

if response.status_code == 200:
    data = response.json()
    if data.get("code") == "Success":
        print("✅ 实例已彻底释放")
    else:
        print(f"❌ 释放失败: {data.get('msg')}")