"""配置管理模块

基于 Pydantic 的强类型配置系统。

模块结构:
- schemas.py: 所有 Pydantic 配置模型定义
- manager.py: ProjectConfig（加载与单例）+ ConfigManager（门面）
- app_config.py: 向后兼容入口（从 manager + schemas 重新导出）

统一入口:
    from config import ProjectConfig

    cfg = ProjectConfig.instance()                        # 单例
    bc = cfg.backtest                                    # → BacktestConfig
    sc = cfg.get_strategy_config("ma")                   # → StrategyItemConfig

ConfigManager 提供统一的配置访问方式（与 ProjectConfig.instance() 行为一致）:
    from config import ConfigManager

    cm = ConfigManager()
    bc = cm.get_backtest_config()
"""

from .manager import (
    ConfigManager,
    ProjectConfig,
)
from .schemas import (
    AccountInfo,
    AppConfig,
    BacktestConfig,
    DataConfig,
    EnvironmentConfig,
    LoggingConfig,
    StrategyItemConfig,
    SystemConfig,
    ThirdPartyConfig,
    ThirdPartyServiceConfig,
)

__all__ = [
    "ProjectConfig",
    "ConfigManager",
    "AccountInfo",
    "AppConfig",
    "BacktestConfig",
    "DataConfig",
    "EnvironmentConfig",
    "LoggingConfig",
    "StrategyItemConfig",
    "SystemConfig",
    "ThirdPartyConfig",
    "ThirdPartyServiceConfig",
]
