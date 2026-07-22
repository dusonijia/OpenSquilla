#!/usr/bin/env python3
"""检查所有实例状态"""
import requests

API_TOKEN = os.environ.get("AUTODL_TOKEN", "")
BASE = "https://api.autodl.com"
H = {"Authorization": API_TOKEN, "Content-Type": "application/json"}

data = requests.post(f"{BASE}/api/v1/dev/instance/pro/list", headers=H, json={"page_index":1,"page_size":20}).json()

if data.get("code") == "Success":
    for inst in data["data"]["list"]:
        print(f"{inst['uuid']} | {inst['status']:10s} | {inst.get('name','')}")
        if inst["status"] == "running":
            print("  ⚠️ 还在计费！")
            # 立即关机
            r = requests.post(f"{BASE}/api/v1/dev/instance/pro/power_off", headers=H, json={"instance_uuid": inst["uuid"]}).json()
            print(f"  关机: {r.get('code')}")
            import time; time.sleep(3)
            r2 = requests.post(f"{BASE}/api/v1/dev/instance/pro/release", headers=H, json={"instance_uuid": inst["uuid"]}).json()
            print(f"  释放: {r2.get('code')}")
else:
    print(f"查询失败: {data}")
