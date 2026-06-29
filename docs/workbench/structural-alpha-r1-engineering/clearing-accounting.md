# 清算、账务与 PnL 引擎规划

> 类型：Workbench / Clearing & Accounting 规划草案  
> 状态：草案  
> 创建日期：2026-06-29  
> 来源：由 [structural-alpha-r1 工程支撑总览](overview.md) 拆分  
> 文档边界：本文只规划成交后清算、账务、成本与 PnL 口径；不定义 Alpha、交易前风险预算、执行策略或研究报告展示。

## 1. 定位

清算系统负责回答：

```text
成交之后，账户、持仓、现金、成本和 PnL 发生了什么？
```

它对应量化系统中的：

```text
Clearing / Accounting / Position Book / PnL Engine
```

该模块应独立于具体策略。`structural-alpha-r1` 只是第一个明确需要统一清算口径的研究场景。

## 2. 为什么要独立

原规划中的部分字段明显属于成交后账务：

- `gross_pnl`
- `net_pnl`
- `commission`
- `slippage_cost`
- `contract_multiplier`
- 成交配对
- 开平仓
- realized / unrealized PnL
- cash movement
- margin
- position ledger
- daily settlement

这些字段不应由策略、回测报告或单个实验各自计算。否则会导致：

- 策略之间 PnL 口径漂移；
- 回测和报告统计不一致；
- diff 工具比较失真；
- 未来实盘或 paper trading 难以对账。

## 3. 行业分层原则

建议采用以下职责边界：

```text
strategy 只产生 intent / signal
execution/backtest 产生 order / fill / trade lifecycle
clearing 接收 fill 并生成 position / cash / pnl / cost
report 只消费 clearing 结果
```

也就是：

```text
Fill Events
→ Position Book
→ Cost Ledger
→ PnL Ledger
→ Account Equity
→ Performance Snapshot
```

## 4. 目标

- 统一合约乘数、手续费、滑点、成交配对和 PnL 口径；
- 为回测报告提供唯一可信的 gross / net PnL；
- 支持 trade-level 与 account-level 两个粒度；
- 为后续归因、蒙特卡洛和实盘对账打基础；
- 避免策略层、报告层重复计算账务字段。

## 5. 输入

| 输入 | 来源 | 说明 |
|------|------|------|
| fill events | Execution / Backtest | 成交价格、数量、方向、时间 |
| instrument metadata | Data / config | 合约乘数、最小变动价位等 |
| commission model | Config / broker rule | 手续费规则 |
| slippage model / actual slippage | Backtest / execution | 滑点成本来源 |
| initial account state | Account config | 初始资金、初始持仓 |

## 6. 输出

建议形成独立账务 artifact。

### 6.1 Trade-level Clearing Ledger

| 字段 | 说明 |
|------|------|
| `trade_id` | 交易标识 |
| `open_fill_id` | 开仓成交 |
| `close_fill_id` | 平仓成交 |
| `symbol` | 合约 |
| `direction` | long / short |
| `volume` | 成交手数 |
| `contract_multiplier` | 合约乘数 |
| `gross_pnl` | 成本前盈亏 |
| `commission` | 手续费 |
| `slippage_cost` | 滑点成本 |
| `net_pnl` | 成本后盈亏 |

### 6.2 Account-level Ledger

| 字段 | 说明 |
|------|------|
| `cash` | 现金 |
| `position_value` | 持仓价值 |
| `realized_pnl` | 已实现盈亏 |
| `unrealized_pnl` | 未实现盈亏 |
| `total_commission` | 累计手续费 |
| `total_slippage_cost` | 累计滑点成本 |
| `equity` | 账户权益 |
| `margin` | 保证金 |

## 7. 明确不属于清算系统的内容

| 内容 | 所属模块 |
|------|----------|
| 共识价格区间 | Alpha Research |
| 严格失败边界 | Alpha Research |
| 目标风险比例 | Pre-trade Risk |
| 理论手数 | Pre-trade Risk |
| exit reason | Execution / Backtest |
| MAE / MFE | Execution / Backtest |
| 胜率、盈亏比、diff | Analytics / Report |

## 8. 与 structural-alpha 的关系

`structural-alpha-r1` 需要清算系统提供统一口径的：

- 每笔交易成本前盈亏；
- 每笔交易成本后盈亏；
- 手续费；
- 滑点成本；
- 账户权益变化；
- 最大单笔亏损；
- 连续亏损和亏损簇的数据基础。

但清算系统不关心这笔交易为什么发生，也不解释结构是否成立。

## 9. 第一阶段实施建议

当前阶段不必一次性实现完整生产级清算系统。建议先做可落库、可追溯的第一阶段账务闭环：

1. 梳理当前回测中手续费、滑点和 PnL 的计算位置；
2. 明确唯一的 trade-level PnL 计算函数；
3. 将 `gross_pnl`、`commission`、`slippage_cost`、`net_pnl` 从策略诊断字段中移出；
4. 在数据库事实层分离 raw fills、trade clearings、account ledger、position ledger；
5. 报告层统一读取 clearing 后的汇总结果，不重复计算账务字段；
6. 本阶段落地 event-level account ledger / position ledger 骨架；完整 margin、daily settlement、多账户和实盘对账后续扩展。

## 10. 验收标准

- 同一笔成交只有一个权威净收益口径；
- 策略层不直接写入 `net_pnl`；
- 报告层不重复计算手续费和滑点；
- trade-level clearing artifact 可被 diff 和 analytics 复用；
- 成本前 / 成本后收益可追溯到成交和成本明细；
- 未来接入实盘或 paper trading 时具备对账边界。

## 11. 当前方案：clearing 作为独立业务域

当前实现中，`workspace/backtest` 内部已有对回测成交的配对和清算计算。新的工程方向是将这部分能力从 backtest 域中抽出，升级为独立的 clearing 业务域。

核心判断：

```text
交易配对、开平仓归集、realized PnL、成本和账户汇总，
不是 backtest 的附属统计，
而是 clearing / accounting 的核心业务能力。
```

新的职责边界：

| 模块 | 职责 |
|------|------|
| `workspace/backtest` | 产生回测模拟成交记录，不拥有最终配对清算和 PnL 解释权 |
| `workspace/clearing` | 执行成交配对、清算、成本、PnL、账户级汇总 |
| `workspace/data` | 读取 backtest trades，写入清算表，更新 backtests 统计 |
| `workspace/report` | 消费 clearing 后的数据，不重新配对或重新计算账务 |

建议新增：

```text
workspace/clearing/
```

作为清算业务域目录。`accounting` 可以作为 clearing 内部概念或后续子模块，不建议作为第一层业务域名称。

## 12. Workflow 触发链路

clearing 应有统一 workflow 入口，而不是散落在不同 backtest run 路径里。

建议新增：

```text
workspace/cli/workflows/clearing.py
```

作为 clearing 业务域的统一调度入口。

回测 run 的多条路径不应分别手动接入 clearing。当前生命周期统一收口点是：

```text
workspace/cli/workflows/backtests_lifecycle.py
└── RunFinalizer
```

因此推荐触发链路为：

```text
backtests_run.py
→ RunFinalizer
→ clearing workflow
→ workspace/clearing
→ workspace/data
→ trade_clearings + account_ledger_entries + position_ledger_entries + backtests summary
```

边界约束：

- `RunFinalizer` 只调度 clearing workflow，不实现清算业务；
- `backtests_run.py` 尽量不直接接入 clearing，避免多路径重复逻辑；
- clearing workflow 应支持从已有 backtest run 重新触发；
- `backtest_completed` 不等于 `clearing_completed`，未来可增加 clearing 状态区分。

状态语义建议：

```text
backtest_completed
→ clearing_pending
→ clearing_completed / clearing_failed
```

报告和分析阶段应优先消费 `clearing_completed` 的 run。

## 13. Data 层落点

现有 `workspace/data` 中已有 backtest trades 表，用于记录回测模拟成交。过去链路是：

```text
backtest trade
→ backtest 内部配对清算
→ backtests 统计字段
```

新的链路应调整为：

```text
backtest_trades
→ clearing domain / clearing workflow
→ trade_clearings
→ account_ledger_entries + position_ledger_entries
→ backtests 统计字段
```

也就是说，数据库落地是 clearing 阶段的核心工作。三张新增表统一属于 clearing 系统，采用 Rails 风格复数表名，同时保留 `backtest_id` / `run_id` 等外键以表达当前 backtest 来源。report JSON、前端数据契约和导出格式后移到 [analytics-reporting.md](analytics-reporting.md) 阶段细化。

### 13.1 清算域三张表

本阶段新增三张 clearing 域表：

```text
trade_clearings
account_ledger_entries
position_ledger_entries
```

命名原则：

- `backtest_trades` 仍属于 backtest 域，记录回测引擎产生的 raw simulated fills；
- `trade_clearings` 属于 clearing 域，记录成交配对后的权威清算结果；
- `account_ledger_entries` 属于 clearing 域，记录账户资金 / 权益变化事件；
- `position_ledger_entries` 属于 clearing 域，记录持仓变化事件。

业务语义：

```text
每条 trade_clearings 记录，代表一次被清算后的 open lot 消耗事实。
每条 account_ledger_entries 记录，代表一次账户层资金 / 权益变化事件。
每条 position_ledger_entries 记录，代表一次持仓数量 / 成本状态变化事件。
```

核心规则：

- 每条清算、账户账本、持仓账本记录都归属于一条 `backtests` 记录；
- `trade_clearings` 由 `backtest_trades` 配对整理生成；
- 每次平仓会生成一条或多条 `trade_clearings`，取决于它消耗了多少 open lot；
- `account_ledger_entries` 可追溯到 `trade_clearings` 或来源 raw fill；
- `position_ledger_entries` 可追溯到 open / close raw fill 和对应 `trade_clearings`；
- backtest trade 的 `reason` 字段包含交易形成的非结构化信息，清算阶段需要保留和整理，不能丢弃。

### 13.2 `trade_clearings` 最小字段

第一阶段至少覆盖：

| 字段类别 | 示例 |
|----------|------|
| run 归属 | `backtest_id` / `run_id` |
| 来源成交 | `open_trade_id`、`close_trade_id`、`source_trade_ids` |
| 合约信息 | `symbol`、`direction`、`volume`、`contract_multiplier` |
| 开平仓信息 | `open_time`、`close_time`、`open_price`、`close_price` |
| 清算结果 | `gross_pnl`、`commission`、`slippage_cost`、`net_pnl` |
| 生命周期 | `holding_seconds` / `holding_bars`、`is_forced_close`、`forced_close_reason` |
| 非结构化来源 | `open_reason`、`close_reason` |
| 强平标记 | `is_forced_close`、`forced_close_reason` |

### 13.3 `account_ledger_entries` 与 `position_ledger_entries` 骨架

第一阶段的 account / position 账本是 event-level 骨架，不是完整生产级账户系统。

`account_ledger_entries` 至少覆盖：

| 字段类别 | 示例 |
|----------|------|
| 归属 | `backtest_id`、`run_id`、`source_type`、`source_id` |
| 来源 | `trade_id`、`clearing_id` |
| 事件 | `event_time`、`event_type`、`symbol` |
| 资金变化 | `cash_delta`、`cash_balance` |
| PnL | `realized_pnl_delta`、`realized_pnl_balance`、`unrealized_pnl_delta`、`unrealized_pnl_balance` |
| 成本 | `commission_delta`、`slippage_delta` |
| 权益 | `equity`、`margin` |
| 扩展 | `metadata_json` |

`position_ledger_entries` 至少覆盖：

| 字段类别 | 示例 |
|----------|------|
| 归属 | `backtest_id`、`run_id`、`source_type`、`source_id` |
| 来源 | `open_trade_id`、`close_trade_id`、`clearing_id` |
| 事件 | `event_time`、`event_type`、`symbol`、`direction` |
| 持仓变化 | `volume_delta`、`position_volume`、`avg_open_price` |
| 清算结果 | `realized_pnl_delta`、`is_forced_close` |
| 扩展 | `metadata_json` |

当前阶段明确预留但不做完整权威口径：

- `unrealized_pnl_*`：先预留，当前以已实现清算为主；
- `margin`：先预留，完整保证金模型后续实现；
- bar-level / daily-level equity snapshots：继续以后续 analytics-reporting 或 clearing 二期细化。

### 13.4 backtests 汇总回填

第一阶段不仅要做 trade-level clearing，还要生成 event-level account ledger / position ledger 骨架，并回填或更新 `backtests` 统计字段。

新方案不是取消原有 backtests 统计，而是把统计来源从 backtest 内部迁移到 clearing：

```text
旧：backtest 直接计算并写入 backtests
新：clearing 根据 trades / clearings 计算并写入 backtests
```

第一阶段应覆盖：

- total gross PnL；
- total net PnL；
- total commission；
- total slippage cost；
- realized PnL；
- final equity / balance；
- trade count；
- win / loss count；
- max single loss；
- max drawdown 所需基础序列；
- forced close 对最终结果的影响。

后置的是更完整的生产级账本能力，例如 margin、daily settlement、多账户、跨日复杂持仓账本和实盘对账。

## 14. 成交配对规则

clearing 不能假设一次平仓刚好关闭全部持仓，应按行业惯例支持部分平仓。

推荐第一阶段采用 FIFO lots：

```text
开仓成交 → 形成 open lots
平仓成交 → 按时间顺序消耗最早的 open lots
```

规则：

- 一笔开仓可以被多次部分平仓；
- 多笔开仓可以被一次平仓消耗；
- 一次平仓如果覆盖多个 open lot，应拆成多条清算记录；
- 一次平仓如果只消耗部分 open lot，剩余部分继续保留为未平仓 lot；
- 每条清算记录对应一次“被平仓成交消耗掉的 open lot 数量”。

核心不变量：

```text
sum(cleared_volume) <= sum(open_volume)
```

对于每个方向和合约，clearing 应保证 open lots 与 close trades 的消耗关系可追溯。

## 15. 回测结束未平仓处理

如果 backtest 结束后仍存在未平仓 open lots，应按强制平仓处理。

建议规则：

```text
close_type = forced_close_at_backtest_end
close_source = synthetic
```

价格来源：

```text
使用回测最后一根可用 K 线的 close 价格
```

后续如果 backtest 引擎已有更明确的 settlement / last price 口径，再按引擎口径统一。

强制平仓记录也应进入 `trade_clearings`，并参与 `account_ledger_entries`、`position_ledger_entries` 和 `backtests` 汇总。这样最终报告可以区分：

- 正常策略退出；
- stop / take profit / time exit；
- 回测结束强制平仓；
- 强平对最终收益和风险指标的影响。

## 16. 平仓后价格后验统计

clearing 可以利用回测用到的 K 线，在平仓后补充有限的后验统计，为后续结构型 Alpha 分析打基础。

第一阶段可先预留，后续按 analytics-reporting 需求计算：

| 字段 | 说明 |
|------|------|
| `post_close_1h_price` | 平仓后一小时附近价格 |
| `post_close_1h_return` | 平仓后一小时收益变化 |
| `post_close_1h_mae` | 平仓后一小时最大不利波动 |
| `post_close_1h_mfe` | 平仓后一小时最大有利波动 |

这些字段服务于后续问题：

- 平仓是否过早；
- 止盈后是否继续大幅有利运动；
- 止损后是否快速回收；
- 时间退出是否合理。

数据契约、导出格式和报告展示方式不在本文展开，留到 [analytics-reporting.md](analytics-reporting.md) 阶段细化。

## 17. 时间复杂度约束

trades 和 bars 理论上都按时间顺序排列，clearing 和后验统计不应引入 `N × M` 扫描。

实现原则：

```text
trades: 按时间升序扫描
bars: 按时间升序扫描
clearing: 使用 open lot 队列
post metrics: 使用 bar cursor / 双指针推进
```

复杂度目标：

```text
O(N trades + M bars)
```

禁止模式：

```text
for each clearing_record:
    scan all bars from beginning
```

该约束应纳入第一阶段验收，避免随着交易数量和 K 线数量增长导致回测后处理不可用。

## 18. 本阶段非目标

当前 clearing 阶段不展开：

- report JSON schema；
- 前端消费字段契约；
- 数据导出格式；
- analytics artifact 形态；
- diff 工具最终消费格式；
- 复杂 margin / daily settlement；
- 多账户和实盘对账。

这些内容在 [analytics-reporting.md](analytics-reporting.md) 或后续 clearing 二期中细化。

## 19. 更新后的第一阶段实施顺序

建议第一阶段按以下顺序推进：

```text
1. 盘点 workspace/backtest 中现有配对、手续费、滑点和 PnL 计算位置
2. 新增 workspace/clearing 业务域
3. 新增 workspace/cli/workflows/clearing.py
4. 在 RunFinalizer 中统一触发 clearing workflow
5. data 层增加 trade_clearings、account_ledger_entries、position_ledger_entries 三张清算域表
6. 从 backtest_trades 读取成交与 reason 信息
7. 实现 FIFO open lot 配对
8. 支持部分平仓和一笔平仓拆多条 clearing record
9. 支持回测结束未平仓强制平仓
10. 计算 trade-level gross / net PnL 和成本
11. 生成 event-level account ledger / position ledger 骨架
12. 回填或更新 backtests 统计字段
13. 为 post-close 后验统计预留字段和线性处理边界，具体计算后移
14. 补充 long / short / 部分平仓 / 强平 / 成本 / 汇总 / ledger 测试
```

## 20. 更新后的验收标准

除第 10 节已有验收外，第一阶段还应满足：

- backtest 内部不再拥有最终交易配对清算口径；
- clearing 可由 `RunFinalizer` 统一触发；
- clearing workflow 可作为独立入口重跑；
- `trade_clearings` 能追溯到来源 `backtest_trades`；
- `account_ledger_entries` 能追溯到来源 `trade_clearings` 或 raw fill；
- `position_ledger_entries` 能追溯到来源 open / close raw fill 和 `trade_clearings`；
- 每条清算记录归属于一条 backtests 记录；
- 支持 FIFO 部分平仓；
- 支持一次平仓拆分为多条清算记录；
- 回测结束未平仓持仓会生成强制平仓清算记录；
- `reason` 中的非结构化交易形成信息被保留；
- clearing 产出 event-level account ledger / position ledger 骨架和 backtests summary；
- backtests 统计字段来自 clearing 汇总，而不是 backtest 私有计算；
- trades 和 bars 有序时，清算与后验统计整体复杂度为线性级别；
- clearing 阶段为后续 analytics-reporting 的数据契约和导出打好数据库基础，但不提前定义最终报告生成物。

## 21. 实施约定与范围修正

结合当前代码现状，第一阶段实施需要增加以下约定，避免误判范围和破坏现有 CLI 生命周期。

### 21.1 CLI 触发范围

本阶段只在 `workspace/cli/workflows/backtests_lifecycle.py` 的 `RunFinalizer` 中确保触发 clearing。

不在本阶段改造所有 CLI 业务路径：

- 不要求直接修改 `backtests_run.py` 的每条 run 路径；
- 不要求本阶段把 TqSdk、Walk-Forward、数据加载失败前路径全部统一到 clearing；
- 其他 CLI 入口、独立重跑命令和用户交互命令属于 CLI 业务域后续工作。

因此，本阶段的最小触发约定是：

```text
vnpy backtest run 持久化完成
→ RunFinalizer
→ clearing workflow
→ ReportWorkflow.build
```

clearing 必须发生在 report data export 之前，否则报告会读到未清算或旧口径数据。

### 21.2 执行顺序与数据来源

本阶段明确采用：

```text
backtest run 先发生
clearing 后发生
```

职责边界：

| 模块 | 本阶段职责 |
|------|------------|
| backtest | 负责运行回测，并向 `backtest_trades` 记录所有模拟成交数据 |
| clearing | 只基于已经落库的 `backtest_trades` 和回测 K 线做配对清算 |
| clearing | 不重新运行策略，不重新跑回测，不重新生成成交 |
| data | 提供读取 `backtest_trades`、读取 K 线、写入清算表、更新 `backtests` 汇总的能力 |

也就是说，clearing 的输入是事实表和行情数据：

```text
backtest_trades + bars
→ clearing
→ trade_clearings + account_ledger_entries + position_ledger_entries + backtests summary
```

### 21.3 本阶段任务边界

由于 `workspace/clearing` 业务域当前尚未创建，第 2.1 - 2.7 类问题不是方案外风险，而是本阶段要解决的核心任务。

本阶段应覆盖：

1. 创建 `workspace/clearing`；
2. 创建 clearing workflow；
3. 在 `RunFinalizer` 中触发 clearing；
4. 新增 `trade_clearings`、`account_ledger_entries`、`position_ledger_entries`；
5. 从 `backtest_trades` 读取成交和 `reason`；
6. 基于 K 线支持期末强制平仓，并为有限后验统计预留线性处理边界；
7. 由 clearing 产出 trade-level clearing、event-level account ledger、position ledger 和 backtests summary；
8. 由 clearing 更新 `backtests` 汇总字段。

### 21.4 已解决的问题

在上述约定下，以下先前风险已被范围控制或转化为明确任务：

| 问题 | 处理 |
|------|------|
| 不应在 `backtests_run.py` 多路径散落接 clearing | 只在 `RunFinalizer` 触发 |
| clearing 不应重新跑回测 | 明确只消费 `backtest_trades` 和 bars |
| backtest 和 clearing 执行顺序不清 | 明确 backtest 先、clearing 后 |
| clearing 业务域不存在 | 明确作为本阶段核心任务 |
| `trade_clearings` / account / position ledger 不存在 | 明确作为本阶段核心任务 |
| account / position ledger 来源不清 | 明确由 clearing 生成 event-level 账本骨架，并由 summary 更新 `backtests` |
| 数据契约 / 导出范围过大 | 后移到 [analytics-reporting.md](analytics-reporting.md) |

### 21.5 仍需注意的问题

即使采用上述约定，仍需在实现时处理以下问题：

1. **`backtest_trades` 当前不是纯 raw fill 表**  
   平仓行已经包含旧 FIFO 派生的 `open_price` 和毛 `pnl`。clearing 第一阶段可以先复用其中的成交事实字段，但应避免把旧派生字段当成权威清算结果。

2. **历史数据无法完整回填 lot-level clearing**  
   历史记录缺少 `open_trade_id`、matched volume 和 lot-level 明细。需要精确 clearing 的历史实验应重新跑回测。

3. **trade-level slippage 可能无法精确拆分**  
   当前 trade 表没有无滑点基准价。第一阶段可先定义清算表字段和 run-level 成本汇总，逐笔 slippage 精确归因可后续补充。

4. **状态字段不要破坏现有 report 查询**  
   不应直接把 `run.status` 或 `backtest.status` 从 `success` 改成 `clearing_completed`。如需状态，应新增 clearing 状态字段或 metadata。

5. **account-level summary 粒度要收敛**  
   第一阶段优先按 `backtest_id` 生成 summary；run 级、多品种组合级、最优 trial 聚合留到后续 analytics/reporting 阶段明确。

6. **清算写入需要幂等**  
   clearing 重跑时应先清理同一 `backtest_id` 的旧 clearings，或使用唯一约束 / upsert，避免重复记录和重复汇总。

7. **跨表写入要考虑事务**  
   `trade_clearings`、`account_ledger_entries`、`position_ledger_entries`、`backtests` 汇总更新应尽量在一致的事务边界内完成，避免半清算状态。

8. **删除和清理路径要同步**  
   新增表后需要同步 `delete_backtest`、FK cascade 和清理脚本，避免 orphan clearing records。

## 22. Q&A：实现决策确认

### Q1：`backtest_trades` 应该记录什么？

`backtest_trades` 应明确为 backtest / vn.py 产生的原始模拟成交事实表，而不是清算结果表。

因此，FIFO 配对、开平仓归集、trade-level PnL、手续费归集、滑点归集和 account-level summary 都应由 clearing 接手。

目标边界：

```text
backtest_trades
= raw simulated fills from backtest engine

trade_clearings
= matched clearing records generated by clearing domain

account_ledger_entries / position_ledger_entries
= event-level accounting and position ledger records generated by clearing domain
```

现有 `backtest_trades` 中的 `open_price`、`pnl` 等配对派生语义应逐步迁出。若字段短期保留，也不能作为权威清算口径。

### Q2：如果 clearing 需要的数据当前 backtest 没有记录，应该怎么办？

应要求 backtest 模块补充记录，而不是让 clearing 重新跑回测。

本阶段顺序固定为：

```text
backtest run
→ write backtest_trades
→ clearing reads backtest_trades + bars
→ clearing writes clearings and summary
```

clearing 不重新执行策略、不重新撮合、不重新生成成交。它只消费已经落库的成交事实和客观行情数据。

### Q3：clearing 使用的 K 线是否必须完全等同于 backtest 当时使用的 K 线？

用于“平仓后一小时发生了什么”等后验统计时，K 线是客观市场事实，不依赖回测执行路径。

因此第一阶段可以使用：

```text
symbol + close_time
→ 查询对应 K 线
→ 计算 post-close metrics
```

不要求为后验统计重新绑定完整回测数据快照。

但如果用于回测结束强制平仓，仍应尽量使用该 backtest 覆盖区间内最后一根可用 K 线，避免使用回测结束之后的数据。

### Q4：account-level ledger 是否完全由 clearing 重新计算？

本阶段不完全替代 vn.py 的 account / daily 结果。

策略：

- 信任 vn.py 生成的 daily / equity / drawdown 等已有结果；
- clearing 负责接手此前 backtest 自己做的配对清算、手续费和成本口径；
- clearing 产出的结果与 vn.py daily / backtests summary 做对比；
- 现阶段如有合理误差，记录 warning 级别日志，不直接阻断 run。

也就是说：

```text
能直接可信地从 vn.py 获取的 backtests / daily 指标，继续保留 vn.py 口径；
此前由 backtest 私有逻辑计算的配对清算和手续费，由 clearing 接管。
```

### Q5：vn.py 手续费口径如何处理？

当前代码中 vn.py `BacktestingEngine.set_parameters` 使用 `rate` 参数，且固定元/手手续费会被换算成百分比费率。这与部分市场真实手续费规则不完全一致。

本阶段决策：

```text
手续费由 clearing 系统统一计算。
```

建议实现方向：

1. 研究并验证 vn.py `rate=0` 是否可行；
2. 若可行，回测执行阶段将 vn.py 手续费设为 0，避免 vn.py 先按错误费率扣费；
3. clearing 根据合约配置和 broker addon 统一计算手续费；
4. clearing 回填涉及手续费、net PnL、summary 的字段；
5. 与 vn.py 原始统计存在差异时记录 warning，作为迁移期校验信号。

当前代码层面看，`VnpyBacktestEngine` 已将 `rate` 传入 `engine.set_parameters(...)`，且全局 `commission_rate` 校验允许 0。因此从项目代码约束看，将传入 vn.py 的 `rate` 置为 0 是可验证的实现方向。

### Q6：滑点如何处理？

本阶段沿用已有约定：vn.py 负责在回测撮合中应用滑点，`backtest_trades.price` 记录的是实际模拟成交价。

因此 clearing 不重新调整成交价，避免重复计算滑点。clearing 只做：

- 保留实际成交价；
- 预留 / 写入 `slippage_cost` 作为成本归因字段；
- 基于合约规格和配置记录最小滑点成本口径；
- 后续在 reason 或 execution diagnostics 中补充策略要求的目标平仓价 / 平仓假设后，再计算更精确的执行偏差。

当前限制是：平仓记录的 `reason` 里可能还没有结构化记录“策略要求的平仓价”。所以本阶段可以知道实际平仓价，但不强求计算“目标价 vs 实际价”的完整滑点分解。

### Q7：是否需要兼容历史数据？

不需要。

本阶段只按当前需求直接调整表结构和运行时 schema migration。历史数据不作为设计约束；需要精确 clearing 的历史实验应重新运行。

### Q8：每次回测结束后是否可以立即触发 clearing？

可以。当前 `RunFinalizer` 的时序是：

```text
finish_run
→ ReportWorkflow.build
```

clearing 应插入在两者之间，或至少插入在 report data export 之前：

```text
finish_run / backtest data persisted
→ clearing workflow
→ ReportWorkflow.build
```

这样可以保证报告读取的是清算后的 `backtests` 和清算表数据。

注意：失败路径是否触发 clearing 不在本阶段默认展开，除非后续明确需要 partial clearing。

## 23. 当前剩余问题

在上述 Q&A 决策后，主要剩余问题已经收敛为实现细节：

1. **raw fill schema 最终字段**  
   需要确定 `backtest_trades` 中价格、数量、方向、offset、reason、source id 等字段的最终命名和迁移方式。

2. **clearing 三表和 summary 表结构**  
   已确定 clearing 域采用 `trade_clearings`、`account_ledger_entries`、`position_ledger_entries` 三张表，并回填 `backtests` summary。后续若扩展 report contracts，再在 analytics-reporting 阶段定义导出 schema。

3. **vn.py rate=0 的实际验证**  
   需要通过最小回测确认 `rate=0` 不破坏 vn.py execution / daily result 生成，并确认 clearing 可正确回填手续费和净收益。

4. **强制平仓价格口径**  
   需要明确回测结束未平仓时使用最后一根 bar 的 `close`，还是未来扩展 settlement / last price。

5. **幂等和事务**  
   clearing 重跑必须避免重复 clearings 和重复 summary，写入过程应有一致事务边界。

6. **清理路径**  
   新增表后需要同步删除逻辑、FK cascade 和清理脚本。

除以上问题外，当前方案已经完成第一阶段主体实现；剩余事项主要是后验统计、reconciliation warning、状态字段和 report contracts 等后续增强。

## 24. Contracts 兼容与后续 Issue 备案

### 24.1 本阶段是否破坏 report contracts

本阶段不主动升级 `workspace/packages/contracts` 中的 report JSON 契约。

原因是当前 clearing 改造的主要落点是数据库事实层：

```text
backtest_trades
→ trade_clearings
→ account_ledger_entries + position_ledger_entries
→ backtests summary
```

而 report artifact、前端消费契约、结构化导出格式已明确后移到 [analytics-reporting.md](analytics-reporting.md) 阶段。

第一阶段兼容原则：

- `trades.json` 继续输出现有字段；
- `backtests.json` / `summary.json` 字段名保持稳定；
- 新增的 `price`、`engine_trade_id`、`engine_order_id` 允许作为额外字段出现；
- `trade_clearings` 暂不导出为 report JSON；
- `account_ledger_entries`、`position_ledger_entries` 暂不导出为 report JSON；
- 不新增 `clearings.schema.json`，直到 analytics-reporting 阶段统一设计。

因此，本阶段可以不破坏现有 contracts。

### 24.2 `trades.json` 兼容口径

虽然数据库中的 `backtest_trades` 将转为 raw fill 语义，但 report 导出的 `trades.json` 第一阶段仍保持旧字段：

| 字段 | 第一阶段导出口径 |
|------|------------------|
| `open_price` | raw fill price，兼容旧前端字段 |
| `close_price` | raw fill price，兼容旧前端字段 |
| `pnl` | raw fill 表中不再作为权威清算结果，可为 0 或兼容值 |
| `commission` | raw fill 表中不再作为权威手续费，可为 0 |
| `price` | 新增实际模拟成交价 |

权威交易级清算结果只存在于 `trade_clearings`，不通过旧 `trades.json` 表达。`account_ledger_entries` 和 `position_ledger_entries` 是数据库事实层骨架，导出契约后移到 analytics-reporting 阶段。

### 24.3 增量导出缓存风险

当前 trades 导出的增量 fingerprint 主要依赖交易条数。如果 clearing 只改变 summary 或交易字段值，而交易条数不变，可能导致旧 `trades.json` 被缓存跳过。

第一阶段建议：

```text
clearing 完成后，本次 ReportWorkflow 应确保 trades / backtests / summary 重新导出。
```

如果实现上不方便强制刷新，应至少把 clearing 后会变化的字段纳入 fingerprint，例如：

- `backtests.total_net_pnl`；
- `backtests.total_commission`；
- `backtests.total_slippage`；
- `backtests.updated_at`；
- clearing 状态或 cleared timestamp。

### 24.4 建议后续单独提 issue 的事项

以下事项不阻塞 clearing 第一阶段，但建议后续作为独立 issue 或 analytics-reporting 阶段任务处理。

#### Issue A：Report contracts 升级到 clearing-aware schema

范围：analytics-reporting 阶段。

目标：新增或升级：

```text
clearings.schema.json
trades.schema.json
structural-diagnostics.schema.json
```

原因：现有 `trades.json` 语义偏旧，无法表达 open lot 配对、forced close、net pnl、slippage attribution 等 clearing 事实。

#### Issue B：reason 结构化与目标价记录

范围：Execution / Backtest 阶段。

目标：让平仓记录或 execution diagnostics 明确记录：

- 策略要求的目标平仓价；
- 触发的退出规则；
- 实际成交价；
- 目标价与实际价之间的执行偏差。

原因：当前 clearing 可以拿到实际模拟成交价，但还不能完整分解“策略目标价 vs 实际成交价”的滑点 / 执行偏差。

#### Issue C：TqSdk / Walk-Forward 生命周期统一

范围：CLI / Backtest 生命周期阶段。

目标：让 TqSdk、Walk-Forward 与 vnpy single/search 一样明确进入：

```text
backtest persisted
→ RunFinalizer
→ clearing
→ report
```

原因：第一阶段只保证 vnpy run 生命周期中的 clearing 触发，其他路径属于后续 CLI 业务域统一工作。

#### Issue D：report 增量缓存纳入 clearing 状态

范围：Report / Analytics 阶段。

目标：让 report cache fingerprint 能感知 clearing 输出变化。

原因：避免 clearing 结果变化但 artifact 未重新导出。

#### Issue E：生产级 account ledger / margin / settlement

范围：Clearing 后续阶段。

目标：在当前 `account_ledger_entries` / `position_ledger_entries` 骨架上扩展完整账户系统：

- 权威 margin 模型；
- daily settlement；
- bar-level / daily-level unrealized pnl；
- production-grade position book；
- 多账户 / portfolio 级账户汇总。

原因：第一阶段已经落地 event-level account / position ledger 骨架，但仍只服务回测后置清算，不实现完整生产级结算系统。

### 24.5 当前处理决定

当前已完成第一阶段主体实现。上述事项先记录在本文作为后续工程备案，不单独创建 `docs/issues` 文件。

原因：它们不是当前策略实验中发现的阻塞性框架 bug，而是 clearing 第一阶段之外的已知后续工程任务。若实施过程中发现其中某项实际阻塞当前清算链路，例如 report cache 导致清算结果无法正确进入报告，再按 `docs/issues` 工作流单独提 issue。

当前第一阶段主体实现已完成，后续按本文记录的问题继续推进增强。