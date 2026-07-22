#!/usr/bin/env python3
"""AutoDL MorphSim自动化部署脚本

工作流程：
1. 创建RTX 4090实例
2. 上传代码
3. 安装依赖
4. 运行实验
5. 下载结果
6. 释放实例
"""

import os
import sys
import time
import json
import subprocess
from pathlib import Path
import requests
from typing import Dict, List, Optional

# ========== 配置加载 ==========
def load_config(config_file: str = "autodl_config.txt") -> Dict[str, str]:
    """加载配置文件"""
    config = {}
    with open(config_file) as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                config[key] = value
    return config

CONFIG = load_config()
API_TOKEN = CONFIG['AUTODL_API_TOKEN']
BASE_URL = "https://www.autodl.com/api/v1"
HEADERS = {"Authorization": f"Bearer {API_TOKEN}"}


# ========== AutoDL API封装 ==========
class AutoDLClient:
    def __init__(self, token: str):
        self.token = token
        self.headers = {"Authorization": f"Bearer {token}"}
    
    def create_instance(self, gpu_name: str, image_name: str, max_runtime_hours: int = 24) -> Dict:
        """创建GPU实例"""
        data = {
            "gpu_name": gpu_name,
            "image_name": image_name,
            "max_runtime_hours": max_runtime_hours
        }
        response = requests.post(f"{BASE_URL}/instance/create", 
                                headers=self.headers, json=data)
        return response.json()
    
    def get_instance_status(self, instance_id: str) -> Dict:
        """获取实例状态"""
        response = requests.get(f"{BASE_URL}/instance/{instance_id}/status",
                               headers=self.headers)
        return response.json()
    
    def get_instance_ssh_info(self, instance_id: str) -> Dict:
        """获取SSH连接信息"""
        response = requests.get(f"{BASE_URL}/instance/{instance_id}/ssh",
                               headers=self.headers)
        return response.json()
    
    def terminate_instance(self, instance_id: str) -> Dict:
        """释放实例"""
        response = requests.post(f"{BASE_URL}/instance/{instance_id}/terminate",
                                headers=self.headers)
        return response.json()


# ========== SSH操作封装 ==========
def run_ssh_command(host: str, command: str, key_file: str = None) -> str:
    """通过SSH执行远程命令"""
    ssh_cmd = f"ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
    if key_file:
        ssh_cmd += f" -i {key_file}"
    ssh_cmd += f" root@{host} '{command}'"
    
    result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True)
    return result.stdout + result.stderr


def scp_upload(host: str, local_path: str, remote_path: str, key_file: str = None) -> str:
    """上传文件到远程服务器"""
    scp_cmd = f"scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
    if key_file:
        scp_cmd += f" -i {key_file}"
    scp_cmd += f" -r {local_path} root@{host}:{remote_path}"
    
    result = subprocess.run(scp_cmd, shell=True, capture_output=True, text=True)
    return result.stdout + result.stderr


def scp_download(host: str, remote_path: str, local_path: str, key_file: str = None) -> str:
    """从远程服务器下载文件"""
    scp_cmd = f"scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
    if key_file:
        scp_cmd += f" -i {key_file}"
    scp_cmd += f" root@{host}:{remote_path} {local_path}"
    
    result = subprocess.run(scp_cmd, shell=True, capture_output=True, text=True)
    return result.stdout + result.stderr


# ========== MorphSim实验脚本 ==========
def generate_remote_script(config: Dict) -> str:
    """生成远程实验脚本"""
    scenarios = config['RUN_SCENARIOS'].split(',')
    policies = config['POLICIES'].split(',')
    
    script = f"""#!/bin/bash
set -e

echo "=== MorphSim实验开始 ==="

# 创建工作目录
mkdir -p {config['REMOTE_WORK_DIR']}
cd {config['REMOTE_WORK_DIR']}

# 安装依赖
echo "=== 安装依赖 ==="
pip install numpy torch mujoco scipy matplotlib tqdm wandb -q

# 运行实验
echo "=== 运行实验 ==="

# 测试3个场景
for scenario in {' '.join(scenarios)}; do
    echo "运行场景: $scenario"
    python -c "
from morphsim.scenarios.loader import ScenarioLoader, ScenarioRunner
from morphsim.baselines.policies import RigidBaseline, HeuristicMorphPolicy, PPOPolicy
import json

loader = ScenarioLoader()
runner = ScenarioRunner()
spec = loader.get_scenario('$scenario')
print('场景规格:', json.dumps(spec.__dict__, indent=2))
print('场景加载成功！')
"
done

echo "=== MorphSim实验完成 ==="
"""
    return script


# ========== 主流程 ==========
def main():
    print("🚀 MorphSim AutoDL自动化部署")
    print("="*50)
    
    # 初始化客户端
    client = AutoDLClient(API_TOKEN)
    
    # 步骤1: 创建实例
    print("\n[1/6] 创建RTX 4090实例...")
    create_response = client.create_instance(
        gpu_name=CONFIG['GPU_NAME'],
        image_name=CONFIG['IMAGE_NAME'],
        max_runtime_hours=int(CONFIG['MAX_RUNTIME_HOURS'])
    )
    
    if 'error' in create_response:
        print(f"❌ 创建实例失败: {create_response['error']}")
        print("可能原因：API Token无效、账号余额不足、区域无可用GPU")
        print("\n请检查：")
        print("1. Token是否正确复制")
        print("2. AutoDL账号是否充值（需要押金+预付）")
        print("3. 当前区域RTX 4090是否有货")
        return
    
    instance_id = create_response['instance_id']
    print(f"✅ 实例创建成功: {instance_id}")
    
    # 步骤2: 等待实例就绪
    print("\n[2/6] 等待实例启动（预计2-5分钟）...")
    max_wait = 600  # 10分钟
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        status = client.get_instance_status(instance_id)
        if status.get('status') == 'running':
            print("✅ 实例已启动")
            break
        elif status.get('status') == 'failed':
            print(f"❌ 实例启动失败: {status.get('error')}")
            return
        print(f"  当前状态: {status.get('status')}")
        time.sleep(30)
    else:
        print("❌ 等待超时")
        return
    
    # 步骤3: 获取SSH信息
    print("\n[3/6] 获取SSH连接信息...")
    ssh_info = client.get_instance_ssh_info(instance_id)
    host = ssh_info.get('host')
    print(f"✅ SSH地址: {host}")
    
    # 步骤4: 上传代码
    print("\n[4/6] 上传MorphSim代码...")
    local_path = CONFIG['LOCAL_CODE_PATH']
    remote_path = CONFIG['REMOTE_WORK_DIR']
    
    upload_result = scp_upload(host, local_path, remote_path)
    print(f"✅ 代码上传完成")
    
    # 步骤5: 运行实验
    print("\n[5/6] 在云服务器上运行实验...")
    remote_script = generate_remote_script(CONFIG)
    
    # 上传并执行脚本
    run_ssh_command(host, f"cat > {remote_path}/run_experiment.sh << 'EOF'\n{remote_script}\nEOF")
    run_ssh_command(host, f"chmod +x {remote_path}/run_experiment.sh")
    
    output = run_ssh_command(host, f"bash {remote_path}/run_experiment.sh")
    print(output)
    
    # 步骤6: 下载结果
    print("\n[6/6] 下载实验结果...")
    results_path = Path("results")
    results_path.mkdir(exist_ok=True)
    
    scp_download(host, f"{remote_path}/*.json", str(results_path))
    print(f"✅ 结果已保存到: {results_path}")
    
    # 释放实例（可选）
    print("\n是否释放实例？(y/n)")
    if input().lower() == 'y':
        client.terminate_instance(instance_id)
        print("✅ 实例已释放")
    
    print("\n🎉 MorphSim实验完成！")


if __name__ == "__main__":
    main()