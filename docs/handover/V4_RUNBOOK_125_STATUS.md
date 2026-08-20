# V4 RUNBOOK 125 STATUS

- **date**: 2026-08-20
- **state**: ACTIVE — P4.5 corpus **DONE** (34 usable); WM retrain in flight
- **HEAD**: `39dee46`
- **current step**: **真·P4.5** = 近带 enrichment + `S_open:S_blocked≈1:1` 重采 → WM 重训 → re-P3 → re-P1 → re-P4 → P7* → P8
- **P3**: **`authoritative=false` / `insufficient_support`**（⓪b `n_frames=95<100`）
  - 补数齐：`near_px_total=790055`；`max_frame_frac=0.0416`；⓪c bins `(0,1.5]` p90=1.978 / `(1.5,3]` p90=0.380；⓪f(3)/(4) 全表见 RUNBOOK §2.1；bins JSON `artifacts/v4_zero_p3_20260820_bins.json`
- **P1**: FAIL reward-only；**`one_step_ok=True`**（h=0：0.5817 < 0.6508）
- **P4**: provisional（⓿e FAIL / 记 `infeasible`）— re-run after P4.5 + ⓿e fix
- **P4.5 prior**: `wm_ckpt_p45_20260820` on **old** corpus — **does not count**
- **enable_policy_update**: false
- **R-16**: **(B)** — P8 blocked until ⓪/⓿/P1 authoritative re-pass
- **signed**: `--spare-count=16`

## Checklist

- [x] P0c / P2 wiring / P6
- [x] P1 FAIL (reward) — must re-pass after P4.5
- [x] P3 corrected → `insufficient_support`
- [x] P4 provisional logged
- [ ] **P4.5 real** — corpus **partial OK** (34 eps: 24 blocked / 11 open; target 1:1); WM retrain running
- [ ] re-P3 / re-P1 / re-P4
- [ ] P7-diag → freeze → P7-accept
- [ ] P8 actor train + gate ①′/④′

## Running jobs

| job | PID | log |
|-----|-----|-----|
| P4.5 WM train | **2790365** | `logs/v4_p45_wm_train_20260820.log` |
| P4.5 collect | done | `logs/v4_p45_collect_20260820.log` → 34/35 usable |

## Notes

- Renderer recovered via `recover_renderer.sh`; AirSim RPC OK on `127.0.0.1:41451`.
- Harness: `experiments/aerial/scripts/v4_p45_collect.py` (balanced scan + approach-bias 20 m).
- §3 #3/#7/#8 still unsigned — freeze may BLOCK after P7-diag.
