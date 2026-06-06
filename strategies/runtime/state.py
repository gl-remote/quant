"""运行时状态容器模块

定义 State 数据结构，用于在 Bridge 和 Strategy 之间传递所有运行时数据。

重构背景:
- 旧架构：Strategy 自己持有 config、position、fills 等所有状态
- 新架构：State 统一持有所有运行时数据，Strategy 成为纯决策逻辑
- 优势：职责清晰、状态管理集中、Bridge 可以同步 vnpy 引擎状态

职责划分 (核心设计原则):
  - State:      保存策略配置、环境配置、持仓、交易记录（所有运行时数据）
  - Strategy:   纯决策逻辑，不持有任何状态，通过 State 获取所有数据
  - BarContext: 保存行情数据、多周期数据、指标、事件（动态行情数据）
  - Bridge:     负责从 vnpy 获取交易状态，更新 State
"""

from dataclasses import dataclass, field
from typing import Any, TypeVar

from .types import Fill, StrategyPosition

# 泛型类型变量，用于表示策略配置的具体类型
T = TypeVar("T")


@dataclass
class State[T]:
    """运行时配置和状态容器

    【设计理念】
    State 是策略运行时的唯一真实数据来源，所有运行时数据都集中在这里。
    这样设计的好处：
    1. 状态管理集中化，避免分散在多个对象中导致不一致
    2. Strategy 成为纯函数，易于测试和维护
    3. Bridge 可以方便地同步 vnpy 引擎的交易状态

    【数据来源】
    - symbol / period: Engine 从回测配置中传入
    - strategy_config: 从 CLI / 优化器传入的 strategy_params 转换而来
    - capital / contract_size: Engine 的配置
    - position / fills: Bridge 在 on_trade 回调中从 vnpy 同步
    - extra: 扩展字段，用于临时存储其他数据

    【使用场景】
    - Bridge.__init__: 构造初始 State
    - Bridge.on_bar: 传递 state 给 strategy.on_bar()
    - Bridge.on_trade: 更新 state.position 和 state.fills
    - Strategy.on_bar: 从 state 读取配置、持仓、交易记录

    【注意事项】
    - State 是可变对象，但在单线程环境（回测/实盘）下无需并发保护
    - position 和 fills 由 Bridge 负责更新，Strategy 只读取不修改
    - strategy_config 在运行期间不应修改（是策略参数）
    """

    # 基本交易标的信息
    symbol: str
    """交易标的代码，如 'rb2505'"""

    period: str
    """主周期，如 '1m'、'5m'、'1h'"""

    # 策略配置（泛型，支持不同策略的配置类型）
    strategy_config: T
    """策略配置对象，类型由 Strategy 的泛型参数决定

    例如：
    - MaStrategyCore 使用 MACrossParams
    - 其他策略可以使用自己的配置类
    """

    # 环境配置
    capital: float = 0.0
    """初始资金，用于计算仓位大小"""

    contract_size: int = 1
    """合约乘数，用于计算仓位大小"""

    margin: float = 1.0
    """保证金比例 (如 0.07 = 7%)，用于计算仓位大小"""

    # 运行时状态（由 Bridge 更新）
    position: StrategyPosition = field(default_factory=StrategyPosition)
    """当前持仓状态

    【数据来源】
    Bridge 在 on_trade 回调中用 vnpy 的成交数据更新此字段。

    【注意事项】
    - Strategy 只读取此字段，不直接修改
    - 此字段与 vnpy 的 self.pos 保持同步
    """

    fills: list[Fill] = field(default_factory=list)
    """历史成交记录列表

    【数据来源】
    Bridge 在每次 on_trade 回调后，将新的成交追加到此列表。

    【用途】
    - 策略可以读取用于分析（虽然 MaStrategyCore 目前不用）
    - 回测结果统计
    """

    # 运行标识（由 Engine 注入，用于日志追踪）
    run_id: int = 0
    """运行 ID，用于关联回测运行记录"""

    backtest_id: int = 0
    """回测记录 ID，由 Engine 创建占位记录后注入"""

    extra: dict[str, Any] = field(default_factory=dict)
    """扩展字段，用于临时存储其他数据

    这是一个灵活的扩展点，可以存储任何临时需要的数据。
    """
