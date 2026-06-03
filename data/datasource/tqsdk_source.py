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

    # tqsdk get_kline_serial 内部上限约 10000 条，preload 往 start 之前倒推
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
        """执行单次天勤 API 拉取"""
        from common.tqsdk_imports import tqsdk

        if not tqsdk.ensure():
            logger.error("tqsdk 未安装，无法拉取数据")
            return pd.DataFrame()

        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        # tqsdk backtest 模式下 preload 最多 ~10000 条，replay 阶段几乎拿不到数据。
        # 直接把 start_dt 设为 end_dt，让 tqsdk 只做 preload 不跑回放，
        # 10000 条全部用于覆盖 end_dt 之前的历史数据。
        start_dt = end_dt

        auth = tqsdk.TqAuth(account.api_key, account.api_secret) if account else None  # type: ignore[attr-defined]

        api = tqsdk.TqApi(
            backtest=tqsdk.TqBacktest(start_dt=start_dt, end_dt=end_dt), auth=auth
        )

        # tqsdk 以 end_dt 为锚点，从数据源拉回最多 data_length 条
        # 设置一个足够大的值让 tqsdk 尽其所能返回
        klines = api.get_kline_serial(
            symbol, duration_seconds=kline_period, data_length=self._MAX_DATA_LENGTH
        )

        rows = []
        prev_len = 0
        try:
            while True:
                api.wait_update()
                if api.is_changing(klines):
                    current_len = len(klines)
                    for i in range(prev_len, current_len):
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
                    prev_len = current_len
        except tqsdk.BacktestFinished:
            pass
        except Exception:
            api.close()
            raise
        finally:
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
