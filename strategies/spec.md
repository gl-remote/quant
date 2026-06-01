# MA Strategy 重构规格说明书

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
- 修改 `_wrap_injected_strategy()` 方法，新增 `state: State` 参数

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
            self._state = _captured_state
            # on_init() 继承自 VnpyStrategyBridge，
            # 按 requirements.periods 从 data 模块加载所需周期数据

    return _InjectedStrategy
```

### 2. VnpyStrategyBridge
- `on_init()` 中完成 DataFeed 初始化（注册周期/指标、按 requirements 加载**非主周期**数据、预计算指标）
- Bridge 通过 `self._state: State[T]` 持有所有运行时数据，config 通过 `self._state.strategy_config` 访问，Bridge 自身不挂 config 字段不读 `self._core.config`

  ```python
  def on_init(self) -> None:
      requirements = self._core.data_requirements(self._state.strategy_config)
      self._requirements = requirements
      data_feed = DataFeedCache.get_or_create(self._state.symbol)
      data_feed.setup(requirements)
      # 主周期（1m）由 vnpy 引擎通过 on_bar 逐根喂入，不在此处预加载
      # 非主周期（5m、15m 等）按 requirements 从 data模块 加载   
      # 代码实现略
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
   - 起始和截止时间相同 → 数据一致，跳过加载
   - 起始时间相同，结束时间不同 → 仅追加新 bars（增量加载）
   - 起始时间不同 → 清空该 period 的缓存，重新加载全量数据
2. **幂等计算**：`calculate_all()` 重复调用时，已计算的指标应跳过
   - 增量加载场景：仅新追加的 bars 需要计算指标，已有 bars 的指标结果保留
   - 全量替换场景：清空计算标记，重新计算所有指标
3. **DataFeedCache.setup()** 多次注册相同指标应幂等（当前已有重复注册检查，`data_feed.py:148-150`）

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

### 15. ✅ build_context 签名变更
- **确定**：`build_context(data_feed, requirements, current_time, bar)`
- 旧签名：`build_context(data_feed, requirements, current_time)` — 从 DataFeed 第一个周期提取 bar（hack）
- 新签名新增 `bar` 参数，直接传入当前标准 Bar，避免 hack

### 16. ✅ config 传递链路
- **确定**：config 全程显式传递，不依赖 Strategy 的 config 属性
- 链路：调用方（CLI/优化器/WF）持有 `strategy_config: T` → `run(pairs, strategy_configs)` → `_run_backtest(df, symbol, strategies, strategy_configs)` → 构造 `State(strategy_config=strategy_configs[i], ...)` → `_wrap_injected_strategy(strategy, state)` → Bridge 持有 `state` → `on_bar(state, ctx)` → Strategy 读取 `state.strategy_config`
- `serialize_strategy_params` 改为接收 config dataclass 而非 Strategy 实例

### 17. ✅ Strategy[T] 与 State[T] 的类型关联
- **确定**：`Strategy[T]` 和 `State[T]` 使用同一个 `T`，即策略的配置类型（如 `MACrossParams`）
- `class MaStrategyCore(Strategy[MACrossParams])` → `State[MACrossParams]`
- Bridge 同时持有 `Strategy[T]` 和 `State[T]`，两者通过泛型参数 `T` 自然关联
- 调用方（Engine/CLI）明确知道 `T` 的具体类型，构造 State 时传入同类型的 `strategy_config`

### 18. ✅ reset() 方法的职责变化
- **确定**：`reset()` 退化为空方法。Strategy 不再持有任何状态，无需重置
- 状态迁移路径：Strategy 的 `_position`、`_fills` → State 的 `position`、`fills`
- State 在 `_run_backtest` 循环中为每个 strategy 创建全新实例（`State(symbol, period, strategy_config, capital, contract_size)`），`position`/`fills` 自然初始化为空
- Bridge 也由 vnpy 在每次 `add_strategy` 时创建全新实例，无需单独 reset
- `_run_backtest` 中原有的 `strategy.reset()` 调用可保留（空实现，不报错）或移除

### 19. ✅ Bridge 同步 State.position 的时机和方式
- **确定**：不使用手动构造 Fill 的方式，而是通过 vnpy 原生 `on_trade(trade)` 回调同步成交状态
- 时机：`_execute_buy`/`_execute_sell` 只负责发单，不更新 position。vnpy 在成交后调用 `on_trade`，此时才：
  - 根据 `trade.direction` 更新 `self._state.position`（买入设持仓，卖出清空）
  - 用 vnpy 的实际成交数据（price、volume、datetime）构造 `Fill`
  - 追加到 `self._state.fills`
  - 回调 `self._core.on_fill(fill)`
- profit 等统计由 vnpy `BacktestingEngine.calculate_statistics()` 统一计算，Bridge 不做手动统计

### 20. ✅ DataFeedCache 生命周期管理
- **确定**：DataFeedCache 全局单例是正确的设计，DataFeed 存的是行情+衍生数据而非策略状态，同 symbol 共享自然成立
- 多轮回测/多策略场景下：
  - 同一 symbol 的多个策略共享同一个 DataFeed — **正确行为**（相同指标只算一次）
  - 多次调用 `_run_backtest`（如 Walk-Forward）时，DataFeed 需要正确处理数据刷新 — 这是 `load_history_data()` 的实现要求：**重复调用时应替换而非追加数据**
  - 如果出现数据混乱，属于 DataFeed 实现层面的 bug，不是设计问题
- `DataFeedCache` 不需要 `clear()` 方法，`load_history_data()` 实现幂等替换即可

### 21. ✅ apply_strategy_config 与 serialize_strategy_params 适配
- **确定**：两个函数从接收 Strategy 改为接收 `strategy_config` dataclass 实例
- `apply_strategy_config(config, config_manager)`：直接操作 config dataclass
- `serialize_strategy_params(strategy_config)`：从 config dataclass 读取字段。调用点 `_run_backtest:193` 传入 `state.strategy_config`

### 22. ✅ UninitializedStrategy 同步更新
- **确定**：随 Strategy ABC 一起更新，移除 `config`/`position` 属性，`reset()` 改为空方法

### 23. ✅ DataFeed.load_history_data() 幂等实现
- **确定**：`DataFeed.load_history_data(period, bars)` 内部按数据范围智能处理，调用方无需关心
- 逻辑：起始和截止时间相同 → 跳过；起始相同、结束不同 → 增量追加；起始不同 → 清空该 period 缓存，全量加载
- Bridge 的 `load_history_data()` 在 `on_init` 中调用，`data_requirements()` 也在 `on_init` 中调用

### 24. ✅ build_context 签名变更
- **确定**：改为 `build_context(data_feed, requirements, current_time, bar)`，移除从 `multi[first_period].get_bar(-1)` 提取 bar 的 hack 代码

### 25. ✅ Bridge 交易流程拆分
- **确定**：`on_bar` 仅发单（`self.buy()`/`self.sell()`），不构造 Fill；成交处理移至 `on_trade`
- `_execute_buy`/`_execute_sell` 简化为纯发单 + 日志
- `self.entry_price` 移除，log 中改用 `self._state.position.entry_price`
- profit 等统计由 vnpy 统一计算

### 26. ✅ self.pos 与 State.position 的关系
- **确定**：两者数据同源（vnpy 引擎），`self._state.position` 在 `on_trade` 中用 vnpy 成交数据填充
- `self.pos`（int）：vnpy CtaTemplate 内置，正=多头、负=空头、0=无持仓。Bridge 的 `on_bar` 用它判断能否下单（`self.pos == 0` / `self.pos > 0`）
- `self._state.position`（`StrategyPosition`）：含 `direction` / `entry_price` / `volume`，供 Strategy 在 `on_bar(state, ctx)` 中读取
  - `volume = abs(self.pos)`，`direction` 从 `trade.direction` 推导
  - 用显式的 `direction` 而非正负号约定编码方向，避免歧义

### 27. ✅ _run_backtest 构造 State
- **确定**：`_run_backtest` 循环内为每个 strategy 构造 `State(symbol, period, strategy_config, capital, contract_size)`，传入 `_wrap_injected_strategy(strategy, state)`
- `run_walk_forward` 同步传入 strategy_config（因内部调用 `_run_backtest`）
- 优化器需同步传入 `strategy_configs`（`run(pairs, strategy_configs)` 接口变更）

### 28. ✅ State 文件位置与导出
- **确定**：新增 `strategies/core/state.py` 存放 `State[T]`
- 在 `strategies/core/__init__.py` 和 `strategies/__init__.py` 中导出

### 29. ✅ MaStrategyCore 内部清理
- **确定**：移除 `MACrossParams.use_data_feed`、`_close_history`、`_prev_sma_short`、`_prev_sma_long`、兼容模式方法
- `self._position` → `state.position`，`self._config` → `state.strategy_config`
- `self._capital`/`self._contract_size` → `state.capital`/`state.contract_size`（通过 `_calc_position_size` 参数传入）
- `__init__` 不再接收 `capital`/`contract_size` 参数

### 30. ✅ DataFeed.update_bar() 时间戳幂等检查
- **确定**：`DataFeed.update_bar(bar, period)` 调用时，检查该 period 中是否已存在相同时间戳的 bar，存在则跳过（不做重复追加）
- 原因：主周期（1m）的数据通过 `on_bar` 逐根喂入，而 `on_init` 只预加载非主周期（5m/15m），两者不会冲突。但加幂等检查可以防止意外重复调用导致数据错乱
- 实现：`PeriodData.append_bar()` 中检查 bar 的 `datetime` 是否已存在于 `_df` 的 timestamp 列中
