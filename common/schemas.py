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

    @pa.dataframe_check  # type: ignore[misc]
    def check_high_greater_than_open_close(cls, df: pd.DataFrame) -> bool:
        """验证最高价 >= 开盘价和收盘价"""
        result: bool = bool((df['high'] >= df[['open', 'close']].max(axis=1)).all())
        return result

    @pa.dataframe_check  # type: ignore[misc]
    def check_low_less_than_open_close(cls, df: pd.DataFrame) -> bool:
        """验证最低价 <= 开盘价和收盘价"""
        result: bool = bool((df['low'] <= df[['open', 'close']].min(axis=1)).all())
        return result

    @pa.dataframe_check  # type: ignore[misc]
    def check_price_range_valid(cls, df: pd.DataFrame) -> bool:
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


# 类型别名，方便使用
KlineDataFrame = DataFrame[KlineSchema]
DailyReturnDataFrame = DataFrame[DailyReturnSchema]
