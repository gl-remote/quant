# Strategy Aspects 设计草案

## 目标

`strategy_aspects` 存放可复用的策略切面，用来把通用交易逻辑从具体策略中抽离。

切面分两类：

1. **拦截型切面**：可以提前返回 `Signal`，直接跳过策略原始逻辑。
2. **建议型切面**：只向 `ctx.aspects` 写入方向性建议，不直接做交易决策。

当前止盈止损类切面属于拦截型切面。后续趋势判断、指标判断、周期判断优先做成建议型切面。

---

## 建议型切面的输出协议

建议型切面统一写入：

```python
ctx.aspects["direction"] = {
    "long": ["reason1", "reason2"],
    "short": ["reason3"],
    "details": {
        "reason1": {...},
        "reason2": {...},
        "reason3": {...},
    },
}
```

含义：

- `long`：支持做多方向的理由 key 列表。
- `short`：支持做空方向的理由 key 列表。
- `details`：每个理由的诊断信息，用于调试、回测记录、解释策略决策。

切面只负责追加理由，不负责判断最终是否开仓。

策略自行组合：

```python
required = {"ma_5m_15m", "macd_1m", "macd_5m", "kdj_1m", "kdj_5m"}
direction = ctx.aspects["direction"]

long_advice = required <= set(direction["long"])
short_advice = required <= set(direction["short"])
```

---

## 原子建议切面

### 1. 指标阈值比较切面

形式：

```text
(周期, 指标, 临界值) -> 方向
```

示例：

```text
1m macd_12_9_26 > 0              -> long:  macd_1m
1m macd_12_9_26 < 0              -> short: macd_1m
5m kdj_3_3_9 < config.oversold   -> long:  kdj_5m
5m kdj_3_3_9 > config.overbought -> short: kdj_5m
```

建议命名：

```python
with_indicator_thresholds
IndicatorThresholdRule
```

规则草案：

```python
@dataclass(frozen=True)
class IndicatorThresholdRule:
    key: str
    period: str
    indicator: str
    long_operator: Literal[">", "<"]
    long_threshold: float | str
    short_operator: Literal[">", "<"]
    short_threshold: float | str
```

说明：

- `indicator` 可以是固定列名，如 `macd_12_9_26`。
- 后续可支持模板，如 `sma_{sma_short}`。
- `threshold` 可以是固定数值，也可以是 `strategy_config` 字段名。

输出示例：

```python
ctx.aspects["direction"]["long"].append("macd_1m")
ctx.aspects["direction"]["details"]["macd_1m"] = {
    "source": "indicator_threshold",
    "period": "1m",
    "indicator": "macd_12_9_26",
    "value": 1.2,
    "operator": ">",
    "threshold": 0,
}
```

---

### 2. 周期间比较切面

形式：

```text
(周期, 周期) -> 方向
```

更准确地说，是：

```text
(周期A的指标值, 周期B的指标值) -> 方向
```

示例：

```text
5m sma_{sma_short} > 15m sma_{sma_long} -> long:  ma_5m_15m
5m sma_{sma_short} < 15m sma_{sma_long} -> short: ma_5m_15m
```

建议命名：

```python
with_period_compares
PeriodCompareRule
```

规则草案：

```python
@dataclass(frozen=True)
class PeriodCompareRule:
    key: str
    left_period: str
    left_indicator: str
    right_period: str
    right_indicator: str
    long_operator: Literal[">", "<"]
    short_operator: Literal[">", "<"]
```

输出示例：

```python
ctx.aspects["direction"]["long"].append("ma_5m_15m")
ctx.aspects["direction"]["details"]["ma_5m_15m"] = {
    "source": "period_compare",
    "left_period": "5m",
    "left_indicator": "sma_10",
    "left": 105.0,
    "right_period": "15m",
    "right_indicator": "sma_40",
    "right": 100.0,
    "operator": ">",
}
```

---

## MA 策略的目标写法

```python
@with_indicator_thresholds([
    IndicatorThresholdRule("macd_1m", "1m", "macd_12_9_26", ">", 0, "<", 0),
    IndicatorThresholdRule("macd_5m", "5m", "macd_12_9_26", ">", 0, "<", 0),
    IndicatorThresholdRule("kdj_1m", "1m", "kdj_3_3_9", "<", "kdj_oversold", ">", "kdj_overbought"),
    IndicatorThresholdRule("kdj_5m", "5m", "kdj_3_3_9", "<", "kdj_oversold", ">", "kdj_overbought"),
])
@with_period_compares([
    PeriodCompareRule("ma_5m_15m", "5m", "sma_{sma_short}", "15m", "sma_{sma_long}", ">", "<"),
])
class MaStrategyCore(...):
    ...
```

策略决策：

```python
required = {"ma_5m_15m", "macd_1m", "macd_5m", "kdj_1m", "kdj_5m"}
direction = ctx.aspects["direction"]

if required <= set(direction["long"]):
    return buy_signal
if required <= set(direction["short"]):
    return sell_signal
```

---

## 设计原则

1. **切面只产出原子理由，不组合最终交易规则。**
2. **策略只依赖 reason key 集合，不关心 reason 来自哪类切面。**
3. **细节放入 `details`，主决策路径只看 `long` / `short`。**
4. **优先保持简单，不引入表达式解析系统。**
5. **需要的指标由切面自动合并到 `data_requirements`。**
6. **同一 reason key 不应同时出现在 `long` 和 `short`，除非规则配置错误。**

---

## 暂不做

- 不做复杂表达式，例如 `long_when="macd > 0 and kdj < 20"`。
- 不做跨多个 reason 的组合判断，组合逻辑留在策略里。
- 不让建议型切面直接返回交易信号。
- 不把临时建议写入 `state`。
