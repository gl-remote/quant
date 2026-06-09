"""天勤 TqSdk 数据源 — 从原 exporter 抽离的 K 线获取逻辑"""

from __future__ import annotations

import contextlib
from datetime import datetime
from typing import Any, ClassVar

import pandas as pd
from loguru import logger

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
        以此为锚点继续往前拉，直到覆盖到 start_date 或无新数据为止。

        对已到期合约的特殊处理：默认 end_date 是交割月首日，但合约实际在
        交割月前就停止交易了。如果从 end_date 开始拿不到数据，会自动往前
        推进 30 天重试，最多 4 次（最多往前推 4 个月）。
        """
        from datetime import timedelta

        end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=15)
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=9)

        # 从合约代码解析到期月（如 DCE.m2601 → 2026-01），若 end_date 落在交割月，
        # 自动向前调整到交割月前，避免已到期合约第一次拉取就失败
        expiry_dt = self._parse_expiry(symbol)
        effective_end = end_dt
        if expiry_dt and end_dt >= expiry_dt:
            # 调整到交割月第1天的前30天（活跃交易期的末尾附近）
            effective_end = (expiry_dt - timedelta(days=30)).replace(hour=15)
            logger.info(
                f"tqsdk {symbol}: end_date ({end_date}) 落在交割月 ({expiry_dt:%Y-%m})，"
                f"调整拉取起始点到 {effective_end:%Y-%m-%d}"
            )

        logger.info(f"tqsdk {symbol}: 拉取 {start_date} ~ {end_date} (period={kline_period}s)")

        all_dfs: list[pd.DataFrame] = []
        seg_end = effective_end
        seg_count = 0
        max_segments = 20
        # 对已到期合约：若初始 end_dt 拿不到数据，往前推进找活跃交易期
        empty_attempts = 0
        max_empty_attempts = 4

        while seg_count < max_segments:
            seg_count += 1
            df = self._fetch_once(symbol, seg_end, kline_period, account)

            if df.empty:
                # 没有拿到数据：如果是刚开始尝试，往前推进 seg_end 找活跃交易期
                if not all_dfs and empty_attempts < max_empty_attempts:
                    empty_attempts += 1
                    old_end = seg_end
                    seg_end = seg_end - timedelta(days=30)
                    logger.info(
                        f"tqsdk {symbol}: 从 {old_end:%Y-%m-%d} 开始未拿到数据，"
                        f"推进到 {seg_end:%Y-%m-%d} 重试 ({empty_attempts}/{max_empty_attempts})"
                    )
                    if seg_end <= start_dt:
                        logger.info(f"tqsdk {symbol}: 已推进到起始日期前，停止尝试")
                        break
                    continue
                break

            all_dfs.append(df)

            # 本段最早数据时间
            min_dt = pd.to_datetime(df["datetime"]).min()

            # 确保 df 有数据时才访问（防御性）
            first_dt = df["datetime"].iloc[0] if len(df) > 0 else "N/A"
            last_dt = df["datetime"].iloc[-1] if len(df) > 0 else "N/A"
            logger.debug(f"tqsdk {symbol}: 分段 {seg_count - empty_attempts}: {first_dt} ~ {last_dt}, {len(df)} 行")

            if min_dt <= datetime.strptime(start_date, "%Y-%m-%d"):
                logger.debug(f"tqsdk {symbol}: 已覆盖到 {start_date}，停止分段拉取")
                break

            # 下一段以本段最早时间 + 1 小时为锚点，继续往前拿
            seg_end = min_dt.to_pydatetime() + timedelta(hours=1)

        if not all_dfs:
            logger.warning(f"tqsdk {symbol}: 未能获取到任何数据（可能已过期或无历史数据）")
            return pd.DataFrame(columns=Qlib_COLUMNS)

        actual_segments = seg_count - empty_attempts
        if actual_segments > 1:
            logger.info(f"tqsdk {symbol}: 分段拉取完成，共 {actual_segments} 段")

        combined = pd.concat(all_dfs, ignore_index=True)
        combined = combined.drop_duplicates(subset="datetime", keep="last")
        combined = combined.sort_values("datetime").reset_index(drop=True)

        # 按用户要求的 start_date 截断
        combined["_dt"] = pd.to_datetime(combined["datetime"])
        combined = combined[combined["_dt"] >= pd.Timestamp(start_date)]
        combined = combined.drop(columns=["_dt"]).reset_index(drop=True)

        # 最终汇总（防御性：combined 可能在过滤后为空）
        if len(combined) > 0:
            logger.info(
                f"tqsdk {symbol}: 最终 {len(combined)} 行, "
                f"{combined['datetime'].iloc[0]} ~ {combined['datetime'].iloc[-1]}"
            )
        else:
            logger.info(f"tqsdk {symbol}: 最终 0 行")

        # 返回原始列（不包含 amount），让 _to_standard_df 统一处理列标准化
        return combined

    @staticmethod
    def _parse_expiry(symbol: str) -> datetime | None:
        """从合约代码解析到期年月。合约格式：交易所.品种YYMM，如 DCE.m2601 → 2026-01-01。"""
        try:
            # 取点后部分的最后4位作为 YYMM
            code = symbol.split(".")[-1]
            if len(code) < 4:
                return None
            yymm = code[-4:]
            yy = int(yymm[:2])
            mm = int(yymm[2:])
            if not (1 <= mm <= 12):
                return None
            year = 2000 + yy
            return datetime(year, mm, 1)
        except (ValueError, IndexError):
            return None

    def _fetch_once(
        self,
        symbol: str,
        end_dt: datetime,
        kline_period: int,
        account: object,
    ) -> pd.DataFrame:
        """单次 tqsdk 拉取：以 end_dt 为锚点，preload 往回拿 ~10000 条

        注意：对已到期合约，end_dt 应落在合约活跃交易期内（不要晚于最后交易日）。
        """
        from datetime import timedelta

        from common.tqsdk_imports import tqsdk

        if not tqsdk.ensure():
            logger.error("tqsdk 未安装，无法拉取数据")
            return pd.DataFrame(columns=Qlib_COLUMNS)

        start_dt = end_dt - timedelta(minutes=30)
        logger.debug(f"_fetch_once: {symbol} 窗口 {start_dt:%Y-%m-%d %H:%M} ~ {end_dt:%Y-%m-%d %H:%M}")

        empty_result = pd.DataFrame(columns=Qlib_COLUMNS)
        api: Any = None

        try:
            auth = tqsdk.TqAuth(account.api_key, account.api_secret) if account else None  # type: ignore[attr-defined]
            api = tqsdk.TqApi(backtest=tqsdk.TqBacktest(start_dt=start_dt, end_dt=end_dt), auth=auth)

            klines = api.get_kline_serial(symbol, duration_seconds=kline_period, data_length=self._MAX_DATA_LENGTH)

            with contextlib.suppress(tqsdk.BacktestFinished):
                api.wait_update()

            # —— 从 klines 对象提取有效数据 ——
            raw_datetime = klines["datetime"]
            raw_open = klines["open"]
            raw_high = klines["high"]
            raw_low = klines["low"]
            raw_close = klines["close"]
            raw_volume = klines["volume"]

            raw_lens = [len(x) for x in [raw_datetime, raw_open, raw_high, raw_low, raw_close, raw_volume]]
            if len(set(raw_lens)) != 1:
                logger.warning(f"_fetch_once: {symbol} klines 列长度不一致 {raw_lens}，返回空")
                api.close()
                return empty_result

            logger.debug(f"_fetch_once: {symbol} 原始 klines 行数 = {raw_lens[0]}")

            kline_df = pd.DataFrame(
                {
                    "datetime": list(raw_datetime),
                    "open": list(raw_open),
                    "high": list(raw_high),
                    "low": list(raw_low),
                    "close": list(raw_close),
                    "volume": list(raw_volume),
                }
            )
            api.close()
        except Exception as e:
            # 已到期合约 / 数据不可用 / tqsdk 内部问题等，返回空，由 _do_fetch 决定是否推进重试
            logger.debug(f"_fetch_once: {symbol} ({end_dt:%Y-%m-%d}) 拉取失败: {e}，返回空")
            try:
                if api is not None:
                    api.close()
            except Exception:
                pass
            return empty_result

        if kline_df.empty or "datetime" not in kline_df.columns:
            logger.debug(f"_fetch_once: {symbol} kline_df 为空，返回空")
            return empty_result

        # 过滤掉 datetime=0 的空行 + 价格全 NaN 行
        before = len(kline_df)
        kline_df = kline_df.dropna(subset=["open", "high", "low", "close"], how="all")
        kline_df = kline_df[kline_df["datetime"] > 0]
        after_drop = len(kline_df)
        if before != after_drop:
            logger.debug(f"_fetch_once: {symbol} 过滤无效行 {before} -> {after_drop}")

        if kline_df.empty:
            logger.debug(f"_fetch_once: {symbol} 过滤后为空，返回空")
            return empty_result

        # 纳秒 -> datetime 字符串
        kline_df["datetime"] = pd.to_datetime(kline_df["datetime"], unit="ns").dt.strftime("%Y-%m-%d %H:%M:%S")

        # 过滤 2000 年之前的脏数据
        kline_df = kline_df[kline_df["datetime"] >= "2000-01-01"]
        if kline_df.empty:
            logger.debug(f"_fetch_once: {symbol} 全部数据在 2000 年之前，返回空")
            return empty_result

        # volume 转整数
        try:
            kline_df["volume"] = kline_df["volume"].fillna(0).astype(int)
        except (ValueError, TypeError):
            logger.warning(f"_fetch_once: {symbol} volume 列转 int 失败，置 0")
            kline_df["volume"] = 0

        kline_df = (
            kline_df.sort_values("datetime").drop_duplicates(subset="datetime", keep="last").reset_index(drop=True)
        )

        logger.debug(f"_fetch_once: {symbol} 返回 {len(kline_df)} 行")
        # 返回原始列（datetime/open/high/low/close/volume），amount 由 _to_standard_df 统一添加
        return kline_df

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
