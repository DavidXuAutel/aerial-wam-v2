# V4 RUNBOOK 125 STATUS

- **date**: 2026-08-20
- **state**: **HOLD** — P3 记法更正后改道；supervisor / P7-diag **已停**
- **HEAD**: (after Mac push)
- **current step**: **真·P4.5** = 近带 enrichment + `S_open:S_blocked≈1:1` 重采 → WM 重训 → **re-P3 → re-P1 → re-P4**
- **P3**: **`authoritative=false` / `insufficient_support`**（不是 ⓪ FAIL）。⓪b：px=790055✅ / frames=95❌ / max_frac=0.0416✅；近带 95/6005=1.6%
- **P4**: provisional（⓿e FAIL）— **非权威**，须重跑
- **P4.5 so-far**: ⚠️ **不合格** — 4090 上用**旧** `dataset_v0_local_depth_r60_20260814` 训了 `wm_ckpt_p45_20260820`（**未**做近带/1:1 重采；H100 sync 失败）。**不得当 P4.5 DONE**
- **P7-diag**: was started — **killed**（⓪ 未权威通过前不进 freeze 链）
- **enable_policy_update**: false
- **R-16**: **(B)** — P8 前 ⓪/⓿/P1 必须全部权威重过；禁止把「无 §6 stop」当放行；禁止直冲 P8 supervisor
- **signed**: `--spare-count=16`

## Checklist

- [x] P0c / P2 wiring / P6
- [x] P1 FAIL (reward) — must re-pass
- [x] P3 corrected → `insufficient_support`
- [x] P4 provisional logged
- [ ] **P4.5 real** (near-band corpus + 1:1 + WM) — prior 4090 WM retrain **does not count**
- [ ] re-P3 / re-P1 / re-P4
- [ ] P7* / P8 only after authoritative ⓪/⓿/P1

## Notes

- Formal §5.0 sign-row for R-16=(B) still owed.
- §3 #3/#7/#8 still unsigned — relevant after authoritative ⓪ + P7-diag, not before.
