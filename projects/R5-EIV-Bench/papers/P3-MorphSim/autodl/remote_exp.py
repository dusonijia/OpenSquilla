#!/usr/bin/env python3
"""MorphSim远程实验脚本 - 带完整错误捕获

这个脚本在GPU实例上运行，结果写入/root/results.json
无论成功还是失败，都会写入结果文件（包含错误信息）
"""
import sys, os, json, traceback, time

RESULT_FILE = "/root/results.json"

def write_result(data):
    """无论成功失败都写入结果文件"""
    with open(RESULT_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"[RESULT] Written to {RESULT_FILE}")

def main():
    print("=== MorphSim实验开始 ===", flush=True)
    
    try:
        # Step 1: 安装依赖
        print("[1/5] 安装mujoco...", flush=True)
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "mujoco", "-q"])
        print("  mujoco安装完成", flush=True)
        
        # Step 2: 导入
        print("[2/5] 导入MorphSim...", flush=True)
        sys.path.insert(0, "/root")
        from morphsim.core.engine import MorphSimEngine, SimConfig
        from morphsim.core.vehicle import MorphableVehicle, MorphMode
        from morphsim.scenarios.loader import ScenarioLoader
        from morphsim.baselines.policies import RigidPolicy, HeuristicPolicy
        print("  导入成功", flush=True)
        
        # Step 3: 加载场景
        print("[3/5] 加载场景...", flush=True)
        loader = ScenarioLoader()
        scenarios = loader.list_scenarios()
        print(f"  场景数: {len(scenarios)}", flush=True)
        
        # 只跑3个场景
        target_scenarios = ["A-01", "B-01", "C-01"]
        policies = {
            "Rigid": RigidPolicy(),
            "Heuristic": HeuristicPolicy(),
            "PPO": RigidPolicy(),  # placeholder
            "DiffOpt": HeuristicPolicy(),  # placeholder
        }
        
        N_STEPS = 200
        results = {}
        
        # Step 4: 跑实验
        print("[4/5] 开始实验...", flush=True)
        for scn_id in target_scenarios:
            print(f"\nSCN {scn_id}:", flush=True)
            results[scn_id] = {}
            
            spec = loader.get(scn_id)
            print(f"  场景名: {spec.name}", flush=True)
            
            for pol_name, policy in policies.items():
                print(f"  策略 {pol_name}...", flush=True)
                
                try:
                    # 创建引擎
                    config = SimConfig(dt=0.01, n_substeps=4)
                    engine = MorphSimEngine(config)
                    
                    # 创建车辆
                    vehicle = MorphableVehicle(
                        mode=MorphMode.STANDARD,
                        wheelbase=2.8,
                        track_width=1.6,
                        mass=1500.0,
                    )
                    vehicle._init_rigid_solver = lambda v=vehicle: None  # skip init
                    vehicle._init_deformable_solver = lambda v=vehicle: None
                    
                    engine.load_vehicle(vehicle)
                    engine.load_scenario(spec)
                    engine.reset()
                    
                    # 跑200步
                    positions = []
                    rewards = []
                    energies = []
                    
                    for step in range(N_STEPS):
                        action = policy.act(engine._state)
                        state, reward, done, info = engine.step(action)
                        pos_x = float(state.pos[0]) if hasattr(state, 'pos') else 0.0
                        positions.append(pos_x)
                        rewards.append(float(reward))
                        energies.append(float(info.get("morph_energy", 0.0)))
                        
                        if step % 50 == 0:
                            print(f"    step {step}/{N_STEPS} pos={pos_x:.4f}", flush=True)
                        
                        if done:
                            print(f"    提前结束 step={step}", flush=True)
                            break
                    
                    final_pos = float(positions[-1]) if positions else 0.0
                    total_reward = sum(rewards)
                    avg_energy = sum(energies) / len(energies) if energies else 0.0
                    
                    results[scn_id][pol_name] = {
                        "final_position": [final_pos, 0.0, 0.0],
                        "total_reward": total_reward,
                        "avg_morph_energy": avg_energy,
                        "steps_completed": len(positions),
                        "positions_sample": positions[::20],  # 每20步采样
                    }
                    print(f"    完成: pos={final_pos:.4f} reward={total_reward:.4f}", flush=True)
                    
                except Exception as e:
                    err_msg = f"{type(e).__name__}: {str(e)}"
                    traceback_str = traceback.format_exc()
                    print(f"    ❌ 失败: {err_msg}", flush=True)
                    print(traceback_str, flush=True)
                    results[scn_id][pol_name] = {
                        "error": err_msg,
                        "traceback": traceback_str[-500:],  # 最后500字符
                        "steps_completed": 0,
                    }
        
        # Step 5: 写结果
        print(f"\n[5/5] 写入结果...", flush=True)
        write_result({
            "status": "completed",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "scenarios": target_scenarios,
            "policies": list(policies.keys()),
            "n_steps": N_STEPS,
            "results": results,
        })
        print("=== 实验完成 ===", flush=True)
        
    except Exception as e:
        # 捕获任何未处理的异常
        err_msg = f"{type(e).__name__}: {str(e)}"
        traceback_str = traceback.format_exc()
        print(f"\n❌ 致命错误: {err_msg}", flush=True)
        print(traceback_str, flush=True)
        write_result({
            "status": "failed",
            "error": err_msg,
            "traceback": traceback_str,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        sys.exit(1)

if __name__ == "__main__":
    main()
