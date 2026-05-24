"""SQLite 数据库 — peewee ORM 适配层 (强类型)

对外暴露 Database (CRUD 入口) 和 DBLogHandler (logging 桥接) 两个类，
底层通过 data.models 中的 peewee ORM 模型操作四张表。

所有返回类型使用 TypedDict 精确描述，消除 Any 残留。
"""

from __future__ import annotations

import logging
from pathlib import Path
from datetime import datetime

import peewee as pw

from data.models import (
    database_proxy,
    ExportMetadata,
    OperationLog,
    Backtest,
    BacktestTrade,
    ExportMetadataDict,
    OperationLogDict,
    BacktestDict,
    BacktestTradeDict,
    BacktestStatsDict,
    EngineConfigDict,
    VnpyDailyResultDict,
    VnpyTradeRecordDict,
)

# ── 日志自动清理配置 ──────────────────────────────────────────
# 公开常量，供 tests/test_database.py 通过 monkeypatch 调整阈值
_MAX_OPERATION_LOG_ROWS: int = 50_000
_PRUNE_CHECK_INTERVAL: int = 100


class Database:
    """SQLite 数据库管理 (peewee ORM 适配)"""

    def __init__(self, db_path: str) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path: str = db_path

        # 如果已有绑定则先关闭，防止连接泄漏 (正常运行中不会发生，但防御多实例场景)
        if database_proxy.obj is not None:
            database_proxy.close()

        self._db = pw.SqliteDatabase(db_path, pragmas={
            'journal_mode': 'wal',
            'foreign_keys': 1,
        })
        database_proxy.initialize(self._db)
        self._insert_count: int = 0
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

    def log(self, command: str, message: str, symbol: str | None = None,
            status: str = "INFO") -> None:
        """写入一条操作日志记录"""
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
            total: int = OperationLog.select().count()  # type: ignore[assignment]
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

            deleted: int = (
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

    def get_logs(self, limit: int = 100) -> list[OperationLogDict]:
        """查询最近的操作日志"""
        return list(
            OperationLog
            .select()
            .order_by(OperationLog.id.desc())
            .limit(limit)
            .dicts()
        )  # type: ignore[return-value]

    # ── 导出元数据 ────────────────────────────────────────────

    def get_metadata(self, symbol: str) -> ExportMetadataDict | None:
        """查询指定品种的最新导出元数据"""
        row = (
            ExportMetadata
            .select()
            .where(ExportMetadata.symbol == symbol)
            .order_by(ExportMetadata.id.desc())
            .limit(1)
            .dicts()
        )
        return next(iter(row), None)  # type: ignore[return-value]

    def upsert_metadata(self, symbol: str, filepath: str, start_date: str,
                        end_date: str, min_dt: str, max_dt: str,
                        total_rows: int) -> None:
        """插入或更新导出元数据"""
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
        error_message: str | None,
        statistics: BacktestStatsDict,
        engine_config: EngineConfigDict,
        params_json: str | None,
        data_start_date: str | None,
        data_end_date: str | None,
    ) -> int:
        """写入一条回测主记录，返回自增 id

        业务逻辑: 将 vnpy calculate_statistics() 返回的字典平铺写表，
        total_return / win_rate 由公式计算而非直接取值。
        """
        now = datetime.now().isoformat()

        total_trades: int = statistics.get('total_trades', 0) or 0
        initial_capital: float = float(engine_config.get('initial_capital', 100000.0))
        end_balance: float = float(statistics.get('end_balance', initial_capital))
        total_return: float = (
            (end_balance - initial_capital) / initial_capital
        ) if initial_capital > 0 and total_trades > 0 else 0.0
        win_rate: float = (
            statistics.get('win_trades', 0) / max(total_trades, 1)
        ) if total_trades > 0 else 0.0

        bt = Backtest.create(
            symbol=symbol,
            strategy=strategy,
            status=status,
            error_message=error_message,
            data_start_date=data_start_date,
            data_end_date=data_end_date,
            start_date=str(statistics.get('start_date', '')),
            end_date=str(statistics.get('end_date', '')),
            total_days=statistics.get('total_days'),
            initial_capital=initial_capital,
            commission_rate=engine_config.get('commission_rate'),
            slippage=engine_config.get('slippage'),
            price_tick=engine_config.get('price_tick'),
            contract_size=engine_config.get('contract_size'),
            kline_interval=engine_config.get('kline_interval'),
            params_json=params_json,
            end_balance=end_balance,
            total_return=total_return,
            annual_return=statistics.get('annual_return'),
            total_trades=total_trades,
            win_trades=statistics.get('win_trades'),
            loss_trades=statistics.get('loss_trades'),
            win_rate=win_rate,
            max_consecutive_win=statistics.get('max_consecutive_win'),
            max_consecutive_loss=statistics.get('max_consecutive_loss'),
            average_win=statistics.get('average_win'),
            average_loss=statistics.get('average_loss'),
            win_loss_ratio=statistics.get('win_loss_ratio'),
            sharpe_ratio=statistics.get('sharpe_ratio'),
            max_drawdown=statistics.get('max_drawdown'),
            max_drawdown_duration=statistics.get('max_ddpercent_duration'),
            daily_std=statistics.get('daily_std'),
            return_drawdown_ratio=statistics.get('return_drawdown_ratio'),
            created_at=now,
            updated_at=now,
        )
        return bt.id  # type: ignore[return-value]

    def insert_backtest_trades(
        self,
        backtest_id: int,
        daily_results: list[VnpyDailyResultDict],
    ) -> int:
        """批量写入交易明细

        Args:
            backtest_id: 关联的 backtests.id
            daily_results: vnpy calculate_result() 的 to_dict('records') 输出

        Returns:
            写入的交易记录数
        """
        now = datetime.now().isoformat()
        rows: list[dict[str, object]] = []

        for day in daily_results:
            if not isinstance(day, dict):
                continue
            trade_day: str = str(day.get('datetime', ''))[:10]
            trades: list[VnpyTradeRecordDict] = day.get('trades', [])
            for trade in trades:
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
            BacktestTrade.insert_many(rows).execute()  # type: ignore[arg-type]
        return len(rows)

    # ── 回测结果查询 ──────────────────────────────────────────

    def get_backtest(self, backtest_id: int) -> BacktestDict | None:
        """按 ID 查询单条回测记录"""
        query = Backtest.select().where(Backtest.id == backtest_id).dicts()
        return next(iter(query), None)  # type: ignore[return-value]

    def get_backtests(
        self,
        symbol: str | None = None,
        strategy: str | None = None,
        status: str = 'success',
        limit: int = 50,
    ) -> list[BacktestDict]:
        """按条件查询回测记录列表"""
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
        )  # type: ignore[return-value]

    def get_latest_backtests(self, limit: int = 10) -> list[BacktestDict]:
        """查询最近的回测记录"""
        return self.get_backtests(limit=limit)

    def get_backtest_trades(self, backtest_id: int) -> list[BacktestTradeDict]:
        """查询指定回测的所有交易明细"""
        return list(
            BacktestTrade
            .select()
            .where(BacktestTrade.backtest_id == backtest_id)
            .order_by(BacktestTrade.datetime.asc())
            .dicts()
        )  # type: ignore[return-value]

    def get_trades_by_symbol(
        self,
        symbol: str,
        limit: int = 200,
    ) -> list[BacktestTradeDict]:
        """按品种查询交易明细"""
        return list(
            BacktestTrade
            .select()
            .where(BacktestTrade.symbol == symbol)
            .order_by(BacktestTrade.datetime.desc())
            .limit(limit)
            .dicts()
        )  # type: ignore[return-value]


# ── DBLogHandler ──────────────────────────────────────────────

class DBLogHandler(logging.Handler):
    """将 Python logging 记录写入 operation_logs 表"""

    def __init__(self, db: Database, command: str, symbol: str | None = None) -> None:
        super().__init__()
        self.db: Database = db
        self.command: str = command
        self.symbol: str | None = symbol

    def emit(self, record: logging.LogRecord) -> None:
        status_map: dict[int, str] = {
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
