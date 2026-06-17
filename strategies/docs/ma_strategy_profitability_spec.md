# MA 策略盈利改进 Spec

## 0. 核心结论

**当前策略的根本问题不是参数没调好，而是策略逻辑本身有结构性缺陷。**

学术研究（Xie et al., 2022）在 21 个中国商品期货 10 年回测中证实：**纯 SMA 交叉策略年化收益为负**。国泰君安期货研报数据：纯量价策略夏普天花板约 1.3，突破 2.0 需要基本面因子或多品种组合。

本 spec 的目标：在现有架构（切面 DSL）上，通过**逻辑重构 + 多品种组合**，将夏普从负值提升到 1.5+（单品种），多品种组合后冲击 2.0。

---

## 1. 当前策略诊断

### 1.1 结构性问题

| 问题 | 严重度 | 说明 |
|------|--------|------|
| **SMA 交叉作为趋势信号** | 致命 | 学术实证：中国商品期货上 SMA 交叉策略年化为负。MACD 显著优于 SMA |
| **入场条件过严** | 高 | 5 个条件 AND（SMA趋势 + 2×MACD + 2×KDJ），交易信号极少，大量趋势行情被错过 |
| **无趋势强度过滤** | 高 | ADX < 20 的震荡市也在交易，频繁假突破导致连续止损 |
| **无成交量确认** | 中 | 突破无量=假突破，当前完全忽略成交量 |
| **固定 SMA 周期** | 中 | 不同品种、不同波动率环境用同一周期，不自适应 |
| **无时间止损** | 中 | 持仓 N 日未盈利仍不退出，占用资金和机会成本 |
| **单品种运行** | 中 | 螺纹钢单独跑，无法通过低相关品种组合提升夏普 |
| **搜索空间过窄** | 低 | 优化器只搜 ATR 倍数和 KDJ 阈值的小范围，核心均线参数不在搜索空间 |

### 1.2 当前入场逻辑分析

```python
# 做多需要 5 个条件全部满足：
@trend_long_when_compare(at(SMA("{sma_short}"), "5m"), ">", at(SMA("{sma_long}"), "15m"))  # 5m短MA > 15m长MA
@confirm_long_when(at(MACD, "1m"), ">", 0)   # 1m MACD > 0
@confirm_long_when(at(MACD, "5m"), ">", 0)   # 5m MACD > 0
@confirm_long_when(at(KDJ, "1m"), "<", "kdj_oversold")  # 1m KDJ < 30
@confirm_long_when(at(KDJ, "5m"), "<", "kdj_oversold")  # 5m KDJ < 30
```

**问题拆解**：

1. **SMA 趋势 + MACD 确认高度相关**：SMA 短>长 ≈ MACD > 0，两个条件几乎等价，AND 组合没有增加信息量
2. **KDJ 超卖 + MACD > 0 矛盾**：KDJ 超卖意味着价格刚跌过，MACD > 0 意味着趋势向上，两者同时满足的窗口极窄
3. **1m + 5m 双周期确认冗余**：1m MACD > 0 和 5m MACD > 0 高度同步，AND 组合只是延迟入场

---

## 2. 改进方案

### 2.1 策略逻辑重构（核心改动）

**原则**：从"所有条件必须满足"改为"趋势信号 + 独立确认"，减少条件冗余，增加信息增量。

#### 改动一：趋势信号从 SMA 交叉改为 MACD 交叉

**理由**：MACD 的信号线交叉比 SMA 交叉更早、更灵敏，且学术实证 MACD 在中国商品期货上显著优于 SMA。

```python
# 旧：SMA 交叉（5m短MA vs 15m长MA）
@trend_long_when_compare(at(SMA("{sma_short}"), "5m"), ">", at(SMA("{sma_long}"), "15m"))

# 新：MACD 柱状线翻正（5m MACD histogram > 0）
@trend_long_when(at(MACD_HIST, "5m"), ">", 0)
```

**新增指标**：`MACD_HIST`（MACD 柱状线 = MACD - Signal），需要扩展 `indicators.py`。

#### 改动二：入场条件从 5-AND 改为 3-AND

**理由**：每个条件应提供独立信息增量，不冗余。

```python
# ── 做多方向切面 ──
@trend_long_when(at(MACD_HIST, "5m"), ">", 0)          # 趋势：5m MACD 柱状线翻正
@confirm_long_when(at(ADX, "15m"), ">", "adx_threshold") # 确认1：15m ADX > 25（趋势强度足够）
@confirm_long_when(at(VOL_RATIO, "5m"), ">", 1.0)       # 确认2：5m 成交量 > 5日均量（放量确认）

# ── 做空方向切面 ──
@trend_short_when(at(MACD_HIST, "5m"), "<", 0)          # 趋势：5m MACD 柱状线翻负
@confirm_short_when(at(ADX, "15m"), ">", "adx_threshold") # 确认1：15m ADX > 25
@confirm_short_when(at(VOL_RATIO, "5m"), ">", 1.0)       # 确认2：5m 成交量 > 5日均量
```

**信息增量分析**：
- MACD_HIST：趋势方向（动量类）
- ADX：趋势强度（是否值得交易），与方向无关，提供独立信息
- VOL_RATIO：资金确认（量价共振），与动量/趋势强度都不同，提供独立信息

#### 改动三：新增时间止损拦截器

**理由**：持仓 N 根 K 线未盈利则退出，避免低效持仓占用资金。

```python
@with_time_stop(bars=60)  # 持仓 60 根 1m K 线（1小时）未盈利则出场
```

#### 改动四：新增 ADX 震荡市过滤拦截器

**理由**：ADX < 阈值时即使方向建议满足也不入场，从源头减少假突破。

```python
@with_adx_filter("15m", threshold="adx_threshold")  # ADX < 25 时阻断入场信号
```

> 注意：这与 `confirm_long_when(at(ADX, "15m"), ">", "adx_threshold")` 有区别——
> ADX 作为 confirm 条件时，ADX 不满足只是"不做多"，但做空信号仍可能触发；
> ADX 作为 filter 拦截器时，ADX 不满足则"不交易"（多空都不做）。
> 推荐用 filter 方式，因为 ADX 低=震荡市，多空都不应做。

### 2.2 参数体系重构

**原则**：参数越少越好，自适应优先于固定值。

| 参数 | 旧值 | 新方案 | 理由 |
|------|------|--------|------|
| sma_short / sma_long | 10 / 40 | **删除** | SMA 交叉被 MACD 替代，不再需要 |
| macd_fast / macd_slow / macd_signal | 无（硬编码 12/26/9） | 保留默认值，可配 | MACD 参数对结果不敏感，保持标准值 |
| adx_threshold | 无 | 新增，默认 25 | ADX > 25 确认趋势存在 |
| kdj_oversold / kdj_overbought | 20 / 80 | **删除** | KDJ 不再作为入场条件 |
| stop_loss_ratio | 0.03 | 保留作为兜底止损 | ATR 止损为主，固定比例兜底 |
| take_profit_ratio | 0.05 | 保留作为兜底止盈 | ATR 止盈为主 |
| atr_stop_loss_multiplier | 2.0 | 搜索范围 1.5~3.5 | 扩大搜索范围 |
| atr_take_profit_multiplier | 3.0 | 搜索范围 2.0~5.0 | 扩大搜索范围 |
| trailing_activation_atr | 1.0 | 搜索范围 0.5~2.0 | 扩大搜索范围 |
| trailing_drawdown_ratio | 0.25 | 搜索范围 0.1~0.4 | 扩大搜索范围 |
| time_stop_bars | 无 | 新增，默认 60 | 1m 周期下 60 根 = 1 小时 |
| position_ratio | 0.1 | 改为 ATR 仓位计算 | 见 2.3 |

### 2.3 仓位管理改进

**旧方案**：固定比例仓位 `position_ratio × capital / (price × contract_size)`

**新方案**：ATR 波动率调仓

```python
vol = target_risk / (atr_value × contract_size)
```

- `target_risk`：单笔最大亏损占账户比例，默认 1%
- 含义：每笔交易的预期最大亏损 = 账户 × 1%
- 好处：高波动品种自动减仓，低波动品种自动加仓，风险均衡

**实现方式**：新增 `with_atr_position_sizing` 拦截型切面，在 on_bar 中覆盖 `calc_position_size` 的计算结果。

### 2.4 多品种组合

**原则**：3-5 个低相关品种组合，分散系统性风险。

推荐品种组合（黑色产业链 + 对冲品种）：

| 品种 | 与螺纹钢相关性 | 角色 |
|------|--------------|------|
| 螺纹钢 (rb) | 1.0 | 核心品种 |
| 铁矿石 (i) | 0.85 | 产业链联动 |
| 焦炭 (j) | 0.80 | 产业链联动 |
| 豆粕 (m) | 0.15 | 农产品对冲 |
| 沪金 (au) | -0.10 | 避险对冲 |

**实现方式**：当前架构已支持多品种独立运行（每个品种一个 Bridge + Strategy 实例），组合层面只需在结果聚合时按等权或风险平价合并净值曲线。

**预期效果**：3 品种组合夏普约 1.5×√3 ≈ 2.6（理论值，实际约 1.8-2.2）

---

## 3. 新增切面清单

### 3.1 新增指标（indicators.py）

| 指标 | IndicatorSpec | 说明 |
|------|--------------|------|
| MACD_HIST | `IndicatorSpec(name="macd_hist", column="macd_hist_12_9_26", params={"fast": 12, "slow": 26, "signal": 9}, window=35)` | MACD 柱状线 |
| ADX | `IndicatorSpec(name="adx", column="adx_14", params={"period": 14}, window=28)` | 趋势强度 |
| VOL_RATIO | `IndicatorSpec(name="vol_ratio", column="vol_ratio_5", params={"ma_period": 5}, window=5)` | 成交量比率（当前量 / N日均量） |

> `VOL_RATIO` 需要自定义计算，不在 pandas_ta 标准指标中。实现方式：在 DataFeed 的指标计算中注册自定义计算函数。

### 3.2 新增建议型切面（direction/）

| 切面 | 签名 | 说明 |
|------|------|------|
| `trend_long_when` | `trend_long_when(metric: MetricRef, op: Literal[">", "<"], threshold: float \| str, *, tag: str \| None = None)` | 单指标阈值趋势判断（现有 `trend_*_when_compare` 是双指标比较，这是单指标版本） |
| `trend_short_when` | 同上 | 做空版本 |

> 当前只有 `trend_*_when_compare`（双指标比较），缺少 `trend_*_when`（单指标阈值）。
> MACD_HIST > 0 只需要单指标阈值判断，不需要比较两个指标。

### 3.3 新增拦截型切面（interceptors/）

| 切面 | 签名 | 说明 |
|------|------|------|
| `with_time_stop` | `with_time_stop(bars: int = 60)` | 持仓 N 根 K 线未盈利则出场 |
| `with_adx_filter` | `with_adx_filter(period: str = "15m", threshold: float \| str = 25)` | ADX < 阈值时阻断所有入场信号 |
| `with_atr_position_sizing` | `with_atr_position_sizing(period: str = "15m", target_risk: float = 0.01)` | ATR 波动率调仓 |

---

## 4. 改进后的策略代码预览

```python
@dataclass
class MACrossParams:
    """均线交叉策略参数 v2 — MACD 趋势 + ADX 过滤 + 量价确认"""

    # MACD 参数（标准值，一般不需要调）
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9

    # ADX 趋势强度阈值
    adx_threshold: int = 25

    # ATR 止盈止损
    atr_period: int = 14
    atr_stop_loss_multiplier: float = 2.0
    atr_take_profit_multiplier: float = 3.0

    # 移动止盈
    trailing_activation_atr: float = 1.0
    trailing_drawdown_ratio: float = 0.25

    # 时间止损
    time_stop_bars: int = 60

    # 兜底止盈止损
    stop_loss_ratio: float = 0.03
    take_profit_ratio: float = 0.05

    # 仓位管理
    target_risk: float = 0.01  # 单笔最大亏损占账户比例


# ── 建议型方向切面 ──
# ── 做多 ──
@trend_long_when(at(MACD_HIST, "5m"), ">", 0)
@confirm_long_when(at(ADX, "15m"), ">", "adx_threshold")
@confirm_long_when(at(VOL_RATIO, "5m"), ">", 1.0)
# ── 做空 ──
@trend_short_when(at(MACD_HIST, "5m"), "<", 0)
@confirm_short_when(at(ADX, "15m"), ">", "adx_threshold")
@confirm_short_when(at(VOL_RATIO, "5m"), ">", 1.0)
# ── 拦截型切面 ──
@with_trade_cooldown(minutes=10)
@with_time_stop(bars=60)
@with_adx_filter("15m", threshold="adx_threshold")
@with_trailing_stop("15m")
@with_atr_stop_take_profit("15m")
@with_atr_position_sizing("15m", target_risk=0.01)
@with_stop_take_profit
class MaStrategyCore(Strategy[MACrossParams]):
    """MACD 趋势策略 — MACD 方向 + ADX 强度 + 量价确认"""

    name: str = STRATEGY_MA
    VERSION: str = f"{CORE_VERSION}-ma8"
    __direction_keys__: ClassVar[dict[str, set[str]]]

    def __init__(self) -> None:
        pass

    @override
    def on_bar(self, state: State[MACrossParams], ctx: BarContext) -> Signal:
        """空仓时检查方向建议是否全部满足，满足则入场"""
        config = state.strategy_config
        direction = state.position.direction
        signal = Signal()

        if not direction:
            long_keys: set[str] = ctx.aspects.direction.long.keys
            short_keys: set[str] = ctx.aspects.direction.short.keys
            direction_keys: dict[str, set[str]] = type(self).__direction_keys__

            vol = self.calc_position_size(
                ctx.bar.close, state.capital, config.position_ratio, state.contract_size, state.margin
            )

            if direction_keys["long"] <= long_keys:
                signal = Signal(action=TRADE_ACTION_BUY, reason="long_entry", volume=vol)
            elif direction_keys["short"] <= short_keys:
                signal = Signal(action=TRADE_ACTION_SELL, reason="short_entry", volume=vol)

        return signal
```

---

## 5. 实施优先级

### P0 — 策略逻辑重构（预期提升最大）

1. 新增 `trend_long_when` / `trend_short_when` 单指标阈值切面
2. 新增 `MACD_HIST`、`ADX`、`VOL_RATIO` 指标定义
3. 重构 `MACrossParams` 参数体系
4. 重写策略装饰器声明（3-AND 替代 5-AND）
5. 新增 `with_time_stop` 拦截器
6. 新增 `with_adx_filter` 拦截器

### P1 — 仓位管理改进

7. 新增 `with_atr_position_sizing` 拦截器
8. 参数搜索空间扩展（覆盖 ATR 倍数、ADX 阈值、时间止损等）

### P2 — 多品种组合

9. 结果聚合层支持多品种等权/风险平价组合
10. 配置文件支持多品种声明
11. 组合夏普计算

### P3 — 验证与上线

12. Walk-Forward 验证（WFE > 0.5 为合格）
13. 参数敏感性分析（热力图，选平台区不选尖峰）
14. 交易成本敏感性测试（滑点从 0 跳到 2 跳）

---

## 6. 预期效果

| 阶段 | 改动 | 预期夏普（单品种） | 预期夏普（3品种组合） |
|------|------|-------------------|---------------------|
| 当前 | SMA 5-AND | < 0 | < 0 |
| P0 完成 | MACD 3-AND + ADX 过滤 + 时间止损 | 0.5-0.8 | 0.9-1.4 |
| P1 完成 | + ATR 仓位 + 参数搜索 | 0.8-1.2 | 1.4-2.0 |
| P2 完成 | + 多品种组合 | 0.8-1.2 | 1.8-2.2 |

> **注意**：纯量价策略夏普天花板约 1.3（国泰君安数据），多品种组合后冲击 2.0 是合理目标。
> 如果需要单品种夏普 2.0，必须加入基本面因子（库存、利润、基差等），这超出了当前技术策略的范畴。

---

## 7. 风险与约束

1. **回测≠实盘**：risk-assessment.md 已标注"回测漂亮实盘拉胯"，Walk-Forward 是唯一可信的验证方式
2. **过拟合防护**：参数越少越好，WFE < 0.3 的策略不上线
3. **交易成本**：1m 周期策略滑点影响大，必须用 2 跳滑点做压力测试
4. **VOL_RATIO 自定义指标**：pandas_ta 没有现成的 vol_ratio，需要自定义计算逻辑
5. **ADX 参数敏感性**：ADX 阈值 20-30 之间效果差异大，需要搜索
6. **多品种数据**：当前 DataManager 是否支持铁矿石、豆粕等品种的数据加载需确认

---

## 8. 暂不做

- 不做基本面因子（库存、利润、基差等）—— 需要额外数据源，超出当前架构范围
- 不做期限结构因子（Contango/Backwardation）—— 需要多个合约数据
- 不做机器学习模型 —— 过拟合风险极高，且与当前声明式 DSL 架构不兼容
- 不做高频策略 —— 当前架构面向分钟级 CTA，不支持 tick 级
- 不改 on_bar 签名和切面 DSL 架构 —— 只在现有框架上扩展新切面
