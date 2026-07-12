#!/usr/bin/env python3
"""
va-asymmetry · 旧管线全链路复现

目的：复现旧全链路结果（32% 年化 / 3.06 夏普 / 148 事件），与 va_composite_p1_cap.py
     共用同一 B0 管线，仅调整数据源和分类规则。

数据源: classifier_v31_timeline.parquet（旧 v31 timeline，非 spec 版本）
分类器: 旧 13-tier A_TIER_RAW 白名单（无 tier_v40 映射，直接用旧 tier）
引擎: P1 冻结引擎（5m 精确模拟 + Cap=4.0 压仓）

运行: uv run python scripts/va_legacy_backtest.py
输出: project_data/va_legacy_backtest/{summary.md, trades.parquet}
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "workspace"))
sys.path.insert(0, str(REPO / "scripts" / "ai_tmp"))

from common.contract_specs import CONTRACT_SPECS  # noqa: E402
from common.symbol_utils import extract_contract_prefix  # noqa: E402

# ---- P1 复用 ----
from va_composite_p1_cap import (  # noqa: E402
    simulate_contract, compress, assign_equity, base_metrics, active_day_set,
    monthly_win_rate, per_trade_ir, nu_implied,
    A_TIER_RAW, SYMBOL_TYPE, EQUITY_INIT, ANNUAL_FACTOR,
    RISK_PER_TRADE, DEDUP_HOURS, K_L_SL, H_L, K_S_SL, H_S,
    MARKET_DIR, CONTRACT_SPECS,
)

# ---- 旧数据路径 ----
OLD_TL_PATH = Path("project_data/logs/poc_va_asymmetry_stage4/classifier_v31_timeline.parquet")
OUT_DIR = REPO / "project_data" / "va_legacy_backtest"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CAP = 4.0


def load_events_legacy(tl: pd.DataFrame) -> pd.DataFrame:
    """旧管线：直接用旧 tier 列 + A_TIER_RAW 白名单筛选，不经过 tier_v40 映射。"""
    a = tl[tl["tier"].isin(A_TIER_RAW)].copy()
    a["direction"] = a["tier"].apply(lambda t: "long" if t.startswith("UP") else "short")
    # 旧数据 daily_atr_10_bps 已是 bps 口径
    a["entry_atr_bps"] = a["daily_atr_10_bps"]
    # 去重 8h
    a = a.sort_values(["contract", "event_time"]).reset_index(drop=True)
    prev = a.groupby("contract")["event_time"].shift(1)
    a = a[(prev.isna()) | ((a["event_time"] - prev) > pd.Timedelta(hours=DEDUP_HOURS))]
    return a.reset_index(drop=True)


def main() -> None:
    print("=" * 78)
    print("va-asymmetry · 旧管线全链路复现（v31 timeline + A_TIER 白名单 · Cap=4.0）")
    print("=" * 78)

    print("[1/5] 加载旧 timeline + 构建事件 ...")
    tl_full = pd.read_parquet(OLD_TL_PATH)
    tl_full["event_time"] = pd.to_datetime(tl_full["event_time"])
    active_days = active_day_set(tl_full, "signed_skew_rank_roll")

    events = load_events_legacy(tl_full)
    n_ev = len(events)
    n_long = int((events["direction"] == "long").sum())
    n_short = int((events["direction"] == "short").sum())
    n_symbols = events["contract"].nunique()
    print(f"      旧 B 事件: {n_ev} | 合约: {n_symbols} | 多: {n_long} / 空: {n_short}")

    # 加载基线 B0
    from va_composite_p1_cap import load_events  # noqa: E402
    events_b0 = load_events()
    n_b0 = len(events_b0)
    print(f"      基线 B0 事件: {n_b0} | 合约: {events_b0['contract'].nunique()} | "
          f"多: {(events_b0['direction']=='long').sum()} / 空: {(events_b0['direction']=='short').sum()}")

    print("[2/5] 逐合约 5m 精确模拟 ...")
    all_rows: list[dict] = []
    for contract, g in events.groupby("contract"):
        all_rows.extend(simulate_contract(contract, g))
    raw = pd.DataFrame(all_rows)
    n_sl = int((raw["exit_reason"] == "SL").sum())
    n_time = int((raw["exit_reason"] == "TIME").sum())
    print(f"      模拟交易数: {len(raw)} | SL: {n_sl} TIME: {n_time}")

    # B0 模拟
    all_b0: list[dict] = []
    for contract, g in events_b0.groupby("contract"):
        all_b0.extend(simulate_contract(contract, g))
    raw_b0 = pd.DataFrame(all_b0)

    print(f"[3/5] Cap=4.0 压仓 + 指标 ...")
    # B (old pipeline)
    tB = compress(raw, CAP)
    tB = assign_equity(tB)
    mB = base_metrics(tB, active_days=active_days)
    mB["monthly_win"] = monthly_win_rate(tB)
    mB["ir"] = per_trade_ir(tB)
    mB["nu_implied"], mB["p_nu_pos"] = nu_implied(tB)

    # B0 (baseline, also at Cap=4.0)
    tB0 = compress(raw_b0, CAP)
    tB0 = assign_equity(tB0)
    mB0 = base_metrics(tB0, active_days=active_days)

    print(f"      旧 B (Cap={CAP}): 年化 {mB['ann_ret']*100:.2f}%  夏普 {mB['sharpe']:.2f}  "
          f"MaxDD {mB['max_dd']*100:.2f}%  胜率 {mB.get('ir', 0)*100:.1f}%")
    print(f"      基线 B0 (Cap={CAP}): 年化 {mB0['ann_ret']*100:.2f}%  夏普 {mB0['sharpe']:.2f}  "
          f"MaxDD {mB0['max_dd']*100:.2f}%")

    # OOS split
    print(f"[4/5] OOS 拆分（后50%） ...")
    all_times = pd.to_datetime(pd.concat([events["event_time"], events_b0["event_time"]]))
    oos_cut = all_times.sort_values().iloc[len(all_times) // 2]
    print(f"      OOS 切点: {oos_cut.strftime('%Y-%m-%d')}")

    evB_is = events[pd.to_datetime(events["event_time"]) < oos_cut]
    evB_oos = events[pd.to_datetime(events["event_time"]) >= oos_cut]
    evB0_is = events_b0[pd.to_datetime(events_b0["event_time"]) < oos_cut]
    evB0_oos = events_b0[pd.to_datetime(events_b0["event_time"]) >= oos_cut]

    def sim_and_metrics(ev):
        rows = []
        for c, g in ev.groupby("contract"):
            rows.extend(simulate_contract(c, g))
        raw_ = pd.DataFrame(rows)
        t_ = compress(raw_, CAP)
        t_ = assign_equity(t_)
        return t_, base_metrics(t_, active_days=active_days)

    tB_is, mB_is = sim_and_metrics(evB_is)
    tB_oos, mB_oos = sim_and_metrics(evB_oos)
    tB0_is, mB0_is = sim_and_metrics(evB0_is)
    tB0_oos, mB0_oos = sim_and_metrics(evB0_oos)

    cols = ["策略", "年化(%)", "夏普", "最大回撤(%)", "胜率(%)", "Calmar"]
    rows = [
        ["基线 B0", f"{mB0['ann_ret']*100:.2f}%", f"{mB0['sharpe']:.2f}",
         f"{mB0['max_dd']*100:.2f}%", f"{len(tB0[tB0['pnl_net_bps']>0])/len(tB0)*100:.1f}%",
         f"{mB0['ann_ret']/abs(mB0['max_dd']):.3f}" if mB0['max_dd'] else "N/A"],
        ["旧策略 B", f"{mB['ann_ret']*100:.2f}%", f"{mB['sharpe']:.2f}",
         f"{mB['max_dd']*100:.2f}%", f"{len(tB[tB['pnl_net_bps']>0])/len(tB)*100:.1f}%",
         f"{mB['ann_ret']/abs(mB['max_dd']):.3f}" if mB['max_dd'] else "N/A"],
        ["旧策略 B IS", f"{mB_is['ann_ret']*100:.2f}%", f"{mB_is['sharpe']:.2f}",
         f"{mB_is['max_dd']*100:.2f}%", f"{len(tB_is[tB_is['pnl_net_bps']>0])/len(tB_is)*100:.1f}%",
         f"{mB_is['ann_ret']/abs(mB_is['max_dd']):.3f}" if mB_is['max_dd'] else "N/A"],
        ["旧策略 B OOS", f"{mB_oos['ann_ret']*100:.2f}%", f"{mB_oos['sharpe']:.2f}",
         f"{mB_oos['max_dd']*100:.2f}%", f"{len(tB_oos[tB_oos['pnl_net_bps']>0])/len(tB_oos)*100:.1f}%",
         f"{mB_oos['ann_ret']/abs(mB_oos['max_dd']):.3f}" if mB_oos['max_dd'] else "N/A"],
    ]
    summary_df = pd.DataFrame(rows, columns=cols)
    print(summary_df.to_string(index=False))

    # 配对增量
    print("[5/5] 配对增量 (B − B0) ...")
    from va_composite_p1_cap import paired_delta  # noqa: E402
    d_all = paired_delta(tB0, tB)
    d_is = paired_delta(tB0_is, tB_is)
    d_oos = paired_delta(tB0_oos, tB_oos)
    print(f"      全量 : ΔSh={d_all['dsharpe']:+.2f}  μ_true={d_all['nu_true']*100:+.3f}%  "
          f"P(B>B0)={d_all['p_nu_pos']:.3f}")
    print(f"      in-sample: ΔSh={d_is['dsharpe']:+.2f}  μ_true={d_is['nu_true']*100:+.3f}%  "
          f"P(B>B0)={d_is['p_nu_pos']:.3f}")
    print(f"      OOS(后50%): ΔSh={d_oos['dsharpe']:+.2f}  μ_true={d_oos['nu_true']*100:+.3f}%  "
          f"P(B>B0)={d_oos['p_nu_pos']:.3f}")

    # 写出
    out_cols = ["contract", "symbol", "symbol_type", "entry_bar", "exit_bar", "direction", "tier",
                "entry_price", "exit_price", "exit_reason", "entry_atr_bps", "qty_raw", "qty_actual",
                "pnl_gross_bps", "cost_entry_bps", "cost_exit_bps",
                "pnl_net_bps", "pnl_net_ccy", "equity_before", "equity_after"]
    tB[out_cols].to_parquet(OUT_DIR / "B_legacy.trades.parquet", index=False)
    tB0[out_cols].to_parquet(OUT_DIR / "B0_baseline.trades.parquet", index=False)

    with open(OUT_DIR / "summary.md", "w") as f:
        f.write("# va-asymmetry 旧管线全链路复现\n\n")
        f.write(f"- 数据源: classifier_v31_timeline.parquet\n")
        f.write(f"- 分类器: 旧 13-tier A_TIER_RAW 白名单\n")
        f.write(f"- 事件数: {n_ev} | 合约: {n_symbols} | 多: {n_long} / 空: {n_short}\n")
        f.write(f"- Cap={CAP}\n\n")
        f.write("## 指标\n\n")
        f.write(summary_df.to_markdown(index=False))
        f.write("\n\n## 配对增量\n\n")
        f.write(f"| 范围 | ΔSharpe | μ_true | P(B>B0) |\n")
        f.write(f"|:---:|---:|---:|---:|\n")
        f.write(f"| 全量 | {d_all['dsharpe']:+.2f} | {d_all['nu_true']*100:+.3f}% | {d_all['p_nu_pos']:.3f} |\n")
        f.write(f"| IS | {d_is['dsharpe']:+.2f} | {d_is['nu_true']*100:+.3f}% | {d_is['p_nu_pos']:.3f} |\n")
        f.write(f"| OOS | {d_oos['dsharpe']:+.2f} | {d_oos['nu_true']*100:+.3f}% | {d_oos['p_nu_pos']:.3f} |\n")

    print(f"      写出: {OUT_DIR / 'summary.md'}")
    print("\n终判: 旧管线全链路复现完成")


if __name__ == "__main__":
    main()
