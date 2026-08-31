# Access (on-campus vs offsite)

**Updated:** 2026-08-31 — **`.110` 公网入口已通**（与 125 同款 Cloudflare Access）。默认 **`ssh a26125-110-public`**，不再经 125 跳进 `.110`。

| Target | On-campus | Offsite / 默认 |
|---|---|---|
| **`.110` 主环境**（评测 / 采集 / AirSim） | `ssh a26125-110` → `10.229.20.110` · `a26125` | **`ssh a26125-110-public`** → `ssh-110.david-x.com`（Access） |
| **AirSim** | **仅** `10.229.20.110:41451` | 同左（在 `.110` 本机跑 client） |
| **125** | `ssh cursor-125` — **仅桥 / git bare / H100 跳板**；**禁止碰 125 进程**、不在此跑 eval | `ssh cursor-125-public` |
| **H100** `.26` | 经 125：`ssh cursor-125[-public]` → `ssh h100-26` | 同左 |
| **Git bare** | `cursor-125:~/repos/aerial-wam-v2.git` | `cursor-125-public:~/repos/…` |

## 强制工作流

```
Mac ──ssh a26125-110-public──► .110 (全部 aerial GPU / AirSim / 评测)
Mac ──ssh cursor-125-public──► 125 (仅 H100 跳 / git) ──► H100
```

备用（Access 异常时）：`ssh a26125-110-via-125`（ProxyJump 125）。日常勿用。

在 **`.110`** 上：

```bash
ssh a26125-110-public
cd ~/aerial-wam-v2 && source experiments/aerial/scripts/env_4090.sh
```

**Mac `~/.ssh/config`（已配）**

```
Host a26125-110-public
  HostName ssh-110.david-x.com
  User a26125
  IdentityFile ~/.ssh/cursor_webbridge_125
  IdentitiesOnly yes
  ProxyCommand …/cloudflared access ssh --hostname %h

Host a26125-110          # 公司局域网
  HostName 10.229.20.110
  User a26125
  …

Host cursor-125-public   # 仅 H100 / git
  HostName ssh-125.david-x.com
  …
```

细节：[`AIRSIM_MIGRATE_110_20260831.md`](AIRSIM_MIGRATE_110_20260831.md)、`cursor-web-bridge/docs/ssh-110-home-client.md`。
