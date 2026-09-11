from pathlib import Path

from experiments.aerial.eval.run_closed_loop import load_annotation
from experiments.aerial.phase3_unified.mixed_corpus import (
    build_mixed_annotation,
    build_mixed_corpus,
    tag_outdoor_routes,
)
from experiments.aerial.rl.scene_profile import SCENE_INDOOR_MICRO, SCENE_OUTDOOR_LONG


def test_tag_outdoor_routes():
    routes = [{"pos": [[0, 0, 0], [1, 0, 0]], "yaw": [0.0, 0.0]}]
    tagged = tag_outdoor_routes(routes)
    assert tagged[0]["scene"] == SCENE_OUTDOOR_LONG
    assert tagged[0]["pose_source"] == "gt_proxy"


def test_build_mixed_corpus_includes_both_scenes():
    outdoor = [{"scene": SCENE_OUTDOOR_LONG, "id": "o"}]
    indoor = [{"scene": SCENE_INDOOR_MICRO, "id": "i"}]
    mixed = build_mixed_corpus(
        outdoor_routes=outdoor,
        indoor_segments=indoor,
        shuffle=False,
    )
    scenes = {ep["scene"] for ep in mixed}
    assert scenes == {SCENE_OUTDOOR_LONG, SCENE_INDOOR_MICRO}
    assert len(mixed) == 2


def test_load_annotation_accepts_phase3_wrapper(tmp_path: Path):
    outdoor = Path("artifacts/seen_airsim16_long_routes.json")
    if not outdoor.is_file():
        import pytest
        pytest.skip("seen routes annotation not present")
    payload = build_mixed_annotation(outdoor, seed=0)
    path = tmp_path / "mixed.json"
    path.write_text(__import__("json").dumps(payload), encoding="utf-8")
    eps = load_annotation(path)
    assert len(eps) == 20
    scenes = {e.get("scene") for e in eps}
    assert "outdoor_long" in scenes and "indoor_micro" in scenes
