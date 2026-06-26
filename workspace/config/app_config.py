"""向后兼容入口 — 从 manager.py 和 schemas.py 重新导出

本文件保留以维持现有代码的导入路径（如 `from config.app_config import X`）。
新代码建议直接从 `config` 顶层导入。
"""

from .manager import (
    ConfigManager,
    ProjectConfig,
)
from .schemas import (
    CLI_DATA_ENVIRONMENTS,
    VALID_DATA_ENVIRONMENTS,
    AccountInfo,
    AppConfig,
    BacktestConfig,
    DataConfig,
    DataEnvironment,
    EnvironmentConfig,
    LoggingConfig,
    OptimizerConfig,
    StrategyItemConfig,
    SystemConfig,
    ThirdPartyConfig,
    ThirdPartyServiceConfig,
)

__all__ = [
    "ProjectConfig",
    "ConfigManager",
    "StrategyItemConfig",
    "OptimizerConfig",
    "BacktestConfig",
    "DataConfig",
    "DataEnvironment",
    "VALID_DATA_ENVIRONMENTS",
    "CLI_DATA_ENVIRONMENTS",
    "LoggingConfig",
    "SystemConfig",
    "ThirdPartyServiceConfig",
    "ThirdPartyConfig",
    "AccountInfo",
    "AppConfig",
    "EnvironmentConfig",
]
