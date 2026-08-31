# 125 Agent：Phase-2 全签 R2（3h H100 窗口 · 修想象 return → 复评）

> **日期**：2026-08-29（晚）  
> **强制 workspace**：`/home/yao/workspaces/aerial-wam-v2-phase2`  
> **Indoor**：禁止动 `/home/yao/aerial-indoor-wam`  
> **H100（当前）**：`ssh -i ~/.ssh/id_ed25519_h100 -p 31126 a25689@10.239.121.22`  
>   （旧 `Host h100-25`→`.25` 勿依赖；Mac 不直连）  
> **Deadline**：本机拉起起算 **≤3 小时** 必须结束 H100 训（到点杀训、用最新 ckpt 评，或写 blocker）  
> **禁止**：Docking / 往返 / 关罩 / 开 escape / 放宽 3 m / 用旧 `step_e` 冒充 / 改门限凑 PASS

---

## 0. R1 已封卷（勿重跑同配方）

| 项 | 值 |
|----|-----|
| DECLARE | `docs/handover/WAM_PHASE2_SIGNOFF_DECLARE_20260829.md` |
| Verdict | **FAIL** · SR=0% · SCR=25% · SPL=0% · ρ̄=56.6% · IR=25% |
| ckpt | `v4_ac_ckpt_phase2_gnorm_20260829` · `condition_on_goal=True` · in_dim=1540 |
| 阻塞 | 想象 `mean_return≈−63`（Step E 同语料曾 **+10.79**）→ π 弱 |

**本回合 = R2**：在 3h 内把想象 return 拉回正域附近，再 16 路；**禁止**无 delta 复跑 R1。

---

## 1. 假设与 delta（冻结）

R1 失败主因：**`w_collision=10` × 近恒定 `p_coll≈0.5` → 每步 −5 税淹没 progress**，g_norm 本身不是唯一元凶。

| 项 | R2 动作 |
|----|---------|
| 训练 | **从零** AC；`--w-collision 1.0`（相对 yaml 10.0）；iters **500**（若 90min 仍未完可砍到用当前 latest） |
| ckpt-dir | **新目录** `v4_ac_ckpt_phase2_gnorm_r2_20260829`（勿覆盖 R1） |
| 语料 / WM | 同 R1：`dataset_v0_d_full_20260828` + `wm_step_3500.pt` |
| 评测 | 125 · 16 路 native · **cruise=10**（与 R1 可比）· 动态罩若已合入可保留 |

若开训前 10min 诊断证明 `p_coll` 已有区分（std 大、gap>0.05）且 return 负主因是别的 → 仍用 `w_collision=1.0` 完成本窗口对照，结果写进 DECLARE。

---

## 2. 步骤

### 2.0 杀旧作业

```bash
# 勿杀 indoor；可杀卡在旧 h100-25 的全签 agent / 残留 long_eval
pgrep -af 'wam_phase2_long_eval|train_v4_ac|WAM_PHASE2_SIGNOFF' | head
source /home/yao/aerial-wam-v2/experiments/aerial/scripts/env_4090.sh
export PATH="$HOME/.local/bin:$PATH"
H100=(ssh -i ~/.ssh/id_ed25519_h100 -o BatchMode=yes -o ConnectTimeout=20 -p 31126 a25689@10.239.121.22)
```

### 2.1 同步代码 → H100

至少同步：`train_v4_ac.py`（含 `--w-collision`）、`goal_features.py`、`actor_critic.py`、`imagination.py`、`reward.py`。

```bash
# 从 WT 或 MAIN → H100（示例）
rsync -avz -e 'ssh -i ~/.ssh/id_ed25519_h100 -p 31126' \
  ~/workspaces/aerial-wam-v2-phase2/experiments/aerial/rl/train_v4_ac.py \
  ~/workspaces/aerial-wam-v2-phase2/experiments/aerial/rl/goal_features.py \
  ~/workspaces/aerial-wam-v2-phase2/experiments/aerial/rl/actor_critic.py \
  ~/workspaces/aerial-wam-v2-phase2/experiments/aerial/rl/imagination.py \
  ~/workspaces/aerial-wam-v2-phase2/experiments/aerial/rl/reward.py \
  a25689@10.239.121.22:~/aerial-wam-v2/experiments/aerial/rl/
```

### 2.2（可选·≤10min）p_coll 快诊

```bash
"${H100[@]}" 'bash -lc "
cd ~/aerial-wam-v2 && source experiments/aerial/scripts/env_h100.sh
# 若有 wam_imagine_coll_rank / 短脚本：记 median gap；无则跳过开训
"'
```

### 2.3 H100 重训（主路径）

```bash
"${H100[@]}" 'bash -lc "
cd ~/aerial-wam-v2
source experiments/aerial/scripts/env_h100.sh
mkdir -p artifacts experiments/aerial/rl/artifacts/v4_ac_ckpt_phase2_gnorm_r2_20260829
nohup python -m experiments.aerial.rl.train_v4_ac \
  --iters 500 \
  --device cuda \
  --dynamics torch \
  --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt \
  --ckpt-dir experiments/aerial/rl/artifacts/v4_ac_ckpt_phase2_gnorm_r2_20260829 \
  --annotation artifacts/seen_airsim16_m1a20.json \
  --backend mock \
  --skip-collect \
  --dataset experiments/aerial/rl/artifacts/dataset_v0_d_full_20260828 \
  --w-collision 1.0 \
  > artifacts/train_v4_ac_phase2_gnorm_r2_20260829.log 2>&1 &
echo TRAIN_PID=\$!
"'
```

**验收**：日志含 `w_collision` 生效痕迹或开训后 `mean_return` 明显好于 −63；ckpt `condition_on_goal=True`；actor in_dim=1540。

**3h 到点**：若未满 500，停训，用目录内最新 `v4_ac_latest.pt`（若有）评测，DECLARE 写明实际 iters。

### 2.4 拉回 125 + 16 路

```bash
scp -i ~/.ssh/id_ed25519_h100 -P 31126 \
  a25689@10.239.121.22:~/aerial-wam-v2/experiments/aerial/rl/artifacts/v4_ac_ckpt_phase2_gnorm_r2_20260829/v4_ac_latest.pt \
  ~/aerial-wam-v2/experiments/aerial/rl/artifacts/v4_ac_ckpt_phase2_gnorm_r2_20260829/
# 同步到 WT 同路径

cd ~/aerial-wam-v2
source experiments/aerial/scripts/env_4090.sh
# 确认 AirSim :41451；无冲突 eval
nohup $PYTHON_BIN experiments/aerial/scripts/wam_phase2_long_eval.py \
  --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt \
  --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_phase2_gnorm_r2_20260829/v4_ac_latest.pt \
  --annotation artifacts/seen_airsim16_long_routes.json \
  --cruise-speed 10.0 \
  --planner --planner-horizon 5 \
  --max-steps 1000 \
  --out artifacts/wam_phase2_signoff_r2_result_20260829.json \
  > artifacts/wam_phase2_signoff_r2_20260829.log 2>&1 &
echo EVAL_PID=\$!
```

### 2.5 DECLARE R2

写：`docs/handover/WAM_PHASE2_SIGNOFF_R2_DECLARE_20260829.md`

含：H100 主机 `.22`、`--w-collision 1.0`、实际 iters、想象 mean_return vs R1、16 路 SR/SCR/SPL/ρ̄/IR、verdict、vs R1 对照表。同步副本到 `~/aerial-wam-v2/docs/handover/`。

---

## 3. 完成回复

- TRAIN：ckpt · w_collision · mean_return · iters  
- 16 路：SR/SCR/SPL/Prog/IR + verdict（相对 R1）  
- DECLARE 路径  
- 若仍 FAIL：下一刀（一句；禁止关罩）

---

## 纪律债（已认）

开训前应落盘本文件；实际先训后补 — 见 [`WAM_PHASE2_STATUS_20260829.md`](WAM_PHASE2_STATUS_20260829.md)。
