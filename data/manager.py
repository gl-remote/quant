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

from loguru import logger
import re
from typing import TYPE_CHECKING, cast

from common.constants import COMMON_KLINE_INTERVALS
from common.schemas import KlineDataFrame
from common.types import BacktestResult
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

class DataManager:
    """数据管理器（单例）

    提供数据加载、保存、查询等高层接口，对外隐藏数据库实现细节。
    所有 DataFrame 数据都经过 Pandera Schema 验证。
    """
    _instance: DataManager | None = None
    _initialized: bool = False

    def __new__(cls, config_manager: ConfigManager | None = None) -> DataManager:
        """单例模式，保证全局只有一个实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # 初始化只执行一次
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_manager: ConfigManager | None = None):
        """
        Args:
            config_manager: ConfigManager实例（可选）
        """
        # 只在第一次初始化时执行
        if self._initialized:
            return
        
        self._config: ConfigManager | None = config_manager
        self._store: DataStore | None = None
        self._data_cache: dict[str, KlineDataFrame] = {}
        self._default_config: ConfigManager | None = None
        self._initialized = True

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
            pattern: 正则表达式模式（匹配文件名，如 'DCE\\.m.*\\.1m\\.' 匹配 DCE 豆粕的 1 分钟数据）

        Returns:
            匹配的品种代码列表
        """
        data_dir = self._get_data_dir()
        csv_dir = Path(data_dir)
        if not csv_dir.exists():
            return []

        files = list(csv_dir.glob('*.csv'))
        common_intervals = COMMON_KLINE_INTERVALS
        known_providers = set(list_sources())

        data_regex = re.compile(pattern) if pattern else None

        symbols: set[str] = set()
        for f in files:
            filename = f.name
            if data_regex and not data_regex.search(filename):
                continue
            name = f.stem
            parts3 = name.rsplit('.', 2)
            if len(parts3) == 3 and parts3[-1] in common_intervals and parts3[1] in known_providers:
                symbols.add(parts3[0])
            else:
                parts2 = name.rsplit('.', 1)
                if len(parts2) == 2 and parts2[-1] in common_intervals:
                    symbols.add(parts2[0])
                else:
                    symbols.add(name)

        return sorted(symbols)

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
                    total_rows=int(meta.get('total_rows', 0) or 0),  # type: ignore[call-overload]  # SQLite dict
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
            logger.exception(f"加载CSV失败 [{filepath}]: {e}")
            return None

    def load_kline(self, symbols: list[str], start_date: str | None = None,
                   end_date: str | None = None, interval: str | None = None,
                   provider: str | None = None) -> list[tuple[str, KlineDataFrame, str]]:
        """加载K线数据，返回 [(symbol, df, data_src), ...]

        data_src 来自 ExportMetadata 表，由导出过程注册，作为数据溯源路径。

        Args:
            symbols: 品种代码列表（如 ['DCE.m2509', 'SHFE.rb2505']）
            start_date: 开始日期（格式 'YYYY-MM-DD'），None 时不作下限过滤
            end_date: 结束日期（格式 'YYYY-MM-DD'），None 时不作上限过滤
            interval: K线周期，None 时从配置读取默认周期
            provider: 数据源名称（如 'tqsdk'），None 时遍历所有可用源

        Returns:
            按 symbols 顺序返回 [(symbol, DataFrame, data_src), ...]

        Raises:
            FileNotFoundError: ExportMetadata 查不到数据源或文件缺失
            Exception: CSV 读取或解析错误
        """
        if interval is None:
            interval = self._get_default_interval()

        if provider:
            candidates = [provider]
        else:
            bt_provider = self._get_default_provider()
            if bt_provider:
                candidates = [bt_provider] + [p for p in list_sources() if p != bt_provider]
            else:
                candidates = list_sources()

        results: list[tuple[str, KlineDataFrame, str]] = []

        for symbol in symbols:
            data_src = self._resolve_data_src(symbol, interval, candidates)
            cache_key = f"{symbol}_{interval}_{start_date}_{end_date}"

            if cache_key in self._data_cache:
                logger.debug(f"从缓存加载数据: {symbol}")
                results.append((symbol, self._data_cache[cache_key], data_src))
                continue

            df = pd.read_csv(data_src)
            df['datetime'] = pd.to_datetime(df['datetime'])

            if start_date:
                df = df[df['datetime'] >= pd.Timestamp(start_date)]
            if end_date:
                df = df[df['datetime'] <= pd.Timestamp(end_date)]

            df = cast(KlineDataFrame, df)
            self._data_cache[cache_key] = df
            logger.info(f"加载K线数据: {symbol}, 共 {len(df)} 条")
            results.append((symbol, df, data_src))

        return results

    def _resolve_data_src(self, symbol: str, interval: str,
                          candidates: list[str]) -> str:
        """查 ExportMetadata 获取指定品种的数据源路径

        Raises:
            FileNotFoundError: 查不到注册记录或文件缺失
        """
        for p in candidates:
            meta = self.store.get_metadata(symbol, p, interval)
            if meta:
                fp = meta['filepath']
                if not isinstance(fp, str):
                    continue
                if not Path(fp).exists():
                    raise FileNotFoundError(
                        f"数据源记录存在但文件缺失: {symbol} "
                        f"provider={p} filepath={fp}"
                    )
                return fp
        raise FileNotFoundError(
            f"ExportMetadata 中找不到 {symbol} "
            f"(interval={interval}, candidates={candidates})"
        )

    # ── 回测记录 ────────────────────────────────────────────

    def insert_backtest(self, result: BacktestResult, run_id: int | None = None,
                        data_src: str | None = None) -> int:
        """插入完整的回测记录

        Args:
            result: 统一 BacktestResult 结构
            run_id: Run 记录 ID
            data_src: 数据源文件路径，用于报告生成时定位K线数据
        """
        return self.store.insert_backtest_detailed(result, run_id=run_id, data_src=data_src)

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

    # ── 报告生成相关查询 ──────────────────────────────────────

    def get_run_info(self, run_id: int) -> dict[str, object] | None:
        """获取运行信息"""
        return self.store.get_run_info(run_id)

    def get_all_runs(self) -> list[dict[str, object]]:
        """获取所有运行记录"""
        return self.store.get_all_runs()

    def get_run_summary(self, run_id: int) -> list[dict[str, object]]:
        """获取每品种最优回测记录"""
        return self.store.get_run_summary(run_id)

    def get_backtests_for_run(self, run_id: int) -> list[dict[str, object]]:
        """获取某 run 下所有回测记录（含参数和日线数据）"""
        return self.store.get_backtests_for_run(run_id)

    def get_equity_data(self, backtest_id: int) -> dict[str, object] | None:
        """获取指定回测记录的资金曲线数据"""
        return self.store.get_equity_data(backtest_id)

    def get_optuna_data(self, run_id: int) -> dict[str, object] | None:
        """获取 Optuna 优化数据"""
        return self.store.get_optuna_data(run_id)

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
