# -*- coding: utf-8 -*-
"""数据管理器 - 统一数据访问入口

提供简洁的高层数据接口，外部模块只需通过此类与data模块交互，
无需关心内部数据库实现细节。

核心设计原则：
    1. 对外隐藏数据库概念，仅暴露数据类型约定
    2. 返回数据直接是 DataFrame，自动通过 Pandera 验证
    3. 提供完整的元数据查询能力
    4. 支持正则匹配查询可用品种
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from common.constants import COMMON_KLINE_INTERVALS
import pandas as pd
from pathlib import Path

import pandera.pandas as pa
from pandera.typing import DataFrame

from .store import DataStore
from .datasource import list_sources
from .models import (
    KlineSchema,
    BacktestRecord,
    TradeRecord,
    SymbolInfo,
    DataSummary,
)

if TYPE_CHECKING:
    from config import ConfigManager

logger = logging.getLogger(__name__)


class DataManager:
    """数据管理器 - 统一数据访问入口

    提供数据加载、保存、查询等高层接口，对外隐藏数据库实现细节。
    所有 DataFrame 数据都经过 Pandera Schema 验证。
    """

    def __init__(self, config_manager: ConfigManager | None = None):
        """
        Args:
            config_manager: ConfigManager实例（可选）
        """
        self._config: ConfigManager | None = config_manager
        self._store: DataStore | None = None
        self._data_cache: dict[str, pd.DataFrame] = {}
        self._default_config: ConfigManager | None = None

    def _get_config(self) -> ConfigManager:
        """获取配置管理器（延迟初始化默认配置）"""
        if self._config:
            return self._config
        if self._default_config is None:
            from config import ConfigManager
            self._default_config = ConfigManager()
        return self._default_config

    def _get_data_dir(self) -> str:
        """获取数据目录"""
        return '.quant_shared_data/csv'

    def _get_filename_template(self) -> str:
        """获取文件名模板配置"""
        return self._get_config().get_data_config().filename_template

    def _get_default_provider(self) -> str:
        """获取回测优先数据源"""
        return self._get_config().get_backtest_config().provider

    def _get_default_interval(self) -> str:
        """获取默认K线周期配置"""
        return self._get_config().get_backtest_config().interval

    def _init_store(self) -> None:
        """延迟初始化存储层"""
        if self._store is None:
            db_path = self._get_config().get_data_config().db_path or '.quant_shared_data/quant_shared.db'
            self._store = DataStore(db_path)

    @property
    def store(self) -> DataStore:
        """获取存储层实例（延迟初始化）"""
        self._init_store()
        assert self._store is not None
        return self._store

    # ── 元数据查询 ─────────────────────────────────────────

    def get_all_symbols(self) -> list[str]:
        """获取所有可用的品种代码列表

        Returns:
            品种代码列表，按字母排序
        """
        data_dir = self._get_data_dir()

        csv_dir = Path(data_dir)
        if not csv_dir.exists():
            return []

        files = list(csv_dir.glob('*.csv'))

        # 从文件名提取品种名
        # 新格式: {symbol}.{provider}.{interval}.csv
        # 旧格式: {symbol}.{interval}.csv
        symbols: set[str] = set()
        common_intervals = COMMON_KLINE_INTERVALS
        known_providers = set(list_sources())
        for f in files:
            name = f.stem
            # 新格式: name.rsplit('.', 2) → [symbol, provider, interval]
            parts3 = name.rsplit('.', 2)
            if len(parts3) == 3 and parts3[-1] in common_intervals and parts3[1] in known_providers:
                symbols.add(parts3[0])
                continue

            # 旧格式: name.rsplit('.', 1) → [symbol, interval]
            parts2 = name.rsplit('.', 1)
            if len(parts2) == 2 and parts2[-1] in common_intervals:
                symbols.add(parts2[0])
                continue

            # 无法解析，直接用文件名
            symbols.add(name)

        return sorted(symbols)

    def search_symbols(self, pattern: str) -> list[str]:
        """按正则表达式搜索可用品种

        Args:
            pattern: 正则表达式模式（如 'DCE\\.m' 匹配所有豆粕合约）

        Returns:
            匹配的品种代码列表
        """
        all_symbols = self.get_all_symbols()
        regex = re.compile(pattern)
        return [s for s in all_symbols if regex.search(s)]

    def get_symbol_info(self, symbol: str) -> SymbolInfo:
        """获取品种的详细元数据信息

        Args:
            symbol: 品种代码

        Returns:
            SymbolInfo: 品种信息
        """
        meta = self.store.get_metadata(symbol)

        if meta:
            meta_filepath = str(meta.get('filepath', ''))
            if meta_filepath and Path(meta_filepath).exists():
                return SymbolInfo(
                    symbol=symbol,
                    available=True,
                    filepath=meta_filepath,
                    start_date=str(meta.get('start_date', '')),
                    end_date=str(meta.get('end_date', '')),
                    total_rows=int(meta.get('total_rows', 0)),  # pyright: ignore[reportArgumentType]  # SQLite dict
                )

        data_dir = self._get_data_dir()
        filename_template = self._get_filename_template()

        provider = self._get_default_provider()
        filename = filename_template.format(symbol=symbol, provider=provider, interval='1m')
        filepath = Path(data_dir) / filename

        if filepath.exists():
            df = self._load_csv_with_validation(filepath)
            if df is not None:
                return SymbolInfo(
                    symbol=symbol,
                    available=True,
                    filepath=str(filepath),
                    start_date=str(df['datetime'].min())[:10] if not df.empty else None,
                    end_date=str(df['datetime'].max())[:10] if not df.empty else None,
                    total_rows=len(df),
                )

        logger.warning(f"品种 {symbol} 的数据文件不存在: {filepath}")
        return SymbolInfo(
            symbol=symbol,
            available=False,
            error='数据文件不存在',
        )

    def get_data_summary(self) -> DataSummary:
        """获取所有可用数据的汇总信息

        Returns:
            DataSummary: 数据汇总
        """
        symbols = self.get_all_symbols()
        symbol_infos = [self.get_symbol_info(s) for s in symbols]
        return DataSummary(total_symbols=len(symbols), symbols=symbol_infos)

    # ── 数据加载（使用 Pandera 验证）────────────────────────

    def _load_csv_with_validation(self, filepath: Path) -> DataFrame[KlineSchema] | None:
        """加载CSV文件并通过 Pandera 验证"""
        try:
            df = pd.read_csv(filepath)
            df['datetime'] = pd.to_datetime(df['datetime'])
            validated_df = KlineSchema.validate(df)
            return validated_df
        except pa.errors.SchemaError as e:
            logger.error(f"数据验证失败 [{filepath}]: {e}")
            return None
        except Exception as e:
            logger.error(f"加载CSV失败 [{filepath}]: {e}", exc_info=True)
            return None

    @pa.check_output(KlineSchema)
    def load_kline(self, symbol: str, start_date: str | None = None, end_date: str | None = None,
                   interval: str | None = None, provider: str | None = None) -> pd.DataFrame:
        """加载K线数据，直接返回经过 Pandera 验证的 DataFrame

        Args:
            symbol: 品种代码（如 'DCE.m2509'）
            start_date: 开始日期（可选，格式 'YYYY-MM-DD'）
            end_date: 结束日期（可选，格式 'YYYY-MM-DD'）
            interval: K线周期（默认从配置读取）
            provider: 数据源（默认从配置读取）

        Returns:
            经过 Pandera KlineSchema 验证的 K 线数据
        """
        if interval is None:
            interval = self._get_default_interval()

        data_dir = self._get_data_dir()
        filename_template = self._get_filename_template()

        # 尝试找到数据文件：指定 provider > 回测配置 provider > 遍历所有
        if provider:
            candidates = [provider]
        else:
            bt_provider = self._get_default_provider()
            if bt_provider:
                candidates = [bt_provider] + [p for p in list_sources() if p != bt_provider]
            else:
                candidates = list_sources()
        filepath = None
        matched_provider = None
        for p in candidates:
            fp = Path(data_dir) / filename_template.format(symbol=symbol, provider=p, interval=interval)
            if fp.exists():
                filepath = fp
                matched_provider = p
                break

        if filepath is None:
            raise FileNotFoundError(
                f"数据文件不存在: {symbol} (interval={interval}, providers={candidates})"
            )

        cache_key = f"{symbol}_{matched_provider}_{interval}_{start_date}_{end_date}"
        if cache_key in self._data_cache:
            logger.debug(f"从缓存加载数据: {symbol}")
            return self._data_cache[cache_key]

        df = pd.read_csv(filepath)
        df['datetime'] = pd.to_datetime(df['datetime'])

        if start_date:
            df = df[df['datetime'] >= pd.Timestamp(start_date)]
        if end_date:
            df = df[df['datetime'] <= pd.Timestamp(end_date)]

        self._data_cache[cache_key] = df  # pyright: ignore[reportArgumentType]  # pandas 类型噪音
        logger.info(f"加载K线数据: {symbol}, 共 {len(df)} 条")

        return df  # pyright: ignore[reportReturnType]

    def load_kline_safe(self, symbol: str, start_date: str | None = None, end_date: str | None = None,
                        interval: str | None = None, provider: str | None = None) -> pd.DataFrame | None:
        """加载K线数据，失败返回None（不抛异常）"""
        try:
            return self.load_kline(symbol, start_date, end_date, interval, provider)
        except Exception as e:
            logger.error(f"加载K线数据失败: {e}")
            return None

    # ── 回测记录 ────────────────────────────────────────────

    def insert_backtest(self, symbol: str, strategy: str, status: str,
                        error_message: str | None, statistics: dict[str, object],
                        engine_config: dict[str, object], params_json: str | None,
                        start_date: str | None, end_date: str | None,
                        strategy_version: str | None = None,
                        git_hash: str | None = None) -> int:
        """插入完整的回测记录"""
        return self.store.insert_backtest_detailed(
            symbol=symbol,
            strategy=strategy,
            status=status,
            error_message=error_message,
            statistics=statistics,
            engine_config=engine_config,
            params_json=params_json,
            start_date=start_date,
            end_date=end_date,
            strategy_version=strategy_version,
            git_hash=git_hash,
        )

    def insert_backtest_trades(self, backtest_id: int, trades: list[dict[str, object]]) -> int:
        """批量插入交易明细"""
        return self.store.insert_backtest_trades(backtest_id, trades)

    def query_backtests(
        self,
        symbol: str | None = None,
        strategy: str | None = None,
        status: str = 'success',
        limit: int = 50,
    ) -> list[BacktestRecord]:
        """查询回测记录列表"""
        return self.store.query_backtests(symbol, strategy, status, limit)

    def get_backtest(self, backtest_id: int) -> BacktestRecord | None:
        """查询单条回测记录"""
        return self.store.get_backtest(backtest_id)

    def query_trades(self, backtest_id: int) -> list[TradeRecord]:
        """查询交易明细"""
        return self.store.query_trades(backtest_id)

    def insert_backtest_daily(self, backtest_id: int, daily_results: list[dict[str, object]]) -> int:
        """批量插入每日资金曲线数据"""
        return self.store.insert_backtest_daily(backtest_id, daily_results)

    def query_daily(self, backtest_id: int) -> list[dict[str, object]]:
        """查询每日资金曲线"""
        return self.store.query_daily(backtest_id)

    def delete_backtest(self, backtest_id: int) -> bool:
        """硬删除回测记录及关联的交易明细和每日资金曲线

        Args:
            backtest_id: 回测记录 ID

        Returns:
            是否成功删除
        """
        self._init_store()
        assert self._store is not None
        return self._store.delete_backtest(backtest_id)

    # ── 资源管理 ────────────────────────────────────────────

    def clear_cache(self) -> None:
        """清除数据缓存"""
        self._data_cache.clear()
        logger.info("数据缓存已清除")

    def close(self) -> None:
        """关闭数据库连接"""
        if self._store:
            self._store.close()
            logger.info("数据库连接已关闭")

    def __enter__(self) -> "DataManager":
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: object) -> None:
        self.close()
