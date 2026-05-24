"""SQLite 数据库 — peewee ORM 适配层

对外暴露 Database (CRUD 入口) 和 DBLogHandler (logging 桥接) 两个类，
底层通过 data.models 中的 peewee ORM 模型操作四张表。

公开 API 与旧 raw-SQL 版本完全兼容 — 所有查询方法仍返回 List[Dict]/Optional[Dict]。
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

import peewee as pw

from data.models import (
    database_proxy,
    ExportMetadata,
    OperationLog,
    Backtest,
    BacktestTrade,
)

# ── 日志自动清理配置 ──────────────────────────────────────────
# 公开常量，供 tests/test_database.py 通过 monkeypatch 调整阈值
_MAX_OPERATION_LOG_ROWS = 50_000
_PRUNE_CHECK_INTERVAL = 100


class Database:
    """SQLite 数据库管理 (peewee ORM 适配)"""

    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path

        # 如果已有绑定则先关闭，防止连接泄漏 (正常运行中不会发生，但防御多实例场景)
        if database_proxy.obj is not None:
            database_proxy.close()

        self._db = pw.SqliteDatabase(db_path, pragmas={
            'journal_mode': 'wal',
            'foreign_keys': 1,
        })
        database_proxy.initialize(self._db)
        self._insert_count = 0
        self._init_db()

    # ── 内部 ──────────────────────────────────────────────────

    def _init_db(self) -> None:
        """建表 (safe=True: 已存在则跳过)"""
        with database_proxy:
            database_proxy.create_tables(
                [ExportMetadata, OperationLog, Backtest, BacktestTrade],
                safe=True,
            )

    # ── 操作日志 ──────────────────────────────────────────────

    def log(self, command: str, message: str, symbol: Optional[str] = None,
            status: str = "INFO") -> None:
        OperationLog.create(
            command=command,
            symbol=symbol,
            message=message,
            status=status,
            created_at=datetime.now().isoformat(),
        )

        self._insert_count += 1
        if self._insert_count % _PRUNE_CHECK_INTERVAL == 0:
            self._prune_old_logs()

    def _prune_old_logs(self) -> int:
        """自动清理过旧日志，保留最近 _MAX_OPERATION_LOG_ROWS 条

        Returns:
            删除的记录数
        """
        try:
            total = OperationLog.select().count()
            if total <= _MAX_OPERATION_LOG_ROWS:
                return 0

            keep_count = _MAX_OPERATION_LOG_ROWS // 2
            cutoff_id = (
                OperationLog
                .select(OperationLog.id)
                .order_by(OperationLog.id.desc())
                .offset(keep_count - 1)
                .limit(1)
                .scalar()
            )
            if cutoff_id is None:
                return 0

            deleted = (
                OperationLog
                .delete()
                .where(OperationLog.id < cutoff_id)
                .execute()
            )
            if deleted > 0:
                logging.getLogger(__name__).info(
                    f"操作日志自动清理: 删除 {deleted} 条旧记录，"
                    f"保留最近 {keep_count} 条")
            return deleted
        except Exception as e:
            logging.getLogger(__name__).warning(f"操作日志清理失败: {e}")
            return 0

    def get_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        return list(
            OperationLog
            .select()
            .order_by(OperationLog.id.desc())
            .limit(limit)
            .dicts()
        )

    # ── 导出元数据 ────────────────────────────────────────────

    def get_metadata(self, symbol: str) -> Optional[Dict[str, Any]]:
        row = (
            ExportMetadata
            .select()
            .where(ExportMetadata.symbol == symbol)
            .order_by(ExportMetadata.id.desc())
            .limit(1)
            .dicts()
        )
        return next(iter(row), None)

    def upsert_metadata(self, symbol: str, filepath: str, start_date: str,
                        end_date: str, min_dt: str, max_dt: str,
                        total_rows: int) -> None:
        now = datetime.now().isoformat()
        existing = (
            ExportMetadata
            .select()
            .where(ExportMetadata.symbol == symbol)
            .order_by(ExportMetadata.id.desc())
            .first()
        )
        if existing:
            (ExportMetadata
             .update(
                 filepath=filepath,
                 start_date=start_date,
                 end_date=end_date,
                 min_dt=min_dt,
                 max_dt=max_dt,
                 total_rows=total_rows,
                 updated_at=now,
             )
             .where(ExportMetadata.id == existing.id)
             .execute())
        else:
            ExportMetadata.create(
                symbol=symbol,
                filepath=filepath,
                start_date=start_date,
                end_date=end_date,
                min_dt=min_dt,
                max_dt=max_dt,
                total_rows=total_rows,
                created_at=now,
                updated_at=now,
            )

    # ── 回测结果持久化 ────────────────────────────────────────

    def insert_backtest(
        self,
        symbol: str,
        strategy: str,
        status: str,
        error_message: Optional[str],
        statistics: Dict[str, Any],
        engine_config: Dict[str, Any],
        params_json: Optional[str],
        data_start_date: Optional[str],
        data_end_date: Optional[str],
    ) -> int:
        """写入一条回测主记录，返回自增 id

        业务逻辑: 将 vnpy calculate_statistics() 返回的字典平铺写表，
        total_return / win_rate 由公式计算而非直接取值。
        """
        now = datetime.now().isoformat()
        stats = statistics or {}
        cfg = engine_config or {}

        total_trades = stats.get('total_trades', 0) or 0
        initial_capital = float(cfg.get('initial_capital', 100000.0))
        end_balance = float(stats.get('end_balance', initial_capital))
        total_return = (
            (end_balance - initial_capital) / initial_capital
        ) if initial_capital > 0 and total_trades > 0 else 0.0
        win_rate = (
            stats.get('win_trades', 0) / max(total_trades, 1)
        ) if total_trades > 0 else 0.0

        bt = Backtest.create(
            symbol=symbol,
            strategy=strategy,
            status=status,
            error_message=error_message,
            data_start_date=data_start_date,
            data_end_date=data_end_date,
            start_date=str(stats.get('start_date', '')),
            end_date=str(stats.get('end_date', '')),
            total_days=stats.get('total_days'),
            initial_capital=initial_capital,
            commission_rate=cfg.get('commission_rate'),
            slippage=cfg.get('slippage'),
            price_tick=cfg.get('price_tick'),
            contract_size=cfg.get('contract_size'),
            kline_interval=cfg.get('kline_interval'),
            params_json=params_json,
            end_balance=end_balance,
            total_return=total_return,
            annual_return=stats.get('annual_return'),
            total_trades=total_trades,
            win_trades=stats.get('win_trades'),
            loss_trades=stats.get('loss_trades'),
            win_rate=win_rate,
            max_consecutive_win=stats.get('max_consecutive_win'),
            max_consecutive_loss=stats.get('max_consecutive_loss'),
            average_win=stats.get('average_win'),
            average_loss=stats.get('average_loss'),
            win_loss_ratio=stats.get('win_loss_ratio'),
            sharpe_ratio=stats.get('sharpe_ratio'),
            max_drawdown=stats.get('max_drawdown'),
            max_drawdown_duration=stats.get('max_ddpercent_duration'),
            daily_std=stats.get('daily_std'),
            return_drawdown_ratio=stats.get('return_drawdown_ratio'),
            created_at=now,
            updated_at=now,
        )
        return bt.id

    def insert_backtest_trades(
        self,
        backtest_id: int,
        daily_results: List[Dict[str, Any]],
    ) -> int:
        """批量写入交易明细

        Args:
            backtest_id: 关联的 backtests.id
            daily_results: vnpy calculate_result() 的 to_dict('records') 输出

        Returns:
            写入的交易记录数
        """
        now = datetime.now().isoformat()
        rows: List[Dict[str, Any]] = []

        for day in daily_results:
            if not isinstance(day, dict):
                continue
            trade_day = str(day.get('datetime', ''))[:10]
            for trade in day.get('trades', []):
                if isinstance(trade, dict):
                    vt_sym = str(trade.get('vt_symbol', ''))
                    dt = str(trade.get('datetime', ''))
                    direction = str(trade.get('direction', '')).lower()
                    offset = str(trade.get('offset', 'open')).lower()
                    price = float(trade.get('price', 0))
                    volume = int(trade.get('volume', 0))
                else:
                    vt_sym = str(getattr(trade, 'vt_symbol', ''))
                    dt = str(getattr(trade, 'datetime', ''))
                    direction = str(getattr(trade, 'direction', '')).lower()
                    offset = str(getattr(trade, 'offset', 'open')).lower()
                    price = float(getattr(trade, 'price', 0))
                    volume = int(getattr(trade, 'volume', 0))

                if not vt_sym or volume <= 0:
                    continue

                rows.append({
                    'backtest_id': backtest_id,
                    'symbol': vt_sym,
                    'datetime': dt,
                    'direction': direction,
                    'offset': offset,
                    'price': price,
                    'volume': volume,
                    'trade_day': trade_day,
                    'created_at': now,
                    'updated_at': now,
                })

        if not rows:
            return 0

        # 单事务批量插入 (peewee insert_many 对大列表性能远优于逐条 create)
        with database_proxy.atomic():
            BacktestTrade.insert_many(rows).execute()
        return len(rows)

    # ── 回测结果查询 ──────────────────────────────────────────

    def get_backtest(self, backtest_id: int) -> Optional[Dict[str, Any]]:
        query = Backtest.select().where(Backtest.id == backtest_id).dicts()
        return next(iter(query), None)

    def get_backtests(
        self,
        symbol: Optional[str] = None,
        strategy: Optional[str] = None,
        status: str = 'success',
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        query = Backtest.select().where(Backtest.status == status)

        if symbol:
            query = query.where(Backtest.symbol == symbol)
        if strategy:
            query = query.where(Backtest.strategy == strategy)

        return list(
            query
            .order_by(Backtest.created_at.desc())
            .limit(limit)
            .dicts()
        )

    def get_latest_backtests(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self.get_backtests(limit=limit)

    def get_backtest_trades(self, backtest_id: int) -> List[Dict[str, Any]]:
        return list(
            BacktestTrade
            .select()
            .where(BacktestTrade.backtest_id == backtest_id)
            .order_by(BacktestTrade.datetime.asc())
            .dicts()
        )

    def get_trades_by_symbol(
        self,
        symbol: str,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        return list(
            BacktestTrade
            .select()
            .where(BacktestTrade.symbol == symbol)
            .order_by(BacktestTrade.datetime.desc())
            .limit(limit)
            .dicts()
        )


# ── DBLogHandler ──────────────────────────────────────────────

class DBLogHandler(logging.Handler):
    """将 Python logging 记录写入 operation_logs 表"""

    def __init__(self, db: Database, command: str, symbol: str = None):
        super().__init__()
        self.db = db
        self.command = command
        self.symbol = symbol

    def emit(self, record: logging.LogRecord):
        status_map = {
            logging.ERROR: 'ERROR',
            logging.WARNING: 'WARNING',
            logging.INFO: 'INFO',
            logging.DEBUG: 'INFO',
        }
        self.db.log(
            command=self.command,
            symbol=self.symbol,
            message=self.format(record),
            status=status_map.get(record.levelno, 'INFO'),
        )
