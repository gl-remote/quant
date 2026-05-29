# -*- coding: utf-8 -*-
"""
策略模块 — 公共 API 入口

架构: Strategy (大脑) + Bridge (四肢)
  - core/            Strategy ABC + Bar/Signal/Fill 标准化类型 + CORE_VERSION
  - utils/           策略加载、配置管理等工具函数
  - ma_strategy.py   均线交叉策略 (继承 Strategy，自主管理全部状态)
  - bridges/         框架桥接器 (vnpy / tqsdk，纯协议转换)

【推荐导入方式】
  from strategies import MaStrategyCore          # 策略核心
  from strategies import VnpyStrategyBridge       # vn.py 桥接器
  from strategies import TqsdkStrategyBridge      # 天勤桥接器
  from strategies import Strategy, Bar, Signal    # 基类 + 数据类型
  from strategies import CORE_VERSION             # 版本号常量
  from strategies.utils import load_strategy      # 工具函数

【不再推荐直接从 core 子模块导入】
  包内所有模块统一从 strategies 顶层导入，
  避免 from strategies.core / from .core.base 等内部路径依赖。
  好处：
  - 不依赖调用方与 core 的相对位置
  - 如果 core/ 内部重组，导入语句不需要改动
  - __all__ 控制导出符号，不会意外引入内部符号


============================================================
策略开发完整流程
============================================================
1. 策略设计
   - 明确交易逻辑、信号触发条件、风控规则
   - 定义参数空间（使用 dataclass 封装）
   - 确定回测目标和约束条件

2. 代码实现
   - 在 strategies/ 目录下创建 xxx_strategy.py
   - 继承 Strategy ABC，实现 on_bar / on_fill / reset / position / config
   - 使用 standardized types (Bar, Signal, Fill, StrategyPosition)
   - 版本号格式: f"{CORE_VERSION}-<策略标识><迭代号>"

3. 参数配置
   - 在 config.toml 中添加策略配置项
   - 确保所有参数都有合理默认值
   - 通过 apply_strategy_config 自动加载配置

4. 回测与验证
   - 使用回测引擎运行单品种回测
   - 检查资金曲线、交易记录、绩效指标
   - 验证退化解检测是否生效（零交易、参数不合理）

5. 参数优化
   - 配置 Optuna / 贝叶斯搜索参数空间
   - 设定目标函数（默认：最大化 sharpe_ratio）
   - 设定惩罚项（max_drawdown > 30% → -inf）
   - 执行优化，分析参数敏感性

6. 多品种回测
   - 运行多品种批量回测
   - 生成报告，检查品种间一致性
   - 验证每个品种的最优回测与数据对应

7. 上线准备（可选）
   - 接入实盘 Bridge
   - 配置实盘参数
   - 小资金试跑


============================================================
新策略开发指南 - 快速起步
============================================================
创建新策略步骤：

1. 复制 ma_strategy.py 为 <策略名>_strategy.py
2. 修改类名（如 MaStrategyCore → XXXStrategyCore）
3. 修改 name 和 VERSION
4. 定义自己的 Params dataclass
5. 在 __init__ 中初始化所需状态
6. 在 on_bar 中实现交易逻辑
   - 优先级：止损 > 止盈 > 交易信号
   - Signal.volume 由策略预计算，Bridge 不做数量决策
7. 在 on_fill 中更新持仓和交易记录
8. 在 reset 中清理所有状态
9. 更新 __init__.py 中的 STRATEGY_XXX 常量（如需）

核心原则：
- Strategy 不依赖任何特定回测/实盘框架
- 所有外部数据通过 Bar 进入，所有决策通过 Signal 输出
- 绩效统计由回测引擎负责，Strategy 只记录 fills


============================================================
最佳实践
============================================================
参数约束：
  - 均线类：sma_short < sma_long（禁止退化解）
  - 止损：必须 > 0，推荐 ATR 而非固定比例
  - 仓位：position_ratio ∈ (0, 1]

信号优先级（从高到低）：
  1. 止损
  2. 止盈
  3. 交易信号（金叉/死叉等）

目标函数配置：
  - 主目标：最大化 sharpe_ratio
  - 惩罚项：max_drawdown > 30% → 目标值 = -inf
  - 退化解：total_trades == 0 → 目标值 = -inf

性能优化：
  - 技术指标计算结果缓存（如 _prev_sma_short）
  - 避免在 on_bar 中重复计算
  - 使用 KlineCache 复用 CSV → JSON 转换结果


============================================================
常见陷阱
============================================================
1. Future Data
   - 不要使用当前 bar 的未来数据（如 bar.close 之后的数据）
   - 技术指标计算基于历史数据，不含当前 bar

2. 过度拟合
   - 不要针对特定历史行情调参
   - 样本外测试与样本内性能对比
   - 参数不要过多，避免维度灾难

3. 退化解未检测
   - 参数空间要加约束（sma_short < sma_long）
   - 优化器要配置退化解惩罚（total_trades == 0 → -inf）

4. 数据不对应
   - 品种汇总必须关联同一最优回测记录（get_run_summary 中锁定 backtest_id）
   - K线、资金曲线、交易标记必须基于同一回测

5. 日期格式问题
   - lightweight-charts v5 要求：日线用 "YYYY-MM-DD"，分钟线用 UTCTimestamp（秒）
   - 参考 _build_kline_dict 中的格式处理


============================================================
现有设计权衡
============================================================
设计 1：Strategy 预计算 Signal.volume
  - 优点：策略可以自由实现复杂的仓位管理（凯利公式、动态仓位等）
  - 缺点：Bridge 需要信任策略的计算，不做二次调整
  - 权衡：策略是决策主体，Bridge 只做执行

设计 2：绩效统计由回测引擎负责
  - 优点：避免策略自行统计盈亏导致的不一致
  - 缺点：策略无法实时查看绩效（只能看 position 和 fills）
  - 权衡：回测引擎统一计算，结果更可靠

设计 3：数据层与业务层分离
  - 优点：report/builder.py 不直接连数据库，通过 DataManager 获取
  - 缺点：多一层抽象
  - 权衡：可维护性 > 微小性能损失

设计 4：增量构建 + 数据指纹
  - 优点：重复构建时跳过未变更的数据，显著提升速度
  - 缺点：需要额外维护 BuildCache
  - 权衡：构建性能优先（尤其多品种回测）

设计 5：标准化类型（Bar/Signal/Fill）
  - 优点：Strategy 框架无关，易于切换回测/实盘引擎
  - 缺点：Bridge 需要做数据转换
  - 权衡：可移植性优先


============================================================
未来改进方向
============================================================
1. 多品种策略支持
   - 当前 Strategy 设计只支持单品种
   - 可扩展为同时处理多个 Bar，生成多个 Signal

2. 多周期策略
   - 当前只接收单一周期 Bar
   - 可扩展为同时接收多个周期数据

3. 实盘 Bridge 完善
   - 当前主要支持 vnpy 回测
   - 可扩展 tqsdk、ctp 等实盘 Bridge

4. 策略单元测试
   - 为 Strategy 添加单元测试框架
   - Mock Bar，验证 Signal 生成逻辑

5. 更多技术指标库
   - 封装常用指标（ATR、RSI、MACD、布林带等）
   - 提供缓存机制避免重复计算

6. 风险指标增强
   - 计算更多风险指标（Calmar、Sortino、VaR 等）
   - 支持自定义目标函数

7. 策略组合
   - 支持多个策略并行运行
   - 组合资金曲线和绩效分析
"""


# 策略核心与类型（来自 core）
from .core import Strategy, Bar, Signal, Fill, StrategyPosition, CORE_VERSION

# 具体策略实现
from .ma_strategy import MaStrategyCore, MACrossParams

# 工具函数（来自 utils）
from .utils import (
    load_strategy,
    get_strategy_class_name,
    apply_strategy_config,
    serialize_strategy_params,
)

# 桥接器（可选导入，可能有依赖缺失）
try:
    from .bridges import VnpyStrategyBridge
except ImportError:
    VnpyStrategyBridge = None

try:
    from .bridges import TqsdkStrategyBridge
except ImportError:
    TqsdkStrategyBridge = None

__all__ = [
    # 版本号
    'CORE_VERSION',
    # 核心类型
    'Strategy', 'Bar', 'Signal', 'Fill', 'StrategyPosition',
    # 策略实现
    'MaStrategyCore', 'MACrossParams',
    # 工具函数
    'load_strategy', 'get_strategy_class_name',
    'apply_strategy_config', 'serialize_strategy_params',
    # 桥接器
    'VnpyStrategyBridge', 'TqsdkStrategyBridge',
]
