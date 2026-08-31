import yaml, json, torch, numpy as np, time
from experiments.aerial.rl.train_rl import _build_env, _build_safety, load_torch_dynamics
from experiments.aerial.rl.actor_critic import LatentActorCritic, LatentActorDeployPolicy
from experiments.aerial.rl.collector import RolloutCollector
from experiments.aerial.rl.depth_predictor import DepthMinPredictor
from experiments.aerial.rl.planner import ImaginationPlanner
from experiments.aerial.rl.reward import RewardConfig
from experiments.aerial.rl.buffer import ReplayBuffer

with open('configs/aerial_rl.yaml') as f:
    cfg = yaml.safe_load(f)

cfg['env']['backend'] = 'airsim'
cfg['env']['step_hz'] = 5.0
cfg['env']['grab_depth'] = True
env = _build_env(cfg['env'])
reward_cfg = RewardConfig(**(cfg.get('reward') or {}))
reward_cfg.success_dist_m = 3.0

dynamics, _ = load_torch_dynamics(cfg.get('world_model') or {}, 'experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt', device='cuda', success_dist_m=3.0)
actor_ac = LatentActorCritic.load_from_checkpoint('experiments/aerial/rl/artifacts/v4_ac_ckpt_step_e_20260828/v4_ac_latest.pt', device='cuda')
policy = LatentActorDeployPolicy(dynamics, actor_ac, deterministic=True)
depth_pred = DepthMinPredictor.from_checkpoint('experiments/aerial/rl/artifacts/depth_ckpt_p45mid_s8j_20260825/depth_best_holdout_da3_ft_head.pt', device='cuda')
shield = _build_safety(cfg.get('safety') or {})

limits = np.array([1.0, 0.4, 0.4, 0.314], dtype=np.float64)
planner = ImaginationPlanner(dynamics=dynamics, horizon=5, reward_cfg=reward_cfg, action_limits=limits, policy=actor_ac, critic=actor_ac)

col = RolloutCollector(env, policy, ReplayBuffer(), max_steps=250, reward_cfg=reward_cfg, safety=shield, depth_predictor=depth_pred, planner=planner, skip_reset_collision=True)

with open('artifacts/seen_airsim16_m1a20.json') as f:
    routes = json.load(f)

r14 = routes[13]
pos = np.asarray(r14['pos'], dtype=np.float64).reshape(-1, 3)
yaws = np.asarray(r14['yaw'], dtype=np.float64).reshape(-1)
start_pos = pos[0].copy()
goal_pos = pos[-1].copy()
start_yaw = float(yaws[0])
ep_dict = {
    'pos': [start_pos.tolist(), goal_pos.tolist()],
    'yaw': [start_yaw, start_yaw],
    'gpt_instruction': r14.get('gpt_instruction', ''),
}
ep_trans, stats = col.collect_episode(ep_dict)
print('Route 14 Steps:', len(ep_trans))
for idx in range(max(0, len(ep_trans)-25), len(ep_trans)):
    t = ep_trans[idx]
    p = t.obs.position
    dist = float(np.linalg.norm(p - goal_pos))
    ch = t.info.get('shield_channels', [])
    cones = t.obs.info.get('depth_cones_pred', {})
    fwd = cones.get('forward', None)
    min_d = t.obs.info.get('depth_min_pred', None)
    print('Step %03d: pos=%s dist=%.2fm fwd=%s min_d=%s act=%s ch=%s' % (idx, [round(x,1) for x in p.tolist()], dist, round(fwd,2) if fwd else None, round(min_d,2) if min_d else None, [round(x,2) for x in t.action.tolist()], ch))
