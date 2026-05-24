"""SQLite 数据库 - 元数据管理与操作日志"""

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
