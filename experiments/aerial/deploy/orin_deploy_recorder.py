"""Local Orin deploy recorder: camera frames + aircraft state + corpus metadata."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np


@dataclass
class OrinDeployRecorderConfig:
    root: Path
    save_native_jpeg: bool = True
    save_wam_jpeg: bool = False
    jpeg_quality: int = 92


class OrinDeployRecorder:
    """Write ``manifest.json``, ``traj.jsonl``, and ``frames/step_XXXX.jpg``."""

    def __init__(self, config: OrinDeployRecorderConfig) -> None:
        self.config = config
        self.root = Path(config.root)
        self.frames_dir = self.root / "frames"
        self.frames_dir.mkdir(parents=True, exist_ok=True)
        self._traj_path = self.root / "traj.jsonl"
        self._traj_fp = self._traj_path.open("a", encoding="utf-8")
        self._step = 0
        self._t0 = time.perf_counter()

    @classmethod
    def open_run(
        cls,
        base_dir: Path,
        run_meta: dict[str, Any],
        *,
        save_native_jpeg: bool = True,
        save_wam_jpeg: bool = False,
    ) -> "OrinDeployRecorder":
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        root = Path(base_dir) / f"run_{stamp}"
        root.mkdir(parents=True, exist_ok=True)
        rec = cls(
            OrinDeployRecorderConfig(
                root=root,
                save_native_jpeg=save_native_jpeg,
                save_wam_jpeg=save_wam_jpeg,
            )
        )
        manifest = {
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "run_dir": str(root),
            **run_meta,
        }
        (root / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return rec

    def record_step(
        self,
        obs: Any,
        *,
        step_info: Optional[dict[str, Any]] = None,
        extra: Optional[dict[str, Any]] = None,
    ) -> Path | None:
        """Save one control-step observation. Returns native frame path if saved."""
        import cv2  # type: ignore

        frame_rel: str | None = None
        wam_rel: str | None = None
        if self.config.save_native_jpeg:
            bgr = (obs.info or {}).get("bgr_native")
            if bgr is not None:
                name = f"step_{self._step:04d}.jpg"
                out = self.frames_dir / name
                cv2.imwrite(str(out), bgr, [int(cv2.IMWRITE_JPEG_QUALITY), int(self.config.jpeg_quality)])
                frame_rel = f"frames/{name}"
        if self.config.save_wam_jpeg and obs.rgb is not None:
            name = f"step_{self._step:04d}_wam.jpg"
            out = self.frames_dir / name
            rgb = np.asarray(obs.rgb, dtype=np.uint8)
            cv2.imwrite(str(out), rgb[:, :, ::-1], [int(cv2.IMWRITE_JPEG_QUALITY), int(self.config.jpeg_quality)])
            wam_rel = f"frames/{name}"

        row: dict[str, Any] = {
            "step": self._step,
            "t_s": round(time.perf_counter() - self._t0, 4),
            "pos": [float(x) for x in np.asarray(obs.position).reshape(-1)[:3]],
            "yaw": float(obs.yaw),
            "state": [float(x) for x in np.asarray(obs.state).reshape(-1)],
            "frame": frame_rel,
            "frame_wam": wam_rel,
        }
        if step_info:
            row["step_info"] = step_info
        mavlink = (obs.info or {}).get("mavlink")
        if mavlink:
            row["mavlink"] = mavlink
        corpus = (obs.info or {}).get("corpus")
        if corpus:
            row["corpus"] = corpus
        if extra:
            row.update(extra)
        self._traj_fp.write(json.dumps(row, ensure_ascii=False) + "\n")
        self._traj_fp.flush()
        self._step += 1
        return self.frames_dir / frame_rel.split("/")[-1] if frame_rel else None

    def close(self) -> None:
        if not self._traj_fp.closed:
            summary = {"steps": self._step, "traj": str(self._traj_path)}
            (self.root / "summary.json").write_text(
                json.dumps(summary, indent=2) + "\n", encoding="utf-8"
            )
            self._traj_fp.close()
