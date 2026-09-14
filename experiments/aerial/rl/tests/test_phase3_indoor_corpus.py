import json
from pathlib import Path

import pytest

from experiments.aerial.phase3_unified.indoor_corpus import (
    IndoorSceneError,
    assert_indoor_episode,
    build_indoor_annotation,
    filter_handover_indoor_legs,
    merge_indoor_episodes,
    tag_indoor_episode,
)
from experiments.aerial.rl.scene_profile import SCENE_INDOOR_MICRO


def test_tag_indoor_episode():
    ep = tag_indoor_episode({"trajectory_id": "x"}, source="test")
    assert ep["scene"] == SCENE_INDOOR_MICRO
    assert ep["map_id"] == "building_99"
    assert ep["leg"] == "indoor"


def test_assert_indoor_rejects_outdoor():
    with pytest.raises(IndoorSceneError):
        assert_indoor_episode({"scene": "outdoor_long", "map_id": "env_airsim_16"})


def test_filter_handover_indoor_legs():
    eps = [
        {"segment_name": "out", "scene": "outdoor_approach", "map_id": "env_airsim_16", "leg": "outdoor"},
        {"segment_name": "in", "scene": "indoor_micro", "map_id": "building_99", "leg": "indoor"},
    ]
    indoor = filter_handover_indoor_legs(eps)
    assert len(indoor) == 1
    assert indoor[0]["segment_name"] == "in"
    assert_indoor_episode(indoor[0])


def test_build_indoor_annotation_from_repo_files():
    handover = Path("experiments/aerial/phase3_unified/annotations/handover_seen_filtered.json")
    b99 = Path("experiments/aerial/phase3_unified/annotations/building99_indoor_short_routes.json")
    if not handover.is_file() or not b99.is_file():
        pytest.skip("annotations not present")

    payload = build_indoor_annotation(handover_path=handover, b99_path=b99)
    assert payload["scene_mix"]["outdoor_prob"] == 0.0
    assert payload["scene_mix"]["indoor_prob"] == 1.0
    assert payload["scene_mix"]["total_n"] >= 8
    for ep in payload["episodes"]:
        assert_indoor_episode(ep, label=str(ep.get("segment_name") or ep.get("trajectory_id")))


def test_merge_keeps_distinct_handover_ids():
    a = tag_indoor_episode(
        {"trajectory_id": "dup", "handover_id": "HO01", "segment_name": "dup"},
        source="a",
    )
    b = tag_indoor_episode(
        {"trajectory_id": "dup", "handover_id": "HO02", "segment_name": "dup"},
        source="b",
    )
    c = tag_indoor_episode({"trajectory_id": "unique"}, source="c")
    merged = merge_indoor_episodes([a, b], [c])
    assert len(merged) == 3
