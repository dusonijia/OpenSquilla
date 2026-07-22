#!/usr/bin/env python3
"""XPBD测试 - 简化版，直接运行完整3场景实验"""

import subprocess
import sys
import os

# 改到autodl目录
os.chdir("/Users/du/Library/Application Support/@opensquilla/desktop-electron/opensquilla/state/workspace/eiv-research/projects/R5-EIV-Bench/papers/P3-MorphSim/autodl")

# 直接运行已有的完整实验脚本
proc = subprocess.run(["/usr/bin/python3", "run_v4.py"], capture_output=True, text=True, timeout=600)

print("=== 输出（最后3000字符）===")
print(proc.stdout[-3000:])
if proc.stderr:
    print("=== 错误（最后500字符）===")
    print(proc.stderr[-500:])

sys.exit(proc.returncode)