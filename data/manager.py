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

import re
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pandas as pd
import pandera.pandas as pa
from loguru import logger
from pandera.typing import DataFrame

from common.constants import COMMON_KLINE_INTERVALS
from common.schemas import KlineDataFrame, validate_backtest_consistency
from common.types import BacktestResult

from .datasource import list_sources
from .models import (
    BacktestRecord,
    DataSummary,
    KlineSchema,
    SymbolInfo,
    TradeRecord,
)
from .store import DataStore

if TYPE_CHECKING:
    from config import ConfigManager


def _get_attr(obj: object, key: str, default: object = None) -> object:
    """获取对象属性值（兼容 dict 和 ORM model）"""
    if hasattr(obj, key):
        return getattr(obj, key, default)
    return obj.get(key, default) if isinstance(obj, dict) else default


class DataManager:
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
        return ".quant_shared_data/csv"

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
            db_path = self._get_config().get_data_config().db_path or ".quant_shared_data/quant_shared.db"
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
        return self._collect_symbols()

    def search_symbols(self, pattern: str, interval: str | None = None) -> list[str]:
        """按正则表达式搜索可用品种

        如果 pattern 不包含周期部分（如 'DCE\\.m.*'），会自动根据 interval 拼出完整 pattern
        `DCE\\.m.*\\.$interval\\.`，只匹配对应周期的文件。

        Args:
            pattern: 正则表达式模式（匹配文件名，如 'DCE\\.m.*' 匹配 DCE 豆粕）
            interval: K线周期，如果提供且不在 pattern 中，会自动拼接到 pattern 后。
                如果不提供，从配置读取默认 interval。

        Returns:
            匹配的品种代码列表
        """
        # 如果用户提供的 pattern 不包含周期后缀，自动加上 interval
        # 文件名格式: {symbol}.{provider}.{interval}.csv → 需要 .* 跨过 provider 段
        if interval is None:
            interval = self._get_default_interval()
        # 简单判断：如果 pattern 中找不到 interval，就自动拼接
        if interval not in pattern:
            pattern = f"{pattern}.*\\.{interval}\\."
        return self._collect_symbols(pattern)

    def search_and_load(
        self,
        pattern: str,
        start_date: str | None = None,
        end_date: str | None = None,
        interval: str | None = None,
    ) -> list[tuple[str, KlineDataFrame, str]]:
        """一步到位：搜索匹配的品种并加载数据

        便利接口：自动处理 pattern 拼接 → 搜索 → 加载 全流程。

        Args:
            pattern: 正则表达式模式（匹配文件名，如 'DCE\\.m.*' 匹配 DCE 豆粕）
            start_date: 开始日期，None 使用默认起始
            end_date: 结束日期，None 使用今天
            interval: K线周期，如果不提供从配置读取

        Returns:
            加载完成的数据集列表
        """
        if interval is None:
            interval = self._get_default_interval()
        symbols = self.search_symbols(pattern, interval)
        return self.load_kline(symbols, start_date, end_date, interval)

    def _collect_symbols(self, pattern: str | None = None) -> list[str]:
        """从 CSV 文件名收集品种代码，可选按文件名正则过滤"""
        csv_dir = Path(self._get_data_dir())
        if not csv_dir.exists():
            return []

        data_regex = re.compile(pattern) if pattern else None
        common_intervals = set(COMMON_KLINE_INTERVALS)
        known_providers = set(list_sources())

        symbols: set[str] = set()
        for f in csv_dir.glob("*.csv"):
            if data_regex and not data_regex.search(f.name):
                continue
            symbols.add(self._parse_symbol_from_filename(f.stem, common_intervals, known_providers))
        return sorted(symbols)

    def _parse_symbol_from_filename(
        self,
        name: str,
        common_intervals: set[str],
        known_providers: set[str],
    ) -> str:
        """从文件名 stem 解析品种代码，兼容新旧 CSV 命名格式"""
        parts3 = name.rsplit(".", 2)
        if len(parts3) == 3 and parts3[-1] in common_intervals and parts3[1] in known_providers:
            return parts3[0]

        parts2 = name.rsplit(".", 1)
        if len(parts2) == 2 and parts2[-1] in common_intervals:
            return parts2[0]

        return name

    def get_symbol_info(self, symbol: str) -> SymbolInfo:
        """获取品种的详细元数据信息

        Args:
            symbol: 品种代码

        Returns:
            SymbolInfo: 品种信息
        """
        meta = self.store.get_metadata(symbol)

        if meta:
            meta_filepath = str(meta.get("filepath", ""))
            if meta_filepath and Path(meta_filepath).exists():
                return SymbolInfo(
                    symbol=symbol,
                    available=True,
                    filepath=meta_filepath,
                    start_date=str(meta.get("start_date", "")),
                    end_date=str(meta.get("end_date", "")),
                    total_rows=int(meta.get("total_rows", 0) or 0),  # type: ignore[call-overload]  # SQLite dict
                )

        data_dir = self._get_data_dir()
        filename_template = self._get_filename_template()

        provider = self._get_default_provider()
        filename = filename_template.format(symbol=symbol, provider=provider, interval="1m")
        filepath = Path(data_dir) / filename

        if filepath.exists():
            df = self._load_csv_with_validation(filepath)
            if df is not None:
                return SymbolInfo(
                    symbol=symbol,
                    available=True,
                    filepath=str(filepath),
                    start_date=str(df["datetime"].min())[:10] if not df.empty else None,
                    end_date=str(df["datetime"].max())[:10] if not df.empty else None,
                    total_rows=len(df),
                )

        logger.warning(f"品种 {symbol} 的数据文件不存在: {filepath}")
        return SymbolInfo(
            symbol=symbol,
            available=False,
            error="数据文件不存在",
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
            df["datetime"] = pd.to_datetime(df["datetime"])
            validated_df = KlineSchema.validate(df)
            return validated_df
        except pa.errors.SchemaError as e:
            logger.error(f"数据验证失败 [{filepath}]: {e}")
            return None
        except Exception as e:
            logger.exception(f"加载CSV失败 [{filepath}]: {e}")
            return None

    def load_kline(
        self,
        symbols: list[str],
        start_date: str | None = None,
        end_date: str | None = None,
        interval: str | None = None,
        provider: str | None = None,
    ) -> list[tuple[str, KlineDataFrame, str]]:
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
            cache_key = f"{symbol}_{interval}"

            if cache_key in self._data_cache:
                logger.debug(f"从缓存加载数据: {symbol}")
                results.append((symbol, self._data_cache[cache_key], data_src))
                continue

            logger.debug(f"加载K线数据: {symbol} data_src={data_src}")

            df = pd.read_csv(data_src)
            df["datetime"] = pd.to_datetime(df["datetime"])

            if start_date:
                df = df[df["datetime"] >= pd.Timestamp(start_date)]
            if end_date:
                df = df[df["datetime"] <= pd.Timestamp(end_date)]

            df = cast(KlineDataFrame, df)
            self._data_cache[cache_key] = df
            logger.debug(f"加载K线数据: {symbol}, 共 {len(df)} 条")
            results.append((symbol, df, data_src))

        return results

    def _resolve_data_src(self, symbol: str, interval: str, candidates: list[str]) -> str:
        """查 ExportMetadata 获取指定品种的数据源路径

        Raises:
            FileNotFoundError: 查不到注册记录或文件缺失
        """
        for p in candidates:
            meta = self.store.get_metadata(symbol, p, interval)
            if meta:
                fp = meta["filepath"]
                if not isinstance(fp, str):
                    continue
                if not Path(fp).exists():
                    raise FileNotFoundError(f"数据源记录存在但文件缺失: {symbol} provider={p} filepath={fp}")
                return fp
        raise FileNotFoundError(f"ExportMetadata 中找不到 {symbol} (interval={interval}, candidates={candidates})")

    # ── 回测记录 ────────────────────────────────────────────

    def insert_backtest(
        self,
        result: BacktestResult,
        run_id: int | None = None,
        data_src: str | None = None,
    ) -> int:
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
        status: str = "success",
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

    def validate_consistency(self, backtest_id: int) -> list[str]:
        """验证回测记录与交易明细之间的一致性

        检查项：
        1. win_trades + loss_trades 是否等于 total_trades
        2. backtest_trades 表的实际记录数是否等于 total_trades
        3. 如果 total_trades > 0，win_trades/loss_trades 不能同时为 None
        4. (2026-06-06新增) profit_days + loss_days ≈ total_days
        5. (2026-06-06新增) total_commission ≈ sum(trade.commission)

        调试沉淀(2026-06-04):
        - 项 2 即为本次 debug 发现的 total_trade_count vs total_trades 键名问题

        Args:
            backtest_id: 回测记录 ID

        Returns:
            错误信息列表，空列表表示验证通过
        """
        bt = self.get_backtest(backtest_id)
        if bt is None:
            return [f"回测记录 {backtest_id} 不存在"]

        trades = self.query_trades(backtest_id)
        trade_count = len(trades)

        # 2026-06-06新增: 聚合逐笔手续费用于一致性校验
        trade_commission_sum = (
            sum(float(cast(float | int, _get_attr(t, "commission", 0))) for t in trades) if trades else 0.0
        )

        return validate_backtest_consistency(
            total_trades=bt.total_trades,
            win_trades=bt.win_trades,
            loss_trades=bt.loss_trades,
            trade_count=trade_count,
            backtest_id=backtest_id,
            # 2026-06-06 新增校验参数
            total_days=cast(int | None, _get_attr(bt, "total_days")),
            profit_days=cast(int | None, _get_attr(bt, "profit_days")),
            loss_days=cast(int | None, _get_attr(bt, "loss_days")),
            total_commission=cast(float | None, _get_attr(bt, "total_commission")),
            trade_commission_sum=trade_commission_sum,
        )

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
        """获取每品种最优回测记录

        委托给 data.report_queries，不再经过 DataStore。
        """
        from .report_queries import get_run_summary as _query

        self._init_store()
        return _query(run_id)

    def get_backtests_for_run(self, run_id: int) -> list[dict[str, object]]:
        """获取某 run 下所有回测记录（含参数和日线数据）

        委托给 data.report_queries，不再经过 DataStore。
        """
        from .report_queries import get_backtests_for_run as _query

        return _query(self.store, run_id)

    def get_equity_data(self, backtest_id: int) -> dict[str, object] | None:
        """获取指定回测记录的资金曲线数据

        委托给 data.report_queries，不再经过 DataStore。
        """
        from .report_queries import get_equity_data as _query

        return _query(self.store, backtest_id)

    def get_optuna_data(self, run_id: int) -> dict[str, object] | None:
        """获取 Optuna 优化数据

        委托给 data.optuna_query，不再经过 DataStore。
        数据库连接由调用方（DataManager）确保已初始化。
        """
        from .optuna_query import get_optuna_data as _query

        return _query(run_id)

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

    def __enter__(self) -> DataManager:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        self.close()

    # ── 日志 sink 管理（用于批量回测时临时重定向日志）────────────────────────

    def get_log_sink_ids(self) -> list[int]:
        """获取当前存储的日志 sink ID 列表"""
        return getattr(self, "_sink_ids", [])

    def add_log_sink_id(self, sink_id: int) -> None:
        """添加一个日志 sink ID"""
        sink_ids = self.get_log_sink_ids()
        sink_ids.append(sink_id)
        # pyright: ignore[reportAttributeAccess]
        object.__setattr__(self, "_sink_ids", sink_ids)
