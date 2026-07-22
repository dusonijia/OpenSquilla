#!/usr/bin/env python3
"""详细查询实例状态"""

import requests
import json

API_TOKEN = os.environ.get("AUTODL_TOKEN", "")
INSTANCE_UUID = "pro-7841c5444592"
BASE_URL = "https://api.autodl.com"

# 1. 查询实例详情
print("=" * 80)
print("查询实例详情")
print("=" * 80)
url1 = f"{BASE_URL}/api/v1/dev/instance/pro/snapshot"
body1 = {"instance_uuid": INSTANCE_UUID}
headers1 = {"Authorization": API_TOKEN, "Content-Type": "application/json"}

response1 = requests.post(url1, headers=headers1, json=body1)
print(f"状态码: {response1.status_code}")
print(f"响应内容:")
print(json.dumps(response1.json(), indent=2, ensure_ascii=False))

# 2. 查询SSH信息
print("\n" + "=" * 80)
print("查询SSH信息")
print("=" * 80)
url2 = f"{BASE_URL}/api/v1/dev/instance/pro/ssh_info"
body2 = {"instance_uuid": INSTANCE_UUID}
response2 = requests.post(url2, headers=headers1, json=body2)
print(f"状态码: {response2.status_code}")
print(f"响应内容:")
print(json.dumps(response2.json(), indent=2, ensure_ascii=False))

# 3. 查询实例日志
print("\n" + "=" * 80)
print("查询实例日志")
print("=" * 80)
url3 = f"{BASE_URL}/api/v1/dev/instance/pro/log"
body3 = {"instance_uuid": INSTANCE_UUID}
response3 = requests.post(url3, headers=headers1, json=body3)
print(f"状态码: {response3.status_code}")
print(f"响应内容:")
print(json.dumps(response3.json(), indent=2, ensure_ascii=False))