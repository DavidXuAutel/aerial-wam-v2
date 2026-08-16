#!/usr/bin/env python3
"""V4 pure-imagination AC short train entrypoint (H100 or local CPU smoke).

Does **not** modify ``configs/aerial_rl.yaml`` — pass overrides on CLI or edit
the in-memory cfg dict only.

    python -m experiments.aerial.rl.train_v4_ac --iters 5 --device cuda

On H100 after bundle/pull, run with ``dynamics.kind=torch`` and a loaded WM ckpt.
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict

import yaml

from experiments.aerial.rl.train_rl import build_from_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _load_cfg(repo: Path) -> Dict[str, Any]:
    cfg_path = repo / "configs" / "aerial_rl.yaml"
    return yaml.safe_load(cfg_path.read_text())


def main() -> int:
    p = argparse.ArgumentParser(description="V4 imagination AC short train")
    p.add_argument("--iters", type=int, default=5)
    p.add_argument("--episodes-per-iter", type=int, default=2)
    p.add_argument("--imagine-batch", type=int, default=16)
    p.add_argument("--imagine-horizon", type=int, default=15)
    p.add_argument("--device", default="cpu", help="cpu | cuda")
    p.add_argument("--ckpt-dir", default=None, help="write actor ckpt dir")
    p.add_argument("--backend", default="mock", choices=("mock", "airsim"))
    args = p.parse_args()

    repo = Path(__file__).resolve().parents[3]
    cfg = _load_cfg(repo)
    cfg.setdefault("corrector", {})
    cfg.setdefault("env", {})
    cfg.setdefault("imagination", {})
    cfg.setdefault("v4", {})
    cfg.setdefault("dynamics", {})
    cfg.setdefault("tau_predictor", {})
    cfg["corrector"]["iterations"] = int(args.iters)
    cfg["corrector"]["episodes_per_iter"] = int(args.episodes_per_iter)
    cfg["corrector"]["enable_policy_update"] = True
    cfg["corrector"]["enable_wm_update"] = False
    cfg["imagination"]["horizon"] = int(args.imagine_horizon)
    cfg["imagination"]["batch"] = int(args.imagine_batch)
    cfg["env"]["backend"] = str(args.backend)
    cfg["dynamics"]["kind"] = "stub" if args.backend == "mock" else cfg["dynamics"].get("kind", "stub")
    cfg["tau_predictor"]["enable"] = False if args.backend == "mock" else cfg["tau_predictor"].get("enable", False)
    cfg["v4"]["device"] = str(args.device)

    loop = build_from_config(cfg)
    if loop.actor_critic is None:
        logger.error("actor_critic not built — install torch")
        return 1

    reports = loop.run()
    losses = []
    for i, r in enumerate(reports):
        rl = r.rl
        logger.info("iter %d rl=%s", i, rl)
        if rl.get("status") == "updated":
            losses.append(float(rl.get("actor_loss", float("nan"))))

    meta = {
        "iters": len(reports),
        "losses": losses,
        "mean_actor_loss": float(sum(losses) / len(losses)) if losses else None,
        "device": str(args.device),
    }
    print(json.dumps(meta, indent=2))

    if args.ckpt_dir:
        ckpt_dir = Path(args.ckpt_dir)
        ckpt_dir.mkdir(parents=True, exist_ok=True)
        try:
            import torch

            ac = loop.actor_critic
            torch.save(
                {
                    "actor": ac._actor.state_dict(),
                    "critic": ac._critic.state_dict(),
                    "log_std": ac._log_std.detach().cpu(),
                    "config": ac.config.__dict__,
                },
                ckpt_dir / "v4_ac_latest.pt",
            )
            logger.info("wrote %s", ckpt_dir / "v4_ac_latest.pt")
        except Exception as exc:
            logger.warning("ckpt save skipped: %s", exc)

    ok = any(r.rl.get("status") == "updated" for r in reports)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
