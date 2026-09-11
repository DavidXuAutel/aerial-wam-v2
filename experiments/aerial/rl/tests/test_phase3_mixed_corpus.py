from experiments.aerial.phase3_unified.mixed_corpus import (
    build_mixed_corpus,
    tag_outdoor_routes,
)
from experiments.aerial.rl.scene_profile import SCENE_INDOOR_MICRO, SCENE_OUTDOOR_LONG


def test_tag_outdoor_routes():
    routes = [{"pos": [[0, 0, 0], [1, 0, 0]], "yaw": [0.0, 0.0]}]
    tagged = tag_outdoor_routes(routes)
    assert tagged[0]["scene"] == SCENE_OUTDOOR_LONG
    assert tagged[0]["pose_source"] == "gt_proxy"


def test_build_mixed_corpus_ratio():
    outdoor = [{"scene": SCENE_OUTDOOR_LONG, "id": "o"}]
    indoor = [{"scene": SCENE_INDOOR_MICRO, "id": "i"}]
    mixed = build_mixed_corpus(
        outdoor_routes=outdoor,
        indoor_segments=indoor,
        outdoor_prob=0.0,
        seed=0,
        shuffle=False,
    )
    assert all(ep["scene"] == SCENE_INDOOR_MICRO for ep in mixed)
