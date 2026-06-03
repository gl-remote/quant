# -*- coding: utf-8 -*-
"""天勤 TqSdk 数据源 — 从原 exporter 抽离的 K 线获取逻辑"""

from __future__ import annotations

from loguru import logger
from datetime import datetime
from typing import ClassVar

import pandas as pd

from .base import BaseDataSource, Qlib_COLUMNS

class TqSdkDataSource(BaseDataSource):
    """天勤量化 (TqSdk) 数据源

    通过 tqsdk 获取期货历史 K 线数据，支持分钟级回放模式。
    需要有效的天勤 API 账号。
    """

    name: ClassVar[str] = "tqsdk"
    supported_intervals: ClassVar[set[str]] = {"1m", "5m", "15m", "30m", "1h", "1d"}

    def fetch_kline(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str = "1m",
        **kwargs: object,  # type: ignore[no-untyped-def]
    ) -> pd.DataFrame:
        """从天勤获取 K 线数据

        Args:
            symbol: 品种代码 (如 DCE.m2509)
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            interval: K 线周期，支持 1m/5m/15m/30m/1h/1d
            **kwargs: 需包含 account (AccountInfo | None)

        Returns:
            标准 Qlib 格式 DataFrame
        """
        account = kwargs.get("account")

        # 将 interval 转为秒数
        kline_period = self._interval_to_seconds(interval)

        def _fetch() -> pd.DataFrame:
            return self._do_fetch(symbol, start_date, end_date, kline_period, account)

        raw_df = self._retry_fetch(_fetch, symbol, start_date, end_date, interval)
        if raw_df.empty:
            return raw_df

        return self._to_standard_df(raw_df)

    # tqsdk get_kline_serial 内部上限约 10000 条（仅文档说明，分段逻辑不再依赖此值）
    _TQ_PRELOAD_BARS: ClassVar[int] = 10000
    # data_length 参数的上限，大于 tqsdk 实际能返回的即可
    _MAX_DATA_LENGTH: ClassVar[int] = 200000

    def _do_fetch(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        kline_period: int,
        account: object,
    ) -> pd.DataFrame:
        """执行天勤 API 拉取，以实际数据驱动分段：每次拉取后取最早时间，
        以此为锚点继续往前拉，直到覆盖到 start_date 或无新数据为止。"""
        from datetime import timedelta

        end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=15)
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=9)

        all_dfs: list[pd.DataFrame] = []
        seg_end = end_dt
        seg_count = 0
        max_segments = 20  # 安全上限

        while seg_count < max_segments:
            seg_count += 1
            df = self._fetch_once(symbol, seg_end, kline_period, account)

            if df.empty:
                break

            all_dfs.append(df)

            # 本段最早数据时间
            min_dt = pd.to_datetime(df["datetime"]).min()

            if min_dt <= start_dt:
                # 已覆盖到用户要求的起始日期
                break

            # 下一段以本段最早时间 + 1 小时为锚点，继续往前拿
            seg_end = min_dt.to_pydatetime() + timedelta(hours=1)

        if not all_dfs:
            return pd.DataFrame(columns=Qlib_COLUMNS)

        if seg_count > 1:
            logger.info(f"tqsdk 分段拉取 {symbol}: 共 {seg_count} 段")

        combined = pd.concat(all_dfs, ignore_index=True)
        combined = combined.drop_duplicates(subset="datetime", keep="last")
        combined = combined.sort_values("datetime").reset_index(drop=True)

        # 按用户要求的 start_date 截断
        combined = combined[combined["datetime"] >= start_date]  # type: ignore[assignment]
        combined = combined.reset_index(drop=True)

        return combined  # type: ignore[return-value]

    def _fetch_once(
        self,
        symbol: str,
        end_dt: datetime,
        kline_period: int,
        account: object,
    ) -> pd.DataFrame:
        """单次 tqsdk 拉取：以 end_dt 为锚点，preload 往回拿 ~10000 条"""
        from datetime import timedelta
        from common.tqsdk_imports import tqsdk

        if not tqsdk.ensure():
            logger.error("tqsdk 未安装，无法拉取数据")
            return pd.DataFrame()

        # start_dt 设为 end_dt 前 1 天，preload 全部用于历史数据
        start_dt = end_dt - timedelta(days=1)

        auth = tqsdk.TqAuth(account.api_key, account.api_secret) if account else None  # type: ignore[attr-defined]

        api = tqsdk.TqApi(
            backtest=tqsdk.TqBacktest(start_dt=start_dt, end_dt=end_dt), auth=auth
        )

        klines = api.get_kline_serial(
            symbol, duration_seconds=kline_period, data_length=self._MAX_DATA_LENGTH
        )

        try:
            api.wait_update()
        except tqsdk.BacktestFinished:
            pass

        rows = []
        for i in range(len(klines)):
            ts = datetime.fromtimestamp(
                klines["datetime"].iloc[i] / 10**9
            )
            row = {
                "datetime": ts.strftime("%Y-%m-%d %H:%M:%S"),
                "open": float(klines["open"].iloc[i]),
                "high": float(klines["high"].iloc[i]),
                "low": float(klines["low"].iloc[i]),
                "close": float(klines["close"].iloc[i]),
                "volume": int(klines["volume"].iloc[i]),
            }
            rows.append(row)

        api.close()

        return pd.DataFrame(rows, columns=Qlib_COLUMNS)

    @staticmethod
    def _interval_to_seconds(interval: str) -> int:
        """将 interval 字符串转换为秒数"""
        mapping = {
            "1m": 60,
            "5m": 300,
            "15m": 900,
            "30m": 1800,
            "1h": 3600,
            "1d": 86400,
        }
        seconds = mapping.get(interval)
        if seconds is None:
            raise ValueError(f"不支持的 K 线周期: {interval!r}")
        return seconds
