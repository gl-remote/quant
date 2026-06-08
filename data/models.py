"""数据类型定义模块

包含：
1. Pandera DataFrameSchema - 从 common.schemas 导入（全局统一）
2. Pydantic BaseModel - 用于单条记录的验证
3. ORM 模型 - 内部数据库模型（不对外暴露）
"""

from peewee import (
    SQL,
    CharField,
    DateField,
    DateTimeField,
    FloatField,
    ForeignKeyField,
    IntegerField,
    Model,
    SqliteDatabase,
    TextField,
)
from pydantic import BaseModel, field_validator

# 从 common.schemas 导入 Pandera Schema，供 manager.py 等上层模块引用
# 注：此 import 作为 re-export 供上层模块使用
from common.schemas import KlineSchema  # noqa: F401  # pyright: ignore[reportUnusedImport]

# ==============================================================================
# Pydantic 模型（对外暴露，用于单条记录验证）
# ==============================================================================


class BacktestRecord(BaseModel):
    """回测记录 — 字段与 ORM Backtest 表保持一致

    2026-06-06 新增 15 个 vnpy 统计字段（max_ddpercent / 盈亏汇总 / 交易日统计 / 进阶指标）
    """

    id: int | None = None
    run: int | None = None  # peewee FK 字段名是 run，存的是 run_id 值
    symbol: str
    strategy: str
    strategy_version: str | None = None
    git_hash: str | None = None
    status: str = "success"
    error_message: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    total_days: int | None = None
    initial_capital: float = 0.0
    end_balance: float | None = None
    total_return: float = 0.0  # [vnpy] 总收益率%
    annual_return: float | None = None  # [vnpy] 年化收益%

    # 风险指标 [vnpy]
    sharpe_ratio: float | None = None  # [vnpy] 夏普比率
    max_drawdown: float | None = None  # [vnpy] 最大回撤(金额)
    max_ddpercent: float | None = None  # [vnpy] 最大回撤百分比 (2026-06-06新增)
    max_drawdown_duration: int | None = None  # [vnpy] 最大回撤持续天数
    daily_std: float | None = None  # [vnpy] 日收益率标准差
    return_drawdown_ratio: float | None = None  # [vnpy] 收益回撤比

    # 盈亏汇总 [vnpy] (2026-06-06新增)
    total_net_pnl: float | None = None  # [vnpy] 总净盈亏金额
    daily_net_pnl: float | None = None  # [vnpy] 日均净盈亏
    total_commission: float | None = None  # [vnpy] 总手续费
    daily_commission: float | None = None  # [vnpy] 日均手续费
    total_slippage: float | None = None  # [vnpy] 总滑点成本
    daily_slippage: float | None = None  # [vnpy] 日均滑点
    total_turnover: float | None = None  # [vnpy] 总成交金额
    daily_turnover: float | None = None  # [vnpy] 日均成交额

    # 交易日统计 [vnpy] (2026-06-06新增)
    profit_days: int | None = None  # [vnpy] 盈利交易日数
    loss_days: int | None = None  # [vnpy] 亏损交易日数
    daily_trade_count: float | None = None  # [vnpy] 日均成交笔数
    daily_return_pct: float | None = None  # [vnpy] 日均收益率%

    # 进阶指标 [vnpy] (2026-06-06新增)
    ewm_sharpe: float | None = None  # [vnpy] EWM夏普比率
    rgr_ratio: float | None = None  # [vnpy] RGR比率

    # 交易统计 (total_trades 来自 vnpy; win/loss/avg 基于逐笔 pnl 聚合)
    total_trades: int = 0  # [vnpy] 总成交笔数（含开仓+平仓）
    win_trades: int | None = None
    loss_trades: int | None = None
    win_rate: float | None = None
    avg_win: float | None = None
    avg_loss: float | None = None
    win_loss_ratio: float | None = None
    max_consecutive_win: int | None = None
    max_consecutive_loss: int | None = None

    # 引擎配置
    commission_rate: float | None = None  # 手续费率
    slippage: float | None = None  # 单边滑点
    price_tick: float | None = None  # 最小变动价位
    contract_size: int | None = None  # 合约乘数
    kline_interval: str | None = None  # K线周期
    data_src: str | None = None  # 数据来源

    created_at: str | None = None


class TradeRecord(BaseModel):
    """交易记录"""

    id: int | None = None
    backtest_id: int
    datetime: str
    symbol: str
    direction: str
    offset: str = "open"
    open_price: float
    close_price: float
    quantity: float
    pnl: float = 0.0  # 净盈亏（已扣除 commission + slippage）
    commission: float = 0.0  # 该笔平仓周期总手续费（开仓侧 + 平仓侧）
    created_at: str | None = None

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("quantity must be greater than 0")
        return v

    @field_validator("commission")
    @classmethod
    def validate_commission(cls, v: float) -> float:
        if v < 0:
            raise ValueError("commission must be >= 0")
        return v


class SymbolInfo(BaseModel):
    """品种信息"""

    symbol: str
    available: bool
    filepath: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    total_rows: int | None = None
    error: str | None = None


class DataSummary(BaseModel):
    """数据汇总"""

    total_symbols: int
    symbols: list[SymbolInfo]


class DataLoadResult(BaseModel):
    """数据加载结果"""

    success: bool
    symbol: str
    start_date: str | None = None
    end_date: str | None = None
    row_count: int = 0
    message: str


# ==============================================================================
# ORM 模型（内部使用，不对外暴露）
# ==============================================================================

database = SqliteDatabase(None)


class OrmBaseModel(Model):
    """基础模型"""

    class Meta:
        database: SqliteDatabase = database


class ExportMetadata(OrmBaseModel):
    """导出元数据 — 联合唯一键 (symbol, provider, interval)"""

    symbol: CharField = CharField()
    provider: CharField = CharField()  # 数据源: tqsdk / akshare
    interval: CharField = CharField()  # K线周期: 1m / 5m / 1d / ...
    filepath: CharField = CharField()
    start_date: DateField = DateField(null=True)
    end_date: DateField = DateField(null=True)
    min_dt: DateField = DateField(null=True)
    max_dt: DateField = DateField(null=True)
    total_rows: IntegerField = IntegerField(default=0)
    created_at: DateTimeField = DateTimeField(constraints=[SQL("DEFAULT CURRENT_TIMESTAMP")])
    updated_at: DateTimeField = DateTimeField(null=True)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        table_name: str = "export_metadata"
        indexes = (
            (("symbol", "provider", "interval"), True),  # 联合唯一约束
        )


class OperationLog(OrmBaseModel):
    """操作日志"""

    command: CharField = CharField()
    symbol: CharField = CharField(null=True)
    message: TextField = TextField()
    status: CharField = CharField()
    created_at: DateTimeField = DateTimeField(constraints=[SQL("DEFAULT CURRENT_TIMESTAMP")])

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        table_name: str = "operation_logs"


class Run(OrmBaseModel):
    """批量回测运行记录 — 每次跑回测一条"""

    strategy: CharField = CharField()
    engine: CharField = CharField(default="grid")
    symbols: IntegerField = IntegerField(default=0)
    status: CharField = CharField(default="running")
    use_fixed_seed: IntegerField = IntegerField(default=0)  # 0=false, 1=true
    random_seed: IntegerField = IntegerField(null=True)
    created_at: DateTimeField = DateTimeField(constraints=[SQL("DEFAULT CURRENT_TIMESTAMP")])

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        table_name: str = "runs"


class RunStudy(OrmBaseModel):
    """关联 runs 与 Optuna studies"""

    run: ForeignKeyField = ForeignKeyField(Run, backref="studies", on_delete="CASCADE")
    study_name: CharField = CharField(unique=True)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        table_name: str = "run_studies"


class Backtest(OrmBaseModel):
    """回测记录（与数据库表结构保持一致）

    字段来源说明:
      - vnpy 直接提供: vnpy calculate_statistics() 输出，基于日度净盈亏(net_pnl)计算
      - 自行计算: 从逐笔交易记录(pnl)聚合统计，改后同样基于净盈亏
      - 配置入参: 回测运行时传入的参数
    """

    run: ForeignKeyField = ForeignKeyField(Run, backref="backtests", null=True, on_delete="SET NULL")
    # ── 标识 ──────────────────────────────────────────
    symbol: CharField = CharField()  # 品种代码 (如 rb2505)
    strategy: CharField = CharField()  # 策略名称
    strategy_version: CharField = CharField(null=True)  # 策略版本号
    git_hash: CharField = CharField(null=True)  # 提交哈希
    # ── 状态 ──────────────────────────────────────────
    status: CharField = CharField()  # running / success / failed
    error_message: TextField = TextField(null=True)  # 错误信息
    # ── 日期范围 ──────────────────────────────────────
    start_date: CharField = CharField(null=True, max_length=10)  # 回测起始日期
    end_date: CharField = CharField(null=True, max_length=10)  # 回测结束日期
    total_days: IntegerField = IntegerField(null=True)  # 总交易日数
    # ── 资金配置（入参）──────────────────────────────
    initial_capital: FloatField = FloatField()  # 初始资金
    commission_rate: FloatField = FloatField(null=True)  # 手续费率（如 0.0003）
    slippage: FloatField = FloatField(null=True)  # 单边滑点（价格单位）
    price_tick: FloatField = FloatField(null=True)  # 最小变动价位
    contract_size: IntegerField = IntegerField(null=True)  # 合约乘数
    kline_interval: CharField = CharField(null=True, max_length=8)  # K线周期 (1m/5m/1h/1d)
    # ── 核心绩效指标（vnpy calculate_statistics 直接输出）──
    end_balance: FloatField = FloatField(null=True)  # 期末权益余额
    total_return: FloatField = FloatField(null=True)  # 总收益率 (%)
    annual_return: FloatField = FloatField(null=True)  # 年化收益率 (%)
    total_trades: IntegerField = IntegerField(null=True)  # 总成交笔数 (vnpy total_trade_count)
    sharpe_ratio: FloatField = FloatField(null=True)  # 夏普比率（基于 net_pnl 日收益序列）
    max_drawdown: FloatField = FloatField(null=True)  # 最大回撤金额
    max_ddpercent: FloatField = FloatField(null=True)  # 最大回撤百分比 (%) [vnpy]
    max_drawdown_duration: IntegerField = IntegerField(null=True)  # 最大回撤持续天数
    daily_std: FloatField = FloatField(null=True)  # 日收益率标准差 (%)
    return_drawdown_ratio: FloatField = FloatField(null=True)  # 收益回撤比
    # ── 盈亏汇总（vnpy 直接输出）─────────────────────
    total_net_pnl: FloatField = FloatField(null=True)  # 总净盈亏金额（扣完费用后）[vnpy]
    daily_net_pnl: FloatField = FloatField(null=True)  # 日均净盈亏金额 [vnpy]
    total_commission: FloatField = FloatField(null=True)  # 总手续费金额 [vnpy]
    daily_commission: FloatField = FloatField(null=True)  # 日均手续费 [vnpy]
    total_slippage: FloatField = FloatField(null=True)  # 总滑点成本金额 [vnpy]
    daily_slippage: FloatField = FloatField(null=True)  # 日均滑点成本 [vnpy]
    total_turnover: FloatField = FloatField(null=True)  # 总成交金额 [vnpy]
    daily_turnover: FloatField = FloatField(null=True)  # 日均成交金额 [vnpy]
    # ── 交易日统计（vnpy 直接输出）────────────────────
    profit_days: IntegerField = IntegerField(null=True)  # 盈利交易日数 [vnpy]
    loss_days: IntegerField = IntegerField(null=True)  # 亏损交易日数 [vnpy]
    daily_trade_count: FloatField = FloatField(null=True)  # 日均成交笔数 [vnpy]
    daily_return_pct: FloatField = FloatField(null=True)  # 日均收益率 (%) [vnpy daily_return]
    # ── 交易级别统计（自行从逐笔 pnl 聚合计算）─────────
    win_trades: IntegerField = IntegerField(null=True)  # 盈利交易笔数（pnl > 0 的平仓次数）
    loss_trades: IntegerField = IntegerField(null=True)  # 亏损交易笔数（pnl <= 0 的平仓次数）
    win_rate: FloatField = FloatField(null=True)  # 胜率 = win_trades / (win+loss)
    max_consecutive_win: IntegerField = IntegerField(null=True)  # 最大连续盈利次数
    max_consecutive_loss: IntegerField = IntegerField(null=True)  # 最大连续亏损次数
    avg_win: FloatField = FloatField(null=True)  # 平均盈利金额（盈利笔的 pnl 均值）
    avg_loss: FloatField = FloatField(null=True)  # 平均亏损金额（亏损笔的 |pnl| 均值）
    win_loss_ratio: FloatField = FloatField(null=True)  # 盈亏比 = avg_win / avg_loss
    # ── 进阶指标（vnpy 输出）─────────────────────────
    ewm_sharpe: FloatField = FloatField(null=True)  # EWM 指数加权夏普比率 [vnpy]
    rgr_ratio: FloatField = FloatField(null=True)  # RGR 比率（CAGR × 稳定性 / 综合风险）[vnpy]
    # ── 元数据 ────────────────────────────────────────
    engine_config: TextField = TextField(null=True)  # JSON: 引擎类型、优化器、study名等
    created_at: DateTimeField = DateTimeField(constraints=[SQL("DEFAULT CURRENT_TIMESTAMP")])
    updated_at: DateTimeField = DateTimeField(constraints=[SQL("DEFAULT CURRENT_TIMESTAMP")])
    data_src: TextField = TextField(null=True)  # 数据源路径

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        table_name: str = "backtests"


class BacktestParam(OrmBaseModel):
    """回测参数 — 每个参数一行，与 backtest_id 关联"""

    backtest: ForeignKeyField = ForeignKeyField(Backtest, backref="params", on_delete="CASCADE")
    param_name: CharField = CharField()
    param_value: FloatField = FloatField()

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        table_name: str = "backtest_params"


class BacktestTrade(OrmBaseModel):
    """回测交易明细（逐笔成交记录）

    注意: vnpy 的 TradeData 代表单笔成交(fill)，不是完整交易(trade)。

    open_price / close_price 语义:
      开仓记录 (offset=open): open_price = close_price = 成交价
      平仓记录 (offset=close):
        open_price = 加权平均开仓价（FIFO 配对时同方向待配对开仓的 Σ(price×vol)/Σ(vol)）
        close_price = 平仓成交价
    """

    backtest: ForeignKeyField = ForeignKeyField(Backtest, backref="trades", on_delete="CASCADE")
    datetime: DateTimeField = DateTimeField()
    symbol: CharField = CharField()
    direction: CharField = CharField()
    offset: CharField = CharField()
    open_price: FloatField = FloatField()  # 开仓=成交价，平仓=加权平均开仓价
    close_price: FloatField = FloatField()  # 实际成交价（开仓/平仓均为此笔的执行价格）
    quantity: FloatField = FloatField()
    pnl: FloatField = FloatField()  # 净盈亏（已扣除 commission + slippage）
    commission: FloatField = FloatField()  # 该笔平仓周期总手续费（开仓侧 + 平仓侧）
    reason: CharField = CharField(max_length=512, default="")
    created_at: DateTimeField = DateTimeField(constraints=[SQL("DEFAULT CURRENT_TIMESTAMP")])

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        table_name: str = "backtest_trades"


class BacktestDaily(OrmBaseModel):
    """回测每日资金曲线

    注意: daily_return 字段实际存储的是当日净盈亏金额(net_pnl)，
    而非百分比收益率。字段名保留 historical compatibility。

    2026-06-06 新增 vnpy 日度字段（turnover/commission/slippage/trade_count）
    """

    backtest: ForeignKeyField = ForeignKeyField(Backtest, backref="daily", on_delete="CASCADE")
    date: DateField = DateField()
    equity: FloatField = FloatField()  # 当日权益
    daily_return: FloatField = FloatField()  # 当日净盈亏(金额)，非百分比
    drawdown: FloatField = FloatField()  # 当日回撤
    # 2026-06-06 新增 vnpy 日度字段
    turnover: FloatField = FloatField(null=True)  # 当日成交金额 [vnpy]
    commission: FloatField = FloatField(null=True)  # 当日手续费 [vnpy]
    slippage: FloatField = FloatField(null=True)  # 当日滑点成本 [vnpy]
    trade_count: IntegerField = IntegerField(null=True)  # 当日成交笔数 [vnpy]
    created_at: DateTimeField = DateTimeField(constraints=[SQL("DEFAULT CURRENT_TIMESTAMP")])

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        table_name: str = "backtest_daily"


# ==============================================================================
# Live / Test 实时交易 ORM 模型（2 个 Model → 4 张物理表）
#
# 设计决策 (参见 cli/tqsdk-test-plan.md §8-9):
#   - test 和 live 共用同一套字段定义，通过工厂函数指定不同表名
#   - test 表: test_sessions / test_trades（信号验证，不下单，pnl/commission 为 NULL）
#   - live 表: live_sessions / live_trades（实盘/模拟交易，有真实盈亏）
#   - 安全隔离: test 命令代码路径中不包含 TargetPosTask，永远不下单
# ==============================================================================


class BaseLiveModel(OrmBaseModel):
    """Live / Test 共用的基类 — 子类必须指定 table_name"""

    class Meta:
        table_name: str | None = None  # pyright: ignore[reportIncompatibleVariableOverride]


def _make_live_session_model(table_name: str) -> type[BaseLiveModel]:
    """工厂函数：返回映射到指定表名的 LiveSession Model

    Args:
        table_name: "test_sessions" 或 "live_sessions"

    用法:
        TestSession = get_live_session_model("test_sessions")
        LiveSession = get_live_session_model("live_sessions")
    """

    class LiveSession(BaseLiveModel):
        # ── 标识 ──────────────────────────────────────
        symbol: CharField = CharField(max_length=20)  # 品种代码 (如 SHFE.rb2509)
        strategy: CharField = CharField(max_length=50)  # 策略名称
        strategy_version: CharField = CharField(null=True, max_length=20)
        git_hash: CharField = CharField(null=True, max_length=40)
        # ── 运行状态 ──────────────────────────────────
        mode: CharField = CharField(max_length=10)  # "test" / "sim" / "live"
        status: CharField = CharField(max_length=20)  # running / stopped / error
        started_at: DateTimeField = DateTimeField()
        ended_at: DateTimeField = DateTimeField(null=True)
        # ── 金额变动（live 时实时更新，test 时为 NULL）──
        initial_capital: FloatField = FloatField(null=True)
        current_balance: FloatField = FloatField(null=True)
        total_pnl: FloatField = FloatField(null=True)
        total_commission: FloatField = FloatField(null=True)
        total_trades: IntegerField = IntegerField(default=0)
        # ── 信号统计（test 时填充，live 时为 0）───────
        total_signals: IntegerField = IntegerField(default=0)
        buy_signals: IntegerField = IntegerField(default=0)
        sell_signals: IntegerField = IntegerField(default=0)
        # ── 统计指标（预留）────────────────────────────
        total_return: FloatField = FloatField(null=True)
        sharpe_ratio: FloatField = FloatField(null=True)
        max_drawdown: FloatField = FloatField(null=True)
        win_rate: FloatField = FloatField(null=True)
        # ── 元数据 ──────────────────────────────────────
        created_at: DateTimeField = DateTimeField(constraints=[SQL("DEFAULT CURRENT_TIMESTAMP")])
        updated_at: DateTimeField = DateTimeField(constraints=[SQL("DEFAULT CURRENT_TIMESTAMP")])

        class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
            pass

    # peewee 元类处理时嵌套类闭包变量不可见，需在类创建后设置表名
    LiveSession._meta.table_name = table_name  # type: ignore[attr-defined]

    return LiveSession


def _make_live_trade_model(table_name: str) -> type[BaseLiveModel]:
    """工厂函数：返回映射到指定表名的 LiveTrade Model

    Args:
        table_name: "test_trades" 或 "live_trades"
    """

    class LiveTrade(BaseLiveModel):
        session_id: IntegerField = IntegerField()  # FK → LiveSession.id
        datetime: DateTimeField = DateTimeField()  # test=信号时间, live=成交时间
        symbol: CharField = CharField(max_length=20)
        direction: CharField = CharField(max_length=10)  # long / short
        offset: CharField = CharField(max_length=10)  # open / close
        price: FloatField = FloatField()  # test=触发价, live=成交价
        quantity: FloatField = FloatField()  # 数量（手）
        pnl: FloatField = FloatField(null=True)  # test 时为 NULL
        commission: FloatField = FloatField(null=True)  # test 时为 NULL
        reason: CharField = CharField(max_length=512, default="")
        created_at: DateTimeField = DateTimeField(constraints=[SQL("DEFAULT CURRENT_TIMESTAMP")])

        class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
            pass

    LiveTrade._meta.table_name = table_name  # type: ignore[attr-defined]

    return LiveTrade


# 公开工厂函数（供 cli/commands/test.py 和 live.py 使用）
def get_live_session_model(table_name: str) -> type[BaseLiveModel]:
    """获取映射到指定表名的 LiveSession Model"""
    return _make_live_session_model(table_name)


def get_live_trade_model(table_name: str) -> type[BaseLiveModel]:
    """获取映射到指定表名的 LiveTrade Model"""
    return _make_live_trade_model(table_name)


def init_database(db_path: str) -> None:
    """初始化数据库连接"""
    database.init(db_path)  # pyright: ignore[reportUnknownMemberType]
    database.create_tables(
        [Run, RunStudy, ExportMetadata, OperationLog, Backtest, BacktestParam, BacktestTrade, BacktestDaily], safe=True
    )  # pyright: ignore[reportUnknownMemberType]


def close_database() -> None:
    """关闭数据库连接"""
    if not database.is_closed():
        _ = database.close()
