# V4 encode + longer train STATUS (125)

- **status**: A) encode-path code implemented — running tests + commit
- **updated**: 2026-08-16T16:45:00+08:00
- **handoff**: Mac bootstrap → agent on 125 (4090 renderer 127.0.0.1:41451)
- **prompt**: docs/handover/V4_ENCODE_TRAIN_125_PROMPT.md
- **sleep-safe**: yes (agent on 125)

## Goal
1. Align train + deploy to real torch WM encode (not StubLatentDynamics / proprio4).
2. Longer H100 AC train → `v4_ac_ckpt_20260816_wm/`.
3. Re-run V4 ①/④ on 125; update gate docs. Never flip `enable_policy_update`.

## A) Encode-path fixes (in progress)
- `train_v4_ac.py`: `--dynamics torch --wm-ckpt <path>`; mock backend OK with torch WM.
- `train_rl.py`: shared `load_torch_dynamics()` for train + deploy.
- `v4_gate_run_partials.py`: `--dynamics-kind torch --wm-ckpt`; latent_dim check vs actor.
- Test: `test_torch_encode_differs_from_stub_proprio4`.

## enable_policy_update
**Must stay false** in `configs/aerial_rl.yaml` — verified unchanged.

## Next
- Commit + `git push origin main`
- H100 longer train (300 iters target)
- Stage WM + actor ckpts on 125; gate re-run
