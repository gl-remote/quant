# time-barrier-selection · Experiment Plan

> 状态：🧊 已冻结（2026-07-31，随 Stage 1 整批归档）· 方向修正为跨周期对比，见 `cross-period-plan.md`
> 目标：**纯描述性扫描**——在 5m 周期上，"市场强度"（$|s|(T)=|\mu_T|/\sigma_T$ 与 $z(T)=\mu_T/\sigma_T$）随持仓窗口 $T$（bar 数）是否呈现可识别的曲线形态
> 首个实验对象：**玉米 DCE.c 5m**
>
> ⚠️ **本实验不引入塑形容器** $(K_S, K_T, T)$——不做 FPT、不开仓、不扣成本，只统计 raw per-bar return 序列在 $T$ bar 窗口内的 $|\mu|/\sigma$ 形态。
> 上游塑形理论（`theorem:structural-shaping-alpha#when-barrier-shaping-yields-alpha` 定义 4.4 的 $T^\ast = \max(K_S, K_T)^2/\sigma^2$ 分界）只作为"曲线在该 $T$ 处是否落入长期区 / 过渡区 / 短期区"的解释工具，**不作为本实验的判据**。

## 1. 核心研究问题

给定 5m 周期上的 raw per-bar log return 序列 $\{r_i\}$，对每个窗口长度 $T \in \{T_1, T_2, \dots\}$（以 5m bar 为单位），在所有 rolling $T$-bar 子序列上计算

$$
|s|(T) \;=\; \frac{|\mu_T|}{\sigma_T}, \qquad
z(T) \;=\; \frac{\mu_T}{\sigma_T}
$$

其中 $\mu_T$、$\sigma_T$ 是窗口内 $T$ 个 per-bar log return 的均值与标准差。**主问题**：

> 玉米 5m 的 $|s|(T)$ 与 $z(T)$ 随 $T$ 增大呈现什么形态——单调衰减？先升后降的平台？幂律？震荡？

### 1.1 从属问题

- **Q1（尺度定位）**：$|s|(T)$ 是否在某个 $T$ 附近进入"平稳平台"（即短期记忆消失后的随机游走区）？若存在平台起点 $T_\text{plateau}$，与 `theorem:structural-shaping-alpha#when-barrier-shaping-yields-alpha` 定义 4.4 的 $T^\ast = \max(K_S, K_T)^2/\sigma_{5m}^2$（在不固定 $(K_S, K_T)$ 的前提下，仅参考其 $\propto 1/\sigma^2$ 的尺度关系）落在什么量级？
- **Q2（短期记忆方向）**：小 $T$（如 $T \le 5$）下 $|s|(T)$ 是否显著大于大 $T$（如 $T \ge 100$）下的 $|s|(T)$？若小 $T$ 端 $|s|$ 显著更大，说明 5m 序列存在短期趋势/均值回归结构；否则为接近 i.i.d. 的弱市场结构。
- **Q3（跨合约稳定性）**：在 c2401 … c2609 多个 5m 主力合约上，$|s|(T)$ 曲线形态是否一致（仅量级差异）？

## 2. Stage 1 · 玉米 5m $|s|(T)$ 形态扫描

### 2.1 数据

- 品种：`DCE.c`（玉米，size=10, tick=1.0, commission=1.21，`workspace/common/contract_specs.py` 已注册）
- 合约：所有可用 5m 主力（c2401 … c2609，共 9+ 个合约）· **每合约独立处理**（遵循 `quant-research-methodology` §9.2 · KF-22 数据边界）
- 周期：5m
- 时间窗口：每合约完整寿命（不做跨合约池化）
- 数据预处理：取每根 5m K 线的 close-to-close log return $r_i = \log(p_{i+1}/p_i)$；**不开仓、不扣成本、不引入方向**，与交易完全脱钩

### 2.2 扫描维度

本节对每个 (合约, $T$) 报告 $\widehat{|s|}(T)$、$\widehat{z}(T)$ 等指标；$T$ 网格定义如下。

- **维度**：窗口长度 `T`（5m bar）
- **候选值**：`{5, 13, 34, 89, 233, 610, ∞}`
- **备注**：Fibonacci 精简，6 个点 + `∞`；覆盖 5m 上 25 分钟 … 50 小时
- **T 网格补充说明**：
  - `∞` 行作为参考基线，对应全合约寿命的整体统计（即 §1 中 $T \to \infty$ 极限），便于发现 $T$ 维有限窗口下的"偏差"；
  - 玉米 5m 每日 ~69 bar，T > 60 时 rolling 窗口必跨日——本实验在 §2.3 改用"按周 cluster + 跨周 rolling"承载大 T；
  - Fibonacci 序列是经验选择（对数尺度均匀）；若 §2.5 形态归类显示拐点在某区间，按需局部加密（候选补 `T ∈ {55, 89, 144, 233}`）。

记号约定（下文 §2.4 / §2.5 沿用）：

$$
\widehat{|s|}(T) \;=\; \frac{|\mu_T|}{\sigma_T}, \qquad
\widehat{z}(T) \;=\; \frac{\mu_T}{\sigma_T}
$$

其中 $\mu_T$、$\sigma_T$ 是滚动 $T$-bar 窗口内 per-bar log return 的均值与标准差。

### 2.3 采样方法（推荐：cluster bootstrap，按周重抽样）

按现有项目惯例（`structural-shaping-alpha` gatekeeper 经验、`quant-research-methodology` §5.2），**推荐 cluster bootstrap 按周重抽样**：

1. **cluster 划分**：每周（周一至周日）的所有 5m bar 视为一个 cluster（intra-week 内日历自相关 + 周末休市间断天然存在），玉米 5m 每周约 5 × 69 ≈ 345 bar；跨周视为近似独立。
2. **rolling 窗口归属**：对每条 bar-by-bar 的跨周 rolling 窗口，把该窗口的 cluster 标签记为"窗口内 bar 数过半所在的那一周"——保证每个窗口归属于唯一一个 cluster。
3. **点估计**：对每个 `(合约, T)`，取所有 rolling $T$-bar 窗口的 $\mu_T$、$\sigma_T$，按窗口平均得到 $\widehat{|s|}(T)$、$\widehat{z}(T)$。
4. **CI 估计**：cluster bootstrap $B=1000$ 次，每次按周（有放回）重抽 cluster 集合，将抽中 cluster 内的所有 5m bar 拼成新序列，重新跑 rolling $T$ 流程，得到 $|s|(T)$ 与 $z(T)$ 的 95% CI。
5. **替代方案（备选）**：
   - **按日 cluster + 仅日内 rolling**：T 必须 ≤ 69，且 cluster bootstrap 区间宽度对应"日"层级不确定性，比"周"更紧；可作为 T ≤ 60 的子网格补充报告；
   - **不重叠窗口**：样本量随 $T$ 增大快速下降，$T=610$ 时可能不足 30 窗口，**仅作 sanity check**。

### 2.4 报告指标

对每个 `(合约, T)`，报告下列指标。指标定义见下方公式块；表格里只放纯文本代号，避免 LaTeX 与 markdown 表格冲突。

| 类别 | 代号 | 计算 | 用途 |
|------|------|------|------|
| 主指标 | `s_abs_hat(T)` | 见下方公式 (1) | 曲线主轴 |
| 主指标 | `CI95_s_abs` | cluster bootstrap 上下界 | 区间宽度反映样本量与稳定性 |
| 主指标 | `z_hat(T)` | 见下方公式 (2) | 与 `s_abs_hat(T)` 对照（仅差符号方向） |
| 主指标 | `CI95_z` | cluster bootstrap 上下界 | 验证 `s_abs` 的非零性 |
| 辅助 | `n_windows` | rolling 窗口总数 | 样本量；`n_windows >= 30` 才作形态判断 |
| 辅助 | `n_indep_days` | 独立日数 | cluster bootstrap 重抽样基数；`>= 30` 为最小门槛 |
| 辅助 | `rho_1` | per-bar return 的一阶自相关 | 5m 短期记忆强弱的辅助判据 |

主指标定义：

$$
\widehat{|s|}(T) = \frac{|\mu_T|}{\sigma_T} \tag{1}
$$

$$
\widehat{z}(T) = \frac{\mu_T}{\sigma_T} \tag{2}
$$

判定门槛（用于判断指标值是否"可作形态判读"）：

$$
n_{\text{windows}} \ge 30, \quad n_{\text{indep\_days}} \ge 30
$$

**sanity check（必做）**：

1. **白噪声对齐**：在人工合成的 i.i.d. $N(0, 1)$ 序列（长度 = 实际 5m bar 数）上跑同样流程，$\widehat{|s|}(T)$ 应随 $T$ 增大以 $\propto 1/\sqrt{T}$ 衰减（无短期记忆下的小数定律），用于校准本流程的 baseline 形态。
2. **AR(1) 已知解**：在 $\phi \in \{0, 0.3, 0.6\}$ 的人工 AR(1) 序列上跑同样流程，与 $\widehat{|s|}(T)$ 的解析曲线对照，验证 pipeline 对短期记忆的检测能力。

### 2.5 形态描述（不预设假设，事后总结）

实验完成后，按下列四种形态**描述**观察到的曲线，**不做 H0/H1 检验**（避免把描述性扫描变成假设检验）。每种形态给出判据公式 + 散文化解释；§2.5 末附**形态汇总表**便于一眼对照。

**形态 A · 单调衰减**

判据：

$$
\log \widehat{|s|}(T) = -\alpha \log T + \beta, \quad R^2 \ge 0.8, \quad \alpha \in (0, 1)
$$

即对所有 `T` 在 log-log 坐标上做线性回归，$R^2 \ge 0.8$ 且斜率 $-\alpha$ 落在 $(-1, 0)$ 内。**解释**：5m 序列接近 i.i.d.，短期记忆弱。

**形态 B · 平台 + 衰减**

判据：

$$
\exists \, T_{\text{plateau}} : \quad
\widehat{|s|}(T) \approx \text{const} \;\; \forall T \le T_{\text{plateau}}, \quad
\widehat{|s|}(T) \text{ 严格单调递减} \;\; \forall T > T_{\text{plateau}}
$$

**解释**：5m 存在短期记忆窗口；$T_{\text{plateau}}$ 即"短期区"边界。

**形态 C · 先升后降**

判据：

$$
\exists \, T^\dagger : \quad
\widehat{|s|}(T^\dagger) > \widehat{|s|}(T) \;\; \forall T \ne T^\dagger, \quad
\text{且两侧差值} > 2 \cdot \mathrm{CI}_{95\%}\text{ 半径}
$$

**解释**：5m 存在"共振周期"或 microstructure 噪声（值得另行研究）。

**形态 D · 单调上升 / 震荡**

判据：不符合形态 A / B / C 中的任何一种。**解释**：5m 上存在显著 drift 或 regime 切换（与 strength-regime-switching 主题相关）。

**形态汇总表**

| 形态 | 判据公式 | 拟合 / 检测要求 | 经济解释 |
|------|---------|----------------|---------|
| A · 单调衰减 | 见上 (A) | log-log 线性 `R^2 >= 0.8` 且 `α ∈ (0, 1)` | 5m 序列接近 i.i.d.，短期记忆弱 |
| B · 平台 + 衰减 | 见上 (B) | 存在拐点 `T_plateau`，`T > T_plateau` 段严格单调递减 | 5m 存在短期记忆窗口；`T_plateau` 即"短期区"边界 |
| C · 先升后降 | 见上 (C) | 局部极大值 `T_dagger` 两侧差值均 `> 2 · CI95` 半径 | 5m 存在"共振周期"或 microstructure 噪声 |
| D · 单调上升 / 震荡 | 排除法 | 不符合 A / B / C 中任何一种 | 5m 上存在显著 drift 或 regime 切换 |

### 2.6 成本与方向

按用户明确要求：

- **不扣交易成本**——本实验是市场结构描述，不评估策略；
- **不引入方向**——只统计 raw per-bar return 序列的 $|\mu|/\sigma$，与 long/short 无关。

### 2.7 输出与工作目录

- 工作目录：`docs/workbench/time-barrier-selection/`
- 脚本：`docs/workbench/time-barrier-selection/scripts/`（临时研究脚本，遵循 `quant-project` 的 AI 临时资产规则）
- 结果输出：`docs/workbench/time-barrier-selection/outputs/`
- 主实验报告：`docs/workbench/time-barrier-selection-stage1.md`（或按大主题拆多份放入 `docs/workbench/time-barrier-selection/`）

### 2.8 判定规则（Stage 1 通过 / 失败 / 降级）

本实验是**描述性扫描**，不存在"通过 / 失败"的二值判定；改为"完成度"判定：

- **完成**：所有合约的 $|s|(T)$ 与 $z(T)$ 曲线均已绘出，CI 全部报告，sanity check 通过，且按 §2.5 四种形态之一给出归类描述；
- **降级 A（样本不足）**：部分合约 $n_\text{indep\_days} < 30$ 或 $n_\text{windows} < 30$；降级标注，不强行归类；
- **降级 B（形态不收敛）**：四种形态均不适用（如曲线剧烈震荡无规律）；如实记录，作为"5m 周期市场结构复杂"的方法论证据登记到 research-status.md。

## 3. Stage 2（预告，Stage 1 完成后启动）

- 跨品种扫描：将玉米 5m 的 $|s|(T)$ 曲线形态与其他 DCE / CZCE / SHFE 品种对照，验证"5m 上市场强度曲线形态是否品种无关";
- 跨周期扫描：在 1m / 15m / 1h 上重复同样流程，验证"5m 上的形态是否仅在 5m 出现"——为 strength-regime-switching 主题的 `archive:2026-07-21-strength-regime-switching` 跨周期结论补充分时尺度证据。

## 4. Stage 3（预告，Stage 2 完成后启动）

- 引入塑形容器（$K_S, K_T$）重新读 $\mathbb{E}[E_\text{net}]$，把 $|s|(T)$ 的描述性结论升级为"在 $|s|(T)$ 平台区，塑形容器更可能实现 $\mathbb{E}[E_\text{net}] > 0$"的命题；
- 此时才进入 `theorem:structural-shaping-alpha#when-barrier-shaping-yields-alpha` 定义的 $T^\ast_\text{PL}$ 完整回填。

## 5. 已知风险与判定护栏

- **风险 A（短期记忆 vs microstructure 噪声混淆）**：5m 上 $|s|(T)$ 的"先升后降"形态可能是 microstructure bid-ask bounce 造成，而非真实趋势；需结合 §2.4 的 $\rho_1(r)$ 辅助判据。
- **风险 B（合约活跃期不一致）**：c2401 … c2609 寿命长度差异大，$T$ 很大时小合约样本量不足；按 §2.8 降级标注。
- **风险 C（Fibonacci `T` 网格粒度）**：精简后 `T ∈ (50, 100)` 区间无采样点，若该区间出现拐点可能漏检；首轮扫描后若曲线在该区间疑似变化，按需局部加密（如补 `T ∈ {55, 89, 144}`）。
- **风险 D（CI 解读误用）**：本实验的 cluster bootstrap CI 反映"同一品种 5m 序列在 $T$ 窗口上的统计不确定性"，**不可外推为"不同周期 / 不同品种"的 CI**——Stage 2 才能做品种间对照。
