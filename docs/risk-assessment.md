# 回测引擎风险评估

> 基于 vnpy 原生 `BacktestingEngine` 与当前分层解耦架构的对比分析。
> 评估日期: 2026-05-30

---

## 一、总体架构

当前系统采用分层解耦架构：

```
DataManager → pd.DataFrame ─┐
                             ├→ VnpyBacktestEngine (Bridge → Strategy → Signal)
OptunaOptimizer → Strategy ─┘         ↓
                             BacktestResult → DB 持久化
```

与 vnpy 原生核心差异：

| 维度 | vnpy 原生 | 当前 |
|------|-----------|------|
| 策略模型 | 继承 `CtaTemplate`，策略内直接调 `self.buy()/self.sell()` | 纯业务 `Strategy ABC`，返回 `Signal`，桥接器负责下单翻译 |
| 数据加载 | vnpy 内置 CSV/MongoDB loader | `DataManager` + `DataStore`，多数据源 (TqSdk/AkShare) |
| 参数优化 | 内置网格搜索 | Optuna 网格+贝叶斯，SQLite 持久化 |
| 回测执行 | 单品种单策略 | 批量多品种×多策略 |
| 结果输出 | `calculate_statistics()` dict | `BacktestResult` dataclass + DB 持久化 |

---

## 二、现有优势

1. **策略与框架完全解耦** — `Strategy` 是纯 Python ABC，零依赖 vnpy，可独立测试，可低成本迁移
2. **参数搜索能力更强** — Optuna 贝叶斯优化 + 网格搜索，高维搜索效率高，Study 可断点恢复
3. **批量编排能力完整** — 多品种×多策略批量回测、Walk-Forward 内置 IS/OOS 汇总与稳定性评分
4. **数据层抽象完整** — 多源数据统一接口，回测/交易记录 SQLite 持久化
5. **错误隔离** — 单个策略异常不影响批次整体
6. **结构化结果** — `BacktestResult` dataclass 统一输出格式

---

## 三、现有缺陷

1. **交易模型简化** — 仅市价单 + 全仓平、无做空、无限价单/止损单
2. **多时间维度不足** — 单周期回测，无 Tick 级，无多周期同时加载
3. **仓位三状态不同步风险** — vnpy `self.pos` ↔ Bridge `self.entry_price` ↔ Strategy `StrategyPosition`，无自动化一致性检查
4. **交易回执链路不完整** — `on_trade`、`on_order` 未转发到策略层
5. **滑点/手续费模型粗糙** — 固定值，不区分品种和交易所
6. **策略发现脆弱** — 基于字符串动态加载，IDE 跳转/重构困难

---

## 四、重大风险

### 风险 1：vnpy API 耦合（高风险）

**表现**：`VnpyBacktestEngine` 直接依赖 `vnpy_ctastrategy.backtesting.BacktestingEngine`、`vnpy.trader.constant.Exchange/Interval`、`vnpy.trader.object.BarData`。

**后果**：vnpy 3.x 如果调整 `BacktestingEngine` API、改 `Interval` 枚举值、或变更 `calculate_statistics()` 的返回结构，整套回测系统直接瘫痪。

**缓解措施**：
- 在 `pyproject.toml`/`requirements.txt` 中显式约束 vnpy 版本范围
- 对 `BacktestingEngine` 调用链写集成测试，检测 API 变更
- 长期考虑：为 `BacktestingEngine` 编写薄适配层接口，隔离上游变更

### 风险 2：数据管道完整性不足（中风险）

**表现**：
- `df_to_vnpy_datalines()` 逐行遍历构造 `BarData`，`datetime` 需 `.to_pydatetime()` 转换
- 列验证仅检查列名存在性，不检查数据范围、类型、排序、时间戳连续性
- 缺失 K 线不报错，静默前进
- `Interval` 映射不完整（缺 4h/周/月）

**后果**：数据质量异常在回测中静默传播，结果失真而不自知。

### 风险 3：策略实例跨场景复用（中风险）

**表现**：`walk_forward` 和 `optimize` 中同一 strategy 实例通过 `reset()` 在多个窗口/试次间复用。

**后果**：如果子类 `reset()` 有遗漏状态，导致数据污染。当前 `MaStrategyCore.reset()` 正确，但未来新策略无强制机制保证清理完整性。

### 风险 4：回测→实盘一致性无保障（高风险）

**表现**：
- 回测路径：`Bridge.on_bar → Strategy.on_bar → Signal → vnpy buy/sell`
- 实盘路径：`TqsdkBridge.on_bar → Strategy.on_bar → Signal → tqsdk API`
- 两条路径完全独立实现，无自动化交叉验证

**后果**：实盘交易决策与回测不一致。回测秀肌肉、实盘裸泳。

### 风险 5：优化过拟合缺乏防护（中风险）

**表现**：
- Optuna 目标函数为 Sharpe 最大化，理论上会找到历史噪音
- Walk-Forward 提供了一定保护，但 `is_oos_return_gap` 指标基础
- 无蒙特卡洛模拟、无 bootstrap 验证、无样本外交叉验证

**后果**：参数在样本集上表现好，实盘失效。

---

## 五、未来大坑预警

| 坑 | 说明 | 预计暴露时间 |
|----|------|------------|
| **vnpy 3.x 迁移** | vnpy 正在往面向对象重写，BacktestingEngine 接口大概率变 | 6-12 个月 |
| **策略数量膨胀后维护成本** | 每个新策略需 Core + Bridge + 测试，验证成本线性增加 | 5+ 策略后 |
| **Optuna 数据库膨胀** | 持续搜索 → SQLite 库体积增大 → 查询变慢，无清理策略 | 持续积累 |
| **无确定性种子** | 如果引入随机元素或 TPE 采样不稳定，回测不可复现 | 随时可能 |
| **Bar.Close 成交偏乐观** | 短周期策略（1m/5m）误差最明显，回测漂亮实盘拉胯 | 短周期策略上线时 |
| **并行化缺失** | 批量回测+优化顺序执行，多品种多参数时是性能瓶颈 | 品种/参数增多后 |
| **数据质量无 pipeline** | TqSdk/AkShare 数据异常（断线、复权、停牌）直接体现，无异常检测 | 随时可能 |

---

## 六、优先行动项

按优先级排列：

1. **高** — 在依赖文件中显式锁定 vnpy 版本范围，跟踪 upstream 变更
2. **高** — 写 Bridge 层的交叉验证测试，确保回测/实盘路径的 `on_bar → Signal` 行为一致
3. **中** — 在 `Strategy ABC` 中引入 `reset()` 模板方法或 `__init_subclass__` 钩子，强制子类清理已知状态字段
4. **中** — 添加 post-backtest assertion 校验 vnpy pos = Bridge pos = Strategy pos
5. **中** — 为 `df_to_vnpy_datalines` 增加数据质量校验（时间连续性、缺失值、异常值）
6. **低** — 调研 vnpy 3.x 进展，规划适配方案