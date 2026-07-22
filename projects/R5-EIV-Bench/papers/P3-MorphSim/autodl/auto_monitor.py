#!/usr/bin/env python3
"""AutoDL实例自动监控脚本 - 防止长时间空跑烧钱

功能：
1. 检查所有实例状态
2. 如果实例running超过30分钟，自动关机+释放
3. 如果实例shutdown，自动释放

由cron每10分钟调用一次
"""

import requests
import time
import json
from datetime import datetime, timezone, timedelta

API_TOKEN = os.environ.get("AUTODL_TOKEN", "")
BASE = "https://api.autodl.com"
H = {"Authorization": API_TOKEN, "Content-Type": "application/json"}

# 最多允许运行30分钟
MAX_RUNTIME_MINUTES = 30

def get_all_instances():
    """获取所有实例列表"""
    r = requests.post(f"{BASE}/api/v1/dev/instance/pro/list", headers=H, json={"page_index": 1, "page_size": 50})
    data = r.json()
    if data.get("code") == "Success":
        return data["data"]["list"]
    return []

def power_off(uuid):
    """关机"""
    r = requests.post(f"{BASE}/api/v1/dev/instance/pro/power_off", headers=H, json={"instance_uuid": uuid})
    return r.json().get("code")

def release(uuid):
    """释放"""
    r = requests.post(f"{BASE}/api/v1/dev/instance/pro/release", headers=H, json={"instance_uuid": uuid})
    return r.json().get("code")

def main():
    now = datetime.now(timezone(timedelta(hours=8)))  # CST
    print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] AutoDL实例监控")
    print("=" * 60)

    instances = get_all_instances()
    if not instances:
        print("无实例，一切正常")
        return

    print(f"总实例数: {len(instances)}")

    for inst in instances:
        uid = inst["uuid"]
        status = inst["status"]
        name = inst.get("instance_name", "")
        created = inst.get("created_at", "")

        print(f"\n  {uid} | {status} | {name} | 创建: {created}")

        if status == "running":
            # 计算运行时间
            try:
                created_time = datetime.fromisoformat(created)
                runtime = (now - created_time).total_seconds() / 60
                print(f"  已运行: {runtime:.0f}分钟")

                if runtime > MAX_RUNTIME_MINUTES:
                    print(f"  ⚠️ 超过{MAX_RUNTIME_MINUTES}分钟！自动关机...")
                    off_result = power_off(uid)
                    print(f"  关机: {off_result}")
                    time.sleep(5)
                    rel_result = release(uid)
                    print(f"  释放: {rel_result}")
                else:
                    print(f"  ✅ 运行中（{runtime:.0f}/{MAX_RUNTIME_MINUTES}分钟）")
            except Exception as e:
                print(f"  ⚠️ 时间解析失败: {e}，直接关机")
                power_off(uid)
                time.sleep(3)
                release(uid)

        elif status == "shutdown":
            print(f"  释放中...")
            rel_result = release(uid)
            print(f"  释放: {rel_result}")

    # 最终确认
    time.sleep(2)
    remaining = get_all_instances()
    print(f"\n最终剩余实例数: {len(remaining)}")

if __name__ == "__main__":
    main()
