#!/usr/bin/env python3
"""
文件级元信息：
- 创建背景：初次对比脚本匹配算法基于入场时间±10min，研究侧整点 vs 工程侧5m close
  天然错位导致仅8笔匹配，不足以定位差距；需用 (合约+方向+tier+同日+价格相近) 组合匹配。
- 用途：加载 compare_research_vs_engineering.py 的落盘 parquet，修复匹配 + 补充研究侧成本
  归因，输出增强版分层对比报告。
- 注意事项：不重跑研究侧管线，只读 docs/workbench/.../compare-r-e/*.parquet。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "workspace"))
OUT_DIR = REPO / "docs/workbench/va-asymmetry-composite/outputs/compare-r-e"
ENG_DB = REPO / "project_data/database/backtest/quant.db"
RUN_ID = 15
EQUITY_INIT = 1_000_000.0
ANNUAL_FACTOR = 252


def load() -> dict:
    return {
        "r_trades": pd.read_parquet(OUT_DIR / "research_trades.parquet"),
        "r_ev": pd.read_parquet(OUT_DIR / "research_events.parquet"),
        "e_pairs": pd.read_parquet(OUT_DIR / "engine_paired_trades.parquet"),
        "e_bt": pd.read_parquet(OUT_DIR / "engine_backtests.parquet"),
    }


def research_costs_and_net(r_trades: pd.DataFrame) -> pd.DataFrame:
    """把研究侧 cost_entry_bps/cost_exit_bps 换算成 ccy，并给出总成本字段。"""
    t = r_trades.copy()
    notional = t["qty_raw"] * t["entry_price"]
    # 从 common.contract_specs 拿 size（qty_raw 单位：张 → entry notional ccy = qty_raw * price * size）
    # reproduce 脚本里 qty_raw 的计算：notional_frac * EQUITY_INIT / (price * size)
    # 所以 notional_frac * EQUITY_INIT = qty_raw * price * size，手续费 bps 按 (qty*price*size) 算：
    notional_ccy = t["_notional_frac"] * EQUITY_INIT
    t["commission_est_ccy"] = (t["cost_entry_bps"] + t["cost_exit_bps"]) / 10000.0 * notional_ccy
    # 研究侧没有单独的滑点模型，但 bps 成本 = commission + slippage 合计（cost_oneway_bps = spec.total_commission + slippage）
    t["net_after_cost_ccy"] = t["pnl_net_ccy"]
    t["gross_pnl_ccy"] = t["pnl_gross_bps"] / 10000.0 * notional_ccy
    return t


def compute_metrics_daily(t: pd.DataFrame, pnl_col: str, active_days=None) -> dict:
    t2 = t.copy()
    if "_exit_date" in t2.columns:
        t2["day"] = t2["_exit_date"]
    else:
        t2["day"] = pd.to_datetime(t2["exit_bar"]).dt.date
    dp = t2.groupby("day")[pnl_col].sum()
    ret = dp / EQUITY_INIT
    if len(ret) == 0:
        return {"n": 0, "ann": 0.0, "sharpe": 0.0, "maxdd": 0.0, "win": 0.0,
                "total_pnl": 0.0, "total": 0}
    if active_days:
        idx = sorted(active_days)
        ret = ret.reindex(idx, fill_value=0.0)
    ann = float(ret.mean() * ANNUAL_FACTOR)
    std = float(ret.std() * np.sqrt(ANNUAL_FACTOR))
    sharpe = ann / std if std > 0 else 0.0
    cum = ret.cumsum()
    maxdd = float((cum - cum.cummax()).min())
    wr = float((t2[pnl_col] > 0).mean()) if len(t2) else 0.0
    return {"n": int(len(t2)), "ann": ann, "sharpe": sharpe, "maxdd": maxdd,
            "win": wr, "total_pnl": float(t2[pnl_col].sum()),
            "total_cost": float(t.get("commission_est_ccy", pd.Series(dtype=float)).sum())
                           if "commission_est_ccy" in t.columns else 0.0}


def robust_match(r: pd.DataFrame, e: pd.DataFrame) -> pd.DataFrame:
    """
    组合匹配键：contract, direction, tier, entry_date(同日), entry_price(±0.3%)。
    保留 (contract, direction, tier, entry_date, 最接近价格) 的贪心匹配。
    """
    rs = r.sort_values("entry_bar").reset_index(drop=True).copy()
    es = e.sort_values("entry_bar").reset_index(drop=True).copy()
    rs["_r_idx"] = rs.index
    es["_e_idx"] = es.index
    if "_entry_date" not in rs.columns:
        rs["_entry_date"] = pd.to_datetime(rs["entry_bar"]).dt.date
    if "_entry_date" not in es.columns:
        es["_entry_date"] = pd.to_datetime(es["entry_bar"]).dt.date
    used_e: set[int] = set()
    matches = []
    PRICE_REL_TOL = 0.003  # 0.3%
    for _, rr in rs.iterrows():
        cands = es[
            (es["contract"] == rr["contract"]) &
            (es["direction"] == rr["direction"]) &
            (es["tier"] == rr["tier"]) &
            (es["_entry_date"] == rr["_entry_date"]) &
            (~es["_e_idx"].isin(used_e))
        ].copy()
        if cands.empty:
            # 放宽 tier，同日同合约同方向 + 价格相近（考虑工程侧 tier 可能命名略不同，实际应该一致，但做兜底）
            cands = es[
                (es["contract"] == rr["contract"]) &
                (es["direction"] == rr["direction"]) &
                (es["_entry_date"] == rr["_entry_date"]) &
                (~es["_e_idx"].isin(used_e))
            ].copy()
        if cands.empty:
            matches.append({"r_idx": int(rr["_r_idx"]), "e_idx": None, "match_type": "research_only"})
            continue
        with np.errstate(divide="ignore", invalid="ignore"):
            cands["price_reldiff"] = np.where(
                rr["entry_price"] != 0,
                (cands["entry_price"] - rr["entry_price"]).abs() / rr["entry_price"],
                np.nan,
            )
        cands = cands[cands["price_reldiff"] <= PRICE_REL_TOL].sort_values(["price_reldiff", "entry_bar"])
        if cands.empty:
            matches.append({"r_idx": int(rr["_r_idx"]), "e_idx": None, "match_type": "research_only"})
            continue
        best = cands.iloc[0]
        used_e.add(int(best["_e_idx"]))
        matches.append({
            "r_idx": int(rr["_r_idx"]), "e_idx": int(best["_e_idx"]),
            "entry_dt_diff_sec": int(abs((pd.Timestamp(best["entry_bar"]) -
                                         pd.Timestamp(rr["entry_bar"])).total_seconds())),
            "entry_price_reldiff": float(best["price_reldiff"]),
            "match_type": "matched",
        })
    for ei in es[~es["_e_idx"].isin(used_e)]["_e_idx"]:
        matches.append({"r_idx": None, "e_idx": int(ei), "match_type": "engine_only"})
    return pd.DataFrame(matches)


def block(title: str) -> None:
    print()
    print("=" * 100)
    print(f"  {title}")
    print("=" * 100)


def main() -> None:
    data = load()
    r_trades_raw = data["r_trades"]
    e_pairs = data["e_pairs"]
    e_bt = data["e_bt"]
    r_ev = data["r_ev"]
    # 研究侧 active_day_set
    import sqlite3
    from common.symbol_utils import extract_contract_prefix
    # active days：从 r_ev 里推（和主脚本一致）
    days: set = set()
    for _, g in r_ev.groupby("contract"):
        for d in g["event_date"]:
            ts = pd.Timestamp(d)
            if ts.weekday() < 5:
                days.add(ts.date())
    active_days = sorted(days)

    r_trades = research_costs_and_net(r_trades_raw)
    m = robust_match(r_trades, e_pairs)
    rs = r_trades.add_prefix("r_")
    es = e_pairs.add_prefix("e_")
    detail = m.merge(rs, left_on="r_idx", right_index=True, how="left") \
             .merge(es, left_on="e_idx", right_index=True, how="left")

    # --- L0：匹配统计 ---
    block("L0 · 修复后匹配统计（键: 合约+方向+tier+同日+价格±0.3%）")
    vc = detail["match_type"].value_counts()
    for k, v in vc.items():
        print(f"  {k:<20}{v:>8,}")

    # --- L1：分层成本 & 信号层缺失归因 ---
    block("L1 · 三层金字塔对比（信号→仓位→资金）")
    r_metric = compute_metrics_daily(r_trades, "pnl_net_ccy", active_days)
    e_metric = compute_metrics_daily(e_pairs, "net_pnl_ccy", active_days)
    # 工程侧 BT 级汇总更准：
    bt_total_net = float(e_bt["total_net_pnl"].sum())
    bt_total_comm = float(e_bt["total_commission"].sum())
    bt_total_slip = float(e_bt["total_slippage"].sum())
    print(f"  {'层':<20}{'研究侧 (R)':>24}{'工程侧 (E)':>24}{'E-R 差':>24}")
    print("  " + "-" * 92)
    def row(name, rv, ev, fmt_r=None, fmt_e=None, show_diff=True):
        fr = fmt_r or (lambda x: f"{x:>24,.2f}")
        fe = fmt_e or fr
        if ev is None or rv is None or not show_diff:
            dstr = f"{'—':>24}"
        else:
            try:
                dv = float(ev) - float(rv)
                dstr = f"{dv:>+24,.2f}"
            except Exception:
                dstr = f"{'—':>24}"
        rv_str = fr(rv) if rv is not None else f"{'—':>24}"
        ev_str = fe(ev) if ev is not None else f"{'—':>24}"
        print(f"  {name:<20}{rv_str}{ev_str}{dstr}")

    row("分类事件数",            len(r_ev),          None,
        fmt_r=lambda x: f"{int(x):>24,}",
        fmt_e=lambda _: f"{'—':>24}")
    row("入场信号数(open)",       r_metric["n"],      int(e_pairs.shape[0]),
        fmt_r=lambda x: f"{int(x):>24,}",
        fmt_e=lambda x: f"{int(x):>24,}")
    row("信号覆盖率 R=100%",      1.0,                e_pairs.shape[0] / max(r_metric["n"],1),
        fmt_r=lambda x: f"{x*100:>23.1f}%",
        fmt_e=lambda x: f"{x*100:>23.1f}%")
    row("平均单笔毛盈亏(¥)",      float(r_trades["gross_pnl_ccy"].mean()),
                                float(e_pairs["gross_pnl_ccy"].mean()),
        fmt_r=lambda x: f"{x:>24,.2f}",
        fmt_e=lambda x: f"{x:>24,.2f}")
    # 成本
    r_cost_total = float(r_trades["commission_est_ccy"].sum())
    e_cost_total = bt_total_comm + bt_total_slip
    row("总成本(¥)",             r_cost_total,       e_cost_total)
    row("  其中: commission 估",  float(r_trades["commission_est_ccy"].sum()), bt_total_comm)
    row("  其中: slippage",      0.0,                bt_total_slip)
    # 盈亏
    row("净盈亏(¥) · 交易级",    r_metric["total_pnl"], float(e_pairs["net_pnl_ccy"].sum()))
    row("净盈亏(¥) · BT级(准)",  r_metric["total_pnl"], bt_total_net)
    # 指标
    def pct(x): return f"{x*100:>23.2f}%"
    def num(x): return f"{x:>24.2f}"
    row("年化收益",              r_metric["ann"],   e_metric["ann"], fmt_r=pct, fmt_e=pct)
    row("夏普",                  r_metric["sharpe"],e_metric["sharpe"], fmt_r=num, fmt_e=num)
    row("MaxDD",                 r_metric["maxdd"], e_metric["maxdd"], fmt_r=pct, fmt_e=pct)
    row("胜率",                  r_metric["win"],   e_metric["win"],   fmt_r=pct, fmt_e=pct)

    # --- L2：信号层缺失根因拆解（Research-only 的 Tier × 方向 × 价格差分布） ---
    block("L2 · 信号覆盖率拆解（R 有 E 无 的 548 笔，按 Tier × 方向）")
    ro = detail[detail["match_type"] == "research_only"].copy()
    grp = ro.groupby(["r_direction", "r_tier"]).size().reset_index(name="cnt")
    grp = grp.sort_values(["r_direction", "cnt"], ascending=[True, False])
    print(f"  {'Dir':<4}{'Tier':<30}{'R-only笔数':>12}{'占缺失%':>12}")
    print("  " + "-" * 60)
    miss_total = int(grp["cnt"].sum()) or 1
    dmap = {1.0: "L", -1.0: "S"}
    for _, r in grp.iterrows():
        pct1 = int(r["cnt"]) / miss_total * 100
        print(f"  {dmap.get(r['r_direction'],'?'):<4}"
              f"{str(r['r_tier']):<30}{int(r['cnt']):>12,}{pct1:>11.1f}%")

    # --- L3：Engine-only 额外信号 ---
    block("L3 · 工程侧额外信号（E 有 R 无）")
    eo = detail[detail["match_type"] == "engine_only"].copy()
    if len(eo):
        ge = eo.groupby(["e_direction", "e_tier"]).size().reset_index(name="cnt")
        ge = ge.sort_values(["e_direction", "cnt"], ascending=[True, False])
        eo_total = int(ge["cnt"].sum()) or 1
        print(f"  {'Dir':<4}{'Tier':<30}{'E-only笔数':>12}{'占额外%':>12}")
        print("  " + "-" * 60)
        for _, r in ge.iterrows():
            pct1 = int(r["cnt"]) / eo_total * 100
            print(f"  {dmap.get(r['e_direction'],'?'):<4}"
                  f"{str(r['e_tier']):<30}{int(r['cnt']):>12,}{pct1:>11.1f}%")

    # --- L4：匹配对（共有交易）逐笔差异统计 ---
    block("L4 · 共有交易匹配对统计（一致信号）")
    matched = detail[detail["match_type"] == "matched"].copy()
    print(f"  共有匹配 N = {len(matched):,} / R 980 = {len(matched)/980*100:.1f}%")
    if len(matched):
        dt = matched["entry_dt_diff_sec"].dropna().astype(float)
        pr = matched["entry_price_reldiff"].dropna().astype(float)
        r_pnl_sum = float(matched["r_pnl_net_ccy"].sum())
        # 工程侧：优先信 net_pnl_ccy（配对级），但用 contract_target_net_pnl / N_per_contract 比例会更好
        e_pnl_sum = float(matched["e_net_pnl_ccy"].sum())
        print(f"  入场时间差(s)  median={dt.median():>7.0f}  mean={dt.mean():>7.0f}  max={dt.max():>7.0f}")
        print(f"  入场价相对差(‰) median={pr.median()*1000:>7.3f}  mean={pr.mean()*1000:>7.3f}  max={pr.max()*1000:>7.3f}")
        print(f"  R 共有交易净盈亏合计(¥) = {r_pnl_sum:>14,.2f}")
        print(f"  E 共有交易净盈亏合计(¥) = {e_pnl_sum:>14,.2f}   (配对级)")
        # exit_reason 一致率
        same = (matched["r_exit_reason"] == matched["e_exit_reason"]).sum()
        print(f"  exit_reason 一致率 = {same}/{len(matched)} = {same/len(matched)*100:.1f}%")
        # 方向一致率（都是同方向匹配，应为 100%）
        dir_same = (matched["r_direction"] == matched["e_direction"]).sum()
        print(f"  direction  一致率 = {dir_same}/{len(matched)} = {dir_same/len(matched)*100:.1f}%")

    # --- L5：把"净盈亏 Δ 2,776,341"拆成可解释的三项 ---
    block("L5 · 净盈亏差归因分解（R 2,634,024 - E(-142,318) → |Δ|~2.78M）")
    r_net = r_metric["total_pnl"]
    e_net = bt_total_net
    delta = e_net - r_net
    # 项 1：信号覆盖率差异带来的"毛盈亏缺口"
    # 假设：E 侧"共有交易"的毛盈亏 / 共有笔数 = 每笔 E 平均表现；
    # 则 E 侧如果能覆盖全部 R 的 980 笔，其期望毛盈亏 ≈ R 的 gross。
    # 但更严谨的分解公式：
    #   E_net - R_net
    #     = (E_net - E_gross*(成本占比)) 不好拆。
    # 简化可解释三项：
    #   a) 数量因子：Δ笔数 × R平均单笔净盈亏
    shared = int((detail["match_type"]=="matched").sum())
    r_only = int((detail["match_type"]=="research_only").sum())
    e_only = int((detail["match_type"]=="engine_only").sum())
    r_avg = r_net / len(r_trades) if len(r_trades) else 0
    a = (shared - len(r_trades)) * r_avg
    # b) 共有匹配对的盈亏差（信号相同但执行/成本/时间退出/止损 导致）
    shared_r_pnl = float(matched["r_pnl_net_ccy"].sum()) if len(matched) else 0
    shared_e_pnl = float(matched["e_net_pnl_ccy"].sum()) if len(matched) else 0
    b = shared_e_pnl - shared_r_pnl
    # c) 残差（工程侧额外信号 + 近似误差）
    c = delta - a - b
    print(f"  参考分解（近似，用于方向归因）：")
    print(f"    总 Δ = E_net - R_net                         = {delta:>14,.2f}  ¥")
    print(f"    a) 覆盖率缺口 = {shared-len(r_trades)} 笔 × R均值 {r_avg:,.1f}¥/笔 = {a:>14,.2f}  ¥")
    print(f"    b) 共有交易单笔盈亏差（执行/成本/退出）         = {b:>14,.2f}  ¥")
    print(f"       其中：共有笔 R 净盈亏 = {shared_r_pnl:,.2f}，E 净盈亏配对 = {shared_e_pnl:,.2f}")
    print(f"    c) 残差(工程额外信号 + 近似误差)               = {c:>14,.2f}  ¥")
    print()
    print(f"  更直接的成本归因：")
    print(f"    R 估计总成本(commission+slippage 合并bps) = {r_cost_total:>14,.2f}  ¥")
    print(f"    E 实际总成本(commission+slippage 分开)    = {e_cost_total:>14,.2f}  ¥")
    print(f"      其中 commission = {bt_total_comm:>14,.2f}  ¥")
    print(f"      其中 slippage   = {bt_total_slip:>14,.2f}  ¥")
    if len(r_trades):
        print(f"    单笔成本 R = {r_cost_total/len(r_trades):>10,.2f} ¥/笔 · E = {e_cost_total/max(len(e_pairs),1):>10,.2f} ¥/笔")

    # 保存增强匹配 detail
    detail.to_parquet(OUT_DIR / "matched_pair_detail_v2.parquet", index=False)
    summary2 = {
        "match_v2_counts": vc.to_dict(),
        "metrics_research": r_metric,
        "metrics_engine_pairs": e_metric,
        "engine_bt_agg": {
            "total_net_pnl": bt_total_net,
            "total_commission": bt_total_comm,
            "total_slippage": bt_total_slip,
        },
        "attribution": {
            "delta_net": delta,
            "coverage_gap": a,
            "shared_per_trade_gap": b,
            "residual_plus_extra": c,
            "r_cost_total": r_cost_total,
            "e_cost_total": e_cost_total,
        },
    }
    (OUT_DIR / "summary_v2.json").write_text(json.dumps(summary2, indent=2, default=str), encoding="utf-8")
    print(f"\n✓ 增强版报告已保存: matched_pair_detail_v2.parquet · summary_v2.json @ {OUT_DIR}")


if __name__ == "__main__":
    main()
