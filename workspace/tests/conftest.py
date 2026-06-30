"""共享测试 fixtures。"""

import os
import tempfile

import pytest
import tomli_w

from tests.helpers.configs import make_base_config_dict, make_trading_config_dict
from tests.helpers.market_data import make_sample_closes, make_sample_kline_df


@pytest.fixture
def sample_closes():
    return make_sample_closes()


@pytest.fixture
def trading_config_dict():
    return make_trading_config_dict()


@pytest.fixture
def base_config_dict():
    return make_base_config_dict()


@pytest.fixture
def sample_kline_df():
    return make_sample_kline_df()


@pytest.fixture(autouse=True)
def _reset_global_state():
    from config.app_config import ConfigManager
    from data.connection import reset_database_binding
    from data.manager import DataManager

    ConfigManager.reset()
    DataManager.reset_environment()
    reset_database_binding()
    yield
    reset_database_binding()
    DataManager.reset_environment()
    ConfigManager.reset()


@pytest.fixture
def temp_config_file(base_config_dict):
    fd, path = tempfile.mkstemp(suffix=".toml")
    with open(fd, "wb") as f:
        f.write(tomli_w.dumps(base_config_dict).encode("utf-8"))
    yield path
    os.unlink(path)


@pytest.fixture
def temp_db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)
    yield path
    if os.path.exists(path):
        os.unlink(path)
    for suffix in ["-wal", "-shm"]:
        p = path + suffix
        if os.path.exists(p):
            os.unlink(p)
