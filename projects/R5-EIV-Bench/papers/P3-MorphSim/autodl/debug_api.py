#!/usr/bin/env python3
"""AutoDL API诊断脚本 - 打印原始响应"""

import requests

# 你的Token
API_TOKEN = os.environ.get("AUTODL_TOKEN", "")

# 测试创建实例的API调用
url = "https://www.autodl.com/api/v1/instance/create"

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

data = {
    "gpu_name": "RTX4090",
    "image_name": "pytorch-2.3.1-cuda12.1-cudnn8-devel",
    "max_runtime_hours": 24
}

print("=" * 80)
print("AutoDL API 诊断测试")
print("=" * 80)
print(f"URL: {url}")
print(f"Method: POST")
print(f"Headers: {headers}")
print(f"Data: {data}")
print()

try:
    response = requests.post(url, headers=headers, json=data, timeout=10)
    
    print(f"响应状态码: {response.status_code}")
    print(f"响应头: {dict(response.headers)}")
    print()
    print("=== 原始响应内容（前1000字符）===")
    print(response.text[:1000])
    print()
    print("=== 尝试解析JSON ===")
    try:
        json_data = response.json()
        print("✅ JSON解析成功:")
        print(json_data)
    except Exception as e:
        print(f"❌ JSON解析失败: {e}")
        print()
        print("=== 完整响应内容 ===")
        print(response.text)
        
except Exception as e:
    print(f"❌ 请求失败: {e}")
    import traceback
    traceback.print_exc()