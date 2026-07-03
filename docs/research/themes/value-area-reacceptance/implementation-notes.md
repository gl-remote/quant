# value_area_reacceptance 工程实现细节

> 类型：Theme / 工程实现细节
> 状态：占位 / 待实现开始后填充
> 最近更新：2026-07-03
> 数学规格：[strategy-math-spec.md](strategy-math-spec.md)
> 实验计划：[experiment-plan.md](experiment-plan.md)
> 参数选择：[parameter-selection-spec.md](parameter-selection-spec.md)
> 主题入口：[README.md](README.md)

## 0. 文档定位

本文件记录 R30 策略从 [strategy-math-spec.md](strategy-math-spec.md) 落到代码时的**工程选择与优化细节**，只涉及"怎么实现"，不改变"是什么"：

- **不定义任何策略行为**——策略行为由 strategy-math-spec.md 唯一确定；
- **不记录实验流水**——实验结果写在 `docs/workbench/` 或归档；
- **不覆盖参数选择流程**——参数选择规则见 parameter-selection-spec.md；
- **只回答**：给定 spec，代码层应如何组织数据结构、事件调度、缓存策略、成交模型桥接、精度处理、性能优化，才能既正确又高效。

若某项工程决定影响策略语义（例如"平仓刷新与再入场的时序"），说明 spec 定义不完整，必须先回补 strategy-math-spec.md，再更新本文件。

## 1. 状态说明

本文件处于占位状态，实际实现开始后按下列小节填充。填充时保持"每条决定都有理由 + 反例说明为什么不选别的方案"的格式。

## 2. 待补写内容清单

### 2.1 数据结构与状态维护

```text
- session 级 vs bar 级状态的存储层次；
- 每侧 s ∈ {L, U} 的状态槽如何组织；
- 冻结变量 (Entry, Stop, Target, F, q, Anchor) 的生命周期与内存模型；
- 状态在 backtest 与实盘之间的兼容层。
```

### 2.2 Profile 滚动窗口的增量维护

```text
- 每次刷新 u 的 profile 是否全量重算 vs 增量维护；
- close-profile 与 range-profile 的桶数据结构选择（dict / SortedDict / numpy array）；
- VA 贪心扩展的边界维护；
- 采用型 vs 监控型刷新的开销分离（Adopt(u) = 0 时可跳过下游代价大的量）。
```

### 2.3 事件调度与 bar 循环

```text
- T_refresh / T_adopt 的构造顺序（先枚举 InitEvent → TickEvent → ExitEvent）；
- 同一 bar 上多事件同时触发时的合并处理；
- Enter 与 Refresh 在同一 bar 上的优先级：Enter 前评估 => Refresh 后处理；
- 平仓刷新与下一 bar Enter 的时序（保证 CooldownOK 正确度量）。
```

### 2.4 突破跟踪 X_s 的实现

```text
- J_s(t) 是否物化整段列表 vs 只维护 min/max 极值；
- i_start(t) 前移时如何逐 bar 剔除过期突破 bar；
- Reset_s = 1 事件如何触发 J_s 与 X_s 清空；
- 反向突破与未成交 R_s 不清空 X_s 的正确性验证。
```

### 2.5 止盈候选状态位

```text
- Anchor / signed_pnl / peak_pnl 在持仓期间的增量维护；
- Armed(t) := 1[peak_pnl(t) >= arm_level] 利用 peak_pnl 单调性 O(1) 更新；
- fast_window(t) / u_fast(t) 的滚动实现；
- TP_fixed_active(t) 与 TP_soft_active(t) 分派到不同成交模型的代码路径。
```

### 2.6 精度与舍入

```text
- price_tick 全局配置 vs 品种级配置；
- bucket_profile / bucket_buy / bucket_sell 的统一实现入口；
- 浮点数比较容差；
- G_τ 越界处理（session 内新极值超出上一次 profile 桶范围）。
```

### 2.7 与回测引擎的桥接

```text
- vnpy BacktestingEngine 的下单接口与 Stop / Target 挂单模型；
- TP_soft（策略级 C_t 平仓）的成交撮合口径；
- 手续费 / 滑点 / 保证金在 R30 策略下的口径与 baseline 保持一致；
- trade_clearings 清算口径 vs vnpy BacktestResult 口径的选择与切换。
```

### 2.8 参数与配置

```text
- θ_profile / θ_signal / θ_exec / θ_size 的配置 schema；
- Ω_pattern / Ω_risk / Ω_direction / Ω_tp 的枚举与序列化格式；
- 每轮实验配置的 config 目录布局；
- CLI / runner 与策略 data_requirements 的一致性校验。
```

### 2.9 性能优化

```text
- 全部 bar 一次性构造 idx / time 数组；
- 滚动窗口的 O(1) 更新技巧（deque / segment tree / SortedList）；
- profile 计算按需重算的短路；
- 大样本回测下的内存 footprint 控制（不保留全部 Π̂_u 历史，只保留 T_adopt 上的采用值）。
```

### 2.10 测试与验证

```text
- 单元测试：POC / VAL / VAH 构造、tie-break、round_τ、reset 触发；
- 集成测试：single-bar smoke test 覆盖 Enter / Exit 全路径；
- 属性测试：随机 bar 序列下 §10.3.4 正交性断言；
- 回归测试：value_area_reacceptance_baseline 与 R30 隔离运行，互不影响。
```

## 3. 与其他文档的边界

- 本文件不定义**任何**策略行为；如需改变行为，先改 [strategy-math-spec.md](strategy-math-spec.md)。
- 本文件不记录**任何**实验结果；实验流水写到 `docs/workbench/`。
- 本文件不给出**任何**参数选择判据；判据见 [parameter-selection-spec.md](parameter-selection-spec.md)。
- 本文件不重述 [experiment-plan.md](experiment-plan.md) 的候选矩阵。

## 4. 更新触发条件

- 开始实现某个模块前，先在对应小节写"计划的实现选择"；
- 实现完成后回填"实际采用的实现 + 反例 + 性能数据"；
- 若某项决定后来被证明影响语义，先回改 [strategy-math-spec.md](strategy-math-spec.md)，再更新本文件；
- 每次 spec 有跨小节的结构性变更，同步检查本文件相关小节是否需要补写。
