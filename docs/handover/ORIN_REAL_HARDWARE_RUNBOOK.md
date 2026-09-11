# RUNBOOK · Orin 真机台架 / 首飞

> **关联**：[`WAM_PHASE2_VGOAL_STATUS.md`](WAM_PHASE2_VGOAL_STATUS.md) · [`RUNBOOK_phase2_vgoal.md`](RUNBOOK_phase2_vgoal.md)  
> **阶段**：仿真 L3 paused（2026-09-11）→ **真机为主战场**

---

## 0. 一句话

**Orin + Pixhawk 6C + C922** 上跑 Phase-2 π 决策栈；台架阶段验证 **相机 + MAVLink + 模型加载**，深度 shield **默认关闭**（域不匹配），感知协议等真机真实场景后再定。

## 1. 硬件与连接

| 组件 | 配置 | 状态（2026-09-10 台架） |
|------|------|-------------------------|
| **Jetson Orin** | `yao@10.229.66.164` | 代码 + venv + 5 ckpt 已同步 |
| **Pixhawk 6C** | USB `/dev/ttyACM0` | heartbeat 正常，DISARMED |
| **Logitech C922** | `/dev/video2`，MJPEG | 推荐；需手动对焦/曝光 |
| **鱼眼 USB** | `/dev/video0` | 不推荐（180° 畸变，需标定） |
| **PyTorch GPU** | Jetson aarch64 wheel | ❌ 未装；**CPU 推理** |

### 1.1 SSH

```bash
ssh yao@10.229.66.164
```

（校园网；密码见团队内部记录。）

### 1.2 仓库布局（Orin）

```bash
~/aerial-wam-v2/                    # project/phase2-vgoal
~/Projects/aerial-vgoal-wam/        # vgoal.* 兄弟仓
~/sim_verify/.venv/                 # Python venv
~/aerial-wam-v2/experiments/aerial/rl/artifacts/   # 5 ckpt（从 125 rsync）
```

### 1.3 Checkpoints（与 125 一致）

| 角色 | 路径 |
|------|------|
| Actor (E2) | `experiments/aerial/rl/artifacts/v4_ac_ckpt_phase2_toward_g_20260905_112006/v4_ac_latest.pt` |
| WM | `experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt` |
| Depth | `experiments/aerial/rl/artifacts/depth_ckpt_p45mid_s8j_20260825/depth_best_holdout_da3_ft_head.pt` |
| Tau | `experiments/aerial/rl/artifacts/tau_ckpt_foe_r60_20260815/tau_foe_calibrator.pt` |
| Routes | `artifacts/seen_airsim16_long_routes.json` |

---

## 2. 能力边界（诚实版）

### ✅ 已在 Orin 验证

1. `~/aerial-wam-v2` + `~/Projects/aerial-vgoal-wam` + venv
2. 5 个 checkpoint 可加载
3. Pixhawk USB heartbeat + OFFBOARD 零速 dry-run（桨叶 off）
4. C922 640×480 采集（对焦/曝光手动调）
5. YOLO 单帧检测（yolov8n，CPU ~1.5–5.7s）
6. Depth 头单帧推理 + 伪彩（CPU ~3.8s，**仅调试**）

### ⚠️ 有代码、待真飞验证

1. `wam_vgoal_deploy` 完整 loop（`--camera 2`，无 `--mock-camera`）
2. OFFBOARD 长时间稳定性
3. vgoal tracker + π 闭环在真实图像上
4. C922 参数 preset 写入 `real_camera.py`（目前每次 `v4l2-ctl` 手动设）

### ❌ 当前不在能力范围

| 项 | 原因 |
|----|------|
| GPU 加速推理 | 需 Jetson 原生 PyTorch wheel |
| 可信绝对深度 / shield 避障 | 训练域为 AirSim 低空前视；24 楼俯视/百米楼群严重偏小 |
| 鱼眼直接去畸变部署 | 需棋盘格标定 |
| 无 GPS 室外绝对导航 | goal 需 `--goal-x/y/z` 或 toward_g fallback |
| AirSim 仿真 | Orin 故意未装 |
| sim 红车/Cart 感知指标 | 资产不可用，已 archived |

### 深度头台架结论（2026-09-10）

| 场景 | 模型输出 | 评价 |
|------|----------|------|
| 24 楼俯视街道 | depth_min ~6 m | 实际 50–80 m+，**不可用** |
| 前视楼群（平视） | p50 ~26 m | 相对结构可参考；前方实际 >100 m，**绝对米数不可信** |
| 台架决策 | — | **禁用 depth shield**；高度用气压计/GPS；水平靠 YOLO+vgoal |

---

## 3. C922 采集 preset（台架）

每次采集前在 Orin 上执行：

```bash
v4l2-ctl -d /dev/video2 --set-ctrl=focus_automatic_continuous=0
v4l2-ctl -d /dev/video2 --set-ctrl=focus_absolute=0      # 近景；远景需扫焦
v4l2-ctl -d /dev/video2 --set-ctrl=auto_exposure=1
v4l2-ctl -d /dev/video2 --set-ctrl=exposure_time_absolute=20   # 外景；暗场景试 40–120
v4l2-ctl -d /dev/video2 --set-ctrl=brightness=90
v4l2-ctl -d /dev/video2 --set-ctrl=gain=0
```

推荐台架参数：`640×480` MJPEG → WAM 内部缩 224。  
1080p 采集可在真机协议稳定后再对齐 `capture_config.py` 默认。

---

## 4. 台架命令阶梯（风险从低到高）

### Stage 1 — 环境自检

```bash
ssh yao@10.229.66.164
cd ~/aerial-wam-v2
git checkout project/phase2-vgoal && git pull
source ~/sim_verify/.venv/bin/activate
python -c "import torch; print(torch.__version__, 'cuda', torch.cuda.is_available())"
python -c "import sys; sys.path.insert(0,'$HOME/Projects/aerial-vgoal-wam'); import vgoal.tracker; print('vgoal OK')"
```

### Stage 2 — 模型 bench load（mock 相机）

```bash
cd ~/aerial-wam-v2
source ~/sim_verify/.venv/bin/activate
python -m experiments.aerial.scripts.wam_vgoal_deploy \
  --mock-camera \
  --vgoal-repo ~/Projects/aerial-vgoal-wam
```

入口脚本已合入本仓：`experiments/aerial/scripts/wam_vgoal_deploy.py`。

### Stage 3 — 感知台架（桨叶 off）

```bash
python -m experiments.aerial.scripts.wam_vgoal_deploy \
  --camera 2 --capture-w 640 --capture-h 480 \
  --vgoal-repo ~/Projects/aerial-vgoal-wam \
  --no-depth-shield
```

目检：YOLO bbox 叠加、goal_rel 打印、无 ARM。

### Stage 4 — MAVLink 控制台架（OFFBOARD · disarmed）

```bash
# 默认即 dry-run：只连 MAVLink + 零速 setpoint 流，不进 OFFBOARD
python -m experiments.aerial.scripts.pixhawk_offboard_hover --port /dev/ttyACM0

# 进 OFFBOARD（仍 disarmed）
python -m experiments.aerial.scripts.pixhawk_offboard_hover \
  --port /dev/ttyACM0 --offboard --warmup-s 5
```

验证 PX4 收到零速 setpoint；桨叶仍 off。

### Stage 5 — 贴地短飞（需 RC + failsafe）

```bash
python -m experiments.aerial.scripts.wam_vgoal_deploy \
  --camera 2 \
  --offboard --arm --run \
  --cruise-speed 2.0 \
  --no-depth-shield \
  --vgoal-repo ~/Projects/aerial-vgoal-wam
```

**前置**：开阔场、RC 手控就绪、QGC failsafe 已配、低速度。

---

## 5. 控制链路

```text
C922 RGB (640×480)
  → resize 224 → WM encode
  → YOLO (640 或 fanout 分支)
  → TargetTracker → goal_rel
  → LatentActorDeployPolicy (Phase-2 E2 ckpt)
  → optional ImaginationPlanner
  → ThreeZoneShield (台架: 关闭或 tau-only)
  → body_delta → MAVLink OFFBOARD velocity NED @ 5–30 Hz
  → Pixhawk 6C → 电机
```

- 只发 **速度 + yaw rate**，不发位置 setpoint
- 依赖 PX4 `LOCAL_POSITION_NED` + EKF；室外需 GPS 原点稳定

---

## 6. 与 125 仿真分工

| | **125 AirSim** | **Orin 真机** |
|---|---|---|
| 用途 | Phase-2 / vgoal **指标 eval**（几何 + GT 烟测） | **边缘 deploy / 台架 / 试飞** |
| 感知 GT | AirSim depth / GT detector | 仅 YOLO + 真实相机 |
| 控制 | AirSim API | MAVLink → Pixhawk |
| GPU | 4090 | CPU fallback |
| L3 视觉验收 | ⏸ paused（sim 资产无效） | **主战场** |

---

## 7. 真机感知协议（待首飞后填写）

台架采集稳定后，在真机场景定义：

| 项 | 待定 |
|----|------|
| 目标类型 | 真实车辆 / 标志物 / custom 类 |
| 检测器 | YOLO COCO / open_vocab / custom fine-tune |
| 评测距离带 | 建议主指标 10–25 m（人眼可确认） |
| spawn / 起飞点 | 开阔场 GPS 原点 + 相对 goal |
| 成功判据 | `goal_from=vision` + `arrived` / `arrived_follow` |
| 采集分辨率 | 640×480 台架 vs 1080p 飞行 |

---

## 8. 代码同步（Mac → Orin）

```bash
# 从 Mac（在项目根目录）
rsync -avz --exclude '.git' --exclude 'artifacts' \
  ~/Projects/aerial-wam-v2/ yao@10.229.66.164:~/aerial-wam-v2/

# 或仅推脚本层
scp -r experiments/aerial/scripts/vgoal_*.py \
  yao@10.229.66.164:~/aerial-wam-v2/experiments/aerial/scripts/
```

同步后 Orin 上：

```bash
cd ~/aerial-wam-v2 && git status   # 确认分支与改动
source ~/sim_verify/.venv/bin/activate
```

---

## 9. 变更记录

| 日期 | 内容 |
|------|------|
| 2026-09-09 | Orin 初装：`project/phase2-vgoal` + venv + ckpt rsync |
| 2026-09-10 | C922 台架；深度头域不匹配定性；Pixhawk dry-run |
| 2026-09-11 | 仿真结案；本 RUNBOOK 建立；真机为主战场 |
