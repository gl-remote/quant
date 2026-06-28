# structural-alpha-r1 工程支撑规划

> 类型：Workbench / 工程规划草案  
> 状态：草案  
> 创建日期：2026-06-28  
> 关联 roadmap：[工程长期路线图](../roadmap/engineering-roadmap.md)、[策略短期研究计划](../roadmap/strategy-short-term-plan.md)、[策略长期共识](../roadmap/strategy-research-framework.md)  
> 文档边界：本文只规划支撑 `structural-alpha-r1` 策略研究的工程工作，不记录具体实验参数、回测结果或阶段结论。

## 1. 背景

0.5 阶段的策略主线已经从指标型 baseline 调参转向结构型 Alpha 验证。当前研究重点不是寻找更复杂的预测信号，也不是扩大参数搜索，而是验证：

```text
共识价格区间
→ 明确失败边界
→ 可估算的短期盈利上界
→ 可执行的 2%~3% 单次账户风险
→ 足够的价格原始盈亏比和账户原始盈亏比
→ 可评估的胜率 / 盈亏比转化效率
→ 成本后长期正期望和安全边际
```

因此，工程侧的首要目标是让每轮实验能稳定回答：

- 为什么进场；
- 共识价格区间是什么；
- 严格失败边界在哪里；
- 盈利上界在哪里；
- 账户风险预算是否可执行；
- 退出来自严格失败、主动止盈、时间退出还是实际止损；
- 胜率提升是否值得牺牲盈亏比和仓位；
- 收益来自结构本身，还是参数偶然性、成本口径或尾部风险遗漏。

## 2. 工程目标

### 2.1 总目标

构建一个服务 `structural-alpha-r1` 的最小工程闭环：

```text
结构定义
→ 回测前预筛
→ 最小策略实现
→ 回测交易诊断
→ 报告展示
→ 结果对比
→ 研究文档沉淀
```

该闭环优先服务研究判断质量，而不是服务跑更多参数。

### 2.2 非目标

当前阶段不优先做：

- 大规模 Optuna / Bayesian search；
- Walk-Forward；
- 多体系复杂叠加；
- 通用策略脚手架；
- TqSdk 生命周期统一；
- Docker / 生产部署；
- 实盘风控通知；
- paper trading。

这些工作只有在结构型 Alpha 初步成立后再推进。

## 3. 优先级总览

| 优先级 | 工作项 | 目标 | 状态 |
|--------|--------|------|------|
| P0 | 结构诊断字段契约 | 统一策略、回测、报告中的结构实验字段 | 待做 |
| P0 | 账户风险预算预筛 | 回测前判断结构是否满足 2%~3% 单次风险约束 | 待做 |
| P0 | `structural-alpha-r1` 最小策略骨架 | 支持严格失败、主动止盈、时间退出、止损放宽对照 | 待做 |
| P0 | 交易级诊断落库 / artifact | 每笔交易记录失败边界、盈利上界、MAE / MFE、exit reason | 待做 |
| P1 | 结构诊断报告 | 在报告中展示结构而非只展示收益曲线 | 待做 |
| P1 | 结果 diff 工具 | 对比不同退出结构的胜率 / 盈亏比转化效率 | 待做 |
| P1 | 共识价格区间特征 | 支持前日高低点、开盘区间、Initial Balance 等客观边界 | 待做 |
| P2 | 归因和蒙特卡洛 | 分解收益来源、评估亏损簇和账户生存能力 | 后置 |

## 4. P0：结构诊断字段契约

### 4.1 目标

定义一套强类型、数值化、可持久化的结构实验诊断字段，避免诊断信息只存在于日志、markdown 或非结构化字符串中。

### 4.2 字段范围

建议分成四层。

#### 结构定义层

| 字段 | 说明 |
|------|------|
| `experiment_version` | 例如 `structural-alpha-r1` |
| `consensus_zone_type` | 共识价格区间类型，例如 previous_day_high_low、opening_range、initial_balance |
| `structure_source` | Price Action、Auction / Market Profile、Wyckoff 等 |
| `traditional_explanation` | 传统解释 |
| `structural_explanation` | 结构塑形解释 |
| `direction_hypothesis` | 多空方向假设 |
| `entry_boundary` | 入场参考边界 |
| `strict_failure_boundary` | 严格失败边界 |
| `expected_profit_boundary` | 预期盈利上界 |

#### 风险预算层

| 字段 | 说明 |
|------|------|
| `strict_failure_distance` | 入场到严格失败边界的价格距离 |
| `expected_profit_distance` | 入场到预期盈利上界的价格距离 |
| `raw_price_r_multiple` | 价格原始盈亏比 |
| `contract_multiplier` | 合约乘数 |
| `min_volume` | 最小手数 |
| `account_equity` | 账户权益 |
| `target_risk_ratio` | 目标风险比例，例如 0.02 或 0.03 |
| `target_risk_amount` | 目标风险金额 |
| `loss_per_min_volume` | 最小手数严格失败损失 |
| `theoretical_volume` | 理论可交易手数 |
| `actual_volume` | 实际下单手数 |
| `account_risk_amount` | 实际账户风险金额 |
| `account_risk_ratio` | 实际账户风险比例 |
| `raw_account_r_multiple` | 账户原始盈亏比 |
| `risk_budget_passed` | 风险预算是否通过 |
| `risk_budget_reject_reason` | 不通过原因 |

#### 交易诊断层

| 字段 | 说明 |
|------|------|
| `acceptance_rejection_evidence` | 接受 / 拒绝证据类型 |
| `fast_retouch_bars` | 严格边界快速再触及所用 K 线数 |
| `fast_retouch` | 是否快速再触及 |
| `mae` | 最大不利波动 |
| `mfe` | 最大有利波动 |
| `mae_r` | MAE / 严格失败距离 |
| `mfe_r` | MFE / 严格失败距离 |
| `exit_reason` | strict_failure、take_profit、time_exit、relaxed_stop、abnormal 等 |
| `holding_bars` | 持仓 K 线数 |
| `gross_pnl` | 成本前盈亏 |
| `net_pnl` | 成本后盈亏 |
| `commission` | 手续费 |
| `slippage_cost` | 滑点成本 |

#### 转化效率层

| 字段 | 说明 |
|------|------|
| `exit_policy` | strict、take_profit、time_exit、relaxed_stop 等 |
| `strict_stop_distance` | 严格失败距离 |
| `actual_stop_distance` | 实际止损距离 |
| `stop_relaxation_multiple` | 止损放宽倍数 |
| `position_adjustment_multiple` | 为维持风险预算所需仓位调整倍数 |
| `cost_adjusted_win_rate` | 成本后胜率 |
| `cost_adjusted_payoff_ratio` | 成本后盈亏比 |
| `breakeven_win_rate` | 盈亏平衡胜率 |
| `win_rate_margin` | 胜率安全边际 |
| `conversion_efficiency` | 胜率 / 盈亏比转化效率 |

### 4.3 实现建议

优先新增内部 Python dataclass / Pydantic model，用于：

- 策略运行时生成诊断；
- 回测交易 artifact 序列化；
- report JSON schema 输出；
- 前端报告读取。

字段应尽量使用数字、枚举和布尔值。展示格式化只在报告层处理，不在 artifact 层提前格式化。

## 5. P0：账户风险预算预筛

### 5.1 目标

在回测前判断一个候选结构是否具备最低可交易性。若严格失败边界无法映射到 2%~3% 单次账户风险，则不进入回测调参。

### 5.2 输入

| 输入 | 说明 |
|------|------|
| `entry_price` | 计划入场价格 |
| `strict_failure_boundary` | 严格失败边界 |
| `expected_profit_boundary` | 预期盈利上界 |
| `direction` | long / short |
| `account_equity` | 账户权益 |
| `target_risk_ratio` | 目标风险比例 |
| `contract_multiplier` | 合约乘数 |
| `min_volume` | 最小手数 |
| `commission` | 手续费估算 |
| `slippage` | 滑点估算 |
| `gap_buffer` | 跳空或超价缓冲 |

### 5.3 输出

| 输出 | 说明 |
|------|------|
| `strict_failure_distance` | 严格失败距离 |
| `expected_profit_distance` | 盈利上界距离 |
| `raw_price_r_multiple` | 价格原始盈亏比 |
| `target_risk_amount` | 目标账户风险金额 |
| `loss_per_min_volume` | 最小手数失败损失 |
| `theoretical_volume` | 理论手数 |
| `actual_volume` | 实际手数 |
| `account_risk_amount` | 实际风险金额 |
| `account_risk_ratio` | 实际风险比例 |
| `raw_account_r_multiple` | 账户原始盈亏比 |
| `passed` | 是否通过 |
| `reject_reason` | 拒绝原因 |

### 5.4 拒绝条件

预筛应至少能拒绝：

1. 严格失败边界为空；
2. 盈利上界为空；
3. 严格失败距离小于等于 0；
4. 盈利上界距离小于等于 0；
5. 价格原始盈亏比不足；
6. 最小手数下账户风险超过 2%~3%；
7. 滑点、手续费或跳空缓冲后成本空间不足；
8. 理论手数低于最小手数；
9. 账户原始盈亏比不足。

## 6. P0：`structural-alpha-r1` 最小策略骨架

### 6.1 目标

实现一个最小策略骨架，用于验证一个客观共识边界附近的结构型 Alpha，而不是开发通用策略框架。

### 6.2 第一阶段候选边界

建议优先支持最容易客观定义的边界：

1. 前日高 / 低点；
2. 昨收；
3. 开盘区间高 / 低点；
4. Initial Balance 高 / 低点。

VAH / VAL / POC 和密集成交区边缘可后置，因为需要更复杂的成交量分布或 profile 计算。

### 6.3 最小对照组

每个候选结构至少输出三组对照：

| 对照 | 说明 |
|------|------|
| 严格失败边界退出 | 验证原始结构是否具备低验证成本和足够原始盈亏比 |
| 主动止盈 / 时间退出 | 验证是否能在盈利上界附近提高兑现质量 |
| 有限止损放宽 + 同步降仓 | 验证吸收噪声后胜率提升是否覆盖盈亏比下降和仓位下降 |

### 6.4 每笔交易必须记录

- 触发的共识边界；
- 入场方向假设；
- 严格失败边界；
- 预期盈利上界；
- 预筛结果；
- 实际止损边界；
- 实际仓位；
- MAE / MFE；
- exit reason；
- 成本后盈亏；
- 是否快速再触及严格边界。

## 7. P0：交易级诊断落库 / artifact

### 7.1 目标

让结构诊断可以跨 CLI、报告、文档复用，而不是只看终端输出。

### 7.2 建议路径

优先选择最小侵入方式：

1. 在回测 trade artifact 中增加 `diagnostics` 字段；
2. `diagnostics` 使用结构化 JSON；
3. report writer 原样导出；
4. 前端报告按结构诊断字段渲染；
5. 后续如查询需求稳定，再考虑数据库 schema 扩展。

### 7.3 注意事项

- 不要把展示字符串写入 artifact；
- 不要依赖 markdown 表格作为数据源；
- 不要让不同策略自由拼接字段名；
- 字段缺失应显式为 `null`，而不是省略后由前端猜测。

## 8. P1：结构诊断报告

### 8.1 目标

新增结构型 Alpha 研究视图，让报告能直接判断结构是否成立。

### 8.2 报告模块

建议包括：

1. 实验概览；
2. 账户风险预算预筛摘要；
3. 价格原始盈亏比分布；
4. 账户原始盈亏比分布；
5. 严格失败距离分布；
6. 盈利上界距离分布；
7. MAE / MFE 分布；
8. 严格边界快速再触及率；
9. exit reason 分布；
10. 成本后胜率、盈亏比、盈亏平衡胜率、胜率安全边际；
11. 最大单笔亏损、连续亏损和亏损簇；
12. 三类退出结构对照表。

### 8.3 报告判断顺序

报告页面不应只突出收益曲线，应按以下顺序展示：

```text
风险预算是否可执行
→ 严格失败边界是否清楚
→ 盈利上界是否足够
→ 价格 / 账户原始盈亏比是否足够
→ 快速再触及率是否可接受
→ 接受 / 拒绝质量是否足够
→ 出口结构是否改善成本后期望
→ 尾部亏损是否可承受
→ 收益指标
```

## 9. P1：结果 diff 工具

### 9.1 目标

提供一个面向研究问题的结果对比工具，用来比较不同退出结构的收益分布变化。

### 9.2 对比对象

优先支持：

- 严格失败退出 vs 主动止盈；
- 严格失败退出 vs 时间退出；
- 严格失败退出 vs 止损放宽 + 同步降仓；
- 同一结构在相邻边界参数下的结果。

### 9.3 对比字段

| 字段 | 目的 |
|------|------|
| 交易次数变化 | 判断样本是否可比 |
| 胜率变化 | 判断表面胜率提升 |
| 成本后盈亏比变化 | 判断胜率是否通过牺牲盈亏比换来 |
| 盈亏平衡胜率变化 | 判断最低胜率门槛 |
| 胜率安全边际变化 | 判断是否有安全边际 |
| 平均账户盈利变化 | 判断盈利质量 |
| 最大单笔亏损变化 | 判断尾部风险 |
| 最大连续亏损变化 | 判断亏损簇 |
| exit reason 分布变化 | 判断退出结构是否按预期工作 |
| 快速再触及率变化 | 判断是否只是用放宽止损购买噪声 |

## 10. P1：共识价格区间特征

### 10.1 第一批

优先做无需复杂成交量 profile 的客观区间：

| 区间 | 说明 |
|------|------|
| 前日高 / 低点 | 高频可观察边界 |
| 昨收 | 日内参考锚点 |
| 开盘区间高 / 低点 | 日内早期边界 |
| Initial Balance 高 / 低点 | 更明确的早盘共识区间 |

### 10.2 第二批

结构闭环跑通后再做：

| 区间 | 说明 |
|------|------|
| VAH / VAL / POC | 需要 profile 计算 |
| 密集成交区边缘 | 需要成交分布或价格停留统计 |
| 假突破极值 | 需要事件状态机 |
| 重新接受 / 拒绝 | 需要边界外停留和回收判断 |

## 11. 实施顺序

建议按以下顺序推进：

```text
1. 定义 structural_alpha 诊断字段模型
2. 在 trade artifact 中接入 diagnostics
3. 实现账户风险预算预筛函数
4. 给预筛补单元测试
5. 实现 structural-alpha-r1 最小策略骨架
6. 支持严格失败边界退出
7. 增加主动止盈和时间退出对照
8. 增加有限止损放宽 + 同步降仓对照
9. 输出 MAE / MFE、快速再触及率和 exit reason
10. 报告 JSON 导出结构诊断字段
11. 前端增加结构诊断视图
12. 增加 run diff 工具
13. 扩展 Initial Balance 等共识区间特征
```

## 12. 验收标准

### 12.1 工程验收

- 每笔 structural-alpha 交易都有结构化 diagnostics；
- 预筛失败的结构不会进入参数搜索；
- 风险预算计算可以解释最小手数、合约乘数、滑点和手续费影响；
- 三类退出结构可以在同一候选区间下对比；
- 报告能展示结构诊断字段；
- diff 工具能回答胜率提升是否覆盖盈亏比下降和成本；
- 字段在 Python artifact、report JSON、前端展示之间语义一致。

### 12.2 研究验收

工程链路完成后，每轮实验至少能回答：

1. 共识价格区间是否客观；
2. 严格失败边界是否明确；
3. 盈利上界是否可估算；
4. 严格失败距离是否合理；
5. 价格原始盈亏比是否足够；
6. 账户风险预算是否可执行；
7. 账户原始盈亏比是否足够；
8. 快速再触及率是否过高；
9. 接受 / 拒绝质量是否足够；
10. 主动止盈、时间退出或止损放宽是否改善成本后期望；
11. 尾部亏损和亏损簇是否可承受；
12. 收益是否能解释为结构优势，而不是参数偶然性。

## 13. 风险与约束

| 风险 | 说明 | 处理 |
|------|------|------|
| 字段过多导致实现拖慢 | 一次性做完整 schema 可能影响节奏 | P0 先覆盖预筛、边界、盈亏比、MAE / MFE、exit reason |
| 过早前端化 | 报告页面可能消耗过多工程时间 | 先保证 JSON artifact，再做最小展示 |
| 重新滑向参数搜索 | 工程工具可能被用来找最优参数 | 预筛和结构诊断必须先于优化器 |
| 诊断字段格式漂移 | 不同策略自由输出字段会破坏对比 | 使用统一 dataclass / schema |
| 数据库 schema 过早固化 | 研究字段可能调整 | 初期优先 JSON diagnostics，稳定后再落数据库列 |
| 只看收益指标 | 可能忽略风险预算和尾部亏损 | 报告按结构判断顺序组织 |

## 14. 当前建议

立即开始的最小工程包：

```text
A. structural_alpha 诊断字段模型
B. risk_budget 预筛函数
C. trade diagnostics artifact 接入
D. structural-alpha-r1 严格失败退出最小策略
E. MAE / MFE + exit reason 输出
```

完成这五项后，再加入主动止盈、时间退出、止损放宽对照和报告视图。

核心原则：**先让实验能被正确解释，再让实验跑得更多。**
