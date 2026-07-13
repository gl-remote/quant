"""VA 非对称复合策略 · 全样本框架回测对比（修复 bridge 回归后）。

对照口径（关键，避免苹果比橘子）:
  - 框架 VAAsymmetryCompositeStrategy 的 A 层查表用 A_TIER_RAW（13 个 raw tier），
    与研究引擎 P1.load_events()(B0 基线宇宙) 同宇宙 —— 故框架对应 B0 宇宙，
    NOT spec B 全六阵营宇宙(566 笔)。
  - (A) 框架: 真实 vnpy 引擎跑 VAAsymmetryCompositeStrategy，逐合约，首根 entry_tf bar 进场
            → 逐日 net_pnl → 等权汇总组合日收益 → 年化/夏普/MaxDD
  - (B) 研究(匹配宇宙): P1.load_events()(A_TIER_RAW) + P1.simulate_contract(event_time 进场)
            → 同口径汇总 → 组合日收益 → 年化/夏普/MaxDD
  - 唯一系统差异 = 进场时点(首根 bar vs event_time) + 撮合(vnpy 次根 vs close_t)。
  - 注: 两侧均不施加 Cap 组合压仓(框架单合约无法做)，故为"无 cap"口径；
        spec B 全样本 68.47%/3.96 是 Cap=4.0 且不同宇宙，仅作参考标注。

用法: 仓库根目录  uv run python scripts/ai_tmp/va_full_backtest_compare.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

import loguru

loguru.logger.remove()
loguru.logger.add(sys.stderr, level="WARNING")

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "workspace"))
sys.path.insert(0, str(REPO / "scripts" / "ai_tmp"))

import va_composite_p1_cap as P1  # noqa: E402
from backtest.vnpy_backtest_engine import VnpyBacktestEngine  # noqa: E402
from config import ConfigManager  # noqa: E402
from config.app_config import BacktestConfig  # noqa: E402
from data import DataManager  # noqa: E402

_cm = ConfigManager(env="backtest")
DataManager(_cm)
from strategies import (  # noqa: E402
    VAAsymmetryCompositeParams,
    VAAsymmetryCompositeStrategy,
)
from strategies.va_asymmetry_composite_strategy import A_TIER_RAW  # noqa: E402

TL_PATH = "project_data/logs/poc_va_asymmetry_stage4/classifier_v31_timeline.parquet"
CSV_DIR = Path("project_data/market_data/csv")
EQUITY = 1_000_000.0


def _portfolio_metrics(daily_pnl_by_contract: dict, label: str) -> dict:
    if not daily_pnl_by_contract:
        print(f"[{label}] 无数据")
        return {}
    mat = pd.DataFrame(daily_pnl_by_contract).fillna(0.0)
    port_daily = mat.sum(axis=1).sort_index()
    # 关键修正: 补齐到完整交易日历(bdate_range), 否则只有"有交易的天"进均值,
    # 年化会被放大数倍(之前 B 侧 115% 的 bug 根源: 200 交易天 vs ~695 交易日历)。
    lo, hi = port_daily.index.min(), port_daily.index.max()
    bidx = pd.bdate_range(lo, hi)
    port_daily = port_daily.reindex(bidx, fill_value=0.0)
    ret = port_daily / EQUITY
    ann = float(ret.mean() * 252)
    sd = float(ret.std())
    sharpe = float(ret.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0
    equity = EQUITY + port_daily.cumsum()
    dd = (equity - equity.cummax()) / equity.cummax()
    maxdd = float(dd.min())
    n_active = int((mat != 0).any(axis=1).sum())
    n_contracts = mat.shape[1]
    print(f"[{label}] 年化={ann*100:6.2f}%  夏普={sharpe:5.2f}  MaxDD={maxdd*100:6.2f}%  "
          f"活跃日={n_active}  合约数={n_contracts}")
    return {"ann": ann, "sharpe": sharpe, "maxdd": maxdd, "n_days": n_active,
            "n_contracts": n_contracts}


def main() -> None:
    print("=" * 70)
    print("VA 非对称复合 · 全样本框架回测 vs 研究(B0 同宇宙)对比")
    print("=" * 70)

    # ── 0. 白名单合约(与研究引擎同 A 层) ──
    tl = pd.read_parquet(TL_PATH, columns=["contract", "tier"])
    wl = tl[tl["tier"].isin(A_TIER_RAW)]
    contracts = sorted(wl["contract"].unique())
    print(f"白名单合约(timeline 内, A_TIER_RAW): {len(contracts)}")

    # ── 1. 装载 5m bar(同源) ──
    pairs = []
    csv_map: dict[str, pd.DataFrame] = {}
    for c in contracts:
        fp = CSV_DIR / f"{c}.tqsdk.5m.csv"
        if not fp.exists():
            continue
        df = pd.read_csv(fp)
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.sort_values("datetime").reset_index(drop=True)
        pairs.append((c, df, "va_asymmetry_composite", {}))
        csv_map[c] = df
    print(f"有 5m 数据可回测的合约: {len(pairs)}")

    # ── 2. (A) 框架策略经真实 vnpy 引擎(全样本) ──
    cfg = BacktestConfig(
        initial_capital=EQUITY,
        commission_rate=0.0002,
        slippage=0.0,
        price_tick=1.0,
        contract_size=10,
        interval="5m",
    )
    A_daily: dict[str, pd.Series] = {}
    ok = fail = 0
    n_trades_total = 0
    for c, df, name, params in pairs:
        try:
            eng = VnpyBacktestEngine(cfg)
            res = eng.run([(c, df, name, params)], batch_mode=True)
            r = res[0]
            if not r.success:
                print(f"  [A] FAIL {c}: {r.error_message}")
                fail += 1
                continue
            dr = pd.DataFrame(r.daily_results)
            n_trades_total += int(r.total_trades or 0)
            if dr.empty or "net_pnl" not in dr.columns:
                A_daily[c] = pd.Series(dtype=float)
                ok += 1
                continue
            datecol = [col for col in dr.columns if col not in (
                "net_pnl", "commission", "slippage", "turnover", "trade_count")][0]
            s = dr.set_index(datecol)["net_pnl"]
            s.index = pd.to_datetime(s.index).date
            A_daily[c] = s
            ok += 1
        except Exception as e:  # noqa: BLE001
            print(f"  [A] ERR {c}: {repr(e)}")
            fail += 1
    print(f"[A] 框架成功 {ok} / 失败 {fail} / 总成交 {n_trades_total}")
    mA = _portfolio_metrics(A_daily, "A: 框架(vnpy, 首根bar进场)")

    # ── 3. (B) 研究引擎 P1.load_events()(A_TIER_RAW, B0 同宇宙) ──
    events = P1.load_events()
    B_daily: dict[str, pd.Series] = {}
    for c, g in events.groupby("contract"):
        if c not in csv_map:
            continue
        P1.bars = csv_map[c]
        try:
            rows = P1.simulate_contract(c, g)
        except Exception as e:  # noqa: BLE001
            print(f"  [B] ERR {c}: {repr(e)}")
            continue
        if not rows:
            continue
        tdf = pd.DataFrame(rows)
        if "_exit_date" not in tdf.columns or tdf.empty:
            continue
        s = tdf.groupby("_exit_date")["pnl_net_ccy"].sum()
        s.index = pd.to_datetime(s.index).date
        B_daily[c] = s
    mB = _portfolio_metrics(B_daily, "B: 研究(load_events, event_time进场)")

    # ── 4. 对照 ──
    print("\n" + "=" * 70)
    print("对照（同 A 层 / 同 sizing / 同 SL+时间退出，仅进场时点不同）")
    print("=" * 70)
    if mA and mB:
        print(f"  年化:   A={mA['ann']*100:6.2f}%   B={mB['ann']*100:6.2f}%   "
              f"Δ={(mA['ann']-mB['ann'])*100:+.2f}pp")
        print(f"  夏普:   A={mA['sharpe']:5.2f}        B={mB['sharpe']:5.2f}        "
              f"Δ={mA['sharpe']-mB['sharpe']:+.2f}")
        print(f"  MaxDD:  A={mA['maxdd']*100:6.2f}%   B={mB['maxdd']*100:6.2f}%   "
              f"Δ={(mA['maxdd']-mB['maxdd'])*100:+.2f}pp")
    print("\n参考(不同宇宙/含 Cap=4.0 压仓, 非同口径):")
    print("  spec 策略 B 全样本(va_composite_backtest.py): 年化 68.47% / 夏普 3.96 / MaxDD -7.42% (566 笔, v40 全六阵营)")
    print("  B0 基线(同上脚本, Cap=4.0):                 年化 35.42% / 夏普 3.50 / MaxDD -4.95% (312 笔)")


if __name__ == "__main__":
    main()
