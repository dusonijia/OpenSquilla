#!/usr/bin/env python3
"""释放所有shutdown状态的实例"""
import requests, time

API_TOKEN = os.environ.get("AUTODL_TOKEN", "")
BASE = "https://api.autodl.com"
H = {"Authorization": API_TOKEN, "Content-Type": "application/json"}

data = requests.post(f"{BASE}/api/v1/dev/instance/pro/list", headers=H, json={"page_index":1,"page_size":20}).json()

if data.get("code") == "Success":
    for inst in data["data"]["list"]:
        uid = inst["uuid"]
        status = inst["status"]
        if status in ("shutdown", "running"):
            # 先确保关机
            if status == "running":
                requests.post(f"{BASE}/api/v1/dev/instance/pro/power_off", headers=H, json={"instance_uuid": uid})
                print(f"{uid}: 关机中...")
                time.sleep(5)
            # 释放
            r = requests.post(f"{BASE}/api/v1/dev/instance/pro/release", headers=H, json={"instance_uuid": uid})
            print(f"{uid}: 释放 -> {r.json().get('code')}")

# 最终确认
time.sleep(3)
data2 = requests.post(f"{BASE}/api/v1/dev/instance/pro/list", headers=H, json={"page_index":1,"page_size":20}).json()
print(f"\n剩余实例数: {data2['data']['result_total'] if data2.get('code')=='Success' else '查询失败'}")
