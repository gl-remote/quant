# -*- coding: utf-8 -*-
"""数据库兼容层 - 提供向后兼容的 Database 接口"""

import logging
from typing import Optional, List, Dict
from .store import DataStore

logger = logging.getLogger(__name__)


class Database:
    """向后兼容的 Database 类
    
    内部使用 DataStore 实现，提供与旧接口兼容的 API。
    """
    
    def __init__(self, db_path: str):
        self._store = DataStore(db_path)
    
    def log(self, command: str, message: str, 
            symbol: Optional[str] = None, status: str = "INFO") -> None:
        """写入操作日志"""
        self._store.log(command, message, symbol, status)
    
    def get_logs(self, limit: int = 100) -> List[Dict]:
        """查询操作日志"""
        return self._store.get_logs(limit)
    
    def get_metadata(self, symbol: str) -> Optional[Dict]:
        """查询品种元数据"""
        return self._store.get_metadata(symbol)
    
    def upsert_metadata(self, symbol: str, filepath: str, start_date: str,
                       end_date: str, min_dt: str, max_dt: str,
                       total_rows: int) -> None:
        """插入或更新元数据"""
        self._store.upsert_metadata(symbol, filepath, start_date, end_date, 
                                   min_dt, max_dt, total_rows)
    
    def get_backtest(self, backtest_id: int) -> Optional[Dict]:
        """查询单条回测记录"""
        bt = self._store.get_backtest(backtest_id)
        if bt:
            return bt.to_dict()
        return None
    
    def get_backtests(self, symbol: Optional[str] = None,
                     strategy: Optional[str] = None,
                     status: str = 'success',
                     limit: int = 50) -> List[Dict]:
        """查询回测记录列表"""
        records = self._store.query_backtests(symbol, strategy, status, limit)
        return [r.to_dict() for r in records]
    
    def get_backtest_trades(self, backtest_id: int) -> List[Dict]:
        """查询回测交易明细"""
        trades = self._store.query_trades(backtest_id)
        return [t.to_dict() for t in trades]
    
    def save_backtest(self, record: Dict) -> int:
        """保存回测记录"""
        from .models import BacktestRecord
        bt = BacktestRecord.from_dict(record)
        return self._store.save_backtest(bt)
    
    def insert_backtest(self, **kwargs) -> int:
        """插入回测记录"""
        return self._store.insert_backtest_detailed(**kwargs)
    
    def insert_backtest_trades(self, backtest_id: int, trades: List[Dict]) -> int:
        """批量插入交易明细"""
        return self._store.insert_backtest_trades(backtest_id, trades)
    
    def _prune_old_logs(self) -> int:
        """手动清理旧日志"""
        return self._store._prune_old_logs()
    
    def close(self):
        """关闭数据库连接"""
        self._store.close()


class DBLogHandler(logging.Handler):
    """数据库日志处理器"""
    
    def __init__(self, db: Database, command: str = "", symbol: Optional[str] = None):
        super().__init__()
        self.db = db
        self.command = command
        self.symbol = symbol
    
    def emit(self, record: logging.LogRecord):
        """发送日志到数据库"""
        status = "ERROR" if record.levelno >= logging.ERROR else "INFO"
        self.db.log(self.command, self.format(record), self.symbol, status)


def setup_db_logging(db: Database, command: str = "", symbol: Optional[str] = None):
    """配置全局数据库日志处理器"""
    handler = DBLogHandler(db, command, symbol)
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logging.getLogger().addHandler(handler)
    return handler
