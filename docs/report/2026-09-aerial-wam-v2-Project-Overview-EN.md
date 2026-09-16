# Aerial WAM v2 Project Work Report

**Reporting Period**: August 2026 — September 2026 (as of September 14)  
**Project Name**: Vision-Only Aerial World-Action-Model Navigation (Aerial WAM v2)  
**Code Repository**: `aerial-wam-v2`  
**Current Phase**: Phase-3 Outdoor–Indoor Fusion + Real-World Deployment

---

## Executive Summary

Since the project repository was spun out in mid-August, the team has built the full pipeline from foundational acceptance, outdoor long-range navigation, through to real-world system deployment. **Outdoor vision-only navigation achieved an 86.7% simulation success rate and has passed formal Phase-2 acceptance**; **integrated hardware–software real-world deployment was completed on September 14**, with full capabilities including manual/autonomous switching, camera capture, and flight-controller communication. In parallel, indoor precision flight, visual target tracking, and outdoor–indoor unified model training have advanced, forming a reusable R&D and evaluation framework.

---

## I. Project Background and Objectives

This project targets **vision-only autonomous UAV navigation**, using a camera as the primary sensor together with IMU and altitude information to build a World-Action Model (WAM) and close the loop of **perception → decision → flight**. The technical path is: **simulation validation → model training → real-world deployment**.

On **August 14, 2026**, the project was split from an existing robot-control codebase into a dedicated repository focused on aerial navigation. The WAM architecture of **RGB perception + latent world model + imagination planning + safety shield** is platform-agnostic; **after aerial navigation acceptance, the natural next step is migrating the same model stack to ground robot platforms** (see Chapter VII).

---

## II. Core Technical Principles

### (1) Problem Definition and Constraints

Navigation in unknown, partially observable environments is fundamentally a **Partially Observable Markov Decision Process (POMDP)**: goal location is unknown in advance, observations are local, the target may be invisible for long periods, and the system requires memory and multi-step decisions rather than single-frame reactive mapping.


| Capability | Meaning |
| ---------- | ------- |
| Autonomous target search | Goal location unknown; active exploration until visual detection |
| Trajectory planning | Multi-step subgoals and short-horizon action sequences built on memory and prediction |
| Active obstacle avoidance | Avoid collisions before they occur, including anticipation of imminent danger configurations |
| Navigation arrival | Approach and stably terminate after target acquisition |


**Hard sensing constraint**: exteroception is limited to a **single monocular RGB camera**; onboard flight-controller sensing (IMU, attitude, barometric/GPS altitude) uses platform-native signals and is allowed without violating the vision-only constraint. Depth cameras, stereo hardware, or global SLAM (loop-closure-corrected global metric maps) are prohibited.

### (2) Overall Architecture

The system uses a layered closed loop of **perception → memory → prediction → decision → safety**:

```text
                 Goal G (coordinates / semantic description)
                              │
RGB 224×224 ──► [1] DreamerV3 RGB Encoder (4-layer Conv) ──► embed ──┬──► [1b] DA3 depth head ──► D̂
 │              + proprio MLP ──► RSSM [h‖z] 1536-D ──► z_t ──┤      (DINOv2-ViT-L + DPT)
IMU/altitude ──► [1c] Local VIO (math integration, non-neural) ──┼──► Local metric scale
 │                                                             │
 │              [1d] FOE optical-flow τ predictor (calibrator MLP) ┼──► τ (independent safety signal)
 │                                                             │
 │                                                             ├──► [2] Hybrid memory (V2, planned)
 │                                                             ├──► [4] TorchRSSM world model
 │                                                             │       ├─ reward head (255-bin two-hot)
 │                                                             │       └─ coll_head (BCE collision risk)
 │                                                             └──► [5] Hierarchical decision & control
 │                                                                       ├─ High: AdaptiveSubgoal (20–55 m)
 │                                                                       ├─ Mid: ImaginationPlanner (H=5)
 │                                                                       │         + LatentActorCritic π
 │                                                                       └─ Low: ThreeZone safety shield
 └───────────────────────────────────────────────────────────────────────────┘

  ┌─ Offline pretraining / distillation branch (training only, not loaded at inference) ─┐
  │  RGB video sequence ──► Wan2.1 VAE Tokenizer (z_dim=48) ──► latent tokens          │
  │       │                                                                            │
  │       ├──► Video DiT ×30 layers (Wan2.2-TI2V-5B, hidden=3072) ──► pixel recon loss │
  │       └──► Action DiT ×30 layers (hidden=1024, action_dim=4) ──► joint action pred │
  │                              │                                                     │
  │                              ▼ distillation                                        │
  │                    TorchRSSM fast world model (online [4], 1536-D)                 │
  └────────────────────────────────────────────────────────────────────────────────────┘
```

Module responsibilities and model specifications:


| Module | Model Type | Network Structure / Layers | Input → Output | Production Weights |
| ------ | ---------- | -------------------------- | -------------- | ------------------ |
| **[1] Vision encoder + RSSM** | DreamerV3-style RSSM (`TorchRSSMDynamics`) | **RGB Encoder**: 4 stride-2 Conv layers (32→64→128→256 channels) + SiLU, 224→14 spatial downsample; **Proprio MLP**: Linear(4→256)+SiLU; **RSSM**: GRUCell(256→512) + 32×32 discrete stochastic latent (1024-D) + 2-layer MLP each for prior/post; **feature dim** `z = [h‖z]` = **1536-D** | RGB 224×224 + proprio4 → `z_t` [1536] | `wm_ckpt_d_full_20260828/wm_step_3500.pt` |
| **[1b] Depth head** | **DA3METRIC-LARGE** (`DA3DepthHead`) | **Encoder**: DINOv2-**ViT-L/14** (**24** Transformer layers, features from layers 4/11/17/23, dim=1024, **frozen**); **Decoder**: DPT dense prediction head (4-level fusion, out_channels=[256,512,1024,1024], features=256, **trainable**) | Single-frame RGB 224×224 → `D̂` [224×224] + `log σ` | `depth_ckpt_p45mid_s8j_20260825/depth_best_holdout_da3_ft_head.pt` |
| **[1b′] Depth head (alternative)** | U-Net trained from scratch (`_DepthHead`) | **Encoder**: 4 Conv layers (base=32, channels 32→64→128→256); **Decoder**: 4 ConvTranspose upsample + output Conv(2) (depth+logσ); supports **4-frame** RGB stack input (12 channels) | 4-frame RGB → `D̂` + `log σ` | `depth_step_5000.pt` (canonical, superseded by DA3) |
| **[1c] Local VIO** | **Non-neural** (`vio.py` math integration layer) | Velocity integration + depth reprojection scale estimation; metric consistency within rolling window, no loop closure | IMU/velocity/depth GT (supervision only) → displacement, scale | — |
| **[1d] Optical-flow ToC** | FOE flow + **calibrator** (`tau_predictor`) | Focus of expansion (FOE) + flow divergence → time to collision; `kind=foe_calibrated`, **does not pass through depth network** | Consecutive RGB frames → `τ` (seconds) | `tau_ckpt_foe_r60_20260815/tau_foe_calibrator.pt` |
| **[4] World model auxiliary heads** | Prediction heads on RSSM | **RGB Decoder**: 4 ConvTranspose layers (reconstruction supervision in training only, no pixel rendering online); **Reward Head**: Linear(1536→64)+SiLU → Linear(64→256)+SiLU → Linear(256→**255**) two-hot bins; **Coll Head**: Linear(1536→1) sigmoid; **Continue Head**: Linear(1536→1) | `z_t` + action → `(z_{t+1}, p_coll, reward, done)` | Included in WM ckpt |
| **[5a] Policy network π** | DreamerV3 λ-return Actor-Critic (`LatentActorCritic`) | **Actor MLP**: 3 layers (Linear→LayerNorm→SiLU)×2 + output, hidden=**256**; input **1540-D** = z[1536] + goal_rel[4]; output 4-D continuous action, **Tanh-bounded** distribution; **Critic MLP**: same structure, outputs scalar V(z) | `z_t` + goal_rel → `a_t` [4] | `v4_ac_ckpt_step_e_20260828/v4_ac_latest.pt` |
| **[5b] Imagination planner** | Candidate action enumeration + WM short rollout (`ImaginationPlanner`) | Roll out **H=5** imagined trajectories in WM, score with reward/coll to pick best action sequence; hard cap H≤15 | Candidate action set → optimal `a_t` | No separate weights (reuses WM + π) |
| **[5c] Safety shield** | Three-zone speed governor (`ThreeZoneSafetyShield`) | Non-neural; L1/L2/L3 speed tiers + redundant triggers from D̂/τ/p_coll + bounded state-feedback retreat | Sensors + predictions → conservative action override | — |


**[0] Wan2.2 offline pretraining (FastWAM joint, training/distillation only)**

> Wan2.2 is **not loaded** in the online closed loop; pixel-level DiT serves only as representation pretraining and distillation teacher. The fast world model `TorchRSSMDynamics` (DreamerV3 RSSM) is the runtime backbone for online `[4]`.


| Component | Model | Network Structure / Layers | Role |
| --------- | ----- | -------------------------- | ---- |
| **VAE Tokenizer** | `Wan-AI/Wan2.1-T2V-1.3B` | 3D VAE encoder–decoder; latent **z_dim=48**; `tokenizer_max_len=128` | RGB video frames → latent tokens (`in_dim=out_dim=48`) |
| **Video DiT** | `Wan-AI/Wan2.2-TI2V-5B` video branch | **30-layer** Transformer DiT; `hidden_dim=3072`, `ffn_dim=14336`; `num_heads=24`, `head_dim=128`; `patch_size=[1,2,2]`; `video_attention_mask_mode=first_frame_causal`; MoT mixed-attention | Latent video denoising / pixel-level world-model prediction (flow-matching) |
| **Action DiT** | Wan2.2 action branch | **30-layer** Transformer DiT; `hidden_dim=1024`, `ffn_dim=4096`; `num_heads=24`, `head_dim=128`; `action_dim=4` | Joint denoising with video DiT, predicts `(dx,dy,dz,dyaw)` action sequence |
| **Text conditioning** | T5 text encoder (offline cache) | `load_text_encoder=false`; uses precomputed text-embed cache (201 shards, `context_len=128`) | Language instruction conditioning (OpenFly corpus) |
| **Training schedule** | Flow Matching | `train_shift=infer_shift=5.0`, `num_train_timesteps=1000` | Shared by video / action branches |
| **Joint loss** | λ weighting | `lambda_video=1.0`, `lambda_action=1.0` | Joint training of video reconstruction + action prediction |
| **Pretrained weights** | Action DiT init | `ActionDiT_linear_interp_Wan22_alphascale_1024hdim.pt` | Action DiT linear-interpolation warm-start |
| **Distillation target** | → `TorchRSSMDynamics` | `WanImaginationDynamics` (`dynamics.py`) wraps VAE encode + `infer_joint` + decode, `**offline_only=true**`, online step prohibited | Provides offline imagined trajectories and representation supervision for 1536-D RSSM fast world model |


**Key dimensions at a glance**:


| Parameter | Value | Description |
| --------- | ----- | ----------- |
| Working resolution | 224×224 | Unified AirSim render + model input |
| RSSM deterministic state h | 512-D | GRU hidden state |
| RSSM stochastic state z | 32×32 = 1024-D | DreamerV3 discrete categorical latent |
| Policy latent z | **1536-D** | `h ‖ z` concatenation |
| Policy input (with goal) | **1540-D** | z[1536] + goal_rel[4] (body frame fwd/left/up/dist) |
| Action space | 4-D | `(dx, dy, dz, dyaw)`, Tanh-bounded, 5 Hz control |
| Imagination planning horizon | H=5 (cap 15) | ImaginationPlanner online rollout steps |
| KL loss | free-bits=1.0 nats | DreamerV3 recipe: β_pred=1, β_dyn=1, β_rep=0.1 |
| Wan2.2 VAE latent | 48-D | Video DiT `in_dim=out_dim=48`; aligned to RSSM 1536-D via distillation |
| Wan2.2 Video DiT | **30 layers**, ~5B params | Offline pixel world-model teacher, not loaded at inference |
| Wan2.2 Action DiT | **30 layers**, 1024 hidden | Offline joint action prediction, not loaded at inference |
| OpenFly training window | 17 RGB frames | `num_frames=17`, `action_video_freq_ratio=4` |
| Online deployment total params (full ckpt load) | **429M (0.43B)** | WM + π + DA3 trio; actual weights loaded on Orin companion computer |
| Online inference active params | **351M (0.35B)** | Excludes WM RGB Decoder (~78M, training-only reconstruction supervision, no pixel rendering in closed loop) |


### Model Parameter Count (Phase-2 Production Stack)

> Counting method: instantiate architecture matching current production ckpts locally (`TorchRSSMDynamics` + `LatentActorCritic` latent=1536 + `DA3DepthHead`). τ calibrator and ImaginationPlanner (<1M).

**Online deployment stack (aerial navigation mainline)**


| Module | Production Weights | Parameters | Online Inference | Notes |
| ------ | ---------------- | ---------- | ---------------- | ----- |
| **World model WM** | `wm_ckpt_d_full_20260828/wm_step_3500.pt` | **93.8M** | Partial | See breakdown below |
| ├ RGB Encoder | — | 0.69M | ✅ | 4-layer Conv vision encoder |
| ├ RSSM (GRU + discrete z) | — | 15.1M | ✅ | Online latent dynamics core |
| ├ RGB Decoder | — | 77.8M | ❌ | **Training only** RGB reconstruction supervision; closed loop does not render pixels step-by-step |
| ├ Prediction heads (reward/coll/continue) | — | 0.19M | ✅ | Imagination planning and collision risk |
| **Policy network π** | `v4_ac_ckpt_step_e_20260828/v4_ac_latest.pt` | **0.92M** | ✅ | Actor+Critic, 3-layer MLP each (hidden=256) |
| **Depth head DA3** | `depth_ckpt_p45mid_s8j_20260825/…` | **334.2M** | ✅ | Largest module in current stack |
| ├ DINOv2-ViT-L Encoder | — | 304.4M | ✅ (frozen) | Weights frozen; still forwarded at inference |
| ├ DPT Decoder | — | 29.8M | ✅ | Trainable part, outputs D̂ |
| **Deployment total (full ckpt load)** | — | **≈ 429M (0.43B)** | — | WM + π + DA3 |
| **Active inference total** | — | **≈ 351M (0.35B)** | — | Excludes 77.8M training-only Decoder in WM |


**Offline pretraining (not loaded at inference)**


| Module | Parameters | Notes |
| ------ | ---------- | ----- |
| Wan2.2 Video DiT | **~5B** | `Wan-AI/Wan2.2-TI2V-5B`, 30 layers, H100 offline joint training/distillation only |
| Wan2.1 VAE Tokenizer | **~1.3B class** | Video tokenization; not co-loaded with online RSSM |
| Action DiT (Wan2.2 action branch) | Part of joint model | 30 layers, hidden=1024, offline joint action prediction |


**Parameter distribution highlights**: in the online stack, **DA3 depth head accounts for ~78%** (334M / 429M); **policy π is only ~0.9M** — RL training updates a lightweight Actor-Critic + medium-scale RSSM, not an end-to-end 5B pixel model.

### (3) Seven Design Principles

1. **Vision-only exteroception closed loop**: geometry from learned prediction + proprioception anchoring, not depth hardware or global SLAM.
2. **Multi-pillar geometry, reject single-pillar dependence**: scale from VIO/IMU, independent safety from flow-ToC, long range from topology — do not put all avoidance and planning on depth prediction alone to avoid common-cause failure.
3. **Hierarchical decision-making**: long range via topology (which region to go to); short range via world-model imagination + predicted depth + local metric cost (how to fly there without collision).
4. **World model in the control loop**: used for short rollouts, collision anticipation, and imagination-based RL; pixel-level video prediction is for pretraining and distillation only, not online step-by-step pixel planning.
5. **Observable modes**: `SEARCH` / `NAV` / `DONE` three modes are loggable, gateable, and debuggable.
6. **Safety hard constraints override learned policy, with redundant trigger signals**: conservative actions are not left to pure value emergence; the safety shield has at least one path (flow-ToC) independent of depth prediction.
7. **Staged verifiability**: each phase has independently acceptable subsystems; do not stack the next phase until the current one passes.

### (4) Safety Shield Mechanism

The safety shield is the system's **final hard constraint**, with priority over planning and learned policy:

- **Trigger sources**: `D̂` (after uncertainty inflation) **∪** `τ` (optical-flow time to collision, independent of `D̂`) **∪** `p_coll` (world-model collision risk prediction)
- **Any threshold exceeded** → stop / bounded retreat / hover and other conservative actions
- **Design intent**: even when depth prediction fails on textureless regions, transparent objects, or strong reflections, the `τ` channel can still provide independent safety triggering, mitigating common-cause failure risk from "safety shield and world model sharing the same depth signal"

### (5) Phase-2 Navigation Decision Mode

Outdoor long-range navigation (Phase-2) uses **goal-directed + scene intent** decision mode, not traditional trajectory tracking:

- **Input**: distant goal G (primary scale 200—500 m) + current scene in view
- **No preset trajectory**: does not rely on annotated polylines or rolling reference trajectories
- **Decision flow**: WAM outer loop generates near-range intent c* from goal G and scene → Phase-1 fast execution layer → safety shield fallback → arrival criterion ‖p−G‖ ≤ 3 m
- **Global reference planning**: subgoal generation, scene-intent planning, and full-stack safety shield work together

### (6) Training and Validation Phases

Capabilities are stacked in stages; each tier has independently verifiable gate signals:


| Phase | Core Content | Pass Criteria |
| ----- | ------------ | ------------- |
| V0 | RGB encoding + multi-frame depth head + VIO | Non-collapse, approach metric rising, depth scale consistent with VIO, near-obstacle shield active |
| V1 | Fast world model + short imagination planning + τ/D̂ dual-channel safety shield | Collision rate down, multi-step rollout meets criteria, dual-channel independent verification |
| V2 | Hybrid memory + exploration policy | Coverage beats random baseline |
| V3 | Semantic grounding, SEARCH→NAV→DONE pipeline | Discovery rate and arrival rate baselines established |
| V4 | RL in world-model imagination + real-environment rollout correction | Discovery steps and arrival rate exceed behavior-cloning ceiling |


**Data principle**: inertial, dense perception, and collision signals come from simulator rollouts (not static datasets); at inference the policy consumes only RGB + proprio4; depth/IMU and other privileged signals are for training supervision only and do not leak into the policy computation graph.

### (7) Real-World Deployment Mapping

Closed-loop capabilities validated in simulation migrate to hardware via a unified interface:


| Simulation Component | Real-World Counterpart |
| -------------------- | ---------------------- |
| AirSim rendering + sensors | SJCAM 4000 USB camera + Pixhawk IMU/altitude |
| MockBridge / OpenFlyBridge | MAVLink flight-controller bridge (57600 baud, GUIDED mode) |
| Policy observation `PolicyObservation` | RGB frames + proprio4, consistent with simulation |
| Manual/autonomous switch | H12 transmitter CH7 one-key toggle |
| Data collection | Orin companion computer auto-records images + trajectory |


---

## III. Phased Work Progress

### (1) Foundational Capability (V0 / V1) — Completed


| Milestone | Date | Status |
| --------- | ---- | ------ |
| V0 four-signal acceptance | Aug 14 | Passed. Validated world model, depth estimation, geometric consistency, and safety shield; depth head and safety modules formally enabled |
| V1 online closed loop | Aug 15 | Passed. Built simulation online closed-loop stack with time-to-collision prediction, imagination planning, and dual-channel safety shield |


**Phase significance**: confirmed technical feasibility and laid groundwork for long-range navigation and real-world deployment.

---

### (2) Policy Training and Acceptance Framework (V4) — Framework Built

- Layered arrival acceptance criteria finalized August 20; **all 16 criteria signed off**
- Multiple engineering iterations on depth estimation, three-zone shield, and reward function
- Full P0—P7 evaluation chain and P4.5 data-collection merge pipeline established

**Phase significance**: established a standardized, quantifiable acceptance framework supporting subsequent iterations.

---

### (3) Outdoor Long-Range Navigation (Phase-2) — Accepted and Closed

**Objective**: outdoor 200—500 m scale autonomous navigation using only vision and goal points, without preset trajectory tracking.

**Main work**:

- Navigation architecture upgrade: from trajectory tracking to **goal-directed + scene intent** decision mode
- Deployed global reference planning, subgoal generation, scene-intent planning, and full-stack safety shield
- Online training policy integration and multiple closed-loop evaluation rounds

**Acceptance results**:

- Phase-2 formally closed **September 8, 2026**
- Outdoor navigation success rate **86.7%**
- Milestone tag: `phase2-pass-20260908`
- Representative long-range closed-loop video in **Appendix A** (Route 15, 100% route progress, 2.0 m from goal at terminus)

---

### (4) Indoor Precision Flight (Indoor 0.xm) — Plan Implemented

Under the same model architecture as outdoor, centimeter-level indoor precision flight capability was extended; completed:

- Indoor scale parameter system (0.5 m success distance, fine action constraints, reduced avoidance range)
- Pose estimation technical contract (A0) to ensure trustworthy evaluation
- Honest baseline evaluation protocol (B); Building_99 indoor scene integrated into unified training framework

**Phase significance**: opened dual-scenario path of **outdoor long-range + indoor precision flight**, preparing for Phase-3 unified model.

---

### (5) Visual Target Tracking (vgoal) — Parallel Effort

On top of coordinate navigation, extended **visual target recognition and tracking**:

- Simulation closed-loop evaluation and real-world deployment programs (`wam_vgoal_eval.py` / `wam_vgoal_deploy.py`, reusing Orin + Pixhawk hardware stack)
- Area search, dynamic follow, and other task extensions (`vgoal/search_planner.py`, `vgoal/dynamic_tracker.py`)
- Detection backends: YOLO class detection, open-vocabulary (`OpenVocabPromptDetector`), simulation GT detector
- Decoupled from mainline coordinate navigation; side repository **`aerial-vgoal-wam`** (not part of Phase-3 unified model mainline)

**Semantic navigation architecture (Method B)**: natural language / visual prompt → open-vocabulary detection → depth back-projection `goal_rel` → reuse WAM π + three-zone safety shield, **without retraining** world model and policy.

```text
instruction (Chinese/English)
  → (P2) Qwen2.5 task decomposition → visual_prompt + search_area + follow_config
  → YOLO / YOLO-World detection (same-frame rgb_yolo)
  → D̂ back-projection → goal_rel
  → FSM: SEARCH | TRACK | APPROACH | DONE
  → π(a | z, goal_rel) + ThreeZone safety shield
```

#### Qwen LLM: Instruction Decomposition Service (P2 Frontend)

> **Code location**: side repo `aerial-vgoal-wam/qwen_deploy/` (H100 deployment; **not on Orin online flight-control path**).

| Item | Description |
| ---- | ----------- |
| **Model** | `Qwen/Qwen2.5-3B-Instruct` (~**3B** parameters) |
| **Deployment** | H100 GPU, `micromamba` env `mot-wam`, `bfloat16`, single GPU `cuda:0` |
| **Service framework** | FastAPI + Uvicorn, default port **8000** |
| **Start script** | `qwen_deploy/start_h100.sh` (background `nohup`, log `server.log`) |

**External API**

| Endpoint | Purpose |
| -------- | ------- |
| `GET /health` | Service health, GPU model and memory usage |
| `POST /api/decompose` | **Main API**: natural-language task instruction → structured flight plan JSON |
| `POST /v1/chat/completions` | OpenAI-compatible chat API (general Q&A / debugging) |

**`/api/decompose` output schema** (for downstream YOLO-World / vgoal):

```json
{
  "task_type": "search_and_follow | search_only | patrol",
  "search_area": { "center_xy": [x, y], "radius_m": 30.0, "altitude_m": 25.0 },
  "target": { "visual_prompt": "blue pickup truck", "category": "truck" },
  "follow_config": { "standoff_dist_m": 6.0, "standoff_height_m": 3.0 }
}
```

System prompt requires the model to **output valid JSON directly** (including `visual_prompt` for open-vocabulary detector and `category` for COCO class filtering).

**Testing and validation**

| Test | Method | Status |
| ---- | ------ | ------ |
| Service connectivity | `qwen_deploy/client.py` calls `/health` | ✅ Script ready |
| Instruction decomposition samples | **4** built-in Chinese/English mixed test cases (search-and-follow vehicle, area patrol for person, coordinate fly-to, English industrial follow) | ✅ Script ready |
| Latency stats | Each `/api/decompose` returns `elapsed_ms` | ✅ Implemented |
| JSON parse robustness | Markdown code-block stripping + regex fallback extraction | ✅ Implemented |
| **End-to-end closed loop** (Qwen → detect → WAM flight) | Designed as semantic navigation **P2** gate | ⏳ **Not closed** (see below) |

**Example test command** (on H100, first `bash qwen_deploy/start_h100.sh`, then):

```bash
python qwen_deploy/client.py http://<h100-host>:8000
```

**Phasing and current conclusions**

| Phase | Content | Qwen Role | Status |
| ----- | ------- | --------- | ------ |
| **P0** | Building99 indoor fixed `visual_prompt` (e.g. `pillar`) + open-vocab detection + fly to standoff | **No LLM** | Checkpoint archived 2026-09-02; **task did not PASS** (root cause: YOLO false positive on gate barrier, not WAM control core) |
| **P1** | Enable search planner when target not in view | — | Plan set; pending P0 detection stability |
| **P2** | One-sentence instruction → Qwen decomposition → `visual_prompt` → search + flight | **Qwen as instruction frontend** | Service code landed; ≥3 scripted instruction end-to-end acceptance **pending** |

**P0 authoritative run summary** (125 + AirSim Building99, without Qwen):

| Config | Arrival | Collision | Conclusion |
| ------ | ------- | --------- | ---------- |
| `pillar@0.15` | 0/3 | 0/3 | `pillar` prompt too weak, zero detections |
| `column@0.05` | 0/3 | 3/3 | Detections lock onto **gate barrier rod** not real column → collision through gate |

Artifacts: `artifacts/indoor_vgoal_eval_20260902_vgoal_*_yolo640.json`; diagnostic frames in `artifacts/videos/indoor_pillar_yolo_diag_20260902/`.

**Relation to mainline**: Qwen **does not enter** Phase-2/Phase-3 coordinate navigation closed loop; only serves as language → visual prompt adapter on vgoal/semantic navigation track. Navigation core remains this repo's WAM (RSSM + π + DA3 + safety shield).

---

### (6) Outdoor–Indoor Unified Model (Phase-3) — Data and Framework Ready

**Objective**: train a single model covering outdoor long-range, indoor precision flight, and outdoor-to-indoor scene transitions.


| Sub-phase | Progress |
| --------- | -------- |
| P0 system setup | Done. Scene config, dual-gate evaluation, training scripts fully wired |
| P1 data collection | Done. **44** valid trajectories (16 outdoor, 4 indoor, 28 scene transitions) |
| P2 fusion training | In progress. Multiple training iterations done; next version (P2e) plan drafted |
| P3 acceptance evaluation | Framework integrated; execution pending training meeting acceptance criteria |


---

### (7) Real-World Deployment — System Landed September 14

Closed-loop capabilities validated in simulation migrated to real hardware; **integrated hardware–software deployment completed**:

**Hardware**


| Component | Model/Spec | Role |
| --------- | ---------- | ---- |
| Companion computer | NVIDIA Orin | WAM decision, camera capture, data logging |
| Flight controller | Pixhawk 6C | Attitude control, motor drive (ArduPilot) |
| Camera | SJCAM 4000 (USB) | Forward vision, 1080p |
| RC system | Yunzhuo H12 + R12 receiver | Manual control; CH7 one-key manual/autonomous switch |


**Software deliverables**

- Camera capture and model input preprocessing module
- MAVLink flight-controller bridge (57600 baud, GUIDED mode)
- Unified interface between real-world and simulation environments
- Manual/autonomous control handoff logic
- One-click closed-loop deployment and bench safety test program
- Automatic flight data recording (images + trajectory)

**Phase significance**: project moved from simulation to **real-world validation phase**, with full conditions for field flight tests and data collection.

---

## IV. Key Results Summary


| # | Result | Key Metrics / Notes |
| - | ------ | ------------------- |
| 1 | Outdoor vision-only long-range navigation | Simulation success **86.7%**, Phase-2 formal acceptance |
| 2 | Foundational model acceptance | V0, V1 passed consecutively |
| 3 | Acceptance criteria framework | V4: 16 criteria finalized and signed |
| 4 | Indoor precision flight plan | Scale system, pose contract, evaluation protocol implemented |
| 5 | Unified model data | Phase-3 mixed corpus 44 trajectories, including scene transitions |
| 6 | Visual target tracking | Simulation and real-world deployment programs ready |
| 7 | Qwen instruction decomposition service | `Qwen2.5-3B-Instruct` H100 API deployed; P0 semantic detection eval run; P2 end-to-end pending |
| 8 | Real-world system deployment | Orin + Pixhawk + camera + RC full stack connected |
| 9 | R&D infrastructure | Mac dev — H100 training — 125 simulation — real hardware four-tier system built |


---

## V. R&D Support Infrastructure

The team has a complete environment spanning development, training, simulation, and real hardware:

- **Development**: local Mac for code and documentation  
- **Training**: H100 cluster for model training and offline acceptance  
- **Simulation**: 125 server + AirSim for closed-loop evaluation (replaced former 110 node)  
- **Real hardware**: Orin companion + Pixhawk 6C for field validation and data collection

Environment setup, code sync, and run procedures are documented for multi-person collaboration and remote execution.

---

## VI. Next Steps

1. **Real-world flight validation**: autonomous closed-loop field flights and flight data collection under bench safety constraints
2. **Phase-3 fusion training**: advance P2e training plan toward outdoor–indoor unified model acceptance
3. **Indoor precision flight**: pose estimation upgrade and H100 targeted fine-tuning for indoor arrival accuracy
4. **Visual target tracking**: complete vgoal closed-loop validation on real hardware; explore joint navigation + tracking
5. **Qwen semantic navigation P2**: complete `qwen_deploy` end-to-end acceptance on H100 (≥3 scripted Chinese/English instructions → detection → WAM flight) and integrate into `wam_vgoal_eval` main chain
6. **Real-world data for training**: use Orin-recorded flight corpus to close the loop on real-environment model performance
7. **Ground robot platform migration**: start ground simulation adaptation and action-space rework; validate WAM cross-platform reuse (see Chapter VII)

---

## VII. Future Extension: Ground Robot Platform

After aerial Phase-2/Phase-3 acceptance, the team plans to extend the **same WAM model stack** to **ground mobile robots** (wheeled/tracked chassis, RoboMaster competition platforms, etc.) for unified **aerial + ground** embodied navigation. This project originates from the `robomaster-tt-control` ecosystem and has natural alignment with ground robot teams on hardware, simulation, and deployment.

### 7.1 Migration Motivation and Feasibility


| Dimension | Aerial (current) | Ground (planned) |
| --------- | ---------------- | ---------------- |
| Exteroception | Monocular RGB 224×224 | **Same spec** — forward/chest camera, still vision-only hard constraint |
| Decision core | TorchRSSM (1536-D) + LatentActorCritic + ImaginationPlanner | **Direct reuse**, domain-adaptation fine-tuning only |
| Geometric perception | DA3 depth head + FOE optical-flow τ | **Reuse architecture**; retrain/fine-tune on ground viewpoint and obstacle heights |
| Safety shield | ThreeZone + D̂ ∪ τ ∪ p_coll | **Reuse logic**; speed tiers and thresholds recalibrated for ground dynamics |
| Proprioception | IMU + baro/GPS altitude | Wheel odometry / IMU + **planar constraint** (fixed or slowly varying z) |
| Action space | `(dx, dy, dz, dyaw)` 4-D body frame | `(dx, dy, 0, dyaw)` or `(v_x, v_y, ω_yaw)`, **vertical dim constrained** |


Core judgment: **model layer (RSSM, π, depth head, planner) is cross-platform reusable**; mainly environment bridge (simulator/chassis driver) and action execution interface need rework, not a new world-model architecture.

### 7.2 Directly Reusable Modules

```text
  ┌─ Cross-platform reuse (aerial → ground) ─────────────────────────────┐
  │  [4] TorchRSSMDynamics (DreamerV3 RSSM, 1536-D)                        │
  │  [5a] LatentActorCritic (Tanh-bounded π + Critic)                    │
  │  [5b] ImaginationPlanner (H≤5 short imagination scoring)             │
  │  [1b] DA3DepthHead (DINOv2-ViT-L + DPT) — ground corpus fine-tune    │
  │  [1d] FOE optical-flow τ channel — forward collision-time logic unchanged │
  │  [5c] Safety shield state machine (D̂ ∪ τ ∪ p_coll redundant triggers) │
  │  [0] Wan2.2 offline pretraining pipeline — ground video corpus distill │
  │  Evaluation: P0–P7 gates, layered arrival criteria, honest baseline    │
  └────────────────────────────────────────────────────────────────────────┘
  ┌─ Platform adaptation (ground-specific) ───────────────────────────────┐
  │  env/ bridge: AirSim/Pixhawk → Gazebo/Isaac + chassis SDK            │
  │  action.py: body_delta_limits for ground max speed/angular rate      │
  │  obs.py: proprio4 → (x,y,yaw,?) or (vx,vy,vyaw,?) ground convention  │
  │  Safety shield: L1/L2/L3 distance lines and v_cruise at 1–3 m/s ground │
  │  Data collection: ground Orin + forward camera + wheel/IMU sync log  │
  └────────────────────────────────────────────────────────────────────────┘
```

### 7.3 Phased Work Plan


| Phase | Goal | Main Work | Expected Output |
| ----- | ---- | --------- | --------------- |
| **G0 Simulation adaptation** | Ground closed loop running | Integrate ground simulator (Gazebo / Isaac Sim); implement `GroundRobotBridge`; planar 3-DOF action constraint; reuse `PolicyObservation` | Ground sim env + smoke closed-loop script |
| **G1 Model migration validation** | Zero/few-shot aerial model on ground | Load aerial `step_e` π + WM ckpt; short ground scenes (10–50 m) closed-loop; compare aerial vs ground SR/collision | Cross-platform migration baseline report |
| **G2 Ground corpus and fine-tune** | Domain adaptation | Collect ground RGB + odometry + depth GT; fine-tune DA3 + optional light WM/π FT (L2-SP anchor aerial weights) | Ground-specific ckpt + Phase-G2 acceptance |
| **G3 Real deployment** | RoboMaster / UGV field validation | Orin + forward camera + chassis comm (CAN/serial/SDK); manual/autonomous switch; indoor corridor + outdoor campus | Ground closed-loop demo + aerial/ground unified eval |


### 7.4 Target Scenarios and Platforms


| Scenario | Description | Aerial capability mapping |
| -------- | ----------- | ------------------------- |
| Indoor corridor navigation | cm–m precision arrival, narrow passage avoidance | Indoor 0.xm precision; success distance can tighten to 0.3–0.5 m |
| Campus/site patrol | 50–200 m goal-directed structured outdoor | Phase-2 long-range; scale and subgoal strategy directly applicable |
| Target search and tracking | Visual semantic target + coordinate navigation | vgoal module; ground better for close-range tracking |
| Air–ground coordination (long term) | UAV reconnaissance + ground robot approach | Unified WAM weights + per-platform env adapter |


**Candidate hardware**: RoboMaster standard infantry/sentry chassis (same source ecosystem), general wheeled UGV (Orin + USB camera), small differential indoor R&D chassis.

### 7.5 Risks and Boundaries

- **Viewpoint difference**: ground camera height low (~0.3–1.0 m); obstacle geometry and sky/ground boundary differ from aerial; depth head needs dedicated fine-tune; cannot reuse aerial AbsRel gate values directly.
- **Dynamics difference**: ground robots have no vertical DOF; hard-constrain `dz=0` consistently in training/eval to avoid meaningless climb commands from aerial policy.
- **Control rate**: ground chassis often 10–50 Hz vs aerial 5 Hz; recalibrate `step_hz` and `body_delta_limits` and re-verify safety shield reaction margin.
- **Simulation foundation**: ground simulator must provide RGB + dense depth + collision + odometry GT (analogous to aerial Fork A GO/NO-GO check) before G0.

---

## Appendix A: Simulation Closed-Loop Video Evidence

Videos recorded on **125 server + AirSim ray-traced simulator**; real closed-loop flight with live telemetry HUD. Key frames and **full MP4 local copies** in `docs/report/aerial-wam-v2-仿真视频佐证/` (`videos/` subfolder); repository backup paths in table below.

### A.1 Video List


| ID | Phase | Description | Duration | Resolution | Local file (bundled) | Repository path |
| -- | ----- | ----------- | -------- | ---------- | -------------------- | --------------- |
| V1 | Step G acceptance | Route 06 ultra-long (153.7 m) dual-view: left FPV + right 3D trajectory | 17 s | 1920×720 | [V1 dual-view](docs/report/aerial-wam-v2-仿真视频佐证/videos/V1_stepg_route06_dual_view.mp4) | `artifacts/videos/route06_153m/route04_dual_view_dashboard.mp4` |
| V2 | Step G acceptance | Route 14 urban canyon first-person HUD closed loop | 25 s | 224×224 | [V2 HUD](docs/report/aerial-wam-v2-仿真视频佐证/videos/V2_stepg_route14_hud.mp4) | `artifacts/videos/route14_closed_loop/route14_closed_loop_hud.mp4` |
| V3 | Phase-2 long range | Route 15 re-anchor closed-loop HUD (100% corridor progress, for comparison) | 200 s | 224×224 | [V3 HUD](docs/report/aerial-wam-v2-仿真视频佐证/videos/V3_phase2_route15_hud.mp4) | `artifacts/videos/wam_phase2_reanchor_r15/long_route15_reanchor_hud.mp4` |
| V4 | V4 policy acceptance | Episode 13 successful arrival (first-person RGB) | 13 s | 1280×720 | [V4 arrival](docs/report/aerial-wam-v2-仿真视频佐证/videos/V4_v4_ep13_arrive.mp4) | `artifacts/videos/v4_pp8_actor_ep13_arrive_20260827.mp4` |
| V5 | V0 depth head | RGB / predicted depth D̂ / GT three-column comparison (trajectory displacement annotated) | 10 s | 672×224 | [V5 depth](docs/report/aerial-wam-v2-仿真视频佐证/videos/V5_depth_rgb_gt.mp4) | `experiments/aerial/rl/artifacts/rgb_dhat_gt_traj_10s.mp4` |


> **Step G authoritative metrics** (16 urban benchmark routes, 2026-08-28): arrival rate **93.33%** (14/15), mean route progress **97.52%**, severe collision rate **0%**, emergency takeover rate **0.80%**. See `docs/handover/WAM_STEP_G_CLOSED_LOOP_ACCEPTANCE_DECLARE_20260828.md`.
>
> **Phase-2 authoritative metrics** (16 outdoor long routes, `wam_phase2_e2_tti25_full16_20260908`): arrival rate **81.25%** (13/16).

### A.2 Key Frame Screenshots

#### V1 · Step G Route 06 — 153 m ultra-long autonomous advance (at 61% progress)

Left: onboard RGB FPV; right: 3D global trajectory (green=start, red=goal, cyan=flown path). HUD: `STATUS: AUTONOMOUS ADVANCE`, shield `SHIELD: NOMINAL`.

![Step G Route 06 dual-view dashboard](docs/report/aerial-wam-v2-仿真视频佐证/stepg_route06_153m_frame02.jpg)

#### V2 · Step G Route 14 — Urban canyon traverse

First-person HUD closed loop with step count, goal distance, forward clearance, and shield status.

![Step G Route 14 HUD closed loop](docs/report/aerial-wam-v2-仿真视频佐证/stepg_route14_hud_frame02.jpg)

#### V3 · Phase-2 Route 15 — Long-range re-anchor closed-loop HUD

Highest corridor progress in Phase-2 re-anchor batch (`step_e` + meter + polyline subgoals): `prog=100%` along reference polyline. 224×224 onboard HUD.

![Phase-2 Route 15 long-range HUD](docs/report/aerial-wam-v2-仿真视频佐证/phase2_long_route15_frame02.jpg)

#### V4 · V4 Policy Episode 13 — Successful arrival

First-person RGB of world-model imagination-driven policy completing end-to-end navigation arrival in urban scene.

![V4 Episode 13 arrival](docs/report/aerial-wam-v2-仿真视频佐证/v4_arrival_ep13_frame02.jpg)

#### V5 · V0 Depth Head — RGB / Predicted Depth / GT Comparison

Left: simulation RGB input; center: multi-frame depth head prediction D̂ (jet colormap, blue=near red=far); right: simulator GT depth. Validates V0 "depth scale consistent with VIO" perception foundation.

![V0 depth head RGB-D̂-GT comparison](docs/report/aerial-wam-v2-仿真视频佐证/depth_rgb_gt_frame02.jpg)

### A.3 Recording Notes


| Item | Description |
| ---- | ----------- |
| Simulation | AirSim Photorealistic Simulator (4090 render host 125) |
| Control rate | 5—10 Hz closed loop (matches `configs/aerial_rl.yaml`) |
| Policy stack | LatentActorDeployPolicy + ImaginationPlanner (H≤5) + ThreeZone safety shield |
| Recording scripts | `wam_phase2_record_route.py` / `v4_record_route_closed_loop.py` / `v4_record_route04_videos.py` (V1) |
| Arrival criterion | Simulation Euclidean distance ≤ 3.0 m (Phase-2 mainline) |


---

## VIII. Conclusion

The Aerial WAM v2 project achieved the critical transition from **technical validation → outdoor navigation acceptance → real-world system deployment** in roughly six weeks. Outdoor vision-only navigation has passed formal acceptance; integrated real-world hardware–software deployment is in place; outdoor–indoor unified model, indoor precision flight, and visual tracking advance in parallel. The project is in the phase of **moving from simulation to real hardware and from single-scenario to multi-scenario expansion**; **the next phase will migrate the validated WAM model stack to ground robot platforms** for unified aerial–ground embodied visual navigation, with a foundation for sustained iteration and cross-platform engineering.

---

*This report is compiled from the project code repository, git milestone records, and internal technical documentation.*
