import numpy as np

from experiments.aerial.phase3_unified.handover_router import (
    FsmState,
    HandoverRouter,
    POLICY_PHASE2_OUTDOOR,
    POLICY_PHASE3_INDOOR,
    RouterInput,
    _point_in_polygon_xy,
    build_router_manifest,
    episode_scene,
    resolve_oracle,
)
from experiments.aerial.rl.scene_profile import (
    SCENE_INDOOR_MICRO,
    SCENE_OUTDOOR_APPROACH,
    SCENE_OUTDOOR_LONG,
)


def test_episode_scene_explicit():
    assert episode_scene({"scene": SCENE_OUTDOOR_LONG}) == SCENE_OUTDOOR_LONG
    assert episode_scene({"scene": SCENE_INDOOR_MICRO}) == SCENE_INDOOR_MICRO


def test_episode_scene_from_leg():
    assert episode_scene({"leg": "indoor"}) == SCENE_INDOOR_MICRO
    assert episode_scene({"leg": "outdoor"}) == SCENE_OUTDOOR_APPROACH


def test_episode_scene_from_map_id():
    assert episode_scene({"map_id": "building_99"}) == SCENE_INDOOR_MICRO
    assert episode_scene({"map_id": "env_airsim_16"}) == SCENE_OUTDOOR_LONG


def test_resolve_oracle_policies():
    outdoor = resolve_oracle({"scene": SCENE_OUTDOOR_APPROACH, "map_id": "env_airsim_16"})
    assert outdoor.fsm_state == FsmState.APPROACH
    assert outdoor.policy_id == POLICY_PHASE2_OUTDOOR

    indoor = resolve_oracle({"scene": SCENE_INDOOR_MICRO, "map_id": "building_99"})
    assert indoor.fsm_state == FsmState.INDOOR
    assert indoor.policy_id == POLICY_PHASE3_INDOOR


def test_build_router_manifest_counts():
    eps = [
        {"segment_name": "A", "scene": SCENE_OUTDOOR_APPROACH, "handover_id": "HO01"},
        {"segment_name": "B", "scene": SCENE_INDOOR_MICRO, "handover_id": "HO01"},
        {"segment_name": "C", "scene": SCENE_OUTDOOR_LONG},
    ]
    rows = build_router_manifest(eps)
    assert len(rows) == 3
    assert rows[0]["policy_id"] == POLICY_PHASE2_OUTDOOR
    assert rows[1]["policy_id"] == POLICY_PHASE3_INDOOR
    assert rows[2]["fsm_state"] == FsmState.OUTDOOR.value


def test_waypoint_approach_radius():
    router = HandoverRouter(mode="waypoint", approach_radius_m=10.0)
    router.reset(FsmState.OUTDOOR)
    wp = np.array([-720.0, -40.0, 15.0])
    out = router.step(
        RouterInput(
            p_hat=np.array([-725.0, -45.0, 15.0]),
            handover_wp=wp,
        )
    )
    assert out.fsm_state == FsmState.APPROACH
    assert out.scene == SCENE_OUTDOOR_APPROACH


def test_waypoint_indoor_geofence_hysteresis():
    fence = np.array([[-5.0, -5.0], [15.0, -5.0], [15.0, 10.0], [-5.0, 10.0]])
    router = HandoverRouter(
        mode="waypoint",
        indoor_confirm_frames=3,
        indoor_geofence=fence,
    )
    router.reset(FsmState.APPROACH)
    inside = np.array([1.0, 1.0, 1.5])
    for _ in range(2):
        out = router.step(RouterInput(p_hat=inside))
        assert out.fsm_state != FsmState.INDOOR
    out = router.step(RouterInput(p_hat=inside))
    assert out.fsm_state == FsmState.INDOOR
    assert out.policy_id == POLICY_PHASE3_INDOOR


def test_gcs_switch_indoor():
    router = HandoverRouter(mode="waypoint")
    router.reset(FsmState.OUTDOOR)
    out = router.step(RouterInput(gcs_command="switch_indoor"))
    assert out.fsm_state == FsmState.INDOOR


def test_point_in_polygon():
    square = np.array([[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]])
    assert _point_in_polygon_xy(np.array([5.0, 5.0]), square)
    assert not _point_in_polygon_xy(np.array([15.0, 5.0]), square)
