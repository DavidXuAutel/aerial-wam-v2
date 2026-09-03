# Access (on-campus vs offsite)

**Updated:** 2026-09-03 — **125 已可跑 eval**：旧的「禁止碰 125 进程、不在此跑 eval」只是因为当时 125 在跑别的 project，**该限制作废**。两台空闲时按路并行（`--routes` + 合表，见 [RUNBOOK §7.1](../../experiments/aerial/RUNBOOK_wam_phase2_long_horizon.md)）。
（2026-08-31：**`.110` 公网入口已通**，与 125 同款 Cloudflare Access。默认 **`ssh a26125-110-public`**，不再经 125 跳进 `.110`。）

| Target | On-campus | Offsite / 默认 |
|---|---|---|
| **`.110` 主环境**（评测 / 采集 / AirSim） | `ssh a26125-110` → `10.229.20.110` · `a26125` | **`ssh a26125-110-public`** → `ssh-110.david-x.com`（Access） |
| **AirSim** | `10.229.20.110:41451`，**125 本机亦有**（E0 的 `direct_g` / `polyline` 两臂即在 125 跑通） | 同左（各自在本机跑 client，勿跨机连 41451） |
| **125** | `ssh cursor-125` — 桥 / git bare / H100 跳板 **+ 第二台 eval 机**（并行用） | `ssh cursor-125-public` |
| **H100** `.23` | 经 125：`ssh cursor-125[-public]` → `ssh h100-23`（直连：`ssh a25689@10.239.121.23 -p 31126`） | 同左 |
| **Git bare** | `cursor-125:~/repos/aerial-wam-v2.git` | `cursor-125-public:~/repos/…` |

## 强制工作流

```
Mac ──ssh a26125-110-public──► .110 (主 aerial GPU / AirSim / 评测)
Mac ──ssh cursor-125-public──► 125 (git bare / H100 跳 / 并行第二台评测) ──► H100
```

并行时两台跑**同一臂的不同路**（`--routes`），跑完必须合表；单台 JSON 的 `Verdict` 是子集上的，不得填 DECLARE。

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
