# RUNBOOK · Phase-2 + vgoal（视觉目标叠在 close 栈上）

> **分支**：`project/phase2-vgoal`  
> **基线 tag**：`phase2-pass-20260908`（几何 `toward_g` SR=86.7% SCR=6.7%）  
> **兄弟仓**：[`aerial-vgoal-wam`](../../../aerial-vgoal-wam)（本机默认 `~/Projects/aerial-vgoal-wam`）  
> **活页**：[`WAM_PHASE2_VGOAL_STATUS.md`](WAM_PHASE2_VGOAL_STATUS.md)  
> **真机**：[`ORIN_REAL_HARDWARE_RUNBOOK.md`](ORIN_REAL_HARDWARE_RUNBOOK.md)

---

## 0. 仿真结案（2026-09-11）

| 层级 | 仿真状态 |
|------|----------|
| L1 Phase-2 几何导航 | ✅ closed（`phase2-pass-20260908`） |
| L2 vgoal 接线 M1–M4 | ✅ 代码合入；GT 烟测可验轨迹 |
| L3 产品视觉导航 | ⏸ **paused** — sim 红车/Cart 资产不可用 |

**不再在 125 上投入**：open_vocab 红车 spawn 池、Cart YOLO、sim flight SR 作为 L3 gate。  
**下一阶段**：Orin 真机采集与实测（见真机 RUNBOOK）。

红车/Cart 旁线脚本保留在 `experiments/aerial/scripts/vgoal_red_car_*.py`，标 **archived**，仅供查阅。

---

## 0b. 一句话

**Phase-2 close 的大脑不动**；只把 `goal_rel` 的来源从「标注世界坐标」换成 **检测器 + 跟踪器**。仿真先用 GT 投影检测器；部署换 YOLO。跟踪丢失时 **回落 `toward_g`**，避免悬停死锁。

## 1. 架构

```text
RGB
  → Visual detector (GT in sim | YOLO deploy)
  → TargetTracker (EMA + dead-reckoning + occlusion timeout)
  → goal_rel [d_fwd, d_left, d_up, dist]   ← 与 Phase-2 π 合同一致
  → LatentActorDeployPolicy (step_e / E2 ckpt)
  → optional ImaginationPlanner
  → TTI ThreeZoneShield (tti_coeff=2.5)
  → env.step

SEARCHING（无检测记忆）:
  → M3 默认: AreaSearchPlanner 割草机/螺旋 → goal_rel → π
  → legacy scan: 慢速前进 + 偏航
  → 可选 fallback: clip_toward_goal(pos, G, r_m)  （消融用）
```

**明确不做（本 project）**：
- Phase-3 室内混采 / 双 profile FT
- 重训 π 以「看目标」为主（先 eval 接线）
- 用 vgoal 成绩宣称几何 Phase-2 已 re-close（须分臂报表）

## 2. 前置

### 2.1 仓库

```bash
cd ~/aerial-wam-v2
git fetch --all
git checkout project/phase2-vgoal
```

### 2.2 兄弟仓 vgoal

```bash
# 须存在且可 import vgoal.*
ls ~/Projects/aerial-vgoal-wam/vgoal/tracker.py
```

评测脚本通过 `--vgoal-repo` 注入 `sys.path`。

### 2.3 125 / 4090 环境

```bash
cd ~/aerial-wam-v2
source experiments/aerial/scripts/env_4090.sh   # AIRSIM_CAMERA / VEHICLE 等
```

### 2.4 Checkpoints（与 Phase-2 close 一致）

| 角色 | 路径 |
|------|------|
| Actor (E2) | `experiments/aerial/rl/artifacts/v4_ac_ckpt_phase2_toward_g_20260905_112006/v4_ac_latest.pt` |
| WM | `experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt` |
| Depth (shield) | `experiments/aerial/rl/artifacts/depth_ckpt_p45mid_s8j_20260825/depth_best_holdout_da3_ft_head.pt` |
| Tau | `experiments/aerial/rl/artifacts/tau_ckpt_foe_r60_20260815/tau_foe_calibrator.pt` |

## 3. 评测命令

### 3.1 几何对照（Phase-2 close 复现臂）

```bash
python -m experiments.aerial.scripts.wam_phase2_long_eval \
  --subgoal-source toward_g \
  --annotation artifacts/seen_airsim16_long_routes.json \
  --cruise-speed 10.0 \
  --tti-coeff 2.5 \
  --max-steps 2000 \
  --planner --planner-horizon 5 \
  --out artifacts/wam_phase2_geom_baseline.json
```

### 3.2 视觉目标主臂（M2 · 单目纯视觉）

```bash
python -m experiments.aerial.scripts.wam_vgoal_eval \
  --vgoal-repo ~/Projects/aerial-vgoal-wam \
  --detector yolo \
  --target-class car \
  --annotation artifacts/seen_airsim16_long_routes.json \
  --cruise-speed 10.0 \
  --tti-coeff 2.5 \
  --max-steps 2000 \
  --planner --planner-horizon 5 \
  --traj-out artifacts/vgoal_traj \
  --out artifacts/wam_vgoal_eval_result.json
```

### 3.3 区域搜寻（M3 · AreaSearchPlanner）

SEARCHING 阶段默认 **割草机** 覆盖 spawn 周围 `--search-area-half-m`（默认 40 m）方框；每步仍跑检测器，见到目标即切 TRACKING。

```bash
# 开发期可用 GT 验证搜寻轨迹（不算产品 pass）
python -m experiments.aerial.scripts.wam_vgoal_eval \
  --vgoal-repo ~/aerial-vgoal-wam \
  --detector gt --gt-nearest-scene-object --gt-scene-pattern "Car.*" \
  --search-pattern lawnmower --search-area-half-m 35 \
  --routes 0,1 --max-steps 400 \
  --traj-out artifacts/vgoal_traj_m3_smoke \
  --out artifacts/wam_vgoal_m3_smoke.json

# 螺旋重搜（丢锁后仍由 tracker SEARCHING 触发）
python -m experiments.aerial.scripts.wam_vgoal_eval \
  --search-pattern spiral --search-spiral-radius-m 30 ...

# 回退旧行为：原地慢速前进 + 偏航
python -m experiments.aerial.scripts.wam_vgoal_eval \
  --search-pattern scan ...
```

### 3.4 抵近/伴飞（M4 · DynamicTargetTracker）

锁定目标后由 EKF 估计目标状态；远距 **INTERCEPTING**，进入 `--intercept-dist-m` 内切 **FOLLOWING**，站位点默认目标后方 6 m、上方 3 m。

```bash
python -m experiments.aerial.scripts.wam_vgoal_eval \
  --vgoal-repo ~/aerial-vgoal-wam \
  --follow-mode standoff \
  --standoff-dist-m 6 --standoff-height-m 3 --intercept-dist-m 12 \
  --follow-success-dist-m 4 \
  --detector gt --gt-nearest-scene-object --gt-scene-pattern "Car.*" \
  --search-pattern lawnmower --routes 0 --max-steps 400 \
  --out artifacts/wam_vgoal_m4_smoke.json
```

开发期仍用 GT；产品验收需 `goal_from=vision` + `arrived_follow=true`。

语义 / 开放词表：

```bash
  --detector open_vocab --visual-prompt "red car"
```

短探针：`--episodes 2` 或 `--routes 0,1`

### 3.2b 户外车目标探针（spawn-only · 125）

**问题**：`seen_airsim16_long_routes` 是 200–500 m 导航走廊，YOLO 几乎看不到车（0909 fanout：`det_frac≈0.3%`）。  
**做法**：室内 pillar 同款——annotation **只定 spawn**，车在场景里已有（`env_airsim_16` 静态车），**不能**代码 spawn 车辆。

**Step 1 — YOLO 可见性快检**（无 π/WM，~30s）：

```bash
cd ~/aerial-wam-v2 && source experiments/aerial/scripts/env_4090.sh
python -m experiments.aerial.scripts.vgoal_yolo_spawn_probe \
  --vgoal-repo ~/aerial-vgoal-wam \
  --annotation experiments/aerial/phase2-vgoal/airsim16_car_spawn_probe.json \
  --routes 0,1,2,3 \
  --yaw-sweep-deg 45 --yaw-step-deg 15 \
  --out artifacts/yolo_spawn_probe.json
```

看 `artifacts/yolo_spawn_snapshots/*.jpg` 与 JSON `hit_rate`。若全 miss，在 UE 里飞到路边有车处，记下 pose 写入 JSON（或调 z/yaw）。

**Step 2 — 短程 TRACKING 探针**（`hit_rate>0` 的 spawn 再跑）：

```bash
TS=$(date +%Y%m%d_%H%M%S)
nohup $PYTHON_BIN -u -m experiments.aerial.scripts.wam_vgoal_eval \
  --vgoal-repo ~/aerial-vgoal-wam \
  --detector yolo --target-class car \
  --annotation experiments/aerial/phase2-vgoal/airsim16_car_spawn_probe.json \
  --routes 0,1,2,3 \
  --capture-w 640 --capture-h 480 --fanout-rgb \
  --yolo-conf 0.2 --search-z-hold-mode auto \
  --cruise-speed 10.0 --tti-coeff 2.5 \
  --max-steps 400 \
  --planner --planner-horizon 5 \
  --traj-out artifacts/vgoal_traj \
  --out artifacts/wam_vgoal_car_probe_${TS}.json \
  > artifacts/wam_vgoal_car_probe_${TS}.log 2>&1 &
```

**验收**：`det_frac > 10%` 且 `vision_frac > 5%` 才说明视觉栈在工作；再扩到 approach/follow。

**GT 管线烟测**（debug，非产品）：

```bash
python -m experiments.aerial.scripts.wam_vgoal_eval \
  --detector gt --routes 0,1 --max-steps 200 \
  --annotation experiments/aerial/phase2-vgoal/airsim16_car_spawn_probe.json \
  --out artifacts/wam_vgoal_gt_smoke.json
```

### 3.3 关键 CLI

| 参数 | 默认 | 说明 |
|------|------|------|
| `--detector` | `yolo` | `yolo` / `open_vocab` / `mock` / `gt`(debug) |
| `--target-class` | `car` | YOLO COCO 类过滤 |
| `--visual-prompt` | — | 开放词表 prompt |
| `--vgoal-repo` | `~/Projects/aerial-vgoal-wam` | 兄弟仓路径 |
| `--capture-w/h` | 1920×1080 | AirSim 原生采集（fan-out 前；`env_4090.sh` 默认） |
| `--search-pattern` | `lawnmower` | M3：`lawnmower` / `spiral` / `scan` |
| `--follow-mode` | `static` | M4：`standoff` 启用 DynamicTargetTracker |
| `--fanout-rgb` | **ON** | `rgb_yolo`/`rgb_vio` 原生 · `rgb`→224 WAM |
| `--wam-encode-size` | 224 | π/WM 分支 |
| `--search-fwd-speed` | **0.2** slow | SEARCHING 前进 (m/step)；`--search-at-cruise` 才用 cs |
| `--search-z-hold-mode` | **auto** | 定高：spawn z 夹在 20–40 m；`off` 关闭 |
| `--search-z-gain` | 1.0 | 定高 P 增益 |
| `--visual-toward-g` | **ON** | TRACKING：视觉 `G` → `TowardGoalIntent` → π |
| `--toward-g-r-m` | 25 | 视觉 G 裁剪半径 (m) |
| `--tracker-min-confidence` | yolo_conf | 与 YOLO 对齐（默认 `max(0.15, min(0.5, yolo_conf))`） |
| `--yolo-conf` | 0.25 | YOLO 检测阈值 |
| `--search-yaw-rate` | 0.314 | SEARCHING 偏航 (rad/step) |
| `--fallback-toward-g` | **OFF** | 消融：SEARCHING 时几何 toward_g |
| `--detector gt` | — | **仅 debug**，非产品路径 |

`env_4090.sh` 默认导出 `AIRSIM_FANOUT_RGB=1` · `AERIAL_CAPTURE_W/H=1920/1080` · `AERIAL_YOLO_MODEL=yolov8m.pt` · `AERIAL_YOLO_IMGSZ=1280`。
CaptureSettings 须与 `--capture-w/h` 一致（勿用 224 outdoor settings 跑 YOLO）。

## 4. 验收阶梯（本 project）

| 步 | 内容 | 过门 |
|----|------|------|
| **V0** | 分支 + 脚本 + RUNBOOK | **本 commit** |
| **V1** | `wam_vgoal_eval` 16 路跑通无 crash | JSON + traj 落盘 |
| **V2** | 与几何臂同协议对比 | SR/closure 不系统性劣于几何（允许略低；须解释 fallback 占比） |
| **V3** | GT 检测器 → YOLO 检测器 | 部署路径；仿真可仍用 GT 对照 |

**禁止**：用几何臂 SR=86.7% 直接宣称 vgoal 已过门。

## 5. 报表字段（vgoal 特有）

每步 traj JSONL 建议含：`tracker_state`, `det_hit`, `using_fallback`, `intent_dev_deg`（若有）。

汇总 JSON 应带 `protocol_version`, `vgoal_repo`, `fallback_toward_g`.

## 6. 与 Phase-3 分叉

- **本 project**：户外 · 视觉目标 · 不重训优先  
- **phase3/unified-outdoor-indoor**：户外+室内 · 混采 FT · vgoal 脚本仅为附带

冲突时：本 RUNBOOK 管 vgoal；Phase-2 长航程 RUNBOOK 管几何 close；Phase-3 RUNBOOK 不管 vgoal 验收。

## 7. 变更记录

| 日期 | 内容 |
|------|------|
| 2026-09-09 | 建立 `project/phase2-vgoal`：起自 `phase2-pass-20260908` + cherry-pick `wam_vgoal_eval.py` |
| 2026-09-10 | M3/M4 合入；1080p fanout + yolov8m 默认（125 验证） |
| 2026-09-11 | **仿真结案**：L3 paused；红车/Cart 旁线 archived；真机 RUNBOOK 建立 |
