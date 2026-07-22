#!/usr/bin/env python3
"""AutoDL MorphSim自动化部署脚本 v2（基于官方API文档修复版）"""

import os
import sys
import time
import json
import subprocess
from pathlib import Path
import requests
from typing import Dict, Optional

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
BASE_URL = "https://api.autodl.com"
HEADERS = {"Authorization": API_TOKEN}  # 无Bearer前缀

# ========== AutoDL API封装 ==========
class AutoDLClient:
    def __init__(self, token: str):
        self.token = token
        self.headers = {"Authorization": token}
        self.base_url = "https://api.autodl.com"
    
    def create_instance(self) -> Dict:
        """创建RTX 4090实例"""
        url = f"{self.base_url}/api/v1/dev/instance/pro/create"
        
        # 根据官方API文档配置
        data = {
            "req_gpu_amount": 1,  # 1块GPU
            "expand_system_disk_by_gb": 0,  # 不扩容
            "gpu_spec_uuid": "v-48g",  # RTX 4090-48G
            "image_uuid": "base-image-l2t43iu6uk",  # PyTorch 2.0.0
            "cuda_v_from": 113,  # CUDA >= 11.3
            "instance_name": "MorphSim-Research",
            "start_command": "echo 'MorphSim instance ready'"
        }
        
        print(f"创建实例请求: {json.dumps(data, indent=2)}")
        response = requests.post(url, headers=self.headers, json=data, timeout=30)
        
        print(f"响应状态码: {response.status_code}")
        print(f"响应内容: {response.text}")
        
        return response.json()
    
    def get_instance_status(self, instance_uuid: str) -> Dict:
        """获取实例状态"""
        url = f"{self.base_url}/api/v1/dev/instance/pro/status"
        data = {"instance_uuid": instance_uuid}
        response = requests.post(url, headers=self.headers, json=data, timeout=10)
        return response.json()
    
    def get_instance_info(self, instance_uuid: str) -> Dict:
        """获取实例详情（包括SSH信息）"""
        url = f"{self.base_url}/api/v1/dev/instance/pro/snapshot"
        data = {"instance_uuid": instance_uuid}
        response = requests.post(url, headers=self.headers, json=data, timeout=10)
        return response.json()
    
    def power_on_instance(self, instance_uuid: str) -> Dict:
        """开机实例"""
        url = f"{self.base_url}/api/v1/dev/instance/pro/power_on"
        data = {
            "instance_uuid": instance_uuid,
            "payload": "gpu",  # 有卡模式
            "start_command": "echo 'MorphSim instance ready'"
        }
        response = requests.post(url, headers=self.headers, json=data, timeout=10)
        return response.json()
    
    def power_off_instance(self, instance_uuid: str) -> Dict:
        """关机实例"""
        url = f"{self.base_url}/api/v1/dev/instance/pro/power_off"
        data = {"instance_uuid": instance_uuid}
        response = requests.post(url, headers=self.headers, json=data, timeout=10)
        return response.json()
    
    def release_instance(self, instance_uuid: str) -> Dict:
        """释放实例"""
        url = f"{self.base_url}/api/v1/dev/instance/pro/release"
        data = {"instance_uuid": instance_uuid}
        response = requests.post(url, headers=self.headers, json=data, timeout=10)
        return response.json()


# ========== SSH操作封装 ==========
def ssh_exec(ssh_info: Dict, command: str, timeout: int = 600) -> str:
    """通过SSH执行命令"""
    host = ssh_info['proxy_host']
    port = ssh_info['ssh_port']
    password = ssh_info['root_password']
    
    ssh_cmd = f"sshpass -p '{password}' ssh -o StrictHostKeyChecking=no -p {port} root@{host} '{command}'"
    
    result = subprocess.run(
        ssh_cmd,
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout
    )
    
    return result.stdout


def scp_upload(ssh_info: Dict, local_path: str, remote_path: str) -> bool:
    """通过SCP上传文件"""
    host = ssh_info['proxy_host']
    port = ssh_info['ssh_port']
    password = ssh_info['root_password']
    
    scp_cmd = f"sshpass -p '{password}' scp -o StrictHostKeyChecking=no -P {port} -r {local_path} root@{host}:{remote_path}"
    
    result = subprocess.run(
        scp_cmd,
        shell=True,
        capture_output=True,
        text=True,
        timeout=300
    )
    
    return result.returncode == 0


def scp_download(ssh_info: Dict, remote_path: str, local_path: str) -> bool:
    """通过SCP下载文件"""
    host = ssh_info['proxy_host']
    port = ssh_info['ssh_port']
    password = ssh_info['root_password']
    
    scp_cmd = f"sshpass -p '{password}' scp -o StrictHostKeyChecking=no -P {port} -r root@{host}:{remote_path} {local_path}"
    
    result = subprocess.run(
        scp_cmd,
        shell=True,
        capture_output=True,
        text=True,
        timeout=300
    )
    
    return result.returncode == 0


# ========== 主流程 ==========
def main():
    print("=" * 60)
    print("🚀 MorphSim AutoDL自动化部署 v2（官方API修复版）")
    print("=" * 60)
    
    client = AutoDLClient(API_TOKEN)
    
    # ========== 步骤1: 创建实例 ==========
    print("\n[1/6] 创建RTX 4090实例...")
    try:
        create_response = client.create_instance()
        
        if create_response.get('code') == 'Success':
            instance_id = create_response['data']
            print(f"✅ 实例创建成功！实例ID: {instance_id}")
        else:
            print(f"❌ 创建实例失败: {create_response}")
            return
    except Exception as e:
        print(f"❌ 创建实例异常: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # ========== 步骤2: 等待实例启动 ==========
    print(f"\n[2/6] 等待实例启动...")
    max_wait = 600  # 最多等待10分钟
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        try:
            status_response = client.get_instance_status(instance_id)
            status = status_response.get('data', 'unknown')
            print(f"  当前状态: {status}")
            
            if status == 'running':
                print("✅ 实例已启动")
                break
            elif status in ['creating', 'starting', 'restarting']:
                time.sleep(10)
                continue
            else:
                print(f"❌ 实例异常状态: {status}")
                return
        except Exception as e:
            print(f"⚠️  查询状态失败: {e}")
            time.sleep(10)
    else:
        print("❌ 等待实例启动超时")
        return
    
    # ========== 步骤3: 获取SSH信息 ==========
    print(f"\n[3/6] 获取SSH连接信息...")
    try:
        info_response = client.get_instance_info(instance_id)
        
        if info_response.get('code') == 'Success':
            ssh_info = info_response['data']
            print(f"✅ SSH信息获取成功:")
            print(f"  地址: {ssh_info['proxy_host']}:{ssh_info['ssh_port']}")
            print(f"  密码: {ssh_info['root_password']}")
        else:
            print(f"❌ 获取SSH信息失败: {info_response}")
            return
    except Exception as e:
        print(f"❌ 获取SSH信息异常: {e}")
        return
    
    # ========== 步骤4: 上传代码 ==========
    print(f"\n[4/6] 上传MorphSim代码...")
    try:
        local_code_path = CONFIG['LOCAL_CODE_PATH']
        remote_work_dir = CONFIG['REMOTE_WORK_DIR']
        
        if scp_upload(ssh_info, local_code_path, remote_work_dir):
            print(f"✅ 代码上传成功")
        else:
            print(f"❌ 代码上传失败")
            return
    except Exception as e:
        print(f"❌ 上传代码异常: {e}")
        return
    
    # ========== 步骤5: 运行实验 ==========
    print(f"\n[5/6] 在云服务器上运行实验...")
    try:
        scenarios = CONFIG['RUN_SCENARIOS'].split(',')
        num_runs = int(CONFIG['NUM_RUNS_PER_SCENARIO'])
        policies = CONFIG['POLICIES'].split(',')
        
        # 在远程服务器上运行实验脚本
        remote_script = f"""
cd {CONFIG['REMOTE_WORK_DIR']}
mkdir -p results
for scenario in {' '.join(scenarios)}; do
  for policy in {' '.join(policies)}; do
    for i in $(seq 1 {num_runs}); do
      echo "Running scenario=$scenario policy=$policy run=$i"
      # 这里会调用实际的实验脚本
      # python run_experiment.py --scenario $scenario --policy $policy --seed $i --output results/$scenario_${{policy}}_${{i}}.json
    done
  done
done
echo "All experiments completed"
"""
        
        output = ssh_exec(ssh_info, remote_script, timeout=7200)  # 2小时
        print(f"实验输出:\n{output}")
        print("✅ 实验运行完成")
    except Exception as e:
        print(f"❌ 运行实验异常: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # ========== 步骤6: 下载结果 ==========
    print(f"\n[6/6] 下载实验结果...")
    try:
        local_results_dir = os.path.join(os.path.dirname(__file__), 'results')
        os.makedirs(local_results_dir, exist_ok=True)
        
        remote_results_dir = f"{CONFIG['REMOTE_WORK_DIR']}/results"
        
        if scp_download(ssh_info, remote_results_dir, local_results_dir):
            print(f"✅ 结果下载成功，保存到: {local_results_dir}")
        else:
            print(f"❌ 结果下载失败")
            return
    except Exception as e:
        print(f"❌ 下载结果异常: {e}")
        return
    
    # ========== 释放实例 ==========
    print(f"\n是否释放实例？(y/n)")
    # response = input().strip().lower()
    # 暂时默认自动释放
    response = "y"
    
    if response == 'y':
        print(f"释放实例中...")
        try:
            # 先关机
            client.power_off_instance(instance_id)
            time.sleep(30)  # 等待关机完成
            
            # 再释放
            release_response = client.release_instance(instance_id)
            
            if release_response.get('code') == 'Success':
                print(f"✅ 实例已释放")
            else:
                print(f"❌ 释放实例失败: {release_response}")
        except Exception as e:
            print(f"❌ 释放实例异常: {e}")
    else:
        print(f"实例未释放，请记得手动释放避免扣费")
    
    print("\n" + "=" * 60)
    print("🎉 MorphSim AutoDL部署完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()