# 渲染器共用事故复盘（2026-09-03）

> **事故日期**：2026-09-03（当日 17:14 – 23:10）
> **影响范围**：phase-1 分支（`feat/actor-rollout-planner`）当日全部验收臂、phase-2 E1 取证轨迹
> **性质**：评测链路故障，**非**策略缺陷。受影响的判定全部作废，不构成对任何 ckpt 的结论
> **根因文件**：`configs/aerial_rl.yaml`（`env.host` 硬编码入 git）
> **修复**：[`experiments/aerial/rl/env/renderer_host.py`](../../experiments/aerial/rl/env/renderer_host.py)（选错机器变得不可能）、[`experiments/aerial/rl/env/rate_gate.py`](../../experiments/aerial/rl/env/rate_gate.py)（链路太慢拒跑）

---

## 1. 一句话

`configs/aerial_rl.yaml` 把 `env.host: 10.229.20.110` 提交进了 git，而 `train_rl._build_env` 只读这个 yaml 值、**从不查 `AIRSIM_HOST`**，于是每一台拉了仓库的机器都去驱动 .110 的渲染器——两台机器抢同一架无人机，且没有任何一行日志说明本次跑的是哪台渲染器。

## 2. 两条独立的伤害路径

同一个根因造成了两种完全不同的失效，事后必须分开看：

### 2.1 双客户端争用一架无人机（数据被污染）

AirSim 渲染器是**单消费者**的：两个客户端各自 `takeoff` / `moveByVelocityAsync` / `simSetVehiclePose`，共同作用在同一架 `drone_1` 上。当日「两台机器各跑一半路数」的并行方案因此让两个进程互相改写对方的位姿。

可复现的证据签名（`logs/wam_accept_mpc_rollout_b_r0007_125.log`）：

```
Route 01/08 | steps=  1 | d0=110.2m -> d_end=238.8m (min= 52.6m) | prog=-116.7% | severe_coll=True
```

单步内终点距离从 110.2 m 变成 238.8 m，位移量级 ~580 m —— 这是被另一条航线的 spawn 传送走了，不是飞出去的。phase-2 E1 的取证轨迹里是同一签名。

### 2.2 跨网抓 depth 把闭环压到 0.3 Hz（数字失去意义）

`DepthPlanar@224` 在 loopback 上约 0.10 s/帧，跨网约 0.7 s/帧。闭环因此从指令 5 Hz 掉到**实测 0.3 Hz**，即每个控制步之间真机推进 ~3 m，护盾与规划器都在对着 3 m 前的世界下指令。

当日被这条链路判 FAIL 的两臂（均为 routes 0–7 的半数分割）：

| 日志 | ckpt | 实测频率 | arrival | mean_progress | 判定 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `logs/wam_accept_actor_rollout_r0007_125.log` | `v4_ac_ckpt_step_e_20260828` | 0.3 Hz（8 次告警） | **0.0** | **−1.6087** | FAIL |
| `logs/wam_accept_mpc_rollout_r0007_125.log` | `v4_ac_ckpt_mpc_rollout_20260903` | 0.3 Hz（8 次告警） | **0.0** | **−1.4583** | FAIL |

第二行那个 ckpt，在健康链路上重测是 **arrival 75.0% / prog +0.899 / PASS**（见 [`WAM_PHASE1_BRANCH_MPC_ROLLOUT_DECLARE_20260904.md`](WAM_PHASE1_BRANCH_MPC_ROLLOUT_DECLARE_20260904.md)）。同一份权重，链路差 13 倍，结论从 FAIL 翻成 PASS——这就是「链路故障会伪装成策略结论」的完整证据。

## 3. 为什么当时没人发现

三个静默点叠在一起，缺一个都不至于出事：

1. **`_connect` 不打印 host**。运行日志里没有任何一行说明本次驱动了哪台渲染器，事后无法从 artifact 反查。
2. **`AIRSIM_HOST` 被无视**。`env_4090.sh` 导出了它、`orch_eval_worker.sh` 也导出了它，但 `_build_env` 只读 yaml，两套配置看起来一致其实无关。
3. **频率只是 WARNING**。`collector achieved 0.3 Hz (< 5.0 Hz target)` 每条航线都打，但跑批已经在飞，日志被后面 250 步刷走，最终 artifact 里**完全没有**频率字段——只有一个干净的 `verdict: FAIL`。

## 4. 修复：把「选错」和「太慢」都变成硬失败

### 4.1 host 解析与单消费者锁 —— `env/renderer_host.py`

* 解析顺序：`AIRSIM_HOST` > 显式 config `host` > 自动探测**本机**监听（loopback 优先）；`configs/aerial_rl.yaml` 与 `aerial_rl_rollout.yaml` 的默认值改为 `host: auto`。
* **非本机 host 一律拒连**，除非显式 `AIRSIM_ALLOW_REMOTE_HOST=1`（存在即生效，沿用 `AERIAL_ALLOW_LEGACY_RESUME` 惯例）。
* **每台机器每个 `host:port` 只允许一个客户端**，用 `mkdir` 原子锁 + `/proc/<pid>` 存活判定（沿用 `orch_eval_worker.sh:43-47` 的写法），退出/`close()` 即释放；`AIRSIM_ALLOW_SHARED_RENDERER=1` 可绕过。
* `_connect` 与 `_build_env` 都记录 `host / port / local|REMOTE / provenance / pid`，一次跑批的日志自己能说清它驱动了谁。
* `env_4090.sh` 改为调用**同一个** Python 解析器（`python -m ...renderer_host --port`），bash 与 Python 不可能再分叉。
* `orch_eval_worker.sh` 是故意跨机的（H100 客户端 → 4090 渲染器），因此在脚本里显式声明 `AIRSIM_ALLOW_REMOTE_HOST=1`，并注明该路径不得抓 depth。

跨机锁是看不见对面机器的，那种情况由「非本机拒连」在结构上排除，而不是靠锁。

### 4.2 开跑前链路测速 —— `env/rate_gate.py`

host 选对了，链路仍可能太慢（GPU 被占、渲染器抖动、第二个消费者）。因此在**验收入口**（`wam_step_g_accept_eval.py`、`wam_phase2_long_eval.py`）加一道硬门：

* 起飞前测 `--link-probe-n`（默认 5）帧 depth，取**中位数**（一次 GPU 抖动不该判死健康链路）；
* 超过 `--depth-budget-s`（默认 **0.15 s**，即 `airsim_env.step` 本来就为 depth 预留的 observe 预算）**直接 raise，不飞任何一条航线**；
* `AERIAL_ALLOW_SLOW_RENDERER=1` 可放行，但**探针结果无论如何写进结果 JSON 的 `link_probe` 字段**——慢链路上的数字可以存在，但再也不能被静默宣告；
* mock 后端没有链路可测，跳过（mock 本来就不参与权威判定）。

判别余量是宽的，不是刀锋：本机 loopback 实测 **0.102 s/帧（上限 9.78 Hz）**，跨网约 0.7 s/帧，阈值 0.15 s 落在两者之间约 7 倍的空档里。

```
# 2026-09-04 在 125 上的实测探针
{"host": "127.0.0.1", "median_s": 0.1022, "depth_hz_ceiling": 9.78,
 "budget_s": 0.15, "commanded_hz": 5.0, "verdict": "ok"}
```

### 4.3 回归测试

| 文件 | 覆盖 |
| :--- | :--- |
| `experiments/aerial/rl/tests/test_airsim_host_resolve.py` | 解析顺序、非本机拒连、锁的获取/失败/陈旧偷取/释放（22 项） |
| `experiments/aerial/rl/tests/test_rate_gate.py` | 阈值与 observe 预算一致、跨网拒跑、中位数而非均值、放行仍记录、无 depth 一律失败、mock 跳过（11 项） |
| `experiments/aerial/rl/tests/test_airsim_env_real.py` | 探针丢弃 warmup 帧、无 depth 渲染器返回空样本（新增 2 项） |

## 5. 作废清单（结论悬空，需在健康链路重测）

| 对象 | 状态 |
| :--- | :--- |
| 2026-09-03 phase-1 两臂 FAIL（arrival 0 / prog −1.6、−1.4） | **作废**，已由 09-04 健康链路三臂取代 |
| phase-2 E0 / E1 / P0 滚动全局的全部判定 | **悬空**，均在事故窗口内产出，需重测 |
| routes 16–19（长航线扩展） | 从未在健康链路上跑过 |

## 6. 遗留

* 归档 `artifacts/wam_accept_planner_v7_16ep.json` 是 `verdict=FAIL` / `action_in_box=0.9098`，而 8-28 的 DECLARE 写 in-box 100% / PASS —— 口径不一致，与本事故无关，待单独订正。
* 本次未改动 `.110` 上的任何东西；该机渲染器的健康状况仍需单独确认。
