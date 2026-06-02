# -*- coding: utf-8 -*-
"""AkShare 数据源 — 基于 akshare 免费数据接口获取期货 K 线

支持周期:
    - 分钟级: 1m/5m/15m/30m/1h (via futures_zh_minute_sina)
    - 日线级: 1d (via futures_zh_daily_sina)
    不支持的周期直接报错，不映射不降级。
"""

from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportAssignmentType=false
# pyright: reportUnknownArgumentType=false, reportUnknownVariableType=false, reportMissingImports=false
# 注：akshare 第三方库缺少类型存根

from loguru import logger
from typing import ClassVar, Any

import pandas as pd

from .base import BaseDataSource, Qlib_COLUMNS

# 分钟线接口: futures_zh_minute_sina(symbol, period)
# 日线接口:   futures_zh_daily_sina(symbol)
_MINUTE_PERIOD_MAP: dict[str, str] = {
    "1m": "1",
    "5m": "5",
    "15m": "15",
    "30m": "30",
    "1h": "60",
}

_SUPPORTED_INTERVALS: set[str] = {*_MINUTE_PERIOD_MAP.keys(), "1d"}


class AkShareDataSource(BaseDataSource):
    """AkShare 免费数据源

    基于 akshare 获取期货历史 K 线数据，无需 API 账号。
    支持 1m/5m/15m/30m/1h/1d 周期，不支持的周期直接报错。
    """

    name: ClassVar[str] = "akshare"

    def fetch_kline(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str = "1m",
        **kwargs: Any,
    ) -> pd.DataFrame:
        """从 AkShare 获取期货 K 线数据

        Args:
            symbol: 品种代码 (如 DCE.m2509)，自动转为 akshare 格式 (M2509)
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            interval: K 线周期，支持: {sorted(_SUPPORTED_INTERVALS)}

        Returns:
            标准 Qlib 格式 DataFrame

        Raises:
            ValueError: interval 不支持
        """
        if interval not in _SUPPORTED_INTERVALS:
            available = ", ".join(sorted(_SUPPORTED_INTERVALS))
            raise ValueError(
                f"akshare 不支持周期 {interval!r}，可选周期: {available}"
            )

        akshare_symbol = self._to_akshare_symbol(symbol)
        logger.debug(
            f"AkShare 拉取: {symbol} → {akshare_symbol}, "
            f"{start_date} ~ {end_date}, interval={interval}"
        )

        def _fetch() -> pd.DataFrame:
            return self._do_fetch(akshare_symbol, start_date, end_date, interval)

        raw_df = self._retry_fetch(_fetch, symbol, start_date, end_date, interval)
        if raw_df.empty:
            return raw_df

        return self._to_standard_df(raw_df)

    def _do_fetch(
        self, akshare_symbol: str, start_date: str, end_date: str, interval: str
    ) -> pd.DataFrame:
        """根据 interval 调用对应的 akshare 接口"""
        import akshare as ak

        if interval == "1d":
            return self._fetch_daily(ak, akshare_symbol, start_date, end_date)
        else:
            period = _MINUTE_PERIOD_MAP[interval]
            return self._fetch_minute(ak, akshare_symbol, period, start_date, end_date)

    @staticmethod
    def _fetch_minute(
        ak: Any, akshare_symbol: str, period: str,
        start_date: str, end_date: str,
    ) -> pd.DataFrame:
        """通过 futures_zh_minute_sina 获取分钟线

        返回列: datetime, open, high, low, close, volume, hold
        注意: 新浪源分钟数据历史区间有限，远期合约可能无数据。
        """
        try:
            df = ak.futures_zh_minute_sina(symbol=akshare_symbol, period=period)
        except Exception:
            logger.error(f"AkShare 分钟线拉取失败: {akshare_symbol}, period={period}")
            raise

        if df is None or df.empty:
            logger.warning(
                f"AkShare 分钟线无数据: {akshare_symbol}, period={period}"
            )
            return pd.DataFrame(columns=Qlib_COLUMNS)

        return _filter_by_date(df, start_date, end_date, col="datetime")

    @staticmethod
    def _fetch_daily(
        ak: Any, akshare_symbol: str, start_date: str, end_date: str,
    ) -> pd.DataFrame:
        """通过 futures_zh_daily_sina 获取日线

        返回列: date, open, high, low, close, volume, hold, settle
        """
        try:
            df = ak.futures_zh_daily_sina(symbol=akshare_symbol)
        except Exception:
            logger.error(f"AkShare 日线拉取失败: {akshare_symbol}")
            raise

        if df is None or df.empty:
            logger.warning(f"AkShare 日线无数据: {akshare_symbol}")
            return pd.DataFrame(columns=Qlib_COLUMNS)

        # 日线接口用 'date' 作为时间列，统一为 'datetime'
        if "date" in df.columns:
            df = df.rename(columns={"date": "datetime"})

        return _filter_by_date(df, start_date, end_date, col="datetime")

    @staticmethod
    def _to_akshare_symbol(symbol: str) -> str:
        """将项目统一格式转为 akshare 期货符号

        DCE.m2509  → M2509
        CZCE.SR309 → SR309
        SHFE.rb2410 → RB2410
        """
        from common.symbol_utils import parse_contract
        c = parse_contract(symbol)
        if c:
            return c.contract_code.upper()
        # 解析失败时回退：去掉交易所前缀 + 转大写
        return symbol.split(".", 1)[-1].upper() if "." in symbol else symbol.upper()


def _filter_by_date(
    df: pd.DataFrame, start_date: str, end_date: str, col: str = "datetime"
) -> pd.DataFrame:
    """按日期范围过滤 DataFrame

    start_date 包含当天 00:00:00，
    end_date 包含当天 23:59:59（避免日期边界把当天分钟数据排除）。
    """
    if col not in df.columns:
        logger.error(f"数据缺少 {col} 列，现有列: {df.columns.tolist()}")
        return pd.DataFrame(columns=Qlib_COLUMNS)

    df = df.copy()
    df[col] = pd.to_datetime(df[col]).dt.strftime("%Y-%m-%d %H:%M:%S")

    start_dt = pd.Timestamp(start_date)
    # end_date 含整天数据：扩展到 23:59:59
    end_dt = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    df["_dt"] = pd.to_datetime(df[col])
    df = df[(df["_dt"] >= start_dt) & (df["_dt"] <= end_dt)]
    df = df.drop(columns=["_dt"])

    if df.empty:
        logger.warning(f"日期范围内无数据: {start_date} ~ {end_date}")

    return df
