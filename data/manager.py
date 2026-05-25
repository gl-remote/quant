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
        self._default_config = None
    
    def _get_config(self):
        """获取配置管理器（延迟初始化默认配置）"""
        if self._config:
            return self._config
        if self._default_config is None:
            from config import ConfigManager
            self._default_config = ConfigManager()
        return self._default_config
    
    def _get_data_dir(self):
        """获取数据目录配置"""
        return self._get_config().get_backtest_config().get('data_dir', '.quant_shared_data/csv')
    
    def _get_filename_template(self):
        """获取文件名模板配置"""
        return self._get_config().get_export_config().get('filename_template', '{symbol}.{interval}.csv')
    
    def _get_default_interval(self):
        """获取默认K线周期配置"""
        return self._get_config().get_backtest_config().get('interval', '1m')
    
    def _init_store(self):
        """延迟初始化存储层"""
        if self._store is None:
            db_path = self._get_config().get_data_config().get('db_path', '.quant_shared_data/quant_shared.db')
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
        data_dir = self._get_data_dir()
        filename_template = self._get_filename_template()
        
        # 先扫描所有CSV文件
        csv_dir = Path(data_dir)
        if not csv_dir.exists():
            return []
        
        files = list(csv_dir.glob('*.csv'))
        
        # 从文件名提取品种名
        symbols = set()
        for f in files:
            name = f.stem
            symbol = None
            
            # 先尝试新格式: {symbol}.{interval}
            # 找到最后一个点号的位置，分隔出interval
            last_dot = name.rfind('.')
            if last_dot != -1:
                suffix_part = name[last_dot + 1:]
                # 检查后面的部分是否像常见的interval
                common_intervals = ['1m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w', '1M', '3M', '6M', '1Y']
                if suffix_part in common_intervals:
                    symbol = name[:last_dot]
            
            # 如果新格式没匹配到，尝试旧格式或无后缀格式
            if symbol is None:
                if name.endswith('_qlib'):
                    symbol = name[:-5]
                else:
                    # 直接用文件名作为symbol
                    symbol = name
            
            symbols.add(symbol)
        
        return sorted(list(symbols))
    
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
            meta_filepath = meta.get('filepath')
            if meta_filepath and Path(meta_filepath).exists():
                return SymbolInfo(
                    symbol=symbol,
                    available=True,
                    filepath=meta_filepath,
                    start_date=meta.get('start_date'),
                    end_date=meta.get('end_date'),
                    total_rows=meta.get('total_rows'),
                )
        
        data_dir = self._get_data_dir()
        filename_template = self._get_filename_template()
        
        filename = filename_template.format(symbol=symbol, interval='1m')
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
                   interval: Optional[str] = None) -> DataFrame[KlineSchema]:
        """加载K线数据，直接返回经过 Pandera 验证的 DataFrame
        
        Args:
            symbol: 品种代码（如 'DCE.m2509'）
            start_date: 开始日期（可选，格式 'YYYY-MM-DD'）
            end_date: 结束日期（可选，格式 'YYYY-MM-DD'）
            interval: K线周期（默认从配置读取）
        
        Returns:
            DataFrame[KlineSchema]: 经过验证的K线数据
        """
        if interval is None:
            interval = self._get_default_interval()
        
        cache_key = f"{symbol}_{interval}_{start_date}_{end_date}"
        if cache_key in self._data_cache:
            logger.debug(f"从缓存加载数据: {symbol}")
            return self._data_cache[cache_key]
        
        data_dir = self._get_data_dir()
        filename_template = self._get_filename_template()
        
        filename = filename_template.format(symbol=symbol, interval=interval)
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
                        interval: Optional[str] = None) -> Optional[DataFrame[KlineSchema]]:
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
                        data_start_date: Optional[str], data_end_date: Optional[str],
                        strategy_version: Optional[str] = None,
                        git_hash: Optional[str] = None) -> int:
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
            strategy_version=strategy_version,
            git_hash=git_hash,
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
    
    def insert_backtest_daily(self, backtest_id: int, daily_results: List[Dict]) -> int:
        """批量插入每日资金曲线数据"""
        return self.store.insert_backtest_daily(backtest_id, daily_results)
    
    def query_daily(self, backtest_id: int) -> List[Dict]:
        """查询每日资金曲线"""
        return self.store.query_daily(backtest_id)
    
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