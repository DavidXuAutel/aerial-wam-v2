#!/usr/bin/env python3
"""Decouple handover eval: oracle router + dual ckpt (outdoor frozen + indoor).

Writes ``router_manifest.json`` and per-scene micro eval JSON. Outdoor long
regression gate is optional (heavy; uses ``wam_phase2_long_eval``).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import yaml

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("eval_phase3_handover_decouple")

PHASE2_OUTDOOR_DEFAULT = (
    "experiments/aerial/rl/artifacts/v4_ac_ckpt_phase2_toward_g_20260905_112006/v4_ac_latest.pt"
)
WM_DEFAULT = "experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _switch_scene(scene_sh: Path, target: str, sleep_s: float = 15.0) -> None:
    logger.info("switching AirSim scene -> %s", target)
    subprocess.run(["bash", str(scene_sh), target], check=True)
    time.sleep(float(sleep_s))


def _resolve_scene_script(root: Path, scene_script: str) -> Path:
    scene_sh = Path(scene_script)
    if not scene_sh.is_file():
        alt = root / "experiments/aerial/phase3_unified/scripts/recover_renderer_scene.sh"
        if alt.is_file():
            return alt
        alt2 = Path.home() / "aerial-indoor-wam/experiments/aerial/scripts/recover_renderer_scene.sh"
        return alt2 if alt2.is_file() else scene_sh
    return scene_sh


def _dedupe_segments(episodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []
    for ep in episodes:
        key = str(ep.get("segment_name") or ep.get("trajectory_id") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(ep)
    return out


def _partition_episodes(
    episodes: Sequence[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    from experiments.aerial.phase3_unified.handover_router import resolve_oracle
    from experiments.aerial.rl.scene_profile import (
        SCENE_INDOOR_MICRO,
        SCENE_OUTDOOR_APPROACH,
        SCENE_OUTDOOR_LONG,
    )

    buckets: Dict[str, List[Dict[str, Any]]] = {
        SCENE_OUTDOOR_LONG: [],
        SCENE_OUTDOOR_APPROACH: [],
        SCENE_INDOOR_MICRO: [],
    }
    for ep in episodes:
        out = resolve_oracle(ep)
        buckets[out.scene].append(ep)
    return buckets


def _eval_micro_segments(
    segments: List[Dict[str, Any]],
    *,
    actor_ckpt: Path,
    wm_ckpt: Path,
    cfg: Dict[str, Any],
    device: str,
    max_steps: int,
    pose_source_override: Optional[str],
    policy_id: str,
    scene_label: str,
) -> List[Dict[str, Any]]:
    from experiments.aerial.rl.actor_critic import LatentActorCritic, LatentActorDeployPolicy
    from experiments.aerial.rl.collector import act_delta, clip_body_delta
    from experiments.aerial.rl.goal_features import body_vel_from_obs, goal_rel_from_obs
    from experiments.aerial.rl.pose_estimate import make_pose_estimator, stamp_pose_on_obs
    from experiments.aerial.rl.reward import RewardConfig
    from experiments.aerial.rl.scene_profile import apply_episode_scene_profile, load_scene_profiles_from_mapping, restore_scene_profile_context
    from experiments.aerial.rl.train_rl import _build_env, load_torch_dynamics

    if not segments:
        return []

    cfg_env = dict(cfg.get("env") or {})
    cfg_env["backend"] = "airsim"
    cfg_env.setdefault("grab_depth", False)
    cfg_env.setdefault("step_hz", 5.0)
    env = _build_env(cfg_env)

    profiles = load_scene_profiles_from_mapping(cfg.get("scene_profiles") or {})
    reward_cfg = RewardConfig(**(cfg.get("reward") or {}))

    dynamics, _ = load_torch_dynamics(
        cfg.get("world_model") or {},
        str(wm_ckpt),
        device=device,
        success_dist_m=3.0,
    )
    actor_ac = LatentActorCritic.load_from_checkpoint(actor_ckpt, device=device)
    policy = LatentActorDeployPolicy(dynamics, actor_ac, deterministic=True, stream_latent=True)

    results: List[Dict[str, Any]] = []
    try:
        for seg in segments:
            label = str(seg.get("segment_name") or seg.get("trajectory_id"))
            goal = np.asarray(seg["pos"][-1] if len(seg["pos"]) > 2 else seg["pos"][1], dtype=np.float64)
            start = np.asarray(seg["pos"][0], dtype=np.float64)
            d0 = float(np.linalg.norm(goal - start))
            pose_source = str(pose_source_override or seg.get("pose_source") or "gt_proxy")
            logger.info("--- [%s] %s d0=%.2fm pose=%s ckpt=%s ---", scene_label, label, d0, pose_source, actor_ckpt.name)

            ctx = apply_episode_scene_profile(
                seg, reward_cfg=reward_cfg, safety=None, step_hz=5.0, profiles=profiles,
            )
            success_dist = float(ctx.profile.success_dist_m)
            limits = np.asarray(ctx.limits, dtype=np.float64)
            pose_est = make_pose_estimator(pose_source)

            obs = env.reset(seg)
            if obs is None or bool(getattr(obs, "collided", False)):
                results.append({
                    "segment_name": label,
                    "handover_id": seg.get("handover_id"),
                    "scene": seg.get("scene"),
                    "policy_id": policy_id,
                    "ok": False,
                    "reason": "spawn_collision",
                })
                restore_scene_profile_context(ctx, reward_cfg, None)
                continue

            pe = pose_est.reset(obs)
            stamp_pose_on_obs(obs, pe)
            if hasattr(policy, "reset"):
                policy.reset()
            latent = np.asarray(dynamics.encode(obs), dtype=np.float64)
            arrived = False
            collided = False
            steps = 0

            for _ in range(int(max_steps)):
                action = act_delta(policy, obs, str(seg.get("gpt_instruction", "")), limits)
                action = clip_body_delta(action, limits)
                next_obs, _info = env.step(action)
                out = dynamics.step(
                    latent,
                    action,
                    goal_rel=goal_rel_from_obs(obs),
                    body_vel=body_vel_from_obs(obs),
                )
                latent = np.asarray(out.z_next, dtype=np.float64)
                obs = next_obs
                pe = pose_est.update(obs, action=action, dt=0.2)
                stamp_pose_on_obs(obs, pe)
                collided = collided or bool(getattr(obs, "collided", False))
                steps += 1
                d_now = float(np.linalg.norm(np.asarray(obs.position, dtype=np.float64).reshape(3) - goal))
                if d_now <= success_dist:
                    arrived = True
                    break
                if collided:
                    break

            d_end = float(np.linalg.norm(np.asarray(obs.position, dtype=np.float64).reshape(3) - goal))
            results.append({
                "segment_name": label,
                "handover_id": seg.get("handover_id"),
                "scene": seg.get("scene"),
                "policy_id": policy_id,
                "ok": True,
                "arrived": arrived,
                "collided": collided,
                "steps": steps,
                "d0_m": round(d0, 3),
                "d_end_m": round(d_end, 3),
                "pose_source": pose_source,
                "success_dist_m": success_dist,
                "actor_ckpt": str(actor_ckpt),
            })
            logger.info(
                "%s arrived=%s d_end=%.3f collided=%s policy=%s",
                label, arrived, d_end, collided, policy_id,
            )
            restore_scene_profile_context(ctx, reward_cfg, None)
    finally:
        close = getattr(env, "close", None)
        if callable(close):
            close()

    return results


def _arrival_summary(results: Sequence[Dict[str, Any]]) -> Tuple[int, int, int]:
    n = len(results)
    n_ok = sum(1 for r in results if r.get("ok"))
    n_arr = sum(1 for r in results if r.get("arrived"))
    return n, n_ok, n_arr


def _convert_phase2_approach_rows(
    segments: Sequence[Dict[str, Any]],
    phase2_payload: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Map ``wam_phase2_long_eval`` episodes → decouple JSON rows."""
    from experiments.aerial.phase3_unified.handover_router import POLICY_PHASE2_OUTDOOR

    rows = list(phase2_payload.get("episodes") or [])
    out: List[Dict[str, Any]] = []
    for i, seg in enumerate(segments):
        label = str(seg.get("segment_name") or seg.get("trajectory_id"))
        row = rows[i] if i < len(rows) else {}
        spawn_fail = bool(row.get("spawn_fail"))
        out.append(
            {
                "segment_name": label,
                "handover_id": seg.get("handover_id"),
                "scene": seg.get("scene"),
                "policy_id": POLICY_PHASE2_OUTDOOR,
                "ok": not spawn_fail,
                "arrived": bool(row.get("arrived")),
                "collided": bool(row.get("collided")),
                "spawn_fail": spawn_fail,
                "spawn_err_m": row.get("spawn_err_m"),
                "steps": row.get("steps"),
                "d0_m": row.get("d_start_m"),
                "d_end_m": row.get("d_final_m"),
                "d_min_m": row.get("d_min_m"),
                "goal_closure": row.get("goal_closure"),
                "intervention_rate": row.get("intervention_rate"),
                "success_dist_m": 3.0,
                "eval_protocol": "phase2_toward_g_planner_shield",
                "subgoal_source": phase2_payload.get("subgoal_source"),
                "cruise_speed_m_s": phase2_payload.get("cruise_speed_m_s"),
            }
        )
    return out


def _eval_outdoor_approach_phase2(
    segments: List[Dict[str, Any]],
    *,
    root: Path,
    actor_ckpt: Path,
    wm_ckpt: Path,
    out_dir: Path,
    max_steps: int,
    cruise_speed: float,
    device: str,
    phase2_config: str,
) -> List[Dict[str, Any]]:
    """Outdoor approach via Phase-2 mainline stack (toward_g + planner + shield)."""
    if not segments:
        return []

    anno_path = out_dir / "outdoor_approach_phase2_annotation.json"
    anno_path.write_text(
        json.dumps({"protocol_version": "decouple_approach_v0", "episodes": segments}, indent=2),
        encoding="utf-8",
    )
    phase2_out = out_dir / "outdoor_approach_phase2_raw.json"
    cmd = [
        sys.executable,
        str(root / "experiments/aerial/scripts/wam_phase2_long_eval.py"),
        "--config",
        str(root / phase2_config),
        "--actor-ckpt",
        str(actor_ckpt),
        "--wm-ckpt",
        str(wm_ckpt),
        "--annotation",
        str(anno_path),
        "--episodes",
        str(len(segments)),
        "--subgoal-source",
        "toward_g",
        "--cruise-speed",
        str(cruise_speed),
        "--planner",
        "--success-dist",
        "3.0",
        "--max-steps",
        str(max_steps),
        "--device",
        str(device),
        "--out",
        str(phase2_out),
    ]
    logger.info(
        "outdoor_approach: phase2 protocol toward_g+planner+shield cs=%.1f max_steps=%d",
        cruise_speed,
        max_steps,
    )
    proc = subprocess.run(cmd, cwd=str(root))
    if not phase2_out.is_file():
        raise RuntimeError(f"phase2 approach eval produced no output: {phase2_out}")
    if proc.returncode not in (0, 1):
        raise RuntimeError(f"phase2 approach eval failed exit={proc.returncode}")
    payload = json.loads(phase2_out.read_text(encoding="utf-8"))
    return _convert_phase2_approach_rows(segments, payload)


def main() -> int:
    p = argparse.ArgumentParser(description="Phase-3 decouple handover eval (oracle router + dual ckpt)")
    p.add_argument("--config", default="configs/aerial_rl_phase3_unified.yaml")
    p.add_argument(
        "--annotation",
        default="experiments/aerial/phase3_unified/annotations/handover_seen_filtered.json",
    )
    p.add_argument("--outdoor-ckpt", default=PHASE2_OUTDOOR_DEFAULT)
    p.add_argument("--indoor-ckpt", default=None, help="defaults to --outdoor-ckpt if unset")
    p.add_argument("--wm-ckpt", default=WM_DEFAULT)
    p.add_argument("--device", default="cuda")
    p.add_argument(
        "--max-steps-approach",
        type=int,
        default=400,
        help="outdoor approach (phase2 protocol; ~30m legs need more than bare 120)",
    )
    p.add_argument("--max-steps-indoor", type=int, default=60)
    p.add_argument(
        "--approach-cruise-speed",
        type=float,
        default=10.0,
        help="match outdoor_approach profile / regression gate",
    )
    p.add_argument(
        "--phase2-config",
        default="configs/aerial_rl.yaml",
        help="config for wam_phase2_long_eval on approach legs",
    )
    p.add_argument(
        "--approach-protocol",
        choices=("phase2", "micro"),
        default="phase2",
        help="phase2=toward_g+planner+shield; micro=legacy bare actor loop",
    )
    p.add_argument("--scene-script", default="experiments/aerial/phase3_unified/scripts/recover_renderer_scene.sh")
    p.add_argument(
        "--out-dir",
        default="artifacts/phase3_unified_eval_decouple",
    )
    p.add_argument(
        "--segments",
        default="outdoor_approach,indoor_micro",
        help="comma-separated scenes to eval (outdoor_long optional)",
    )
    p.add_argument("--dry-run", action="store_true", help="write router manifest only; no AirSim")
    p.add_argument(
        "--run-outdoor-long-gate",
        action="store_true",
        help="also run outdoor long regression gate on outdoor-ckpt",
    )
    p.add_argument(
        "--outdoor-long-baseline",
        default="artifacts/phase3_unified_eval_20260911/outdoor_long_eval_phase2_baseline.json",
    )
    args = p.parse_args()

    root = _repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from experiments.aerial.eval.run_closed_loop import load_annotation
    from experiments.aerial.phase3_unified.handover_router import (
        POLICY_PHASE2_OUTDOOR,
        POLICY_PHASE3_INDOOR,
        build_router_manifest,
    )
    from experiments.aerial.rl.scene_profile import SCENE_INDOOR_MICRO, SCENE_OUTDOOR_APPROACH, SCENE_OUTDOOR_LONG

    ann_path = root / args.annotation
    raw = load_annotation(ann_path)
    episodes = list(raw) if isinstance(raw, list) else list((raw or {}).get("episodes") or [])
    if not episodes:
        logger.error("no episodes in %s", ann_path)
        return 1

    manifest = build_router_manifest(episodes)
    buckets = _partition_episodes(episodes)
    want = {s.strip() for s in str(args.segments).split(",") if s.strip()}

    out_dir = root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "router_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "evaluation_title": "Phase-3 decouple router manifest (oracle)",
                "annotation": str(ann_path),
                "scene_counts": {k: len(v) for k, v in buckets.items()},
                "episodes": manifest,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    logger.info("Wrote %s (%d episodes)", manifest_path, len(manifest))

    outdoor_ckpt = root / args.outdoor_ckpt
    indoor_ckpt = root / (args.indoor_ckpt or args.outdoor_ckpt)
    if args.indoor_ckpt is None:
        logger.warning("indoor-ckpt not set; using outdoor-ckpt (placeholder until P3-indoor trains)")

    summary: Dict[str, Any] = {
        "evaluation_title": "Phase-3 decouple handover eval",
        "annotation": str(ann_path),
        "outdoor_ckpt": str(outdoor_ckpt),
        "indoor_ckpt": str(indoor_ckpt),
        "dry_run": bool(args.dry_run),
        "segments_requested": sorted(want),
        "scene_counts": {k: len(v) for k, v in buckets.items()},
        "router_manifest": str(manifest_path),
    }

    if args.dry_run:
        summary_path = out_dir / "handover_decouple_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        logger.info("dry-run complete -> %s", summary_path)
        return 0

    cfg = yaml.safe_load((root / args.config).read_text()) or {}
    wm_ckpt = root / args.wm_ckpt
    scene_sh = _resolve_scene_script(root, args.scene_script)

    all_results: Dict[str, List[Dict[str, Any]]] = {}

    if SCENE_OUTDOOR_APPROACH in want:
        approach_eps = _dedupe_segments(buckets[SCENE_OUTDOOR_APPROACH])
        _switch_scene(scene_sh, "outdoor")
        if str(args.approach_protocol) == "phase2":
            all_results[SCENE_OUTDOOR_APPROACH] = _eval_outdoor_approach_phase2(
                approach_eps,
                root=root,
                actor_ckpt=outdoor_ckpt,
                wm_ckpt=wm_ckpt,
                out_dir=out_dir,
                max_steps=int(args.max_steps_approach),
                cruise_speed=float(args.approach_cruise_speed),
                device=str(args.device),
                phase2_config=str(args.phase2_config),
            )
            approach_title = "Decouple outdoor approach (Phase-2 toward_g+planner+shield)"
            approach_protocol = "phase2_toward_g_planner_shield"
        else:
            all_results[SCENE_OUTDOOR_APPROACH] = _eval_micro_segments(
                approach_eps,
                actor_ckpt=outdoor_ckpt,
                wm_ckpt=wm_ckpt,
                cfg=cfg,
                device=str(args.device),
                max_steps=int(args.max_steps_approach),
                pose_source_override=None,
                policy_id=POLICY_PHASE2_OUTDOOR,
                scene_label=SCENE_OUTDOOR_APPROACH,
            )
            approach_title = "Decouple outdoor approach (bare micro loop)"
            approach_protocol = "micro_actor"
        approach_path = out_dir / "outdoor_approach_eval.json"
        n, n_ok, n_arr = _arrival_summary(all_results[SCENE_OUTDOOR_APPROACH])
        approach_path.write_text(
            json.dumps(
                {
                    "evaluation_title": approach_title,
                    "actor_ckpt": str(outdoor_ckpt),
                    "policy_id": POLICY_PHASE2_OUTDOOR,
                    "eval_protocol": approach_protocol,
                    "cruise_speed_m_s": float(args.approach_cruise_speed),
                    "max_steps": int(args.max_steps_approach),
                    "n_segments": n,
                    "arrival_rate": round(n_arr / max(n, 1), 4),
                    "episodes": all_results[SCENE_OUTDOOR_APPROACH],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        logger.info("Wrote %s arrivals %d/%d protocol=%s", approach_path, n_arr, n, approach_protocol)

    if SCENE_INDOOR_MICRO in want:
        indoor_eps = _dedupe_segments(buckets[SCENE_INDOOR_MICRO])
        _switch_scene(scene_sh, "building99")
        all_results[SCENE_INDOOR_MICRO] = _eval_micro_segments(
            indoor_eps,
            actor_ckpt=indoor_ckpt,
            wm_ckpt=wm_ckpt,
            cfg=cfg,
            device=str(args.device),
            max_steps=int(args.max_steps_indoor),
            pose_source_override="gt_proxy",
            policy_id=POLICY_PHASE3_INDOOR,
            scene_label=SCENE_INDOOR_MICRO,
        )
        indoor_path = out_dir / "indoor_micro_eval.json"
        n, n_ok, n_arr = _arrival_summary(all_results[SCENE_INDOOR_MICRO])
        indoor_path.write_text(
            json.dumps(
                {
                    "evaluation_title": "Decouple indoor micro (P3-indoor ckpt)",
                    "actor_ckpt": str(indoor_ckpt),
                    "policy_id": POLICY_PHASE3_INDOOR,
                    "n_segments": n,
                    "arrival_rate": round(n_arr / max(n, 1), 4),
                    "episodes": all_results[SCENE_INDOOR_MICRO],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        logger.info("Wrote %s arrivals %d/%d", indoor_path, n_arr, n)

    if args.run_outdoor_long_gate:
        gate_sh = root / "experiments/aerial/scripts/eval_phase3_outdoor_regression_gate.sh"
        if not gate_sh.is_file():
            logger.error("missing gate script: %s", gate_sh)
            return 1
        env = dict(**{"OUT_DIR": str(out_dir)})
        subprocess.run(
            ["bash", str(gate_sh), str(outdoor_ckpt), str(root / args.outdoor_long_baseline)],
            check=False,
            env={**os.environ, **env},
        )
        summary["outdoor_long_gate"] = str(out_dir / "regression_gate_p2b.json")

    for scene, rows in all_results.items():
        n, n_ok, n_arr = _arrival_summary(rows)
        summary[f"{scene}_arrivals"] = f"{n_arr}/{n}"
        summary[f"{scene}_arrival_rate"] = round(n_arr / max(n, 1), 4)
    if SCENE_OUTDOOR_APPROACH in want:
        summary["outdoor_approach_protocol"] = (
            "phase2_toward_g_planner_shield"
            if str(args.approach_protocol) == "phase2"
            else "micro_actor"
        )

    summary_path = out_dir / "handover_decouple_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info("Wrote %s", summary_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
