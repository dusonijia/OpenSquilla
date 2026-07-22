#!/usr/bin/env python3
"""删除异常实例"""

import requests
import json

API_TOKEN = os.environ.get("AUTODL_TOKEN", "")
INSTANCE_UUID = "pro-7841c5444592"
BASE_URL = "https://api.autodl.com"

print("=" * 80)
print("尝试删除异常实例")
print("=" * 80)

# 尝试删除实例
url = f"{BASE_URL}/api/v1/dev/instance/pro/terminate"
body = {"instance_uuid": INSTANCE_UUID}
headers = {"Authorization": API_TOKEN, "Content-Type": "application/json"}

response = requests.post(url, headers=headers, json=body)

print(f"状态码: {response.status_code}")
print(f"响应内容:")
print(response.text)

# 尝试读取JSON（如果可能）
try:
    data = response.json()
    print(f"\n解析结果:")
    print(json.dumps(data, indent=2, ensure_ascii=False))
except:
    print("\n（响应不是JSON格式）")