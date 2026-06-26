# 策略运行时指标历史读取问题

> 类型：Roadmap / 框架缺陷记录  
> 状态：待修复  
> 创建日期：2026-06-26  
> 发现分支：feature/atr-signal-density  
> 发现基准 hash：9c3a740  
> 关联文档：[strategy-atr-tuning.md](./strategy-atr-tuning.md)  
> 目标：修复策略运行时对指标历史值和指标 warmup 的不稳定支持，避免策略层重复维护指标状态。

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

### 2.2 指标 window 与 warmup 语义不一致

ATR 本轮发现 `KDJ.window` 不足以支持 TA-Lib `STOCH` 稳定输出。

现象：

- `lookback_bars = KDJ.window + 1` 时，最新 KDJ 仍可能长期为 `NaN`；
- 将 5m KDJ lookback 提高到 `20` 后，入场信号才开始正常触发。

原因判断：

- 当前指标声明中的 `window` 更像“逻辑窗口”；
- 但 TA-Lib 指标常常需要额外 warmup；
- 框架目前没有统一区分：
  - 业务参数窗口；
  - 最小计算预热长度。

影响：

- 策略需求声明看起来满足，但运行时指标不可用；
- 参数化指标越复杂，越容易出现预热不足；
- 策略作者只能靠经验手动放大 `lookback_bars`。

## 3. 临时绕法

ATR 本轮采用策略层临时方案：

1. 在 `data_requirements()` 中显式把 5m KDJ lookback 提高到 `20`；
2. 每根 bar 在 `state.extra` 里保存最新 5m KDJ；
3. 入场判断只读策略自己维护的最近 KDJ 值；
4. 不再依赖 `PeriodDataView.indicator(name, -2)` 等历史指标读取。

这是绕法，不是最终框架修复。

## 4. 建议修复方向

### P1：提供可靠的指标历史读取 API

新增或修复以下能力之一：

```python
view.indicator_history(name: str, bars: int) -> list[float]
view.indicator_series(name: str, bars: int | None = None) -> pd.Series
```

要求：

- 返回值必须与当前 `PeriodDataView` 的可见时间范围一致；
- 不读取未来数据；
- 对形成中 bar 的指标值有明确语义；
- 对历史完整 bar 和最新 bar 的读取路径一致；
- 不要求策略层自己缓存指标历史。

### P2：区分 indicator window 与 warmup bars

指标声明建议增加 warmup 语义，例如：

```python
IndicatorSpec(
    name="kdj",
    params={"fastk": 9, "slowk": 3, "slowd": 3},
    window=9,
    warmup_bars=20,
)
```

要求：

- `DataRequirements` 合并时使用 `warmup_bars` 保障计算；
- 策略逻辑仍可使用 `window` 表示业务参数；
- KDJ/STOCH、MACD、ATR、SMA 等指标分别补齐合理 warmup。

### P3：补回归测试

至少覆盖：

1. 同一 `BarContext` 中：
   - `indicator(name, -1)` 可读；
   - `indicator(name, -2)` 可读；
   - `indicator_history(name, 2)` 与上述一致。
2. 多次顺序 `build_context()` 后，历史指标不会退化为 `None`。
3. KDJ 在声明的默认需求下不会因为 warmup 不足长期为 `NaN`。
4. 高周期 forming bar 场景下，历史指标读取不包含未来数据。

## 5. 验收标准

修复完成后：

- ATR 策略不再需要通过 `state.extra` 维护 KDJ 历史；
- 可直接使用框架 API 表达“最近 N 根指标状态”；
- `KDJ.window` / `warmup_bars` 语义清晰；
- 历史指标读取有单测覆盖；
- ATR 信号密度回测结果不因删除策略层缓存而退化。

## 6. 与 ATR roadmap 的关系

本问题是在 [strategy-atr-tuning.md](./strategy-atr-tuning.md) 的 P1.5 信号密度重构过程中发现的框架层缺陷。

短期 ATR 可继续使用策略层缓存推进实验；长期应先修复本框架问题，再清理 ATR 中的临时绕法。
