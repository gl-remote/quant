# Volume Spike Regime Shift · 实验计划

> **配套文档**：[strategy-math-spec.md](strategy-math-spec.md)
>
> **实验目标（r1 当前版）**：验证"1h 成交量同时段 z-score 越界"切分市场制度的效力与机制。r1 已确认因子**不是方向信号、不是制度重置**，而是**不确定性跃升 / 波动发散放大器**；后续实验围绕这个收敛后的命题做 OOS、交互效应、尾部非对称与可应用性验证。

---

## 1. 已完成阶段（r1 Stage 0–3）

| 阶段 | 结论 | 证据 |
|------|------|------|
| Stage 0 数据审计 | 26 个 1h 合约 / 12 prefix；$Z$ 重尾（kurt=16.7），5σ 实测命中率 0.97%（正态的 3.4 万倍） | workbench:volume-spike-regime-shift-r1-stage0 |
| Stage 1 全时段 z | 原口径被开盘 bar 主导（75% spike 在 09:00/21:00）；证伪原口径 | workbench:volume-spike-regime-shift-r1-stage1 |
| Stage 1.5 同时段 z | 改用同时段 rolling 后 spike 时段分布均匀；横截面显示 σ/\|r\| 放大（p<0.002，保留率 0.83–1.00） | workbench:volume-spike-regime-shift-r1-stage1_5 |
| Stage 2 ATR 控制 | BH-FDR 9 个波动度量通过；ATR 三档内 sign 一致；1:3 匹配后仍显著（ATR 解释 30–50%） | workbench:volume-spike-regime-shift-r1-stage2 |
| Stage 2.5 pre/post | 发现 pre 窗已高波动，spike 是波动簇峰值而非突变；市场强度从 0.06–0.07 降到 ~0 | workbench:volume-spike-regime-shift-r1-stage2_5 |
| Stage 3 路径分析 | **无统一方向规律**（post mean +9bps CI 含 0，跨品种 sign 不一致）；唯一稳健规律是**路径发散**（双向尾部扩张，向下更明显）；pre→post 波动相关 0.735 延续、方向相关 0.107 接近 0；\|pre_cum\|→path_disp 相关 spike 0.328 vs baseline 0.198 | workbench:volume-spike-regime-shift-r1-stage3 |

**核心命题（已收敛）**：

> 同时段 $Z\ge2$ 放量不重置市场制度，而是**在既有波动簇的峰值处放大不确定性**——前趋势越强，后 20 根 bar 路径越发散，且向下尾部扩张多于向上。因子是风险/波动率 regime gate 候选，不是方向信号。

---

## 2. 后续验证顺序

```
Stage 4 · OOS：时间半分 + LOPO（验证发散效应稳健性）
   ↓
Stage 5 · 交互效应：pre-trend × spike 的发散放大是否单调、是否独立于 ATR
   ↓
Stage 6 · 尾部非对称：向下尾部扩张的来源（跳空 / 板块 / 时段 / spike bar 跌幅）
   ↓
Stage 7 · 规格稳健性：阈值网格 + lookback N 敏感性 + 缩量对照
   ↓
Stage 8 · 可应用性：作为"风险上调 gate"的回测验证（不做方向策略）
   ↓
Stage 9 · r2 候选：更细粒度（5m/tick）、主动买卖量、跨周期
```

每阶段写数字 + 结论进 workbench 日志；未通过 gate 不进入下一阶段。

---

## 3. Stage 4 · 样本外

### 3.1 时间 OOS

- 每合约按 bar 顺序前 70% / 后 30% 切分；IS 确定全部规格（$z_0=2$、$h=20$、度量定义），OOS 冻结规格重算；
- 关键验证指标：
  1. `path_disp` 的 spike−baseline Δ：IS 与 OOS sign 一致、OOS CI 排除 0；
  2. `max_adv`（向下尾部）Δ：同上；
  3. corr(\|pre_cum\|, path_disp) 在 spike 组 OOS 仍 ≥ baseline 组；
  4. post_cum 均值仍 ≈ 0（CI 含 0），确认"无方向"结论稳健。
- 通过：1–3 全部 sign 一致且 1、2 CI 排除 0；4 保持。

### 3.2 品种 LOPO

- 每次留出一个 prefix，在其余 11 个 prefix 上估计 `path_disp` Δ 与 corr(\|pre_cum\|, path_disp)，在留出 prefix 上验证；
- 报告 LOPO 保留率（Δ sign 一致比例）；
- ≥ 70% 视为品种维度稳健；< 70% 则报告哪些品种驱动效应。

### 3.3 不做

- 不重新选阈值/后窗（r1 固定网格）；
- 不做 walk-forward 优化。

---

## 4. Stage 5 · 交互效应（pre-trend × spike）

Stage 3 发现 spike 组 corr(\|pre_cum\|, path_disp)=0.33 vs baseline 0.20，这是"放量放大前趋势张力"的初步证据。本阶段确认该交互是否独立于 ATR 与 pre 波动。

### 5.1 回归法

在 spike ∪ baseline 事件上拟合：

$$
\text{path\_disp}_i = \beta_0 + \beta_1 \mathbb{1}_{\text{spike},i}
  + \beta_2 |\text{pre\_cum}_i|
  + \beta_3 \mathbb{1}_{\text{spike},i}\cdot|\text{pre\_cum}_i|
  + \beta_4 \text{pre\_abs}_i + \beta_5 \text{atr\_pct}_i
  + \epsilon_i
$$

cluster bootstrap CI（cluster = `(symbol, session_date)`）。

判决：
- $\beta_3 > 0$ 且 CI 排除 0 → **spike 对前趋势张力的放大效应独立于前波动和 ATR**；
- 若 $\beta_3$ 在加入 $\beta_4,\beta_5$ 后消失，则发散来自前波动而非 spike。

### 5.2 分层验证

按 `|pre_cum|` 五分位切桶，在每桶内：
- 计算 spike vs baseline 的 path_disp Δ；
- 检查 Δ 是否随 `|pre_cum|` 桶单调上升。

### 5.3 pre-trend 方向分层

pre_up / pre_flat / pre_down 三桶内分别算 path_disp Δ、max_fav Δ、max_adv Δ，检验：
- 前涨时放量是否偏向下行尾部（max_adv 扩张 > max_fav）；
- 前跌时放量是否偏向上行尾部（反转对称）还是同向延续。

这能区分"不确定性对称放大"与"涨多了放量偏下杀"两种机制。

---

## 5. Stage 6 · 尾部非对称来源

Stage 3 的 max_adv DiD=−0.00158 大于 max_fav DiD=+0.00108。需要解释向下尾部为何扩张更多。

### 6.1 候选解释与检验

| 候选 | 检验 |
|------|------|
| 杠杆效应 / 波动反馈（跌时波动天然更高） | 在 baseline 内测 corr(post_cum, post_abs)，比较 spike/baseline 差异 |
| 跳空驱动（夜盘→日盘开盘 gap） | 拆含/不含隔夜跳空的事件；按 hour-of-spike 分层（21h、9h、其他） |
| 板块集中（黑色/能化偏空） | 按板块分层重做 max_adv Δ |
| spike bar 本身阴线偏多 | spike 阴/阳 × pre_trend 2×3 分层，看尾部非对称是否由阴 spike 驱动 |
| ATR 档交互 | 高 ATR 档是否单独贡献非对称 |

### 6.2 判决

- 若非对称集中在特定 hour/板块/spike 颜色 → 是结构性现象，不是通用规律；
- 若所有拆分后仍存在 → 记录为"放量后下行尾部偏厚"的稳健 empirical fact，r2 再找机制。

---

## 6. Stage 7 · 规格稳健性

### 7.1 阈值网格

在同时段口径下重算 $z_0\in\{1.5,2.0,2.5,3.0,4.0,5.0\}$ 的命中率、$n_{\text{clusters}}$、path_disp Δ、max_adv Δ、corr(\|pre_cum\|, path_disp)。

预期：发散效应随 $z_0$ 单调增强；高阈值小样本按 §2.5 降级规则处理。

### 7.2 Lookback 敏感性

$N\in\{20,60,120\}$（同时段）三种窗口重算主规格，确认发散效应不依赖短窗 σ 噪声。

### 7.3 缩量对照

$Z\le-1.0$（命中率约 0.9%）作为反向事件，检查：
- 缩量后 path_disp 是否下降（对称）或无变化（非对称）；
- 用于区分"放量=信息到达"与"偏离均值"两种解释。

### 7.4 Baseline 选择

用 $|Z|<0.5$ 主规格 vs 全样本 baseline 对照，确认结论不依赖 baseline 窗口选择。

---

## 7. Stage 8 · 可应用性（风险 gate，非方向策略）

Stage 1–7 已确认无方向 edge，**不做 Stage 5 的成本净值检验**。改为验证因子作为"风险上调 gate"的实际用途。

### 8.1 用途假设

对一个假设在 spike 后仍持仓的策略，spike 信号能否预测：

1. **未来 20 bar 的 VaR/ES 上升**：用 spike 触发的条件波动率/分位数 vs baseline 比较；
2. **止损被触发概率上升**：固定 1×ATR 止损距离下，spike 后 20 bar 内被扫损的概率是否高于 baseline；
3. **ATR 扩张**：spike 后 ATR 相对当前 ATR 的变化分布，验证是否应提高名义止损距离或减仓。

### 8.2 判决

- 若 spike 后 20 bar 内 1×ATR 止损命中率显著上升、ES 显著恶化 → 因子可作为"减仓/拉宽止损/暂停加仓"的风险 gate；
- 若止损命中率无差异（波动放大被时间分散）→ 因子只有信息价值，不直接改变风控动作。

### 8.3 产物

一份风险 gate 建议规格（在哪个 horizon、用什么阈值、触发什么动作），但**不实现策略**。若未来某个方向策略需要用，再把它当 feature 接进去。

---

## 8. Stage 9 · r2 候选（不在 r1 做）

仅在 r1 结论稳健后考虑：

- 5m / tick 数据：检验 1h spike 内部的主动买卖方向、订单流不平衡是否能解释方向；
- 跨周期：日/周线 spike 是否有同样的发散效应；
- 与其他因子交互：spike × ER 趋势强度 × ATR 档；
- 品种特异性：哪些品种 spike 效应更强、是否与板块/投资者结构相关。

---

## 9. 脚本与产物落点

```
docs/workbench/volume-spike-regime-shift/scripts/
  stage0_data_audit.py
  stage1_breadth_scan.py
  stage1_5_hour_calibration.py
  stage2_regime_attribution.py
  stage2_5_prepost_event_study.py
  stage3_path_divergence.py
  stage4_oos.py                # 待写
  stage5_pretrend_interaction.py
  stage6_tail_asymmetry.py
  stage7_robustness.py
  stage8_risk_gate.py
```

- 临时数据：`project_data/research/volume-spike-regime-shift/`（不进 git）；
- 阶段日志：`docs/workbench/volume-spike-regime-shift-r1-stageN.md`。

---

## 10. 判据速查（更新）

| 阶段 | 关键判据 | 失败动作 |
|------|---------|---------|
| Stage 4 | OOS sign 一致 + path_disp / max_adv CI 排除 0；LOPO ≥70% | 判时效/品种依赖，降级为观察 |
| Stage 5 | β3（spike×\|pre_cum\|）> 0 且排除 0；五分位单调 | 发散效应被前波动解释，缩小主张 |
| Stage 6 | 识别尾部非对称来源；若全拆分后消失则降级 | 记录为结构现象 |
| Stage 7 | 阈值/N 网格 sign 一致；缩量不矛盾 | 回到 Stage 4 重定主规格 |
| Stage 8 | spike 后止损命中率/ES 显著恶化 | 因子仅信息价值，不做风控 gate |

---

## 11. 风险与边界

- **数据短**：每合约 ~400–1400 根 1h bar，OOS 后段可能只有 ~200 spike 事件，CI 会宽；若 OOS 不显著但 sign 一致，记为"方向一致但信度不足"，不强行判过；
- **1h 无主动方向**：所有方向结论的精度受限于 K 线粒度，r2 上 tick/5m；
- **不重复 Stage 1–3 的工作**：横截面波动放大、pre/post 对比、路径发散已定性，后续只做确认与机制，不再换度量刷显著。
