"""验证 cli/commands/backtest.py 的参数路由 + 跨字段校验"""

from __future__ import annotations

import argparse
from typing import Any

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
        "early_stop_patience": 0,
        "profile": False,
        "no_search": False,
        "dump_indicators": False,
        "strategy_params": None,
        "build_report": False,
        "env": "backtest",
        "config": None,
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
    assert req.strategy_param_overrides == {}


def test_build_search_request_parses_strategy_params():
    from cli.commands.backtest import _build_search_request

    args = _make_args(strategy_params='{"stop_widen_multiplier":1.5,"price_tick":1.0}')
    req = _build_search_request(args)

    assert req.strategy_param_overrides == {"stop_widen_multiplier": 1.5, "price_tick": 1.0}


def test_build_search_request_rejects_invalid_strategy_params():
    from cli.commands.backtest import _build_search_request

    with pytest.raises(ValueError, match="合法 JSON"):
        _build_search_request(_make_args(strategy_params="{"))

    with pytest.raises(ValueError, match="顶层必须是 object"):
        _build_search_request(_make_args(strategy_params="[]"))


def test_register_accepts_single_mode_and_strategy_params() -> None:
    from cli.commands.backtest import register

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    register(subparsers)

    args = parser.parse_args(
        [
            "backtest",
            "--strategy",
            "ma",
            "--mode",
            "single",
            "--strategy-params",
            '{"sma_short":5}',
        ]
    )

    assert args.mode == "single"
    assert args.strategy_params == '{"sma_short":5}'


def test_no_report_flag_flows_into_request() -> None:
    from cli.commands.backtest import _build_search_request, _build_walk_forward_request, register

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    register(subparsers)

    # 默认不构建报告
    args = parser.parse_args(["backtest", "--strategy", "ma"])
    assert args.build_report is False
    assert _build_search_request(_make_args()).no_report is True
    assert _build_walk_forward_request(_make_args()).no_report is True

    # 显式开启 --build-report 才构建
    args = parser.parse_args(["backtest", "--strategy", "ma", "--build-report"])
    assert args.build_report is True

    search_req = _build_search_request(_make_args(build_report=True))
    assert search_req.no_report is False

    wf_req = _build_walk_forward_request(_make_args(build_report=True))
    assert wf_req.no_report is False


def test_validate_rejects_strategy_params_for_walk_forward():
    from cli.commands.backtest import _validate_cross_field

    with pytest.raises(ValueError, match="search/single"):
        _validate_cross_field(_make_args(mode="walk-forward", strategy_params='{"sma_short":5}'))


def test_validate_rejects_strategy_params_for_tqsdk():
    from cli.commands.backtest import _validate_cross_field

    with pytest.raises(ValueError, match="仅支持 --engine vnpy"):
        _validate_cross_field(
            _make_args(
                engine="tqsdk",
                symbol="DCE.m2509",
                start="2025-01-01",
                end="2025-06-30",
                strategy_params='{"sma_short":5}',
            )
        )


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


def test_register_defines_parallel_arguments() -> None:
    from cli.commands.backtest import register

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    register(subparsers)

    args = parser.parse_args(["backtest", "--strategy", "ma", "--parallel", "--workers", "4"])

    assert args.command == "backtest"
    assert args.engine == "vnpy"
    assert args.mode == "search"
    assert args.parallel is True
    assert args.workers == 4


def test_register_rejects_unknown_engine() -> None:
    from cli.commands.backtest import register

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    register(subparsers)

    with pytest.raises(SystemExit):
        parser.parse_args(["backtest", "--strategy", "ma", "--engine", "unknown"])


def test_cmd_backtest_routes_vnpy_search(monkeypatch: pytest.MonkeyPatch) -> None:
    from cli.commands import backtest

    calls: list[tuple[str, Any]] = []

    class _Workflow:
        def __init__(self, **_: Any) -> None:
            pass

        def run_vnpy_search(self, req) -> None:
            calls.append(("search", req))

        def run_vnpy_walk_forward(self, req) -> None:
            calls.append(("walk_forward", req))

        def run_tqsdk(self, req) -> None:
            calls.append(("tqsdk", req))

    monkeypatch.setattr(backtest, "BacktestRunWorkflow", _Workflow)

    backtest.cmd_backtest(_make_args(symbol="DCE.m2509", parallel=True, workers=2))

    assert len(calls) == 1
    route, req = calls[0]
    assert route == "search"
    assert req.symbol == "DCE.m2509"
    assert req.parallel is True
    assert req.workers == 2


def test_cmd_backtest_routes_vnpy_single_as_no_search(monkeypatch: pytest.MonkeyPatch) -> None:
    from cli.commands import backtest

    calls: list[tuple[str, Any]] = []

    class _Workflow:
        def __init__(self, **_: Any) -> None:
            pass

        def run_vnpy_search(self, req) -> None:
            calls.append(("search", req))

        def run_vnpy_walk_forward(self, req) -> None:
            calls.append(("walk_forward", req))

        def run_tqsdk(self, req) -> None:
            calls.append(("tqsdk", req))

    monkeypatch.setattr(backtest, "BacktestRunWorkflow", _Workflow)

    backtest.cmd_backtest(_make_args(mode="single", symbol="DCE.m2509", strategy_params='{"sma_short":5}'))

    assert len(calls) == 1
    route, req = calls[0]
    assert route == "search"
    assert req.no_search is True
    assert req.strategy_param_overrides == {"sma_short": 5}


def test_cmd_backtest_routes_vnpy_walk_forward(monkeypatch: pytest.MonkeyPatch) -> None:
    from cli.commands import backtest

    calls: list[tuple[str, Any]] = []

    class _Workflow:
        def __init__(self, **_: Any) -> None:
            pass

        def run_vnpy_search(self, req) -> None:
            calls.append(("search", req))

        def run_vnpy_walk_forward(self, req) -> None:
            calls.append(("walk_forward", req))

        def run_tqsdk(self, req) -> None:
            calls.append(("tqsdk", req))

    monkeypatch.setattr(backtest, "BacktestRunWorkflow", _Workflow)

    backtest.cmd_backtest(_make_args(mode="walk-forward", symbol="DCE.m2509"))

    assert len(calls) == 1
    route, req = calls[0]
    assert route == "walk_forward"
    assert req.symbol == "DCE.m2509"
    assert not hasattr(req, "parallel")


def test_cmd_backtest_routes_tqsdk(monkeypatch: pytest.MonkeyPatch) -> None:
    from cli.commands import backtest

    calls: list[tuple[str, Any]] = []

    class _Workflow:
        def __init__(self, **_: Any) -> None:
            pass

        def run_vnpy_search(self, req) -> None:
            calls.append(("search", req))

        def run_vnpy_walk_forward(self, req) -> None:
            calls.append(("walk_forward", req))

        def run_tqsdk(self, req) -> None:
            calls.append(("tqsdk", req))

    monkeypatch.setattr(backtest, "BacktestRunWorkflow", _Workflow)

    args = _make_args(engine="tqsdk", symbol="DCE.m2509", start="2025-01-01", end="2025-06-30", gui=True)
    backtest.cmd_backtest(args)

    assert len(calls) == 1
    route, req = calls[0]
    assert route == "tqsdk"
    assert req.symbol == "DCE.m2509"
    assert req.gui is True
