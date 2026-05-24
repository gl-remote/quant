"""peewee ORM 模型定义 — SQLite 数据库表映射

本模块定义全部 4 张表的 ORM 模型:
  - ExportMetadata  : CSV 数据导出元数据
  - OperationLog    : 系统操作日志
  - Backtest        : 回测运行主表
  - BacktestTrade   : 回测交易明细 (ForeignKey → Backtest)

所有模型通过 database_proxy (DatabaseProxy) 延迟绑定实际数据库连接，
在 Database.__init__ 时由 data/database.py 完成绑定。
"""

import peewee as pw

# 数据库代理 — 模块级单例，运行时由 Database 类完成绑定和解绑
database_proxy = pw.DatabaseProxy()


class BaseModel(pw.Model):
    """所有模型的基类，统一绑定 database_proxy"""
    class Meta:
        database = database_proxy


# ── export_metadata ──────────────────────────────────────────────

class ExportMetadata(BaseModel):
    """CSV 数据导出元数据 — 每次天勤导出时 upsert 一条记录"""

    symbol = pw.CharField(max_length=64)
    filepath = pw.CharField(max_length=512)
    start_date = pw.CharField(max_length=10, null=True)
    end_date = pw.CharField(max_length=10, null=True)
    min_dt = pw.CharField(max_length=19, null=True)
    max_dt = pw.CharField(max_length=19, null=True)
    total_rows = pw.IntegerField(default=0)
    created_at = pw.CharField(max_length=26)
    updated_at = pw.CharField(max_length=26)

    class Meta:
        table_name = 'export_metadata'


# ── operation_logs ───────────────────────────────────────────────

class OperationLog(BaseModel):
    """系统操作日志 — 记录 export/backtest/live/test 等命令执行历史

    自动清理: 超过 _MAX_OPERATION_LOG_ROWS 条时触发，逻辑在 Database._prune_old_logs
    """

    command = pw.CharField(max_length=32)
    symbol = pw.CharField(max_length=64, null=True)
    message = pw.TextField(null=True)
    status = pw.CharField(max_length=16, default='INFO')
    created_at = pw.CharField(max_length=26)

    class Meta:
        table_name = 'operation_logs'


# ── backtests ────────────────────────────────────────────────────

class Backtest(BaseModel):
    """回测运行主表 — 每次 run_full_pipeline 产生一条记录"""

    symbol = pw.CharField(max_length=64)
    strategy = pw.CharField(max_length=64)
    status = pw.CharField(max_length=16, default='running')
    error_message = pw.TextField(null=True)
    # 数据范围
    data_start_date = pw.CharField(max_length=10, null=True)
    data_end_date = pw.CharField(max_length=10, null=True)
    start_date = pw.CharField(max_length=10, null=True)
    end_date = pw.CharField(max_length=10, null=True)
    total_days = pw.IntegerField(null=True)
    # 引擎参数
    initial_capital = pw.FloatField()
    commission_rate = pw.FloatField(null=True)
    slippage = pw.FloatField(null=True)
    price_tick = pw.FloatField(null=True)
    contract_size = pw.IntegerField(null=True)
    kline_interval = pw.CharField(max_length=8, null=True)
    params_json = pw.TextField(null=True)
    # 资金
    end_balance = pw.FloatField(null=True)
    total_return = pw.FloatField(null=True)
    annual_return = pw.FloatField(null=True)
    # 交易统计
    total_trades = pw.IntegerField(null=True)
    win_trades = pw.IntegerField(null=True)
    loss_trades = pw.IntegerField(null=True)
    win_rate = pw.FloatField(null=True)
    max_consecutive_win = pw.IntegerField(null=True)
    max_consecutive_loss = pw.IntegerField(null=True)
    average_win = pw.FloatField(null=True)
    average_loss = pw.FloatField(null=True)
    win_loss_ratio = pw.FloatField(null=True)
    # 风险
    sharpe_ratio = pw.FloatField(null=True)
    max_drawdown = pw.FloatField(null=True)
    max_drawdown_duration = pw.IntegerField(null=True)
    daily_std = pw.FloatField(null=True)
    return_drawdown_ratio = pw.FloatField(null=True)
    # 时间戳
    created_at = pw.CharField(max_length=26)
    updated_at = pw.CharField(max_length=26)

    class Meta:
        table_name = 'backtests'
        indexes = (
            (('symbol',), False),
            (('strategy',), False),
            (('created_at',), False),
            (('symbol', 'strategy'), False),
        )


# ── backtest_trades ──────────────────────────────────────────────

class BacktestTrade(BaseModel):
    """回测交易明细 — 每笔成交一条，FK 关联 backtests.id"""

    backtest_id = pw.ForeignKeyField(
        Backtest, backref='trades', on_delete='CASCADE',
    )
    symbol = pw.CharField(max_length=64)
    datetime = pw.CharField(max_length=26)
    direction = pw.CharField(max_length=8)
    offset = pw.CharField(max_length=8, default='open')
    price = pw.FloatField()
    volume = pw.IntegerField()
    trade_day = pw.CharField(max_length=10, null=True)
    created_at = pw.CharField(max_length=26)
    updated_at = pw.CharField(max_length=26)

    class Meta:
        table_name = 'backtest_trades'
        indexes = (
            (('backtest_id',), False),
            (('symbol',), False),
            (('datetime',), False),
            (('trade_day',), False),
        )
