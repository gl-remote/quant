"""
通用类型别名 — 全项目共享的类型定义

【文件职责】
1. 通用类型别名：Literal 类型、类型别名等，供全项目共享
2. 数据容器：跨层传递的 dataclass（如 BacktestResult、IndicatorFuncInfo）
3. Protocol：接口定义（如 IndicatorFunction）

【不包含的内容】
- Pandera Schema 定义（请使用 common/schemas.py）
- DataFrame 类型别名（请使用 common/schemas.py）

【原则】
- 遵循 common/ 零依赖原则：纯类型定义，不 import 任何业务模块
- 所有类型别名仅供静态类型检查使用，零运行时开销
- BacktestResult 等 dataclass 例外 — 它们是跨层传递的数据容器，有运行时行为

【使用方式】
    from common.types import TradeAction, PositionDirection, IndicatorCalcMode

    signal = Signal(action='buy')  # type checker validates 'buy' | 'sell' | ''

【单一事实来源】
- 全项目（core、strategies、bridges）共享同一组 Literal 类型
- 与 common/constants.py 中同名运行时常量同源，修改时同步更新
"""

from dataclasses import dataclass, field
from typing import Literal, Callable, Any, Protocol, Optional

from .constants import STATUS_FAILED

TradeAction = Literal['buy', 'sell', '']
"""交易动作: 'buy' (买入) | 'sell' (卖出) | '' (无操作)"""

PositionDirection = Literal['long', 'short', '']
"""持仓方向: 'long' (多头) | '' (空仓)"""


# 技术指标计算相关类型
IndicatorCalcMode = Literal['batch', 'incremental']
"""指标计算模式: 'batch'（批量计算） | 'incremental'（增量计算）"""


@dataclass
class IndicatorFuncInfo:
    """指标函数信息
    用于注册和管理技术指标计算函数。
    """
    func: Callable[..., Any]  # 指标计算函数
    calc_mode: IndicatorCalcMode  # 计算模式
    name: str  # 指标名称
    description: Optional[str] = None  # 指标描述


class IndicatorFunction(Protocol):
    """指标计算函数协议
    定义技术指标计算函数的标准接口。
    """
    def __call__(self, data: Any, **params: Any) -> Any: ...


@dataclass
class BacktestResult:
    """回测结果 — 统一传递结构，在各层之间传递

    消除 dict[str, object] 在各层间手动 unpack，提供精确类型。

    字段来源说明:
      - vnpy 直接提供: vnpy calculate_statistics() 输出
      - 自行计算: 从逐笔交易记录(pnl)聚合统计（基于净盈亏）
      - 配置入参: 回测运行时传入的参数
    """
    # ── 标识 ──────────────────────────────────────────
    symbol: str                                              # 品种代码
    strategy: str                                            # 策略名称
    strategy_version: str | None = None                      # 策略版本号
    backtest_id: int | None = None                           # 回测记录ID（占位后可更新）
    # ── 状态 ──────────────────────────────────────────
    status: str = STATUS_FAILED                              # running / success / failed
    error_message: str | None = None                         # 错误信息
    success: bool = False                                    # 是否成功
    # ── 日期范围 ──────────────────────────────────────
    start_date: str | None = None                            # 回测起始日期
    end_date: str | None = None                              # 回测结束日期
    total_days: int | None = None                            # 总交易日数
    # ── 核心绩效指标（vnpy calculate_statistics 输出）───
    total_trades: int = 0                                    # 总成交笔数 [vnpy]
    end_balance: float = 0.0                                 # 期末权益余额 [vnpy]
    total_return: float = 0.0                                # 总收益率 (%) [vnpy]，如 15.5 表示 15.5%
    annual_return: float | None = None                       # 年化收益率 (%) [vnpy]
    sharpe_ratio: float | None = None                        # 夏普比率 [vnpy]
    max_drawdown: float | None = None                        # 最大回撤金额（绝对值，如 50000.0 表示回撤 5 万元）[vnpy]
    max_ddpercent: float | None = None                       # 最大回撤百分比 (%) [vnpy]
    max_drawdown_duration: int | None = None                 # 最大回撤持续天数 [vnpy]
    daily_std: float | None = None                           # 日收益率标准差 (%) [vnpy]
    return_drawdown_ratio: float | None = None               # 收益回撤比 [vnpy]
    # ── 盈亏汇总（vnpy 直接输出）───────────────────────
    total_net_pnl: float | None = None                       # 总净盈亏金额（扣完费用）[vnpy]
    daily_net_pnl: float | None = None                       # 日均净盈亏金额 [vnpy]
    total_commission: float | None = None                    # 总手续费金额 [vnpy]
    daily_commission: float | None = None                    # 日均手续费 [vnpy]
    total_slippage: float | None = None                      # 总滑点成本金额 [vnpy]
    daily_slippage: float | None = None                      # 日均滑点成本 [vnpy]
    total_turnover: float | None = None                      # 总成交金额 [vnpy]
    daily_turnover: float | None = None                      # 日均成交金额 [vnpy]
    # ── 交易日统计（vnpy 直接输出）──────────────────────
    profit_days: int | None = None                           # 盈利交易日数 [vnpy]
    loss_days: int | None = None                             # 亏损交易日数 [vnpy]
    daily_trade_count: float | None = None                   # 日均成交笔数 [vnpy]
    daily_return_pct: float | None = None                    # 日均收益率 (%) [vnpy]
    # ── 交易级别统计（自行从逐笔 pnl 聚合计算）──────────
    win_trades: int = 0                                      # 盈利交易笔数 (pnl > 0)
    loss_trades: int = 0                                     # 亏损交易笔数 (pnl < 0 的平仓次数，pnl=0 不计入)
    win_rate: float | None = None                            # 胜率
    max_consecutive_win: int | None = None                    # 最大连续盈利次数
    max_consecutive_loss: int | None = None                   # 最大连续亏损次数
    avg_win: float | None = None                             # 平均盈利金额
    avg_loss: float | None = None                            # 平均亏损金额
    win_loss_ratio: float | None = None                      # 盈亏比
    # ── 进阶指标（vnpy 输出）───────────────────────────
    ewm_sharpe: float | None = None                          # EWM 指数加权夏普比率 [vnpy]
    rgr_ratio: float | None = None                           # RGR 比率 [vnpy]
    # ── 引擎配置（入参）────────────────────────────────
    initial_capital: float = 0.0                             # 初始资金
    commission_rate: float = 0.0                              # 手续费率（小数比例，如 0.0003 表示万三）
    slippage: float = 0.0                                    # 单边滑点
    price_tick: float = 0.0                                  # 最小变动价位
    contract_size: int = 0                                   # 合约乘数
    kline_interval: str = ""                                  # K线周期
    # ── 原始数据 ──────────────────────────────────────
    engine_config: dict[str, object] = field(default_factory=dict)  # JSON 元数据
    data_src: str | None = None                              # 数据源路径
    strategy_params: dict[str, float] | None = None          # 策略参数
    fills: list[dict[str, object]] = field(default_factory=list)     # 逐笔交易记录
    daily_results: list[dict] = field(default_factory=list)         # 每日资金曲线
    # ── 链路信息 ──────────────────────────────────────
    git_hash: str | None = None                              # Git 提交哈希