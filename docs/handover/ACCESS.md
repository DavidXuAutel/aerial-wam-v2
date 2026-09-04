# Access (on-campus vs offsite)

**Updated:** 2026-09-04 — **`.110` 退役**：PCIe x1 硬件缺陷（应为 x16），渲染帧率仅 22 fps vs 125 的 42 fps，且 AirSim 对部分路有瞬移 bug。**所有 eval / AirSim 工作迁至 125，110 不再使用。**

| Target | On-campus | Offsite / 默认 |
|---|---|---|
| **125**（唯一 eval / AirSim 机） | `ssh cursor-125` | `ssh cursor-125-public` |
| **H100** `.23` | 经 125：`ssh cursor-125[-public]` → `ssh h100-23`（直连：`ssh a25689@10.239.121.23 -p 31126`） | 同左 |
| **Git bare** | `cursor-125:~/repos/aerial-wam-v2.git` | `cursor-125-public:~/repos/…` |

## 强制工作流

```
Mac ──ssh cursor-125-public──► 125 (eval / AirSim / git bare) ──► H100
```

在 **125** 上：

```bash
ssh cursor-125-public
cd ~/aerial-wam-v2 && source experiments/aerial/scripts/env_4090.sh
```

**Mac `~/.ssh/config`（已配）**

```
Host cursor-125-public
  HostName ssh-125.david-x.com
  …
```

---

## 历史：`.110` 退役记录（2026-09-04）

- PCIe Gen3 x1（应为 x16），GPU 带宽 ~1 GB/s vs 125 的 ~32 GB/s
- AirSim 帧率 22 fps vs 125 的 42 fps
- route 1 在 110 上跑有 580m 瞬移 bug（E1 forensics 实测）
- Git origin 仍在 125 bare repo，110 的 checkout 不再维护
