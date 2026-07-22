#!/usr/bin/env python3
"""AutoDL API测试脚本 - 用于调试Token和API响应"""

import requests
import json

# 你的Token
API_TOKEN = os.environ.get("AUTODL_TOKEN", "")

# 测试多个可能的API endpoint
ENDPOINTS = [
    "https://www.autodl.com/api/v1/instances",
    "https://api.autodl.com/v1/instances",
    "https://www.autodl.com/api/instances",
]

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json",
    "User-Agent": "MorphSim-Research/1.0"
}

print("=" * 60)
print("AutoDL API Token 测试")
print("=" * 60)

for i, base_url in enumerate(ENDPOINTS, 1):
    print(f"\n[{i}] 测试: {base_url}")
    
    try:
        # GET请求测试
        response = requests.get(base_url, headers=HEADERS, timeout=10)
        
        print(f"  Status: {response.status_code}")
        print(f"  Content-Type: {response.headers.get('Content-Type', 'N/A')}")
        
        # 显示响应的前500字符
        preview = response.text[:500]
        print(f"  Response Preview:\n{preview}")
        
        # 尝试解析JSON
        try:
            data = response.json()
            print(f"  ✅ JSON解析成功")
            print(f"  Keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
        except Exception as e:
            print(f"  ❌ JSON解析失败: {e}")
            
    except Exception as e:
        print(f"  ❌ 请求失败: {e}")

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)