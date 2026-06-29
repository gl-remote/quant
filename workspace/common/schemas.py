"""全局统一的 Pandera Schema 定义

【文件职责】
1. Pandera Schema：继承自 pandera.DataFrameModel 的数据验证规则
2. DataFrame 类型别名：使用 pandera.typing.DataFrame 定义的类型别名

【不包含的内容】
- 通用类型别名（请使用 common/types.py）
- 数据容器 dataclass（请使用 common/types.py）
- Protocol 接口定义（请使用 common/types.py）

【原则】
- 集中管理所有 DataFrame 验证规则，供整个项目复用
- 所有 Schema 都继承自 pandera.DataFrameModel，提供运行时验证能力
- DataFrame 类型别名使用 pandera.typing.DataFrame[Schema] 格式

【注意】
以下 pyright ignore 是针对 pandera 库的类型系统限制：
  - pandera 的 Series/Field 声明使用复杂的泛型叠加，静态分析器无法准确推断
  - 这是 pandera 的类型存根缺失导致的已知问题，非代码逻辑缺陷

【使用方式】
    from common.schemas import KlineDataFrame, KlineSchema

    # 类型注解
    def process_kline(data: KlineDataFrame) -> KlineDataFrame:
        ...

    # 运行时验证
    validated_data = KlineSchema.validate(raw_data)
"""

# pyright: reportAny=false
# pyright: reportUnknownMemberType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportMissingTypeStubs=false
# pyright: reportIncompatibleVariableOverride=false

import pandas as pd
import pandera.pandas as pa
from pandera.typing import DataFrame, Series


class KlineSchema(pa.DataFrameModel):
    """K线数据验证Schema

    用于验证从 CSV 加载的 K线数据，确保数据质量和一致性。
    字段说明：
        datetime: 时间戳（唯一）
        open: 开盘价
        high: 最高价
        low: 最低价
        close: 收盘价
        volume: 成交量
    """

    datetime: Series[pd.Timestamp] = pa.Field(unique=True)
    open: Series[float] = pa.Field(ge=0.0)
    high: Series[float] = pa.Field(ge=0.0)
    low: Series[float] = pa.Field(ge=0.0)
    close: Series[float] = pa.Field(ge=0.0)
    volume: Series[int] = pa.Field(ge=0)

    @pa.dataframe_check
    def check_high_greater_than_open_close(self, df: pd.DataFrame) -> bool:  # type: ignore[misc]
        """验证最高价 >= 开盘价和收盘价"""
        result: bool = bool((df["high"] >= df[["open", "close"]].max(axis=1)).all())
        return result

    @pa.dataframe_check
    def check_low_less_than_open_close(self, df: pd.DataFrame) -> bool:  # type: ignore[misc]
        """验证最低价 <= 开盘价和收盘价"""
        result: bool = bool((df["low"] <= df[["open", "close"]].min(axis=1)).all())
        return result

    @pa.dataframe_check
    def check_price_range_valid(self, df: pd.DataFrame) -> bool:  # type: ignore[misc]
        """验证价格区间有效性：low <= close <= high"""
        result: bool = bool((df["low"] <= df["close"]).all() & (df["close"] <= df["high"]).all())
        return result

    class Config:
        coerce = True


class DailyReturnSchema(pa.DataFrameModel):
    """日收益率验证Schema

    用于验证每日收益率数据。
    字段说明：
        date: 日期（唯一）
        return: 收益率
        equity: 权益值
    """

    date: Series[pd.DatetimeTZDtype] = pa.Field(unique=True)
    return_: Series[float] = pa.Field(alias="return")
    equity: Series[float] = pa.Field()

    class Config:
        coerce = True
        extra = "allow"


class TradeRecordSchema(pa.DataFrameModel):
    """回测原始成交记录验证 Schema（字段与 ORM BacktestTrade 对齐）。

    验证写入 backtest_trades 表的 raw simulated fills。

    字段说明：
        datetime: 成交时间
        symbol: 品种代码（如 DCE.m2601）
        direction: 成交方向（long/short），保持 vnpy 成交方向语义
        offset: 开平标志（open/close/closetoday）
        price: 实际模拟成交价，已包含 vnpy 撮合层应用的滑点
        quantity: 成交量（ORM 统一用 quantity，非 vnpy 原生 volume）
        reason: 策略或引擎记录的成交原因，当前仍可能是非结构化字符串
        engine_trade_id: vn.py 原始 trade id / vt_tradeid
        engine_order_id: vn.py 原始 order id / vt_orderid
        raw_direction: 引擎原始 direction 字符串，用于排查映射问题
        raw_offset: 引擎原始 offset 字符串，用于排查映射问题
        open_price / close_price: report 契约兼容字段，第一阶段等于 price
        pnl: raw fill 表不再存权威清算盈亏，权威值由 trade_clearings 生成
        commission: raw fill 表不再存权威手续费，权威值由 clearing 统一计算

    统一规则：
    - backtest_trades 只保存回测引擎产生的原始模拟成交事实。
    - FIFO 配对、gross/net PnL、手续费、滑点归因属于 clearing 业务域。
    - store 层不再从 raw fill 推导清算结果。
    - report JSON 兼容字段暂时保留，契约升级留到 analytics-reporting 阶段。
    """

    datetime: Series[pd.Timestamp] = pa.Field()
    symbol: Series[str] = pa.Field()
    direction: Series[str] = pa.Field(isin=["long", "short"])
    offset: Series[str] = pa.Field(isin=["open", "close", "closetoday"])
    price: Series[float] = pa.Field(ge=0.0)
    quantity: Series[float] = pa.Field(gt=0.0)
    reason: Series[str] = pa.Field(nullable=True)
    engine_trade_id: Series[str] = pa.Field(nullable=True)
    engine_order_id: Series[str] = pa.Field(nullable=True)
    raw_direction: Series[str] = pa.Field(nullable=True)
    raw_offset: Series[str] = pa.Field(nullable=True)
    open_price: Series[float] = pa.Field(ge=0.0)
    close_price: Series[float] = pa.Field(ge=0.0)
    pnl: Series[float] = pa.Field()
    commission: Series[float] = pa.Field(ge=0.0)

    class Config:
        coerce = True
        strict = False


class BacktestDailySchema(pa.DataFrameModel):
    """回测每日资金曲线验证Schema

    验证写入 backtest_daily 表的每日资金数据。
    字段说明：
        date: 日期
        equity: 当日权益（可为负数，期货亏损可能超过本金）
        daily_return: 当日净盈亏（金额）
        drawdown: 当日回撤（负数或零）
    2026-06-06 新增 vnpy 日度字段：
        turnover: 当日成交金额
        commission: 当日手续费
        slippage: 当日滑点成本
        trade_count: 当日成交笔数
    """

    date: Series[pd.Timestamp] = pa.Field()
    equity: Series[float] = pa.Field()
    daily_return: Series[float] = pa.Field()
    drawdown: Series[float] = pa.Field(le=0.0)
    # 2026-06-06 新增 vnpy 日度字段（nullable）
    turnover: Series[float] = pa.Field(nullable=True)
    commission: Series[float] = pa.Field(ge=0, nullable=True)
    slippage: Series[float] = pa.Field(ge=0, nullable=True)
    trade_count: Series[int] = pa.Field(ge=0, nullable=True)

    class Config:
        coerce = True
        strict = False


# ── 类型别名 ──────────────────────────────────────────────────
KlineDataFrame = DataFrame[KlineSchema]
DailyReturnDataFrame = DataFrame[DailyReturnSchema]
TradeRecordDataFrame = DataFrame[TradeRecordSchema]
BacktestDailyDataFrame = DataFrame[BacktestDailySchema]


# ── 回测数据一致性验证函数 ────────────────────────────────────
def validate_backtest_consistency(
    total_trades: int,
    win_trades: int | None,
    loss_trades: int | None,
    trade_count: int,
    backtest_id: int | None = None,
    # 2026-06-06 新增 vnpy 统计字段校验参数
    total_days: int | None = None,
    profit_days: int | None = None,
    loss_days: int | None = None,
    total_commission: float | None = None,
    trade_commission_sum: float | None = None,
) -> list[str]:
    """验证回测统计字段与交易记录之间的一致性

    调试沉淀(2026-06-04):
    - vn.py statistics 中总交易数字段为 total_trade_count
    - backtest_trades 表的实际记录数应等于 total_trades（总成交笔数）

    2026-06-06 新增/调整:
    - total_commission 应约等于逐笔交易 commission 之和（允许 1 元误差）
    - 2026-06-06 调整: win_trades + loss_trades 不再要求 == total_trades，
      因为 win/loss 只统计有实际盈亏的平仓交易，而 total_trades 包含所有成交(含开仓)。
      改为校验: win_trades + loss_trades <= total_trades，且差值合理（开仓笔数）

    Args:
        total_trades: 回测统计中的总交易数（vnpy total_trade_count，含开仓+平仓）
        win_trades: 盈利交易数（仅统计有实际盈亏的平仓）
        loss_trades: 亏损交易数（仅统计有实际盈亏的平仓）
        trade_count: backtest_trades 表中的实际交易记录数
        backtest_id: 回测记录 ID（用于日志）
        total_days: 总交易日数 [vnpy]
        profit_days: 盈利交易日数 [vnpy]
        loss_days: 亏损交易日数 [vnpy]
        total_commission: 回测统计中的总手续费 [vnpy]
        trade_commission_sum: 逐笔交易手续费之和（从 backtest_trades 聚合）

    Returns:
        错误信息列表，空列表表示验证通过
    """
    errors: list[str] = []
    prefix = f"[bt={backtest_id}] " if backtest_id else ""

    # 1. 实际交易记录数 = total_trades（总成交笔数应一致）
    if trade_count != total_trades:
        errors.append(f"{prefix}backtest_trades 实际记录数({trade_count}) ≠ total_trades({total_trades})")

    # 2. win_trades + loss_trades ≤ total_trades（盈亏笔数是总成交的子集）
    # 差值即为开仓笔数 + 持平笔数(pnl=0)，应 >= 0 且合理
    if win_trades is not None and loss_trades is not None:
        closed_cnt = win_trades + loss_trades
        if closed_cnt > total_trades:
            errors.append(
                f"{prefix}win_trades({win_trades}) + loss_trades({loss_trades}) "
                f"= {closed_cnt} > total_trades({total_trades}), "
                f"不可能：盈亏笔数不能超过总成交笔数"
            )

    # 3. 如果 total_trades > 0，则 win_trades/loss_trades 不能同时为 None
    if total_trades > 0 and win_trades is None and loss_trades is None:
        errors.append(f"{prefix}total_trades={total_trades}>0，但 win_trades 和 loss_trades 均为 None")

    # profit_days/loss_days 是有交易或有盈亏的天数，不能要求覆盖 total_days；
    # 无交易日通常既不是盈利日也不是亏损日，只校验二者不超过 total_days。
    if total_days is not None and profit_days is not None and loss_days is not None and total_days > 0:
        day_sum = profit_days + loss_days
        if day_sum > total_days:
            errors.append(
                f"{prefix}profit_days({profit_days}) + loss_days({loss_days}) = {day_sum} > total_days({total_days})"
            )

    # 5. 2026-06-06新增: total_commission ≈ sum(trade.commission) (允许1元误差)
    if (
        total_commission is not None
        and trade_commission_sum is not None
        and abs(total_commission - trade_commission_sum) > 1.0
    ):
        errors.append(
            f"{prefix}total_commission({total_commission:.2f}) "
            f"≠ 逐笔commission之和({trade_commission_sum:.2f}), "
            f"差异={abs(total_commission - trade_commission_sum):.2f}"
        )

    return errors
