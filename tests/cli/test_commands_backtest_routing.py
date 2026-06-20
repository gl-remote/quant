"""验证 cli/commands/backtest.py 的参数路由 + 跨字段校验"""

from __future__ import annotations

import argparse

import pytest


def _make_args(**overrides):
    defaults = {
        "engine": "vnpy",
        "symbol": None,
        "pattern": None,
        "start": None,
        "end": None,
        "strategy": "ma",
        "capital": None,
        "contract_size": None,
        "gui": False,
        "mode": "search",
        "optimizer": None,
        "trials": None,
        "parallel": False,
        "workers": None,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_validate_tqsdk_missing_symbol():
    from cli.commands.backtest import _validate_cross_field

    with pytest.raises(ValueError, match="--engine tqsdk 必须指定 --symbol"):
        _validate_cross_field(_make_args(engine="tqsdk"))


def test_validate_tqsdk_missing_dates():
    from cli.commands.backtest import _validate_cross_field

    with pytest.raises(ValueError, match="必须显式指定 --start / --end"):
        _validate_cross_field(_make_args(engine="tqsdk", symbol="DCE.m2509"))


def test_validate_tqsdk_complete_passes():
    from cli.commands.backtest import _validate_cross_field

    # 不抛异常即算通过
    _validate_cross_field(_make_args(engine="tqsdk", symbol="DCE.m2509", start="2025-01-01", end="2025-06-30"))


def test_build_search_request_fields():
    from cli.commands.backtest import _build_search_request

    args = _make_args(
        symbol="DCE.m2509",
        capital=100000.0,
        contract_size=10,
        optimizer="grid",
        trials=8,
        parallel=True,
        workers=4,
    )
    req = _build_search_request(args)
    assert req.strategy == "ma"
    assert req.symbol == "DCE.m2509"
    assert req.capital == 100000.0
    assert req.contract_size == 10
    assert req.optimizer == "grid"
    assert req.trials == 8
    assert req.parallel is True
    assert req.workers == 4


def test_build_walk_forward_request_fields():
    from cli.commands.backtest import _build_walk_forward_request

    args = _make_args(symbol="DCE.m2509", capital=50000.0, contract_size=20, mode="walk-forward")
    req = _build_walk_forward_request(args)
    # walk-forward 不包含 optimizer/trials/parallel/workers
    assert not hasattr(req, "optimizer")
    assert not hasattr(req, "parallel")
    assert req.symbol == "DCE.m2509"
    assert req.capital == 50000.0


def test_build_tqsdk_request_fields():
    from cli.commands.backtest import _build_tqsdk_request

    args = _make_args(
        engine="tqsdk", symbol="DCE.m2509", start="2025-01-01", end="2025-06-30", capital=80000.0, gui=True
    )
    req = _build_tqsdk_request(args)
    # tqsdk 不包含 pattern/optimizer/trials/parallel/mode/contract_size
    assert not hasattr(req, "pattern")
    assert not hasattr(req, "optimizer")
    assert not hasattr(req, "parallel")
    assert not hasattr(req, "mode")
    assert not hasattr(req, "contract_size")
    # tqsdk 必填字段类型上是 str（非 Optional）
    assert req.symbol == "DCE.m2509"
    assert req.start == "2025-01-01"
    assert req.end == "2025-06-30"
    assert req.gui is True


def test_validate_warns_gui_under_vnpy(caplog):
    from cli.commands.backtest import _validate_cross_field

    # vnpy 引擎 + --gui 应当 warn 但不抛错
    _validate_cross_field(_make_args(engine="vnpy", gui=True))
