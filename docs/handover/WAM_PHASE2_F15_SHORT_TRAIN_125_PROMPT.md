# 125 Agent：F15 效率短训（H100）→ `.110` 复测

> **日期**：2026-09-01  
> **DECLARE**：`docs/handover/WAM_PHASE2_F15_EFFICIENCY_DECLARE_20260901.md`  
> **H100**：`ssh -i ~/.ssh/id_ed25519_h100 -p 31126 a25689@10.239.121.22`（经 125；Mac / `.110` 不直连）  
> **评测**：`.110` · `ssh a26125-110-public` · **禁止碰 125 AirSim/GPU 长评**  
> **Deadline**：拉起起算 **≤3h** 必须结束训（到点杀、用 latest 评，或写 blocker）

---

## 0. 背景（勿重跑）

* assist / heading_reentry 均 **FAIL**（R05 仍 yaw-dead + idle）  
* 下一步 = **step_e warm-start + F15 `w_eff_*` 想象补训**  
* 主航道仍锁：`step_e` + meter + Subgoal + planner + ThreeZone；assist 默认 OFF

---

## 1. 同步代码 → H100

至少：

```text
reward.py  imagination.py  train_rl.py  train_v4_ac.py
configs/aerial_rl.yaml
```

```bash
H100=(ssh -i ~/.ssh/id_ed25519_h100 -o BatchMode=yes -o ConnectTimeout=20 -p 31126 a25689@10.239.121.22)
# 从 125 上 aerial-wam-v2（或已 sync 的 WT）tar/scp 到 H100
```

确认底座存在：

```bash
"${H100[@]}" 'ls ~/aerial-wam-v2/experiments/aerial/rl/artifacts/v4_ac_ckpt_step_e_20260828/v4_ac_latest.pt
ls ~/aerial-wam-v2/experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt
ls -d ~/aerial-wam-v2/experiments/aerial/rl/artifacts/dataset_v0_d_full_20260828'
```

---

## 2. H100 短训

```bash
"${H100[@]}" 'bash -lc "
cd ~/aerial-wam-v2
source experiments/aerial/scripts/env_h100.sh
mkdir -p artifacts experiments/aerial/rl/artifacts/v4_ac_ckpt_f15_eff_ft_20260901
nohup python -m experiments.aerial.rl.train_v4_ac \
  --iters 300 \
  --device cuda \
  --dynamics torch \
  --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt \
  --ckpt-dir experiments/aerial/rl/artifacts/v4_ac_ckpt_f15_eff_ft_20260901 \
  --init-actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_step_e_20260828/v4_ac_latest.pt \
  --annotation artifacts/seen_airsim16_m1a20.json \
  --backend mock \
  --skip-collect \
  --dataset experiments/aerial/rl/artifacts/dataset_v0_d_full_20260828 \
  --w-eff-idle 0.2 \
  --w-eff-heading 0.3 \
  --w-eff-strafe 0.15 \
  > artifacts/train_v4_ac_f15_eff_ft_20260901.log 2>&1 &
echo TRAIN_PID=\$!
"'
```

**开训验收（日志）**：

* `F15 reward weights: w_eff_strafe=0.15 w_eff_heading=0.3 w_eff_idle=0.2`  
* `warm-started actor from ...step_e...`  
* `goal_feat_mode=meter` · `condition_on_goal=True`

---

## 3. 拉 ckpt → `.110` 复测

```bash
# H100 → 125 → .110（或直 rsync 到 .110 若密钥允许）
# 目标路径：
#   ~/aerial-wam-v2/experiments/aerial/rl/artifacts/v4_ac_ckpt_f15_eff_ft_20260901/v4_ac_latest.pt
```

在 **`.110`**：

```bash
source ~/aerial-wam-v2/experiments/aerial/scripts/env_4090.sh
cd ~/aerial-wam-v2
OUT=artifacts/videos/wam_phase2_f15_eff_ft_probe_20260901
mkdir -p "$OUT" artifacts
nohup "$PYTHON_BIN" -m experiments.aerial.scripts.wam_phase2_offtrack_probes \
  --routes 4,0 --arms wam --max-steps 300 \
  --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_f15_eff_ft_20260901/v4_ac_latest.pt \
  --out-dir "$OUT" \
  > artifacts/wam_phase2_f15_eff_ft_probe_20260901.log 2>&1 &
```

对照：`wam_phase2_f15_strafe_baseline_20260901`。assist **必须 OFF**。

---

## 4. 回报格式

| 项 | 填 |
|----|----|
| 实际 iters | |
| 想象末 `mean_return` / `mean_progress` | |
| R05/R01 ds · cte_end · idle · cos30 vs baseline | |
| Verdict | PASS / FAIL / BLOCKED |
| 下一刀（一句） | |

**禁止**：默认 assist 开；覆盖 step_e；未看 R05 就抬全量训或改 safety.py。
