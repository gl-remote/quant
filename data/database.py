"""SQLite 数据库 - 元数据管理与操作日志"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any


_SCHEMA = """
CREATE TABLE IF NOT EXISTS export_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    filepath TEXT NOT NULL,
    start_date TEXT,
    end_date TEXT,
    min_dt TEXT,
    max_dt TEXT,
    total_rows INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS operation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    command TEXT NOT NULL,
    symbol TEXT,
    message TEXT,
    status TEXT DEFAULT 'INFO',
    created_at TEXT NOT NULL
);
"""


class Database:
    """SQLite 数据库管理"""

    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
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
