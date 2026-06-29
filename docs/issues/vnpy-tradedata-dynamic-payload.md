# vnpy TradeData 动态扩展承载策略决策 payload 风险

> 类型：框架缺陷 / 回测链路 / vnpy 桥接边界  
> 状态：已确认  
> 发现日期：2026-06-29  
> 发现分支：当前工作分支  
> 关联实验：structural-alpha-r1 工程支撑 / decision payload 落库链路  
> 相关代码：[vnpy_backtest_bridge.py](../../workspace/strategies/bridges/vnpy_backtest_bridge.py)，[vnpy_backtest_engine.py](../../workspace/backtest/vnpy_backtest_engine.py)，[store.py](../../workspace/data/store.py)

## 背景

`reason` 字段已被拆分为：

```text
reason = 人类可读摘要
decision_payload = 机器可读决策事件载荷
```

在 vnpy 回测链路中，策略信号的 `decision_payload` 需要随成交记录进入：

```text
Signal
→ Order
→ Trade / Fill
→ backtest_trades.decision_payload_json
→ report / analytics
```

当前 bridge 已将原先的“最近一次 signal 暂存”修正为：

```text
order_id → SignalDecisionContext(reason, decision_payload_json)
```

这解决了延迟成交、多订单、部分成交场景下 `reason` / `decision_payload` 可能错配的问题。

## 现象

当前实现仍通过 Python 动态属性把项目自定义字段注入 vnpy 的 `TradeData`：

```text
trade.reason = trade_reason
trade.decision_payload_json = trade_payload_json
```

随后 backtest engine 从 vnpy engine 的成交集合中读取：

```text
getattr(trade, "reason", "")
getattr(trade, "decision_payload_json", "")
```

也就是说，`decision_payload_json` 的采集链路依赖：

```text
vnpy TradeData 对象允许动态挂载项目自定义属性
```

这不是 vnpy 原生数据契约。vnpy 的标准连接点是 `orderid` / `tradeid` 等成交事实字段，而不是任意策略 payload 字段。

## 影响

| 影响面 | 说明 |
|--------|------|
| 回测诊断 payload | 若动态属性未被保留，`decision_payload_json` 会丢失 |
| report / analytics | 下游无法复用结构化决策事件，只能看到成交事实和 reason 摘要 |
| 版本升级 | 如果 vnpy `TradeData` 未来改为 slots、冻结 dataclass、复制对象或重新构造对象，动态属性可能失效 |
| 框架边界 | 项目自定义诊断字段混入 vnpy 原生对象，边界不清晰 |
| 当前策略结论 | 不直接影响成交、仓位、PnL 计算，但会影响结构化诊断和离线分析完整性 |

## 已确认的短期修复

已完成一项必要修复：

```text
_last_signal_reason / _last_signal_payload_json
→ _order_contexts[order_id]
```

这使 `reason` 和 `decision_payload` 按订单归因，而不是按“最近一次 signal”归因。

但该修复仍保留了：

```text
on_trade 中动态扩展 TradeData
```

因此本 issue 记录的是剩余的桥接边界风险。

## 最小复现方向

构造一个最小回测，要求策略信号带非空 `decision_payload`：

```text
Signal.decision_payload = {"probe": "payload-check"}
```

检查链路：

```text
1. bridge._order_contexts 是否按 orderid 记录 payload；
2. on_trade 后 vnpy trade 是否存在 decision_payload_json；
3. vnpy_backtest_engine._parse_trades() 是否能读到该字段；
4. backtest_trades.decision_payload_json 是否成功落库；
5. report JSON 是否能导出该字段。
```

进一步风险复现方向：

```text
模拟或替换一个不允许动态属性的 TradeData 对象，验证当前注入方式会失败或字段丢失。
```

## 当前处理建议

### 短期

保留当前实现，但明确它是项目侧 bridge hack：

```text
order_id → context
on_trade 动态注入 TradeData
backtest engine getattr 读取
```

同时增加回归测试，覆盖：

```text
Signal.decision_payload
→ trade.decision_payload_json
→ formatted_trades
→ backtest_trades.decision_payload_json
```

### 中期

避免依赖 `TradeData` 动态属性，改为 bridge 自己维护 sidecar：

```text
order_id / trade_id → SignalDecisionContext
```

然后 backtest engine 采集时显式合并：

```text
engine.trades
+
bridge.export_trade_contexts()
```

这样项目自定义 payload 不再污染 vnpy 原生对象。

### 长期

如果 `decision_payload` 成为正式 data line，可考虑独立表：

```text
backtest_decision_payloads
backtest_trades.decision_payload_id
```

但该建模优化应在运行时事件归因稳定后再做。

## 不建议的修复

不建议只把 `decision_payload_json` 从 `backtest_trades` 拆到独立表，而不修运行时关联方式。

原因：如果运行时 payload 已经错配，独立表只会更规范地存储错误关联。

## 修复记录

- 2026-06-29：已将 bridge 的最近 signal 暂存改为 `order_id → SignalDecisionContext`，避免 reason / payload 因延迟成交或多订单发生错配。

## 验证记录

已通过：

```text
uv run pytest workspace/tests/strategies/test_ma_strategy.py workspace/tests/backtest/test_vnpy_backtest_engine.py --tb=short
uv run mypy workspace/strategies/bridges/vnpy_backtest_bridge.py workspace/backtest/vnpy_backtest_engine.py workspace/strategies/core
ruff check workspace/strategies/bridges/vnpy_backtest_bridge.py workspace/backtest/vnpy_backtest_engine.py workspace/strategies/core
```

尚缺：专门验证 `decision_payload_json` 从 signal 到数据库 / report 的回归测试。
