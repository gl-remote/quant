"""Pydantic 配置模型定义

按职责划分的配置模型集合：
- 策略配置：StrategyItemConfig
- 参数优化：OptimizerConfig
- 回测配置：BacktestConfig
- 数据配置：DataConfig
- 系统配置：LoggingConfig, SystemConfig
- 第三方服务：ThirdPartyServiceConfig, ThirdPartyConfig
- 账户信息：AccountInfo
- 应用环境：AppConfig, EnvironmentConfig
- 根配置：ProjectConfig

所有模型仅包含数据定义和验证逻辑，加载路径由 ProjectConfig 负责。
"""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from common.constants import (
    DEFAULT_COMMISSION_RATE,
    DEFAULT_CONTRACT_SIZE,
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_POSITION_RATIO,
    DEFAULT_PRICE_TICK,
    DEFAULT_SLIPPAGE,
)
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

# ============================================================
# 策略配置
# ============================================================


class StrategyItemConfig(BaseModel):
    """单个策略配置项。extra=\"allow\" 允许策略自定义参数字段。"""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")

    name: str
    enabled: bool = True
    sma_short: int = 10
    sma_long: int = 40
    stop_loss_ratio: float = 0.03
    take_profit_ratio: float = 0.05
    position_ratio: float = DEFAULT_POSITION_RATIO
    kline_period: int = 5
    atr_period: int = 14
    atr_stop_loss_multiplier: float = 2.0
    atr_take_profit_multiplier: float = 3.0
    trailing_activation_atr: float = 1.0
    trailing_drawdown_ratio: float = 0.25
    kdj_pullback_long: int = 45
    kdj_pullback_short: int = 55
    search_space: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @field_validator("stop_loss_ratio", "take_profit_ratio", "position_ratio")
    @classmethod
    def _ratio_in_range(cls, v: float) -> float:
        if not (0 < v <= 1):
            raise ValueError(f"ratio must be in (0, 1], got {v}")
        return v

    @field_validator("sma_short")
    @classmethod
    def _sma_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(f"sma_short must be positive, got {v}")
        return v


# ============================================================
# 参数优化
# ============================================================


class OptimizerConfig(BaseModel):
    """参数优化器配置

    基于 Optuna 的统一优化框架，支持两种搜索模式：
    - engine: \"grid\" — 使用 GridSampler 穷举搜索
    - engine: \"bayesian\" — 使用 TPESampler 贝叶斯优化

    注意：
    - 串行模式（默认）：n_jobs=1，vnpy 引擎非线程安全
    - 并行模式（CLI --parallel）：使用 multiprocessing 进程隔离，可安全并行
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    enabled: bool = False
    engine: str = "grid"
    n_trials: int = 50
    early_stop_patience: int = 0
    use_fixed_seed: bool = False
    random_seed: int = 42
    search_space: dict[str, dict[str, Any]] = Field(default_factory=dict)
    strategy_spaces: dict[str, dict[str, dict[str, Any]]] = Field(default_factory=dict)


# ============================================================
# 回测配置
# ============================================================


class BacktestConfig(BaseModel):
    initial_capital: float = DEFAULT_INITIAL_CAPITAL
    commission_rate: float = DEFAULT_COMMISSION_RATE
    slippage: float = DEFAULT_SLIPPAGE
    price_tick: float = DEFAULT_PRICE_TICK
    contract_size: int = DEFAULT_CONTRACT_SIZE
    interval: str = "1m"
    provider: str = ""

    @field_validator("initial_capital")
    @classmethod
    def _capital_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(f"initial_capital must be > 0, got {v}")
        return v

    @field_validator("commission_rate")
    @classmethod
    def _commission_in_range(cls, v: float) -> float:
        if not (0 <= v < 1):
            raise ValueError(f"commission_rate must be in [0, 1), got {v}")
        return v

    @field_validator("slippage")
    @classmethod
    def _slippage_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError(f"slippage must be >= 0, got {v}")
        return v

    @field_validator("price_tick", "contract_size")
    @classmethod
    def _positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(f"must be > 0, got {v}")
        return v


# ============================================================
# 数据配置
# ============================================================


DataEnvironment = Literal["backtest", "test", "live", "unit_test"]
VALID_DATA_ENVIRONMENTS: set[str] = {"backtest", "test", "live", "unit_test"}
CLI_DATA_ENVIRONMENTS: set[str] = {"backtest", "test", "live"}


class DataConfig(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    provider: str = "tqsdk"
    cache_enabled: bool = False
    environment: DataEnvironment
    base_dir: str = ""
    export_dir: str = ""
    database_path: str
    filename_template: str = "{symbol}.{provider}.{interval}.csv"


# ============================================================
# 系统配置
# ============================================================


class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: str = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{line} | {message}"


class SystemConfig(BaseModel):
    modules: list[str] = Field(default_factory=list)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


# ============================================================
# 第三方服务 & 账户
# ============================================================


class ThirdPartyServiceConfig(BaseModel):
    name: str
    provider: str = ""
    api_key: str = ""
    api_secret: str = ""
    enabled: bool = True

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")


class ThirdPartyConfig(BaseModel):
    services: list[ThirdPartyServiceConfig] = Field(default_factory=list)


class AccountInfo(BaseModel):
    api_key: str
    api_secret: str
    account_type: str = "tqsim"
    broker_id: str = ""
    broker_user: str = ""
    broker_password: str = ""


# ============================================================
# 应用 & 环境
# ============================================================


class AppConfig(BaseModel):
    name: str = ""
    version: str = ""
    mode: str = "test"


class EnvironmentConfig(BaseModel):
    name: str = "development"
    debug: bool = True
