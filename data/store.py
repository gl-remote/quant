# -*- coding: utf-8 -*-
"""内部存储层 - 数据库操作实现（对外隐藏）

提供数据库连接管理和CRUD操作，被DataManager调用，
外部模块不应直接使用此模块。
"""

from __future__ import annotations

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false, reportArgumentType=false
# pyright: reportAttributeAccessIssue=false, reportUnusedCallResult=false
# 注：以上规则抑制是因为 peewee ORM 缺少类型存根，所有方法链、
# 字段描述符访问、`dict[str, object]` 查询返回值都会产生误报。

import logging
from pathlib import Path
from datetime import datetime


from .models import (
    database,
    ExportMetadata,
    OperationLog,
    Backtest,
    BacktestTrade,
    BacktestDaily,
    BacktestRecord,
    TradeRecord,
)
import common.constants as constants
from common.formulas import total_return as calc_total_return, win_rate as calc_win_rate

logger = logging.getLogger(__name__)


def _normalize_max_dd(raw_value: float | None) -> float:
    """将vnpy返回的max_drawdown归一化为比值"""
    if raw_value is None:
        return 0.0
    v = float(raw_value)
    if abs(v) > 1:
        return v / 100.0
    return v


class DataStore:
    """数据存储层 - 管理数据库连接和CRUD操作"""

    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path: str = db_path
        database.init(db_path, pragmas={
            'journal_mode': 'wal',
            'foreign_keys': 1,
        })
        self._insert_count: int = 0
        self._init_tables()

    def _init_tables(self):
        """初始化数据库表"""
        database.create_tables(
            [ExportMetadata, OperationLog, Backtest, BacktestTrade, BacktestDaily],
            safe=True,
        )

    def close(self):
        """关闭数据库连接"""
        if not database.is_closed():
            database.close()

    # ── 日志操作 ────────────────────────────────────────────────────

    def log(self, command: str, message: str,
            symbol: str | None = None, status: str = "INFO") -> None:
        """写入操作日志"""
        OperationLog.create(
            command=command,
            symbol=symbol,
            message=message,
            status=status,
            created_at=datetime.now(),
        )

        self._insert_count += 1
        if self._insert_count % constants.PRUNE_CHECK_INTERVAL == 0:
            self._prune_old_logs()
        total = OperationLog.select().count()
        if total >= constants.MAX_OPERATION_LOG_ROWS:
            self._prune_old_logs()

    def _prune_old_logs(self) -> int:
        """自动清理过旧日志，保留最近 MAX_OPERATION_LOG_ROWS 条"""
        try:
            max_rows = constants.MAX_OPERATION_LOG_ROWS
            total = OperationLog.select().count()
            if total <= max_rows - 1:
                return 0

            cutoff_id = (
                OperationLog
                .select(OperationLog.id)
                .order_by(OperationLog.id.desc())
                .offset(max_rows - 2)
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
                logger.info(f"操作日志自动清理: 删除 {deleted} 条旧记录")
            return deleted
        except Exception as e:
            logger.warning(f"操作日志清理失败: {e}")
            return 0

    def get_logs(self, limit: int = 100) -> list[dict[str, object]]:
        """查询操作日志"""
        rows = list(
            OperationLog
            .select()
            .order_by(OperationLog.id.desc())
            .limit(limit)
            .dicts()
        )
        for row in rows:
            for field in ['created_at', 'updated_at']:
                if row.get(field) is not None:
                    row[field] = str(row[field])
        return rows

    # ── 元数据操作 ──────────────────────────────────────────────────

    def get_metadata(self, symbol: str) -> dict[str, object] | None:
        """查询品种元数据"""
        row = (
            ExportMetadata
            .select()
            .where(ExportMetadata.symbol == symbol)
            .order_by(ExportMetadata.id.desc())
            .limit(1)
            .dicts()
        )
        result = next(iter(row), None)
        if result:
            for field in ['start_date', 'end_date', 'min_dt', 'max_dt', 'created_at', 'updated_at']:
                if result.get(field) is not None:
                    result[field] = str(result[field])
        return result

    def upsert_metadata(self, symbol: str, filepath: str, start_date: str,
                        end_date: str, min_dt: str, max_dt: str,
                        total_rows: int) -> None:
        """插入或更新元数据"""
        now = datetime.now()
        existing = (
            ExportMetadata
            .select()
            .where(ExportMetadata.symbol == symbol)
            .order_by(ExportMetadata.id.desc())
            .first()
        )
        if existing:
            ExportMetadata.update(
                filepath=filepath,
                start_date=start_date,
                end_date=end_date,
                min_dt=min_dt,
                max_dt=max_dt,
                total_rows=total_rows,
                updated_at=now,
            ).where(ExportMetadata.id == existing.id).execute()
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

    # ── 回测记录操作 ────────────────────────────────────────────────

    def insert_backtest_detailed(
        self,
        symbol: str,
        strategy: str,
        status: str,
        error_message: str | None,
        statistics: dict[str, object],
        engine_config: dict[str, object],
        params_json: str | None,
        start_date: str | None,
        end_date: str | None,
        strategy_version: str | None = None,
        git_hash: str | None = None,
    ) -> int:
        """插入完整的回测记录"""
        now = datetime.now()

        total_trades = statistics.get('total_trade_count', statistics.get('total_trades', 0)) or 0
        initial_capital = float(engine_config.get('initial_capital', constants.DEFAULT_INITIAL_CAPITAL))
        end_balance = float(statistics.get('end_balance', initial_capital))
        total_return = calc_total_return(initial_capital, end_balance, total_trades=total_trades)
        # vnpy 使用 profit_days/loss_days（日级别），测试 fixture 用 win_trades/loss_trades
        win_trades_v = statistics.get('profit_days', statistics.get('win_trades', 0))
        loss_trades_v = statistics.get('loss_days', statistics.get('loss_trades', 0))
        win_rate_val = calc_win_rate(win_trades_v, total_trades)

        bt = Backtest.create(
            symbol=symbol,
            strategy=strategy,
            strategy_version=strategy_version,
            git_hash=git_hash,
            status=status,
            error_message=error_message,
            start_date=start_date,
            end_date=end_date,
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
            win_trades=win_trades_v,
            loss_trades=loss_trades_v,
            win_rate=win_rate_val,
            max_consecutive_win=statistics.get('max_consecutive_win'),
            max_consecutive_loss=statistics.get('max_consecutive_loss'),
            avg_win=statistics.get('average_win'),
            avg_loss=statistics.get('average_loss'),
            win_loss_ratio=statistics.get('win_loss_ratio'),
            sharpe_ratio=statistics.get('sharpe_ratio'),
            max_drawdown=_normalize_max_dd(statistics.get('max_drawdown')),
            max_drawdown_duration=statistics.get('max_drawdown_duration',
                                                 statistics.get('max_ddpercent_duration', 0)),
            daily_std=statistics.get('return_std', statistics.get('daily_std')),
            return_drawdown_ratio=statistics.get('return_drawdown_ratio'),
            created_at=now,
            updated_at=now,
        )
        return bt.id

    def insert_backtest_trades(self, backtest_id: int, trades: list[dict[str, object]]) -> int:
        """批量插入交易明细"""
        now = datetime.now()
        rows = []

        for trade in trades:
            rows.append({
                'backtest_id': backtest_id,
                'symbol': str(trade.get('symbol', '')),
                'datetime': trade.get('datetime', ''),
                'direction': str(trade.get('direction', '')).lower(),
                'offset': str(trade.get('offset', 'open')).lower(),
                'open_price': float(trade.get('open_price', trade.get('price', 0))),
                'close_price': float(trade.get('close_price', trade.get('price', 0))),
                'quantity': int(trade.get('quantity', trade.get('volume', 0))),
                'pnl': float(trade.get('pnl', 0)),
                'commission': float(trade.get('commission', 0)),
                'created_at': now,
            })

        if not rows:
            return 0

        with database.atomic():
            BacktestTrade.insert_many(rows).execute()
        return len(rows)

    def query_backtests(
        self,
        symbol: str | None = None,
        strategy: str | None = None,
        status: str = 'success',
        limit: int = 50,
    ) -> list[BacktestRecord]:
        """查询回测记录"""
        query = Backtest.select().where(Backtest.status == status)

        if symbol:
            query = query.where(Backtest.symbol == symbol)
        if strategy:
            query = query.where(Backtest.strategy == strategy)

        results_raw = (
            query
            .order_by(Backtest.created_at.desc())
            .limit(limit)
            .dicts()
        )
        results = list(results_raw)

        records = []
        for row in results:
            row['created_at'] = str(row.get('created_at', ''))
            records.append(BacktestRecord(**row))
        return records

    def get_backtest(self, backtest_id: int) -> BacktestRecord | None:
        """查询单条回测记录"""
        row = Backtest.select().where(Backtest.id == backtest_id).dicts()
        result = next(iter(row), None)
        if result:
            result['created_at'] = str(result.get('created_at', ''))
            return BacktestRecord(**result)
        return None

    def query_trades(self, backtest_id: int) -> list[TradeRecord]:
        """查询交易明细"""
        rows = list(
            BacktestTrade
            .select()
            .where(BacktestTrade.backtest_id == backtest_id)
            .order_by(BacktestTrade.datetime.asc())
            .dicts()
        )

        records = []
        for row in rows:
            # ORM DateTimeField → str 转换，Pydantic TradeRecord 期望 str
            for dt_field in ('datetime', 'created_at'):
                if row.get(dt_field) is not None:
                    row[dt_field] = str(row[dt_field])
            row['backtest_id'] = row.pop('backtest_id') if 'backtest_id' in row else backtest_id
            records.append(TradeRecord(**row))
        return records

    def insert_backtest_daily(self, backtest_id: int, daily_results: list[dict[str, object]]) -> int:
        """批量插入每日资金曲线数据"""
        now = datetime.now()
        rows: list[dict[str, object]] = []
        peak: float = 0.0

        for daily in daily_results:
            # vnpy 字段名是 `date`（非 `datetime`）；calculate_statistics 后含 `balance`
            dt = daily.get('date', daily.get('datetime'))
            if not dt:
                continue
            date_str = str(dt).split(' ')[0] if ' ' in str(dt) else str(dt).split('T')[0]

            net_pnl = float(daily.get('net_pnl', daily.get('daily_return', 0)))
            equity = float(daily.get('balance', daily.get('equity', 0)))
            if equity > peak:
                peak = equity
            drawdown = equity - peak if peak != 0 else 0.0

            rows.append({
                'backtest_id': backtest_id,
                'date': date_str,
                'equity': equity,
                'daily_return': net_pnl,
                'drawdown': drawdown,
                'created_at': now,
            })

        if not rows:
            return 0

        with database.atomic():
            BacktestDaily.insert_many(rows).execute()
        return len(rows)

    def query_daily(self, backtest_id: int) -> list[dict[str, object]]:
        """查询每日资金曲线"""
        rows = list(
            BacktestDaily
            .select()
            .where(BacktestDaily.backtest_id == backtest_id)
            .order_by(BacktestDaily.date.asc())
            .dicts()
        )

        results = []
        for row in rows:
            results.append({
                'date': str(row.get('date', '')),
                'equity': row.get('equity', 0),
                'daily_return': row.get('daily_return', 0),
                'drawdown': row.get('drawdown', 0),
            })
        return results

    def delete_backtest(self, backtest_id: int) -> bool:
        """硬删除回测记录及其关联的交易明细和每日资金曲线

        Args:
            backtest_id: 回测记录 ID

        Returns:
            是否成功删除
        """
        try:
            bt = Backtest.get_or_none(Backtest.id == backtest_id)
            if bt is None:
                logger.warning(f"回测记录不存在 id={backtest_id}")
                return False
            # 先删关联数据，再删主记录 (虽然有 CASCADE，显式删除更安全)
            with database.atomic():
                BacktestDaily.delete().where(
                    BacktestDaily.backtest_id == backtest_id
                ).execute()
                BacktestTrade.delete().where(
                    BacktestTrade.backtest_id == backtest_id
                ).execute()
                bt.delete_instance()
            logger.info(f"已删除回测记录 id={backtest_id} 及其关联数据")
            return True
        except Exception as e:
            logger.error(f"删除回测记录失败 id={backtest_id}: {e}")
            return False
