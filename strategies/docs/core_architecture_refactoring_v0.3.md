# 核心架构重构规格说明书 v0.3

> ⚠️ **历史文档** — 2026-06-03 起 v0.3 方案中的锁/缓存设计已废弃。
>
> 保留供架构演进记录参考。

**文档版本**: v0.3（历史）  
**编制日期**: 2026年6月2日  
**文档状态**: 已废弃  
**变更记录**:
- v0.1: 初始设计方案
- v0.2: State 设计与 runtime 集成方案
- v0.3: 完整实施方案与代码实现同步

---

## 概述

重构 `ma_strategy.py`，使其完全采用新的 runtime 数据管理架构，移除兼容模式代码，作为验证新架构的示范策略。

## 目标

1. **State 解耦**：定义 `State[T]` dataclass，将策略配置、持仓、交易记录从 Strategy 迁移到 State，使 Strategy 成为纯决策逻辑
2. **Runtime 集成**：VnpyStrategyBridge 集成 DataFeedCache，通过 on_init 完成 DataFeed 初始化、on_bar 中通过 update_bar/build_context 完整接入 runtime 数据管理架构
3. **移除兼容模式**：MaStrategyCore 移除 `use_data_feed` 开关和 `_on_bar_compatible` 代码，仅保留 ctx 模式
4. **接口统一**：Strategy 基类接口变更（`on_bar(state, ctx)`、`data_requirements(config)`），移除 `config`/`position` 属性，`reset()` 退化为空方法

## 现状分析：数据管线与责任边界

### 完整数据管线

```
DataManager
    ↓ (加载 K 线数据为 DataFrame)
VnpyBacktestEngine
    ↓ (df_to_vnpy_datalines: DataFrame → vnpy BarData)
vnpy.BacktestingEngine
    ↓ (回测回放，调用 on_bar)
VnpyStrategyBridge
    ↓ (_vnpy_bar_to_bar: vnpy BarData → 标准 Bar)
MaStrategyCore
    ↓ (策略决策：on_bar(bar) → Signal)
VnpyStrategyBridge
    ↓ (_execute_buy/_execute_sell: Signal → vnpy 下单)
vnpy.BacktestingEngine
    ↓ (模拟成交)
VnpyStrategyBridge
    ↓ (构造 Fill 并回调)
MaStrategyCore
```

### 各层责任边界

#### 1. DataManager 层 (data/)
- **责任**：数据加载、存储、管理
- **输出**：KlineDataFrame (pandas.DataFrame)
- **不涉及**：策略逻辑、回测执行

#### 2. VnpyBacktestEngine 层 (backtest/)
- **责任**：
  - 接收 DataFrame + Strategy
  - DataFrame 转换为 vnpy BarData ([`df_to_vnpy_datalines`](file:///Users/REDACTED_API_KEY/Documents/src/quant/backtest/vnpy_backtest_engine.py#L42-L93))
  - 封装 vnpy BacktestingEngine 执行回测
  - 返回结构化 BacktestResult
- **关键方法**：
  - [`_run_backtest`](file:///Users/REDACTED_API_KEY/Documents/src/quant/backtest/vnpy_backtest_engine.py#L386-L474)：执行单次回测
  - [`_wrap_injected_strategy`](file:///Users/REDACTED_API_KEY/Documents/src/quant/backtest/vnpy_backtest_engine.py#L362-L384)：注入策略到桥接器
- **不涉及**：数据计算、策略决策

#### 3. VnpyStrategyBridge 层 (strategies/bridges/)
- **核心理念**：Bridge 天然就是用来适配第三方运行时的
  - 向下适配：vnpy 回测/实盘引擎
  - 向上适配：我们的 runtime 数据管理架构
- **责任**：
  - vnpy BarData → 标准 Bar ([`_vnpy_bar_to_bar`](file:///Users/REDACTED_API_KEY/Documents/src/quant/strategies/bridges/vnpy_bridge.py#L84-L93))
  - 集成 runtime 架构：DataFeed setup、数据加载、BarContext 构造
  - 调用 strategy.on_bar(state, ctx) 获取 Signal
  - Signal → vnpy buy/sell ([`_execute_buy`](file:///Users/REDACTED_API_KEY/Documents/src/quant/strategies/bridges/vnpy_bridge.py#L95-L114), [`_execute_sell`](file:///Users/REDACTED_API_KEY/Documents/src/quant/strategies/bridges/vnpy_bridge.py#L116-L136))
  - 成交后构造 Fill 并回调 strategy.on_fill(fill)
- **原则**：不持有任何交易状态，所有状态由 Strategy 管理

#### 4. MaStrategyCore 层 (strategies/ma_strategy.py)
- **当前责任**（双重模式）：
  - 兼容模式：自行维护 _close_history，计算 SMA
  - 新数据管理模式：通过 data_requirements() 声明需求，从 BarContext 获取预计算指标
- **数据流向**：
  - 输入：Bar (可选 ctx: BarContext)
  - 输出：Signal
  - 回调：on_fill(Fill) 更新仓位

### runtime 架构的接入点评估

#### 方案对比

| 维度 | Engine 接入 | Bridge 接入 |
|------|-------------|-------------|
| 数据转换 | 需要重复转换 | 天然已有转换 |
| 职责边界 | Engine 耦合 runtime | Engine 保持简单 |
| 策略 proximity | 间接持有 | 直接持有 Strategy |
| 共享数据管理 | 天然统一管理 | 需要通过 Cache 协调 |

#### 推荐方案：在 VnpyStrategyBridge 接入

```
VnpyBacktestEngine
    ↓ (df_to_vnpy_datalines 保持不变)
vnpy.BacktestingEngine
    ↓ (回测回放，调用 bridge.on_bar)
VnpyStrategyBridge (新增 runtime 接入)
    ├─→ on_init 时：注册 DataFeed + 加载多周期历史数据 + 预计算指标
    ├─→ on_bar 时：
    │   ├─→ update_bar(标准 Bar)
    │   ├─→ build_context 构造 BarContext
    │   └─→ 调用 strategy.on_bar(state, ctx)
    ↓
MaStrategyCore (仅使用 ctx 模式)
```

**关键变更点**：
- VnpyStrategyBridge 新增 runtime 集成逻辑
- VnpyBacktestEngine 需要传递 State 信息给 bridge
- MaStrategyCore 移除兼容模式，仅依赖 BarContext
- 通过 DataFeedCache 单例确保多策略数据共享

## State 数据结构

定义一个 `State` dataclass，用于传递运行时配置和关键数据，支持泛型以适配不同策略的配置类型：

```python
from dataclasses import dataclass, field
from typing import List, Dict, Any, TypeVar, Generic
from strategies import StrategyPosition, Fill

T = TypeVar('T')


@dataclass
class State(Generic[T]):
    """运行时配置和状态，用于 Bridge 初始化和策略运行

    职责划分:
    - State: 保存策略配置、环境配置、持仓、交易记录（所有运行时数据）
    - Strategy: 纯决策逻辑，不持有任何状态，通过 State 获取所有数据
    - BarContext: 保存行情数据、多周期数据、指标、事件（动态行情数据）
    - Bridge: 负责从 vnpy 获取交易状态，更新 State
    """
    # 基本配置
    symbol: str
    period: str

    # 策略配置（泛型，支持不同策略的配置类型）
    strategy_config: T

    # 环境配置
    capital: float = 0.0
    contract_size: int = 1

    # 运行时状态（由 Bridge 更新）
    position: StrategyPosition = field(default_factory=StrategyPosition)
    fills: List[Fill] = field(default_factory=list)

    # 其他扩展字段
    extra: Dict[str, Any] = field(default_factory=dict)
```

## 最终选定方案

### 1. VnpyBacktestEngine
- 仍然需要提供历史数据给 vnpy 回测引擎（这是 vnpy 的要求）
- 修改 `_wrap_injected_strategy()` 方法，接收 `strategy_name`, `strategy_params`, `symbol`，内部构造 Strategy 和 State

**实现示意**：
```python
def _wrap_injected_strategy(
    self, 
    strategy_name: str, 
    strategy_params: dict[str, Any],
    symbol: str
) -> type:
    from strategies.bridges import VnpyStrategyBridge
    from strategies.utils.loader import load_strategy
    from strategies.core.state import State

    _captured_strategy_name = strategy_name
    _captured_strategy_params = strategy_params
    _captured_symbol = symbol
    _captured_period = self.interval
    _captured_capital = self.initial_capital
    _captured_contract_size = self.contract_size

    class _InjectedStrategy(VnpyStrategyBridge):

        def _load_default_core(self, _setting: object | None = None) -> None:
            pass

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            
            # Bridge 内部构造 Strategy 和 State
            self._core = load_strategy(
                _captured_strategy_name,
                strategy_params=_captured_strategy_params
            )
            
            # 构造 State
            # 这里假设策略有 create_config 方法，或者直接用 strategy_params
            # 实际实现需要与策略的 config 类型适配
            self._state = State(
                symbol=_captured_symbol,
                period=_captured_period,
                strategy_config=_captured_strategy_params,  # 视情况转换为具体类型
                capital=_captured_capital,
                contract_size=_captured_contract_size
            )
            # on_init() 继承自 VnpyStrategyBridge，
            # 按 requirements.periods 从 data 模块加载所需周期数据

    return _InjectedStrategy
```

### 2. VnpyStrategyBridge
- `on_init()` 中完成 DataFeed 初始化（注册周期/指标、按 requirements 加载**非主周期**数据、预计算指标）
- Bridge 通过 `self._state: State[T]` 持有所有运行时数据，config 通过 `self._state.strategy_config` 访问，Bridge 自身不挂 config 字段不读 `self._core.config`

  ```python
  def on_init(self) -> None:
      if self._core.name == "_uninitialized":
          logger.error(f"[{self.strategy_name}] strategy 未注入，初始化跳过")
          return
      
      logger.info(f"[{self.strategy_name}] 桥接器初始化: {self._core.name}")
      self.write_log(f"策略初始化: {self._core.name}")
      
      # 获取数据需求
      requirements = self._core.data_requirements(self._state.strategy_config)
      self._requirements = requirements
      
      # 初始化 DataFeed
      data_feed = DataFeedCache.get_or_create(self._state.symbol)
      data_feed.setup(requirements)
      
      # 加载非主周期历史数据（DataManager 已是单例，直接获取）
      if requirements:
          from data.manager import DataManager
          dm = DataManager()  # 直接获取单例
          
          for period in requirements.periods:
              if period == self._state.period:
                  continue  # 主周期数据由 vnpy 引擎通过 on_bar 逐根喂入
                  
              # 从 data 模块加载非主周期 DataFrame，直接加载到 DataFeed
              # 使用 DataFeed.load_history_df() 避免全量转换
              # df = dm.load_kline([self._state.symbol], period=period)[0][1]
              # data_feed.load_history_df(period, df)
      
      # 预计算指标
      data_feed.calculate_all()
      self._data_feed = data_feed
  ```
- **注意**：主周期（`state.period`，如 1m）的 bar 由 vnpy 引擎通过 `on_bar` 逐根回放，不需要预加载
- 在 `on_bar` 中：
  - 将 vnpy Bar 转换为标准 Bar
  - 调用 `DataFeed.update_bar()` 更新单根 K 线
  - 通过 `build_context(data_feed, requirements, current_time, bar)` 构造 BarContext
  - 调用 `strategy.on_bar(self._state, ctx)` 获取 Signal
  - 根据 Signal 下单：`self.buy()` / `self.sell()`（仅下单，不构造 Fill）
- 从 vnpy 同步交易状态（通过 vnpy 原生回调）：
  - **`on_trade(trade)`**：vnpy 在成交后回调，此时才更新 State：
    - 更新 `self._state.position`
    - 用 vnpy 的实际成交数据构造 `Fill`，追加到 `self._state.fills`
    - 回调 `self._core.on_fill(fill)`
  - profit 等统计信息由 vnpy `BacktestingEngine.calculate_statistics()` 统一计算，Bridge 不做手动计算

### 3. Strategy 基类接口变更
- **移除**：`config` 属性（策略配置从 State 里获取）
- **移除**：`position` 属性（持仓从 State 里获取）
- **保留**：`on_fill(fill: Fill)` 回调（成交通知，策略可能需要触发逻辑）
- **保留**：`reset()` 重置方法
- **修改**：`data_requirements()` 签名：
  - 当前签名：`data_requirements(self) -> Optional[DataRequirements]`
  - 新签名：`data_requirements(self, config: T) -> Optional[DataRequirements]`
- **修改**：`on_bar()` 签名：
  - 当前签名：`on_bar(self, bar: Bar, ctx: Optional[BarContext] = None) -> Signal`
  - 新签名：`on_bar(self, state: State[T], ctx: BarContext) -> Signal`
  - 变更点：
    - 移除了单独的 `bar` 参数（`ctx` 里已经包含了 `ctx.bar`）
    - `ctx` 不再是 Optional，总是存在（移除兼容模式）
    - 新增 `state` 参数包含所有运行时数据
  - 理由：
    - `ctx` 里已经包含了当前的 `bar`（`ctx.bar`）
    - `state` 保存策略的配置、持仓、交易记录等所有运行时数据
    - `ctx` 保存行情数据、多周期数据、指标、事件等动态行情数据
    - 两个参数，职责清晰

**说明**：
- State 里的 `position` 和 `fills` 由 Bridge 同步和管理
- Strategy 通过 `on_fill` 获得成交通知，但不自己管理这些状态
- State 是唯一真实的数据来源

### 4. MaStrategyCore
- 移除兼容模式代码
- 仅保留 runtime 模式
- 实现新的接口签名

### 5. DataFeed 加载保障机制
`DataFeed` 的 `load_history_data()` 和 `calculate_all()` 在多轮流回测中可能被重复调用，需确保数据正确性：

1. **幂等加载**：`load_history_data(period, bars)` 重复调用时按数据范围智能处理：
   - 起始时间相同，且新结束时间 ≤ 现有结束时间 → 数据已包含或一致，跳过加载
   - 起始时间相同，且新结束时间 > 现有结束时间 → 仅追加增量部分
   - 起始时间不同 → 清空该 period 的缓存，重新加载全量数据
2. **幂等计算**：`calculate_all()` 重复调用时，已计算的指标应跳过
   - 增量加载场景：仅新追加的 bars 需要计算指标，已有 bars 的指标结果保留
   - 全量替换场景：清空计算标记，重新计算所有指标
3. **DataFeedCache.setup()** 多次注册相同指标应幂等（当前已有重复注册检查，`data_feed.py:148-150`）

#### DataFeed.load_history_data() 实现建议
```python
def load_history_data(self, period: str, bars: List[Bar], events: Optional[List[Event]] = None) -> None:
    if period not in self._periods:
        self.register_period(period)
    
    period_data = self._periods[period]
    
    if not bars:
        return
    
    new_start = pd.Timestamp(bars[0].datetime)
    new_end = pd.Timestamp(bars[-1].datetime)
    
    if period_data.length > 0:
        existing_start = period_data._df.index[0]
        existing_end = period_data._df.index[-1]
        
        if new_start == existing_start and new_end <= existing_end:
            # 数据已包含或范围一致，跳过
            return
        elif new_start == existing_start and new_end > existing_end:
            # 起始时间相同，新数据范围更大，仅追加增量部分
            incremental_bars = [bar for bar in bars if pd.Timestamp(bar.datetime) > existing_end]
            if incremental_bars:
                period_data.append_bars(incremental_bars)
        else:
            # 起始时间不同，清空并重新加载
            self._periods[period] = PeriodData(period)
            period_data = self._periods[period]
            period_data.append_bars(bars)
            # 清空指标计算状态
            period_data.clear_indicator_calculation()
    else:
        # 首次加载
        period_data.append_bars(bars)
    
    if events:
        self.append_events(events)
```

#### PeriodData.append_bar() 幂等检查实现建议
```python
def append_bar(self, bar: Bar) -> None:
    bar_time = pd.Timestamp(bar.datetime)

    if len(self._df) > 0:
        latest = self._df.index[-1]
        if bar_time <= latest:
            # 时间戳已存在，跳过
            if bar_time in self._df.index:
                return
            raise ValueError(f"Bar time {bar_time} is not after latest data time {latest}")

    new_row = pd.Series({
        'open': bar.open,
        'high': bar.high,
        'low': bar.low,
        'close': bar.close,
        'volume': bar.volume
    }, name=bar_time)

    self._df = pd.concat([self._df, new_row.to_frame().T])
    self._last_updated_at = pd.Timestamp.now()
    self._update_count += 1
```

### 6. DataFeed 直接支持从 DataFrame 加载（推荐方案）

**设计原则**：避免不必要的全量转换，让 DataFeed 直接支持从 DataFrame 加载，而不是先转成 Bar 列表再加载。

#### 方案 A：为 DataFeed 添加直接加载 DataFrame 的方法（推荐）

```python
# 在 strategies/runtime/data_feed.py 中添加
def load_history_df(self, period: str, df: pd.DataFrame, events: Optional[List[Event]] = None) -> None:
    """直接从 DataFrame 加载历史数据，避免全量转换"""
    if period not in self._periods:
        self.register_period(period)
    
    period_data = self._periods[period]
    
    if df.empty:
        return
    
    new_start = df['datetime'].iloc[0]
    new_end = df['datetime'].iloc[-1]
    
    if period_data.length > 0:
        existing_start = period_data._df.index[0]
        existing_end = period_data._df.index[-1]
        
        if new_start == existing_start and new_end <= existing_end:
            return
        elif new_start == existing_start and new_end > existing_end:
            # 增量加载
            incremental_df = df[df['datetime'] > existing_end].copy()
            if not incremental_df.empty:
                period_data.append_df(incremental_df)
        else:
            # 全量替换
            self._periods[period] = PeriodData(period)
            period_data = self._periods[period]
            period_data.load_df(df)
            period_data.clear_indicator_calculation()
    else:
        # 首次加载
        period_data.load_df(df)
    
    if events:
        self.append_events(events)
```

```python
# 在 strategies/runtime/period.py 中添加
def load_df(self, df: pd.DataFrame) -> None:
    """直接从 DataFrame 加载数据，不经过 Bar 转换"""
    new_df = df.set_index('datetime').copy()
    # 确保列名正确
    expected_cols = ['open', 'high', 'low', 'close', 'volume']
    for col in expected_cols:
        if col not in new_df.columns:
            new_df[col] = 0.0
        else:
            new_df[col] = new_df[col].astype(float)
    
    self._df = new_df[expected_cols]
    self._last_updated_at = pd.Timestamp.now()
    self._update_count += len(df)

def append_df(self, df: pd.DataFrame) -> None:
    """直接从 DataFrame 追加数据"""
    new_df = df.set_index('datetime').copy()
    expected_cols = ['open', 'high', 'low', 'close', 'volume']
    for col in expected_cols:
        if col not in new_df.columns:
            new_df[col] = 0.0
        else:
            new_df[col] = new_df[col].astype(float)
    
    self._df = pd.concat([self._df, new_df[expected_cols]])
    self._last_updated_at = pd.Timestamp.now()
    self._update_count += len(df)
```

#### 方案 B：提供单行转换函数（备用方案）

如果确实需要逐行转换，提供一个轻量的单行转换函数：

```python
# 在 strategies/utils/loader.py 中
from typing import Optional
import pandas as pd
from strategies.core.types import Bar

def row_to_bar(row: pd.Series) -> Bar:
    """将单行数据转换为 Bar（按需调用，避免全量转换）"""
    return Bar(
        symbol='',
        datetime=row['datetime'],
        open=float(row['open']),
        high=float(row['high']),
        low=float(row['low']),
        close=float(row['close']),
        volume=float(row['volume'])
    )
```

**优化要点**：
1. **推荐使用 **方案 A**：DataFeed 直接支持 DataFrame 加载，避免全量 Bar 转换
2. **只在必要时**使用单行转换，避免不必要的循环转换
3. **保持接口一致性**：主周期数据依然通过 on_bar 逐根喂入，非主周期数据直接加载 DataFrame

### 7. build_context() 签名变更实现
修改 `build_context()` 函数签名，新增 `bar` 参数：

```python
def build_context(
    data_feed: DataFeed,
    requirements: DataRequirements,
    current_time: Union[pd.Timestamp, dt],
    bar: Bar,
    timeout: Optional[float] = None
) -> BarContext:
    multi: Dict[str, PeriodDataView] = {}

    # 获取多周期数据
    for period, req in requirements.periods.items():
        view = data_feed.get_data(period, current_time, req.lookback_bars, timeout)
        if view is not None:
            multi[period] = view

    # 获取事件
    events: List[Event] = []
    events_req = requirements.events

    # 先获取所有事件，然后按需求筛选
    all_events = data_feed.get_events(end_time=current_time)

    for event in all_events:
        include = False
        # 检查全局事件
        if events_req.include_global_events and event.period is None:
            include = True
        # 检查周期特定事件
        if not include and events_req.include_period_events:
            if "*" in events_req.include_period_events or event.period in events_req.include_period_events:
                include = True
        # 检查事件类型白名单
        if include and events_req.event_types:
            if event.type not in events_req.event_types:
                include = True
        if include:
            events.append(event)

    return BarContext(
        symbol=data_feed.symbol,
        bar=bar,
        multi=multi,
        events=events
    )
```

---

## 已确定的问题

### 1. ✅ data_requirements() 签名变更
- **确定**：`data_requirements(self, config: T) -> Optional[DataRequirements]`

### 2. ✅ on_bar() 签名变更
- **确定**：`on_bar(self, state: State[T], ctx: BarContext) -> Signal`
- 原因：
  - `ctx` 里已经包含了 `bar`
  - 职责清晰

### 3. ✅ State 命名和职责
- **确定**：叫 `State`，支持泛型 `State[T]`
- 职责：保存策略配置、环境配置、持仓、交易记录（所有运行时数据）

### 4. ✅ 持仓管理
- **确定**：持仓和交易记录都在 `State` 里，由 Bridge 负责更新
- 好处：多个策略可以共享 vnpy 的交易状态

### 5. ✅ Strategy 的纯粹性
- **确定**：Strategy 不持有配置和持仓状态，只做纯决策逻辑，所有数据从 State 和 BarContext 获取

### 6. ✅ on_fill 回调
- **确定**：保留 `on_fill(fill: Fill)` 回调
- 用途：策略可以在成交时触发一些逻辑
- 注意：State 是唯一真实的数据来源，on_fill 只是通知，不改变数据

### 7. ✅ 历史数据获取方式
- **确定**：Engine 只负责将 DataFrame 转换为 vnpy BarData 供回放（`df_to_vnpy_datalines`），不参与 DataFeed 的数据加载。非主周期数据由 Bridge 在 `on_init` 中按 `requirements.periods` 从 data 模块自行加载
- 流程：Bridge.on_init → 读取 requirements.periods → 排除主周期 → 从 data 模块获取非主周期数据 → `DataFeed.load_history_data(period, bars)` → `DataFeed.calculate_all()`
- 主周期 bar 由 vnpy 引擎通过 `on_bar` 逐根回放，无需预加载

### 8. ✅ 初始化时机
- **确定**：所有初始化（DataFeed 周期/指标注册、多周期历史数据加载、指标预计算）统一在 `on_init()` 中完成
- 原因：`on_init` 时 `_state` 已通过 `__init__` 注入到 Bridge，且 vnpy 引擎保证 `on_init` 在 `on_bar` 回放前调用。非主周期数据由 Bridge 在 `on_init` 中通过 requirements 从 data 模块加载

### 9. ✅ 数据一致性
- **确定**：vnpy 回测引擎和 DataFeed 来自同一数据源（DataManager），数值完全一致
- vnpy 侧：`df_to_vnpy_datalines()` → vnpy BarData
- DataFeed 侧：Bridge 在 `on_init` 中从 data 模块加载 → 标准 Bar 列表 → `DataFeed.load_history_data()`
- 差异仅在于包装类型（vnpy BarData vs 标准 Bar），数值一致

### 10. ✅ 多策略 DataFeed 共享
- **确定**：同一品种多个策略共享同一个 DataFeed 实例，通过 `DataFeedCache` 单例实现
- 机制：`DataFeedCache.get_or_create(symbol)` 保证一个 symbol 对应一个 DataFeed
- 注意：多策略共享 DataFeed 时，指标仅需计算一次，但 DataFeed 的生命周期管理需单独处理

### 11. ✅ State 并发安全
- **确定**：回测场景（单线程）和实盘场景（vnpy 单线程事件驱动）均无需额外并发保护
- State 作为可变 dataclass 在单线程环境下使用，无需加锁

### 12. ✅ 回测与实盘的数据来源
- **确定**：
  - **回测**：DataManager 加载 DataFrame → 同时提供给 vnpy（`df_to_vnpy_datalines`）和 DataFeed（标准 Bar 列表）
  - **实盘**：vnpy `on_bar` 是唯一数据来源，Bridge 在 `on_bar` 中同时完成：转换标准 Bar → `DataFeed.update_bar()` → `build_context()` → `strategy.on_bar(state, ctx)`
- vnpy BarData 与标准 Bar 的转换已在 `_vnpy_bar_to_bar()` 中实现（字段映射 + float 转换）

### 13. ✅ data_requirements 缓存策略
- **确定**：在 `on_init()` 时调用 `data_requirements(state.strategy_config)` 一次并缓存结果
- 原因：策略配置在运行期间不会动态变化
- Bridge 将缓存的 requirements 用于后续每次 `on_bar` 中的 `build_context()` 调用

### 14. ✅ 实盘与回测架构一致性
- **确定**：同一套 Bridge + State + DataFeed 架构同时适用于回测和实盘
- 区别仅在于数据来源：回测由 Engine 注入历史数据，实盘由 vnpy `on_bar` 实时推送
- Bridge 的设计目标就是适配不同运行时，无需为实盘做特殊改造



### 15. ✅ config 传递链路
- **确定**：Bridge 在 `__init__` 中构造 Strategy 和 State，`strategy_config` 由 Engine 从优化器/CLI 传入的参数传递给 Bridge
- 当前链路：`run(pairs)` 接收 Strategy 实例 → `_run_backtest` 调用 `_wrap_injected_strategy(strategy)`
- 新链路：`run(pairs)` 接收 `(symbol, df, strategy_name, strategy_params)` → `_wrap_injected_strategy(strategy_name, strategy_params, symbol)` → Bridge 内部构造 Strategy 和 State → `on_bar(state, ctx)` → Strategy 读取 `state.strategy_config`
- Engine 已有全部 State 构造所需信息：`symbol`（从 pairs）、`period`（`self.interval`）、`capital`/`contract_size`（Engine 自身配置）、`strategy_params`（优化器/CLI 传入，转换为 strategy_config）

### 16. ✅ Strategy[T] 与 State[T] 的类型关联
- **确定**：`Strategy[T]` 和 `State[T]` 使用同一个 `T`，即策略的配置类型（如 `MACrossParams`）
- `class MaStrategyCore(Strategy[MACrossParams])` → `State[MACrossParams]`
- Bridge 同时持有 `Strategy[T]` 和 `State[T]`，两者通过泛型参数 `T` 自然关联
- 调用方（Engine/CLI）明确知道 `T` 的具体类型，构造 State 时传入同类型的 `strategy_config`

### 17. ✅ reset() 方法的职责变化
- **确定**：`reset()` 退化为空方法。Strategy 不再持有任何状态，无需重置
- 状态迁移路径：Strategy 的 `_position`、`_fills` → State 的 `position`、`fills`
- State 在 `_run_backtest` 循环中为每个 strategy 创建全新实例（`State(symbol, period, strategy_config, capital, contract_size)`），`position`/`fills` 自然初始化为空
- Bridge 也由 vnpy 在每次 `add_strategy` 时创建全新实例，无需单独 reset
- `_run_backtest` 中原有的 `strategy.reset()` 调用可保留（空实现，不报错）或移除

### 18. ✅ Bridge 同步 State.position 的时机和方式
- **确定**：不使用手动构造 Fill 的方式，而是通过 vnpy 原生 `on_trade(trade)` 回调同步成交状态
- 时机：`_execute_buy`/`_execute_sell` 只负责发单，不更新 position。vnpy 在成交后调用 `on_trade`，此时才：
  - 根据 `trade.direction` 更新 `self._state.position`（买入设持仓，卖出清空）
  - 用 vnpy 的实际成交数据（price、volume、datetime）构造 `Fill`
  - 追加到 `self._state.fills`
  - 回调 `self._core.on_fill(fill)`
- profit 等统计由 vnpy `BacktestingEngine.calculate_statistics()` 统一计算，Bridge 不做手动统计

### 19. ✅ DataFeedCache 生命周期管理
- **确定**：DataFeedCache 全局单例是正确的设计，DataFeed 存的是行情+衍生数据而非策略状态，同 symbol 共享自然成立
- 多轮回测/多策略场景下：
  - 同一 symbol 的多个策略共享同一个 DataFeed — **正确行为**（相同指标只算一次）
  - 多次调用 `_run_backtest`（如 Walk-Forward）时，DataFeed 需要正确处理数据刷新 — 这是 `load_history_data()` 的实现要求：**重复调用时应替换而非追加数据**
  - 如果出现数据混乱，属于 DataFeed 实现层面的 bug，不是设计问题
- `DataFeedCache` 不需要 `clear()` 方法，`load_history_data()` 实现幂等替换即可

### 20. ✅ apply_strategy_config 与 serialize_strategy_params 适配
- **确定**：两个函数从接收 Strategy 改为接收 `strategy_config` dataclass 实例
- `apply_strategy_config(config, config_manager)`：直接操作 config dataclass
- `serialize_strategy_params(strategy_config)`：从 config dataclass 读取字段。调用点 `_run_backtest:193` 传入 `state.strategy_config`

### 21. ✅ UninitializedStrategy 同步更新
- **确定**：随 Strategy ABC 一起更新，移除 `config`/`position` 属性，`reset()` 改为空方法

### 22. ✅ DataFeed.load_history_data() 幂等实现
- **确定**：`DataFeed.load_history_data(period, bars)` 内部按数据范围智能处理，调用方无需关心
- 逻辑：起始和截止时间相同 → 跳过；起始相同、结束不同 → 增量追加；起始不同 → 清空该 period 缓存，全量加载
- Bridge 的 `load_history_data()` 在 `on_init` 中调用，`data_requirements()` 也在 `on_init` 中调用

### 23. ✅ Bridge 交易流程拆分
- **确定**：`on_bar` 仅发单（`self.buy()`/`self.sell()`），不构造 Fill；成交处理移至 `on_trade`
- `_execute_buy`/`_execute_sell` 简化为纯发单 + 日志
- `self.entry_price` 移除，log 中改用 `self._state.position.entry_price`
- profit 等统计由 vnpy 统一计算

### 24. ✅ self.pos 与 State.position 的关系
- **确定**：两者数据同源（vnpy 引擎），`self._state.position` 在 `on_trade` 中用 vnpy 成交数据填充
- `self.pos`（int）：vnpy CtaTemplate 内置，正=多头、负=空头、0=无持仓。Bridge 的 `on_bar` 用它判断能否下单（`self.pos == 0` / `self.pos > 0`）
- `self._state.position`（`StrategyPosition`）：含 `direction` / `entry_price` / `volume`，供 Strategy 在 `on_bar(state, ctx)` 中读取
  - `volume = abs(self.pos)`，`direction` 从 `trade.direction` 推导
  - 用显式的 `direction` 而非正负号约定编码方向，避免歧义

### 25. ✅ _wrap_injected_strategy 内部构造 State
- **确定**：`_wrap_injected_strategy` 内部构造 Strategy 和 State，不再由 `_run_backtest` 构造 State
- `_run_backtest` 接收 `strategy_names` 和 `strategy_params_list`，调用 `_wrap_injected_strategy(strategy_name, strategy_params, symbol)`
- `run_walk_forward` 自动适配（因调用 `_run_backtest`）
- 优化器需要修改（`run(pairs)` 接口改为 `(symbol, df, strategy_name, strategy_params)`）

### 26. ✅ State 文件位置与导出
- **确定**：新增 `strategies/core/state.py` 存放 `State[T]`
- 在 `strategies/core/__init__.py` 和 `strategies/__init__.py` 中导出

### 27. ✅ MaStrategyCore 内部清理
- **确定**：移除 `MACrossParams.use_data_feed`、`_close_history`、`_prev_sma_short`、`_prev_sma_long`、兼容模式方法
- `self._position` → `state.position`，`self._config` → `state.strategy_config`
- `self._capital`/`self._contract_size` → `state.capital`/`state.contract_size`（通过 `_calc_position_size` 参数传入）
- `__init__` 不再接收 `capital`/`contract_size` 参数

### 28. ✅ DataFeed.update_bar() 时间戳幂等检查
- **确定**：`DataFeed.update_bar(bar, period)` 调用时，检查该 period 中是否已存在相同时间戳的 bar，存在则跳过（不做重复追加）
- 原因：主周期（1m）的数据通过 `on_bar` 逐根喂入，而 `on_init` 只预加载非主周期（5m/15m），两者不会冲突。但加幂等检查可以防止意外重复调用导致数据错乱
- 实现：`PeriodData.append_bar()` 中检查 bar 的 `datetime` 是否已存在于 `_df` 的 timestamp 列中

### 29. ✅ build_context 实现（已在第7节详细说明）
- 说明：`build_context(data_feed, requirements, current_time, bar)` 签名与实现在第7节有详细代码示例

---

## 文档中未提及的问题与建议

### 问题 1：VnpyBacktestEngine.run() 接口调整

**现状**：
- `VnpyBacktestEngine.run()` 主要在优化器中使用（`/Users/REDACTED_API_KEY/Documents/src/quant/backtest/optimizer.py:198`）
- 当前：优化器构造 `pairs = [(sym, df, strategy)]`，调用 `engine.run(pairs)`
- 问题：重构后需要构造 State，strategy_config 需要从外部传入

**最终方案**：Bridge 自己持有 State 和构造 Strategy

**修改内容**：

1. **Engine `run()` 接口**：
   ```python
   # 旧：list[tuple[str, pd.DataFrame, Strategy[Any]]]
   # 新：list[tuple[str, pd.DataFrame, str, dict[str, Any]]]
   # 参数：(symbol, df, strategy_name, strategy_params)
   ```

2. **Engine `_run_backtest()` 接口**：
   ```python
   # 旧：strategies: list[Strategy[Any]]
   # 新：strategy_names: list[str], strategy_params_list: list[dict[str, Any]]
   ```

3. **`_wrap_injected_strategy()` 修改**：
   - 接收：`strategy_name`, `strategy_params`, `symbol`
   - Bridge `__init__` 中：
     - 调用 `load_strategy()` 构造 Strategy
     - 构造 State
     - Bridge 持有 `self._core` 和 `self._state`

4. **优化器修改**：
   - 不再构造 Strategy 实例
   - 直接传 `(sym, df, strategy_name, strategy_params)` 给 Engine

**取舍说明**：

**为什么选这个方案**：
1. **Engine 已有全部必要信息** - capital/contract_size/interval 都在 Engine 配置里，不需要额外传递
2. **Bridge 是策略容器的自然归属** - Bridge 本身就是连接 Strategy 和 vnpy 的层，持有 State 和 Strategy 最合理
3. **职责分离清晰** - 优化器只负责参数搜索，Engine 负责回测执行，Bridge 负责策略和状态管理

**为什么不选其他方案**：
- ❌ **不选直接传 Strategy 实例**：Strategy 不再持有 config，无法通过它获取 strategy_config
- ❌ **不选传 Bridge 实例**：vnpy 需要的是策略类（class），不是实例，vnpy 会自己调用 `add_strategy()` 创建实例
- ❌ **不选 Engine 构造 Strategy 再传 Bridge**：多此一举，Bridge 自己构造更直接
- ❌ **不选更激进的简化（去掉 _wrap_injected_strategy()）**：保留 `_wrap_injected_strategy()` 可以保持代码结构清晰，方便维护

**优势**：
- Engine 已有全部必要信息（capital/contract_size/interval）
- Bridge 作为策略容器，自然持有 State 和 Strategy
- 逻辑清晰，职责分离

### 问题 2：tqsdk_bridge.py 同步更新
**状态**：本次同步处理

**问题描述**：
文档只提到了 `vnpy_bridge.py` 的更新，但 `tqsdk_bridge.py` 也需要同步更新以保持架构一致性。

**建议方案**：
- tqsdk_bridge.py 同样需要：
  1. 集成 State 机制
  2. 集成 DataFeed 架构
  3. 实现成交回调更新 State
  4. 适配新的 Strategy 接口

### 问题 3：实盘场景下非主周期数据获取方式不明确
**状态**：暂不考虑，实现时再处理

**说明**：
- 本次重构先聚焦回测场景
- 实盘场景可在后续实现时：
  - 区分回测/实盘模式走不同逻辑分支
  - 或重新写一个适配 vnpy 实盘的桥

### 问题 4：DataManager 实例如何传递给 Bridge
**状态**：已确认方案（DataManager 已改为单例）

**分析**：
- DataManager 已改为单例模式，全局共享一个实例
- 可以直接使用 `DataManager()` 获取单例，无需传递
- `_data_cache` 可以在多次回测间复用，减少 IO

**最终方案**：Bridge 在 `on_init()` 中直接获取 DataManager 单例
```python
# 在 VnpyStrategyBridge.on_init() 中
def on_init(self):
    # ... 其他代码 ...
    
    # 直接获取 DataManager 单例加载非主周期数据
    from data.manager import DataManager
    dm = DataManager()  # 获取单例，多次调用返回同一个实例
    # 加载非主周期数据
    # ...
```

**为什么选这个方案**：
- 最简单直接，不需要传递任何东西
- DataManager 单例可以复用数据缓存，性能更好
- 回测场景是单线程，不会有并发问题

### 问题 5：策略创建方式需要调整
**问题描述**：
当前策略创建可能还依赖 config 属性，重构后 Strategy 不再持有 config，需要调整策略创建方式。

**状态**：已在问题1中覆盖

**说明**：
- 此问题已在问题1的方案中处理：Bridge 在 `__init__` 中调用 `load_strategy()` 构造 Strategy，同时构造 State 并持有 `strategy_config`
- Strategy 不再持有 config，而是通过 `data_requirements(config)` 和 `on_bar(state, ctx)` 接收配置

**建议方案**（同问题1）：
- 策略构造函数不再接收 strategy_params（由 Bridge 内部处理）
- strategy_config 由调用方（Engine/CLI）通过参数传递，最终由 Bridge 放入 State
- Strategy 类通过 data_requirements(config) 和 on_bar(state, ctx) 接收配置

### 问题 6：与现有优化器/CLI 的集成
**状态**：已分析，仅需改优化器→Engine 层

**分析**：
- **CLI 不需要改** - 现有 `--strategy` 参数传递策略名称、通过配置文件读取策略参数的方式很合理
- **仅需改优化器到 Engine 这一层** - 具体链路：
  1. `_run_batch_backtest` → `execute_parameter_search` / `execute_walk_forward`：已传递 `strategy_name` 和 `strategy_params` ✓
  2. `execute_parameter_search` → `run_param_search`：已传递 `strategy_name` 和 `strategy_params` ✓
  3. `run_param_search` / `OptunaOptimizer`：当前构造 Strategy 实例然后传给 Engine，需改
  4. `VnpyBacktestEngine.run`：需从接收 `(symbol, df, strategy)` 改为接收 `(symbol, df, strategy_name, strategy_params)`

**修改点**（同问题1）：
- `OptunaOptimizer.objective`：不构造 Strategy 实例，直接传递 `strategy_name` 和 `strategy_params`
- `VnpyBacktestEngine.run`：接口改为接收 `(symbol, df, strategy_name, strategy_params)`
- `VnpyBacktestEngine._wrap_injected_strategy`：接收 `strategy_name` 和 `strategy_params`，在内部构造 Strategy 和 State
- `apply_strategy_config` 和 `serialize_strategy_params`：可能需要适配，视具体实现而定
