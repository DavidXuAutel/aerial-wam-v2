#!/usr/bin/env python3
"""Short collision-head repair FT (runbook B→D bridge).

Loads an existing WM ckpt, freezes backbone, trains only ``coll_head`` with the
new near-depth / pos_weight loss, saves a dated ckpt, does not touch deploy yaml.

  source experiments/aerial/scripts/env_4090.sh
  $AERIAL_PY experiments/aerial/scripts/wam_coll_head_ft.py \\
    --dataset experiments/aerial/rl/artifacts/dataset_v0_p45_merged_20260821 \\
    --init-ckpt experiments/aerial/rl/artifacts/wm_ckpt_p45_merged_20260821/wm_step_500.pt \\
    --steps 300 --save-dir experiments/aerial/rl/artifacts/wm_ckpt_coll_ft_20260827
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def main() -> int:
    root = _repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    p = argparse.ArgumentParser(description="Collision-head only FT")
    p.add_argument("--dataset", required=True)
    p.add_argument("--init-ckpt", required=True)
    p.add_argument("--config", default="configs/aerial_rl.yaml")
    p.add_argument("--steps", type=int, default=300)
    p.add_argument("--wm-batch", type=int, default=8)
    p.add_argument("--window", type=int, default=8)
    p.add_argument("--device", default="cuda")
    p.add_argument(
        "--save-dir",
        default="experiments/aerial/rl/artifacts/wm_ckpt_coll_ft",
    )
    args = p.parse_args()

    import torch

    from experiments.aerial.rl import dataset as ds
    from experiments.aerial.rl.buffer import ReplayBuffer
    from experiments.aerial.rl.dynamics_torch import TorchRSSMDynamics

    cfg_path = Path(args.config)
    if not cfg_path.is_absolute():
        cfg_path = root / cfg_path
    cfg = yaml.safe_load(cfg_path.read_text()) or {}
    wm_cfg = dict(cfg.get("world_model") or {})
    wm_cfg["device"] = str(args.device)

    dataset = Path(args.dataset).expanduser()
    if not dataset.is_absolute():
        dataset = root / dataset
    init_ckpt = Path(args.init_ckpt).expanduser()
    if not init_ckpt.is_absolute():
        init_ckpt = root / init_ckpt
    save_dir = Path(args.save_dir).expanduser()
    if not save_dir.is_absolute():
        save_dir = root / save_dir
    save_dir.mkdir(parents=True, exist_ok=True)

    episodes = ds.load_dataset(dataset, skip_quarantined=True)
    buf = ReplayBuffer(capacity_episodes=max(8, len(episodes) + 4))
    for ep in episodes:
        if len(ep) < int(args.window):
            continue
        buf.add_episode(ep)
    if buf.num_episodes < 1:
        print("[coll-ft] no usable episodes", file=sys.stderr)
        return 2

    sample_obs = buf.sample_windows(1, 1)[0][0].obs
    wm_cfg["image_size"] = int(np.asarray(sample_obs.rgb).shape[0])
    model = TorchRSSMDynamics.from_config(wm_cfg)
    model.load_checkpoint(str(init_ckpt))
    model.train()

    model.apply_freeze_backbone_train_coll_head()
    opt = torch.optim.AdamW(
        list(model.coll_head.parameters()),
        lr=float(wm_cfg.get("lr", 1e-4)),
    )

    log_path = save_dir / "coll_ft.jsonl"
    if log_path.exists():
        log_path.unlink()
    rows: List[Dict[str, Any]] = []
    for i in range(int(args.steps)):
        windows = buf.sample_windows(int(args.wm_batch), int(args.window))
        loss_dict = model.update_coll_head(windows, optimizer=opt)
        row = {
            "step": i + 1,
            "loss": loss_dict.get("loss"),
            "loss_coll": loss_dict.get("loss_coll"),
            "loss_coll_hinge": loss_dict.get("loss_coll_hinge"),
            "coll_hinge_gap": loss_dict.get("coll_hinge_gap"),
            "coll_pos_weight": loss_dict.get("coll_pos_weight"),
        }
        rows.append(row)
        with log_path.open("a") as f:
            f.write(json.dumps(row) + "\n")
        if (i + 1) % max(1, int(args.steps) // 10) == 0:
            print(
                f"[coll-ft] step={i+1} loss_coll={row.get('loss_coll'):.4f} "
                f"hinge={row.get('loss_coll_hinge', 0.0):.4f} "
                f"gap={row.get('coll_hinge_gap', 0.0):.4f} "
                f"pw={row.get('coll_pos_weight')}"
            )

    model.eval()
    out_ckpt = save_dir / f"wm_step_{int(args.steps)}.pt"
    model.save_checkpoint(str(out_ckpt), optimizer=None, step=int(args.steps))
    meta = {
        "init_ckpt": str(init_ckpt),
        "dataset": str(dataset),
        "steps": int(args.steps),
        "coll_near_depth_m": float(getattr(model, "coll_near_depth_m", 0.0)),
        "coll_pos_weight_cfg": float(getattr(model, "coll_pos_weight", 0.0)),
        "out_ckpt": str(out_ckpt),
        "n_episodes": int(buf.num_episodes),
        "final_loss_coll": rows[-1].get("loss_coll") if rows else None,
    }
    (save_dir / "coll_ft_meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
