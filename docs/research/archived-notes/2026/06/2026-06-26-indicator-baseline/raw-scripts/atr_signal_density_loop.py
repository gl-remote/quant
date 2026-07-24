"""ATR 信号密度研究性 loop。

该脚本通过真实 CLI no-search 回测执行多组 ATR 释放机制变体，
再从回测数据库汇总交易数、持仓周期和退出原因。
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "project_data" / "database" / "backtest" / "quant.db"
CONFIG_PATH = ROOT / "workspace" / "config" / "conf.backtest.local.toml"
PATTERN = "DCE\\.m260[135]"


@dataclass(frozen=True)
class LoopVariant:
    name: str
    time_stop_bars: int = 48
    entry_cooldown_minutes: int = 10
    exit_on_reverse_signal: bool = False


VARIANTS = [
    LoopVariant(name="r13_base"),
    LoopVariant(name="weak_cooldown", entry_cooldown_minutes=0),
    LoopVariant(name="fast_release", time_stop_bars=24, entry_cooldown_minutes=0),
    LoopVariant(name="reverse_release", entry_cooldown_minutes=0, exit_on_reverse_signal=True),
]


def _write_local_config(variant: LoopVariant) -> str | None:
    previous = CONFIG_PATH.read_text() if CONFIG_PATH.exists() else None
    CONFIG_PATH.write_text(
        f"""[[strategies]]
name = "atr"
enabled = true
sma_short = 20
sma_long = 60
stop_loss_ratio = 0.3
take_profit_ratio = 0.5
position_ratio = 1.0
kline_period = 1
atr_period = 14
atr_stop_loss_multiplier = 2.5
atr_take_profit_multiplier = 4.0
kdj_oversold = 30
kdj_overbought = 70
kdj_pullback_long = 45
kdj_pullback_short = 55
kdj_signal_long = 50
kdj_signal_short = 50
time_stop_bars = {variant.time_stop_bars}
entry_cooldown_minutes = {variant.entry_cooldown_minutes}
exit_on_reverse_signal = {str(variant.exit_on_reverse_signal).lower()}
trailing_activation_atr = 2.0
trailing_drawdown_ratio = 0.3
"""
    )
    return previous


def _restore_local_config(previous: str | None) -> None:
    if previous is None:
        CONFIG_PATH.unlink(missing_ok=True)
    else:
        CONFIG_PATH.write_text(previous)


def _run_variant(variant: LoopVariant) -> int:
    with sqlite3.connect(DB_PATH) as conn:
        before_row = conn.execute("select coalesce(max(id), 0) from runs").fetchone()
    before_run_id = int(before_row[0]) if before_row else 0
    cmd = [
        "uv",
        "run",
        "python",
        "main.py",
        "backtest",
        "--env",
        "backtest",
        "--pattern",
        PATTERN,
        "--strategy",
        "atr",
        "--mode",
        "search",
        "--no-search",
        "--capital",
        "100000",
        "--contract-size",
        "10",
    ]
    subprocess.run(cmd, cwd=ROOT, check=True)
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "select max(id) from runs where strategy='atr' and id > ?",
            (before_run_id,),
        ).fetchone()
    if row is None or row[0] is None:
        raise RuntimeError(f"无法定位 {variant.name} 的 run_id")
    return int(row[0])


def _reason_name(reason: str) -> str:
    if not reason.startswith("{"):
        return reason
    try:
        data = json.loads(reason)
    except json.JSONDecodeError:
        return reason
    return str(data.get("r", reason))


def _bar_index(symbol: str) -> dict[datetime, int]:
    csv_path = ROOT / "project_data" / "market_data" / "csv" / f"{symbol}.tqsdk.5m.csv"
    with csv_path.open() as f:
        next(f)
        return {datetime.fromisoformat(line.split(",", 1)[0]): idx for idx, line in enumerate(f)}


def _variant_rows(variant: LoopVariant, run_id: int) -> list[dict[str, object]]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        backtests = conn.execute(
            "select id, symbol, total_return, max_drawdown from backtests where run_id=? order by symbol",
            (run_id,),
        ).fetchall()
        rows: list[dict[str, object]] = []
        for bt in backtests:
            trades = conn.execute(
                "select datetime, offset, reason from backtest_trades where backtest_id=? order by datetime",
                (bt["id"],),
            ).fetchall()
            entries = [t for t in trades if t["offset"] == "open"]
            exits = [t for t in trades if t["offset"] != "open"]
            hold_bars: list[int] = []
            exit_reasons: dict[str, int] = {}
            bar_index = _bar_index(bt["symbol"])
            last_open: datetime | None = None
            for trade in trades:
                dt = datetime.fromisoformat(str(trade["datetime"]))
                if trade["offset"] == "open":
                    last_open = dt
                    continue
                if last_open is not None:
                    hold_bars.append(max(bar_index.get(dt, 0) - bar_index.get(last_open, 0), 0))
                    last_open = None
                reason = _reason_name(str(trade["reason"] or ""))
                exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
            avg_hold = sum(hold_bars) / len(hold_bars) if hold_bars else 0.0
            rows.append(
                {
                    "variant": variant.name,
                    "run_id": run_id,
                    "symbol": bt["symbol"],
                    "entries": len(entries),
                    "exits": len(exits),
                    "avg_hold_bars": round(avg_hold, 1),
                    "max_hold_bars": max(hold_bars) if hold_bars else 0,
                    "exit_1d_ratio": round(sum(1 for bars in hold_bars if bars <= 48) / len(hold_bars), 2)
                    if hold_bars
                    else 0.0,
                    "exit_gt_2d_ratio": round(sum(1 for bars in hold_bars if bars > 96) / len(hold_bars), 2)
                    if hold_bars
                    else 0.0,
                    "total_return": round(float(bt["total_return"] or 0.0), 2),
                    "max_drawdown": round(float(bt["max_drawdown"] or 0.0), 2),
                    "exit_reasons": ",".join(f"{k}:{v}" for k, v in sorted(exit_reasons.items())),
                }
            )
    return rows


def _print_table(rows: list[dict[str, object]]) -> None:
    cols = [
        "variant",
        "run_id",
        "symbol",
        "entries",
        "exits",
        "avg_hold_bars",
        "max_hold_bars",
        "exit_1d_ratio",
        "exit_gt_2d_ratio",
        "total_return",
        "max_drawdown",
        "exit_reasons",
    ]
    widths = {col: max(len(col), *(len(str(row[col])) for row in rows)) for col in cols}
    print(" ".join(col.ljust(widths[col]) for col in cols))
    for row in rows:
        print(" ".join(str(row[col]).ljust(widths[col]) for col in cols))

    summary: dict[str, dict[str, float]] = {}
    for row in rows:
        variant = str(row["variant"])
        item = summary.setdefault(variant, {"entries": 0, "exits": 0})
        item["entries"] += float(row["entries"])
        item["exits"] += float(row["exits"])
    print("\n=== variant summary ===")
    for variant, item in summary.items():
        print(f"{variant}: entries={int(item['entries'])} exits={int(item['exits'])}")


def main() -> None:
    previous = None
    rows: list[dict[str, object]] = []
    try:
        previous = _write_local_config(VARIANTS[0])
        for variant in VARIANTS:
            _write_local_config(variant)
            run_id = _run_variant(variant)
            rows.extend(_variant_rows(variant, run_id))
    finally:
        _restore_local_config(previous)
    _print_table(rows)


if __name__ == "__main__":
    main()
