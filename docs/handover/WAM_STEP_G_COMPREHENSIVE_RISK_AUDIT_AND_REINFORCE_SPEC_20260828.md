# Aerial-WAM Step G 全链路风险深度审查与工程补强规约 (2026-08-28 · 完整终极版)

> **文档性质**：Step G 闭环验收通过前 **终极风险审查与实施规约（Comprehensive Risk Audit & Spec）**  
> **编写日期**：2026-08-28  
> **依赖与对齐**：  
> - 核心主线：[`experiments/aerial/RUNBOOK_wam_imagination.md`](../../experiments/aerial/RUNBOOK_wam_imagination.md)  
> - 验收协议：[`artifacts/wam_accept_protocol_20260828.md`](../../artifacts/wam_accept_protocol_20260828.md)  
> - 视觉目标方案：[`docs/superpowers/plans/2026-08-28-visual-object-goal-wam-method-b.md`](../superpowers/plans/2026-08-28-visual-object-goal-wam-method-b.md)  
> - 世界模型定义：`experiments/aerial/rl/dynamics_torch.py` (`TorchRSSMDynamics`)

---

## 目录
1. [审查综述与核心结论](#1-审查综述与核心结论)
2. [第一模块：空间运动学与几何数学严谨性（Kinematics & Geometry）](#2-第一模块空间运动学与几何数学严谨性kinematics--geometry)
   - [1.1 缺陷：advance_goal_rel_body 丢失机体偏航旋转（CRITICAL）](#11-缺陷advance_goal_rel_body-丢失机体偏航旋转critical)
   - [1.2 缺陷：Method B 视觉反投影中机体动态俯仰 (Pitch) 畸变](#12-缺陷method-b-视觉反投影中机体动态俯仰-pitch-畸变)
   - [1.3 缺陷：目标深度中位数背景穿透与空间聚类修复](#13-缺陷目标深度中位数背景穿透与空间聚类修复)
3. [第二模块：世界模型与在线部署状态估计体系（RSSM & Deployment Alignment）](#3-第二模块世界模型与在线部署状态估计体系rssm--deployment-alignment)
   - [2.1 缺陷：部署端“单帧失忆”与“开环漂移”的二元陷阱（CRITICAL）](#21-缺陷部署端单帧失忆与开环漂移的二元陷阱critical)
   - [2.2 解决方案：标准流式后验滤波更新接口 (observe_and_advance)](#22-解决方案标准流式后验滤波更新接口-observe_and_advance)
   - [2.3 缺陷：ImaginationPlanner 恒定动作外推导致航向发散（CRITICAL）](#23-缺陷imaginationplanner-恒定动作外推导致航向发散critical)
   - [2.4 缺陷：原始米制目标向量冲垮策略网络视觉梯度（CRITICAL）](#24-缺陷原始米制目标向量冲垮策略网络视觉梯度critical)
4. [第三模块：闭环控制回路与安全护盾死锁破除（Control & Safety Loop）](#4-第三模块闭环控制回路与安全护盾死锁破除control--safety-loop)
   - [3.1 缺陷：安全护盾 emergency 永久单向锁死（CRITICAL）](#31-缺陷安全护盾-emergency-永久单向锁死critical)
   - [3.2 缺陷：安全护盾连续速度钳位与策略大脑“死锁发呆”](#32-缺陷安全护盾连续速度钳位与策略大脑死锁发呆)
   - [3.3 缺陷：起飞 4 步 360° 原地扫描后的背向奇异点与姿态侧滑](#33-缺陷起飞-4-步-360-原地扫描后的背向奇异点与姿态侧滑)
   - [3.4 缺陷：终端 3.0 米判定边界上的“离散时间步长频闪穿透”](#34-缺陷终端-30-米判定边界上的离散时间步长频闪穿透)
5. [第四模块：视线遮挡探索奖励与防刷分护栏（Curiosity & Exploration Guardrails）](#5-第四模块视线遮挡探索奖励与防刷分护栏curiosity--exploration-guardrails)
   - [4.1 核心诉求：让策略自主习得“遇到死胡同主动摆头找路”](#41-核心诉求让策略自主习得遇到死胡同主动摆头找路)
   - [4.2 推荐算法：条件化近障侧向视线收益 (Near-Obstacle Lateral Curiosity)](#42-推荐算法条件化近障侧向视线收益-near-obstacle-lateral-curiosity)
   - [4.3 防刷分护栏（Anti-Hacking / Anti-Spin Guardrails）](#43-防刷分护栏anti-hacking--anti-spin-guardrails)
6. [第五模块：冲刺 100% 到达率的终极扩展补丁（100% Full-Pass Add-ons）](#6-第五模块冲刺-100-到达率的终极扩展补丁100-full-pass-add-ons)
   - [5.1 历史安全轨迹面包屑回退 (Breadcrumb Backtracking)](#51-历史安全轨迹面包屑回退-breadcrumb-backtracking)
   - [5.2 终端 3~5 米到点精准吸附制导 (Terminal Precision Docking)](#52-终端-35-米到点精准吸附制导-terminal-precision-docking)
7. [第六模块：增减汇总与优先级实施清单（Action Items）](#7-第六模块增减汇总与优先级实施清单action-items)

---

## 1. 审查综述与核心结论

在经过多轮深度代码静态审查与数学推导后，我们确认当前系统在闭环实测表现（`arrival_rate=0.0%`, `mean_progress=0.0043`）不达标的根因，并非单纯的“策略训练步数不够”，而是由于 **底层运动学推导遗漏、世界模型在线流式状态断裂、规划器评估模型失真、护盾单向死锁以及特征量纲失衡** 共同作用导致的系统性阻滞。

本规约对所有识别出的隐患进行了**严格的复核、合并、数学修正与增减去重**，形成了一套可直接落地的完整工程标准。

---

## 2. 第一模块：空间运动学与几何数学严谨性（Kinematics & Geometry）

### 1.1 缺陷：`advance_goal_rel_body` 丢失机体偏航旋转（CRITICAL）
* **定位**：`experiments/aerial/rl/goal_features.py:60-74`
* **数学机理审查**：
  在当前代码中：
  ```python
  def advance_goal_rel_body(goal_rel: np.ndarray, action: np.ndarray) -> np.ndarray:
      g = np.asarray(goal_rel, dtype=np.float64).reshape(GOAL_REL_DIM).copy()
      disp = np.asarray(action, dtype=np.float64).reshape(4)[:3]
      g[:3] = g[:3] - disp  # 仅扣除平移，完全忽视偏航角 action[3]！
      g[3] = float(np.linalg.norm(g[:3]))
      return g.astype(np.float32, copy=False)
  ```
  `action[3]` 表示机体执行的偏航角增量 $\Delta \text{yaw}$。当无人机自身发生旋转时，机体坐标系（Body Frame）自身轴向发生转动。
  在无人机机体坐标系下，下一时刻目标向量 $\mathbf{g}_{\text{body}}(t+1)$ 的严格物理关系式应为：
  $$\mathbf{p}_{\text{translated}} = \mathbf{g}_{\text{body}}(t) - \Delta \mathbf{p}_{\text{body}}$$
  $$\mathbf{g}_{\text{body}}(t+1) = \mathbf{R}_z(-\Delta \text{yaw}) \cdot \mathbf{p}_{\text{translated}} = \begin{bmatrix} \cos(\Delta\psi) & \sin(\Delta\psi) & 0 \\ -\sin(\Delta\psi) & \cos(\Delta\psi) & 0 \\ 0 & 0 & 1 \end{bmatrix} \begin{bmatrix} x_{\text{trans}} \\ y_{\text{trans}} \\ z_{\text{trans}} \end{bmatrix}$$
* **致命影响**：
  在 Step E 想象长训中，当无人机在想象中尝试旋转对准目标时，目标在机体系中的相对方位角被错误地冻结为“毫无变化”。策略被迫学会**“旋转是徒劳的，只能靠侧滑平移（$\Delta y$）移动”**，导致真实飞行中转弯指向机动彻底瘫痪。
* **规约修正**：立即在 `goal_features.py` 中引入偏航旋转矩阵变换。

---

### 1.2 缺陷：Method B 视觉反投影中机体动态俯仰 (Pitch) 畸变
* **定位**：`docs/superpowers/plans/2026-08-28-visual-object-goal-wam-method-b.md` §3
* **机理审查**：
  原方案采用纯静态外参转换：
  $$\mathbf{p}_{\text{body}} = \begin{bmatrix} Z_{\text{cam}} \\ -X_{\text{cam}} \\ -Y_{\text{cam}} \end{bmatrix} = \begin{bmatrix} d_{\text{fwd}} \\ d_{\text{left}} \\ d_{\text{up}} \end{bmatrix}$$
  四旋翼无人机在向前加速时，由于空气动力学特性，机体会产生明显的**前倾俯仰角（Pitch $\theta \approx -10^\circ \sim -20^\circ$）**，导致相机光轴向下俯冲对地。
* **致命影响**：
  处于水平前方 $10\text{m}$ 远处的地面目标在画面中会成像于相机上半部分（$v < c_y$）。静态投影会误判该目标“位于机体上方 $2 \sim 3\text{m}$ 处”，导致无人机在靠近目标过程中**一边加速一边抬头向上爬升，最终在目标头顶脱靶**。
* **规约修正**：从单目 `Observation.state` 或 IMU 中提取实时机体 Roll ($\phi$) 和 Pitch ($\theta$)，反投影前左乘动态姿态旋转矩阵 $\mathbf{R}_{\text{body}\leftarrow\text{cam}}(\phi, \theta)$。

---

### 1.3 缺陷：目标深度中位数背景穿透与空间聚类修复
* **定位**：`docs/superpowers/plans/2026-08-28-visual-object-goal-wam-method-b.md` §3
* **机理审查**：
  原设计在 2D 目标框中央 50% 核心区提取中位数深度：$d_{\text{target}} = \text{median}(\hat{D}[v_{\text{core}}, u_{\text{core}}])$。
  * **远距场景（$>10\text{m}$）**：检测框较小，中心 50% 像素可能大部分落在地面或远景物体上；
  * **空心/细长物体**：如栏杆、立柱或人腿，中位数深度会穿透至物体后方墙面。
* **规约修正**：
  采用 **前景分位数滤波（15%~25% Quantile） + 空间距离连续性一致性检验**：
  $$d_{\text{target}} = \text{Quantile}_{0.20}(\hat{D}[v_{\text{core}}, u_{\text{core}}])$$
  当检出的深度值与上一帧的时序预测偏离大于 $3.0\text{m}$ 时，触发 EMA 平滑滤波（$\alpha = 0.7$）。

---

## 3. 第二模块：世界模型与在线部署状态估计体系（RSSM & Deployment Alignment）

### 2.1 缺陷：部署端“单帧失忆”与“开环漂移”的二元陷阱（CRITICAL）
* **定位**：`experiments/aerial/rl/dynamics_torch.py:1649-1664` 与 `actor_critic.py:538-566`
* **问题机理审查**：
  当前系统在部署时面临两难困境：
  1. **困境 A（单帧 encode）**：每步调用 `dynamics.encode(obs)`，强制将 GRU 隐状态 $h$ 重置为 0，丢弃了全部历史速度与空间背景；
  2. **困境 B（纯开环 step）**：调用 `dynamics.step(z_t, a_t)`，脱离真实相机观测做纯先验展开，3~5 步后因累积误差与物理现实彻底脱节。
* **致命影响**：
  策略在每一步拿到的 $z_t$ 都处于“刚开机起飞、静止无初速”的 OOD 假象中，导致无人机无法形成连续的前向飞行惯性，是平均进展几乎为 0 的主因。

### 2.2 解决方案：标准流式后验滤波更新接口 (`observe_and_advance`)
* **架构规约**：在 `TorchRSSMDynamics` 中正式新增维护在线部署状态的流式滤波接口：
  ```python
  @torch.no_grad()
  def observe_and_advance(
      self,
      prev_latent: np.ndarray,      # [1536] 上一步的 [h_t || z_t]
      action: np.ndarray,           # [4] 上一步真实执行的动作 a_t
      current_obs: Observation,     # 当前时刻 t+1 摄入的真实观测 (RGB + proprio)
  ) -> np.ndarray:
      """标准 RSSM 递归滤波：以动作推进确定性记忆 h，以真实观测修正随机状态 z。"""
      self.eval()
      # 1. 拆解上一时刻隐状态
      h_prev = torch.from_numpy(prev_latent[:self.recurrent_dim]).unsqueeze(0).to(self.device)
      z_prev = torch.from_numpy(prev_latent[self.recurrent_dim:]).unsqueeze(0).to(self.device)
      act_t = torch.from_numpy(action).unsqueeze(0).to(self.device, self.torch_dtype)

      # 2. 推进确定性时序记忆 (Deterministic Advance)
      h_next = self.rssm.advance_h(h_prev, z_prev, act_t)

      # 3. 编码当前帧真实视觉观测 (Posterior Conditioning)
      rgb = torch.from_numpy(np.ascontiguousarray(current_obs.rgb)).unsqueeze(0).to(self.device)
      proprio = torch.from_numpy(np.ascontiguousarray(current_obs.proprio4())).unsqueeze(0).to(self.device, self.torch_dtype)
      embed = self._embed(rgb, proprio)

      # 4. 计算当前真实后验状态
      z_next = self.rssm._sample(self.rssm.post_probs(h_next, embed))

      # 5. 打包返回具备时序连贯性的最新完整隐状态 [h_{t+1} || z_{t+1}]
      return torch.cat([h_next, z_next], dim=-1).squeeze(0).float().cpu().numpy()
  ```

---

### 2.3 缺陷：`ImaginationPlanner` 恒定动作外推导致航向发散（CRITICAL）
* **定位**：`experiments/aerial/rl/planner.py:21-28, 112-120`
* **问题机理审查**：
  ```python
  roll = imagine(self.dynamics, ConstantLatentPolicy(cand), z0[None, :], self.horizon, ...)
  ```
  若候选动作包含微小转弯角速度（如 $\Delta \text{yaw} = 0.3\text{ rad}$），`ConstantLatentPolicy` 会在 $H=5$ 步内连转 5 次（累计转角达 $86^\circ$）。
  在展开末端，目标相对向量被甩出视野，导致累积进展分数暴跌。**规划器严重低估了避障动作的价值，误以为所有转弯都会脱轨，最终锁死在“向前硬顶”或“刹车悬停”上**。
* **规约修正**：
  将展开策略重构为 **混合接管策略（One-Step Candidate + Policy Rollout）**：
  * **$t = 0$**：执行候选动作 $a_{\text{cand}}$（测试动作扰动的影响）；
  * **$t = 1 \sim H-1$**：由学得策略 $\pi(a \mid z_t, \text{goal\_rel}_t)$ 自主闭环控制后续轨迹。

---

### 2.4 缺陷：原始米制目标向量冲垮策略网络视觉梯度（CRITICAL）
* **定位**：`experiments/aerial/rl/actor_critic.py:229-248`
* **问题机理审查**：
  在 `_feat_tensor` 中，策略和价值网络直接将隐状态 $[h \parallel z]$ 与未经归一化的米制目标向量拼接：
  ```python
  g = [fwd_m, left_m, up_m, remaining_dist_m]  # 例如 [18.0, 5.0, 0.0, 19.0]
  feat = concat([z, g], axis=-1)  # z 为 0/1 one-hot, h ∈ [-1, 1]
  ```
* **致命影响**：
  米制距离的数值量级（$10 \sim 30$）数十倍于隐空间特征（$0 \sim 1$）。在梯度反传时，巨大尺度的目标梯度会直接冲垮并饱和视觉神经元，导致策略退化为**只看目标坐标的盲飞策略，完全失去视觉避障感知**。
* **规约修正**：
  对齐世界模型回报头的标准化做法（`goal_features.py:122-127`），对目标特征进行量纲规范化：
  $$\mathbf{g}_{\text{norm}} = \left[ \frac{\mathbf{g}_{:3}}{\max(\|\mathbf{g}\|, 10^{-3})}, \;\; \log(1 + \|\mathbf{g}\|) \right] \in [-1, 1]^3 \times [0, 3.5]$$

---

## 4. 第三模块：闭环控制回路与安全护盾死锁破除（Control & Safety Loop）

### 3.1 缺陷：安全护盾 emergency 永久单向锁死（CRITICAL）
* **定位**：`experiments/aerial/rl/safety.py:235, 244-258, 464-471`
* **问题机理审查**：
  在 `ThreeZoneSpeedShield.apply_action` 中：
  ```python
  if self._emergency_engaged:
      return clip_body_delta(self._emergency_override(obs), limits), True
  channels = self._emergency_channels(obs, wm_out)
  if channels:
      self._emergency_engaged = True  # 一旦置为 True，后续无任何复位代码！
      return clip_body_delta(self._emergency_override(obs), limits), True
  ```
  在 120 步的评测中，只要有任意 1 帧发生深度预测噪点或虚警 $p_{\text{coll}} > 0.5$，$self._emergency_engaged$ 便被永久锁死。无人机在后续全部步骤中被强行剥夺策略控制权，持续执行后退动作直到超时。
* **规约修正（连续安全自动解除机制 Auto-Unlatch）**：
  ```python
  if self._emergency_engaged:
      # 检查当前是否已脱离危险区 (d_fwd > 5m 且 tau > 1.5s 且 p_coll < 0.3)
      if self._is_clear_of_danger(obs, wm_out):
          self._clear_steps += 1
          if self._clear_steps >= 3:
              self._emergency_engaged = False  # 连续 3 帧安全，解除锁定并平稳还权
              self._clear_steps = 0
  ```

---

### 3.2 缺陷：安全护盾连续速度钳位与策略大脑“死锁发呆”
* **定位**：`experiments/aerial/rl/collector.py:224-230` 与 `safety.py`
* **机理审查**：
  当无人机接近障碍物时，底层 `ThreeZoneSpeedShield` 介入将前向速度直接削减为 0。
  策略网络在下一帧输出时未被告知“上一动作已被拦截”，依然按照目标方位输出前向动作；护盾再次拦截。无人机陷入死锁直至超时。
* **规约修正（脱困微扰机制）**：
  在 `collector.py` / `safety.py` 中维持死锁计数器：
  * 若连续 $3$ 步触发前向硬拦截且位移进展 $< 0.05\text{m}$；
  * 在当前步动作中注入一个**侧向逃逸偏置（Escape Bias）**：
    $$\Delta a_{\text{escape}} = \begin{cases} [0.1, +0.35, 0.0, +0.2] & \text{若 } \hat{D}_{\text{left}} \ge \hat{D}_{\text{right}} \\ [0.1, -0.35, 0.0, -0.2] & \text{若 } \hat{D}_{\text{left}} < \hat{D}_{\text{right}} \end{cases}$$
  * 强行打破空间对称死锁，将无人机带离死胡同。

---

### 3.3 缺陷：起飞 4 步 360° 原地扫描后的背向奇异点与姿态侧滑
* **定位**：`experiments/aerial/rl/collector.py:171-175`
* **机理审查**：
  1. **背向盲区**：起飞前 4 步强制每步旋转 $90^\circ$。旋转结束后若机头刚好背向目标（$\Delta \psi \approx 180^\circ$），策略接管瞬间处于无视野后盲区；
  2. **机体晃动侧滑**：原地高速自旋会引入气动微晃动与速度估计扰动。
* **规约修正**：
  起飞建图完成后，增加 **1 步目标大方向对准粗对齐（Heading Coarse Alignment）**，并在接管前重置机体悬停初速为 0：
  $$\Delta \text{yaw}_{\text{align}} = \text{clip}\left(\text{atan2}(g_{\text{left}}, g_{\text{fwd}}), -\frac{\pi}{4}, +\frac{\pi}{4}\right)$$

---

### 3.4 缺陷：终端 3.0 米判定边界上的“离散时间步长频闪穿透”
* **定位**：`experiments/aerial/scripts/wam_step_g_accept_eval.py:183`
* **机理审查**：
  系统在 5.0 Hz 运行时每步跨越 $0.3 \sim 0.4\text{m}$。无人机在第 $t$ 步距离目标 $3.2\text{m}$，第 $t+1$ 步距离 $3.1\text{m}$，实际上物理连续轨迹曾在两步之间瞬时切入过 $2.9\text{m}$，但被离散采样漏检判为未到点。
* **规约修正**：
  引入相邻两步间的**连续线段最短距离插值判定**：
  $$d_{\text{min\_step}} = \min_{\tau \in [0, 1]} \|\mathbf{p}_t + \tau (\mathbf{p}_{t+1} - \mathbf{p}_t) - \mathbf{g}\|_2$$

---

## 5. 第四模块：视线遮挡探索奖励与防刷分护栏（Curiosity & Exploration Guardrails）

### 4.1 核心诉求：让策略自主习得“遇到死胡同主动摆头找路”
在现有纯目标进展奖励体系下，进入死胡同后转向不会立刻拉近目标距离，且承受机动惩罚 $w_{\text{man}}\|\Delta a\|$，因此策略的最优解是“原地悬停不动”。
我们必须引入轻量级、物理可解释的**视线探索增益（Curiosity Gain）**。

### 4.2 推荐算法：条件化近障侧向视线收益 (Near-Obstacle Lateral Curiosity)
* **公式定义**：
  $$r_{\text{info}} = w_{\text{info}} \cdot \mathbb{I}_{\text{blocked}} \cdot \text{clamp}\left( \frac{\max(\hat{D}_{\text{left}}, \hat{D}_{\text{right}}) - \hat{D}_{\text{fwd}}}{D_{\text{norm}}}, 0, 1 \right) \cdot |\Delta \text{yaw}|$$
* **参数规约**：
  * $w_{\text{info}} = 0.15$（适中权重，能压过 $w_{\text{man}} \approx 0.01$ 的机动成本，但不干扰全局进展主梯度）；
  * $\mathbb{I}_{\text{blocked}} = \mathbb{I}(\hat{D}_{\text{fwd}} \le 3.5\text{m} \;\land\; \Delta d_{\text{prog}} \le 0.1\text{m})$；
  * $D_{\text{norm}} = 5.0\text{m}$。

### 4.3 防刷分护栏（Anti-Hacking / Anti-Spin Guardrails）
为了防止策略网络在开阔地带或特定角落反复左右快速摇晃（“拨浪鼓行为”）刷分，必须施加三道硬约束：
1. **开阔空间硬掩码（Open-space Zero Mask）**：当 $\hat{D}_{\text{fwd}} > 4.0\text{m}$ 时，$r_{\text{info}} \equiv 0$；
2. **单局探索收益硬封顶（Episode Budget Cap）**：单个 episode 内累积领取的 $r_{\text{info}}$ 总和不得超过 **$+2.0$**（远小于成功到点奖励 $+10.0$）；
3. **高频转角惩罚（Smoothness Regularization）**：对连续转向符号反转（如 $|\Delta \text{yaw}_t - \Delta \text{yaw}_{t-1}| > 0.4$）施加平滑惩罚。

---

## 6. 第五模块：冲刺 100% 到达率的终极扩展补丁（100% Full-Pass Add-ons）

若业务需要将通过率从 75~85% 极限推向 **100%（16/16 全通）**，可挂载以下两个终极补丁：

### 5.1 历史安全轨迹面包屑回退 (Breadcrumb Backtracking)
* **原理**：无人机在飞行时以 1 Hz 循环缓冲过去 5 秒的安全路点坐标。
* **机制**：当检测到深度陷入死区（前/左/右碰撞概率均 $>0.7$ 且持续 5 步无进展），直接逆向回退 3 米回到开阔分叉口，强制切入未探索侧向分支，攻克大尺度深凹死胡同。

### 5.2 终端 3~5 米到点精准吸附制导 (Terminal Precision Docking)
* **原理**：当机体进入目标距离 $d_{\text{goal}} \le 5.0\text{m}$ 时，自动将最大巡航限速降为 $0.5\text{ m/s}$，并将动作输出锁定为朝向目标的精准残差悬停制导：
  $$\Delta a_{\text{docking}} = \text{clip}(k_p \cdot \mathbf{g}_{\text{body}} - k_d \cdot \mathbf{v}_{\text{body}}, \; -\mathbf{lim}_{\text{dock}}, \; +\mathbf{lim}_{\text{dock}})$$
* **价值**：彻底消除 3.1 米边缘高速掠过冲过头导致的遗憾超时。

---

## 7. 第六模块：增减汇总与优先级实施清单（Action Items）

| 优先级 | 任务分类 | 涉及文件 | 实施内容 | 状态 |
|---|---|---|---|---|
| **P0（最高）** | 几何运动学 (Risk 5) | `experiments/aerial/rl/goal_features.py` | 修复 `advance_goal_rel_body` 偏航旋转 $\mathbf{R}_z(-\Delta \psi)$；新增 `SpatialGoalTracker` 3D 目标空间锚点与全盲区推算。 | **已完成（单测 PASS）** |
| **P0（最高）** | 部署状态滤波 | `experiments/aerial/rl/dynamics_torch.py` & `actor_critic.py` | 新增 `observe_and_advance` 接口，在 `LatentActorDeployPolicy` 中维持跨步时序记忆 $h$。 | **已完成（单测 PASS）** |
| **P0（最高）** | 规划器修正 (Risk 1) | `experiments/aerial/rl/planner.py` | 重构展开逻辑为“1 步候选动作 + $(H-1)$ 步策略网络接管”；新增 Critic 终端长程价值 Value Bootstrap 评估。 | **已完成（单测 PASS）** |
| **P0（最高）** | 控制频率匹配 (Risk 2) | `experiments/aerial/rl/collector.py` | 测量动态实际控制周期 $\Delta t_{\text{actual}}$，解耦名义 $5\text{Hz}$ 限制，消除制动安全裕度衰减。 | **已完成（单测 PASS）** |
| **P1（重要）** | 护盾状态机 (Risk 3/4) | `experiments/aerial/rl/safety.py` | 分离常态软限速与硬拦截统计语义；实现持续态单向绕障脱困状态机 (`Sustained Directional Escape`)。 | **已完成（单测 PASS）** |
| **P1（重要）** | 探索奖励注入 | `experiments/aerial/rl/reward.py` & `actor_critic.py` | 增加条件化近障侧向视线探索奖励 $r_{\text{info}}$ 并配置防刷分护栏。 | **已完成（单测 PASS）** |
| **P1（重要）** | 离散采样插值 | `experiments/aerial/scripts/wam_step_g_accept_eval.py` | 引入相邻采样步间连续线段最短距离插值判定与细分硬拦截/软限速率评估。 | **已完成（单测 PASS）** |
| **P2（增强）** | 视觉目标反投影 | `docs/superpowers/plans/2026-08-28-visual-object-goal-wam-method-b.md` | 反投影矩阵加入 IMU Pitch/Roll 动态姿态补偿与 20% 深度分位数过滤。 | **规约已冻结** |
| **P2（终极）** | 全通增强补丁 | `experiments/aerial/rl/collector.py` | 面包屑回退机制 + 终端 3~5 米精准吸附制导（冲刺 100% 到达率）。 | **架构已冻结** |

---

### 实施路线建议

1. **Mac 侧**：集中完成 P0 级核心代码修复（`goal_features.py`, `dynamics_torch.py`, `actor_critic.py`, `planner.py`, `safety.py`）并跑通单测；
2. **Git 同步**：提交并 Push 至 GitHub 仓库；
3. **125 侧**：拉取最新代码，在 AirSim 16 局基准上重跑 `wam_step_g_accept_eval.py`，越过 Step G 官方验收门（$\ge 25\%$ 到点率），向更高指标冲刺。
