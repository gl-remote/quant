from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import pandas as pd
from backtest import VnpyBacktestEngine
from cli.workflows.backtests_run import get_git_hash
from config import ConfigManager
from data import DataManager
from data.output_paths import project_data_root
from run_value_area_deepening_r2 import _required_interval
from run_value_area_random_baseline import STRUCTURE_PARAMS, _to_trial_result


@dataclass(frozen=True)
class TradeDiagnostic:
    symbol: str
    min_reaccept_ticks: int
    entry_time: str
    exit_time: str
    side: str
    pnl: float
    bars_held: int
    exit_reason: str
    mae_ticks: float
    mfe_ticks: float
    is_win: bool
    is_loss: bool
    quick_failure_1: bool
    quick_failure_2: bool
    quick_failure_3: bool


@dataclass(frozen=True)
class MechanismSummary:
    symbol: str
    min_reaccept_ticks: int
    total_return: float
    total_net_pnl: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    closed_trades: int
    avg_mae_ticks: float
    avg_mfe_ticks: float
    median_mae_ticks: float
    median_mfe_ticks: float
    quick_failure_1_rate: float
    quick_failure_2_rate: float
    quick_failure_3_rate: float
    max_single_loss: float
    max_consecutive_losses: int
    worst_loss_cluster: float
    cost_to_avg_win: float
    avg_bars_held: float
    take_profit_count: int
    strict_failure_count: int
    stop_loss_count: int
    time_exit_count: int
    force_flat_count: int
    other_exit_count: int


def main() -> None:
    args = _parse_args()
    output_dir = project_data_root() / "research" / "random_baseline"
    output_dir.mkdir(parents=True, exist_ok=True)

    summaries: list[MechanismSummary] = []
    diagnostics: list[TradeDiagnostic] = []
    for symbol in args.symbols:
        for min_reaccept_ticks in args.min_reaccept_ticks:
            summary, trades = _run_diagnostics(symbol, min_reaccept_ticks)
            summaries.append(summary)
            diagnostics.extend(trades)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    trades_path = output_dir / f"value_area_deepening_r3_trades_{timestamp}.csv"
    summary_path = output_dir / f"value_area_deepening_r3_summary_{timestamp}.json"
    _write_trades_csv(trades_path, diagnostics)
    output = {
        "symbols": args.symbols,
        "min_reaccept_ticks": args.min_reaccept_ticks,
        "git_hash": get_git_hash(),
        "trades_path": str(trades_path),
        "summaries": [asdict(summary) for summary in summaries],
    }
    summary_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"Trades: {trades_path}")
    print(f"Summary: {summary_path}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose value area deep reacceptance MAE/MFE and failure quality")
    parser.add_argument("--symbols", nargs="+", default=["DCE.m2601", "CZCE.SR601"])
    parser.add_argument("--min-reaccept-ticks", type=int, nargs="+", default=[1, 2, 3])
    return parser.parse_args()


def _run_diagnostics(symbol: str, min_reaccept_ticks: int) -> tuple[MechanismSummary, list[TradeDiagnostic]]:
    params = {**STRUCTURE_PARAMS, "min_reaccept_ticks": min_reaccept_ticks}
    cm = ConfigManager(env="backtest")
    dm = DataManager(cm)
    bc = cm.get_backtest_config()
    interval = _required_interval("value_area_reacceptance", params, bc.interval)
    bc = bc.model_copy(update={"interval": interval})
    datasets = dm.load_kline([symbol], None, None, interval)
    if not datasets:
        raise RuntimeError(f"数据加载失败: {symbol} {interval}")
    loaded_symbol, df, _ = datasets[0]
    engine = VnpyBacktestEngine(bc)
    engine.set_git_hash(get_git_hash())
    result = engine.run([(loaded_symbol, df, "value_area_reacceptance", params)], batch_mode=True)[0]
    trial = _to_trial_result(result, seed=0, mode="same")
    diagnostics = _trade_diagnostics(symbol, min_reaccept_ticks, df, result.fills, bc.price_tick)
    return _mechanism_summary(symbol, min_reaccept_ticks, trial, diagnostics), diagnostics


def _trade_diagnostics(
    symbol: str,
    min_reaccept_ticks: int,
    df: pd.DataFrame,
    fills: list[dict[str, object]],
    price_tick: float,
) -> list[TradeDiagnostic]:
    bars = df.copy()
    bars["datetime"] = pd.to_datetime(bars["datetime"])
    open_queue: list[dict[str, object]] = []
    diagnostics: list[TradeDiagnostic] = []
    for fill in fills:
        if fill.get("offset") == "open":
            open_queue.append(fill)
            continue
        if not open_queue:
            continue
        open_fill = open_queue.pop(0)
        entry_time = pd.Timestamp(str(open_fill["datetime"]))
        exit_time = pd.Timestamp(str(fill["datetime"]))
        entry_price = _float_value(open_fill["close_price"])
        exit_reason = _base_reason(str(fill.get("reason", "")))
        side = "long" if str(open_fill.get("direction")) == "long" else "short"
        pnl = _float_value(fill.get("pnl", 0.0))
        window = bars[(bars["datetime"] >= entry_time) & (bars["datetime"] <= exit_time)]
        bars_held = max(1, len(window) - 1)
        mae_ticks, mfe_ticks = _mae_mfe_ticks(window, side, entry_price, price_tick)
        is_failure = exit_reason in {"strict_failure_close", "stop_loss"}
        diagnostics.append(
            TradeDiagnostic(
                symbol=symbol,
                min_reaccept_ticks=min_reaccept_ticks,
                entry_time=str(entry_time),
                exit_time=str(exit_time),
                side=side,
                pnl=pnl,
                bars_held=bars_held,
                exit_reason=exit_reason,
                mae_ticks=mae_ticks,
                mfe_ticks=mfe_ticks,
                is_win=pnl > 0,
                is_loss=pnl < 0,
                quick_failure_1=is_failure and bars_held <= 1,
                quick_failure_2=is_failure and bars_held <= 2,
                quick_failure_3=is_failure and bars_held <= 3,
            )
        )
    return diagnostics


def _float_value(value: object) -> float:
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        return float(value)
    return 0.0


def _mae_mfe_ticks(window: pd.DataFrame, side: str, entry_price: float, price_tick: float) -> tuple[float, float]:
    if window.empty or price_tick <= 0:
        return 0.0, 0.0
    high = float(cast(float, window["high"].max()))
    low = float(cast(float, window["low"].min()))
    if side == "long":
        mae = max(0.0, entry_price - low)
        mfe = max(0.0, high - entry_price)
    else:
        mae = max(0.0, high - entry_price)
        mfe = max(0.0, entry_price - low)
    return mae / price_tick, mfe / price_tick


def _mechanism_summary(
    symbol: str,
    min_reaccept_ticks: int,
    trial: Any,
    diagnostics: list[TradeDiagnostic],
) -> MechanismSummary:
    losses = [trade.pnl for trade in diagnostics if trade.pnl < 0]
    wins = [trade.pnl for trade in diagnostics if trade.pnl > 0]
    exit_counts = {reason: sum(1 for trade in diagnostics if trade.exit_reason == reason) for reason in _exit_reasons()}
    total_cost = trial.total_commission + trial.total_slippage
    avg_win = sum(wins) / len(wins) if wins else 0.0
    return MechanismSummary(
        symbol=symbol,
        min_reaccept_ticks=min_reaccept_ticks,
        total_return=trial.total_return,
        total_net_pnl=trial.total_net_pnl,
        max_drawdown=trial.max_drawdown,
        win_rate=trial.win_rate,
        total_trades=trial.total_trades,
        closed_trades=len(diagnostics),
        avg_mae_ticks=_mean([trade.mae_ticks for trade in diagnostics]),
        avg_mfe_ticks=_mean([trade.mfe_ticks for trade in diagnostics]),
        median_mae_ticks=_median([trade.mae_ticks for trade in diagnostics]),
        median_mfe_ticks=_median([trade.mfe_ticks for trade in diagnostics]),
        quick_failure_1_rate=_rate(diagnostics, "quick_failure_1"),
        quick_failure_2_rate=_rate(diagnostics, "quick_failure_2"),
        quick_failure_3_rate=_rate(diagnostics, "quick_failure_3"),
        max_single_loss=min(losses) if losses else 0.0,
        max_consecutive_losses=_max_consecutive_losses(diagnostics),
        worst_loss_cluster=_worst_loss_cluster(diagnostics),
        cost_to_avg_win=total_cost / avg_win if avg_win > 0 else 0.0,
        avg_bars_held=_mean([trade.bars_held for trade in diagnostics]),
        take_profit_count=exit_counts["take_profit"],
        strict_failure_count=exit_counts["strict_failure_close"],
        stop_loss_count=exit_counts["stop_loss"],
        time_exit_count=exit_counts["time_exit"],
        force_flat_count=exit_counts["force_flat"],
        other_exit_count=len(diagnostics) - sum(exit_counts.values()),
    )


def _exit_reasons() -> list[str]:
    return ["take_profit", "strict_failure_close", "stop_loss", "time_exit", "force_flat"]


def _base_reason(reason: str) -> str:
    return reason.split("|", 1)[0]


def _rate(diagnostics: list[TradeDiagnostic], attr: str) -> float:
    if not diagnostics:
        return 0.0
    return sum(1 for trade in diagnostics if bool(getattr(trade, attr))) / len(diagnostics)


def _mean(values: list[float | int]) -> float:
    return sum(float(value) for value in values) / len(values) if values else 0.0


def _median(values: list[float | int]) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _max_consecutive_losses(diagnostics: list[TradeDiagnostic]) -> int:
    max_losses = 0
    current = 0
    for trade in diagnostics:
        if trade.pnl < 0:
            current += 1
            max_losses = max(max_losses, current)
        elif trade.pnl > 0:
            current = 0
    return max_losses


def _worst_loss_cluster(diagnostics: list[TradeDiagnostic]) -> float:
    worst = 0.0
    current = 0.0
    for trade in diagnostics:
        if trade.pnl < 0:
            current += trade.pnl
            worst = min(worst, current)
        elif trade.pnl > 0:
            current = 0.0
    return worst


def _write_trades_csv(path: Path, diagnostics: list[TradeDiagnostic]) -> None:
    if not diagnostics:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(TradeDiagnostic.__dataclass_fields__))
        writer.writeheader()
        for trade in diagnostics:
            writer.writerow(asdict(trade))


if __name__ == "__main__":
    main()
