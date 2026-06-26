"""config/ 配置管理测试

覆盖:
    - ConfigManager 加载、默认值、验证
    - Pydantic 验证 / 环境变量优先级
    - 数据/导出/日志配置
"""

import os
import tempfile

import pytest
import tomli_w
from config.app_config import ConfigManager, ProjectConfig
from pydantic import ValidationError


class TestConfigLoading:
    def test_load_from_temp_file(self, temp_config_file):
        cm = ConfigManager(config_file=temp_config_file)
        tc = cm.get_trading_config()
        assert tc.sma_short == 10
        assert tc.sma_long == 40
        assert tc.stop_loss_ratio == 0.03

    def test_defaults_when_no_config(self):
        cm = ConfigManager(env="backtest")
        tc = cm.get_trading_config()
        assert tc.sma_short == 3
        assert tc.position_ratio == 1.0


class TestTradingConfig:
    def test_get_trading_config_defaults(self):
        cm = ConfigManager(env="backtest")
        tc = cm.get_trading_config()
        assert tc.stop_loss_ratio == 0.3
        assert tc.take_profit_ratio == 0.5
        assert tc.position_ratio == 1.0
        assert tc.sma_short == 3
        assert tc.sma_long == 10
        assert tc.kline_period == 1

    def test_get_trading_config_from_file(self, temp_config_file):
        cm = ConfigManager(config_file=temp_config_file)
        tc = cm.get_trading_config()
        assert tc.sma_short == 10
        assert tc.sma_long == 40


class TestBacktestConfig:
    def test_get_backtest_config_defaults(self):
        cm = ConfigManager(env="backtest")
        bc = cm.get_backtest_config()
        assert bc.initial_capital == 100000.0
        assert bc.commission_rate == 0.0003
        assert bc.slippage == 1.0
        assert bc.price_tick == 1.0
        assert bc.contract_size == 5
        assert bc.interval == "5m"


class TestValidateConfig:
    def test_valid_default_config(self, temp_config_file):
        cm = ConfigManager(config_file=temp_config_file)
        assert cm.validate_config() is True

    def test_invalid_stop_loss_ratio(self, base_config_dict):
        """stop_loss_ratio=0 → Pydantic field_validator 拒绝"""
        base_config_dict["strategies"][0]["stop_loss_ratio"] = 0.0
        fd, path = tempfile.mkstemp(suffix=".toml")
        with open(fd, "wb") as f:
            f.write(tomli_w.dumps(base_config_dict).encode("utf-8"))
        with pytest.raises(ValidationError):
            ConfigManager(config_file=path)
        os.unlink(path)

    def test_invalid_sma_ordering(self, base_config_dict):
        """sma_short >= sma_long → validate_config 返回 False"""
        base_config_dict["strategies"][0]["sma_short"] = 30
        base_config_dict["strategies"][0]["sma_long"] = 10
        fd, path = tempfile.mkstemp(suffix=".toml")
        with open(fd, "wb") as f:
            f.write(tomli_w.dumps(base_config_dict).encode("utf-8"))
        cm = ConfigManager(config_file=path)
        assert cm.validate_config() is False
        os.unlink(path)

    def test_invalid_commission_rate(self, base_config_dict):
        """commission_rate=1.5 → Pydantic field_validator 拒绝"""
        base_config_dict["backtest"]["commission_rate"] = 1.5
        fd, path = tempfile.mkstemp(suffix=".toml")
        with open(fd, "wb") as f:
            f.write(tomli_w.dumps(base_config_dict).encode("utf-8"))
        with pytest.raises(ValidationError):
            ConfigManager(config_file=path)
        os.unlink(path)

    def test_invalid_negative_slippage(self, base_config_dict):
        """slippage=-1 → Pydantic field_validator 拒绝"""
        base_config_dict["backtest"]["slippage"] = -1.0
        fd, path = tempfile.mkstemp(suffix=".toml")
        with open(fd, "wb") as f:
            f.write(tomli_w.dumps(base_config_dict).encode("utf-8"))
        with pytest.raises(ValidationError):
            ConfigManager(config_file=path)
        os.unlink(path)

    def test_invalid_price_tick(self, base_config_dict):
        """price_tick=0 → Pydantic field_validator 拒绝"""
        base_config_dict["backtest"]["price_tick"] = 0
        fd, path = tempfile.mkstemp(suffix=".toml")
        with open(fd, "wb") as f:
            f.write(tomli_w.dumps(base_config_dict).encode("utf-8"))
        with pytest.raises(ValidationError):
            ConfigManager(config_file=path)
        os.unlink(path)


class TestAccountInfo:
    """测试 _resolve_account 逻辑：环境变量优先 + 占位符过滤"""

    def test_no_services(self, base_config_dict, monkeypatch):
        monkeypatch.delenv("TQSDK_API_KEY", raising=False)
        monkeypatch.delenv("TQSDK_API_SECRET", raising=False)
        base_config_dict.pop("third_party", None)
        result = ProjectConfig._resolve_account(base_config_dict)
        assert result.get("account") is None

    def test_placeholder_values(self, base_config_dict, monkeypatch):
        monkeypatch.delenv("TQSDK_API_KEY", raising=False)
        monkeypatch.delenv("TQSDK_API_SECRET", raising=False)
        base_config_dict["third_party"] = {
            "services": [
                {
                    "name": "tqsdk",
                    "api_key": "PLACEHOLDER_API_KEY",
                    "api_secret": "PLACEHOLDER_API_SECRET",
                }
            ]
        }
        result = ProjectConfig._resolve_account(base_config_dict)
        assert result.get("account") is None

    def test_valid_keys(self, base_config_dict, monkeypatch):
        monkeypatch.delenv("TQSDK_API_KEY", raising=False)
        monkeypatch.delenv("TQSDK_API_SECRET", raising=False)
        base_config_dict["third_party"] = {
            "services": [
                {
                    "name": "tqsdk",
                    "api_key": "real_key_123",
                    "api_secret": "real_secret_456",
                }
            ]
        }
        result = ProjectConfig._resolve_account(base_config_dict)
        assert result["account"]["api_key"] == "real_key_123"
        assert result["account"]["api_secret"] == "real_secret_456"

    def test_account_fields_from_config(self, base_config_dict, monkeypatch):
        monkeypatch.delenv("TQSDK_API_KEY", raising=False)
        monkeypatch.delenv("TQSDK_API_SECRET", raising=False)
        base_config_dict["third_party"] = {
            "services": [
                {
                    "name": "tqsdk",
                    "api_key": "real_key_123",
                    "api_secret": "real_secret_456",
                    "account_type": "tqaccount",
                    "broker_id": "BROKER",
                    "broker_user": "USER",
                    "broker_password": "PASS",
                }
            ]
        }
        result = ProjectConfig._resolve_account(base_config_dict)
        assert result["account"]["account_type"] == "tqaccount"
        assert result["account"]["broker_id"] == "BROKER"
        assert result["account"]["broker_user"] == "USER"
        assert result["account"]["broker_password"] == "PASS"

    def test_env_var_priority_over_config(self, monkeypatch, base_config_dict):
        monkeypatch.setenv("TQSDK_API_KEY", "env_key_abc")
        monkeypatch.setenv("TQSDK_API_SECRET", "env_secret_xyz")
        base_config_dict["third_party"] = {
            "services": [
                {
                    "name": "tqsdk",
                    "api_key": "config_key_123",
                    "api_secret": "config_secret_456",
                    "account_type": "tqaccount",
                }
            ]
        }
        result = ProjectConfig._resolve_account(base_config_dict)
        assert result["account"]["api_key"] == "env_key_abc"
        assert result["account"]["api_secret"] == "env_secret_xyz"
        assert result["account"]["account_type"] == "tqaccount"

    def test_env_var_only_without_third_party(self, monkeypatch):
        monkeypatch.setenv("TQSDK_API_KEY", "pure_env_key")
        monkeypatch.setenv("TQSDK_API_SECRET", "pure_env_secret")
        result = ProjectConfig._resolve_account({})
        assert result["account"]["api_key"] == "pure_env_key"
        assert result["account"]["api_secret"] == "pure_env_secret"

    def test_env_var_partial_ignored(self, monkeypatch, base_config_dict):
        """仅设置一个环境变量 → 不全则不使用，退回配置文件"""
        monkeypatch.delenv("TQSDK_API_KEY", raising=False)
        monkeypatch.delenv("TQSDK_API_SECRET", raising=False)
        monkeypatch.setenv("TQSDK_API_KEY", "half_env_key")
        # 不设置 TQSDK_API_SECRET
        base_config_dict["third_party"] = {
            "services": [
                {
                    "name": "tqsdk",
                    "api_key": "fallback_key",
                    "api_secret": "fallback_secret",
                }
            ]
        }
        result = ProjectConfig._resolve_account(base_config_dict)
        # 环境变量不全 → 退回配置文件
        assert result["account"]["api_key"] == "fallback_key"
        assert result["account"]["api_secret"] == "fallback_secret"


class TestDataConfig:
    def test_get_data_config_defaults(self):
        cm = ConfigManager(env="backtest")
        dc = cm.get_data_config()
        assert dc.environment == "backtest"
        assert dc.database_path.endswith("project_data/database/backtest/quant.db")

    def test_get_data_config_filename_template(self):
        cm = ConfigManager(env="backtest")
        dc = cm.get_data_config()
        assert "{symbol}" in dc.filename_template


class TestLoggingConfig:
    def test_get_system_logging_config_defaults(self):
        cm = ConfigManager(env="backtest")
        sl = cm.get_system_logging_config()
        assert sl.level == "INFO"
        assert sl.format  # 非空字符串
