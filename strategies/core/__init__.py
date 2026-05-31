"""策略核心模块
提供策略基类、标准化数据类型定义、版本管理。

设计原则:
  - Strategy ABC: 框架无关的策略抽象
  - 标准化类型: Bar, Signal, Fill, StrategyPosition
  - 版本追踪: CORE_VERSION + 策略自身版本，确保回测可追溯

子模块:
  - base: Strategy ABC 基类
  - types: Bar, Signal, Fill, StrategyPosition 标准化数据类型
  - runtime（同级）：运行时数据管理（DataFeed, PeriodData, Event 等）

【推荐导入方式】
  from strategies import Strategy, Bar, Signal  # 从顶层统一入口导入
  from strategies import CORE_VERSION             # 版本号常量
  from strategies import DataFeed, PeriodData     # 运行时数据管理
  包内模块推荐从 strategies 顶层导入，避免依赖内部目录结构。

【版本号规则】
  CORE_VERSION: 策略基础设施版本，core/ 下任何文件改动 → 递增此版本
  各策略引用: from strategies import CORE_VERSION
  策略版本格式: f"{CORE_VERSION}-<策略标识><迭代号>"
    例: ma_strategy.py → VERSION = f"{CORE_VERSION}-ma1"
"""

# ============================================================
# 核心版本号
# ============================================================
CORE_VERSION = "v2.0.0"

# ============================================================
# 核心基类和类型
# ============================================================
from .base import Strategy, UninitializedStrategy
from .types import Bar, Signal, Fill, StrategyPosition

__all__ = [
    # 版本号
    'CORE_VERSION',
    # 核心基类和类型
    'Strategy', 'UninitializedStrategy', 'Bar', 'Signal', 'Fill', 'StrategyPosition',
]
