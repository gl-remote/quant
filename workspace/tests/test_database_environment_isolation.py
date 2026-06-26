"""数据库环境隔离护栏测试。"""

from __future__ import annotations

from pathlib import Path

import pytest
import tomli_w
from cli.commands.report import cmd_report
from cli.env import build_data_context
from config import ConfigManager
from data import DataManager
from data.models import current_database_path, init_database
from data.output_paths import database_path
from data.store import DataStore


def test_environment_config_resolves_different_database_paths() -> None:
    paths = {}
    for env in ("backtest", "test", "live"):
        cm = ConfigManager(env=env)
        dc = cm.get_data_config()
        paths[env] = dc.database_path
        assert dc.environment == env
        assert Path(dc.database_path) == database_path(env)  # type: ignore[arg-type]

    assert len(set(paths.values())) == 3


def test_config_file_must_match_explicit_env(tmp_path: Path) -> None:
    config_path = tmp_path / "conf.test.toml"
    config_path.write_text(tomli_w.dumps({"data": {"environment": "test", "database_path": str(tmp_path / "test.db")}}))

    with pytest.raises(ValueError, match="配置环境不匹配"):
        ConfigManager(config_file=str(config_path), env="backtest")


def test_data_manager_requires_initialized_environment() -> None:
    with pytest.raises(RuntimeError, match="initialized data environment"):
        DataManager()


def test_data_manager_reuses_current_environment() -> None:
    cm = ConfigManager(env="backtest")
    first = DataManager(cm)
    second = DataManager()

    assert first is not second
    assert second._get_config().get_data_config().environment == "backtest"


def test_data_manager_rejects_environment_switch() -> None:
    DataManager(ConfigManager(env="backtest"))

    with pytest.raises(RuntimeError, match="already initialized"):
        DataManager(ConfigManager(env="test"))


def test_peewee_binding_rejects_different_database(tmp_path: Path) -> None:
    first_path = tmp_path / "first.db"
    second_path = tmp_path / "second.db"

    first_store = DataStore(str(first_path))
    assert current_database_path() == str(first_path.resolve())

    with pytest.raises(RuntimeError, match="already bound"):
        DataStore(str(second_path))

    first_store.close()


def test_init_database_uses_same_binding_guard(tmp_path: Path) -> None:
    first_path = tmp_path / "first.db"
    second_path = tmp_path / "second.db"

    init_database(str(first_path))
    with pytest.raises(RuntimeError, match="already bound"):
        init_database(str(second_path))


def test_cli_command_environment_validation() -> None:
    class Args:
        env = "test"
        config = None

    with pytest.raises(ValueError, match="backtest 命令不允许"):
        build_data_context(Args(), "backtest")


def test_report_does_not_create_missing_database(tmp_path: Path) -> None:
    db_path = tmp_path / "missing" / "quant.db"
    config_path = tmp_path / "conf.report.toml"
    config_path.write_text(tomli_w.dumps({"data": {"environment": "test", "database_path": str(db_path)}}))

    class Args:
        env = None
        config = str(config_path)
        build = False
        clean_id = None
        id = None
        symbol = None
        strategy = None
        limit = 20

    with pytest.raises(SystemExit):
        cmd_report(Args())

    assert not db_path.exists()
    assert not db_path.parent.exists()


def test_read_only_data_manager_rejects_missing_database(tmp_path: Path) -> None:
    db_path = tmp_path / "missing" / "quant.db"
    config_path = tmp_path / "conf.readonly.toml"
    config_path.write_text(tomli_w.dumps({"data": {"environment": "test", "database_path": str(db_path)}}))

    dm = DataManager(ConfigManager(config_file=str(config_path)), create_database=False)
    with pytest.raises(FileNotFoundError):
        _ = dm.store

    assert not db_path.exists()
    assert not db_path.parent.exists()


def test_write_mode_creates_environment_database(tmp_path: Path) -> None:
    db_path = tmp_path / "created" / "quant.db"
    config_path = tmp_path / "conf.write.toml"
    config_path.write_text(tomli_w.dumps({"data": {"environment": "test", "database_path": str(db_path)}}))

    dm = DataManager(ConfigManager(config_file=str(config_path)), create_database=True)
    _ = dm.store

    assert db_path.exists()
