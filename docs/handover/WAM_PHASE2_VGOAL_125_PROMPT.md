# Phase-2 + vgoal · 125 执行手递（2026-09-09）

> **分支**：`project/phase2-vgoal`（已推 `origin` + `github`）  
> **RUNBOOK**：[`RUNBOOK_phase2_vgoal.md`](RUNBOOK_phase2_vgoal.md)

在 **125** 上执行（需先完成 Cloudflare SSH 登录）。

## 0. 拉分支 + 环境

```bash
cd ~/aerial-wam-v2
git fetch origin project/phase2-vgoal
git checkout project/phase2-vgoal
git pull origin project/phase2-vgoal
git log -1 --oneline

source experiments/aerial/scripts/env_4090.sh

# 兄弟仓（若无则 clone 到 ~/Projects/aerial-vgoal-wam）
test -f ~/Projects/aerial-vgoal-wam/vgoal/tracker.py || \
  git clone <aerial-vgoal-wam-url> ~/Projects/aerial-vgoal-wam

test -f experiments/aerial/rl/artifacts/v4_ac_ckpt_phase2_toward_g_20260905_112006/v4_ac_latest.pt \
  && echo CKPT_OK || echo CKPT_MISSING
```

## 1. V1 短探针（2 路 · 后台）

```bash
cd ~/aerial-wam-v2
source experiments/aerial/scripts/env_4090.sh
mkdir -p logs artifacts/vgoal_traj

TS=$(date +%Y%m%d_%H%M%S)
LOG=logs/wam_vgoal_probe_125_${TS}.log
OUT=artifacts/wam_vgoal_probe_125.json

nohup bash -c "
echo HOST=125 START=\$(date -Iseconds) ARM=vgoal_probe >>$LOG
\$PYTHON_BIN -u -m experiments.aerial.scripts.wam_vgoal_eval \
  --vgoal-repo ~/Projects/aerial-vgoal-wam \
  --annotation artifacts/seen_airsim16_long_routes.json \
  --episodes 2 \
  --cruise-speed 10.0 \
  --tti-coeff 2.5 \
  --max-steps 2000 \
  --planner --planner-horizon 5 \
  --traj-out artifacts/vgoal_traj \
  --out $OUT >>$LOG 2>&1
echo EXIT_CODE=\$? FINISHED_AT=\$(date -Iseconds) >>$LOG
" >/dev/null 2>&1 &

echo PID=\$!
sleep 3
pgrep -af wam_vgoal_eval | grep -v pgrep
tail -20 $LOG
```

粗估：**~30–50 min/路**（max-steps 2000）→ 2 路约 **1–1.5 h**。

## 2. 探针通过后 · 全 16 路

```bash
OUT=artifacts/wam_vgoal_eval_full16_20260909.json
LOG=logs/wam_vgoal_full16_125_$(date +%Y%m%d_%H%M%S).log

nohup bash -c "
\$PYTHON_BIN -u -m experiments.aerial.scripts.wam_vgoal_eval \
  --vgoal-repo ~/Projects/aerial-vgoal-wam \
  --annotation artifacts/seen_airsim16_long_routes.json \
  --episodes 16 \
  --cruise-speed 10.0 \
  --tti-coeff 2.5 \
  --max-steps 2000 \
  --planner --planner-horizon 5 \
  --traj-out artifacts/vgoal_traj \
  --out $OUT >>$LOG 2>&1
echo EXIT_CODE=\$? FINISHED_AT=\$(date -Iseconds) >>$LOG
" >/dev/null 2>&1 &
```

## 3. 可选几何对照（同机串行或另一会话）

```bash
\$PYTHON_BIN -u -m experiments.aerial.scripts.wam_phase2_long_eval \
  --subgoal-source toward_g \
  --cruise-speed 10.0 --tti-coeff 2.5 --max-steps 2000 \
  --planner --planner-horizon 5 \
  --out artifacts/wam_phase2_geom_baseline_125.json
```

## 4. 回报

- `tail -30` 对应 LOG
- `$OUT` 里 `arrival_rate` / `mean_goal_closure` / `severe_collision_rate`
- traj 里 `using_fallback` 占比（若 JSON 有汇总）

填 [`WAM_PHASE2_VGOAL_STATUS.md`](WAM_PHASE2_VGOAL_STATUS.md)。
