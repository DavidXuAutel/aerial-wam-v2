#!/usr/bin/env python3
"""V4 proposal §A / §A.3 — read-only imagined return decomposition.

§A arms (unit magnitude), same z0 / goal_rel0 / H=15:
  (a) trained π  act_latent(z)
  (b) constant forward  [+1, 0, 0, 0]
  (c) constant retreat  [-1, 0, 0, 0]

§A.3 scale-matched arms — π saturates ‖a‖≈3.4 (action_scale=3), so (b)/(c) at
unit magnitude cannot tell a *direction* defect from a *magnitude* exploit:
  (b3) forward at π's measured ‖a0[:3]‖
  (c3) retreat at the same magnitude

Reports Σ progress / p_coll / maneuver terms, Σ reward, λ-return
(λ=0.95, γ=0.997), plus per-step progress / p_coll / ‖a‖ / ‖goal_rel‖ so that
"imagination believes π arrives" (z-transition infidelity) is separable from
"RH over-rewards big actions" (reward scaling). Does not write ckpts, yaml, or train.

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


def _goal_dist_traj(
    goal_rel0: np.ndarray,
    actions: np.ndarray,
    done: np.ndarray,
) -> np.ndarray:
    """Reconstruct ‖goal_rel‖ over the imagined rollout, [B, H+1].

    Mirrors ``imagine``: ``advance_goal_rel_body`` applies ``g[:3] -= a[:3]``
    only while the batch element is still alive after the step.
    """
    b, h, _ = actions.shape
    out = np.zeros((b, h + 1), dtype=np.float64)
    cur = np.asarray(goal_rel0, dtype=np.float64)[:, :3].copy()
    out[:, 0] = np.linalg.norm(cur, axis=1)
    alive = np.ones(b, dtype=bool)
    for t in range(h):
        step_alive = alive & ~done[:, t]
        cur[step_alive] -= actions[step_alive, t, :3]
        out[:, t + 1] = np.linalg.norm(cur, axis=1)
        alive = step_alive
    return out


def _apply_a3(summary: Dict[str, Any], init_goal_dist: float) -> Dict[str, Any]:
    """§A.3 — scale-matched direction test + magnitude-exploit accounting.

    Pre-committed (proposal §A.3):
      (b3) > (a)  → RH direction preference survives at π's magnitude ⇒ §4
                    In-table sufficient; magnitude under-penalty logged as a
                    known exploit, ‖a‖ distribution mandatory at re-gate.
      (b3) ≤ (a)  → RH prefers π's own backward vector even scale-matched ⇒
                    A.2 branch 2: fix RH before the In-table revision.
      Separately, if arm (a) drives ‖goal_rel‖ → ~0 the fault is z-transition
      fidelity, not RH calibration (own case).
    """
    a = summary["a_pi"]
    b = summary["b_forward"]
    b3 = summary.get("b3_forward_scaled")
    c3 = summary.get("c3_retreat_scaled")
    if b3 is None or c3 is None:
        return {"verdict": "not_run", "disposition": "scale-matched arms missing"}

    lam_a = float(a["mean_lambda_G0"])
    lam_b3 = float(b3["mean_lambda_G0"])
    lam_c3 = float(c3["mean_lambda_G0"])

    # Magnitude under-penalty: π vs unit forward, progress gained per unit of
    # extra maneuver penalty paid. imagine's maneuver term is the only brake on
    # action magnitude, so a large ratio means magnitude is effectively free.
    d_prog = float(a["mean_sum_progress_term"] - b["mean_sum_progress_term"])
    d_man = float(b["mean_sum_maneuver_term"] - a["mean_sum_maneuver_term"])  # penalty grows
    under_penalty = float(d_prog / d_man) if abs(d_man) > 1e-9 else float("inf")

    arrival = float(a["goal_dist_min_mean"]) <= float(a.get("success_dist_m", 0.0) or 0.0)
    ood = float(a["goal_dist_max_mean"]) / init_goal_dist if init_goal_dist > 0 else float("nan")

    if lam_b3 > lam_a:
        verdict = "b3_gt_a"
        disposition = (
            "RH direction preference holds at π's magnitude; §4 In-table sufficient. "
            "Magnitude under-penalty is a known exploit: report ‖a‖ distribution and "
            "imagined-vs-real return correlation at re-gate."
        )
    else:
        verdict = "b3_le_a"
        disposition = (
            "RH prefers π's backward vector even scale-matched → A.2 branch 2: "
            "fix RH before the In-table revision; do not sign §4 as sufficient."
        )
    return {
        "lambda_G0_a_pi": lam_a,
        "lambda_G0_b3_forward_scaled": lam_b3,
        "lambda_G0_c3_retreat_scaled": lam_c3,
        "match_scale": float(b3["const_scale"]),
        "verdict": verdict,
        "disposition": disposition,
        "magnitude_under_penalty_ratio": under_penalty,
        "magnitude_note": (
            "Δprogress / Δmaneuver-penalty for π vs unit forward; >>1 means the "
            "imagined objective is maximized by saturating ‖a‖ regardless of direction."
        ),
        "pi_imagined_arrival": arrival,
        "pi_goal_dist_max_over_init": ood,
        "ood_note": (
            "goal_rel is propagated by g-=a[:3]; a retreating arm inflates ‖goal_rel‖ "
            "beyond the RH training range, so its progress is an OOD query."
        ),
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
    p.add_argument(
        "--match-scale",
        type=float,
        default=0.0,
        help="§A.3 constant-arm ‖a[:3]‖; 0 = auto from π's measured first action",
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

    arms: Dict[str, Any] = {}

    def _run_arm(name: str, pol: Any, const_scale: Optional[float] = None) -> Dict[str, Any]:
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
        act_norm3 = np.linalg.norm(roll.actions[:, :, :3], axis=-1)  # [B, H]
        gdist = _goal_dist_traj(goal_rel0, roll.actions, roll.done)  # [B, H+1]
        rec = {
            "mean_sum_progress_term": float(np.mean(terms["sum_progress_term"])),
            "mean_sum_p_coll_term": float(np.mean(terms["sum_p_coll_term"])),
            "mean_sum_maneuver_term": float(np.mean(terms["sum_maneuver_term"])),
            "mean_sum_reward": float(np.mean(roll.rewards.sum(axis=1))),
            "mean_lambda_G0": float(np.mean(lam[:, 0])),
            "mean_lambda_all_t": float(np.mean(lam)),
            "mean_progress_per_step": float(np.mean(terms["mean_progress"])),
            "mean_p_coll_per_step": float(np.mean(terms["mean_p_coll"])),
            "mean_first_action": mean_act0,
            # §A.3: magnitude + goal-distance trajectories (imagined arrival vs OOD).
            "act0_norm3_mean": float(np.mean(act_norm3[:, 0])),
            "act_norm3_mean": float(np.mean(act_norm3)),
            "goal_dist_min_mean": float(np.mean(gdist.min(axis=1))),
            "goal_dist_max_mean": float(np.mean(gdist.max(axis=1))),
            "goal_dist_final_mean": float(np.mean(gdist[:, -1])),
            "success_dist_m": float(reward_cfg.success_dist_m),
            "per_step": {
                "progress": np.mean(roll.progress, axis=0).tolist(),
                "p_coll": np.mean(roll.p_coll, axis=0).tolist(),
                "act_norm3": np.mean(act_norm3, axis=0).tolist(),
                "goal_dist": np.mean(gdist, axis=0).tolist(),
            },
            "const_scale": float(const_scale) if const_scale is not None else None,
            "n": n,
        }
        print(
            f"[§A] {name}: Σprog={rec['mean_sum_progress_term']:+.3f} "
            f"Σpcoll={rec['mean_sum_p_coll_term']:+.3f} "
            f"Σman={rec['mean_sum_maneuver_term']:+.3f} "
            f"Σr={rec['mean_sum_reward']:+.3f} "
            f"λG0={rec['mean_lambda_G0']:+.3f} "
            f"‖a0‖={rec['act0_norm3_mean']:.3f} "
            f"goal_d {gdist[:, 0].mean():.1f}→{rec['goal_dist_final_mean']:.1f} "
            f"a0={np.round(mean_act0, 3).tolist()}"
        )
        return rec

    # Pass 1 — §A unit-magnitude arms.
    arms["a_pi"] = _run_arm("a_pi", ImaginationActorPolicy(actor_ac, deterministic=True))
    arms["b_forward"] = _run_arm("b_forward", _ConstPolicy(np.array([1.0, 0.0, 0.0, 0.0])), 1.0)
    arms["c_retreat"] = _run_arm("c_retreat", _ConstPolicy(np.array([-1.0, 0.0, 0.0, 0.0])), 1.0)

    a2 = _apply_a2(arms)
    print("[§A] A.2", json.dumps(a2, indent=2))

    # Pass 2 — §A.3 scale-matched arms at π's own first-action magnitude.
    scale = float(args.match_scale) if float(args.match_scale) > 0 else float(
        arms["a_pi"]["act0_norm3_mean"]
    )
    print(f"[§A.3] match_scale={scale:.4f} (0 → auto from π ‖a0[:3]‖)")
    arms["b3_forward_scaled"] = _run_arm(
        "b3_forward_scaled", _ConstPolicy(np.array([+scale, 0.0, 0.0, 0.0])), scale
    )
    arms["c3_retreat_scaled"] = _run_arm(
        "c3_retreat_scaled", _ConstPolicy(np.array([-scale, 0.0, 0.0, 0.0])), scale
    )

    a3 = _apply_a3(arms, float(np.linalg.norm([fwd, left, up])))
    print("[§A.3] A.3", json.dumps(a3, indent=2))

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
        "A3": a3,
        "match_scale": scale,
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
