from pathlib import Path

from experiments.aerial.phase3_unified.handover_corpus import (
    MAP_INDOOR,
    MAP_OUTDOOR,
    build_handover_annotation,
    filter_episodes_by_spawn_report,
    rebuild_handover_pairs_from_legs,
)


def test_handover_annotation_has_both_maps():
    outdoor = Path("artifacts/seen_airsim16_long_routes.json")
    indoor = Path("experiments/aerial/phase3_unified/annotations/building99_indoor_short_routes.json")
    if not outdoor.is_file() or not indoor.is_file():
        import pytest
        pytest.skip("route annotations not present")

    payload = build_handover_annotation(
        outdoor_path=outdoor,
        indoor_path=indoor,
        include_long_outdoor=False,
        seed=0,
    )
    maps = {e.get("map_id") for e in payload["episodes"]}
    assert MAP_OUTDOOR in maps
    assert MAP_INDOOR in maps
    assert payload["scene_mix"]["handover_pairs"] >= 1


def test_handover_pairs_alternate_legs():
    outdoor = Path("artifacts/seen_airsim16_long_routes.json")
    indoor = Path("experiments/aerial/phase3_unified/annotations/building99_indoor_short_routes.json")
    if not outdoor.is_file() or not indoor.is_file():
        import pytest
        pytest.skip("route annotations not present")

    payload = build_handover_annotation(
        outdoor_path=outdoor,
        indoor_path=indoor,
        include_long_outdoor=False,
        seed=0,
    )
    by_hid: dict = {}
    for e in payload["episodes"]:
        hid = e.get("handover_id")
        if not hid:
            continue
        by_hid.setdefault(hid, []).append(e)
    assert by_hid
    hid, legs = next(iter(by_hid.items()))
    assert len(legs) == 2
    leg_names = {e["leg"] for e in legs}
    assert leg_names == {"outdoor", "indoor"}


def test_spawn_report_filters_incomplete_pairs():
    eps = [
        {"segment_name": "Approach_A", "leg": "outdoor", "handover_id": "HO01"},
        {"segment_name": "B99_a", "leg": "indoor", "handover_id": "HO01"},
        {"segment_name": "Approach_B", "leg": "outdoor", "handover_id": "HO02"},
        {"segment_name": "B99_b", "leg": "indoor", "handover_id": "HO02"},
    ]
    report = {
        "maps": {
            "env_airsim_16": [
                {"label": "Approach_A", "ok": True},
                {"label": "Approach_B", "ok": False},
            ],
            "building_99": [
                {"label": "B99_a", "ok": True},
                {"label": "B99_b", "ok": True},
            ],
        }
    }
    filtered = filter_episodes_by_spawn_report(eps, report)
    paired = rebuild_handover_pairs_from_legs(filtered)
    hids = {e["handover_id"] for e in paired}
    assert hids == {"HO01"}
    assert len(paired) == 2
