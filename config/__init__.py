"""
配置管理模块

基于 Pydantic 的强类型配置系统。

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

from .app_config import (
    # 子模型
    AccountInfo,
    AppConfig,
    BacktestConfig,
    ConfigManager,
    DataConfig,
    EnvironmentConfig,
    LoggingConfig,
    ProjectConfig,
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
