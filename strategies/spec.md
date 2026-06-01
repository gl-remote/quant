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

定义一个 `State` dataclass，用于传递运行时配置和关键数据：

```python
from dataclasses import dataclass, field
from typing import List, Dict, Any
from strategies import StrategyPosition, Fill


@dataclass
class State:
    """运行时配置和状态，用于 Bridge 初始化和策略运行"""
    # 基本配置
    symbol: str
    period: str
    
    # 策略配置（可选，可与 Strategy.config 配合使用）
    strategy_config: Dict[str, Any] = field(default_factory=dict)
    
    # 环境配置
    capital: float = 0.0
    contract_size: int = 1
    
    # 运行时状态（可选，用于初始化时恢复）
    initial_position: StrategyPosition = field(default_factory=StrategyPosition)
    initial_fills: List[Fill] = field(default_factory=list)
    
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
- 新增 `setup(state: State)` 方法，在该方法中：
  - 通过 `DataFeedCache.setup()` 方法，根据 strategy 的 `data_requirements(config)` 完成 DataFeed 的配置
  - 加载历史数据
- 在 `on_bar` 中：
  - 调用 `DataFeed.update_bar()` 更新单根 K 线
  - 通过 `build_context()` 构造 BarContext
  - 调用 `strategy.on_bar(state, ctx)`

### 3. MaStrategyCore
- 移除兼容模式代码
- 仅保留 runtime 模式
- 修改 `data_requirements()` 签名，增加 config 参数
- 修改 `on_bar()` 签名，bar 参数改为 state

---

## 需要进一步讨论的问题

### 1. data_requirements() 签名变更
- 当前签名：`data_requirements(self) -> Optional[DataRequirements]`
- 提议签名：`data_requirements(self, config: T) -> Optional[DataRequirements]`
- **问题**：这个变更需要修改 Strategy 基类，影响所有策略，是否值得？

### 2. on_bar() 签名变更
- 当前签名：`on_bar(self, bar: Bar, ctx: Optional[BarContext] = None) -> Signal`
- 提议签名：把 `bar: Bar` 改成某种 State
- **问题**：
  - 这个 State 是什么？是 RuntimeState？还是一个新的类型？
  - State 和 BarContext 的职责边界在哪里？
  - 如果改成 State，如何保持向后兼容？

### 3. RuntimeSetup / RuntimeState 命名
- 当前用了 `RuntimeSetup`
- 提议改成某种 State
- **问题**：这个类型的作用主要是 setup 时传递信息，还是在整个运行时都在更新？

### 4. 历史数据获取问题
- Bridge 如何获取完整的历史数据来调用 `DataFeed.load_history_data()`？
- 需要考虑是从 Engine 传递一份副本过来，还是 Bridge 自己从 vnpy 引擎获取？

### 5. 初始化时机问题
- 应该在什么时候调用 bridge.setup()？
- 在 vnpy 的 on_init() 之前？之后？需要考虑 vnpy 的生命周期

### 6. 数据一致性问题
- vnpy 回测引擎回放的数据，和我们传给 DataFeed 的历史数据，是否完全一致？
- 需要确保两边的数据是相同的，避免策略看到的数据和实际回放的数据不一致

### 7. 多策略回测时的 DataFeed 共享
- 同一品种多个策略时，是否共享同一个 DataFeed？
- DataFeedCache 已经是单例，应该能处理这个问题，但需要验证
