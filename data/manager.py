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

import logging
import re
from typing import Optional, List, Dict, Any
import pandas as pd
from pathlib import Path

import pandera.pandas as pa
from pandera.typing import DataFrame

from .store import DataStore
from .models import (
    KlineSchema,
    TradeRecordSchema,
    BacktestResultSchema,
    BacktestRecord,
    TradeRecord,
    SymbolInfo,
    DataSummary,
)
from common.constants import (
    DEFAULT_EXPORT_DIR,
    DEFAULT_KLINE_PERIOD,
    KLINE_INTERVAL_1MIN,
)

logger = logging.getLogger(__name__)


class DataManager:
    """数据管理器 - 统一数据访问入口
    
    提供数据加载、保存、查询等高层接口，对外隐藏数据库实现细节。
    所有 DataFrame 数据都经过 Pandera Schema 验证。
    """
    
    def __init__(self, config_manager=None):
        """
        Args:
            config_manager: ConfigManager实例（可选）
        """
        self._config = config_manager
        self._store = None
        self._data_cache = {}
    
    def _init_store(self):
        """延迟初始化存储层"""
        if self._store is None:
            if self._config:
                db_path = self._config.get_data_config().get('db_path', 'data/quant.sqlite')
            else:
                db_path = 'data/quant.sqlite'
            self._store = DataStore(db_path)
    
    @property
    def store(self):
        """获取存储层实例（延迟初始化）"""
        self._init_store()
        return self._store
    
    # ── 元数据查询 ─────────────────────────────────────────
    
    def get_all_symbols(self) -> List[str]:
        """获取所有可用的品种代码列表
        
        Returns:
            品种代码列表，按字母排序
        """
        data_dir = DEFAULT_EXPORT_DIR
        if self._config:
            data_dir = self._config.get_backtest_config().get('data_dir', DEFAULT_EXPORT_DIR)
        
        files = list(Path(data_dir).glob('*_1m.csv'))
        symbols = [f.stem.replace('_1m', '') for f in files]
        return sorted(symbols)
    
    def search_symbols(self, pattern: str) -> List[str]:
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
            return SymbolInfo(
                symbol=symbol,
                available=True,
                filepath=meta.get('filepath'),
                start_date=meta.get('start_date'),
                end_date=meta.get('end_date'),
                total_rows=meta.get('total_rows'),
            )
        
        data_dir = DEFAULT_EXPORT_DIR
        if self._config:
            data_dir = self._config.get_backtest_config().get('data_dir', DEFAULT_EXPORT_DIR)
        
        filepath = Path(data_dir) / f"{symbol}_1m.csv"
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
    
    def _load_csv_with_validation(self, filepath: Path) -> Optional[DataFrame[KlineSchema]]:
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
    def load_kline(self, symbol: str, start_date=None, end_date=None, 
                   interval: str = KLINE_INTERVAL_1MIN) -> DataFrame[KlineSchema]:
        """加载K线数据，直接返回经过 Pandera 验证的 DataFrame
        
        Args:
            symbol: 品种代码（如 'DCE.m2509'）
            start_date: 开始日期（可选，格式 'YYYY-MM-DD'）
            end_date: 结束日期（可选，格式 'YYYY-MM-DD'）
            interval: K线周期（默认1分钟）
        
        Returns:
            DataFrame[KlineSchema]: 经过验证的K线数据
        """
        cache_key = f"{symbol}_{interval}_{start_date}_{end_date}"
        if cache_key in self._data_cache:
            logger.debug(f"从缓存加载数据: {symbol}")
            return self._data_cache[cache_key]
        
        data_dir = DEFAULT_EXPORT_DIR
        if self._config:
            data_dir = self._config.get_backtest_config().get('data_dir', DEFAULT_EXPORT_DIR)
        
        filename = f"{symbol}_{interval}.csv"
        filepath = Path(data_dir) / filename
        
        if not filepath.exists():
            logger.error(f"数据文件不存在: {filepath}")
            raise FileNotFoundError(f"数据文件不存在: {filepath}")
        
        df = pd.read_csv(filepath)
        df['datetime'] = pd.to_datetime(df['datetime'])
        
        if start_date:
            df = df[df['datetime'] >= pd.Timestamp(start_date)]
        if end_date:
            df = df[df['datetime'] <= pd.Timestamp(end_date)]
        
        self._data_cache[cache_key] = df
        logger.info(f"加载K线数据: {symbol}, 共 {len(df)} 条")
        
        return df
    
    def load_kline_safe(self, symbol: str, start_date=None, end_date=None, 
                        interval: str = KLINE_INTERVAL_1MIN) -> Optional[DataFrame[KlineSchema]]:
        """加载K线数据，失败返回None（不抛异常）"""
        try:
            return self.load_kline(symbol, start_date, end_date, interval)
        except Exception as e:
            logger.error(f"加载K线数据失败: {e}")
            return None
    
    # ── 回测记录 ────────────────────────────────────────────
    
    def save_backtest(self, record: BacktestRecord) -> int:
        """保存回测记录
        
        Args:
            record: BacktestRecord实例
        
        Returns:
            记录ID
        """
        return self.store.save_backtest(record)
    
    def insert_backtest(self, symbol: str, strategy: str, status: str,
                        error_message: Optional[str], statistics: dict,
                        engine_config: dict, params_json: Optional[str],
                        data_start_date: Optional[str], data_end_date: Optional[str]) -> int:
        """插入完整的回测记录"""
        return self.store.insert_backtest_detailed(
            symbol=symbol,
            strategy=strategy,
            status=status,
            error_message=error_message,
            statistics=statistics,
            engine_config=engine_config,
            params_json=params_json,
            data_start_date=data_start_date,
            data_end_date=data_end_date,
        )
    
    def insert_backtest_trades(self, backtest_id: int, trades: List[Dict]) -> int:
        """批量插入交易明细"""
        return self.store.insert_backtest_trades(backtest_id, trades)
    
    def query_backtests(
        self,
        symbol: Optional[str] = None,
        strategy: Optional[str] = None,
        status: str = 'success',
        limit: int = 50,
    ) -> List[BacktestRecord]:
        """查询回测记录列表"""
        return self.store.query_backtests(symbol, strategy, status, limit)
    
    def get_backtest(self, backtest_id: int) -> Optional[BacktestRecord]:
        """查询单条回测记录"""
        return self.store.get_backtest(backtest_id)
    
    def query_trades(self, backtest_id: int) -> List[TradeRecord]:
        """查询交易明细"""
        return self.store.query_trades(backtest_id)
    
    # ── 资源管理 ────────────────────────────────────────────
    
    def clear_cache(self):
        """清除数据缓存"""
        self._data_cache.clear()
        logger.info("数据缓存已清除")
    
    def close(self):
        """关闭数据库连接"""
        if self._store:
            self._store.close()
            logger.info("数据库连接已关闭")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()