"""数据源抽象基类 — 定义统一的数据获取接口

每个数据源自行处理 interval 兼容性，基类不强制。
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import ClassVar

import pandas as pd
from loguru import logger

# amount = 成交额，源数据有则保留原始值，无则留空字符串
Qlib_COLUMNS: list[str] = ["datetime", "open", "high", "low", "close", "volume", "amount"]


class BaseDataSource(ABC):
    """数据源抽象基类

    所有数据源必须实现 fetch_kline，返回统一格式的 DataFrame。

    子类需定义:
        - name: 数据源名称 (类属性)
        - fetch_kline(): 核心数据获取方法
    """

    name: ClassVar[str] = ""

    # 重试配置（子类可覆盖）
    max_retries: ClassVar[int] = 3
    retry_backoff_base: ClassVar[float] = 1.0

    def _to_standard_df(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        """将原始数据转换为标准 Qlib 格式

        amount (成交额) 处理规则：
            源数据提供了 amount 列 → 保留原始值
            源数据未提供 → 留空字符串 ""

        Args:
            raw_df: 原始 DataFrame，需包含 datetime/open/high/low/close/volume 列

        Returns:
            标准格式 DataFrame，列顺序: datetime/open/high/low/close/volume/amount
        """
        if raw_df.empty:
            return pd.DataFrame(columns=Qlib_COLUMNS)

        df = raw_df.copy()

        # amount (成交额)：源数据提供了就保留，没提供就留空字符串
        if "amount" in df.columns:
            df["amount"] = df["amount"].fillna("")
        else:
            df["amount"] = ""

        # 选择并排序可用列
        available_cols = [c for c in Qlib_COLUMNS if c in df.columns]
        df = df[available_cols]

        # 补充缺失列（amount 已在上面处理，不会走到这里）
        for col in Qlib_COLUMNS:
            if col not in df.columns:
                df[col] = 0.0

        # 排序去重
        df = df.sort_values("datetime").drop_duplicates(subset="datetime", keep="last")

        # 过滤无效数据：timestamp=0 导致的 1970 年脏数据、全 NaN 行
        df["_dt"] = pd.to_datetime(df["datetime"])
        df = df[df["_dt"].dt.year >= 2000]
        df = df.dropna(subset=["open", "high", "low", "close"], how="all")
        df = df.drop(columns=["_dt"])

        df = df.reset_index(drop=True)

        return df[Qlib_COLUMNS]  # type: ignore[no-any-return]

    def _retry_fetch(
        self, fetch_fn: Callable[[], pd.DataFrame], symbol: str, start_date: str, end_date: str, interval: str
    ) -> pd.DataFrame:
        """带指数退避重试的通用 fetch 包装"""
        source_name = self.name or self.__class__.__name__
        for attempt in range(1, self.max_retries + 1):
            try:
                return fetch_fn()
            except Exception as e:
                if attempt < self.max_retries:
                    backoff: float = self.retry_backoff_base * (2 ** (attempt - 1))
                    logger.warning(
                        f"{source_name} 数据拉取失败 (第 {attempt}/{self.max_retries} 次): {e}，"
                        f"{backoff:.0f}s 后重试...",
                        exc_info=(attempt == 1),  # 第一次失败时保留完整堆栈
                    )
                    time.sleep(backoff)
                else:
                    logger.error(f"{source_name} 数据拉取失败，已重试 {self.max_retries} 次: {e}")

        logger.error(f"拉取 {symbol} 数据失败，已耗尽 {self.max_retries} 次重试")
        return pd.DataFrame(columns=Qlib_COLUMNS)

    @abstractmethod
    def fetch_kline(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str = "1m",
        **kwargs: object,  # type: ignore[no-untyped-def]
    ) -> pd.DataFrame:
        """获取 K 线数据

        Args:
            symbol: 品种代码 (如 DCE.m2509)
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            interval: K 线周期 (1m / 5m / 15m / 30m / 1h / 1d)
                     默认 1m，数据源自行处理不支持的周期

        Returns:
            标准 Qlib 格式 DataFrame
            列: datetime, open, high, low, close, volume, amount (成交额)
        """
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.name!r})>"
