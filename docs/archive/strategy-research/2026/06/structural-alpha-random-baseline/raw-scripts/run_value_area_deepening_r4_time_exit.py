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
class TimeExitTrade:
    symbol: str
    min_reaccept_ticks: int
    max_hold_bars: int
    entry_time: str
    exit_time: str
    side: str
    exit_reason: str
    pnl: float
    bars_held: int
    mae_ticks: float
    mfe_ticks: float
    target_distance_ticks: float
    mfe_target_coverage: float
    reached_50pct_target: bool
    reached_75pct_target: bool
    reached_90pct_target: bool
    is_time_exit: bool


@dataclass(frozen=True)
class TimeExitSummary:
    symbol: str
    min_reaccept_ticks: int
    max_hold_bars: int
    total_return: float
    total_net_pnl: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    closed_trades: int
    take_profit_count: int
    time_exit_count: int
    time_exit_rate: float
    time_exit_avg_pnl: float
    time_exit_win_rate: float
    time_exit_avg_mfe_ticks: float
    time_exit_avg_target_coverage: float
    time_exit_reached_50pct_rate: float
    time_exit_reached_75pct_rate: float
    time_exit_reached_90pct_rate: float
    take_profit_avg_mfe_ticks: float
    take_profit_avg_bars: float
    non_time_exit_avg_pnl: float


def main() -> None:
    args = _parse_args()
    output_dir = project_data_root() / "research" / "random_baseline"
    output_dir.mkdir(parents=True, exist_ok=True)

    summaries: list[TimeExitSummary] = []
    trades: list[TimeExitTrade] = []
    for symbol in args.symbols:
        for min_reaccept_ticks in args.min_reaccept_ticks:
            for max_hold_bars in args.max_hold_bars:
                summary, trade_rows = _run_time_exit_diagnostics(symbol, min_reaccept_ticks, max_hold_bars)
                summaries.append(summary)
                trades.extend(trade_rows)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    trades_path = output_dir / f"value_area_deepening_r4_time_exit_trades_{timestamp}.csv"
    summary_path = output_dir / f"value_area_deepening_r4_time_exit_summary_{timestamp}.json"
    _write_trades_csv(trades_path, trades)
    output = {
        "symbols": args.symbols,
        "min_reaccept_ticks": args.min_reaccept_ticks,
        "max_hold_bars": args.max_hold_bars,
        "git_hash": get_git_hash(),
        "trades_path": str(trades_path),
        "summaries": [asdict(summary) for summary in summaries],
    }
    summary_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"Trades: {trades_path}")
    print(f"Summary: {summary_path}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose value area time_exit realization quality")
    parser.add_argument("--symbols", nargs="+", default=["DCE.m2601", "CZCE.SR601"])
    parser.add_argument("--min-reaccept-ticks", type=int, nargs="+", default=[2, 3])
    parser.add_argument("--max-hold-bars", type=int, nargs="+", default=[6, 12, 18, 24])
    return parser.parse_args()


def _run_time_exit_diagnostics(
    symbol: str,
    min_reaccept_ticks: int,
    max_hold_bars: int,
) -> tuple[TimeExitSummary, list[TimeExitTrade]]:
    params = {
        **STRUCTURE_PARAMS,
        "min_reaccept_ticks": min_reaccept_ticks,
        "max_hold_bars": max_hold_bars,
    }
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
    trades = _time_exit_trades(symbol, min_reaccept_ticks, max_hold_bars, df, result.fills, bc.price_tick)
    return _time_exit_summary(symbol, min_reaccept_ticks, max_hold_bars, trial, trades), trades


def _time_exit_trades(
    symbol: str,
    min_reaccept_ticks: int,
    max_hold_bars: int,
    df: pd.DataFrame,
    fills: list[dict[str, object]],
    price_tick: float,
) -> list[TimeExitTrade]:
    bars = df.copy()
    bars["datetime"] = pd.to_datetime(bars["datetime"])
    prev_poc_by_date = _previous_poc_by_date(bars, price_tick)
    open_queue: list[dict[str, object]] = []
    rows: list[TimeExitTrade] = []
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
        side = "long" if str(open_fill.get("direction")) == "long" else "short"
        pnl = _float_value(fill.get("pnl", 0.0))
        exit_reason = _base_reason(str(fill.get("reason", "")))
        prev_poc = prev_poc_by_date.get(entry_time.date())
        target_distance_ticks = _target_distance_to_poc(prev_poc, entry_price, side, price_tick)
        window = bars[(bars["datetime"] >= entry_time) & (bars["datetime"] <= exit_time)]
        bars_held = max(1, len(window) - 1)
        mae_ticks, mfe_ticks = _mae_mfe_ticks(window, side, entry_price, price_tick)
        coverage = mfe_ticks / target_distance_ticks if target_distance_ticks > 0 else 0.0
        rows.append(
            TimeExitTrade(
                symbol=symbol,
                min_reaccept_ticks=min_reaccept_ticks,
                max_hold_bars=max_hold_bars,
                entry_time=str(entry_time),
                exit_time=str(exit_time),
                side=side,
                exit_reason=exit_reason,
                pnl=pnl,
                bars_held=bars_held,
                mae_ticks=mae_ticks,
                mfe_ticks=mfe_ticks,
                target_distance_ticks=target_distance_ticks,
                mfe_target_coverage=coverage,
                reached_50pct_target=coverage >= 0.5,
                reached_75pct_target=coverage >= 0.75,
                reached_90pct_target=coverage >= 0.9,
                is_time_exit=exit_reason == "time_exit",
            )
        )
    return rows


def _previous_poc_by_date(bars: pd.DataFrame, price_tick: float) -> dict[object, float]:
    poc_by_date: dict[object, float] = {}
    prev_poc_by_date: dict[object, float] = {}
    previous_poc: float | None = None
    for session_date, day_bars in bars.groupby(bars["datetime"].dt.date, sort=True):
        if previous_poc is not None:
            prev_poc_by_date[session_date] = previous_poc
        previous_poc = _session_poc(day_bars, price_tick)
        poc_by_date[session_date] = previous_poc
    return prev_poc_by_date


def _session_poc(day_bars: pd.DataFrame, price_tick: float) -> float:
    if day_bars.empty or price_tick <= 0:
        return 0.0
    profile: dict[float, float] = {}
    for row in day_bars.itertuples(index=False):
        close = _float_value(row.close)
        volume = _float_value(getattr(row, "volume", 0.0))
        price = round(close / price_tick) * price_tick
        profile[price] = profile.get(price, 0.0) + volume
    if not profile:
        return float(cast(float, day_bars["close"].iloc[-1]))
    session_close = float(cast(float, day_bars["close"].iloc[-1]))
    return max(profile, key=lambda price: (profile[price], -abs(price - session_close)))


def _target_distance_to_poc(prev_poc: float | None, entry_price: float, side: str, price_tick: float) -> float:
    if prev_poc is None or price_tick <= 0:
        return 0.0
    target_distance = prev_poc - entry_price if side == "long" else entry_price - prev_poc
    return max(0.0, target_distance / price_tick)


def _time_exit_summary(
    symbol: str,
    min_reaccept_ticks: int,
    max_hold_bars: int,
    trial: Any,
    trades: list[TimeExitTrade],
) -> TimeExitSummary:
    time_exits = [trade for trade in trades if trade.is_time_exit]
    take_profits = [trade for trade in trades if trade.exit_reason == "take_profit"]
    non_time_exits = [trade for trade in trades if not trade.is_time_exit]
    return TimeExitSummary(
        symbol=symbol,
        min_reaccept_ticks=min_reaccept_ticks,
        max_hold_bars=max_hold_bars,
        total_return=trial.total_return,
        total_net_pnl=trial.total_net_pnl,
        max_drawdown=trial.max_drawdown,
        win_rate=trial.win_rate,
        total_trades=trial.total_trades,
        closed_trades=len(trades),
        take_profit_count=len(take_profits),
        time_exit_count=len(time_exits),
        time_exit_rate=len(time_exits) / len(trades) if trades else 0.0,
        time_exit_avg_pnl=_mean([trade.pnl for trade in time_exits]),
        time_exit_win_rate=_win_rate(time_exits),
        time_exit_avg_mfe_ticks=_mean([trade.mfe_ticks for trade in time_exits]),
        time_exit_avg_target_coverage=_mean([trade.mfe_target_coverage for trade in time_exits]),
        time_exit_reached_50pct_rate=_bool_rate([trade.reached_50pct_target for trade in time_exits]),
        time_exit_reached_75pct_rate=_bool_rate([trade.reached_75pct_target for trade in time_exits]),
        time_exit_reached_90pct_rate=_bool_rate([trade.reached_90pct_target for trade in time_exits]),
        take_profit_avg_mfe_ticks=_mean([trade.mfe_ticks for trade in take_profits]),
        take_profit_avg_bars=_mean([trade.bars_held for trade in take_profits]),
        non_time_exit_avg_pnl=_mean([trade.pnl for trade in non_time_exits]),
    )


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


def _base_reason(reason: str) -> str:
    return reason.split("|", 1)[0]


def _mean(values: list[float | int]) -> float:
    return sum(float(value) for value in values) / len(values) if values else 0.0


def _bool_rate(values: list[bool]) -> float:
    return sum(1 for value in values if value) / len(values) if values else 0.0


def _win_rate(trades: list[TimeExitTrade]) -> float:
    non_zero = [trade for trade in trades if trade.pnl != 0]
    return sum(1 for trade in non_zero if trade.pnl > 0) / len(non_zero) if non_zero else 0.0


def _write_trades_csv(path: Path, trades: list[TimeExitTrade]) -> None:
    if not trades:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(TimeExitTrade.__dataclass_fields__))
        writer.writeheader()
        for trade in trades:
            writer.writerow(asdict(trade))


if __name__ == "__main__":
    main()
