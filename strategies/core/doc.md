# Core 模块设计文档

## 一、设计目标

`strategies/core` 是整个策略系统的**基础设施层**，提供三个核心价值：

1. **框架无关的策略抽象**：`Strategy` ABC 不依赖 vnpy、tqsdk 或任何回测/实盘框架
2. **标准化通信协议**：`Bar`、`Signal`、`Fill`、`StrategyPosition` 四种数据类型贯穿 Strategy ↔ Bridge 的通信
3. **版本可追溯**：`CORE_VERSION` + 策略自身版本号，确保回测结果可复现

---

## 二、模块职责

```
strategies/core/
├── __init__.py    # 导出入口，统一管理对外暴露的符号
├── base.py        # Strategy ABC 抽象基类
├── types.py       # Bar, Signal, Fill, StrategyPosition 数据类型
└── doc.md         # 本文档
```

### 2.1 `base.py` — Strategy ABC 基类

**最小抽象接口**，共 6 个抽象成员：

| 成员 | 类型 | 职责 |
|------|------|------|
| `on_bar(bar) -> Signal` | 抽象方法 | 接收 K 线，生成交易信号 |
| `on_fill(fill) -> None` | 抽象方法 | 接收成交回执，更新内部状态 |
| `position -> StrategyPosition` | 抽象属性 | 返回当前持仓快照 |
| `config -> Any` | 抽象属性 | 返回当前策略配置 |
| `config = value` | 抽象 setter | 动态更新策略配置 |
| `reset() -> None` | 抽象方法 | 重置策略到初始状态 |

**核心原则**：

- Strategy 只做两件事：**信号生成**（`on_bar`）和**状态管理**（`on_fill`、`position`、`reset`）
- `Signal.volume` 由策略预计算，Bridge 只做执行，不做数量决策
- 绩效统计由回测引擎统一计算，Strategy 不自行统计盈亏
- 不依赖任何框架类型，输入输出全是自定义 dataclass

### 2.2 `types.py` — 标准化通信协议

四个 dataclass 构成了策略系统内部的数据流协议：

```
外部行情 → [Bridge] → Bar → [Strategy] → Signal → [Bridge] → 下单
                        ↑                          ↓
                    Fill ← [Bridge] ← 成交回报  StrategyPosition (状态查询)
```

| 类型 | 方向 | 语义 |
|------|------|------|
| `Bar` | 输入 | K 线行情数据 |
| `Signal` | 输出 | 交易决策（动作 + 理由 + 数量） |
| `Fill` | 回执 | 成交确认（价格 + 数量 + 时间） |
| `StrategyPosition` | 快照 | 当前持仓状态 |

### 2.3 `__init__.py` — 导出入口

当前导出 6 个符号：

- `CORE_VERSION` — 基础设施版本号
- `Strategy` — 策略抽象基类
- `Bar`、`Signal`、`Fill`、`StrategyPosition` — 四种数据类型

---

## 三、架构分层

```
┌─────────────────────────────────────────┐
│             策略实例层                     │
│  ma_strategy.py, 未来的 macd_strategy.py │
│  继承 Strategy ABC，实现 on_bar/on_fill  │
│  定义自身 VERSION、参数 Dataclass         │
├─────────────────────────────────────────┤
│             核心抽象层 (core)             │
│  Strategy ABC + 标准类型定义              │
│  框架无关，纯 Python 业务逻辑             │
├─────────────────────────────────────────┤
│             Bridge 适配层                │
│  vnpy_bridge.py / tqsdk_bridge.py       │
│  负责 框架类型 ↔ 标准类型 的双向转换      │
│  处理下单执行、持仓同步等基础设施操作       │
├─────────────────────────────────────────┤
│         回测 / 实盘运行环境               │
│  backtest 模块 / 实盘引擎                 │
├─────────────────────────────────────────┤
│           通用基础层 (common)            │
│  类型别名 · 常量字典 · 纯函数公式库       │
│  零 I/O · 零框架依赖                    │
└─────────────────────────────────────────┘
```

关键约束：**依赖只能从上到下**。策略实例层依赖 core，core 依赖 common（纯类型定义，无框架依赖）。Bridge 依赖 core 的类型，但不依赖策略实例（通过 `Strategy` 接口交互）。`common` 处于最底层，零依赖。

---

## 四、版本管理策略

### 版本号构成

```
CORE_VERSION = "v1.0.0"          # 基础设施版本
Strategy.VERSION = "v1.0.0-ma1"  # 策略版本 = CORE_VERSION + 策略标识 + 迭代号
```

### 变更规则

- `core/` 下任何文件（base.py / types.py / `__init__.py`）改动 → 递增 `CORE_VERSION`
- 策略逻辑迭代 → 递增策略自身的迭代号（如 `ma1` → `ma2`）
- Bridge 适配框架升级（如 tqsdk 版本变更）→ 不涉及 `CORE_VERSION` 变更，由 Bridge 自身版本管理

这样做的目的是：**通过版本号即可判断某次回测结果对应哪一套策略逻辑和基础设施**。

---

## 五、设计讨论与潜在改进

### 5.1 导入路径统一

**已实施**：所有文件已统一为 `from strategies import ...` 顶层导入。

| 文件 | 原写法 | 改后 |
|------|--------|------|
| `ma_strategy.py` | `from strategies.core import CORE_VERSION` + `from .core.base import Strategy` + `from .core.types import ...` | `from strategies import CORE_VERSION, Strategy, Bar, Signal, Fill, StrategyPosition` |
| `bridges/tqsdk_bridge.py` | `from ..core.base import Strategy` + `from ..core.types import ...` | `from strategies import Strategy, Bar, Signal, Fill` |
| `bridges/vnpy_bridge.py` | `from ..core.types import Bar, Signal, Fill` | `from strategies import Bar, Signal, Fill` |
| `utils/loader.py` | `from strategies.core.base import Strategy` | `from strategies import Strategy` |
| `utils/config.py` | `from strategies.core.base import Strategy` | `from strategies import Strategy` |
| `backtest/vnpy_backtest_engine.py` | `from strategies.core.base import Strategy` | `from strategies import Strategy` |
| `cli/commands/test.py` | `from strategies.core import Bar, Fill` | `from strategies import Bar, Fill` |
| `tests/test_strategies.py` | `from strategies.core.types import Bar, Signal, Fill` | `from strategies import Bar, Signal, Fill` |

**好处**：
- 不依赖调用方与 `core` 的相对位置
- 如果 `core/` 内部重组（如把 types 拆成多个文件），导入语句不需要改动
- `__all__` 已控制导出符号，不会意外引入内部符号

### 5.2 字符串类型收紧 — 已实施

**问题**：`Signal.action`、`Fill.action`、`StrategyPosition.direction` 虽然只有约定取值集合，但类型定义为 `str`，拼写错误不会被静态检查发现。

**已实施方案**：

在 `common/types.py` 定义全项目共享的 Literal 类型别名，`core/types.py` 导入使用：

**`common/types.py`**（零依赖的底层定义）：

```python
from typing import Literal

TradeAction = Literal['buy', 'sell', '']
PositionDirection = Literal['long', '']
```

**`core/types.py`**（导入并使用）：

```python
from common.types import TradeAction, PositionDirection

@dataclass
class Signal:
    action: TradeAction = ''
    reason: str = ""
    volume: int = 0

@dataclass
class StrategyPosition:
    direction: PositionDirection = ''
    ...

@dataclass
class Fill:
    action: TradeAction = ''
    ...
```

**这样做的理由**：

1. **core 层不再零依赖** —— 但 `common` 是纯 Python 基础层（零 I/O、零框架依赖），不影响 core 框架无关的本质
2. **全项目单一事实来源** —— `TradeAction` 在 `common`，所有模块（core、strategies、bridges）共享同一组类型别名
3. **与运行时常量同源** —— `common/types.py` 的类型别名和 `common/constants.py` 的运行时常量（`TRADE_ACTION_BUY` 等）在同一个包下，修改时同步

下游使用示例：

```python
# 策略层 / Bridge 层赋值时，用运行时常量 + 类型自动检查
from common.constants import TRADE_ACTION_BUY, SIGNAL_GOLDEN_CROSS
from common.types import TradeAction

signal = Signal(action=TRADE_ACTION_BUY, reason=SIGNAL_GOLDEN_CROSS)
# type checker 知道 signal.action 是 Literal['buy', 'sell', '']
# 如果拼成 TRADE_ACTION_BYE 编译时就发现了
```

### 5.3 `Bar.datetime` 类型选择 — 已实施

**已实施方案**：

```python
from datetime import datetime

@dataclass
class Bar:
    datetime: datetime = datetime.min
    ...
```

**改动范围**：

| 文件 | 变化 |
|------|------|
| `core/types.py` | `datetime: str` → `datetime: datetime` |
| `bridges/vnpy_bridge.py` | 去掉 `str()` 包装，直接传 vnpy 原生 `datetime` |
| `bridges/tqsdk_bridge.py` | 去掉 `str()` 包装，直接传 `datetime.now()` |
| `cli/commands/test.py` | 传 `datetime(2026, 1, 1)` 而非字面量字符串 |
| `tests/test_strategies.py` | `_make_bar` 参数类型同步更新 |

**好处**：策略层（`on_bar` 内）现在可以直接 `bar.datetime.hour`、`bar.datetime.weekday()` 做时间维度逻辑，不需要自行 `strptime` 解析。

**边界**：`Fill.timestamp` 保持 `str` 不变，因为成交时间戳在 Bridge 中已有格式化逻辑（`strftime`），且和 `Bar.datetime` 语义不同。从 `Bar.datetime` 转手到 `Fill.timestamp` 时通过 `str()` 显式转换。

### 5.4 `config` 泛型化 — 已实施

**现状**：

```python
from typing import Generic, TypeVar

T = TypeVar('T')

class Strategy(ABC, Generic[T]):
    @property
    @abstractmethod
    def config(self) -> T: ...
    @config.setter
    def config(self, value: T) -> None: ...

# 子类使用时：
class MaStrategyCore(Strategy[MACrossParams]):
    @property
    def config(self) -> MACrossParams:
        return self._config
```

**好处**：回测引擎在调用 `strategy.config` 时，静态类型检查能自动推断出具体参数类型。

### 5.5 是否在 core 层引入指标缓存

**现状**：每个策略自己维护内部状态

```python
# ma_strategy.py
class MaStrategyCore(Strategy[MACrossParams]):
    def __init__(self):
        self._close_history: list[float] = []
        self._prev_sma_short: float = 0.0
        self._prev_sma_long: float = 0.0
```

**考虑**：如果未来有多个策略共享 K 线数据或指标计算（比如多个策略都算 SMA、EMA），当前架构没有复用机制。

**我的看法**：在目前的规模下，这属于过设计。指标缓存更适合做成独立的 indicator 模块，放在 `strategies/` 或 `common/` 下，按需引入：

```
strategies/
├── indicators/
│   ├── sma.py
│   ├── ema.py
│   └── ...
```

core 层保持抽象和最小接口，不涉及具体指标实现。等到有 3 个以上策略共享指标计算时再引入 indicator 模块不迟。

---

## 六、扩展建议

### 如果需要新增类型

比如需要 `Trade` 类型表示已成交订单的完整记录（包含手续费、滑点等），定位为回测引擎的输出，而非 Strategy ↔ Bridge 的通信协议。应放在回测模块而非 core。

**判断准则**：如果是 Strategy 和 Bridge 之间传递的数据 → 放 core；如果是回测或实盘运行产生的衍生数据 → 放对应模块。

### 如果需要新增抽象方法

比如 `on_tick(tick) -> Signal` （支持 tick 级策略），参考 `on_bar` 的签名：

```python
@abstractmethod
def on_tick(self, tick: Tick) -> Signal: ...
```

其中 `Tick` 需要作为新类型放在 types.py 中。是否要加这个接口取决于实际需求——目前 `on_bar` 已覆盖主要使用场景。