"""ConfigManager 配置管理测试"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
import yaml
import os
import tempfile
from pathlib import Path
from config.config_manager import ConfigManager


class TestConfigLoading:
    def test_load_from_temp_file(self, temp_config_file):
        cm = ConfigManager(config_file=temp_config_file)
        tc = cm.get_trading_config()
        assert tc['sma_short'] == 5
        assert tc['sma_long'] == 20
        assert tc['stop_loss_ratio'] == 0.03

    def test_defaults_when_no_config(self):
        """no conf.yaml exists in test directory, should use defaults"""
        cm = ConfigManager(config_file='/nonexistent/path.yaml')
        tc = cm.get_trading_config()
        assert tc['sma_short'] == 5
        assert tc['position_ratio'] == 0.1


class TestTradingConfig:
    def test_get_trading_config_defaults(self):
        cm = ConfigManager(config_file='/nonexistent/path.yaml')
        tc = cm.get_trading_config()
        assert tc['stop_loss_ratio'] == 0.03
        assert tc['take_profit_ratio'] == 0.05
        assert tc['position_ratio'] == 0.1
        assert tc['sma_short'] == 5
        assert tc['sma_long'] == 20
        assert tc['kline_period'] == 5

    def test_get_trading_config_from_file(self, temp_config_file):
        cm = ConfigManager(config_file=temp_config_file)
        tc = cm.get_trading_config()
        assert tc['sma_short'] == 5
        assert tc['sma_long'] == 20


class TestBacktestConfig:
    def test_get_backtest_config_defaults(self):
        cm = ConfigManager(config_file='/nonexistent/path.yaml')
        bc = cm.get_backtest_config()
        assert bc['initial_capital'] == 100000.0
        assert bc['commission_rate'] == 0.0003
        assert bc['slippage'] == 1.0
        assert bc['price_tick'] == 1.0
        assert bc['contract_size'] == 10
        assert bc['interval'] == '1m'


class TestValidateConfig:
    def test_valid_default_config(self, temp_config_file):
        cm = ConfigManager(config_file=temp_config_file)
        assert cm.validate_config() is True

    def test_invalid_stop_loss_ratio(self, base_config_dict):
        base_config_dict['strategies'][0]['stop_loss_ratio'] = 0.0
        fd, path = tempfile.mkstemp(suffix='.yaml')
        with open(fd, 'w', encoding='utf-8') as f:
            yaml.dump(base_config_dict, f)
        cm = ConfigManager(config_file=path)
        assert cm.validate_config() is False
        os.unlink(path)

    def test_invalid_sma_ordering(self, base_config_dict):
        base_config_dict['strategies'][0]['sma_short'] = 30
        base_config_dict['strategies'][0]['sma_long'] = 10
        fd, path = tempfile.mkstemp(suffix='.yaml')
        with open(fd, 'w', encoding='utf-8') as f:
            yaml.dump(base_config_dict, f)
        cm = ConfigManager(config_file=path)
        assert cm.validate_config() is False
        os.unlink(path)

    def test_invalid_commission_rate(self, base_config_dict):
        base_config_dict['backtest']['commission_rate'] = 1.5
        fd, path = tempfile.mkstemp(suffix='.yaml')
        with open(fd, 'w', encoding='utf-8') as f:
            yaml.dump(base_config_dict, f)
        cm = ConfigManager(config_file=path)
        assert cm.validate_config() is False
        os.unlink(path)

    def test_invalid_negative_slippage(self, base_config_dict):
        base_config_dict['backtest']['slippage'] = -1.0
        fd, path = tempfile.mkstemp(suffix='.yaml')
        with open(fd, 'w', encoding='utf-8') as f:
            yaml.dump(base_config_dict, f)
        cm = ConfigManager(config_file=path)
        assert cm.validate_config() is False
        os.unlink(path)

    def test_invalid_price_tick(self, base_config_dict):
        base_config_dict['backtest']['price_tick'] = 0
        fd, path = tempfile.mkstemp(suffix='.yaml')
        with open(fd, 'w', encoding='utf-8') as f:
            yaml.dump(base_config_dict, f)
        cm = ConfigManager(config_file=path)
        assert cm.validate_config() is False
        os.unlink(path)


class TestAccountInfo:
    def test_get_account_info_no_services(self, base_config_dict):
        base_config_dict.pop('third_party', None)
        fd, path = tempfile.mkstemp(suffix='.yaml')
        with open(fd, 'w', encoding='utf-8') as f:
            yaml.dump(base_config_dict, f)
        cm = ConfigManager.__new__(ConfigManager)
        cm.config = yaml.safe_load(open(path, encoding='utf-8')) or {}
        assert cm.get_account_info() == {}
        os.unlink(path)

    def test_get_account_info_placeholder(self, base_config_dict):
        base_config_dict['third_party'] = {
            'services': [{
                'name': 'tqsdk',
                'api_key': 'PLACEHOLDER_API_KEY',
                'api_secret': 'PLACEHOLDER_API_SECRET',
            }]
        }
        fd, path = tempfile.mkstemp(suffix='.yaml')
        with open(fd, 'w', encoding='utf-8') as f:
            yaml.dump(base_config_dict, f)
        cm = ConfigManager.__new__(ConfigManager)
        cm.config = yaml.safe_load(open(path, encoding='utf-8')) or {}
        assert cm.get_account_info() == {}
        os.unlink(path)

    def test_get_account_info_valid(self, base_config_dict):
        base_config_dict['third_party'] = {
            'services': [{
                'name': 'tqsdk',
                'api_key': 'real_key_123',
                'api_secret': 'real_secret_456',
            }]
        }
        fd, path = tempfile.mkstemp(suffix='.yaml')
        with open(fd, 'w', encoding='utf-8') as f:
            yaml.dump(base_config_dict, f)
        cm = ConfigManager.__new__(ConfigManager)
        cm.config = yaml.safe_load(open(path, encoding='utf-8')) or {}
        info = cm.get_account_info()
        assert info['api_key'] == 'real_key_123'
        assert info['api_secret'] == 'real_secret_456'
        os.unlink(path)

    def test_env_var_priority_over_config(self, monkeypatch, base_config_dict):
        """环境变量优先级高于 conf.local.yaml"""
        monkeypatch.setenv('TQSDK_API_KEY', 'env_key_abc')
        monkeypatch.setenv('TQSDK_API_SECRET', 'env_secret_xyz')

        base_config_dict['third_party'] = {
            'services': [{
                'name': 'tqsdk',
                'api_key': 'config_key_123',
                'api_secret': 'config_secret_456',
            }]
        }
        fd, path = tempfile.mkstemp(suffix='.yaml')
        with open(fd, 'w', encoding='utf-8') as f:
            yaml.dump(base_config_dict, f)
        cm = ConfigManager.__new__(ConfigManager)
        cm.config = yaml.safe_load(open(path, encoding='utf-8')) or {}
        info = cm.get_account_info()
        assert info['api_key'] == 'env_key_abc'
        assert info['api_secret'] == 'env_secret_xyz'
        os.unlink(path)

    def test_env_var_only_without_config(self, monkeypatch):
        """仅设置环境变量，无配置文件时也正常工作"""
        monkeypatch.setenv('TQSDK_API_KEY', 'pure_env_key')
        monkeypatch.setenv('TQSDK_API_SECRET', 'pure_env_secret')
        cm = ConfigManager.__new__(ConfigManager)
        cm.config = {}
        info = cm.get_account_info()
        assert info['api_key'] == 'pure_env_key'
        assert info['api_secret'] == 'pure_env_secret'

    def test_env_var_partial_ignored(self, monkeypatch, base_config_dict):
        """仅设置一个环境变量时不会误用，回退到配置文件"""
        monkeypatch.setenv('TQSDK_API_KEY', 'half_env_key')
        # 不设置 TQSDK_API_SECRET

        base_config_dict['third_party'] = {
            'services': [{
                'name': 'tqsdk',
                'api_key': 'fallback_key',
                'api_secret': 'fallback_secret',
            }]
        }
        fd, path = tempfile.mkstemp(suffix='.yaml')
        with open(fd, 'w', encoding='utf-8') as f:
            yaml.dump(base_config_dict, f)
        cm = ConfigManager.__new__(ConfigManager)
        cm.config = yaml.safe_load(open(path, encoding='utf-8')) or {}
        info = cm.get_account_info()
        # TQSDK_API_SECRET 未设置，ak+sk 不全 → 不回环境变量 → 走配置文件
        assert info['api_key'] == 'fallback_key'
        assert info['api_secret'] == 'fallback_secret'
        os.unlink(path)


class TestDataConfig:
    def test_get_data_config_defaults(self):
        cm = ConfigManager(config_file='/nonexistent/path.yaml')
        dc = cm.get_data_config()
        # base_dir 已通过 _resolve 转为绝对路径，应包含 .quant_shared_data
        assert '.quant_shared_data' in dc['base_dir']
        assert Path(dc['base_dir']).is_absolute()
        assert 'csv' in dc['export_dir']
        assert Path(dc['export_dir']).is_absolute()

    def test_get_export_config_defaults(self):
        cm = ConfigManager(config_file='/nonexistent/path.yaml')
        ec = cm.get_export_config()
        assert '{symbol}' in ec['filename_template']


class TestLoggingConfig:
    def test_get_system_logging_config_defaults(self):
        cm = ConfigManager(config_file='/nonexistent/path.yaml')
        sl = cm.get_system_logging_config()
        assert sl['level'] == 'INFO'
        assert 'format' in sl