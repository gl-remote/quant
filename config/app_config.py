"""应用配置 — Pydantic 全量模型 + 统一单例入口

层级结构:
    ProjectConfig (根模型，单例 & 统一访问入口)
    ├── app:             AppConfig
    ├── environment:     EnvironmentConfig
    ├── strategies:      list[StrategyItemConfig]
    ├── data:            DataConfig (包含数据源、存储、导出配置)
    ├── backtest:        BacktestConfig
    ├── system:          SystemConfig
    │   └── logging:     LoggingConfig
    ├── third_party:     ThirdPartyConfig
    │   └── services:    list[ThirdPartyServiceConfig]
    └── account:         AccountInfo | None

设计原则:
    - 所有配置读取方法返回 Pydantic 模型，禁止裸露 dict
    - ProjectConfig.instance() 是唯一配置加载入口
    - CLI 层按需组合 BacktestConfig + StrategyItemConfig → 直接传给 engine/strategy

用法:
    from config import ProjectConfig

    cfg = ProjectConfig.instance()                        # 单例
    bc = cfg.backtest                                    # → BacktestConfig
    sc = cfg.get_strategy_config("ma")                   # → StrategyItemConfig
"""

import os
import tomllib  # pyright: ignore[reportMissingImports]
from pathlib import Path
from typing import Any, ClassVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from common.constants import (
    DEFAULT_COMMISSION_RATE,
    DEFAULT_CONTRACT_SIZE,
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_KLINE_PERIOD,
    DEFAULT_POSITION_RATIO,
    DEFAULT_PRICE_TICK,
    DEFAULT_SLIPPAGE,
    DEFAULT_SMA_LONG,
    DEFAULT_SMA_SHORT,
    DEFAULT_STOP_LOSS_RATIO,
    DEFAULT_TAKE_PROFIT_RATIO,
    KLINE_INTERVAL_1MIN,
    STRATEGY_MA,
)

# ============================================================
# 策略配置
# ============================================================


class StrategyItemConfig(BaseModel):
    """单个策略配置项。extra="allow" 允许策略自定义参数字段。"""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")

    name: str
    enabled: bool = True
    # 以下是 MA 策略通用字段（其他策略可忽略/覆盖）
    sma_short: int = DEFAULT_SMA_SHORT
    sma_long: int = DEFAULT_SMA_LONG
    stop_loss_ratio: float = DEFAULT_STOP_LOSS_RATIO
    take_profit_ratio: float = DEFAULT_TAKE_PROFIT_RATIO
    position_ratio: float = DEFAULT_POSITION_RATIO
    kline_period: int = DEFAULT_KLINE_PERIOD
    # ATR 相关参数
    atr_period: int = 14
    atr_stop_loss_multiplier: float = 2.0
    atr_take_profit_multiplier: float = 3.0
    # 回撤止盈参数
    trailing_activation_atr: float = 1.0
    """移动止盈激活阈值（ATR 倍数），盈利超过 atr * activation 后启动跟踪，默认 1.0"""
    trailing_drawdown_ratio: float = 0.25
    """移动止盈回撤比例，激活后从最高价回落超过此比例触发止盈，默认 0.25 (25%)"""
    # 策略专属的参数搜索空间（同时支持 grid 和 bayesian 模式）
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
    """参数优化器配置。

    基于 Optuna 的统一优化框架，支持两种搜索模式：
    - engine: "grid" — 使用 GridSampler 穷举搜索
    - engine: "bayesian" — 使用 TPESampler 贝叶斯优化

    注意：本优化器强制单线程执行（n_jobs=1），
    因为 vnpy BacktestingEngine 非线程安全。
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    enabled: bool = False
    engine: str = "grid"  # grid | bayesian
    n_trials: int = 50
    use_fixed_seed: bool = False  # 是否使用固定随机种子，默认不使用（随机）
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
    interval: str = KLINE_INTERVAL_1MIN
    provider: str = ""  # 回测优先数据源，空字符串 = 自动遍历所有

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


class DataConfig(BaseModel):
    provider: str = "tqsdk"
    cache_enabled: bool = False
    base_dir: str = ""
    export_dir: str = ""
    db_path: str = ""
    filename_template: str = "{symbol}.{provider}.{interval}.csv"  # 文件名模板：标的名.数据源.数据周期.csv


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


# ============================================================
# 应用 & 环境
# ============================================================


class AppConfig(BaseModel):
    name: str = ""
    version: str = ""
    mode: str = "test"  # test / backtest / live


class EnvironmentConfig(BaseModel):
    name: str = "development"
    debug: bool = True


# ============================================================
# 根配置 — 启动时加载一次
# ============================================================

# 模块级单例（避免 Pydantic PrivateAttr 的类级访问问题）
_project_config_instance: "ProjectConfig | None" = None


class ProjectConfig(BaseModel):
    """全局配置根模型。

    启动时通过 ProjectConfig.load() 加载 TOML 并解析环境变量，
    后续通过 ProjectConfig.instance() 获取单例。

    所有配置读取方法返回 Pydantic 模型，禁止裸露 dict。
    统一入口: ProjectConfig.instance()
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    app: AppConfig = Field(default_factory=AppConfig)
    environment: EnvironmentConfig = Field(default_factory=EnvironmentConfig)
    strategies: list[StrategyItemConfig] = Field(default_factory=list)
    data: DataConfig = Field(default_factory=DataConfig)
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)
    optimizer: OptimizerConfig = Field(default_factory=OptimizerConfig)
    system: SystemConfig = Field(default_factory=SystemConfig)
    third_party: ThirdPartyConfig = Field(default_factory=ThirdPartyConfig)
    account: AccountInfo | None = None

    # --------------------------------------------------
    # 单例（使用模块级变量，避免 Pydantic PrivateAttr）
    # --------------------------------------------------

    @classmethod
    def instance(
        cls,
        config_file: str | None = None,
    ) -> "ProjectConfig":
        """获取全局单例（首次调用时自动加载 TOML）

        Args:
            config_file: 可选 TOML 路径，传入时（重新）加载
        """
        global _project_config_instance
        if _project_config_instance is None or config_file is not None:
            _project_config_instance = cls.load(config_file)
        return _project_config_instance

    @classmethod
    def reset(cls) -> None:
        """清空单例（仅供测试使用）"""
        global _project_config_instance
        _project_config_instance = None

    # --------------------------------------------------
    # 工厂方法
    # --------------------------------------------------

    @classmethod
    def load(
        cls,
        config_file: str | None = None,
        project_root: Path | None = None,
    ) -> "ProjectConfig":
        """从 TOML 加载配置，解析路径和环境变量。

        Args:
            config_file: TOML 配置文件路径，None 则使用默认 conf.toml
            project_root: 项目根目录，None 则自动推断
        """
        if project_root is None:
            project_root = Path(__file__).parent.parent
        if config_file is None:
            config_file = str(Path(__file__).parent / "conf.toml")

        raw = cls._parse_toml(config_file, Path(__file__).parent)
        # 解析相对路径 → 绝对路径
        cls._resolve_data_paths(raw, project_root)
        cls._resolve_backtest_paths(raw, project_root)
        # 解析账户凭证
        raw = cls._resolve_account(raw)
        # 设置 app/environment 默认值（如果 TOML 中未配置）
        raw.setdefault("app", {})
        raw.setdefault("environment", {})
        raw.setdefault("strategies", [])
        return cls(**raw)

    @classmethod
    def _parse_toml(cls, config_file: str, config_dir: Path) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
        """读取基础配置 + local 覆盖，返回合并后的字典"""
        base_path = Path(config_file)
        config: dict[str, Any] = {}  # pyright: ignore[reportExplicitAny]
        if base_path.exists():
            with open(base_path, "rb") as f:
                config = tomllib.load(f)

        local_path = config_dir / "conf.local.toml"
        if local_path.exists():
            with open(local_path, "rb") as f:
                cls._deep_merge(config, tomllib.load(f))
        return config

    @staticmethod
    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> None:  # pyright: ignore[reportExplicitAny]
        for k, v in override.items():
            if isinstance(v, dict) and isinstance(base.get(k), dict):
                ProjectConfig._deep_merge(base[k], v)
            else:
                base[k] = v

    @staticmethod
    def _resolve_data_paths(raw: dict[str, Any], root: Path) -> None:  # pyright: ignore[reportExplicitAny]
        dc = raw.setdefault("data", {})
        for key in ("base_dir", "export_dir", "db_path"):
            val = dc.get(key, "")
            if val and not Path(val).is_absolute():
                dc[key] = str(root / val)

    @staticmethod
    def _resolve_backtest_paths(raw: dict[str, Any], root: Path) -> None:  # pyright: ignore[reportExplicitAny]
        bc = raw.get("backtest", {})
        data_dir = bc.get("data_dir", "")
        if data_dir and not Path(data_dir).is_absolute():
            bc["data_dir"] = str(root / data_dir)

    @staticmethod
    def _resolve_account(raw: dict[str, Any]) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
        """解析账户信息：环境变量优先，其次 TOML config"""
        ak = os.environ.get("TQSDK_API_KEY", "")
        sk = os.environ.get("TQSDK_API_SECRET", "")
        if ak and sk:
            raw["account"] = {"api_key": ak, "api_secret": sk}
            return raw

        services = raw.get("third_party", {}).get("services", [])
        for svc in services:
            if svc.get("name") == "tqsdk":
                ak = svc.get("api_key", "")
                sk = svc.get("api_secret", "")
                placeholders = {
                    "PLACEHOLDER_API_KEY",
                    "PLACEHOLDER_API_SECRET",
                    "your_api_key_here",
                    "your_api_secret_here",
                }
                if ak and ak not in placeholders and sk and sk not in placeholders:
                    raw["account"] = {"api_key": ak, "api_secret": sk}
                break
        return raw

    # --------------------------------------------------
    # 查询方法
    # --------------------------------------------------

    def get_strategy_config(self, strategy_name: str = STRATEGY_MA) -> StrategyItemConfig:
        """按名称查找策略配置 (返回 Pydantic 模型)"""
        for s in self.strategies:
            if s.name == strategy_name:
                return s
        # 返回默认配置
        return StrategyItemConfig(name=strategy_name)

    def get_trading_config(self, strategy_name: str = STRATEGY_MA) -> StrategyItemConfig:
        """获取交易配置 (返回 Pydantic 模型)"""
        return self.get_strategy_config(strategy_name)

    def get_account_info(self) -> AccountInfo | None:
        """获取账户凭证 (返回 Pydantic 模型)"""
        return self.account

    def find_service(self, name: str) -> ThirdPartyServiceConfig | None:
        for s in self.third_party.services:
            if s.name == name:
                return s
        return None

    @property
    def is_valid(self) -> bool:
        """检查配置是否通过 Pydantic 校验"""
        try:
            # 重校验自身及子模型
            _ = self.model_validate(self.model_dump())
            return True
        except Exception:
            return False


# ============================================================
# 单例访问门面 — 向后兼容
# ============================================================


class ConfigManager:
    """配置访问入口 — 委托 ProjectConfig 单例，向后兼容

    所有方法返回 Pydantic 模型，消除裸露 dict。
    统一入口: `cm = ConfigManager()` 等价于 `cfg = ProjectConfig.instance()`
    ConfigManager 本身不维护状态，每次实例化创建轻量 wrapper 指向同一 ProjectConfig 单例。

    用法:
        cm = ConfigManager()                                    # 轻量 wrapper
        bc = cm.get_backtest_config()                           # → BacktestConfig
        tc = cm.get_trading_config()                            # → StrategyItemConfig
        ai = cm.get_account_info()                              # → AccountInfo | None
    """

    _config: ProjectConfig

    def __init__(self, config_file: str | None = None):
        self._config = ProjectConfig.instance(config_file)

    # --------------------------------------------------
    # 策略配置（全部返回 Pydantic 模型）
    # --------------------------------------------------

    def get_strategy_config(self, strategy_name: str = STRATEGY_MA) -> StrategyItemConfig:
        """获取指定策略的配置 (返回 StrategyItemConfig 模型)"""
        return self._config.get_strategy_config(strategy_name)

    def get_strategy_item(self, strategy_name: str = STRATEGY_MA) -> StrategyItemConfig:
        """获取策略配置的 Pydantic 模型 (同 get_strategy_config)"""
        return self._config.get_strategy_config(strategy_name)

    def get_strategy_list(self) -> list[StrategyItemConfig]:
        """获取所有已配置的策略"""
        return list(self._config.strategies)

    def get_trading_config(self, strategy_name: str = STRATEGY_MA) -> StrategyItemConfig:
        """获取交易配置 (返回 StrategyItemConfig 模型)"""
        return self._config.get_strategy_config(strategy_name)

    # --------------------------------------------------
    # 账户
    # --------------------------------------------------

    def get_account_info(self) -> AccountInfo | None:
        """获取账户凭证 (返回 AccountInfo 模型)"""
        return self._config.account

    # --------------------------------------------------
    # 回测
    # --------------------------------------------------

    def get_backtest_config(self) -> BacktestConfig:
        return self._config.backtest

    # --------------------------------------------------
    # 数据
    # --------------------------------------------------

    def get_data_config(self) -> DataConfig:
        return self._config.data

    # --------------------------------------------------
    # 系统
    # --------------------------------------------------

    def get_system_logging_config(self) -> LoggingConfig:
        return self._config.system.logging

    # --------------------------------------------------
    # 优化器
    # --------------------------------------------------

    def get_optimizer_config(self) -> OptimizerConfig:
        return self._config.optimizer

    # --------------------------------------------------
    # 校验
    # --------------------------------------------------

    def validate_config(self) -> bool:
        """校验配置合法性（Pydantic 自带 + 自定义约束）"""
        try:
            if not self._config.is_valid:
                return False
            return all(not (s.name == STRATEGY_MA and s.sma_short >= s.sma_long) for s in self._config.strategies)
        except Exception:
            return False

    # --------------------------------------------------
    # 重置（测试用）
    # --------------------------------------------------

    @classmethod
    def reset(cls) -> None:
        """清空单例（仅供测试使用）"""
        ProjectConfig.reset()
