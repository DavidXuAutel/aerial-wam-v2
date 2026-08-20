# V4 RUNBOOK 125 STATUS

- **date**: 2026-08-20
- **state**: ACTIVE — **P4.5 collection** in flight
- **HEAD**: `a67be85` (+ local harness)
- **current step**: **真·P4.5** = 近带 enrichment + `S_open:S_blocked≈1:1` 重采 → WM 重训 → re-P3 → re-P1 → re-P4 → P7* → P8
- **P3**: **`authoritative=false` / `insufficient_support`**（⓪b `n_frames=95<100`）
- **P4**: provisional（⓿e FAIL）— re-run after P4.5
- **P4.5 prior**: `wm_ckpt_p45_20260820` on **old** corpus — **does not count**
- **enable_policy_update**: false
- **R-16**: **(B)** — P8 blocked until ⓪/⓿/P1 authoritative re-pass
- **signed**: `--spare-count=16`

## Checklist

- [x] P0c / P2 wiring / P6
- [x] P1 FAIL (reward) — must re-pass after P4.5
- [x] P3 corrected → `insufficient_support`
- [x] P4 provisional logged
- [ ] **P4.5 real** (near-band + 1:1 + WM)
- [ ] re-P3 / re-P1 / re-P4
- [ ] P7-diag → freeze → P7-accept
- [ ] P8 actor train + gate ①′/④′

## Running jobs

| job | PID | log |
|-----|-----|-----|
| P4.5 collect | (pending launch) | `logs/v4_p45_collect_20260820.log` |

## Notes

- Renderer recovered via `recover_renderer.sh`; AirSim RPC OK on `127.0.0.1:41451`.
- Harness: `experiments/aerial/scripts/v4_p45_collect.py` (balanced scan + approach-bias 20 m).
- §3 #3/#7/#8 still unsigned — freeze may BLOCK after P7-diag.
