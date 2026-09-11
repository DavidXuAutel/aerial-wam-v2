import numpy as np

from experiments.aerial.rl.reward import RewardConfig
from experiments.aerial.rl.scene_profile import (
    SCENE_INDOOR_MICRO,
    SCENE_OUTDOOR_LONG,
    apply_episode_scene_profile,
    load_scene_profiles,
    resolve_scene_profile,
    restore_scene_profile_context,
)


def test_resolve_indoor_profile_limits():
    p = resolve_scene_profile({"scene": SCENE_INDOOR_MICRO}, step_hz=5.0)
    assert p.success_dist_m == 0.5
    assert np.allclose(p.action_limits, [0.15, 0.08, 0.08, 0.10])


def test_resolve_outdoor_default():
    p = resolve_scene_profile({"scene": SCENE_OUTDOOR_LONG}, step_hz=5.0)
    assert p.success_dist_m == 3.0
    assert p.action_limits[0] == 1.0


def test_load_scene_profiles_from_yaml():
    profiles = load_scene_profiles("configs/aerial_rl_phase3_unified.yaml")
    assert SCENE_OUTDOOR_LONG in profiles
    assert SCENE_INDOOR_MICRO in profiles
    assert profiles[SCENE_INDOOR_MICRO].success_dist_m == 0.5


def test_apply_and_restore_reward_success_dist():
    reward_cfg = RewardConfig(success_dist_m=3.0)
    ctx = apply_episode_scene_profile(
        {"scene": SCENE_INDOOR_MICRO},
        reward_cfg,
        None,
        step_hz=5.0,
    )
    assert reward_cfg.success_dist_m == 0.5
    restore_scene_profile_context(ctx, reward_cfg, None)
    assert reward_cfg.success_dist_m == 3.0
