"""数据库 Schema 版本管理 — 极简实现

设计目标（适配「多个 AI 协同改代码」场景）：
1. ORM 模型加了字段时，AI 只需在此文件末尾追加一条迁移记录
2. 启动时自动对比「数据库里的版本号」与「代码里的版本号」，按顺序执行
3. 迁移失败直接 panic，避免静默吞异常导致后续数据错乱
4. 所有迁移集中在一个文件，便于 review 和审计

使用方式（给 AI 看的约定）：
- 修改 data/models.py 中任何 ORM 字段后，必须在此文件 MIGRATIONS 列表末尾追加一条
- 迁移编号单调递增（整数），不要复用编号
- 每个迁移只管一件事：加一个/一组字段，或建一张新表
- SQLite 不支持 DROP COLUMN，如需删字段请重建表（一般场景下直接忽略旧列也行）
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from loguru import logger

from .models import (
    SchemaInfo,
    database,
)

# ── 当前代码期望的 schema 版本 ────────────────────────────────
# 任何新的 ALTER TABLE 都要让这个数 +1，并在 MIGRATIONS 中追加一条
CURRENT_SCHEMA_VERSION: int = 6

# ── 迁移清单（按版本号升序排列） ────────────────────────────
# 约定：version 从 1 开始单调递增；每条 migration.up 只执行一个结构变更
MIGRATIONS: list[dict] = [
    {
        "version": 1,
        "description": "初始化 schema_info 表；对现有旧库做第一次版本标记",
        "up": lambda allow_aggressive=False: _migration_1_init_schema_info(),
    },
    {
        "version": 2,
        "description": "补齐 runs / backtest_trades / backtests / backtest_daily 的历史字段",
        "up": lambda allow_aggressive=False: _migration_2_add_historical_columns(),
    },
    {
        "version": 3,
        "description": "扩展 backtest_params 支持非数值策略参数",
        "up": lambda allow_aggressive=False: _migration_3_extend_backtest_params(),
    },
    {
        "version": 4,
        "description": "重建 backtest_params，移除 param_value 的旧 NOT NULL 约束",
        "up": lambda allow_aggressive=False: _migration_4_rebuild_backtest_params(allow_aggressive),
    },
    {
        "version": 5,
        "description": "将 backtest_trades 转为 raw fill 并新增 trade_clearings",
        "up": lambda allow_aggressive=False: _migration_5_add_clearing_tables(),
    },
    {
        "version": 6,
        "description": "新增清算域账户账本和持仓账本表",
        "up": lambda allow_aggressive=False: _migration_6_add_account_position_ledgers(),
    },
]


# ── 迁移管理器 ─────────────────────────────────────────────
class SchemaVersionManager:
    """管理 schema 版本与迁移执行"""

    def __init__(self) -> None:
        self._applied_versions: set[int] = set()

    def ensure_schema_info_table(self) -> None:
        """确保 schema_info 表存在（新库第一次启动时创建）"""
        database.create_tables([SchemaInfo], safe=True)

    def get_db_version(self) -> int:
        """读取数据库当前的 schema 版本号。没有 schema_info 或表空 → 返回 0"""
        try:
            cursor = database.execute_sql("SELECT MAX(version) FROM schema_info")
            row = cursor.fetchone()
            if row is None or row[0] is None:
                return 0
            return int(row[0])
        except Exception:
            # schema_info 表不存在 → 这是一张从未跑过版本化迁移的旧库
            return 0

    def run_pending_migrations(self, *, allow_aggressive: bool = False) -> None:
        """执行待执行的迁移。失败直接 raise，不吞异常"""
        self.ensure_schema_info_table()

        db_version = self.get_db_version()
        if db_version >= CURRENT_SCHEMA_VERSION:
            logger.info(
                "数据库 schema 已是最新版本 (db={}, code={})",
                db_version,
                CURRENT_SCHEMA_VERSION,
            )
            return

        logger.info(
            "检测到待执行迁移：当前 db={}，代码期望={}，aggressive={}，开始按顺序执行…",
            db_version,
            CURRENT_SCHEMA_VERSION,
            allow_aggressive,
        )

        for migration in sorted(MIGRATIONS, key=lambda m: m["version"]):
            version: int = migration["version"]
            if version <= db_version:
                continue

            description: str = migration["description"]
            up_fn: Callable[[bool], None] = migration["up"]

            logger.info("执行迁移 #{}：{}", version, description)
            try:
                with database.atomic():
                    up_fn(allow_aggressive)
                    SchemaInfo.create(
                        version=version,
                        description=description,
                        applied_at=datetime.now(),
                    )
                    self._applied_versions.add(version)
                    logger.info("迁移 #{} 完成", version)
            except Exception as e:
                logger.error("迁移 #{} ({}) 失败：{}", version, description, e)
                raise  # 不吞异常 — 失败就停止启动，让开发者看到问题

        logger.info(
            "所有迁移完成：db_version {} → {}",
            db_version,
            CURRENT_SCHEMA_VERSION,
        )


# ── 迁移实现（按版本号排序） ───────────────────────────────


def _table_columns(table_name: str) -> set[str]:
    """读取某张表已有列名，用于「字段不存在时再加」"""
    cursor = database.execute_sql(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}


def _column_notnull(table_name: str, column_name: str) -> bool:
    """读取 SQLite 列 NOT NULL 约束。"""
    cursor = database.execute_sql(f"PRAGMA table_info({table_name})")
    for row in cursor.fetchall():
        if row[1] == column_name:
            return bool(row[3])
    return False


def _migration_1_init_schema_info() -> None:
    """第一次版本标记 — 确保 schema_info 表已建（在 ensure_schema_info_table 中处理），
    这里什么都不做，只为了给旧库打一个「至少跑到 v1」的版本锚点。

    目的：原本没有 schema_info 表的旧数据库，跑完这条后版本号变成 1，
    后续新的迁移可以在此基础上继续叠加。
    """
    pass


def _migration_2_add_historical_columns() -> None:
    """补齐历史上硬编码在 _init_tables() 中的所有 ALTER COLUMN

    对应旧逻辑：data/store.py _init_tables() 里的 4 段 PRAGMA + ALTER TABLE
    """
    # ── runs 表 ──────────────────────────────────────
    runs_cols = _table_columns("runs")
    if "use_fixed_seed" not in runs_cols:
        database.execute_sql("ALTER TABLE runs ADD COLUMN use_fixed_seed INTEGER DEFAULT 0")
    if "random_seed" not in runs_cols:
        database.execute_sql("ALTER TABLE runs ADD COLUMN random_seed INTEGER")

    # ── backtest_trades 表 ───────────────────────────
    bt_trades_cols = _table_columns("backtest_trades")
    if "reason" not in bt_trades_cols:
        database.execute_sql("ALTER TABLE backtest_trades ADD COLUMN reason VARCHAR(512) DEFAULT ''")

    # ── backtests 表（vnpy 全量指标字段） ───────────
    backtests_cols = _table_columns("backtests")
    backtests_new_cols: list[tuple[str, str]] = [
        ("max_ddpercent", "REAL"),
        ("total_net_pnl", "REAL"),
        ("daily_net_pnl", "REAL"),
        ("total_commission", "REAL"),
        ("daily_commission", "REAL"),
        ("total_slippage", "REAL"),
        ("daily_slippage", "REAL"),
        ("total_turnover", "REAL"),
        ("daily_turnover", "REAL"),
        ("profit_days", "INTEGER"),
        ("loss_days", "INTEGER"),
        ("daily_trade_count", "REAL"),
        ("daily_return_pct", "REAL"),
        ("ewm_sharpe", "REAL"),
        ("rgr_ratio", "REAL"),
    ]
    for col_name, col_type in backtests_new_cols:
        if col_name not in backtests_cols:
            database.execute_sql(f"ALTER TABLE backtests ADD COLUMN {col_name} {col_type}")

    # ── backtest_daily 表（vnpy 日度字段） ──────────
    bd_cols = _table_columns("backtest_daily")
    bd_new_cols: list[tuple[str, str]] = [
        ("turnover", "REAL"),
        ("commission", "REAL"),
        ("slippage", "REAL"),
        ("trade_count", "INTEGER"),
    ]
    for col_name, col_type in bd_new_cols:
        if col_name not in bd_cols:
            database.execute_sql(f"ALTER TABLE backtest_daily ADD COLUMN {col_name} {col_type}")


def _migration_3_extend_backtest_params() -> None:
    """扩展 backtest_params，使其可保存非数值策略参数原始值。"""
    cols = _table_columns("backtest_params")
    if "param_type" not in cols:
        database.execute_sql("ALTER TABLE backtest_params ADD COLUMN param_type VARCHAR(255) DEFAULT 'float'")
    if "param_text" not in cols:
        database.execute_sql("ALTER TABLE backtest_params ADD COLUMN param_text TEXT")
    if "param_value" in cols:
        database.execute_sql(
            "UPDATE backtest_params SET param_text = CAST(param_value AS TEXT) WHERE param_text IS NULL"
        )


def _migration_4_rebuild_backtest_params(allow_aggressive: bool) -> None:
    """重建 backtest_params，使 param_value 真正允许 NULL。"""
    if not _column_notnull("backtest_params", "param_value"):
        return
    if not allow_aggressive:
        raise RuntimeError(
            "backtest_params.param_value 仍有 NOT NULL 约束；"
            "需要开启 data.allow_aggressive_schema_migration 后才能重建旧表"
        )

    cols = _table_columns("backtest_params")
    if "param_type" not in cols:
        database.execute_sql("ALTER TABLE backtest_params ADD COLUMN param_type VARCHAR(255) DEFAULT 'float'")
    if "param_text" not in cols:
        database.execute_sql("ALTER TABLE backtest_params ADD COLUMN param_text TEXT")
    database.execute_sql("UPDATE backtest_params SET param_text = CAST(param_value AS TEXT) WHERE param_text IS NULL")
    database.execute_sql("PRAGMA foreign_keys=OFF")
    try:
        database.execute_sql(
            """
            CREATE TABLE backtest_params_new (
                id INTEGER NOT NULL PRIMARY KEY,
                backtest_id INTEGER NOT NULL,
                param_name VARCHAR(255) NOT NULL,
                param_value REAL,
                param_type VARCHAR(255) NOT NULL DEFAULT 'float',
                param_text TEXT,
                FOREIGN KEY(backtest_id) REFERENCES backtests(id) ON DELETE CASCADE
            )
            """
        )
        database.execute_sql(
            """
            INSERT INTO backtest_params_new (
                id, backtest_id, param_name, param_value, param_type, param_text
            )
            SELECT id,
                   backtest_id,
                   param_name,
                   param_value,
                   COALESCE(param_type, 'float'),
                   COALESCE(param_text, CAST(param_value AS TEXT))
            FROM backtest_params
            """
        )
        database.execute_sql("DROP TABLE backtest_params")
        database.execute_sql("ALTER TABLE backtest_params_new RENAME TO backtest_params")
        database.execute_sql("CREATE INDEX backtestparam_backtest_id ON backtest_params (backtest_id)")
    finally:
        database.execute_sql("PRAGMA foreign_keys=ON")


def _migration_5_add_clearing_tables() -> None:
    """将 backtest_trades 扩展为 raw fill，并新增清算表。"""
    bt_trades_cols = _table_columns("backtest_trades")
    bt_trades_new_cols: list[tuple[str, str]] = [
        ("price", "REAL"),
        ("engine_trade_id", "VARCHAR(128)"),
        ("engine_order_id", "VARCHAR(128)"),
        ("raw_direction", "VARCHAR(32)"),
        ("raw_offset", "VARCHAR(32)"),
    ]
    for col_name, col_type in bt_trades_new_cols:
        if col_name not in bt_trades_cols:
            database.execute_sql(f"ALTER TABLE backtest_trades ADD COLUMN {col_name} {col_type}")
    if "price" not in bt_trades_cols:
        database.execute_sql(
            "UPDATE backtest_trades SET price = COALESCE(NULLIF(close_price, 0), NULLIF(open_price, 0), 0)"
        )

    database.execute_sql(
        """
        CREATE TABLE IF NOT EXISTS trade_clearings (
            id INTEGER NOT NULL PRIMARY KEY,
            backtest_id INTEGER NOT NULL,
            run_id INTEGER,
            symbol VARCHAR(255) NOT NULL,
            open_trade_id INTEGER,
            close_trade_id INTEGER,
            source_trade_ids TEXT,
            direction VARCHAR(255) NOT NULL,
            volume REAL NOT NULL,
            open_time DATETIME NOT NULL,
            close_time DATETIME NOT NULL,
            open_price REAL NOT NULL,
            close_price REAL NOT NULL,
            contract_multiplier REAL NOT NULL,
            price_tick REAL,
            gross_pnl REAL NOT NULL,
            commission REAL NOT NULL,
            slippage_cost REAL NOT NULL,
            net_pnl REAL NOT NULL,
            open_reason VARCHAR(512) NOT NULL DEFAULT '',
            close_reason VARCHAR(512) NOT NULL DEFAULT '',
            holding_seconds REAL,
            holding_bars INTEGER,
            is_forced_close INTEGER NOT NULL DEFAULT 0,
            forced_close_reason VARCHAR(128),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(backtest_id) REFERENCES backtests(id) ON DELETE CASCADE,
            FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE SET NULL,
            FOREIGN KEY(open_trade_id) REFERENCES backtest_trades(id) ON DELETE SET NULL,
            FOREIGN KEY(close_trade_id) REFERENCES backtest_trades(id) ON DELETE SET NULL
        )
        """
    )
    database.execute_sql("CREATE INDEX IF NOT EXISTS tradeclearings_backtest_id ON trade_clearings (backtest_id)")
    database.execute_sql(
        "CREATE INDEX IF NOT EXISTS tradeclearings_backtest_close_time ON trade_clearings (backtest_id, close_time)"
    )
    database.execute_sql(
        "CREATE INDEX IF NOT EXISTS tradeclearings_backtest_symbol ON trade_clearings (backtest_id, symbol)"
    )
    database.execute_sql("CREATE INDEX IF NOT EXISTS tradeclearings_open_trade_id ON trade_clearings (open_trade_id)")
    database.execute_sql("CREATE INDEX IF NOT EXISTS tradeclearings_close_trade_id ON trade_clearings (close_trade_id)")


def _migration_6_add_account_position_ledgers() -> None:
    _migration_5_add_clearing_tables()
    database.execute_sql(
        """
        CREATE TABLE IF NOT EXISTS account_ledger_entries (
            id INTEGER NOT NULL PRIMARY KEY,
            backtest_id INTEGER NOT NULL,
            run_id INTEGER,
            trade_id INTEGER,
            clearing_id INTEGER,
            source_type VARCHAR(32) NOT NULL DEFAULT 'backtest',
            source_id INTEGER,
            event_time DATETIME NOT NULL,
            event_type VARCHAR(64) NOT NULL,
            symbol VARCHAR(255),
            cash_delta REAL NOT NULL DEFAULT 0,
            realized_pnl_delta REAL NOT NULL DEFAULT 0,
            unrealized_pnl_delta REAL NOT NULL DEFAULT 0,
            commission_delta REAL NOT NULL DEFAULT 0,
            slippage_delta REAL NOT NULL DEFAULT 0,
            cash_balance REAL NOT NULL DEFAULT 0,
            realized_pnl_balance REAL NOT NULL DEFAULT 0,
            unrealized_pnl_balance REAL NOT NULL DEFAULT 0,
            equity REAL NOT NULL DEFAULT 0,
            margin REAL,
            metadata_json TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(backtest_id) REFERENCES backtests(id) ON DELETE CASCADE,
            FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE SET NULL,
            FOREIGN KEY(trade_id) REFERENCES backtest_trades(id) ON DELETE SET NULL,
            FOREIGN KEY(clearing_id) REFERENCES trade_clearings(id) ON DELETE CASCADE
        )
        """
    )
    database.execute_sql(
        """
        CREATE TABLE IF NOT EXISTS position_ledger_entries (
            id INTEGER NOT NULL PRIMARY KEY,
            backtest_id INTEGER NOT NULL,
            run_id INTEGER,
            open_trade_id INTEGER,
            close_trade_id INTEGER,
            clearing_id INTEGER,
            source_type VARCHAR(32) NOT NULL DEFAULT 'backtest',
            source_id INTEGER,
            event_time DATETIME NOT NULL,
            event_type VARCHAR(64) NOT NULL,
            symbol VARCHAR(255) NOT NULL,
            direction VARCHAR(255) NOT NULL,
            volume_delta REAL NOT NULL DEFAULT 0,
            position_volume REAL NOT NULL DEFAULT 0,
            avg_open_price REAL NOT NULL DEFAULT 0,
            realized_pnl_delta REAL NOT NULL DEFAULT 0,
            is_forced_close INTEGER NOT NULL DEFAULT 0,
            metadata_json TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(backtest_id) REFERENCES backtests(id) ON DELETE CASCADE,
            FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE SET NULL,
            FOREIGN KEY(open_trade_id) REFERENCES backtest_trades(id) ON DELETE SET NULL,
            FOREIGN KEY(close_trade_id) REFERENCES backtest_trades(id) ON DELETE SET NULL,
            FOREIGN KEY(clearing_id) REFERENCES trade_clearings(id) ON DELETE CASCADE
        )
        """
    )
    database.execute_sql(
        "CREATE INDEX IF NOT EXISTS accountledgerentries_backtest_time ON account_ledger_entries (backtest_id, event_time)"
    )
    database.execute_sql(
        "CREATE INDEX IF NOT EXISTS accountledgerentries_run_time ON account_ledger_entries (run_id, event_time)"
    )
    database.execute_sql(
        "CREATE INDEX IF NOT EXISTS accountledgerentries_clearing_id ON account_ledger_entries (clearing_id)"
    )
    database.execute_sql(
        "CREATE INDEX IF NOT EXISTS accountledgerentries_trade_id ON account_ledger_entries (trade_id)"
    )
    database.execute_sql(
        "CREATE INDEX IF NOT EXISTS positionledgerentries_backtest_time ON position_ledger_entries (backtest_id, event_time)"
    )
    database.execute_sql(
        "CREATE INDEX IF NOT EXISTS positionledgerentries_run_time ON position_ledger_entries (run_id, event_time)"
    )
    database.execute_sql(
        "CREATE INDEX IF NOT EXISTS positionledgerentries_symbol_direction_time ON position_ledger_entries (backtest_id, symbol, direction, event_time)"
    )
    database.execute_sql(
        "CREATE INDEX IF NOT EXISTS positionledgerentries_clearing_id ON position_ledger_entries (clearing_id)"
    )
    database.execute_sql(
        "CREATE INDEX IF NOT EXISTS positionledgerentries_open_trade_id ON position_ledger_entries (open_trade_id)"
    )
    database.execute_sql(
        "CREATE INDEX IF NOT EXISTS positionledgerentries_close_trade_id ON position_ledger_entries (close_trade_id)"
    )


# ── 公开 API ─────────────────────────────────────────────


def run_pending_migrations(*, allow_aggressive: bool = False) -> None:
    """外部入口：执行所有待执行的迁移"""
    manager = SchemaVersionManager()
    manager.run_pending_migrations(allow_aggressive=allow_aggressive)


def get_current_version() -> int:
    """获取数据库当前 schema 版本号（用于调试/检查）"""
    manager = SchemaVersionManager()
    manager.ensure_schema_info_table()
    return manager.get_db_version()


def get_expected_version() -> int:
    """获取代码期望的 schema 版本号"""
    return CURRENT_SCHEMA_VERSION
