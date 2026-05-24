"""SQLite 数据库 - 元数据管理、操作日志与回测结果持久化"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any


# 操作日志自动清理阈值：超过此数量时自动删除最旧的一半记录
_MAX_OPERATION_LOG_ROWS = 50_000
_PRUNE_CHECK_INTERVAL = 100  # 每 N 次插入检查一次是否需要清理


_SCHEMA = """
-- ============================================================
-- export_metadata: CSV 数据导出元数据
-- 记录每次从天勤拉取并导出的数据文件信息，
-- 用于数据去重合并、时间范围追踪和增量更新
-- ============================================================
CREATE TABLE IF NOT EXISTS export_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 自增主键
    symbol TEXT NOT NULL,                   -- 品种代码 (e.g. DCE.m2509)
    filepath TEXT NOT NULL,                -- CSV 文件绝对路径
    start_date TEXT,                       -- 用户请求的起始日期 YYYY-MM-DD
    end_date TEXT,                         -- 用户请求的结束日期 YYYY-MM-DD
    min_dt TEXT,                           -- CSV 中实际最早时间戳
    max_dt TEXT,                           -- CSV 中实际最晚时间戳
    total_rows INTEGER DEFAULT 0,         -- CSV 总行数
    created_at TEXT NOT NULL,              -- 记录创建时间 ISO8601
    updated_at TEXT NOT NULL               -- 记录最后更新时间 ISO8601
);

-- ============================================================
-- operation_logs: 系统操作日志
-- 记录 export/backtest/live/test 等所有命令的执行历史，
-- 用于操作审计、问题排查和运行回溯
-- 自动清理: 超过 50,000 条时删除最旧记录
-- ============================================================
CREATE TABLE IF NOT EXISTS operation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 自增主键
    command TEXT NOT NULL,                  -- 命令名称 (export/backtest/live/test)
    symbol TEXT,                           -- 相关品种代码 (可选)
    message TEXT,                          -- 日志消息内容
    status TEXT DEFAULT 'INFO',            -- 状态级别 (INFO/SUCCESS/WARNING/ERROR)
    created_at TEXT NOT NULL               -- 日志创建时间 ISO8601
);

-- ============================================================
-- backtests: vn.py 批量回测运行主表
-- 每次 run_full_pipeline 产生一条记录，包含全部统计指标
-- ============================================================
CREATE TABLE IF NOT EXISTS backtests (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    -- ---- 标识 ----
    symbol                  TEXT    NOT NULL,           -- 品种代码 (e.g. DCE.m2509)
    strategy                TEXT    NOT NULL,           -- 策略名称 (e.g. ma)
    status                  TEXT    NOT NULL DEFAULT 'running',  -- running/success/failed
    error_message           TEXT,                       -- 失败时的异常信息
    -- ---- 数据范围 ----
    data_start_date         TEXT,                       -- CSV 数据最早日期
    data_end_date           TEXT,                       -- CSV 数据最晚日期
    start_date              TEXT,                       -- 回算后实际回测起始日期
    end_date                TEXT,                       -- 回算后实际回测结束日期
    total_days              INTEGER,                    -- 实际交易日数
    -- ---- 引擎参数 (可复现) ----
    initial_capital         REAL    NOT NULL,           -- 初始资金
    commission_rate         REAL,                       -- 手续费率 (比值)
    slippage                REAL,                       -- 滑点
    price_tick              REAL,                       -- 最小变动价位
    contract_size           INTEGER,                    -- 合约乘数
    kline_interval          TEXT,                       -- K 线周期 (1m/5m/1h/d)
    params_json             TEXT,                       -- 策略参数快照 (JSON)
    -- ---- 资金 ----
    end_balance             REAL,                       -- 最终权益
    total_return            REAL,                       -- 总收益率 (比值)
    annual_return           REAL,                       -- 年化收益率 (比值)
    -- ---- 交易统计 ----
    total_trades            INTEGER,                    -- 总交易次数
    win_trades              INTEGER,                    -- 盈利交易次数
    loss_trades             INTEGER,                    -- 亏损交易次数
    win_rate                REAL,                       -- 胜率 (比值)
    max_consecutive_win     INTEGER,                    -- 最大连续盈利次数
    max_consecutive_loss    INTEGER,                    -- 最大连续亏损次数
    average_win             REAL,                       -- 平均盈利金额
    average_loss            REAL,                       -- 平均亏损金额
    win_loss_ratio          REAL,                       -- 盈亏比
    -- ---- 风险 ----
    sharpe_ratio            REAL,                       -- 夏普比率
    max_drawdown            REAL,                       -- 最大回撤 (比值)
    max_drawdown_duration   INTEGER,                    -- 最大回撤持续天数
    daily_std               REAL,                       -- 日收益率标准差
    return_drawdown_ratio   REAL,                       -- 收益回撤比
    -- ---- 时间戳 ----
    created_at              TEXT    NOT NULL,           -- ISO8601
    updated_at              TEXT    NOT NULL            -- ISO8601
);

CREATE INDEX IF NOT EXISTS idx_backtests_symbol ON backtests(symbol);
CREATE INDEX IF NOT EXISTS idx_backtests_strategy ON backtests(strategy);
CREATE INDEX IF NOT EXISTS idx_backtests_created_at ON backtests(created_at);
CREATE INDEX IF NOT EXISTS idx_backtests_symbol_strategy ON backtests(symbol, strategy);

-- ============================================================
-- backtest_trades: 回测交易明细
-- 每笔成交一条，与 backtests 为一对多关系
-- 数据来源: vnpy daily_results[day]['trades'] 列表
-- ============================================================
CREATE TABLE IF NOT EXISTS backtest_trades (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    backtest_id             INTEGER NOT NULL,          -- 关联 backtests.id
    symbol                  TEXT    NOT NULL,           -- 标的名称 (e.g. m2509.DCE)
    -- ---- 交易信息 ----
    datetime                TEXT    NOT NULL,           -- 成交时间 ISO8601
    direction               TEXT    NOT NULL,           -- 方向: long / short
    offset                  TEXT    NOT NULL DEFAULT 'open',  -- 开平: open / close
    price                   REAL    NOT NULL,           -- 成交价格
    volume                  INTEGER NOT NULL,           -- 成交手数
    trade_day               TEXT,                       -- 所属交易日 YYYY-MM-DD (冗余)
    -- ---- 时间戳 ----
    created_at              TEXT    NOT NULL,
    updated_at              TEXT    NOT NULL,

    FOREIGN KEY (backtest_id) REFERENCES backtests(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_backtest_trades_backtest_id ON backtest_trades(backtest_id);
CREATE INDEX IF NOT EXISTS idx_backtest_trades_symbol ON backtest_trades(symbol);
CREATE INDEX IF NOT EXISTS idx_backtest_trades_datetime ON backtest_trades(datetime);
CREATE INDEX IF NOT EXISTS idx_backtest_trades_trade_day ON backtest_trades(trade_day);
"""


class Database:
    """SQLite 数据库管理"""

    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._insert_count = 0  # 日志写入计数器，用于周期性清理检查
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            conn.commit()

    # ---- 操作日志 ----
    def log(self, command: str, message: str, symbol: Optional[str] = None,
            status: str = "INFO") -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO operation_logs (command, symbol, message, status, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (command, symbol, message, status, datetime.now().isoformat()))
            conn.commit()

        self._insert_count += 1
        if self._insert_count % _PRUNE_CHECK_INTERVAL == 0:
            self._prune_old_logs()

    def _prune_old_logs(self) -> int:
        """自动清理过旧日志，保留最近 _MAX_OPERATION_LOG_ROWS 条

        Returns:
            删除的记录数
        """
        try:
            with self._connect() as conn:
                row = conn.execute("SELECT COUNT(*) FROM operation_logs").fetchone()
                total = row[0] if row else 0
                if total <= _MAX_OPERATION_LOG_ROWS:
                    return 0

                excess = total - (_MAX_OPERATION_LOG_ROWS // 2)
                conn.execute(
                    "DELETE FROM operation_logs WHERE id IN "
                    "(SELECT id FROM operation_logs ORDER BY id ASC LIMIT ?)",
                    (excess,))
                conn.commit()
                deleted = conn.total_changes
                if deleted > 0:
                    logging.getLogger(__name__).info(
                        f"操作日志自动清理: 删除 {deleted} 条旧记录，"
                        f"保留最近 {_MAX_OPERATION_LOG_ROWS // 2} 条")
                return deleted
        except Exception as e:
            logging.getLogger(__name__).warning(f"操作日志清理失败: {e}")
            return 0

    def get_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, command, symbol, message, status, created_at "
                "FROM operation_logs ORDER BY id DESC LIMIT ?",
                (limit,)).fetchall()
        return [dict(zip(['id', 'command', 'symbol', 'message', 'status', 'created_at'], r))
                for r in rows]

    # ---- 导出元数据 ----
    def get_metadata(self, symbol: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, symbol, filepath, start_date, end_date, "
                "min_dt, max_dt, total_rows, created_at, updated_at "
                "FROM export_metadata WHERE symbol=? ORDER BY id DESC LIMIT 1",
                (symbol,)).fetchone()
        if not row:
            return None
        return dict(zip(
            ['id', 'symbol', 'filepath', 'start_date', 'end_date',
             'min_dt', 'max_dt', 'total_rows', 'created_at', 'updated_at'], row))

    def upsert_metadata(self, symbol: str, filepath: str, start_date: str,
                        end_date: str, min_dt: str, max_dt: str, total_rows: int) -> None:
        now = datetime.now().isoformat()
        existing = self.get_metadata(symbol)
        with self._connect() as conn:
            if existing:
                conn.execute(
                    "UPDATE export_metadata SET filepath=?, start_date=?, end_date=?, "
                    "min_dt=?, max_dt=?, total_rows=?, updated_at=? WHERE id=?",
                    (filepath, start_date, end_date, min_dt, max_dt, total_rows, now,
                     existing['id']))
            else:
                conn.execute(
                    "INSERT INTO export_metadata (symbol, filepath, start_date, end_date, "
                    "min_dt, max_dt, total_rows, created_at, updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (symbol, filepath, start_date, end_date, min_dt, max_dt, total_rows,
                     now, now))
            conn.commit()


    # ---- 回测结果持久化 ----

    _BACKTEST_COLS = [
        'symbol', 'strategy', 'status', 'error_message',
        'data_start_date', 'data_end_date', 'start_date', 'end_date', 'total_days',
        'initial_capital', 'commission_rate', 'slippage',
        'price_tick', 'contract_size', 'kline_interval', 'params_json',
        'end_balance', 'total_return', 'annual_return',
        'total_trades', 'win_trades', 'loss_trades', 'win_rate',
        'max_consecutive_win', 'max_consecutive_loss',
        'average_win', 'average_loss', 'win_loss_ratio',
        'sharpe_ratio', 'max_drawdown', 'max_drawdown_duration',
        'daily_std', 'return_drawdown_ratio',
        'created_at', 'updated_at',
    ]

    _BACKTEST_TRADE_COLS = [
        'backtest_id', 'symbol', 'datetime', 'direction', 'offset',
        'price', 'volume', 'trade_day', 'created_at', 'updated_at',
    ]

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

        将 vnpy calculate_statistics() 返回的统计字典平铺写入 backtests 表。
        status 为 'failed' 时 statistics 和 engine_config 可为空字典。
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

        values = {
            'symbol': symbol,
            'strategy': strategy,
            'status': status,
            'error_message': error_message,
            'data_start_date': data_start_date,
            'data_end_date': data_end_date,
            'start_date': str(stats.get('start_date', '')),
            'end_date': str(stats.get('end_date', '')),
            'total_days': stats.get('total_days'),
            'initial_capital': initial_capital,
            'commission_rate': cfg.get('commission_rate'),
            'slippage': cfg.get('slippage'),
            'price_tick': cfg.get('price_tick'),
            'contract_size': cfg.get('contract_size'),
            'kline_interval': cfg.get('kline_interval'),
            'params_json': params_json,
            'end_balance': end_balance,
            'total_return': total_return,
            'annual_return': stats.get('annual_return'),
            'total_trades': total_trades,
            'win_trades': stats.get('win_trades'),
            'loss_trades': stats.get('loss_trades'),
            'win_rate': win_rate,
            'max_consecutive_win': stats.get('max_consecutive_win'),
            'max_consecutive_loss': stats.get('max_consecutive_loss'),
            'average_win': stats.get('average_win'),
            'average_loss': stats.get('average_loss'),
            'win_loss_ratio': stats.get('win_loss_ratio'),
            'sharpe_ratio': stats.get('sharpe_ratio'),
            'max_drawdown': stats.get('max_drawdown'),
            'max_drawdown_duration': stats.get('max_ddpercent_duration'),
            'daily_std': stats.get('daily_std'),
            'return_drawdown_ratio': stats.get('return_drawdown_ratio'),
            'created_at': now,
            'updated_at': now,
        }

        cols = [c for c in self._BACKTEST_COLS if c in values]
        placeholders = ','.join(['?' for _ in cols])
        col_names = ','.join(cols)

        with self._connect() as conn:
            cursor = conn.execute(
                f"INSERT INTO backtests ({col_names}) VALUES ({placeholders})",
                tuple(values[c] for c in cols))
            conn.commit()
            return cursor.lastrowid

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
        rows: List[tuple] = []

        for day in daily_results:
            if not isinstance(day, dict):
                continue
            trade_day = str(day.get('datetime', ''))[:10]
            for trade in day.get('trades', []):
                # vnpy TradeData 是对象，转换为 dict 后统一取值
                if isinstance(trade, dict):
                    vt_sym = str(trade.get('vt_symbol', ''))
                    dt = str(trade.get('datetime', ''))
                    direction = str(trade.get('direction', '')).lower()
                    offset = str(trade.get('offset', 'open')).lower()
                    price = float(trade.get('price', 0))
                    volume = int(trade.get('volume', 0))
                else:
                    # TradeData 对象 (vnpy dataclass)
                    vt_sym = str(getattr(trade, 'vt_symbol', ''))
                    dt = str(getattr(trade, 'datetime', ''))
                    direction = str(getattr(trade, 'direction', '')).lower()
                    offset = str(getattr(trade, 'offset', 'open')).lower()
                    price = float(getattr(trade, 'price', 0))
                    volume = int(getattr(trade, 'volume', 0))

                if not vt_sym or volume <= 0:
                    continue

                rows.append((
                    backtest_id, vt_sym, dt, direction, offset,
                    price, volume, trade_day, now, now,
                ))

        if not rows:
            return 0

        placeholders = ','.join(['(?,?,?,?,?,?,?,?,?,?)' for _ in rows])
        flat = [v for row in rows for v in row]

        with self._connect() as conn:
            conn.execute(
                f"INSERT INTO backtest_trades "
                f"(backtest_id, symbol, datetime, direction, offset, "
                f"price, volume, trade_day, created_at, updated_at) "
                f"VALUES {placeholders}",
                flat)
            conn.commit()
        return len(rows)

    # ---- 回测结果查询 (供 report 模块使用) ----

    _BACKTEST_QUERY_COLS = [
        'id', 'symbol', 'strategy', 'status', 'error_message',
        'data_start_date', 'data_end_date', 'start_date', 'end_date', 'total_days',
        'initial_capital', 'commission_rate', 'slippage',
        'price_tick', 'contract_size', 'kline_interval', 'params_json',
        'end_balance', 'total_return', 'annual_return',
        'total_trades', 'win_trades', 'loss_trades', 'win_rate',
        'max_consecutive_win', 'max_consecutive_loss',
        'average_win', 'average_loss', 'win_loss_ratio',
        'sharpe_ratio', 'max_drawdown', 'max_drawdown_duration',
        'daily_std', 'return_drawdown_ratio',
        'created_at', 'updated_at',
    ]

    _BACKTEST_TRADE_QUERY_COLS = [
        'id', 'backtest_id', 'symbol', 'datetime', 'direction', 'offset',
        'price', 'volume', 'trade_day', 'created_at', 'updated_at',
    ]

    def get_backtest(self, backtest_id: int) -> Optional[Dict[str, Any]]:
        """查询单条回测记录"""
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT {','.join(self._BACKTEST_QUERY_COLS)} "
                f"FROM backtests WHERE id=?",
                (backtest_id,)).fetchone()
        if not row:
            return None
        return dict(zip(self._BACKTEST_QUERY_COLS, row))

    def get_backtests(
        self,
        symbol: Optional[str] = None,
        strategy: Optional[str] = None,
        status: str = 'success',
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """按条件查询回测记录列表

        Args:
            symbol: 品种代码过滤 (None = 不限)
            strategy: 策略名称过滤 (None = 不限)
            status: 状态过滤，默认只查成功的
            limit: 最大返回条数
        """
        conditions = ['status = ?']
        params: list[Any] = [status]

        if symbol:
            conditions.append('symbol = ?')
            params.append(symbol)
        if strategy:
            conditions.append('strategy = ?')
            params.append(strategy)

        where = ' AND '.join(conditions)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT {','.join(self._BACKTEST_QUERY_COLS)} "
                f"FROM backtests WHERE {where} "
                f"ORDER BY created_at DESC LIMIT ?",
                params + [limit]).fetchall()
        return [dict(zip(self._BACKTEST_QUERY_COLS, r)) for r in rows]

    def get_latest_backtests(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近 N 条成功的回测记录"""
        return self.get_backtests(limit=limit)

    def get_backtest_trades(self, backtest_id: int) -> List[Dict[str, Any]]:
        """查询某次回测的全部交易明细，按时间排序"""
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT {','.join(self._BACKTEST_TRADE_QUERY_COLS)} "
                f"FROM backtest_trades WHERE backtest_id=? "
                f"ORDER BY datetime ASC",
                (backtest_id,)).fetchall()
        return [dict(zip(self._BACKTEST_TRADE_QUERY_COLS, r)) for r in rows]

    def get_trades_by_symbol(
        self,
        symbol: str,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """按品种查询交易明细 (跨回测运行)"""
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT {','.join(self._BACKTEST_TRADE_QUERY_COLS)} "
                f"FROM backtest_trades WHERE symbol=? "
                f"ORDER BY datetime DESC LIMIT ?",
                (symbol, limit)).fetchall()
        return [dict(zip(self._BACKTEST_TRADE_QUERY_COLS, r)) for r in rows]


class DBLogHandler(logging.Handler):
    """将日志写入 operation_logs 表"""

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
            status=status_map.get(record.levelno, 'INFO'))
