# time-barrier-selection · Experiment Plan

> 状态：活跃 · Stage 1 待执行
> 目标：回答"单合约持仓多少 bar 能让单笔期望净收益覆盖交易成本"
> 首个实验对象：**玉米 DCE.c 5m**

## 1. 核心研究问题

给定塑形容器 $(K_S, K_T, T)$ 与真实成本 $c$，在 5m 周期上找到 $T \in \{T_1, T_2, \dots\}$ 使得

$$
\mathbb{E}[E_{\text{net}}(T; K_S, K_T)] = \mathbb{E}[X_{\tau \wedge T}] - 2c > 0
$$

**同时**回答三个从属问题：

- **Q1（存在性）**：$T^\ast_{\text{PL}} := \min\{T : \mathbb{E}[E_{\text{net}}] > 0\}$ 是否存在？（可能不存在，即所有 $T$ 下期望都为负）
- **Q2（尺度定位）**：$T^\ast_{\text{PL}}$ 与 `theorem:structural-shaping-alpha#when-barrier-shaping-yields-alpha` 定义 4.4 的 $T^\ast = \max(K_S, K_T)^2/\sigma_{5m}^2$（"短期/过渡/长期"分界）落在什么比例关系？
- **Q3（time-exit 占比）**：$\mathbb{P}(\tau = T)$（time-exit 概率）在最优 $T$ 附近的取值——按 KF-14 跨周期 time-exit 不变性 (`theorem:structural-shaping-alpha#when-barrier-shaping-yields-alpha` 附录 A)，$\mathbb{P}(\tau = T) < 5\%$ 应对应"长期区"。

## 2. Stage 1 · 玉米 5m 广度扫描

### 2.1 数据

- 品种：`DCE.c`（玉米，size=10, tick=1.0, commission=1.21，`workspace/common/contract_specs.py` 已注册）
- 合约：所有可用 5m 主力（c2401 … c2609，共 9+ 个合约）· **每合约独立处理**（遵循 `quant-research-methodology` §9.2 · KF-22 数据边界）
- 周期：5m
- 时间窗口：每合约完整寿命（不做跨合约池化）

### 2.2 参数网格

| 维度 | 候选值 | 备注 |
|------|-------|------|
| $K_S$（止损，ATR）| $\{0.75, 1.0, 1.5, 2.0, 2.5, 3.0\}$ | ATR 归一化 · 下界 0.75 来自 KF-23 跳空修正 |
| $R = K_T/K_S$ | $\{1.0, 1.5, 2.0, 3.0\}$ | $R=1$ 作为 Doob 保守律 sanity check（应恒为 $-2c$）|
| $T$（时间上限，5m bar）| $\{20, 40, 80, 160, 320, 640, \infty\}$ | 覆盖 5m 上"短期到长期区"· $\infty$ 对应 FPT 无限时间 |

**入场规则**：**随机入场 DirRandom**（每个 bar 独立均匀采样 long/short 各 50%，seed 固定），复用 `structural-shaping-alpha` Stage 1 的 gatekeeper 惯例——本主题**不引入方向筛选**（通道 A）。

**出场规则**：first-passage exit at $\tau = \min(\tau_{K_S}, \tau_{K_T}, T)$，close 价近似（不做 tick-level 撮合）。

### 2.3 判据

对每个 $(K_S, R, T)$ combo，报告：

| 指标 | 计算 | 判据 |
|------|------|------|
| $n_\text{events}$ / $n_\text{indep\_days}$ | event 数 / 独立日 数（cluster 单位）| $n_\text{indep\_days} \ge 30$ 才作决策 |
| $\bar{E}_\text{gross}$ | 平均单笔毛收益（ATR）| 参考量 |
| $\bar{E}_\text{net}$ | $= \bar{E}_\text{gross} - 2c$（$c$ 按真实成本模型） | **主判据**：> 0 视为"cost-cover"通过 |
| $\mathrm{CI}_\text{95\%}(\bar{E}_\text{net})$ | cluster bootstrap（cluster 单位 = `(contract, date)`）| CI 下限 > 0 视为显著 |
| $\mathbb{P}(\tau = T)$ | time-exit 占比 | Q3；< 5% 表示 5m 上 $T$ 已入长期区 |
| $\mathbb{E}[\tau]$ | 平均持仓 bar 数 | 用于回填 Q1 的 $T^\ast_{\text{PL}}$ |

**成本模型**：真实成本（`workspace/common/contract_specs.py` 中 `c` 品种：commission=1.21 × broker_markup=2.0 → ×3=3.63 元/手/单边 + 滑点 $= \text{size} \times \text{tick} \times \text{slip\_tick} = 10 \times 1.0 \times 0.5 = 5$ 元/手/单边），按 entry 价换算为 ATR 单位。参照 `quant-research-methodology` §5.1 硬约束——**跨合约判决必须用真实成本**，禁止扁平 0.05 ATR 简化。

### 2.4 sanity check（在跑主实验前必做）

1. **Doob 保守律核对**：$R = 1$（$K_S = K_T$）+ DirRandom + $T = \infty$ 应给出 $\bar{E}_\text{net} \approx -2c$；若显著偏离，说明数据/成本模型有 bug。
2. **Fourier null 核对**：$\nu = 0$ 假设下（DirRandom），$P_\text{win}^\text{finiteT}$ 应匹配 `theorem:structural-shaping-alpha#when-barrier-shaping-yields-alpha` 命题 6.1 的级数值。

### 2.5 输出与工作目录

- 工作目录：`docs/workbench/time-barrier-selection/`
- 脚本：`docs/workbench/time-barrier-selection/scripts/`（临时研究脚本，遵循 `quant-project` 的 AI 临时资产规则）
- 结果输出：`docs/workbench/time-barrier-selection/outputs/`
- 主实验报告：`docs/workbench/time-barrier-selection-stage1.md`（或按大主题拆多份放入 `docs/workbench/time-barrier-selection/`）

### 2.6 判定规则（Stage 1 通过/失败/降级）

- **通过**：至少一个 combo 满足 $\bar{E}_\text{net} > 0$ 且 CI_95% 下限 > 0 且 $n_\text{indep\_days} \ge 30$；此时**记录 $T^\ast_\text{PL}$、time-exit%、$\mathbb{E}[\tau]$**，进入 Stage 2（跨品种广度扫描）；
- **失败**：所有 combo $\bar{E}_\text{net} \le 0$ 或 CI 下限均不显著；此时判定"玉米 5m 无有效持仓周期"，冻结或换周期（1h / daily）；
- **降级**：$\bar{E}_\text{net}$ 名义值为正但 CI 不显著，或依赖极小样本；此时**不作决策**，扩展到更多合约或延长历史（不池化）。

## 3. Stage 2（预告，Stage 1 通过后启动）

- 跨品种广度扫描：将玉米 5m 的最优 $(K_S, R, T)$ 组合应用到其他 DCE / CZCE / SHFE 品种，验证 $T^\ast_\text{PL}$ 的品种依赖；
- 目标：验证假设 H3（$T^\ast$ 与 $\sigma_\text{bar}$ 的反相关关系）。

## 4. Stage 3（预告，Stage 2 通过后启动）

- 参数稳健性 + Walk-Forward 时间样本外验证（`quant-research-methodology` §6）；
- 通过后再考虑引入通道 A（方向筛选）与仓位管理，进入组合层。

## 5. 已知风险与判定护栏

- **风险 A**：玉米 5m 可能位于"过渡区"（$T/T^\ast \in (1, 3]$）——time-exit 占比 $\in [10^{-4}, 0.3]$——此时判据必须显式包含 time-exit 事件的期望贡献；
- **风险 B**：5m 上真实成本占 ATR 比例可能过大，导致 $x_\min$ 门槛超过品种 $|s|$ 分布上限——按 `theorem:structural-shaping-alpha#when-barrier-shaping-yields-alpha` 定理 11.3 与 §11.5，Stage 1 应同步报告品种 $|s|$ 的分布 $D$，为下一阶段"识别器 se 目标"提供先验；
- **风险 C**：DirRandom 下 $\bar{E}_\text{net}$ 恒 ≤ $-2c$（Doob 保守律）——**Stage 1 的目标不是通过 DirRandom 找到正 $\bar{E}_\text{net}$**，而是**测量并回填 Q1/Q2/Q3 三个从属问题**，为下游"是否需要通道 A 或通道 B 补充"提供依据。若 Stage 1 结论是"5m 上 DirRandom 恒负 + $T^\ast_\text{PL}$ 不存在"，即完整地证伪了 H1，仍是**有价值的证据**。
