#!/usr/bin/env python3
"""value_area_reacceptance 结构拆解诊断。"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Literal

DEFAULT_BACKTEST_IDS = [688, 689, 695, 697, 703, 704, 705, 706]
DEFAULT_DB = Path("project_data/database/backtest/quant.db")
FORWARD_BARS = [5, 15, 30, 60]
STOP_WIDEN_MULTIPLIERS = [1.0, 1.2, 1.5]
ATR_BARS = 20
ATR_RATIO_BUCKETS = [
    (0.0, 1.0, "<1.0"),
    (1.0, 1.5, "1.0-1.5"),
    (1.5, 2.0, "1.5-2.0"),
    (2.0, 3.0, "2.0-3.0"),
    (3.0, float("inf"), ">=3.0"),
]


@dataclass(frozen=True)
class CsvBar:
    dt: datetime
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class TradeRow:
    backtest_id: int
    symbol: str
    ticks: int
    kline_interval: str
    data_src: Path
    direction: str
    open_time: datetime
    close_time: datetime
    open_price: float
    close_price: float
    volume: float
    contract_multiplier: float
    commission: float
    slippage_cost: float
    net_pnl: float
    exit_reason: str
    mae: float
    mfe: float
    diagnostics: dict[str, Any]


@dataclass(frozen=True)
class StopCounterfactual:
    multiplier: float
    original_exit: str
    simulated_exit: str
    original_net_pnl: float
    simulated_net_pnl: float
    earlier_stop: bool
    killed_take_profit: bool
    killed_positive_time_exit: bool


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("T", " "))


def _fmt(value: float | int | None, digits: int = 1) -> str:
    if value is None:
        return "-"
    if isinstance(value, int):
        return str(value)
    return f"{value:.{digits}f}"


def _avg(values: list[float | None]) -> float | None:
    valid = [value for value in values if value is not None]
    return mean(valid) if valid else None


def _sum(values: list[float | None]) -> float:
    return sum(value for value in values if value is not None)


def _markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def _load_csv(path: Path) -> tuple[list[CsvBar], dict[datetime, int]]:
    bars: list[CsvBar] = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            dt = _parse_dt(row["datetime"])
            bars.append(CsvBar(dt=dt, high=float(row["high"]), low=float(row["low"]), close=float(row["close"])))
    return bars, {bar.dt: i for i, bar in enumerate(bars)}


def _load_trades(db_path: Path, backtest_ids: list[int]) -> list[TradeRow]:
    placeholders = ",".join("?" for _ in backtest_ids)
    sql = f"""
        SELECT
            c.backtest_id,
            b.symbol,
            CAST(p.param_value AS INTEGER) AS ticks,
            b.kline_interval,
            b.data_src,
            c.direction,
            c.open_time,
            c.close_time,
            c.open_price,
            c.close_price,
            c.volume,
            c.contract_multiplier,
            c.commission,
            c.slippage_cost,
            c.net_pnl,
            COALESCE(c.exit_reason, c.close_reason, '') AS exit_reason,
            COALESCE(c.mae, 0) AS mae,
            COALESCE(c.mfe, 0) AS mfe,
            COALESCE(c.diagnostics_json, '{{}}') AS diagnostics_json
        FROM trade_clearings c
        JOIN backtests b ON b.id = c.backtest_id
        LEFT JOIN backtest_params p
          ON p.backtest_id = c.backtest_id AND p.param_name = 'min_reaccept_ticks'
        WHERE c.backtest_id IN ({placeholders})
        ORDER BY c.backtest_id, c.open_time
    """
    rows: list[TradeRow] = []
    with sqlite3.connect(db_path) as conn:
        for row in conn.execute(sql, backtest_ids):
            diagnostics = json.loads(row[18]) if row[18] else {}
            rows.append(
                TradeRow(
                    backtest_id=int(row[0]),
                    symbol=str(row[1]),
                    ticks=int(row[2]),
                    kline_interval=str(row[3]),
                    data_src=Path(str(row[4])),
                    direction=str(row[5]),
                    open_time=_parse_dt(str(row[6])),
                    close_time=_parse_dt(str(row[7])),
                    open_price=float(row[8]),
                    close_price=float(row[9]),
                    volume=float(row[10]),
                    contract_multiplier=float(row[11]),
                    commission=float(row[12]),
                    slippage_cost=float(row[13]),
                    net_pnl=float(row[14]),
                    exit_reason=str(row[15]),
                    mae=float(row[16]),
                    mfe=float(row[17]),
                    diagnostics=diagnostics,
                )
            )
    return rows


def _directional_return(trade: TradeRow, future_close: float) -> float:
    if trade.direction == "long":
        return future_close - trade.open_price
    return trade.open_price - future_close


def _forward_returns(trades: list[TradeRow]) -> dict[int, dict[int, float | None]]:
    cache: dict[Path, tuple[list[CsvBar], dict[datetime, int]]] = {}
    result: dict[int, dict[int, float | None]] = {}
    for idx, trade in enumerate(trades):
        if trade.data_src not in cache:
            cache[trade.data_src] = _load_csv(trade.data_src)
        bars, by_dt = cache[trade.data_src]
        open_idx = by_dt.get(trade.open_time)
        values: dict[int, float | None] = {}
        for n in FORWARD_BARS:
            if open_idx is None or open_idx + n >= len(bars):
                values[n] = None
                continue
            values[n] = _directional_return(trade, bars[open_idx + n].close)
        result[idx] = values
    return result


def _diag(trade: TradeRow, section: str, key: str) -> Any:
    value = trade.diagnostics.get(section, {}).get(key)
    return value


def _exit_group(trade: TradeRow) -> str:
    if trade.exit_reason == "time_exit":
        return "time_exit_pos" if trade.net_pnl > 0 else "time_exit_nonpos"
    return trade.exit_reason or "unknown"


def _overview_table(trades: list[TradeRow]) -> str:
    grouped: dict[tuple[int, str, int], list[TradeRow]] = defaultdict(list)
    for trade in trades:
        grouped[(trade.backtest_id, trade.symbol, trade.ticks)].append(trade)

    rows: list[list[str]] = []
    for key in sorted(grouped):
        rows_for_key = grouped[key]
        wins = sum(1 for trade in rows_for_key if trade.net_pnl > 0)
        losses = sum(1 for trade in rows_for_key if trade.net_pnl < 0)
        n = len(rows_for_key)
        rows.append(
            [
                str(key[0]),
                key[1],
                str(key[2]),
                str(n),
                str(wins),
                str(losses),
                _fmt(100 * wins / n),
                _fmt(sum(trade.net_pnl for trade in rows_for_key), 0),
                _fmt(mean(trade.mfe for trade in rows_for_key)),
                _fmt(mean(trade.mae for trade in rows_for_key)),
            ]
        )
    return _markdown_table(
        ["backtest_id", "symbol", "ticks", "n", "wins", "losses", "win_pct", "net_pnl", "avg_mfe", "avg_mae"],
        rows,
    )


def _exit_path_table(trades: list[TradeRow], forwards: dict[int, dict[int, float | None]]) -> str:
    grouped: dict[str, list[tuple[int, TradeRow]]] = defaultdict(list)
    for idx, trade in enumerate(trades):
        grouped[_exit_group(trade)].append((idx, trade))

    rows: list[list[str]] = []
    for group in sorted(grouped):
        items = grouped[group]
        group_trades = [trade for _, trade in items]
        forward_avgs = [_avg([forwards[idx][n] for idx, _ in items]) for n in FORWARD_BARS]
        wins = sum(1 for trade in group_trades if trade.net_pnl > 0)
        n = len(group_trades)
        rows.append(
            [
                group,
                str(n),
                _fmt(_sum([trade.net_pnl for trade in group_trades]), 0),
                _fmt(100 * wins / n),
                _fmt(mean(trade.mfe for trade in group_trades)),
                _fmt(mean(trade.mae for trade in group_trades)),
                *[_fmt(value) for value in forward_avgs],
            ]
        )
    return _markdown_table(
        ["exit_group", "n", "net_pnl", "win_pct", "avg_mfe", "avg_mae", "fwd_5", "fwd_15", "fwd_30", "fwd_60"],
        rows,
    )


def _diagnostics_table(trades: list[TradeRow]) -> str:
    grouped: dict[str, list[TradeRow]] = defaultdict(list)
    for trade in trades:
        grouped[_exit_group(trade)].append(trade)

    rows: list[list[str]] = []
    for group in sorted(grouped):
        group_trades = grouped[group]
        raw_rr = [float(value) for trade in group_trades if (value := _diag(trade, "risk", "raw_price_r_multiple")) is not None]
        expected_distance = [
            float(value) for trade in group_trades if (value := _diag(trade, "risk", "expected_profit_distance")) is not None
        ]
        strict_distance = [
            float(value) for trade in group_trades if (value := _diag(trade, "risk", "strict_failure_distance")) is not None
        ]
        va_width = [float(value) for trade in group_trades if (value := _diag(trade, "risk", "va_width")) is not None]
        reaccept_ratio = [
            float(value) for trade in group_trades if (value := _diag(trade, "risk", "reaccept_depth_va_ratio")) is not None
        ]
        edge_or_away = [bool(_diag(trade, "alpha", "would_filter_edge_or_away")) for trade in group_trades]
        poc_edges = Counter(str(_diag(trade, "alpha", "poc_edge_bucket")) for trade in group_trades)
        migrations = Counter(str(_diag(trade, "alpha", "current_acceptance_migration_bucket")) for trade in group_trades)
        rows.append(
            [
                group,
                str(len(group_trades)),
                _fmt(_avg(raw_rr), 3),
                _fmt(_avg(expected_distance)),
                _fmt(_avg(strict_distance)),
                _fmt(_avg(va_width)),
                _fmt(_avg(reaccept_ratio), 3),
                _fmt(100 * sum(edge_or_away) / len(edge_or_away)) if edge_or_away else "-",
                poc_edges.most_common(1)[0][0] if poc_edges else "-",
                migrations.most_common(1)[0][0] if migrations else "-",
            ]
        )
    return _markdown_table(
        [
            "exit_group",
            "n",
            "avg_raw_rr",
            "avg_expected_dist",
            "avg_strict_dist",
            "avg_va_width",
            "avg_reaccept_va_ratio",
            "edge_or_away_pct",
            "top_poc_edge",
            "top_migration",
        ],
        rows,
    )


def _concentration_table(trades: list[TradeRow]) -> str:
    grouped: dict[tuple[int, str, int], list[TradeRow]] = defaultdict(list)
    for trade in trades:
        grouped[(trade.backtest_id, trade.symbol, trade.ticks)].append(trade)

    rows: list[list[str]] = []
    for key in sorted(grouped):
        group_trades = grouped[key]
        pnl_values = sorted((trade.net_pnl for trade in group_trades if trade.net_pnl > 0), reverse=True)
        total_net = sum(trade.net_pnl for trade in group_trades)
        total_positive = sum(pnl_values)
        top1 = pnl_values[0] if pnl_values else 0.0
        top2 = sum(pnl_values[:2])
        top3 = sum(pnl_values[:3])
        rows.append(
            [
                str(key[0]),
                key[1],
                str(key[2]),
                str(len(group_trades)),
                _fmt(total_net, 0),
                _fmt(total_positive, 0),
                _fmt(100 * top1 / total_positive if total_positive else None),
                _fmt(total_net - top1, 0),
                _fmt(total_net - top2, 0),
                _fmt(total_net - top3, 0),
            ]
        )
    return _markdown_table(
        [
            "backtest_id",
            "symbol",
            "ticks",
            "n",
            "net_pnl",
            "positive_pnl",
            "top1_pos_share",
            "net_ex_top1",
            "net_ex_top2",
            "net_ex_top3",
        ],
        rows,
    )


def _trade_net_pnl_at_price(trade: TradeRow, exit_price: float) -> float:
    if trade.direction == "long":
        gross = (exit_price - trade.open_price) * trade.volume * trade.contract_multiplier
    else:
        gross = (trade.open_price - exit_price) * trade.volume * trade.contract_multiplier
    return gross - trade.commission - trade.slippage_cost


def _stop_price(trade: TradeRow, multiplier: float) -> float | None:
    strict_distance = _diag(trade, "risk", "strict_failure_distance")
    if strict_distance is None:
        return None
    distance = float(strict_distance) * multiplier
    if trade.direction == "long":
        return trade.open_price - distance
    return trade.open_price + distance


def _first_tighter_stop(
    trade: TradeRow,
    bars: list[CsvBar],
    by_dt: dict[datetime, int],
    multiplier: float,
) -> tuple[datetime, float] | None:
    stop_price = _stop_price(trade, multiplier)
    if stop_price is None:
        return None
    open_idx = by_dt.get(trade.open_time)
    close_idx = by_dt.get(trade.close_time)
    if open_idx is None or close_idx is None or close_idx <= open_idx:
        return None
    for bar in bars[open_idx + 1 : close_idx + 1]:
        if trade.direction == "long" and bar.low <= stop_price:
            return bar.dt, stop_price
        if trade.direction == "short" and bar.high >= stop_price:
            return bar.dt, stop_price
    return None


def _stop_counterfactuals(trades: list[TradeRow]) -> list[StopCounterfactual]:
    cache: dict[Path, tuple[list[CsvBar], dict[datetime, int]]] = {}
    results: list[StopCounterfactual] = []
    for trade in trades:
        if trade.data_src not in cache:
            cache[trade.data_src] = _load_csv(trade.data_src)
        bars, by_dt = cache[trade.data_src]
        for multiplier in STOP_WIDEN_MULTIPLIERS:
            stop_hit = _first_tighter_stop(trade, bars, by_dt, multiplier)
            if stop_hit is None:
                simulated_exit = trade.exit_reason
                simulated_net_pnl = trade.net_pnl
                earlier_stop = False
            else:
                _, exit_price = stop_hit
                simulated_exit = "counterfactual_stop"
                simulated_net_pnl = _trade_net_pnl_at_price(trade, exit_price)
                earlier_stop = trade.exit_reason != "stop_loss" or abs(simulated_net_pnl - trade.net_pnl) > 1e-9
            results.append(
                StopCounterfactual(
                    multiplier=multiplier,
                    original_exit=_exit_group(trade),
                    simulated_exit=simulated_exit,
                    original_net_pnl=trade.net_pnl,
                    simulated_net_pnl=simulated_net_pnl,
                    earlier_stop=earlier_stop,
                    killed_take_profit=earlier_stop and trade.exit_reason == "take_profit",
                    killed_positive_time_exit=earlier_stop and trade.exit_reason == "time_exit" and trade.net_pnl > 0,
                )
            )
    return results


def _stop_counterfactual_summary_table(trades: list[TradeRow]) -> str:
    rows: list[list[str]] = []
    results = _stop_counterfactuals(trades)
    for multiplier in STOP_WIDEN_MULTIPLIERS:
        items = [item for item in results if item.multiplier == multiplier]
        original_net = sum(item.original_net_pnl for item in items)
        simulated_net = sum(item.simulated_net_pnl for item in items)
        earlier_stop_n = sum(1 for item in items if item.earlier_stop)
        killed_take_profit_n = sum(1 for item in items if item.killed_take_profit)
        killed_time_exit_pos_n = sum(1 for item in items if item.killed_positive_time_exit)
        rows.append(
            [
                _fmt(multiplier, 1),
                str(len(items)),
                _fmt(original_net, 0),
                _fmt(simulated_net, 0),
                _fmt(simulated_net - original_net, 0),
                str(earlier_stop_n),
                str(killed_take_profit_n),
                str(killed_time_exit_pos_n),
            ]
        )
    return _markdown_table(
        [
            "stop_widen",
            "n",
            "original_net",
            "simulated_net",
            "delta",
            "earlier_stop_n",
            "killed_take_profit_n",
            "killed_time_exit_pos_n",
        ],
        rows,
    )


def _stop_counterfactual_by_exit_table(trades: list[TradeRow]) -> str:
    results = _stop_counterfactuals(trades)
    grouped: dict[tuple[float, str], list[StopCounterfactual]] = defaultdict(list)
    for item in results:
        grouped[(item.multiplier, item.original_exit)].append(item)

    rows: list[list[str]] = []
    for key in sorted(grouped):
        items = grouped[key]
        original_net = sum(item.original_net_pnl for item in items)
        simulated_net = sum(item.simulated_net_pnl for item in items)
        rows.append(
            [
                _fmt(key[0], 1),
                key[1],
                str(len(items)),
                _fmt(original_net, 0),
                _fmt(simulated_net, 0),
                _fmt(simulated_net - original_net, 0),
                str(sum(1 for item in items if item.earlier_stop)),
            ]
        )
    return _markdown_table(
        ["stop_widen", "original_exit", "n", "original_net", "simulated_net", "delta", "earlier_stop_n"],
        rows,
    )


def _actual_stop_distance(trade: TradeRow) -> float | None:
    actual = _diag(trade, "risk", "actual_stop_distance")
    if actual is not None:
        return float(actual)
    strict = _diag(trade, "risk", "strict_failure_distance")
    if strict is None:
        return None
    return float(strict)


def _atr_by_dt(bars: list[CsvBar], atr_bars: int = ATR_BARS) -> dict[datetime, float]:
    true_ranges: list[float] = []
    result: dict[datetime, float] = {}
    for idx, bar in enumerate(bars):
        if idx == 0:
            true_range = bar.high - bar.low
        else:
            prev_close = bars[idx - 1].close
            true_range = max(bar.high - bar.low, abs(bar.high - prev_close), abs(bar.low - prev_close))
        true_ranges.append(true_range)
        if len(true_ranges) >= atr_bars:
            result[bar.dt] = mean(true_ranges[-atr_bars:])
    return result


def _atr_ratio_bucket(ratio: float) -> str:
    for low, high, label in ATR_RATIO_BUCKETS:
        if low <= ratio < high:
            return label
    return ATR_RATIO_BUCKETS[-1][2]


def _stop_atr_ratio_rows(trades: list[TradeRow]) -> list[tuple[TradeRow, float, float, float, str]]:
    cache: dict[Path, tuple[list[CsvBar], dict[datetime, float]]] = {}
    rows: list[tuple[TradeRow, float, float, float, str]] = []
    for trade in trades:
        if trade.data_src not in cache:
            bars, _ = _load_csv(trade.data_src)
            cache[trade.data_src] = (bars, _atr_by_dt(bars))
        _, atr_map = cache[trade.data_src]
        stop_distance = _actual_stop_distance(trade)
        atr = atr_map.get(trade.open_time)
        if stop_distance is None or atr is None or atr <= 0:
            continue
        ratio = stop_distance / atr
        rows.append((trade, stop_distance, atr, ratio, _atr_ratio_bucket(ratio)))
    return rows


def _stop_atr_summary_table(rows: list[tuple[TradeRow, float, float, float, str]], group_by: str) -> str:
    grouped: dict[tuple[str, ...], list[tuple[TradeRow, float, float, float, str]]] = defaultdict(list)
    for item in rows:
        trade = item[0]
        bucket = item[4]
        if group_by == "symbol":
            key = (str(trade.backtest_id), trade.symbol)
        elif group_by == "bucket":
            key = (bucket,)
        elif group_by == "symbol_bucket":
            key = (trade.symbol, bucket)
        else:
            raise ValueError(f"未知 group_by: {group_by}")
        grouped[key].append(item)

    def sort_key(key: tuple[str, ...]) -> tuple[str, int]:
        bucket_order = {label: idx for idx, (_, _, label) in enumerate(ATR_RATIO_BUCKETS)}
        if group_by == "bucket":
            return ("", bucket_order.get(key[0], 99))
        if group_by == "symbol_bucket":
            return (key[0], bucket_order.get(key[1], 99))
        return (key[1], int(key[0]))

    table_rows: list[list[str]] = []
    for key in sorted(grouped, key=sort_key):
        items = grouped[key]
        trades = [item[0] for item in items]
        stops = [item[1] for item in items]
        atrs = [item[2] for item in items]
        ratios = [item[3] for item in items]
        wins = sum(1 for trade in trades if trade.net_pnl > 0)
        losses = sum(1 for trade in trades if trade.net_pnl < 0)
        n = len(trades)
        prefix = list(key)
        table_rows.append(
            [
                *prefix,
                str(n),
                str(wins),
                str(losses),
                _fmt(100 * wins / n),
                _fmt(sum(trade.net_pnl for trade in trades), 0),
                _fmt(mean(trade.net_pnl for trade in trades), 0),
                _fmt(mean(ratios), 2),
                _fmt(mean(stops), 2),
                _fmt(mean(atrs), 2),
                str(sum(1 for trade in trades if trade.exit_reason == "stop_loss")),
                str(sum(1 for trade in trades if trade.exit_reason == "strict_failure_close")),
                str(sum(1 for trade in trades if trade.exit_reason == "take_profit")),
                str(sum(1 for trade in trades if trade.exit_reason == "time_exit")),
            ]
        )

    prefix_headers = {
        "symbol": ["backtest_id", "symbol"],
        "bucket": ["stop_atr_bucket"],
        "symbol_bucket": ["symbol", "stop_atr_bucket"],
    }[group_by]
    return _markdown_table(
        [
            *prefix_headers,
            "n",
            "wins",
            "losses",
            "win_pct",
            "net_pnl",
            "avg_pnl",
            "avg_stop_atr",
            "avg_stop",
            "avg_atr20",
            "stop_loss_n",
            "strict_n",
            "tp_n",
            "time_n",
        ],
        table_rows,
    )


def _stop_atr_widest_table(rows: list[tuple[TradeRow, float, float, float, str]], limit: int = 12) -> str:
    table_rows: list[list[str]] = []
    for trade, stop_distance, atr, ratio, bucket in sorted(rows, key=lambda item: item[3], reverse=True)[:limit]:
        table_rows.append(
            [
                str(trade.backtest_id),
                trade.symbol,
                trade.open_time.strftime("%Y-%m-%d %H:%M"),
                trade.exit_reason,
                _fmt(trade.net_pnl, 0),
                _fmt(stop_distance, 2),
                _fmt(atr, 2),
                _fmt(ratio, 2),
                bucket,
            ]
        )
    return _markdown_table(
        ["backtest_id", "symbol", "open_time", "exit", "net_pnl", "stop", "atr20", "stop_atr", "bucket"],
        table_rows,
    )


def _stop_atr_ratio_report(trades: list[TradeRow]) -> str:
    rows = _stop_atr_ratio_rows(trades)
    return "\n\n".join(
        [
            "## 第三轮结构诊断输出：stop_distance / ATR20 分桶",
            "",
            "### A. 按合约汇总",
            "",
            _stop_atr_summary_table(rows, "symbol"),
            "",
            "### B. 按 stop_distance / ATR20 分桶",
            "",
            _stop_atr_summary_table(rows, "bucket"),
            "",
            "### C. 按合约与分桶交叉",
            "",
            _stop_atr_summary_table(rows, "symbol_bucket"),
            "",
            "### D. stop/ATR 最大的交易",
            "",
            _stop_atr_widest_table(rows),
        ]
    )


def _passes_atr_filter(filter_name: str, ratio: float) -> bool:
    if filter_name == "baseline":
        return True
    if filter_name == "drop_lt_1":
        return ratio >= 1.0
    if filter_name == "drop_2_3":
        return not 2.0 <= ratio < 3.0
    if filter_name == "drop_lt1_and_2_3":
        return ratio >= 1.0 and not 2.0 <= ratio < 3.0
    if filter_name == "max_2_0":
        return ratio < 2.0
    if filter_name == "max_2_5":
        return ratio < 2.5
    if filter_name == "max_3_0":
        return ratio < 3.0
    if filter_name == "range_1_0_2_0":
        return 1.0 <= ratio < 2.0
    if filter_name == "range_1_0_3_0":
        return 1.0 <= ratio < 3.0
    if filter_name == "range_1_5_2_0":
        return 1.5 <= ratio < 2.0
    raise ValueError(f"未知 ATR filter: {filter_name}")


def _atr_filter_names() -> list[str]:
    return [
        "baseline",
        "drop_lt_1",
        "drop_2_3",
        "drop_lt1_and_2_3",
        "max_2_0",
        "max_2_5",
        "max_3_0",
        "range_1_0_2_0",
        "range_1_0_3_0",
        "range_1_5_2_0",
    ]


def _atr_filter_summary_table(rows: list[tuple[TradeRow, float, float, float, str]]) -> str:
    original_trades = [item[0] for item in rows]
    original_net = sum(trade.net_pnl for trade in original_trades)
    table_rows: list[list[str]] = []
    for filter_name in _atr_filter_names():
        kept = [item[0] for item in rows if _passes_atr_filter(filter_name, item[3])]
        removed_n = len(rows) - len(kept)
        n = len(kept)
        wins = sum(1 for trade in kept if trade.net_pnl > 0)
        losses = sum(1 for trade in kept if trade.net_pnl < 0)
        net = sum(trade.net_pnl for trade in kept)
        table_rows.append(
            [
                filter_name,
                str(n),
                str(removed_n),
                str(wins),
                str(losses),
                _fmt(100 * wins / n if n else None),
                _fmt(net, 0),
                _fmt(mean(trade.net_pnl for trade in kept) if kept else None, 0),
                _fmt(net - original_net, 0),
                str(sum(1 for trade in kept if trade.exit_reason == "stop_loss")),
                str(sum(1 for trade in kept if trade.exit_reason == "take_profit")),
                str(sum(1 for trade in kept if trade.exit_reason == "time_exit")),
            ]
        )
    return _markdown_table(
        [
            "filter",
            "kept_n",
            "removed_n",
            "wins",
            "losses",
            "win_pct",
            "net_pnl",
            "avg_pnl",
            "delta_vs_base",
            "stop_loss_n",
            "tp_n",
            "time_n",
        ],
        table_rows,
    )


def _atr_filter_by_symbol_table(rows: list[tuple[TradeRow, float, float, float, str]]) -> str:
    table_rows: list[list[str]] = []
    for filter_name in _atr_filter_names():
        grouped: dict[str, list[TradeRow]] = defaultdict(list)
        for trade, _, _, ratio, _ in rows:
            if _passes_atr_filter(filter_name, ratio):
                grouped[trade.symbol].append(trade)
        for symbol in sorted({item[0].symbol for item in rows}):
            kept = grouped.get(symbol, [])
            n = len(kept)
            wins = sum(1 for trade in kept if trade.net_pnl > 0)
            net = sum(trade.net_pnl for trade in kept)
            table_rows.append(
                [
                    filter_name,
                    symbol,
                    str(n),
                    str(wins),
                    _fmt(100 * wins / n if n else None),
                    _fmt(net, 0),
                    _fmt(mean(trade.net_pnl for trade in kept) if kept else None, 0),
                ]
            )
    return _markdown_table(["filter", "symbol", "kept_n", "wins", "win_pct", "net_pnl", "avg_pnl"], table_rows)


def _atr_bucket_concentration_table(rows: list[tuple[TradeRow, float, float, float, str]]) -> str:
    grouped: dict[str, list[TradeRow]] = defaultdict(list)
    for trade, _, _, _, bucket in rows:
        grouped[bucket].append(trade)

    table_rows: list[list[str]] = []
    bucket_order = {label: idx for idx, (_, _, label) in enumerate(ATR_RATIO_BUCKETS)}
    for bucket in sorted(grouped, key=lambda item: bucket_order.get(item, 99)):
        trades = grouped[bucket]
        wins = sorted((trade.net_pnl for trade in trades if trade.net_pnl > 0), reverse=True)
        total_net = sum(trade.net_pnl for trade in trades)
        positive_pnl = sum(wins)
        top1 = wins[0] if wins else 0.0
        top2 = sum(wins[:2])
        table_rows.append(
            [
                bucket,
                str(len(trades)),
                _fmt(total_net, 0),
                _fmt(positive_pnl, 0),
                _fmt(100 * top1 / positive_pnl if positive_pnl else None),
                _fmt(total_net - top1, 0),
                _fmt(total_net - top2, 0),
            ]
        )
    return _markdown_table(
        ["bucket", "n", "net_pnl", "positive_pnl", "top1_pos_share", "net_ex_top1", "net_ex_top2"],
        table_rows,
    )


def _stop_atr_filter_report(trades: list[TradeRow]) -> str:
    rows = _stop_atr_ratio_rows(trades)
    return "\n\n".join(
        [
            "## 第四轮结构诊断输出：stop/ATR 过滤反事实",
            "",
            "### A. 过滤规则汇总",
            "",
            _atr_filter_summary_table(rows),
            "",
            "### B. 过滤后分合约表现",
            "",
            _atr_filter_by_symbol_table(rows),
            "",
            "### C. 各 stop/ATR 桶盈利集中度",
            "",
            _atr_bucket_concentration_table(rows),
        ]
    )


def build_report(
    db_path: Path,
    backtest_ids: list[int],
    section: Literal["all", "paths", "stop", "atr", "atr_filter"] = "all",
) -> str:
    trades = _load_trades(db_path, backtest_ids)
    non_1m = sorted({trade.backtest_id for trade in trades if trade.kline_interval != "1m"})
    if non_1m:
        raise ValueError(f"发现非 1m 样本: {non_1m}")

    lines: list[str] = []
    if section in {"all", "paths"}:
        forwards = _forward_returns(trades)
        lines.extend(
            [
                "## 第一轮结构诊断输出",
                "",
                "### A. 样本总览",
                "",
                _overview_table(trades),
                "",
                "### B. 按 exit_group 的路径表现",
                "",
                _exit_path_table(trades, forwards),
                "",
                "### C. 按 exit_group 的入场诊断字段",
                "",
                _diagnostics_table(trades),
                "",
                "### D. 盈利集中度",
                "",
                _concentration_table(trades),
            ]
        )
    if section in {"all", "stop"}:
        if lines:
            lines.append("")
        lines.extend(
            [
                "## 第二轮结构诊断输出：stop_widen_multiplier 反事实",
                "",
                "### A. 总览",
                "",
                _stop_counterfactual_summary_table(trades),
                "",
                "### B. 按原始 exit_group 拆分",
                "",
                _stop_counterfactual_by_exit_table(trades),
            ]
        )
    if section in {"all", "atr"}:
        if lines:
            lines.append("")
        lines.append(_stop_atr_ratio_report(trades))
    if section in {"all", "atr_filter"}:
        if lines:
            lines.append("")
        lines.append(_stop_atr_filter_report(trades))
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="value_area_reacceptance 结构拆解诊断")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--backtest-ids", nargs="+", type=int, default=DEFAULT_BACKTEST_IDS)
    parser.add_argument("--section", choices=["all", "paths", "stop", "atr", "atr_filter"], default="all")
    args = parser.parse_args()

    print(build_report(args.db, args.backtest_ids, args.section))


if __name__ == "__main__":
    main()
