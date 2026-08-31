# AirSim + 评测环境 → `10.229.20.110`（2026-08-31）

> **状态**：**主环境 = `.110` only**。仓库 / venv / Outdoor / Indoor 均在 `.110`。  
> **125 = 纯跳板**（Cloudflare 入口、`a26125-110`、`h100-26`、git bare）。**禁止**在 125 跑 `env_4090` / forensics / AirSim。  
> **venv**：`.110` 系统 Python 3.12；venv 解释器已挂到 conda `py310`（site-packages 自 125 同步）。

---

## 拓扑

| 角色 | 主机 | 说明 |
|------|------|------|
| **评测 / 采集 / AirSim** | `10.229.20.110` · `a26125` | `~/aerial-wam-v2` + `~/sim_verify/.venv` + `~/aerial_airsim_persistent` |
| **Outdoor** | 同机 `:41451` | `env_airsim_16`；settings → `drone_1`（绑 `10.229.20.110`，非 127.0.0.1） |
| **Indoor** | 同机 | `scene/Building_99` |
| **125** | `10.229.20.125` | **仅桥**；Indoor Building_99 已停，勿再起正式渲染 |
| **H100** | 经 125 → `.26:31126` | 长训 |

```
Mac ──► 125 (bridge) ──► .110 (all aerial GPU/sim work)
                     └──► H100
```

---

## `.110` 日常

```bash
ssh a26125-110-public          # 默认（公网 Access）
# ssh a26125-110               # 公司局域网

bash --noprofile --norc ~/aerial_airsim_persistent/recover_renderer.sh
ss -ltn | grep 41451

cd ~/aerial-wam-v2
source experiments/aerial/scripts/env_4090.sh
```

---

## 从 125 增量同步（仅维护时）

在 **125** 上 rsync 到 `a26125-110:`（代码/ckpt），**不要**在 125 执行评测命令。见历史 rsync 排除列表（旧 depth/wm/dataset 未全量拷）。

---

## 仓库

- `configs/aerial_rl*.yaml` → `host: 10.229.20.110`
- `env_4090.sh` → `$HOME` + 默认 `AIRSIM_HOST=10.229.20.110`；在 125/`yao` 路径下会 **拒绝** source
- [`ACCESS.md`](ACCESS.md)
