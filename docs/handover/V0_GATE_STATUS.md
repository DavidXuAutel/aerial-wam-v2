# V0 Gate 状态活文档

> **用途**:`_v0_gate --merge` 到底还差什么,一处说清。**每次 gate 相关动作后必须更新本文件**(这是 Claude 会话间遗忘的补丁 —— Mac 侧 artifacts/ 无任何 emit JSON,历史结果全在 H100,不写这里就丢)。
> **权威性**:阈值以 frozen spec §4.1 为唯一真相源;信号现状以总 RUNBOOK §2 + 本文件为准。本文件**不新建阈值**。
> **关联**:总 RUNBOOK `experiments/aerial/RUNBOOK_v0.md`(顶层入口 + 文档地图)、方案评估报告 `2026-08-12-v2-plan-risk-assessment.md`。

---

## 1. 一句话结论(2026-08-12)

**四信号从未在「同一 depth head + 一次 merge」下合拢过。** 各信号在不同时间/机器/ckpt 上分别通过,但 `_v0_gate --merge` 要求所有 signal 的 verdict JSON 并存且全 `ok=true`(`_v0_gate.py:1260` `all_ok = all(v["ok"] is True ...)`)→ **merge 从未跑成**。

---

## 2. 四信号:还差什么

| 信号 | 判据(§4.1) | 最后已知结果 | **还差什么** |
|---|---|---|---|
| **①a–c** | loss↓≥2% / recon 不劣 / min entropy-frac ≥0.10 | 🟡 dry-run 数字**三条全过且余量量级**(16.80→1.49 / 0.3245→0.0282 / min_ent 0.4368),**但语料实质失格**(dt-desync,靠 `--allow-v0-desync` 放行 → §3.3) | **重采合格语料 + 重跑**(用户拍板);或先用 `dataset_v1_rgb`(8 Hz,过守卫)出一份合格日志。根因已修(§3.4)。**V0 唯一测 RSSM 的信号,不可砍** |
| **①d** | AbsRel ≤0.30 | ✅ head A 0.132(代表)/0.167(approach OOD);✅ **head B local 0.0483**(晚⁷) | **无 —— 已在 head B 通过,不再跑**(用户拍板 2026-08-12) |
| **②** | N=16;progress ≥random+5.0 ∨ final_dist ≤random−3.0 | ✅ 决定性通过(多次:24.13/−5.11、11.18/−3.75 等) | 仅 **n<16**(已决定不追,见 §4) |
| **③** | reproj median 相对误差 ≤0.25;有效窗 ≥8 | ✅ head A 0.05–0.12(余量对 0.25 不宽) | **head B 上未跑** ← 唯一 depth 侧 gap(理由见 §3A) |
| **④** | before ≥0.50;ratio ≤0.80 | ✅ head B 稳健 PASS ×3(晚¹⁸:ratio 0.13/0.23/0.12) | 仅 **n<16** + `before=1.0` 属合法空过 |

### 2.1 核心 gap:head 一致性

- ①③ 的权威 verdict 用 **head A** = `depth_ckpt_da3_20260810`
- ④ 的 shield predictor 用 **head B** = `depth_ckpt_da3_near_20260811`(near_weight=3.0)
- **部署只用一个 head → merge 必须同 ckpt**

→ **只需在 head B 上补跑 `--signals 3`**(①d 已在 head B 通过,见上表)。
→ 意义(2026-08-12 与用户确认):head B 的 `near_weight=3.0` 是**修复真实近场缺陷**(晚⁶ 实锤:1.5m 墙读成 6.415m,`P(trigger)=0`,且各 GT 箱 D̂ 分布重叠 ⇒ 调阈值救不了),**不是妥协**。
→ **为什么 ③ 仍要跑一次,而 ①d 不用**(2026-08-12 定性):①d 是**全图聚合** AbsRel,远景/地面像素占绝大多数,近带被稀释 → DA3 硬扛得住(实测 0.132→0.0483 反而更好)。③ 测的是**尺度**、且在**接近窗**上重投影,而 `near_weight=3.0` 恰恰把接近段的近带压了约 10×(前向 6.415→0.645m)—— **改动正好落在被测量上**,head A 的 0.05–0.12 对阈值 0.25 也不算宽余量。故这一条不属于"DA3 硬通过",跑一次确认(期望过,不拉锯)。

---

## 3. 待办清单(按依赖排序)

- [ ] **A. head B 上跑 ③(仅 signal 3)** — H100,离线,~分钟级
      ⚠️ **①d 在 head B 上已完成(晚⁷ local 0.0483 PASS),不要重跑。**
      ⚠️ **前置:盘要挂上。** 晚¹⁹ 记录 `dataset_v0_local_depth`/`approach_scale_d18` 在**可拆卸共享盘**,H100 .22 当时未挂载(而 near_head ckpt 可达,是因 artifacts 在另一块当时挂着的盘)——这也解释了"数据在 `~/aerial_ft_cache/` 还是 `~/aerial-rl-skeleton/`"的路径冲突:**两条路径可能分属不同盘**。跑 ③ 前先 `ls -d` 确认语料可见。
      `_v0_gate --signals 3 --depth-ckpt <head B>/depth_step_2000_da3_head.pt --dataset <local_depth 语料> --window 8 --max-windows 256 --device cuda --emit artifacts/v0_partial_3_headB.json`
      **为何 ③ 不是"DA3 硬通过"**:`near_weight=3.0` 把近带压了约 10×(6.415→0.645m),而 ③ 测的就是**尺度**、且在**接近窗**上做重投影 —— 改动正好打在被测量上;head A 余量 0.05–0.12 vs 阈值 0.25 不宽。对比 ①d 是全图聚合(远景/地面像素稀释近带)故 DA3 扛得住。
- [x] ~~**B. ①a–c:先找 dry-run 的训练日志**~~ → **已查清,结论:重采语料**(2026-08-12 第三轮,详见 §3.3)
      日志找到了(`wm_ckpt_v2clean_20260810/wm_train.jsonl`,500 行,字段齐全),**三条判据全过且余量是量级的**:a loss 16.80→1.49(降 91%,只需 2%)、b recon 0.3245→0.0282(降 11.5×)、c min_ent 0.4368(需 ≥0.10,最小值在 step 2 ⇒ 全程无后验塌缩)。
      **但不能用** —— 见 §3.3 的失格理由(dt-desync 语料)。用户拍板:**重采一份语料**,不做语料考古。
- [ ] **B'. 用合格语料重跑 ①a–c** ← 取代旧 B
      用户拍板(2026-08-12):**重采一份语料,不做语料考古** —— 证明一份 7 月语料的来历比重采更贵、结论更弱。
      **候选省事路径(可选)**:`dataset_v1_rgb`(16 集 @8 Hz,已在 H100)标称 8.0 ≤ 8.5 → **过 `_refuse_v0` 守卫**,且正是 RUNBOOK Step 6 `--dataset <Step4语料>` 所指那份。集数偏薄(16 集对 WM 少),但**今天就能跑出一份合格日志**把 ①a–c 走通;重采仍值得做,两者不互斥。
      **为何 ①a–c 不能砍(不变)**:①d/③=DA3 硬扛、②=不看图的 HeuristicPolicy、④=DA3 闭环 → **①a–c 是 V0 唯一测 RSSM 本身的信号**,而 RSSM 正是 v1 崩掉的东西(`wm_step_5000.pt` 单柱 shortcut 已失效)。砍掉它,V0 就只认证了"DA3 是个好深度模型",而 V1 想象规划要建在这个未验证 WM 上 —— 正是 v1 崩的原因。
- [ ] **C. P0 修复:shield 方向锥** — 在 ④ 重跑前做(会改 ④ 行为,merge 后再改等于作废);与 A/B 并行,不冲突
- [ ] **D. n 的 re-freeze** — 见 §4,待用户定 n 值
- [ ] **E. ②④ 重跑**(P0 之后,4090 渲染器需先起)→ emit partial
- [ ] **F. `--merge` 全四 partial JSON** → **exit 0 才翻 flags**

### 3.1 H100 查证进展(2026-08-12 第一轮已回)

**已解除:③ 的盘挂载前置** —— `~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_local_depth` **存在**(正是 §6 权威 gate 路径)。
⚠️ **存在两份同名语料**:`aerial-rl-skeleton/.../artifacts/` 与 `rl_collect_run/.../artifacts/` 各一份 → **一律用 `aerial-rl-skeleton/` 那份**(RUNBOOK §6 权威路径),勿混。
⚠️ `approach_scale_d18` 尚未确认存在,跑 ③ 前一并 `ls`。

**仍待查:①a–c 的 `wm_train.jsonl`** —— 用户首轮 `find` 用 `*log*` 匹配,**匹配不到 `.jsonl` 结尾的文件名,故漏搜**。
代码钉死:`_wm_train_validate.py:218` `log_path = ckpt_dir / "wm_train.jsonl"` —— 训练时**无条件写在 `--checkpoint-dir` 内部** → 大概率就在 `wm_ckpt_v2clean_20260810/` 里。

```bash
# 1. 找 dry-run 的 wm_train.jsonl
ls -la ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/wm_ckpt_v2clean_20260810/
find ~ -name "wm_train.jsonl" 2>/dev/null

# 2. 硬判据:是否带 recon/entropy 字段
head -1 ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/wm_ckpt_v2clean_20260810/wm_train.jsonl
wc -l ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/wm_ckpt_v2clean_20260810/wm_train.jsonl

# 3. ③ 的另一份语料
ls -d ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/approach_scale_d18 2>&1
```

**第 2 条是硬判据**(`_v0_gate.py:186-195`):日志缺 `recon_err`/`recon` 或 `post_entropy_frac`/`ent` **任一** → 直接判 FAIL,代码注释原话:"与其让 pass-safe 默认值(recon 0, ent 1)靠 loss drop 单独放行,不如判挂"。→ `head -1` 那行 JSON 的 key 直接决定 ①a–c 是**零成本出 verdict** 还是**必须重训**。

**已排除:7 月那批日志全部不可用** —— 用户列出的 `logs/ft/collapse_fix/train_20260731*.log`、`FastWAM/logs/train_*_2026072*.log` 等均为 **0720–0731**,属老 v1 时代;v2clean dry-run 是 **8/10**,时间对不上。且格式为 `.log` 非 `.jsonl`。**即便格式可转,语料也不是 Step-6 的 —— 拿 v1 崩掉的那次训练充当 V0 证据 = gaming,不做。**

### 3.3 ①a–c 已查清:v2clean 为何**实质失格**(不是记账疏漏)

**日志本身没问题**:`wm_ckpt_v2clean_20260810/wm_train.jsonl`(500 行)字段齐全,`check_learning_curves`(`v0_metrics.py:51`,k=500//10=50,首尾各 50 行取均值)三条全过、余量量级级:

| 判据 | 实测 | 阈值 | 余量 |
|---|---|---|---|
| a loss↓ | 16.7991 → **1.4948**(−91%) | 需 <16.4631(−2%) | ~11× |
| b recon 不劣 | 0.3245 → **0.0282** | 需 ≤0.3245 | 11.5× |
| c min entropy-frac | **0.4368**(argmin 在 step 2) | 需 ≥0.10 | 4.4×,**全程无后验塌缩** |

**但这份日志不能当 ①a–c 权威证据**,理由是语料而非数字:

`_wm_train_validate.py:45-77` `_refuse_v0()` 明文拒绝 `step_hz > 8.5` 的语料,报错原文 *"is the dt-desynced V0 corpus — **do not train a real WM on it**. Pass `--allow-v0-desync` **only to exercise the code path**"*。而 `collect_v1.sh:4` 记载 7 月 `dataset_v0` **标称 12 Hz、实测仅 7.1–8.3** → 标称 12 > 8.5 → **该语料必须靠 `--allow-v0-desync` 逃生舱才能训**。

→ 所以"非权威"是**实质失格**:漂亮的三条数字建立在一份代码明文写着"不要用它训真 WM"的 dt-desync 语料上。**用它充当 ①a–c 证据 = 拿逃生舱放行的训练冒充 gate 证据,性质等同调阈值凑过。**

**根因(已修,见 §3.4)**:`wm_train.jsonl` 只写 loss/recon/ent,**`--dataset` 完全不落盘** → 曲线无法自证语料 → 三周后无人能判权威性。**这就是"你经常忘"在代码层的对应物;不修,重采一份新语料后新日志同样不自证。**

### 3.4 根因修复(2026-08-12,Mac 侧已落):训练产物自证语料

`_wm_train_validate.py` 新增 `_write_train_meta()` → 训练**开始前**在 `--checkpoint-dir` 内写 `wm_train_meta.json`,记录:`dataset` 绝对路径、`dataset_manifest_meta`(含 `step_hz`/`grab_depth`)、`allow_v0_desync`、**`authoritative`(= not allow_v0_desync)**、episodes/transitions、steps/window/wm_batch、config、image_size、`git_sha`。用了逃生舱则 stdout 直接打 `⚠ allow_v0_desync=TRUE → NOT authoritative ①a–c evidence`。

**治理**:纯增量旁挂文件。`_v0_gate._signal1abc_from_log` **只 parse `.jsonl`、从不读该文件** → 冻结 §4.1 verdict **逐字节不变**;未动阈值/shield/env/模型/flags。训练前写以便崩溃/中断也留痕。
**测试**:`tests/test_wm_train_meta.py` 4 例(记录语料并标 authoritative / `--allow-v0-desync` 标 authoritative=False / 缺 manifest 不抛 / 不污染 gate 读的 `.jsonl`);模块级 `importorskip("torch")` 照 `test_dynamics_torch.py:12` 惯例 → Mac 跳过、H100 真跑。**Mac 全套 177 passed / 3 skipped,无回归。**

### 3.2 悬空引用:两个被 RUNBOOK 引用但 Mac 侧不存在的文档

Mac worktree 全盘 `find` 均无:
- `docs/handover/2026-08-12-v2-plan-risk-assessment.md` —— RUNBOOK §8 晚²⁰ 引用的方案评估报告。**我(Claude)写了 §8 记录却未确认文件落盘**,可能写在别的 worktree 或压根没写成。
- `docs/handover/2026-08-12-v0-gate-status-and-roadmap.md` —— 晚¹⁹ 声称"状态收敛成的单一权威文档"。

→ **本文件(V0_GATE_STATUS.md)要治的正是这个病,结果自己也被咬。** 处置:H100 上 `ls` 确认;确实不存在则从 RUNBOOK §8 删除悬空引用(不要留指向空文件的"权威文档"指针)。

---

## 4. n=16 的处置(用户拍板 2026-08-12)

**不再追 scan 喂满 16** —— 理由:"如果非要做就会出现之前的 harness bug"(晚⁸–晚¹⁴ 那一串 probe/scan/spawn-collision 几何 bug)。

**治理收口(必须做,否则踩红线)**:`n_eval_episodes: 16` 是 §4.1 **冻结值**。静默用 n<16 跑 = 悄悄弱化 gate = gaming。干净做法 = **一次 re-freeze**,把 n 降到实测可达值(历史实测 ②n=9~12 / ④n=7),理由写明"scan 喂满 16 不可达,强做必重引 harness 几何 bug"。
状态:**待用户定 n 值** → 然后改 frozen spec §4.1 + RUNBOOK §8 记一笔。

---

## 5. 治理红线(不变)

- 四信号全过前**不翻 flags**(`depth_head.enable` / `safety.kind` / `corrector.enable_wm_update`);`enable_policy_update`(V4)绝不顺带开
- **不为凑过调阈值/shield 参数** —— shield **控制律**是被测系统(可改),§4.1 **阈值**不可改(改需 re-freeze)
- 代码走 git,禁 scp 热补丁

---

## 6. 变更记录

- **2026-08-12(第三轮)** —— ①a–c 查清并**结案为"重采语料"**;根因(训练产物不自证语料)已在 Mac 侧修掉。
  1. **日志找到了**(用户 H100 实测):`wm_ckpt_v2clean_20260810/wm_train.jsonl` 500 行,`recon_err`/`post_entropy_frac` 齐全 → `_v0_gate.py:186-195` 的"缺字段直接 FAIL"分支不触发。首轮 `find` 用 `*log*` 匹配不到 `.jsonl`,故此前漏搜。
  2. **判据三条全过、余量量级**(见 §3.3 表)。
  3. **但语料实质失格** —— `_refuse_v0()` 明文拒 `step_hz>8.5`("do not train a real WM on it");7 月 `dataset_v0` 标称 12 Hz → 必须靠 `--allow-v0-desync`("only to exercise the code path")。→ **"非权威"不是记账疏漏。** 用户拍板重采,不做语料考古。
  4. **根因修复**(§3.4):新增 `wm_train_meta.json` 旁挂,记 dataset 绝对路径 + `step_hz` + `allow_v0_desync` + `authoritative` + git_sha,训练前写。**gate verdict 逐字节不变**;4 新单测;Mac 177 passed/3 skipped。
  5. 另记:H100 上有**两份** `wm_train.jsonl` —— `wm_ckpt/`(无日期,默认目录 fallback,疑 v1 时代)与 `wm_ckpt_v2clean_20260810/`。**喂 gate 必须用带日期的全路径**,勿混。
- **2026-08-12(第二轮修订)** —— 用户质疑"head B 的 ①③ 是硬通过的,为什么又要做 ①a–c 重训"。查证后三处订正:
  1. **①d 从待办移除** —— head B 上晚⁷ 已 PASS(0.0483),我上一版列成"approach 语料未跑"属重复列项。**待办只剩 ③。**
  2. **①a–c 不是"重训"而是"缺日志"** —— RUNBOOK line 23 + 晚¹⁹ line 117("①a–c 需 `--learning-log`")显示"非权威"卡在 (a) 非 Step-6 语料 (b) 未留日志;而 ①a–c 判 `_check_learning` **吃日志不吃 ckpt** → 日志若在则零训练成本出 verdict。上一版"V0 唯一未完成的训练工作"**定性过重,撤回**。
  3. **补上晚¹⁹ 的盘挂载卡点** —— `dataset_v0_local_depth`/`approach_scale_d18` 在可拆卸共享盘,.22 当时未挂载;这同时解释了 `~/aerial_ft_cache/` vs `~/aerial-rl-skeleton/` 的路径冲突(**分属不同盘**)。③ 的真实前置是盘,不只是命令。
  另发现 §3.2 两个悬空文档引用(含我自己在 RUNBOOK §8 晚²⁰ 引用却未落盘的评估报告)。**①a–c 不可砍的论证不变**(见 §3B)。
- **2026-08-12** —— 建本文件。动因:Mac 侧 `artifacts/` 无任何 emit verdict JSON,gate 历史结果全在 H100,跨会话必丢。核实内容:`_v0_gate.py:1260` merge 判据、`_ALL_SIGNALS=("1","2","3","4")`、artifacts 目录实际内容。确认 head 一致性为主 gap。head B 定性由"妥协"更正为"修复真实缺陷"(依晚⁶ 证据 + 用户确认)。
