"""测试公共 fixtures：注册默认指标函数"""

from strategies.runtime.indicators import register_default_indicators


def pytest_configure(config):
    """在测试启动时注册默认指标函数"""
    register_default_indicators()
