# Strategy Aspects 可实现规格

> 类型：Design / 已实现设计记录  
> 状态：已实现  
> 完成日期：2026-06-16  
> Git 参考：`bb3d0d6 feat(strategy_aspects): implement advisory direction DSL and refactor MA strategy`

## 0. 交接摘要

本 spec 的核心结论：

- `strategy_aspects` 是策略切面能力库。
- 已有止盈止损类切面属于**拦截型切面**，可以提前返回 `Signal`。
- 新增方向判断能力属于**建议型切面 DSL**，只产生当前 bar 的方向理由，不直接交易。
- 建议型切面 DSL 只声明 `市场事实 -> 方向理由`。
- 策略代码负责声明 `方向理由集合 -> 交易信号`。
- `ctx.aspects` 必须是 `StrategyAspects` dataclass，不使用自由 dict。
- 使用者不传 `role` 字符串，也不传完整 `reason.key`。
- 角色和方向由装饰器名绑定，例如 `confirm_long_when`、`trend_short_when_compare`。
- 装饰器自动在类上注册 `__direction_keys__`，策略不手写 key 字符串。
- 装饰器提供可选 `tag` 参数，用于同指标同周期不同阈值时区分 name；不传时自动从 MetricRef 生成。
- `IndicatorSpec` 描述指标如何计算，不描述周期。
- `MetricRef = at(indicator, period)` 描述某周期上的某指标。
- 第一版不做 and/or 组合切面，不做 reason 派生 reason。

***

## 1. 背景

`strategy_aspects` 是策略切面能力库，用来把可复用的策略横切逻辑从具体策略类中抽离。

当前 MA 策略里存在两类逻辑：

1. **通用出场逻辑**
   - 固定比例止盈止损
   - ATR 止盈止损
   - 回撤止盈
2. **通用方向判断逻辑**
   - 某周期指标与阈值比较，例如 `1m macd > 0`
   - 两个周期的指标值比较，例如 `5m sma_short > 15m sma_long`

出场逻辑适合做成拦截型切面；方向判断逻辑适合做成建议型切面 DSL。

***

## 2. 目标

### 2.1 拦截型切面

拦截型切面可以提前返回 `Signal`，直接跳过策略原始 `on_bar`。

适用场景：

- 止盈
- 止损
- 强制平仓
- 风控熔断
- 冷却期阻断

当前已有切面：

- `with_stop_take_profit`
- `with_atr_stop_take_profit`
- `with_trailing_stop`
- `with_trade_cooldown`

`with_trade_cooldown` 基于 `state.fills` 中最近一笔成交时间和当前 `ctx.bar.datetime` 判断冷却期；只在空仓时阻断新的入场信号，不阻断已有持仓的出场逻辑。

### 2.2 建议型切面 DSL

建议型切面不直接返回交易信号，只向 `ctx.aspects` 写入当前 bar 的方向性建议。

建议型切面 DSL 的职责是声明：

```text
市场事实 -> 方向理由
```

它不声明：

```text
方向理由 -> 交易信号
```

最终是否交易，由策略自己组合理由并决定。

***

## 3. 核心数据结构

### 3.1 DirectionReason

```python
DirectionRole = Literal["trend", "confirm"]


@dataclass(frozen=True)
class DirectionReason:
    role: DirectionRole
    name: str
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.role}:{self.name}"
```

字段说明：

- `role`：理由角色。
  - `trend`：趋势方向理由，由 `trend_*` DSL 生成。
  - `confirm`：确认理由，由 `confirm_*` DSL 生成。
- `name`：理由名称，在同一 role 下应保持稳定。
- `detail`：诊断信息，用于解释该理由如何产生。
- `key`：稳定字符串形式，与 `name` 相同。

约束：

- 使用者不直接传入完整 `reason.key`。
- `DirectionReason` 由 DSL 装饰器内部生成。
- 第一阶段不在 `DirectionReason` 里加入权重、置信度等字段。
- 如果未来需要更多元信息，优先放入 `detail`；只有当策略主逻辑需要直接使用时，再提升为显式字段。

***

### 3.2 DirectionSideAdvice

`DirectionSideAdvice` 表示某个方向上的理由集合，并按 role 分桶。

```python
@dataclass
class DirectionSideAdvice:
    trend: list[DirectionReason] = field(default_factory=list)
    confirm: list[DirectionReason] = field(default_factory=list)

    @property
    def reasons(self) -> list[DirectionReason]:
        return [*self.trend, *self.confirm]

    @property
    def keys(self) -> set[str]:
        return {reason.key for reason in self.reasons}
```

字段说明：

- `trend`：该方向上的趋势理由。
- `confirm`：该方向上的确认理由。
- `reasons`：该方向上所有理由的平铺列表。
- `keys`：该方向上所有 reason key 的集合，用于策略组合判断。

设计目的：

- role 不只是 `reason.key` 里的字符串前缀，而是在结构上强制分桶。
- 策略实现者需要显式思考：哪些是趋势理由，哪些是确认理由。
- diagnostics 可以自然拆分为 trend / confirm。

***

### 3.3 DirectionAdvice

```python
@dataclass
class DirectionAdvice:
    long: DirectionSideAdvice = field(default_factory=DirectionSideAdvice)
    short: DirectionSideAdvice = field(default_factory=DirectionSideAdvice)
```

字段说明：

- `long`：支持做多方向的理由集合。
- `short`：支持做空方向的理由集合。

约束：

- 同一个 `reason.key` 正常情况下不应同时出现在 `long.keys` 和 `short.keys`。
- 如果同时出现，通常说明规则配置冲突，应该通过测试暴露。

***

### 3.4 StrategyAspects

```python
@dataclass
class StrategyAspects:
    """当前 bar 上由策略切面产生的临时建议和诊断。

    生命周期仅限本次 on_bar 调用，不应跨 bar 持久化。
    跨 bar 状态应放到 state 或未来的 state.aspect_state。
    """

    direction: DirectionAdvice = field(default_factory=DirectionAdvice)
```

设计要求：

- `ctx.aspects` 必须是 dataclass，不使用自由 `dict[str, Any]`。
- 后续新增能力时，优先向 `StrategyAspects` 增加字段，例如：
  - `risk`
  - `exit`
  - `diagnostics`
- 不把跨 bar 状态塞进 `ctx.aspects`。

***

### 3.5 BarContext 扩展

`BarContext` 应持有 `StrategyAspects`：

```python
@dataclass
class BarContext:
    symbol: str
    bar: Bar
    multi: dict[str, PeriodDataView]
    events: list[Event]
    aspects: StrategyAspects = field(default_factory=StrategyAspects)
```

***

## 4. 指标定义与指标引用

为了让每个原子表达足够短，指标计算逻辑由 `IndicatorSpec` 承载，具体周期上的指标引用由 `MetricRef` 承载。

### 4.1 IndicatorSpec

`IndicatorSpec` 只描述指标如何计算，不描述周期。

```python
@dataclass(frozen=True)
class IndicatorSpec:
    name: str
    column: str
    params: dict[str, Any]
    window: int | str
```

字段说明：

- `name`：指标需求名称，例如 `macd`、`kdj`、`sma`。
- `column`：指标输出列名，可支持模板，例如 `sma_{sma_short}`。
- `params`：指标参数，可支持模板值，例如 `{"period": "{sma_short}"}`。
- `window`：指标最小窗口，可支持模板值，例如 `{sma_short}`。

### 4.2 MetricRef

`MetricRef` 表示“某个周期上的某个指标”。

```python
@dataclass(frozen=True)
class MetricRef:
    period: str
    indicator: IndicatorSpec

    @property
    def name(self) -> str:
        return f"{self.indicator.name}_{self.period}"


def at(indicator: IndicatorSpec, period: str) -> MetricRef:
    return MetricRef(period=period, indicator=indicator)
```

字段说明：

- `period`：行情/数据周期，例如 `1m`、`5m`。
- `indicator`：指标定义。
- `name`：默认方向理由名称，格式为 `<indicator.name>_<period>`。

### 4.3 常用指标

常用指标可以定义为常量或工厂：

```python
MACD = IndicatorSpec(
    name="macd",
    column="macd_12_9_26",
    params={"fast": 12, "slow": 26, "signal": 9},
    window=35,
)

KDJ = IndicatorSpec(
    name="kdj",
    column="kdj_3_3_9",
    params={"n": 9, "k_period": 3, "d_period": 3},
    window=9,
)


def SMA(period: int | str) -> IndicatorSpec:
    return IndicatorSpec(
        name="sma",
        column=f"sma_{period}",
        params={"period": period},
        window=period,
    )
```

***

## 5. 建议型切面 DSL

建议型切面 DSL 提供一组角色绑定、方向绑定的装饰器。

设计原则：

- 使用者不传 `role` 字符串。
- 使用者不传完整 `reason.key`。
- 角色由装饰器名绑定，例如 `confirm_*`、`trend_*`。
- 方向由装饰器名绑定，例如 `*_long_*`、`*_short_*`。
- 数据结构按 role 分桶，装饰器必须写入对应桶。
- 每个装饰器只表达一个原子事实。

第一版提供两类 DSL：

1. `confirm_*_when`：指标阈值确认理由。
2. `trend_*_when_compare`：周期间趋势理由。

未来如果需要 `filter` / `risk`，应新增角色绑定装饰器，例如：

```python
filter_long_when(...)
risk_short_when(...)
```

而不是把 `role` 重新暴露为字符串参数。

***

## 6. 原子建议切面一：指标阈值确认

### 6.1 语义

```text
一个方向 + 一个 MetricRef + 一个判断条件 -> 一个 confirm 方向理由
```

示例：

```text
at(MACD, "1m") > 0              -> long:  macd_1m
at(MACD, "5m") > 0              -> long:  macd_5m
at(MACD, "1m") < 0              -> short: macd_1m
at(MACD, "5m") < 0              -> short: macd_5m
at(KDJ, "1m") < config.oversold -> long:  kdj_1m
```

### 6.2 命名

```python
confirm_long_when
confirm_short_when
```

### 6.3 装饰器签名

```python
def confirm_long_when(
    metric: MetricRef,
    op: Literal[">", "<"],
    threshold: float | str,
    *,
    tag: str | None = None,
) -> Any: ...


def confirm_short_when(
    metric: MetricRef,
    op: Literal[">", "<"],
    threshold: float | str,
    *,
    tag: str | None = None,
) -> Any: ...
```

字段说明：

- `metric`：具体周期上的指标引用，例如 `at(MACD, "1m")`。
- `op`：比较操作符。
- `threshold`：固定阈值或 `state.strategy_config` 字段名。
- `tag`：可选，自定义 reason name。不传时自动使用 `metric.name`。

生成规则：

- `confirm_long_when` 满足条件时向 `ctx.aspects.direction.long.confirm` 追加理由。
- `confirm_short_when` 满足条件时向 `ctx.aspects.direction.short.confirm` 追加理由。
- `DirectionReason.role` 固定为 `confirm`。
- `DirectionReason.name`：传了 `tag` 则使用 `tag`，否则使用 `metric.name`。
- 每个装饰器最多产生一个 `DirectionReason`。

类属性注册：

- 装饰器将生成的 key 注册到被装饰类的 `__direction_keys__` 和 `__direction_key_map__`。
- `__direction_keys__`：`dict[str, set[str]]`，按方向（`"long"` / `"short"`）收集所有 key。
- `__direction_key_map__`：`dict[str, str]`，从 `name` 映射到完整 `key`，供策略按 name 引用而无需手写 `role:` 前缀。
- 多个同方向装饰器叠加时，key 自动合并到同一集合中。

***

## 7. 原子建议切面二：周期间趋势比较

### 7.1 语义

```text
一个方向 + 两个 MetricRef 的比较 -> 一个 trend 方向理由
```

示例：

```text
at(SMA("{sma_short}"), "5m") > at(SMA("{sma_long}"), "15m") -> long:  sma_5m_vs_sma_15m
at(SMA("{sma_short}"), "5m") < at(SMA("{sma_long}"), "15m") -> short: sma_5m_vs_sma_15m
```

### 7.2 命名

```python
trend_long_when_compare
trend_short_when_compare
```

### 7.3 装饰器签名

```python
def trend_long_when_compare(
    left: MetricRef,
    op: Literal[">", "<"],
    right: MetricRef,
    *,
    tag: str | None = None,
) -> Any: ...


def trend_short_when_compare(
    left: MetricRef,
    op: Literal[">", "<"],
    right: MetricRef,
    *,
    tag: str | None = None,
) -> Any: ...
```

字段说明：

- `left`：左侧指标引用。
- `op`：比较操作符。
- `right`：右侧指标引用。
- `tag`：可选，自定义 reason name。不传时自动使用 `<left.name>_vs_<right.name>`。

生成规则：

- `trend_long_when_compare` 满足条件时向 `ctx.aspects.direction.long.trend` 追加理由。
- `trend_short_when_compare` 满足条件时向 `ctx.aspects.direction.short.trend` 追加理由。
- `DirectionReason.role` 固定为 `trend`。
- `DirectionReason.name`：传了 `tag` 则使用 `tag`，否则自动生成为 `<left.name>_vs_<right.name>`。
- name 不包含 `op`，方向由 `long` / `short` 容器表达。

***

## 8. data\_requirements 合并

建议型切面应自动合并 `MetricRef.indicator` 对应的数据需求。

合并规则：

- 同一 `MetricRef.period`、同一指标名称、同一参数的需求应去重。
- `MetricRef.indicator.column`、`params`、`window` 中的模板值从 `state.strategy_config` 解析。
- 指标缺失时，切面不写入 reason，也不抛错。

模板值解析时机：

- **`IndicatorSpec` 中的模板值**（`column`、`params`、`window`）：在构建 `data_requirements` 时解析。此时 `state.strategy_config` 已就绪，模板值替换为实际值后用于数据订阅。
- **`threshold` 中的字符串值**（如 `"kdj_oversold"`）：在 `on_bar` 运行时解析。每次切面判断时从 `state.strategy_config` 取实际阈值，支持运行时动态调整。
- **`tag`**：纯静态字符串，不含模板值，无需解析。

***

## 9. MA 策略目标落地

### 9.1 切面配置

```python
@confirm_long_when(at(MACD, "1m"), ">", 0)
@confirm_long_when(at(MACD, "5m"), ">", 0)
@confirm_short_when(at(MACD, "1m"), "<", 0)
@confirm_short_when(at(MACD, "5m"), "<", 0)
@confirm_long_when(at(KDJ, "1m"), "<", "kdj_oversold")
@confirm_long_when(at(KDJ, "5m"), "<", "kdj_oversold")
@confirm_short_when(at(KDJ, "1m"), ">", "kdj_overbought")
@confirm_short_when(at(KDJ, "5m"), ">", "kdj_overbought")
@trend_long_when_compare(at(SMA("{sma_short}"), "5m"), ">", at(SMA("{sma_long}"), "15m"))
@trend_short_when_compare(at(SMA("{sma_short}"), "5m"), "<", at(SMA("{sma_long}"), "15m"))
class MaStrategyCore(...):
    ...
```

### 9.2 策略决策

装饰器自动在类上注册 `__direction_keys__`，策略直接引用，无需手写 key 字符串。

```python
# 装饰器自动生成，等价于：
# MaStrategyCore.__direction_keys__ = {
#     "long": {"sma_5m_vs_sma_15m", "macd_1m", "macd_5m", "kdj_1m", "kdj_5m"},
#     "short": {"sma_5m_vs_sma_15m", "macd_1m", "macd_5m", "kdj_1m", "kdj_5m"},
# }

long_keys: set[str] = ctx.aspects.direction.long.keys
short_keys: set[str] = ctx.aspects.direction.short.keys

# Python set 的 <= 表示"是否为子集"，不是数值大小比较。
# 含义：装饰器声明的所有 long reason key 都出现在当前 bar 的 long_keys 中。
if type(self).__direction_keys__["long"] <= long_keys:
    return buy_signal

if type(self).__direction_keys__["short"] <= short_keys:
    return sell_signal
```

说明：

- `__direction_keys__` 由装饰器在类创建时自动注册，策略不手写任何 key 字符串。
- 装饰器变更后 `__direction_keys__` 自动同步，不存在手写与自动生成不一致的风险。
- `key` = `name`，不含 role 前缀；role 已在 `DirectionSideAdvice` 的 `trend` / `confirm` 分桶中结构化表达。

### 9.3 组合语义

切面 DSL 不提供 and/or 组合装饰器。

组合规则留在策略代码中完成：

- 单个 `set[str]` 表示 AND：所有 reason key 都出现才成立。
- 多个 `set[str]` 的 `any(...)` 可表示 OR。
- 不支持 reason 派生 reason。
- 不支持组合 reason 再被其他切面依赖。
- 不支持跨 `long` / `short` 容器组合。

示例：

```python
long_keys = ctx.aspects.direction.long.keys

long_plans = [
    {"sma_5m_vs_sma_15m", "macd_1m"},
    {"sma_5m_vs_sma_15m", "kdj_1m"},
]

long_advice = any(plan <= long_keys for plan in long_plans)
```

***

### 9.4 diagnostics

MA 策略应把方向建议写入 diagnostics：

```python
signal.diagnostics["direction_long_trend"] = [reason.key for reason in ctx.aspects.direction.long.trend]
signal.diagnostics["direction_long_confirm"] = [reason.key for reason in ctx.aspects.direction.long.confirm]
signal.diagnostics["direction_short_trend"] = [reason.key for reason in ctx.aspects.direction.short.trend]
signal.diagnostics["direction_short_confirm"] = [reason.key for reason in ctx.aspects.direction.short.confirm]
signal.diagnostics["direction_detail"] = {
    reason.key: reason.detail
    for reason in [*ctx.aspects.direction.long.reasons, *ctx.aspects.direction.short.reasons]
}
```

***

## 10. 目录规划

`strategy_aspects` 分为三层：协议层、拦截型切面、建议型方向 DSL。

推荐目录：

```text
strategies/strategy_aspects/
  __init__.py
  spec.md

  primitives.py
  indicators.py

  interceptors/
    __init__.py
    _stop_take.py
    _atr_stop_take.py
    _trailing_stop.py
    _trade_cooldown.py

  direction/
    __init__.py
    _confirm.py
    _trend.py
```

职责说明：

- `primitives.py`：放 DSL 基础结构和协议类型。
  - `DirectionReason`
  - `DirectionSideAdvice`
  - `DirectionAdvice`
  - `StrategyAspects`
  - `IndicatorSpec`
  - `MetricRef`
  - `at(...)`
- `indicators.py`：放常用指标定义和工厂。
  - `MACD`
  - `KDJ`
  - `SMA(...)`
- `interceptors/`：放拦截型切面，触发后可以提前返回 `Signal`。
  - `with_stop_take_profit`
  - `with_atr_stop_take_profit`
  - `with_trailing_stop`
  - `with_trade_cooldown`
- `direction/`：放建议型方向 DSL，只写入 `ctx.aspects.direction`，不直接返回交易信号。
  - `_confirm.py`：`confirm_long_when` / `confirm_short_when`
  - `_trend.py`：`trend_long_when_compare` / `trend_short_when_compare`

对外导出仍由 `strategy_aspects/__init__.py` 统一平铺，策略代码不直接依赖内部目录结构。

示例：

```python
from strategies.strategy_aspects import (
    MACD,
    KDJ,
    SMA,
    at,
    confirm_long_when,
    confirm_short_when,
    trend_long_when_compare,
    trend_short_when_compare,
    with_atr_stop_take_profit,
    with_stop_take_profit,
    with_trade_cooldown,
    with_trailing_stop,
)
```

***

## 11. 实现顺序

1. 按目录规划移动已有拦截型切面到 `interceptors/`。
2. 在 `primitives.py` 中新增：
   - `DirectionReason`
   - `DirectionSideAdvice`
   - `DirectionAdvice`
   - `StrategyAspects`
   - `IndicatorSpec`
   - `MetricRef`
   - `at(...)`
3. 修改 `BarContext.aspects` 类型为 `StrategyAspects`。
4. 在 `indicators.py` 中新增常用指标定义/工厂。
5. 在 `direction/_confirm.py` 中新增 `confirm_long_when` / `confirm_short_when`。
6. 在 `direction/_trend.py` 中新增 `trend_long_when_compare` / `trend_short_when_compare`。
7. 将 MA 策略里的方向判断迁移到建议型切面 DSL。
8. 更新测试。
9. 更新顶层导出。

***

## 12. 验收标准

### 12.1 单元测试

应覆盖：

- `DirectionReason.key` 生成正确。
- `MetricRef.name` 生成正确。
- `DirectionSideAdvice.reasons` / `keys` 生成正确。
- `BarContext` 默认带有空 `StrategyAspects`。
- `confirm_long_when` / `confirm_short_when`：
  - 自动合并 `MetricRef.indicator` 对应的 `data_requirements`。
  - 每个装饰器最多写入一个 reason。
  - 指标满足阈值时写入对应方向的 `confirm` 桶。
  - 指标缺失时不写入 reason。
- `trend_long_when_compare` / `trend_short_when_compare`：
  - 自动合并左右指标需求。
  - 比较条件满足时写入对应方向的 `trend` 桶。
  - 任一侧指标缺失时不写入 reason。
  - 自动生成稳定 name：`<left.name>_vs_<right.name>`。
- MA 策略：
  - 原有 long entry 行为保持。
  - 原有 short entry 行为保持。
  - 原有出场切面行为保持。

### 12.2 静态检查

至少运行：

```bash
ruff check strategies tests/strategies
pytest tests/strategies/test_new_architecture.py
pytest tests/strategies/test_decorators.py tests/strategies/test_decorators_atr.py
```

如新增专门测试文件，也应加入对应 pytest 命令。

***

## 13. 暂不做

- 不做复杂表达式，例如 `macd > 0 and kdj < 20`。
- 不做跨多个 reason 的组合判断，组合逻辑留在策略里。
- 不做评分系统。
- 不让建议型切面直接返回交易信号。
- 不把临时建议写入 `state`。
- 不在第一版 `DirectionReason` 中加入权重、置信度等扩展字段。
- 不暴露通用 `role` 字符串参数；如需新角色，新增角色绑定装饰器。

