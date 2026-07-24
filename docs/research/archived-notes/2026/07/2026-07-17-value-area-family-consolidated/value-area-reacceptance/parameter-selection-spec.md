# value_area_reacceptance 参数选择规格

> 类型：Theme / 参数选择规格
> 状态：占位 / 待首轮实验后填充
> 最近更新：2026-07-03
> 数学规格：[strategy-math-spec.md](strategy-math-spec.md)
> 实验计划：[experiment-plan.md](experiment-plan.md)
> 工程实现细节：[implementation-notes.md](implementation-notes.md)
> 主题入口：[README.md](README.md)

## 0. 文档定位

本文件描述 R30 spec 定义好的候选矩阵在**外样本**上应如何被固定或搜索，即：

- 哪些参数是**结构参数**，实验完成后应冻结；
- 哪些参数是**执行参数**，可按品种 / 波动率环境自适应选择；
- 哪些参数是**候选组合**，需要按 spec §6.4 的四维矩阵展开；
- 参数选择的**判据**（结构指标优先 / 随机基准分位 / 泛化外样本）；
- 参数选择的**流程**（先冻结哪一层、再搜哪一层）；
- 参数选择结果的**回填格式**（默认候选、按品种表、按环境表）。

## 1. 状态说明

本文件处于占位状态。具体参数选择规则待以下前置条件完成后再补写：

```text
1. strategy-math-spec.md 定义的策略已实现并通过 smoke test；
2. experiment-plan.md 首轮候选矩阵在 R29 固定样本上跑完；
3. 汇总出 POC touch rate / random baseline percentile / by_condition pnl 等结构指标；
4. 至少确认过 VA -> POC 主线是否优于随机基准。
```

在这些前置条件满足前，参数选择规则处于草稿阶段，不应用于外样本推断。

## 2. 待补写内容清单

### 2.1 参数分层

```text
结构参数（固定）：
- poc_mode
- va_mode
- ρ
- n_profile / n_step
- Ω_pattern / Ω_risk / Ω_direction / Ω_tp
- direction_mode

执行参数（可搜）：
- b / r / δ / m
- rr_raw_min（当 R1 ∈ Ω_risk）
- α / β / λ / rr_min
- stop_atr_bars / stop_atr_multiplier
- η_arm / η_retrace / n_fast / η_fast / n_fast_hold
- max_hold_bars / strict_close_exit

上下文参数（按标的自适应）：
- N_max / cooldown
- trade_start_time / last_entry_time / force_flat_time
```

### 2.2 判据

```text
主判据：
- 结构指标改善优先于收益改善；
- 相对同 runner 随机基准的分位数（percentile）作为通过阈值；
- 外样本泛化优于样本内精调。

否决判据：
- 单笔异常 pnl 支配总收益；
- 参数搜索维度爆炸后靠随机命中；
- 新增参数才能救回结果（视为过拟合）。
```

### 2.3 流程

```text
Phase 1: 冻结结构参数
- 依据 experiment-plan.md Stage B / C / D 的结果，固定 poc_mode/va_mode/ρ/n_profile/n_step 与 direction_mode。

Phase 2: 冻结候选矩阵
- 依据 Stage B/D 的 by_condition pnl 与 random_baseline_percentile，确定 Ω_pattern/Ω_risk/Ω_direction/Ω_tp 的选中组合。

Phase 3: 搜索执行参数
- 在冻结的结构 + 候选矩阵下，用小步长搜索执行参数；
- 每一步只搜一个组，避免维度乘积。

Phase 4: 按标的 / 环境自适应
- 若 Phase 3 结果对全品种不稳定，再按标的分组重跑；
- 若发现明显 by_environment 分层，把上下文参数按环境记录。
```

### 2.4 回填格式

```text
默认候选（全品种统一）：
- 完整 θ 快照。

按品种表：
- (合约代码, θ_signal 差异, θ_exec 差异)。

按环境表：
- (strong_trend / trend_bias / non_strong_trend, θ_signal 差异, θ_exec 差异)。
```

## 3. 与其他文档的边界

- 本文件**不定义**任何策略行为——策略行为一律以 [strategy-math-spec.md](strategy-math-spec.md) 为准；
- 本文件**不记录**实验结果——实验结果写在 `docs/workbench/` 或归档到 `docs/archive/`；
- 本文件**只回答**"给定 spec，如何在多样本上选定一组默认参数"。

## 4. 更新触发条件

- 首轮候选矩阵回测完成 → 从"占位"升级为"草案"；
- 至少一个通过外推的组合定型 → 升级为"活跃"；
- 参数选择结果失效或前提假设变化 → 降级并归档旧版本。
