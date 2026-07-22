# AutoDL部署脚本使用说明

## 文件说明

```
autodl/
├── autodl_config.txt      ← 配置文件（已填入你的API Token）
└── deploy_autodl.py       ← 自动化部署脚本
```

## 使用步骤

### 1. 安装依赖

```bash
cd eiv-research/projects/R5-EIV-Bench/papers/P3-MorphSim/autodl
pip install requests
```

### 2. 检查配置

编辑 `autodl_config.txt`，确认以下配置：

- `AUTODL_API_TOKEN`: 已填入你的Token ✅
- `GPU_NAME`: RTX4090（默认）
- `MAX_RUNTIME_HOURS`: 24小时（默认）
- `RUN_SCENARIOS`: A-01,B-01,C-01（验证3个场景）
- `NUM_RUNS_PER_SCENARIO`: 20次运行
- `POLICIES`: 4种基线策略

### 3. 运行脚本

```bash
python deploy_autodl.py
```

### 4. 工作流程

脚本会自动执行以下步骤：

```
[1/6] 创建RTX 4090实例
   ↓
[2/6] 等待实例启动（2-5分钟）
   ↓
[3/6] 获取SSH连接信息
   ↓
[4/6] 上传MorphSim代码
   ↓
[5/6] 在云服务器上运行实验
   ↓
[6/6] 下载实验结果
```

### 5. 查看结果

实验结果会保存在 `results/` 目录下：
- `results/A-01/*.json` — 场景A-01的结果
- `results/B-01/*.json` — 场景B-01的结果
- `results/C-01/*.json` — 场景C-01的结果

### 6. 释放实例

实验完成后，脚本会询问是否释放实例：
```
是否释放实例？(y/n)
```
输入 `y` 释放，输入 `n` 保留。

## 成本估算

| 项目 | 费用 |
|------|------|
| RTX 4090 租用 | ¥2.5-3/小时 |
| 3场景验证（约2小时） | ¥5-6 |
| 50场景全量（约60小时） | ¥150-180 |

## 常见问题

### Q1: 创建实例失败？

可能原因：
- API Token无效 → 检查Token是否正确复制
- 账号余额不足 → 充值AutoDL账号
- 区域无可用GPU → 切换区域或等待

### Q2: SSH连接失败？

可能原因：
- 实例未完全启动 → 等待更长时间
- 网络问题 → 检查本地网络
- 实例已释放 → 重新创建实例

### Q3: 依赖安装失败？

可能原因：
- 镜像不匹配 → 修改 `IMAGE_NAME` 配置
- 网络问题 → 重试或更换镜像

## 进阶使用

### 修改实验范围

编辑 `autodl_config.txt`：
```bash
# 只跑A-01场景，10次
RUN_SCENARIOS=A-01
NUM_RUNS_PER_SCENARIO=10
```

### 添加新策略

编辑 `deploy_autodl.py` 中的 `policies` 列表。

### 自定义镜像

修改 `autodl_config.txt`：
```bash
IMAGE_NAME=your-custom-image
```

## 手动SSH连接

如果需要手动调试SSH：

```bash
# 获取SSH地址
python -c "
from deploy_autodl import AutoDLClient
client = AutoDLClient('your-token')
info = client.get_instance_ssh_info('instance-id')
print(info['host'])
"

# 手动连接
ssh root@<host>

# 手动上传
scp -r morphsim root@<host>:/root/
```

## 安全提示

- API Token已保存在本地，不要泄露
- 实例运行完毕及时释放，避免扣费
- 代码包含敏感数据，注意权限管理