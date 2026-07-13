#!/usr/bin/env python3
"""
甜蜜区 A/B · 趋势方向 × 触发器方向交叉分析
=========================================
问题：VA reaccept 触发是「两侧都能做」还是「只有顺势才能做」？

设计：
  1. 用 trend_ret_10d 确定当下趋势方向：>0 上涨 / <0 下跌 / |x|<threshold 中性
  2. 触发器分 L/S 两侧
  3. 交叉四象限：
     - (uptrend, L)  → 顺势做多（跌后反弹买入 · 顺 uptrend）
     - (downtrend, L) → 逆势做多（抄底 · 逆 downtrend）
     - (downtrend, S) → 顺势做空（涨后回落卖出 · 顺 downtrend）
     - (uptrend, S)  → 逆势做空（做顶 · 逆 uptrend）
  4. 每象限跑 cluster bootstrap B=1000，看 H2/H4/H8 real 的方向净值

对 A 区、B 区分别做，共 8 象限
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workspace"))

import numpy as np
import pandas as pd
from common.contract_specs import CONTRACT_SPECS

DATASET_PATH = Path("project_data/logs/poc_va_asymmetry_stage4/dataset_full.parquet")
OUT_DIR = Path("project_data/ai_tmp")
N_BOOT = 1000
SEED = 20260709
FLAT_COST_ATR = 0.05
HOLD_TAGS = ["H2", "H4", "H8"]

ZONES = {
    "A": {"desc": "sk_mild × tr_stable × atr_hi",
          "skew_lo": 0.10, "skew_hi": 0.20,
          "trend_lo": 0.35, "trend_hi": 0.65, "trend_inside": True,
          "atr_lo": 0.67, "atr_hi": 1.01},
    "B": {"desc": "sk_xsym × tr_unstable × atr_hi",
          "skew_lo": 0.00, "skew_hi": 0.10,
          "trend_lo": 0.35, "trend_hi": 0.65, "trend_inside": False,
          "atr_lo": 0.67, "atr_hi": 1.01},
}


def preprocess(df):
    df = df.copy()
    df["event_time"] = pd.to_datetime(df["event_time"])
    df["event_date"] = pd.to_datetime(df["event_date"]).dt.date
    df = df.sort_values(["contract", "event_time"]).reset_index(drop=True)
    df["abs_skew"] = (df["signed_skew_rank_roll"] - 0.5).abs()
    df["rank20"] = df.groupby("contract")["close_t"].transform(
        lambda s: s.rolling(20, min_periods=10).rank(pct=True)
    )
    df["close_diff"] = df.groupby("contract")["close_t"].diff(1)
    cL = df["rank20"].notna() & df["close_diff"].notna() & (df["rank20"] <= 0.20) & (df["close_diff"] > 0)
    cS = df["rank20"].notna() & df["close_diff"].notna() & (df["rank20"] >= 0.80) & (df["close_diff"] < 0)
    df["trigger_side"] = np.where(cL, "L", np.where(cS, "S", None))
    df["is_trigger"] = df["trigger_side"].notna()

    df["cost_flat_bps"] = df["daily_atr_10_bps"] * FLAT_COST_ATR
    out = np.full(len(df), np.nan)
    for c in df["contract"].unique():
        spec = CONTRACT_SPECS.get_symbol(c)
        if spec is None:
            continue
        m = (df["contract"] == c).values
        p = df.loc[m, "close_t"].values
        size = spec.size
        if hasattr(spec, "total_commission_np"):
            comm = spec.total_commission_np(p, 1)
        else:
            comm = np.array([spec.total_commission(price=float(x), lots=1) for x in p])
        slip = spec.slippage(lots=1)
        out[m] = 2 * (comm + slip) / (p * size) * 10000
    df["cost_real_bps"] = out

    r4 = df["ret_4h"].values
    df["ret_4h_bps"] = r4 * 10000 if np.nanmean(np.abs(r4)) < 0.1 else r4
    df["ret_2h_bps"] = df["ret_4h_bps"] / 2.0

    # 方向 PnL（做多/做空各自的净值）
    for h, rc in zip(HOLD_TAGS, ["ret_2h_bps", "ret_4h_bps", "ret_8h_bps"]):
        # L 侧（做多）
        L = np.where(df["trigger_side"] == "L", df[rc] - df["cost_real_bps"], np.nan)
        # S 侧（做空）
        S = np.where(df["trigger_side"] == "S", -df[rc] - df["cost_real_bps"], np.nan)
        df[f"pnl_{h}_L"] = L
        df[f"pnl_{h}_S"] = S
    return df


def apply_zone_mask(df, zone):
    m = df["abs_skew"].between(zone["skew_lo"], zone["skew_hi"], inclusive="left")
    m &= df["atr_rank_roll"].between(zone["atr_lo"], zone["atr_hi"], inclusive="right")
    trend_in = df["trend_rank_roll"].between(zone["trend_lo"], zone["trend_hi"], inclusive="both")
    m &= trend_in if zone["trend_inside"] else ~trend_in
    return m


def cluster_boot_mean(values, contracts, dates, n_boot, rng):
    """Cluster bootstrap by (contract, date)"""
    df_tmp = pd.DataFrame({"v": values, "c": contracts, "d": dates}).dropna(subset=["v"])
    if len(df_tmp) == 0:
        return None, None, None
    clusters = df_tmp.groupby(["c", "d"]).indices
    keys = list(clusters.keys())
    n = len(keys)
    arr = df_tmp["v"].values
    boot = np.empty(n_boot)
    for b in range(n_boot):
        sampled = rng.choice(n, size=n, replace=True)
        idx = []
        for k in sampled:
            idx.extend(clusters[keys[k]])
        boot[b] = np.nanmean(arr[idx])
    return float(np.nanmean(arr)), float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))


def analyze_zone_direction(df, zone_id, zone, rng):
    print(f"\n{'=' * 78}")
    print(f"甜蜜区 {zone_id}: {zone['desc']}")
    print("=" * 78)
    mask = apply_zone_mask(df, zone)
    sub = df.loc[mask].copy()
    print(f"[filter] n_sub={len(sub)}, "
          f"triggers L={sub['trigger_side'].eq('L').sum()}, "
          f"S={sub['trigger_side'].eq('S').sum()}")

    # 趋势方向：用 trend_ret_10d 的符号
    sub["trend_dir"] = np.where(sub["trend_ret_10d"] > 0, "up",
                                np.where(sub["trend_ret_10d"] < 0, "down", "flat"))
    print(f"[trend_dir] up={sub['trend_dir'].eq('up').sum()}, "
          f"down={sub['trend_dir'].eq('down').sum()}, "
          f"flat={sub['trend_dir'].eq('flat').sum()}")

    # 触发事件的趋势方向分布
    trig_sub = sub[sub["is_trigger"]]
    print(f"\n[触发事件 · 趋势 × 触发器 交叉分布]")
    cross = pd.crosstab(trig_sub["trend_dir"], trig_sub["trigger_side"], margins=True)
    print(cross.to_string())

    # 四象限：L 侧的 up/down，S 侧的 up/down
    quadrants = {
        "顺势L(uptrend×L)":   {"trend_dir": "up",   "side": "L"},
        "逆势L(downtrend×L)": {"trend_dir": "down", "side": "L"},
        "逆势S(uptrend×S)":   {"trend_dir": "up",   "side": "S"},
        "顺势S(downtrend×S)": {"trend_dir": "down", "side": "S"},
    }

    print(f"\n[四象限方向净值 · real 成本 · cluster bootstrap B={N_BOOT}]")
    print(f"{'quadrant':<25s} {'n':>5s} {'contracts':>9s} "
          f"{'H2 mean':>10s} {'H2 CI_lo':>10s} "
          f"{'H4 mean':>10s} {'H4 CI_lo':>10s} "
          f"{'H8 mean':>10s} {'H8 CI_lo':>10s} verdict")

    zone_results = {}
    for qname, cond in quadrants.items():
        q_sub = trig_sub[
            (trig_sub["trend_dir"] == cond["trend_dir"])
            & (trig_sub["trigger_side"] == cond["side"])
        ]
        n = len(q_sub)
        n_contracts = q_sub["contract"].nunique()
        if n < 10:
            print(f"{qname:<25s} {n:>5d} {n_contracts:>9d}  样本不足")
            zone_results[qname] = {"n": n, "insufficient": True}
            continue

        pnl_col = f"pnl_{{h}}_{cond['side']}"
        row = {"n": n, "n_contracts": n_contracts, "insufficient": False}
        row_disp = f"{qname:<25s} {n:>5d} {n_contracts:>9d}"
        for h in HOLD_TAGS:
            col = f"pnl_{h}_{cond['side']}"
            m, lo, hi = cluster_boot_mean(
                q_sub[col].values, q_sub["contract"].values,
                q_sub["event_date"].values, N_BOOT, rng)
            row[f"{h}_mean"] = m
            row[f"{h}_ci_lo"] = lo
            row[f"{h}_ci_hi"] = hi
            if m is not None:
                row_disp += f"  {m:>+9.2f} {lo:>+9.2f}"
            else:
                row_disp += "         -         -"
        # 判决基于 H4 real
        h4_lo = row.get("H4_ci_lo")
        verdict = "✅ 可做" if h4_lo is not None and h4_lo > 0 else "❌ 不可"
        row_disp += f"  {verdict}"
        print(row_disp)
        zone_results[qname] = row

    # 汇总：顺势 vs 逆势
    print(f"\n[顺势 vs 逆势 · H4 real mean 汇总]")
    trend_align = {}
    for qname, r in zone_results.items():
        if r.get("insufficient"):
            continue
        align = "顺势" if "顺势" in qname else "逆势"
        trend_align.setdefault(align, []).append({
            "quadrant": qname, "n": r["n"],
            "H4_mean": r.get("H4_mean"), "H4_ci_lo": r.get("H4_ci_lo"),
        })
    for align, items in trend_align.items():
        total_n = sum(x["n"] for x in items)
        if total_n == 0:
            continue
        weighted_mean = sum((x["H4_mean"] or 0) * x["n"] for x in items) / total_n
        print(f"  {align}: n={total_n}, 加权 H4 mean={weighted_mean:+.2f} bps")
        for x in items:
            print(f"    - {x['quadrant']}: n={x['n']}, H4={x['H4_mean']:+.2f} (CI_lo={x['H4_ci_lo']:+.2f})")

    return zone_results


def main():
    t0 = time.time()
    print("=" * 78)
    print("趋势方向 × 触发器方向 · 甜蜜区 A/B 交叉分析")
    print("=" * 78)
    df = pd.read_parquet(DATASET_PATH)
    df = preprocess(df)

    rng = np.random.RandomState(SEED)
    all_results = {}
    for zone_id, zone in ZONES.items():
        all_results[zone_id] = analyze_zone_direction(df, zone_id, zone, rng)

    # 对比总结
    print(f"\n{'=' * 78}")
    print("A/B 对比 · 顺势 vs 逆势 · H4 real")
    print("=" * 78)
    for zone_id, results in all_results.items():
        print(f"\n甜蜜区 {zone_id}:")
        for qname, r in results.items():
            if r.get("insufficient"):
                print(f"  {qname:<25s} n={r['n']:>4d}  样本不足")
            else:
                verdict = "✅" if r.get("H4_ci_lo", -999) > 0 else "❌"
                print(f"  {qname:<25s} n={r['n']:>4d}  "
                      f"H4 mean={r['H4_mean']:+7.2f}  "
                      f"CI=[{r['H4_ci_lo']:+7.2f}, {r['H4_ci_hi']:+7.2f}]  {verdict}")

    print(f"\n[total] elapsed = {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
