# -*- coding: utf-8 -*-
"""
全局业务常量字典

统一项目内全部硬编码字符、数值、标识、配置字段的命名口径，消除魔术数字和
魔术字符串在代码库中的散落。

本模块遵循 common/ 零依赖原则：纯常量定义，不 import 任何业务模块。

使用方式:
    from common.constants import (
        TRADE_ACTION_BUY, TRADE_ACTION_SELL,
        DEFAULT_INITIAL_CAPITAL, STATUS_SUCCESS,
    )

分类:
    - Trade      交易方向 / 开平仓 / 信号原因
    - Status     状态码 (回测 / 日志 / DB)
    - Command    CLI 子命令名
    - Strategy   策略配置默认值
    - Backtest   回测引擎默认参数
    - Data       数据切分 / 路径 / 周期
    - Finance    金融行业通用常数
    - StrategyName  策略标识名
"""

# ============================================================================
# 交易方向与动作 (Trade Direction & Action)
# ============================================================================

TRADE_ACTION_BUY = 'buy'           # 买入动作
TRADE_ACTION_SELL = 'sell'          # 卖出动作
TRADE_DIRECTION_LONG = 'long'      # 多头持仓方向
TRADE_DIRECTION_SHORT = 'short'     # 空头持仓方向
TRADE_OFFSET_OPEN = 'open'         # 开仓
TRADE_OFFSET_CLOSE = 'close'        # 平仓

# vnpy Direction/Offset 枚举值 → 标准字段映射
# vnpy 中文 locale 下 .value 返回中文，需要映射为 Schema 接受的英文
DIRECTION_MAP = {
    '多': 'long', '空': 'short',
    'LONG': 'long', 'SHORT': 'short',
}
OFFSET_MAP = {
    '开': 'open', '平': 'close', '平今': 'closetoday',
    'OPEN': 'open', 'CLOSE': 'close', 'CLOSETODAY': 'closetoday',
}


# ============================================================================
# 信号触发原因 (Signal Reasons)
# ============================================================================

SIGNAL_STOP_LOSS = 'stop_loss'      # 止损触发
SIGNAL_TAKE_PROFIT = 'take_profit'    # 止盈触发
SIGNAL_DEATH_CROSS = 'death_cross'    # 死叉信号
SIGNAL_GOLDEN_CROSS = 'golden_cross'   # 金叉信号


# ============================================================================
# 状态码 (Status Codes)
# ============================================================================

# 回测 / DB 操作状态
STATUS_SUCCESS = 'success'   # 成功
STATUS_FAILED = 'failed'    # 失败

# 日志级别状态
LOG_STATUS_INFO = 'INFO'     # 信息
LOG_STATUS_SUCCESS = 'SUCCESS'  # 操作成功
LOG_STATUS_ERROR = 'ERROR'    # 错误


# ============================================================================
# CLI 子命令名称 (Command Names)
# ============================================================================

CMD_EXPORT = 'export'       # 数据导出
CMD_BACKTEST = 'backtest'     # vnpy 批量回测
CMD_TEST = 'test'         # 策略逻辑测试
CMD_LIVE = 'live'         # 实盘/模拟交易
CMD_REPORT = 'report'       # 回测报告查询


# ============================================================================
# 回测运行模式 (Backtest Mode)
# ============================================================================

MODE_SINGLE = 'single'   # 单品种模式
MODE_BATCH = 'batch'    # 批量模式 (多品种)
MODE_MULTI = 'multi'    # 多品种标识 (日志/DB symbol 占位)


# ============================================================================
# 策略标识名称 (Strategy Identifiers)
# ============================================================================

STRATEGY_MA = 'ma'       # 双均线交叉策略


# ============================================================================
# 策略配置默认值 (Strategy Defaults)
# ============================================================================

DEFAULT_SMA_SHORT = 10       # 短期均线周期 (K线)
DEFAULT_SMA_LONG = 40      # 长期均线周期 (K线)
DEFAULT_STOP_LOSS_RATIO = 0.03   # 止损比例 (3%)
DEFAULT_TAKE_PROFIT_RATIO = 0.05  # 止盈比例 (5%)
DEFAULT_POSITION_RATIO = 0.3    # 仓位比例 (30%)
DEFAULT_KLINE_PERIOD = 5      # K线周期 (分钟)


# ============================================================================
# 回测引擎默认参数 (Backtest Engine Defaults)
# ============================================================================

DEFAULT_INITIAL_CAPITAL = 100000.0   # 初始资金
DEFAULT_COMMISSION_RATE = 0.0003     # 手续费率 (0.03%)
DEFAULT_SLIPPAGE = 1.0        # 滑点 (最小变动价位)
DEFAULT_PRICE_TICK = 1.0        # 最小价格变动单位
DEFAULT_CONTRACT_SIZE = 10         # 合约乘数


# ============================================================================
# 数据切分配置默认值 (Data Split Defaults)
# ============================================================================

DEFAULT_TRAIN_RATIO = 0.6     # 训练集占比 (60%)
DEFAULT_VAL_RATIO = 0.2     # 验证集占比 (20%)
DEFAULT_TEST_RATIO = 0.2     # 测试集占比 (20%)
DEFAULT_RANDOM_SEED = 42      # 随机种子


# ============================================================================
# 数据存储默认路径 (Data Storage Defaults)
# ============================================================================

DEFAULT_DATA_BASE_DIR = '.quant_shared_data'              # 共享数据根目录
DEFAULT_EXPORT_DIR = '.quant_shared_data/csv'          # CSV 导出目录
DEFAULT_DB_PATH = '.quant_shared_data/quant_shared.db'  # SQLite 数据库路径




# ============================================================================
# 日志格式 (Logging Format)
# ============================================================================

DEFAULT_LOG_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}"
)


# ============================================================================
# K线周期 (KLine Interval)
# ============================================================================

KLINE_INTERVAL_1MIN = '1m'   # 1 分钟 K线

# 通用 K 线周期列表（用于文件名解析）
COMMON_KLINE_INTERVALS = [
    '1m', '5m', '15m', '30m', '1h', '2h', '4h',
    '6h', '8h', '12h', '1d', '3d', '1w', '1M', '3M', '6M', '1Y',
]


# ============================================================================
# 操作日志自动清理 (Operation Log Pruning)
# ============================================================================

MAX_OPERATION_LOG_ROWS = 50_000   # 最大日志行数，超出自动清理
PRUNE_CHECK_INTERVAL = 100      # 每 N 次 insert 检查一次是否需要清理
