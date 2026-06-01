# MA Strategy 重构规格说明书

## 概述

重构 `ma_strategy.py`，使其完全采用新的 runtime 数据管理架构，移除兼容模式代码，作为验证新架构的示范策略。

## 目标

待定

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
  - 调用 strategy.on_bar(bar, ctx) 获取 Signal
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
    ├─→ 初始化时：setup DataFeed（通过 DataFeedCache）
    ├─→ on_init 时：load_history_data
    ├─→ on_bar 时：
    │   ├─→ update_bar(标准 Bar)
    │   ├─→ build_context 构造 BarContext
    │   └─→ 调用 strategy.on_bar(bar, ctx)
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
- 修改 `_wrap_injected_strategy()` 方法，新增 `state: State` 参数
- 在 `_InjectedStrategy` 的 `__init__` 中调用 bridge 的 `setup()` 方法

**实现示意**：
```python
def _wrap_injected_strategy(self, strategy: Strategy, state: State) -> type:
    from strategies.bridges import VnpyStrategyBridge
    
    _captured_strategy = strategy
    _captured_state = state
    
    class _InjectedStrategy(VnpyStrategyBridge):
        def _load_default_core(self, _setting: object | None = None) -> None:
            pass
            
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self._core = _captured_strategy
            self.setup(_captured_state)  # 在这里调用 setup()
            
    return _InjectedStrategy
```

### 2. VnpyStrategyBridge
- 持有并管理 `State` 实例：保存策略配置、环境信息、持仓、交易记录
- 新增 `setup(state: State[T])` 方法，在该方法中：
  - 通过 `DataFeedCache.setup()` 方法，根据 strategy 的 `data_requirements(state.strategy_config)` 完成 DataFeed 的配置
  - 加载历史数据
- 在 `on_bar` 中：
  - 将 vnpy Bar 转换为标准 Bar
  - 调用 `DataFeed.update_bar()` 更新单根 K 线
  - 通过 `build_context(data_feed, requirements, current_time)` 构造 BarContext
  - 调用 `strategy.on_bar(self._state, ctx)`
- 从 vnpy 同步交易状态：
  - 在成交时更新 `State` 中的 `position` 和 `fills`
  - 确保 State 里的数据和 vnpy 引擎里的一致

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

## 需要进一步讨论的问题

### 1. 历史数据获取问题
- Bridge 如何获取完整的历史数据来调用 `DataFeed.load_history_data()`？
- 需要考虑是从 Engine 传递一份副本过来，还是 Bridge 自己从 vnpy 引擎获取？

### 2. 初始化时机问题
- 应该在什么时候调用 bridge.setup()？
- 在 vnpy 的 on_init() 之前？之后？需要考虑 vnpy 的生命周期

### 3. 数据一致性问题
- vnpy 回测引擎回放的数据，和我们传给 DataFeed 的历史数据，是否完全一致？
- 需要确保两边的数据是相同的，避免策略看到的数据和实际回放的数据不一致

### 4. 多策略回测时的 DataFeed 共享
- 同一品种多个策略时，是否共享同一个 DataFeed？
- DataFeedCache 已经是单例，应该能处理这个问题，但需要验证

### 5. State 的可变性与并发安全
- State 是可变的 dataclass，多个策略共享同一个 State（如同一交易账号）时，是否有并发问题？
- **回测场景**：单线程，问题不大
- **实盘场景**：可能需要考虑并发安全，但 vnpy 实盘也是单线程的事件驱动，可能也没问题

### 5a. 回测 vs 实盘的数据来源
- **回测**：历史数据可以从 DataManager 加载为 DataFrame，然后同时提供给 vnpy 和 DataFeed
- **实盘**：vnpy 的 on_bar() 是唯一的数据来源，Bridge 需要同时：
  - 将 vnpy Bar 转换为标准 Bar
  - 更新 DataFeed
  - 构造 BarContext
  - 调用 strategy.on_bar()
- **vnpy BarData 与标准 Bar 的区别**：
  - vnpy 字段名是 open_price, high_price, close_price，我们是 open, high, close
  - 我们把所有数值转换为 float

### 6. Strategy[T] 与 State[T] 的类型关联
- Strategy 基类是泛型 `Strategy[T]`，State 也是 `State[T]`，如何明确这两个 T 的关联？

### 7. reset() 方法的职责变化
- 之前 Strategy.reset() 会重置自身状态，现在状态都在 State 里了，那 reset() 方法应该做什么？
- 需要明确 reset() 的新职责

### 8. data_requirements 的缓存策略
- `data_requirements(config)` 是在 setup() 时调用一次并缓存，还是每次 on_bar() 都调用？
- 建议在 setup() 时调用一次并保存，因为策略配置一般不会动态变化

### 9. 历史数据加载的具体实现方式
- spec.md 提到 Bridge 需要加载历史数据，但没有明确是通过 Engine 传递 DataFrame，还是通过其他方式
- Engine 里已经有完整的 DataFrame，可以传递给 Bridge

### 10. 实盘与回测的一致性验证
- 我们现在设计的是回测场景，实盘时这个架构（vnpy 同步 State）是否也适用？
- 应该是适用的，因为 Bridge 的设计就是为了适配不同的运行时
