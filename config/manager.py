"""配置加载与单例管理

ProjectConfig: 根配置模型 + TOML 加载 + 环境变量解析
ConfigManager: 轻量门面，委托 ProjectConfig.instance()，向后兼容

用法:
    from config.manager import ProjectConfig, ConfigManager

    cfg = ProjectConfig.instance()              # 单例
    cm = ConfigManager()                        # 轻量 wrapper
    bc = cm.get_backtest_config()               # → BacktestConfig
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from common.constants import (
    STRATEGY_MA,
)

from .schemas import (
    AccountInfo,
    AppConfig,
    BacktestConfig,
    DataConfig,
    EnvironmentConfig,
    LoggingConfig,
    OptimizerConfig,
    StrategyItemConfig,
    SystemConfig,
    ThirdPartyConfig,
    ThirdPartyServiceConfig,
)

# 模块级单例（避免 Pydantic PrivateAttr 的类级访问问题）
_project_config_instance: ProjectConfig | None = None


class ProjectConfig(BaseModel):
    """全局配置根模型

    启动时通过 ProjectConfig.load() 加载 TOML 并解析环境变量，
    后续通过 ProjectConfig.instance() 获取单例。

    所有配置读取方法返回 Pydantic 模型，禁止裸露 dict。
    统一入口: ProjectConfig.instance()
    """

    model_config = ConfigDict(extra="forbid")

    app: AppConfig = Field(default_factory=AppConfig)
    environment: EnvironmentConfig = Field(default_factory=EnvironmentConfig)
    strategies: list[StrategyItemConfig] = Field(default_factory=list)
    data: DataConfig = Field(default_factory=DataConfig)
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)
    optimizer: OptimizerConfig = Field(default_factory=OptimizerConfig)
    system: SystemConfig = Field(default_factory=SystemConfig)
    third_party: ThirdPartyConfig = Field(default_factory=ThirdPartyConfig)
    account: AccountInfo | None = None

    # ── 单例 ──────────────────────────────────────────────

    @classmethod
    def instance(cls, config_file: str | None = None) -> ProjectConfig:
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

    # ── 工厂方法 ──────────────────────────────────────────

    @classmethod
    def load(
        cls,
        config_file: str | None = None,
        project_root: Path | None = None,
    ) -> ProjectConfig:
        """从 TOML 加载配置，解析路径和环境变量

        Args:
            config_file: TOML 配置文件路径，None 则使用默认 conf.toml
            project_root: 项目根目录，None 则自动推断
        """
        if project_root is None:
            project_root = Path(__file__).parent.parent
        if config_file is None:
            config_file = str(Path(__file__).parent / "conf.toml")

        raw = cls._parse_toml(config_file, Path(__file__).parent)
        cls._resolve_data_paths(raw, project_root)
        cls._resolve_backtest_paths(raw, project_root)
        raw = cls._resolve_account(raw)
        raw.setdefault("app", {})
        raw.setdefault("environment", {})
        raw.setdefault("strategies", [])
        return cls(**raw)

    @classmethod
    def _parse_toml(cls, config_file: str, config_dir: Path) -> dict[str, Any]:
        """读取基础配置 + local 覆盖，返回合并后的字典"""
        base_path = Path(config_file)
        config: dict[str, Any] = {}
        if base_path.exists():
            with open(base_path, "rb") as f:
                config = tomllib.load(f)

        local_path = config_dir / "conf.local.toml"
        if local_path.exists():
            with open(local_path, "rb") as f:
                cls._deep_merge(config, tomllib.load(f))
        return config

    @staticmethod
    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> None:
        for k, v in override.items():
            if isinstance(v, dict) and isinstance(base.get(k), dict):
                ProjectConfig._deep_merge(base[k], v)
            else:
                base[k] = v

    @staticmethod
    def _resolve_data_paths(raw: dict[str, Any], root: Path) -> None:
        dc = raw.setdefault("data", {})
        for key in ("base_dir", "export_dir", "db_path"):
            val = dc.get(key, "")
            if val and not Path(val).is_absolute():
                dc[key] = str(root / val)

    @staticmethod
    def _resolve_backtest_paths(raw: dict[str, Any], root: Path) -> None:
        bc = raw.get("backtest", {})
        data_dir = bc.get("data_dir", "")
        if data_dir and not Path(data_dir).is_absolute():
            bc["data_dir"] = str(root / data_dir)

    @staticmethod
    def _resolve_account(raw: dict[str, Any]) -> dict[str, Any]:
        """解析账户信息：环境变量优先，其次 TOML config

        【优先级规则】
        1. 若同时设置了 TQSDK_API_KEY 和 TQSDK_API_SECRET → 使用环境变量
        2. 否则扫描 third_party.services 找 name="tqsdk" 的条目
        3. 找到则使用其 api_key/api_secret，但会排除 PLACEHOLDER_* / your_api_* 等占位符

        【为什么只设置一个环境变量会被忽略】
        必须两个变量都非空才会走环境变量路径；只设一个会让整条规则不触发，
        直接回退到 TOML config。这是为了避免"半配置"状态导致的调试混乱。
        """
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

    # ── 查询方法 ──────────────────────────────────────────

    def get_strategy_config(self, strategy_name: str = STRATEGY_MA) -> StrategyItemConfig:
        """按名称查找策略配置（返回 Pydantic 模型）"""
        for s in self.strategies:
            if s.name == strategy_name:
                return s
        return StrategyItemConfig(name=strategy_name)

    def get_trading_config(self, strategy_name: str = STRATEGY_MA) -> StrategyItemConfig:
        """获取交易配置（返回 Pydantic 模型）"""
        return self.get_strategy_config(strategy_name)

    def get_account_info(self) -> AccountInfo | None:
        """获取账户凭证（返回 Pydantic 模型）"""
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
            _ = self.model_validate(self.model_dump())
            return True
        except Exception:
            return False


class ConfigManager:
    """配置访问入口 — 委托 ProjectConfig 单例，向后兼容

    所有方法返回 Pydantic 模型，消除裸露 dict。
    统一入口: `cm = ConfigManager()` 等价于 `cfg = ProjectConfig.instance()`
    ConfigManager 本身不维护状态，每次实例化创建轻量 wrapper 指向同一 ProjectConfig 单例。

    用法:
        cm = ConfigManager()
        bc = cm.get_backtest_config()          # → BacktestConfig
        tc = cm.get_trading_config()            # → StrategyItemConfig
        ai = cm.get_account_info()              # → AccountInfo | None
    """

    _config: ProjectConfig

    def __init__(self, config_file: str | None = None) -> None:
        self._config = ProjectConfig.instance(config_file)

    # ── 策略配置 ──────────────────────────────────────────

    def get_strategy_config(self, strategy_name: str = STRATEGY_MA) -> StrategyItemConfig:
        return self._config.get_strategy_config(strategy_name)

    def get_strategy_item(self, strategy_name: str = STRATEGY_MA) -> StrategyItemConfig:
        return self._config.get_strategy_config(strategy_name)

    def get_strategy_list(self) -> list[StrategyItemConfig]:
        return list(self._config.strategies)

    def get_trading_config(self, strategy_name: str = STRATEGY_MA) -> StrategyItemConfig:
        return self._config.get_strategy_config(strategy_name)

    # ── 账户 ──────────────────────────────────────────────

    def get_account_info(self) -> AccountInfo | None:
        return self._config.account

    # ── 回测 ──────────────────────────────────────────────

    def get_backtest_config(self) -> BacktestConfig:
        return self._config.backtest

    # ── 数据 ──────────────────────────────────────────────

    def get_data_config(self) -> DataConfig:
        return self._config.data

    # ── 系统 ──────────────────────────────────────────────

    def get_system_logging_config(self) -> LoggingConfig:
        return self._config.system.logging

    # ── 优化器 ────────────────────────────────────────────

    def get_optimizer_config(self) -> OptimizerConfig:
        return self._config.optimizer

    # ── 校验 ──────────────────────────────────────────────

    def validate_config(self) -> bool:
        try:
            if not self._config.is_valid:
                return False
            return all(not (s.name == STRATEGY_MA and s.sma_short >= s.sma_long) for s in self._config.strategies)
        except Exception:
            return False

    # ── 重置（测试用） ────────────────────────────────────

    @classmethod
    def reset(cls) -> None:
        ProjectConfig.reset()
