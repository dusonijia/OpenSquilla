#!/usr/bin/env python3
"""AutoDL SSH远程监控脚本"""

import subprocess
import time

# SSH连接信息（从AutoDL控制台获取）
# 先尝试获取SSH详情
import requests

API_TOKEN = os.environ.get("AUTODL_TOKEN", "")
INSTANCE_UUID = "pro-7841c5444592"
BASE_URL = "https://api.autodl.com"

# 获取SSH信息
print("获取SSH信息...")
url = f"{BASE_URL}/api/v1/dev/instance/pro/snapshot"
body = {"instance_uuid": INSTANCE_UUID}
headers = {"Authorization": API_TOKEN, "Content-Type": "application/json"}

response = requests.post(url, headers=headers, json=body)
data = response.json()

if data.get("code") == "Success":
    ssh_info = data.get("data", {})
    host = ssh_info.get("proxy_host")
    port = ssh_info.get("ssh_port")
    password = ssh_info.get("root_password")
    
    print(f"\nSSH连接信息:")
    print(f"  地址: {host}")
    print(f"  端口: {port}")
    print(f"  密码: {password}")
    
    # SSH远程查看实验进度
    print(f"\n正在连接SSH查看实验进度...")
    ssh_cmd = f"sshpass -p '{password}' ssh -o StrictHostKeyChecking=no -p {port} root@{host}"
    
    try:
        # 查看实验进度
        progress_cmd = f"{ssh_cmd} 'cd /root/morphsim && ps aux | grep python'"
        result = subprocess.run(progress_cmd, shell=True, capture_output=True, text=True, timeout=30)
        print("\n实验进程状态:")
        print(result.stdout)
        
        # 查看结果文件
        result_cmd = f"{ssh_cmd} 'ls -lh /root/morphsim/results/'"
        result = subprocess.run(result_cmd, shell=True, capture_output=True, text=True, timeout=30)
        print("\n结果文件:")
        print(result.stdout)
        
    except Exception as e:
        print(f"SSH连接失败: {e}")
        print("\n请手动SSH连接查看:")
        print(f"ssh -p {port} root@{host}")
        print(f"密码: {password}")
else:
    print(f"获取SSH信息失败: {data.get('msg')}")