"""隔离 harness：绕开 vnpy 子进程，用真实 m2409 5m 棒直接驱动策略+复刻 bridge 派发，
验证 Fix A（墙钟计时）与开盘宽限（open_grace）的联合行为。
仅用于本地验证，不进生产。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # workspace

from common.constants import TRADE_DIRECTION_LONG, TRADE_DIRECTION_SHORT, TRADE_ACTION_BUY, TRADE_ACTION_SELL
from strategies.core import Bar, Signal, State, StrategyPosition
from strategies.runtime.requirements import BarContext
from strategies.va_asymmetry_composite_strategy import (
    VAAsymmetryCompositeParams,
    VAAsymmetryCompositeStrategy,
)


def main() -> None:
    csv = Path("project_data/market_data/csv/DCE.m2409.tqsdk.5m.csv")
    df = pd.read_csv(csv)
    df["datetime"] = pd.to_datetime(df["datetime"])
    start, end = pd.Timestamp("2024-06-04"), pd.Timestamp("2024-06-07 23:59")
    df = df[(df["datetime"] >= start) & (df["datetime"] <= end)].reset_index(drop=True)
    print(f"[harness] m2409 5m bars in window: {len(df)} | {df['datetime'].min()} -> {df['datetime'].max()}")

    core = VAAsymmetryCompositeStrategy()
    cfg = VAAsymmetryCompositeParams()
    state = State(
        symbol="DCE.m2409",
        period="5m",
        strategy_config=cfg,
        capital=100_000.0,
        contract_size=10,
    )

    fills: list[dict] = []
    open_trade: dict | None = None  # 当前持仓开仓记录

    def dispatch(sig: Signal, bar_time: pd.Timestamp, price: float) -> None:
        nonlocal open_trade
        act = sig.action
        pos = state.position.direction
        if act == TRADE_ACTION_BUY and pos in ("", None):
            # 开多
            state.position = StrategyPosition(direction=TRADE_DIRECTION_LONG, entry_price=price, volume=sig.volume)
            open_trade = {"side": "long", "entry_t": bar_time, "entry_px": price, "vol": sig.volume, "reason": sig.reason}
            fills.append(open_trade)
        elif act == TRADE_ACTION_SELL and pos in ("", None):
            # 开空
            state.position = StrategyPosition(direction=TRADE_DIRECTION_SHORT, entry_price=price, volume=sig.volume)
            open_trade = {"side": "short", "entry_t": bar_time, "entry_px": price, "vol": sig.volume, "reason": sig.reason}
            fills.append(open_trade)
        elif act == TRADE_ACTION_BUY and pos == TRADE_DIRECTION_SHORT:
            # 平空
            dur = (bar_time - open_trade["entry_t"]).total_seconds() / 3600.0
            fills.append({"side": "close_short", "entry_t": open_trade["entry_t"], "exit_t": bar_time,
                          "exit_px": price, "hold_h": dur, "reason": sig.reason})
            state.position = StrategyPosition()
            open_trade = None
        elif act == TRADE_ACTION_SELL and pos == TRADE_DIRECTION_LONG:
            # 平多
            dur = (bar_time - open_trade["entry_t"]).total_seconds() / 3600.0
            fills.append({"side": "close_long", "entry_t": open_trade["entry_t"], "exit_t": bar_time,
                          "exit_px": price, "hold_h": dur, "reason": sig.reason})
            state.position = StrategyPosition()
            open_trade = None
        else:
            print(f"[harness][WARN] 未处理的 signal {act} pos={pos} @{bar_time}")

    for _, row in df.iterrows():
        bar_time = row["datetime"]
        bar = Bar(symbol="DCE.m2409", datetime=bar_time.to_pydatetime(),
                  open=float(row["open"]), high=float(row["high"]),
                  low=float(row["low"]), close=float(row["close"]), volume=float(row["volume"]))
        ctx = BarContext(symbol="DCE.m2409", bar=bar, multi={}, events=[])
        sig = core.on_bar(state, ctx)
        if sig.action:
            dispatch(sig, bar_time, float(row["close"]))

    # 汇总
    print(f"\n[harness] 总 fill 记录: {len(fills)}")
    opens = [f for f in fills if f.get("side") in ("long", "short")]
    closes = [f for f in fills if f.get("side") in ("close_long", "close_short")]
    print(f"[harness] 开仓次数: {len(opens)} | 平仓次数: {len(closes)}")

    print("\n=== 开仓明细（验证开盘宽限：首笔不应为 09:05）===")
    for o in opens:
        print(f"  {o['side']:5s} @ {o['entry_t']}  px={o['entry_px']:.1f} vol={o['vol']:.3f} reason={o['reason']}")

    print("\n=== 平仓明细（验证 Fix A 墙钟计时：持仓应≈8h/10h，非数日）===")
    for c in closes:
        print(f"  {c['side']:12s} entry={c['entry_t']} exit={c['exit_t']} hold={c['hold_h']:.2f}h reason={c['reason']}")

    # 断言
    print("\n=== 校验 ===")
    if opens:
        first_open_t = opens[0]["entry_t"]
        ok_grace = not (first_open_t.hour == 9 and first_open_t.minute == 5)
        print(f"  开盘宽限: 首笔开仓 {first_open_t} -> {'OK ✅ 非09:05' if ok_grace else 'FAIL ❌ 仍在09:05'}")
    else:
        print("  开盘宽限: 无开仓，无法验证 ⚠️")
    bad = [c for c in closes if c["hold_h"] > 24]
    print(f"  Fix A 墙钟计时: 持仓>24h 的平仓数 = {len(bad)} -> {'OK ✅ 无跨日长持' if not bad else 'FAIL ❌ 存在'+str(bad)}")


if __name__ == "__main__":
    main()
