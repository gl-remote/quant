# 策略运行时指标历史读取问题

> 类型：Roadmap / 框架缺陷记录  
> 状态：待修复  
> 创建日期：2026-06-26  
> 发现分支：feature/atr-signal-density  
> 发现基准 hash：9c3a740  
> 开发分支：fix/framework-indicator-history  
> 开分支 hash：630296b  
> 实现提交 hash：待提交  
> 关联文档：[strategy-atr-tuning.md](./strategy-atr-tuning.md)  
> 目标：修复策略运行时对指标历史值和指标计算窗口的不稳定支持，避免策略层重复维护指标状态。

## 1. 背景

在 ATR 策略信号密度重构过程中，需要表达类似：

- 最近一根 5m KDJ 是否站上中线；
- 前一根或最近几根 5m KDJ 是否处于回调/反弹状态；
- 基于 5m 指标历史判断“回调完成后再启动”。

策略层原本尝试通过 `PeriodDataView.indicator(name, idx)` 读取历史指标，例如：

```python
view.indicator("5m_kdj_3_3_9", -1)
view.indicator("5m_kdj_3_3_9", -2)
```

实际运行中发现：`idx=-1` 通常可用，但 `idx=-2/-3/...` 经常返回 `None` 或 `NaN`，导致回调状态判断不触发。ATR 本轮临时改为把最新 KDJ 写入 `state.extra`，由策略自己维护短历史。

## 2. 已观察问题

### 2.1 历史指标读取不稳定

相关位置：

- `workspace/strategies/runtime/period.py`
  - `PeriodDataView.get_indicator(...)`
  - `PeriodDataView.store_indicator(...)`
- `workspace/strategies/runtime/data_feed.py`
  - `DataFeed.build_context(...)`
  - `_compute_all_indicators(...)`

现象：

1. 当前 bar 的最新指标值通常可通过 `_indicator_cache` 读取；
2. 历史指标值需要从 `_base_df_ref` 或 `_df_ref` 读取；
3. 动态计算出的最新指标值是否已可靠写回历史 DataFrame，依赖此前上下文构造和 persist 行为；
4. 策略运行时使用 `indicator(name, -2)` 等历史索引时，可能读到 `None` 或 `NaN`。

影响：

- 策略无法可靠表达“最近 N 根指标状态”；
- 策略不得不在 `state.extra` 中重复维护指标历史；
- 不只是 ATR 策略，任何依赖历史指标序列的策略都可能踩坑。

### 2.2 指标 window 语义不清

ATR 本轮发现 `KDJ.window` 设置过短，不足以支持 TA-Lib `STOCH` 稳定输出。

现象：

- `lookback_bars = KDJ.window + 1` 且 `KDJ.window=9` 时，最新 KDJ 仍可能长期为 `NaN`；
- 将 5m KDJ lookback 提高到 `20` 后，入场信号才开始正常触发。

原因判断：

- 指标业务参数已经在 `params` 中表达，例如 KDJ 的 `n=9`；
- `window` 原本用于告诉 `DataFeed` 最少取多少根 bar 才能计算当前指标；
- 但当前部分指标把 `window` 设置成了业务参数窗口，而不是实际计算窗口；
- TA-Lib 递推、平滑或组合指标常常需要比业务参数更多历史。

影响：

- 策略需求声明看起来满足，但运行时指标不可用；
- 参数化指标越复杂，越容易出现计算窗口设置不足；
- 策略作者只能靠经验手动放大 `lookback_bars`。

### 2.3 历史指标的 NaN 返回语义不明确

即使后续提供 `indicator_history()`，也必须明确历史值不可用时的返回语义。

当前风险：

1. `indicator(name, -2)` 可能返回 `None`、`NaN` 或不可区分的无效值；
2. 策略无法统一判断“连续 N 根满足条件”；
3. 不同策略会各自实现 `None/NaN` 过滤逻辑，导致行为不一致；
4. 指标刚完成计算窗口要求时，可用历史数量可能少于策略请求数量，但框架没有统一表达。

待修复点：

- 明确历史指标序列保留 `NaN`；
- 明确可用历史数量不足 `bars` 时返回当前视图内已有的短序列；
- 策略层如只关心有效值，应自行过滤 `NaN`；
- 连续确认、回调后再启动、趋势持续判断等场景必须能可靠区分“条件不满足”和“数据尚不可用”。

### 2.4 最新指标与历史指标读取路径不一致

当前 `indicator(name, -1)` 和 `indicator(name, -2)` 的读取路径可能不同：

- 最新值更多依赖 `_indicator_cache`；
- 历史值更多依赖 `_base_df_ref` 或 `_df_ref`；
- 动态计算出的最新指标是否写回历史序列依赖上下文构造和 persist 行为。

这会导致：

1. 最新值可读，但上一根不可读；
2. 最新值和历史序列不连续；
3. `indicator(name, -1)` 与未来的 `indicator_history(name, 1)` 语义不一致；
4. 策略无法用同一套 API 判断最近 N 根状态。

待修复点：

- 最新指标和历史指标应来自同一条“当前可见时间序列”；
- forming bar 与完整历史 bar 的边界必须明确；
- 指标动态计算结果应可靠进入该可见序列，或 API 明确区分 cache 最新值与历史完整值；
- `indicator(name, -1)`、`indicator(name, -2)`、`indicator_history(name, 2)` 的结果应可互相校验。

### 2.5 指标计算窗口不能只依赖业务参数窗口

当前部分指标把 `window` 当成业务参数窗口，导致语义过载。

问题表现：

1. `window=9` 对策略含义是 9 周期 KDJ，但 TA-Lib `STOCH` 可能需要更多历史才能稳定输出；
2. MACD、ATR、KDJ 等指标的真实计算窗口不同；
3. `DataRequirements` 看似满足，但运行时仍得到长期 `NaN`；
4. 策略作者不得不手动把 `lookback_bars` 放大到经验值。

待修复点：

- 指标声明统一用 `window` 表示最小计算历史长度；
- 业务参数保留在 `params` 中；
- `DataRequirements` / 方向 DSL 自动注册周期时使用 `window + 1`；
- `DataFeed` 构造上下文时应保证指标计算窗口足够；
- 策略层不应负责猜测 TA-Lib 或其他指标实现的计算窗口。

## 3. 临时绕法

ATR 本轮采用策略层临时方案：

1. 在 `data_requirements()` 中显式把 5m KDJ lookback 提高到 `20`；
2. 每根 bar 在 `state.extra` 里保存最新 5m KDJ；
3. 入场判断只读策略自己维护的最近 KDJ 值；
4. 不再依赖 `PeriodDataView.indicator(name, -2)` 等历史指标读取。

这是绕法，不是最终框架修复。

## 4. 建议修复方向

### P1：提供可靠的视图内指标历史读取 API

新增以下能力：

```python
view.indicator_history(name: str, bars: int) -> list[float]
view.indicator_series(name: str, bars: int | None = None) -> pd.Series
```

要求：

- 返回值必须与当前 `PeriodDataView` 的可见时间范围一致；
- 不读取未来数据；
- 对形成中 bar 的指标值有明确语义：forming bar 若存在，作为当前视图最后一根参与指标计算和历史读取；
- 对历史完整 bar 和最新 bar 的读取路径一致；
- 历史序列保留 `NaN`，策略可按业务需要过滤；
- 可用历史数量不足 `bars` 时，返回当前视图内最多 `bars` 根；
- 不要求策略层自己缓存指标历史；
- 运行时历史读取不依赖 `dump_indicators`，也不依赖把指标列持久化回底层 DataFrame。

建议实现：

现有缓存机制分工如下：

- `PeriodDataView._indicator_cache` 已缓存当前视图最新指标值，但只覆盖 `idx=-1`；本修复应复用并扩展这套视图内缓存，而不是另建无关机制；
- `DataFeed` 的内存缓存缓存的是整个 `DataFeed` 实例，主要用于避免重复加载/反序列化，不适合作为单个 `BarContext` 的指标历史读取 API；
- DataFrame/parquet 指标列缓存依赖 `dump_indicators` 或磁盘缓存，适合调试/落地/恢复，不应成为运行时指标历史读取的主路径。

因此主方案是：扩展现有 `PeriodDataView` 指标缓存，从“只缓存最新值”升级为“缓存当前视图内完整指标序列”。

1. `DataFeed.calculate_indicators(...)` 仍负责在 `build_context(...)` 中统一计算指标；
2. `PeriodDataView.store_indicator(...)` 除保存最新值 `_indicator_cache` 外，还保存当前视图范围内完整的 `result_series`；
3. `PeriodDataView.indicator(name, idx)` 优先从视图内指标序列缓存读取，使 `idx=-1/-2/-3` 走同一套路径；
4. DataFrame 指标列读取只作为兼容旧缓存/落地数据的 fallback，不作为运行时历史读取的主路径；
5. 高周期历史指标不得使用高周期行号直接索引 `base_df`，避免周期行号与基础周期行号错位。

### P2：明确 indicator window 为计算窗口

不新增额外预热字段，统一收敛 `IndicatorSpec.window` 语义：

```python
IndicatorSpec(
    name="kdj",
    params={"n": 9, "k_period": 3, "d_period": 3},
    window=20,
)
```

语义：

- `params` 表示指标业务参数，例如 KDJ 的 `n=9`；
- `window` 表示计算当前指标值所需的最小历史 bar 数；
- 当指标需要比业务参数更多历史时，直接放大 `window`；
- 不再区分额外预热字段，避免框架概念过度复杂。

要求：

- `DataRequirements` / 方向 DSL 自动注册周期时，使用 `window + 1` 保障计算和历史读取；
- `DataFeed` 构建含指标的周期视图时，应使用指标 `window` 放大实际计算视图，避免策略手写较小 `lookback_bars` 时导致指标长期为 `NaN`；
- 允许带指标的 `PeriodDataView.length` 大于策略显式声明的 `lookback_bars`，因为此时 lookback 是最小业务需求，指标 `window` 是计算需求；
- 策略业务参数仍通过 `params` 表达；
- 在 `strategy_aspects/indicators.py` 模块注释中写明 `window` 计算规则；
- KDJ/STOCH、MACD、ATR、SMA 等指标分别补齐合理 `window`。

建议默认值：

- `SMA(period)`: `window=period`；
- `ATR(period)`: `window=period + 1` 或框架测试确认后的最小稳定值；
- `MACD(12, 26, 9)`: `window=35`；
- `KDJ(9, 3, 3)`: `window=20`。

### P3：清理 ATR 策略临时绕法

在 P1/P2 完成后：

1. 删除 ATR 策略中通过 `state.extra` 维护 KDJ 短历史的临时逻辑；
2. `_recent_kdj_values(...)` 改为直接调用 `view.indicator_history(...)`；
3. ATR 的 5m KDJ `lookback_bars=20` 手动放大逻辑应由框架指标 `window` 接管，策略层只保留业务所需 lookback。

### P4：补回归测试

至少覆盖：

1. 同一 `BarContext` 中：
   - `indicator(name, -1)` 可读；
   - `indicator(name, -2)` 可读；
   - `indicator_history(name, 2)` 与上述一致。
2. 多次顺序 `build_context()` 后，历史指标不会退化为 `None`。
3. KDJ 在声明的默认需求下不会因为计算窗口不足长期为 `NaN`。
4. 高周期 forming bar 场景下，历史指标读取不包含未来数据。
5. `dump_indicators=False` 时，运行时历史指标读取仍然稳定。
6. 指标序列缓存优先于底层 DataFrame fallback，避免高周期 base_df 行号错位。

## 5. 验收标准

修复完成后：

- ATR 策略不再需要通过 `state.extra` 维护 KDJ 历史；
- 可直接使用框架 API 表达“最近 N 根指标状态”；
- `KDJ.window` 语义清晰；
- 历史指标读取有单测覆盖；
- ATR 信号密度回测结果不因删除策略层缓存而退化。

## 6. 与 ATR roadmap 的关系

本问题是在 [strategy-atr-tuning.md](./strategy-atr-tuning.md) 的 P1.5 信号密度重构过程中发现的框架层缺陷。

短期 ATR 可继续使用策略层缓存推进实验；长期应先修复本框架问题，再清理 ATR 中的临时绕法。
