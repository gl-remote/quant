"""
文件级元信息：
- 创建背景：c3 显示 L_seg2 在 test 折过门但 hour=11 单点驱动；本脚本做参数
  敏感度：(a) 放宽/收紧 rank 阈值看信号稳定性、(b) 多折 walk-forward 而非
  单 8:2、(c) 组合 L_seg2 + L_seg3 池、(d) 换 rank 窗口大小复验。
- 用途：判断 L_seg2 alpha 对 tier 边界的敏感性 —— 若小幅调阈值即塌，是过拟合；
  若相邻阈值同向，是真信号。
- 注意事项：临时研究脚本，产物在
  docs/workbench/va-asymmetry-revisit/outputs/c4/。
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "/Users/gaolei/Documents/src/quant/workspace")
sys.path.insert(0, "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/scripts")

from common.contract_specs import CONTRACT_SPECS  # noqa: E402
from h1b_regime_stratified import cluster_bootstrap_mean  # noqa: E402
from c1_causal_tier_scan import (  # noqa: E402
    add_rank, add_future_returns, enrich_intra_features,
)

LONG_PATH = Path(
    "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/h1/h1_long_events.csv"
)

OUT_DIR = Path(
    "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/c4"
)
OUT_DIR.mkdir(parents=True, exist_ok=True)


def one_side_cost_frac(row) -> float:
    spec = CONTRACT_SPECS.get_symbol(row["symbol"])
    if spec is None:
        return np.nan
    price = float(row["close_t"])
    slip = (spec.tick * spec.slip_tick) / price
    try:
        comm_yuan = spec.total_commission(price, 1)
        comm = comm_yuan / (spec.size * price) if spec.size > 0 else 0.0
    except Exception:
        comm = 0.0
    return slip + comm


def prepare_events(rank_win: int) -> pd.DataFrame:
    """Cache-aware version: 若 rank_win 与 c1 相同（240），直接用 c1 output"""
    c1_path = Path(
        "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/c1/c1_events_with_tier.csv"
    )
    if rank_win == 240 and c1_path.exists():
        df = pd.read_csv(c1_path)
        df["event_time"] = pd.to_datetime(df["event_time"])
        df["event_date"] = pd.to_datetime(df["event_date"]).dt.date
        return df

    print(f"[prep] recomputing with rank_win={rank_win} …", flush=True)
    df = pd.read_csv(LONG_PATH)
    df["event_time"] = pd.to_datetime(df["event_time"])
    df["event_date"] = pd.to_datetime(df["event_date"]).dt.date
    df = enrich_intra_features(df)
    df = add_future_returns(df)
    for col in ["A3_skew", "atr_intra", "trend_intra"]:
        df = add_rank(df, col, rank_win)
    df["cost_rt"] = 2.0 * df.apply(one_side_cost_frac, axis=1)
    df["ce_key"] = df["contract"].astype(str) + "|" + df["event_date"].astype(str)
    return df


def label_l2_soft(df: pd.DataFrame, rs_lo: float, rs_hi: float,
                  ra_hi: float, rt_lo: float, rt_hi: float) -> pd.Series:
    """L_seg2 相似规则：skew 高分位 + ATR 低分位 + trend flat。"""
    rs = df["A3_skew_rank"]
    ra = df["atr_intra_rank"]
    rt = df["trend_intra_rank"]
    mask = (
        (rs >= rs_lo) & (rs <= rs_hi)
        & (ra <= ra_hi)
        & (rt >= rt_lo) & (rt <= rt_hi)
    )
    return mask


def main() -> None:
    df = prepare_events(240)
    print(f"Loaded {len(df)} events")

    HORIZONS = ["ret_6h", "ret_8h", "ret_10h", "ret_12h"]

    # =========================================================================
    # [A] Rank threshold sensitivity for L_seg2-like
    # =========================================================================
    print("\n=== [A] Rank threshold sensitivity ===")
    sens_rows = []
    grid = [
        ("baseline_spec", 0.81, 0.91, 0.33, 0.20, 0.75),
        ("skew_wider",    0.75, 0.95, 0.33, 0.20, 0.75),
        ("skew_narrow",   0.85, 0.90, 0.33, 0.20, 0.75),
        ("atr_looser",    0.81, 0.91, 0.50, 0.20, 0.75),
        ("atr_tighter",   0.81, 0.91, 0.20, 0.20, 0.75),
        ("trend_wider",   0.81, 0.91, 0.33, 0.10, 0.85),
        ("trend_narrow",  0.81, 0.91, 0.33, 0.35, 0.65),
        ("skew_low_atr",  0.70, 0.91, 0.33, 0.20, 0.75),  # skew 阈值扩展到 0.70
    ]
    for name, rs_lo, rs_hi, ra_hi, rt_lo, rt_hi in grid:
        mask = label_l2_soft(df, rs_lo, rs_hi, ra_hi, rt_lo, rt_hi)
        sub = df[mask].sort_values("event_time").reset_index(drop=True)
        if len(sub) < 30:
            sens_rows.append({"variant": name, "n": len(sub)})
            continue
        split = int(len(sub) * 0.8)
        for split_name, part in [("all", sub), ("train", sub.iloc[:split]),
                                 ("test", sub.iloc[split:])]:
            for h in HORIZONS:
                y = part[h].to_numpy() - part["cost_rt"].to_numpy()
                mu, lo, hi, p, n = cluster_bootstrap_mean(y, part["ce_key"].to_numpy())
                sens_rows.append({
                    "variant": name, "split": split_name, "horizon": h,
                    "n": n, "mean_net": mu, "ci_lo": lo, "ci_hi": hi, "p_two": p,
                })
    sens_df = pd.DataFrame(sens_rows)
    sens_df.to_csv(OUT_DIR / "c4_sensitivity.csv", index=False)
    # Pivot only 10h all-split
    pv = sens_df[(sens_df["horizon"] == "ret_10h")].pivot(
        index="variant", columns="split", values="mean_net")
    print(pv.round(6).to_string())
    print("\np_two (10h):")
    pv_p = sens_df[(sens_df["horizon"] == "ret_10h")].pivot(
        index="variant", columns="split", values="p_two")
    print(pv_p.round(3).to_string())

    # =========================================================================
    # [B] 3-fold walk-forward
    # =========================================================================
    print("\n=== [B] 3-fold walk-forward baseline_spec · 10h net ===")
    l2 = df[label_l2_soft(df, 0.81, 0.91, 0.33, 0.20, 0.75)].sort_values(
        "event_time").reset_index(drop=True)
    n_l2 = len(l2)
    print(f"L_seg2 events: {n_l2}")
    fold_rows = []
    for i, (tr_frac_lo, tr_frac_hi, te_frac_lo, te_frac_hi) in enumerate([
        (0.0, 0.5, 0.5, 0.7),
        (0.0, 0.7, 0.7, 0.85),
        (0.0, 0.85, 0.85, 1.0),
    ]):
        tr = l2.iloc[int(tr_frac_lo * n_l2):int(tr_frac_hi * n_l2)]
        te = l2.iloc[int(te_frac_lo * n_l2):int(te_frac_hi * n_l2)]
        for name, sub in [("train", tr), ("test", te)]:
            for h in HORIZONS:
                y = sub[h].to_numpy() - sub["cost_rt"].to_numpy()
                mu, lo, hi, p, n = cluster_bootstrap_mean(y, sub["ce_key"].to_numpy())
                fold_rows.append({
                    "fold": i, "split": name, "horizon": h,
                    "n": n, "mean_net": mu, "ci_lo": lo, "ci_hi": hi, "p_two": p,
                })
    fold_df = pd.DataFrame(fold_rows)
    fold_df.to_csv(OUT_DIR / "c4_folds.csv", index=False)
    print(fold_df.to_string(index=False))

    # =========================================================================
    # [C] L_seg2 + L_seg3 池 · walk-forward
    # =========================================================================
    print("\n=== [C] L_seg2 + L_seg3 池 · walk-forward · 10h net ===")
    tier_pool = df[df["tier"].isin(["L_seg2_low_flat", "L_seg3_lowmid_up"])].sort_values(
        "event_time").reset_index(drop=True)
    split = int(len(tier_pool) * 0.8)
    for name, sub in [("train", tier_pool.iloc[:split]),
                      ("test", tier_pool.iloc[split:])]:
        for h in HORIZONS:
            y = sub[h].to_numpy() - sub["cost_rt"].to_numpy()
            mu, lo, hi, p, n = cluster_bootstrap_mean(y, sub["ce_key"].to_numpy())
            print(f"  {name} {h}: n={n}, net={mu:.6f} CI=[{lo:.6f},{hi:.6f}] p={p:.3f}")

    # =========================================================================
    # [D] 更大 rank window (360) 复验
    # =========================================================================
    print("\n=== [D] rank_win=360 复验 L_seg2 · 10h net ===")
    df360 = prepare_events(360)
    l2_360 = df360[label_l2_soft(df360, 0.81, 0.91, 0.33, 0.20, 0.75)].sort_values(
        "event_time").reset_index(drop=True)
    print(f"L_seg2 events (rank_win=360): {len(l2_360)}")
    if len(l2_360) >= 50:
        split = int(len(l2_360) * 0.8)
        for name, sub in [("all", l2_360),
                          ("train", l2_360.iloc[:split]),
                          ("test", l2_360.iloc[split:])]:
            for h in HORIZONS:
                y = sub[h].to_numpy() - sub["cost_rt"].to_numpy()
                mu, lo, hi, p, n = cluster_bootstrap_mean(y, sub["ce_key"].to_numpy())
                print(f"  {name} {h}: n={n}, net={mu:.6f} "
                      f"CI=[{lo:.6f},{hi:.6f}] p={p:.3f}")

    print(f"\nAll outputs in: {OUT_DIR}")


if __name__ == "__main__":
    main()
