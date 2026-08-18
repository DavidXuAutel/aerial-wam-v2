#!/usr/bin/env python3
"""V4 proposal §A — read-only imagined return decomposition.

Three arms, same z0 / goal_rel0 / H=15:
  (a) trained π  act_latent(z)
  (b) constant forward  [+1, 0, 0, 0]
  (c) constant retreat  [-1, 0, 0, 0]

Reports Σ progress / p_coll / maneuver terms, Σ reward, λ-return
(λ=0.95, γ=0.997). Does not write ckpts, yaml, or train.

Usage (125, offline, no renderer):
  source experiments/aerial/scripts/env_4090.sh
  $PYTHON_BIN experiments/aerial/scripts/v4_imagine_return_decomp.py \\
    --repo ~/aerial-wam-v2 \\
    --dataset ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_headon_20260811 \\
    --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_20260817_wm_rh_goal_rgb/v4_ac_latest.pt \\
    --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_r60_rh_20260816/wm_step_1000.pt \\
    --out artifacts/v4_imagine_return_decomp_20260818.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

# Measured ①-eval ep0 body-frame goal (V4_PROGRESS_DIAG): fwd≈+30, left≈0, up≈0.85
_DEFAULT_GOAL_REL = (29.998834719910043, -0.0007621006679254805, 0.8479232788085938)


class _ConstPolicy:
    def __init__(self, action: np.ndarray) -> None:
        self._a = np.asarray(action, dtype=np.float64).reshape(4)

    def act_latent(self, z: np.ndarray) -> np.ndarray:
        return self._a.copy()


def _repo_root(explicit: Optional[str]) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    return Path(__file__).resolve().parents[3]


def _term_sums(
    progress: np.ndarray,
    p_coll: np.ndarray,
    actions: np.ndarray,
    done: np.ndarray,
    cfg: Any,
) -> Dict[str, np.ndarray]:
    """Per-batch summed weighted terms (done steps already zero in imagine)."""
    man = np.linalg.norm(actions, axis=-1)
    # Score the terminal step; drop post-done continuation.
    B, H = progress.shape
    mask = np.ones((B, H), dtype=bool)
    mask[:, 1:] = ~done[:, :-1]
    prog_t = cfg.w_progress * progress * mask
    coll_t = -cfg.w_collision * p_coll * mask
    man_t = -cfg.w_maneuver * man * mask
    return {
        "sum_progress_term": prog_t.sum(axis=1),
        "sum_p_coll_term": coll_t.sum(axis=1),
        "sum_maneuver_term": man_t.sum(axis=1),
        "mean_p_coll": np.where(mask.sum(axis=1) > 0, (p_coll * mask).sum(axis=1) / mask.sum(axis=1), 0.0),
        "mean_progress": np.where(mask.sum(axis=1) > 0, (progress * mask).sum(axis=1) / mask.sum(axis=1), 0.0),
    }


def _apply_a2(summary: Dict[str, Any]) -> Dict[str, Any]:
    b = summary["b_forward"]
    c = summary["c_retreat"]
    lam_b = float(b["mean_lambda_G0"])
    lam_c = float(c["mean_lambda_G0"])
    d_prog = float(c["mean_sum_progress_term"] - b["mean_sum_progress_term"])
    d_coll = float(c["mean_sum_p_coll_term"] - b["mean_sum_p_coll_term"])
    d_man = float(c["mean_sum_maneuver_term"] - b["mean_sum_maneuver_term"])
    # Which term drives (c)-(b) on the reward sum (same weights as imagine).
    drivers = {
        "progress": d_prog,
        "p_coll": d_coll,
        "maneuver": d_man,
    }
    dominant = max(drivers, key=lambda k: abs(drivers[k]))
    if lam_c >= lam_b and dominant == "p_coll":
        verdict = "c_ge_b_p_coll_dominant"
        disposition = "In-table necessary but not sufficient; open reward-balance case first"
    elif lam_c >= lam_b and dominant == "progress":
        verdict = "c_ge_b_progress_dominant"
        disposition = "RH progress direction wrong; fix RH before In-table"
    elif lam_b > lam_c:
        verdict = "b_gt_c"
        disposition = "imagined objective is forward-preferring; §4 In-table is sufficient"
    else:
        verdict = "c_ge_b_maneuver_or_tie"
        disposition = "unexpected dominant term — inspect JSON; do not sign §4 yet"
    return {
        "lambda_G0_b": lam_b,
        "lambda_G0_c": lam_c,
        "delta_c_minus_b": {"progress": d_prog, "p_coll": d_coll, "maneuver": d_man},
        "dominant_term_c_minus_b": dominant,
        "verdict": verdict,
        "disposition": disposition,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default=None)
    p.add_argument("--config", default="configs/aerial_rl.yaml")
    p.add_argument("--device", default="cuda")
    p.add_argument(
        "--dataset",
        default="~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_headon_20260811",
    )
    p.add_argument(
        "--actor-ckpt",
        default="experiments/aerial/rl/artifacts/v4_ac_ckpt_20260817_wm_rh_goal_rgb/v4_ac_latest.pt",
    )
    p.add_argument(
        "--wm-ckpt",
        default="experiments/aerial/rl/artifacts/wm_ckpt_r60_rh_20260816/wm_step_1000.pt",
    )
    p.add_argument("--n-starts", type=int, default=8)
    p.add_argument("--horizon", type=int, default=15)
    p.add_argument(
        "--goal-rel",
        nargs=3,
        type=float,
        default=list(_DEFAULT_GOAL_REL),
        help="body-frame goal [fwd, left, up]; dist = L2 (①-eval measured default)",
    )
    p.add_argument("--out", default="artifacts/v4_imagine_return_decomp.json")
    args = p.parse_args()

    root = _repo_root(args.repo)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    import yaml

    from experiments.aerial.rl.actor_critic import (
        ImaginationActorPolicy,
        LatentActorCritic,
        compute_lambda_returns,
    )
    from experiments.aerial.rl.dataset import load_dataset
    from experiments.aerial.rl.imagination import imagine
    from experiments.aerial.rl.reward import RewardConfig
    from experiments.aerial.rl.train_rl import load_torch_dynamics

    cfg = yaml.safe_load((root / args.config).read_text()) or {}
    reward_cfg = RewardConfig(**(cfg.get("reward") or {})) if cfg.get("reward") else RewardConfig()
    wm_cfg = cfg.get("world_model", {}) or {}

    actor_ckpt = Path(args.actor_ckpt).expanduser()
    if not actor_ckpt.is_absolute():
        actor_ckpt = root / actor_ckpt
    wm_ckpt = Path(args.wm_ckpt).expanduser()
    if not wm_ckpt.is_absolute():
        wm_ckpt = root / wm_ckpt
    ds_path = Path(args.dataset).expanduser()
    if not ds_path.is_absolute():
        ds_path = root / ds_path

    dynamics, wm_payload = load_torch_dynamics(
        wm_cfg, wm_ckpt, device=str(args.device),
        success_dist_m=float(reward_cfg.success_dist_m),
    )
    actor_ac = LatentActorCritic.load_from_checkpoint(actor_ckpt, device=str(args.device))
    if int(actor_ac.config.latent_dim) != int(dynamics.latent_dim):
        print(
            f"[§A] latent mismatch actor={actor_ac.config.latent_dim} "
            f"wm={dynamics.latent_dim}",
            file=sys.stderr,
        )
        return 2

    episodes = load_dataset(ds_path, skip_quarantined=True)
    if not episodes:
        print("[§A] empty dataset", file=sys.stderr)
        return 2
    n = min(int(args.n_starts), len(episodes))
    z0_list = []
    for ep in episodes[:n]:
        z0_list.append(dynamics.encode(ep[0].obs))
    z0 = np.stack(z0_list, axis=0)

    fwd, left, up = (float(x) for x in args.goal_rel)
    dist = float(np.linalg.norm([fwd, left, up]))
    goal_rel0 = np.tile(np.array([fwd, left, up, dist], dtype=np.float32), (n, 1))
    body_vel0 = np.zeros((n, 3), dtype=np.float32)

    policies = {
        "a_pi": ImaginationActorPolicy(actor_ac, deterministic=True),
        "b_forward": _ConstPolicy(np.array([1.0, 0.0, 0.0, 0.0])),
        "c_retreat": _ConstPolicy(np.array([-1.0, 0.0, 0.0, 0.0])),
    }

    arms: Dict[str, Any] = {}
    for name, pol in policies.items():
        roll = imagine(
            dynamics, pol, z0, int(args.horizon),
            reward_cfg=reward_cfg,
            goal_rel0=goal_rel0,
            body_vel0=body_vel0,
        )
        terms = _term_sums(roll.progress, roll.p_coll, roll.actions, roll.done, reward_cfg)
        values = actor_ac.value(roll.z)  # [B, H+1]
        lam = compute_lambda_returns(
            roll.rewards, values,
            gamma=0.997, lambda_gae=0.95, done=roll.done,
        )
        mean_act0 = roll.actions[:, 0].mean(axis=0).tolist()
        arms[name] = {
            "mean_sum_progress_term": float(np.mean(terms["sum_progress_term"])),
            "mean_sum_p_coll_term": float(np.mean(terms["sum_p_coll_term"])),
            "mean_sum_maneuver_term": float(np.mean(terms["sum_maneuver_term"])),
            "mean_sum_reward": float(np.mean(roll.rewards.sum(axis=1))),
            "mean_lambda_G0": float(np.mean(lam[:, 0])),
            "mean_lambda_all_t": float(np.mean(lam)),
            "mean_progress_per_step": float(np.mean(terms["mean_progress"])),
            "mean_p_coll_per_step": float(np.mean(terms["mean_p_coll"])),
            "mean_first_action": mean_act0,
            "n": n,
        }
        print(
            f"[§A] {name}: Σprog={arms[name]['mean_sum_progress_term']:+.3f} "
            f"Σpcoll={arms[name]['mean_sum_p_coll_term']:+.3f} "
            f"Σman={arms[name]['mean_sum_maneuver_term']:+.3f} "
            f"Σr={arms[name]['mean_sum_reward']:+.3f} "
            f"λG0={arms[name]['mean_lambda_G0']:+.3f} "
            f"a0={np.round(mean_act0, 3).tolist()}"
        )

    a2 = _apply_a2(arms)
    print("[§A] A.2", json.dumps(a2, indent=2))

    out = {
        "read_only": True,
        "n_starts": n,
        "horizon": int(args.horizon),
        "goal_rel0": [fwd, left, up, dist],
        "body_vel0": "zeros (deploy-like)",
        "gamma": 0.997,
        "lambda_gae": 0.95,
        "reward_weights": {
            "w_progress": reward_cfg.w_progress,
            "w_collision": reward_cfg.w_collision,
            "w_maneuver": reward_cfg.w_maneuver,
        },
        "actor_ckpt": str(actor_ckpt),
        "wm_ckpt": str(wm_ckpt),
        "wm_step": wm_payload.get("step"),
        "dataset": str(ds_path),
        "arms": arms,
        "A2": a2,
    }
    out_path = Path(args.out).expanduser()
    if not out_path.is_absolute():
        out_path = root / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2) + "\n")
    print(f"[§A] wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
