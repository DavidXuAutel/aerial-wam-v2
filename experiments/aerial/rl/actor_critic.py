"""DreamerV3-style λ-return actor-critic for imagination RL (V4-MVP).

Pure imagination training: sample ``z0`` → ``imagine(H)`` → ``update(rollout)``.
Uses λ-return targets, REINFORCE policy gradient with value baseline,
return normalization, entropy regularization, and stop-grad on value targets
for the actor (DreamerV3 §2.5 — **no PPO**).

The actor exposes ``act_latent(z) -> [4]`` for ``imagine()``; the critic
estimates ``V(z)`` on latent states.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

import numpy as np

from experiments.aerial.rl.imagination import ImaginedRollout

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
except ImportError:  # pragma: no cover - H100 has torch; stub host may not
    torch = None  # type: ignore
    nn = None  # type: ignore
    F = None  # type: ignore


@dataclass
class ActorCriticConfig:
    """MVP hyperparameters (design spec §3)."""

    latent_dim: int = 8
    action_dim: int = 4
    hidden_dim: int = 256
    lambda_gae: float = 0.95
    gamma: float = 0.997
    entropy_scale: float = 3.0e-4
    actor_lr: float = 1.0e-4
    critic_lr: float = 1.0e-4
    grad_clip: float = 100.0
    action_scale: float = 3.0
    device: str = "cpu"


def _require_torch() -> None:
    if torch is None:
        raise RuntimeError(
            "actor_critic requires torch (install with pip install 'aerial-wam-v2[gpu]')"
        )


def compute_lambda_returns(
    rewards: np.ndarray,
    values: np.ndarray,
    *,
    gamma: float = 0.997,
    lambda_gae: float = 0.95,
    done: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Backward λ-return (GAE-style) over imagined trajectories.

    ``rewards`` [B, H], ``values`` [B, H+1] (bootstrap at H), ``done`` [B, H].
    Returns [B, H] targets for the critic and advantages for the actor.
    """
    rews = np.asarray(rewards, dtype=np.float64)
    vals = np.asarray(values, dtype=np.float64)
    if rews.ndim != 2 or vals.ndim != 2:
        raise ValueError("rewards must be [B,H] and values [B,H+1]")
    batch, horizon = rews.shape
    if vals.shape != (batch, horizon + 1):
        raise ValueError(f"values shape {vals.shape} != ({batch}, {horizon + 1})")

    dones = np.zeros_like(rews, dtype=bool) if done is None else np.asarray(done, dtype=bool)
    returns = np.zeros_like(rews)
    adv = np.zeros_like(rews)
    gae = np.zeros(batch, dtype=np.float64)
    for t in reversed(range(horizon)):
        nonterminal = (~dones[:, t]).astype(np.float64)
        delta = rews[:, t] + gamma * vals[:, t + 1] * nonterminal - vals[:, t]
        gae = delta + gamma * lambda_gae * nonterminal * gae
        adv[:, t] = gae
        returns[:, t] = adv[:, t] + vals[:, t]
    return returns


def normalize_advantage(adv: np.ndarray, eps: float = 1e-8) -> np.ndarray:
    """Per-batch advantage normalization (DreamerV3 return norm)."""
    a = np.asarray(adv, dtype=np.float64)
    std = float(np.std(a))
    if std < eps:
        return a - float(np.mean(a))
    return (a - float(np.mean(a))) / (std + eps)


class _MLP(nn.Module):  # type: ignore[misc]
    def __init__(self, in_dim: int, out_dim: int, hidden: int) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden),
            nn.LayerNorm(hidden),
            nn.SiLU(),
            nn.Linear(hidden, hidden),
            nn.LayerNorm(hidden),
            nn.SiLU(),
            nn.Linear(hidden, out_dim),
        )

    def forward(self, x: "torch.Tensor") -> "torch.Tensor":
        return self.net(x)


class ImaginationActorPolicy:
    """Adapter wrapping ``LatentActorCritic`` for ``imagine()``."""

    def __init__(self, ac: "LatentActorCritic", *, deterministic: bool = False) -> None:
        self._ac = ac
        self.deterministic = bool(deterministic)

    def act_latent(self, z: np.ndarray) -> np.ndarray:
        return self._ac.act_latent(z, deterministic=self.deterministic)


@dataclass
class LatentActorCritic:
    """λ-return actor-critic on latent states (V4 deliverable)."""

    config: ActorCriticConfig = field(default_factory=ActorCriticConfig)
    _actor: Any = field(default=None, repr=False)
    _critic: Any = field(default=None, repr=False)
    _actor_opt: Any = field(default=None, repr=False)
    _critic_opt: Any = field(default=None, repr=False)
    _log_std: Any = field(default=None, repr=False)
    _device: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        _require_torch()
        cfg = self.config
        self._device = torch.device(str(cfg.device))
        ld, ad, hd = int(cfg.latent_dim), int(cfg.action_dim), int(cfg.hidden_dim)
        self._actor = _MLP(ld, ad, hd).to(self._device)
        self._critic = _MLP(ld, 1, hd).to(self._device)
        self._log_std = nn.Parameter(
            torch.zeros(ad, device=self._device) - 0.5,
        )
        self._actor_opt = torch.optim.Adam(
            list(self._actor.parameters()) + [self._log_std],
            lr=float(cfg.actor_lr),
        )
        self._critic_opt = torch.optim.Adam(self._critic.parameters(), lr=float(cfg.critic_lr))

    @classmethod
    def from_config(cls, cfg: Any) -> "LatentActorCritic":
        """Build from a plain dict / OmegaConf-like ``v4`` block."""
        if isinstance(cfg, ActorCriticConfig):
            return cls(config=cfg)
        if isinstance(cfg, dict):
            ac_cfg = ActorCriticConfig(
                latent_dim=int(cfg.get("latent_dim", 8)),
                lambda_gae=float(cfg.get("lambda_gae", 0.95)),
                gamma=float(cfg.get("gamma", 0.997)),
                entropy_scale=float(cfg.get("entropy_scale", 3.0e-4)),
                actor_lr=float(cfg.get("actor_lr", 1.0e-4)),
                critic_lr=float(cfg.get("critic_lr", 1.0e-4)),
                device=str(cfg.get("device", "cpu")),
            )
            return cls(config=ac_cfg)
        return cls(
            config=ActorCriticConfig(
                lambda_gae=float(getattr(cfg, "lambda_gae", 0.95)),
                gamma=float(getattr(cfg, "gamma", 0.997)),
                entropy_scale=float(getattr(cfg, "entropy_scale", 3.0e-4)),
                actor_lr=float(getattr(cfg, "actor_lr", 1.0e-4)),
                critic_lr=float(getattr(cfg, "critic_lr", 1.0e-4)),
                device=str(getattr(cfg, "device", "cpu")),
            )
        )

    def _z_tensor(self, z: np.ndarray) -> "torch.Tensor":
        z = np.asarray(z, dtype=np.float32).reshape(-1, self.config.latent_dim)
        return torch.as_tensor(z, device=self._device)

    def value(self, z: np.ndarray) -> np.ndarray:
        z_arr = np.asarray(z, dtype=np.float32)
        orig = z_arr.shape
        if z_arr.ndim == 1:
            z_arr = z_arr.reshape(1, -1)
        flat = z_arr.reshape(-1, self.config.latent_dim)
        with torch.no_grad():
            v = self._critic(self._z_tensor(flat)).squeeze(-1)
        out = v.cpu().numpy()
        if len(orig) == 1:
            return out
        if len(orig) == 2:
            return out.reshape(orig[0])
        return out.reshape(orig[0], orig[1])

    def _action_dist(self, z_t: "torch.Tensor") -> Tuple["torch.Tensor", "torch.Tensor"]:
        mean = self._actor(z_t) * float(self.config.action_scale)
        std = torch.exp(self._log_std).clamp(min=1e-4, max=2.0)
        return mean, std

    def act_latent(self, z: np.ndarray, *, deterministic: bool = False) -> np.ndarray:
        z_t = self._z_tensor(z)
        with torch.no_grad():
            mean, std = self._action_dist(z_t)
            if deterministic:
                act = mean
            else:
                act = mean + std * torch.randn_like(mean)
        return act.squeeze(0).cpu().numpy().astype(np.float64)

    def evaluate_actions(
        self, z: np.ndarray, actions: np.ndarray
    ) -> Tuple["torch.Tensor", "torch.Tensor", "torch.Tensor"]:
        """Log-prob and entropy for taken actions (diagonal Gaussian)."""
        z_t = self._z_tensor(z)
        a_t = torch.as_tensor(actions, dtype=torch.float32, device=self._device)
        if a_t.ndim == 1:
            a_t = a_t.unsqueeze(0)
        mean, std = self._action_dist(z_t)
        dist = torch.distributions.Normal(mean, std)
        logp = dist.log_prob(a_t).sum(-1)
        ent = dist.entropy().sum(-1)
        return logp, ent, self._critic(z_t).squeeze(-1)

    def update(self, rollout: ImaginedRollout) -> Dict[str, Any]:
        """One imagination AC step on a batched ``ImaginedRollout``."""
        cfg = self.config
        z = np.asarray(rollout.z, dtype=np.float64)
        acts = np.asarray(rollout.actions, dtype=np.float64)
        rews = np.asarray(rollout.rewards, dtype=np.float64)
        dones = np.asarray(rollout.done, dtype=bool)
        batch, horizon_p1, ld = z.shape
        horizon = horizon_p1 - 1

        # Flatten [B, H] steps; mask out post-done padding.
        z_flat = z[:, :horizon].reshape(-1, ld)
        a_flat = acts.reshape(-1, acts.shape[-1])
        alive = (~dones).reshape(-1)
        if not np.any(alive):
            return {"status": "skipped", "reason": "all trajectories terminated at t=0"}

        z_alive = z_flat[alive]
        a_alive = a_flat[alive]

        # Reconstruct per-trajectory alive slices for λ-return.
        vals_all = self.value(z)
        lam_targets = compute_lambda_returns(
            rews, vals_all, gamma=cfg.gamma, lambda_gae=cfg.lambda_gae, done=dones,
        )
        lam_flat = lam_targets.reshape(-1)[alive]

        target_t = torch.as_tensor(lam_flat, dtype=torch.float32, device=self._device)

        logp, ent, v_pred = self.evaluate_actions(z_alive, a_alive)

        # Critic: MSE to λ-return targets.
        critic_loss = F.mse_loss(v_pred, target_t)
        self._critic_opt.zero_grad()
        critic_loss.backward()
        nn.utils.clip_grad_norm_(self._critic.parameters(), cfg.grad_clip)
        self._critic_opt.step()

        # Actor: REINFORCE with stop-grad baseline + entropy bonus.
        with torch.no_grad():
            baseline = self._critic(self._z_tensor(z_alive)).squeeze(-1)
        adv_actor = target_t.detach() - baseline  # stop-grad on value for actor
        adv_actor = (adv_actor - adv_actor.mean()) / (adv_actor.std() + 1e-8)
        actor_loss = -(logp * adv_actor).mean() - float(cfg.entropy_scale) * ent.mean()
        self._actor_opt.zero_grad()
        actor_loss.backward()
        nn.utils.clip_grad_norm_(
            list(self._actor.parameters()) + [self._log_std], cfg.grad_clip,
        )
        self._actor_opt.step()

        return {
            "status": "updated",
            "batch": int(batch),
            "horizon": int(horizon),
            "n_steps": int(alive.sum()),
            "actor_loss": float(actor_loss.item()),
            "critic_loss": float(critic_loss.item()),
            "mean_return": float(rews.sum(axis=1).mean()),
            "mean_entropy": float(ent.mean().item()),
        }
