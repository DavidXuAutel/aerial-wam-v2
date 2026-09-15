"""Tests for Orin deploy local recorder."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from experiments.aerial.deploy.orin_deploy_recorder import OrinDeployRecorder


def _fake_obs(bgr: np.ndarray) -> SimpleNamespace:
    return SimpleNamespace(
        position=np.array([1.0, 2.0, 3.0]),
        yaw=0.5,
        state=np.zeros(7, dtype=np.float32),
        rgb=None,
        info={
            "bgr_native": bgr,
            "mavlink": {"armed": False, "rc": {"ch7": 1050}},
            "corpus": {"scene": "test"},
        },
    )


def test_orin_deploy_recorder_writes_manifest_traj_frame(tmp_path: Path) -> None:
    bgr = np.zeros((48, 64, 3), dtype=np.uint8)
    bgr[10, 20] = (255, 0, 0)
    rec = OrinDeployRecorder.open_run(tmp_path, {"note": "unit"})
    rec.record_step(_fake_obs(bgr), step_info={"phase": "reset"})
    rec.close()

    manifest = json.loads((rec.root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["note"] == "unit"
    assert (rec.root / "frames" / "step_0000.jpg").is_file()
    lines = (rec.root / "traj.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["step"] == 0
    assert row["frame"] == "frames/step_0000.jpg"
    assert row["corpus"]["scene"] == "test"
    assert row["mavlink"]["rc"]["ch7"] == 1050
