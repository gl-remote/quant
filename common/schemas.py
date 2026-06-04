# -*- coding: utf-8 -*-
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
from pandera.typing import Series
from pandera.typing import DataFrame


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
    def check_high_greater_than_open_close(cls, df: pd.DataFrame) -> bool:  # type: ignore[misc]
        """验证最高价 >= 开盘价和收盘价"""
        result: bool = bool((df['high'] >= df[['open', 'close']].max(axis=1)).all())
        return result

    @pa.dataframe_check
    def check_low_less_than_open_close(cls, df: pd.DataFrame) -> bool:  # type: ignore[misc]
        """验证最低价 <= 开盘价和收盘价"""
        result: bool = bool((df['low'] <= df[['open', 'close']].min(axis=1)).all())
        return result

    @pa.dataframe_check
    def check_price_range_valid(cls, df: pd.DataFrame) -> bool:  # type: ignore[misc]
        """验证价格区间有效性：low <= close <= high"""
        result: bool = bool((df['low'] <= df['close']).all() & (df['close'] <= df['high']).all())
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
    return_: Series[float] = pa.Field(alias='return')
    equity: Series[float] = pa.Field(ge=0.0)

    class Config:
        coerce = True
        extra = 'allow'


class TradeRecordSchema(pa.DataFrameModel):
    """回测交易记录验证Schema（字段与 ORM BacktestTrade 完全对齐）

    验证写入 backtest_trades 表的交易记录数据。
    字段说明：
        datetime:   成交时间
        symbol:     品种代码 (如 DCE.m2505)
        direction:  方向 (long/short)
        offset:     开平标志 (open/close/closetoday)
        open_price: 开仓价 / 成交价
        close_price: 平仓价 / 成交价
        quantity:   成交量（ORM 统一用 quantity，非 vnpy 原生 volume）
        pnl:        单笔盈亏
        commission: 手续费

    统一规则(2026-06-04):
    - 各引擎层（vnpy/TqSdk）产出时必须使用本 Schema 定义的字段名
    - store 层不再做字段名兼容转换（fallback）
    - vnpy TradeData.volume → 映射为 quantity
    """
    datetime: Series[pd.Timestamp] = pa.Field()
    symbol: Series[str] = pa.Field()
    direction: Series[str] = pa.Field(isin=['long', 'short'])
    offset: Series[str] = pa.Field(isin=['open', 'close', 'closetoday'])
    open_price: Series[float] = pa.Field(ge=0.0)
    close_price: Series[float] = pa.Field(ge=0.0)
    quantity: Series[float] = pa.Field(ge=0.0)
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
        equity: 当日权益
        daily_return: 当日收益率
        drawdown: 当日回撤
    """
    date: Series[pd.Timestamp] = pa.Field()
    equity: Series[float] = pa.Field(ge=0.0)
    daily_return: Series[float] = pa.Field()
    drawdown: Series[float] = pa.Field(le=0.0)

    @pa.dataframe_check
    def check_equity_positive(cls, df: pd.DataFrame) -> bool:  # type: ignore[misc]
        """验证权益值始终为正（账户未爆仓）"""
        return bool((df['equity'] > 0).all())

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
) -> list[str]:
    """验证回测统计字段与交易记录之间的一致性

    调试沉淀(2026-06-04):
    - vn.py statistics 中总交易数字段为 total_trade_count
    - win_trades + loss_trades 应等于 total_trades（允许 None 缺失）
    - backtest_trades 表的实际记录数应等于 total_trades

    Args:
        total_trades: 回测统计中的总交易数
        win_trades: 盈利交易数
        loss_trades: 亏损交易数
        trade_count: backtest_trades 表中的实际交易记录数
        backtest_id: 回测记录 ID（用于日志）

    Returns:
        错误信息列表，空列表表示验证通过
    """
    errors: list[str] = []
    prefix = f"[bt={backtest_id}] " if backtest_id else ""

    # 1. win_trades + loss_trades ≈ total_trades
    if win_trades is not None and loss_trades is not None:
        expected = win_trades + loss_trades
        if expected != total_trades:
            errors.append(
                f"{prefix}win_trades({win_trades}) + loss_trades({loss_trades}) "
                f"= {expected} ≠ total_trades({total_trades})"
            )

    # 2. 实际交易记录数 = total_trades
    if trade_count != total_trades:
        errors.append(
            f"{prefix}backtest_trades 实际记录数({trade_count}) "
            f"≠ total_trades({total_trades})"
        )

    # 3. 如果 total_trades > 0，则 win_trades/loss_trades 不能同时为 None
    if total_trades > 0:
        if win_trades is None and loss_trades is None:
            errors.append(
                f"{prefix}total_trades={total_trades}>0，"
                f"但 win_trades 和 loss_trades 均为 None"
            )

    return errors
