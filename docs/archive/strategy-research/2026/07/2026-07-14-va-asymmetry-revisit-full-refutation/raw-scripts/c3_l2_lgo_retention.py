"""
文件级元信息：
- 创建背景：c2 发现 L_seg2_low_flat walk-forward test 通过（10h/12h net p<0.05 CI 排 0）
  但 per-symbol IR 函数因 min_periods=30 全 NaN 未测品种保留率。本脚本修 bug
  + 补做：品种保留率、LGO 品种留 1 组、hour × horizon 交叉稳健、L_seg2 vs
  H-1 baseline 净 alpha 对比。
- 用途：判定 L_seg2 是否真 alpha（品种保留率 ≥60% + LGO 4/5 通过为过门）。
- 注意事项：临时研究脚本，产物在
  docs/workbench/va-asymmetry-revisit/outputs/c3/。
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/scripts")
from h1b_regime_stratified import cluster_bootstrap_mean  # noqa: E402

OUT_DIR = Path(
    "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/c3"
)
OUT_DIR.mkdir(parents=True, exist_ok=True)

EVENTS_PATH = Path(
    "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/c1/c1_events_with_tier.csv"
)

SECTOR_MAP: dict[str, str] = {
    # 由 h1 pool 推断
    "SHFE.rb": "black", "DCE.i": "black", "SHFE.hc": "black",
    "SHFE.cu": "metals", "SHFE.al": "metals", "SHFE.ag": "metals",
    "INE.sc": "energy", "CZCE.TA": "chem",
    "DCE.m": "agri", "DCE.p": "agri", "DCE.y": "agri", "DCE.c": "agri",
    "CZCE.SR": "agri", "CZCE.CF": "agri", "CZCE.RM": "agri",
}


def get_sector(symbol: str) -> str:
    for prefix, sec in SECTOR_MAP.items():
        if symbol.startswith(prefix):
            return sec
    return "other"


def load_events() -> pd.DataFrame:
    df = pd.read_csv(EVENTS_PATH)
    df["event_time"] = pd.to_datetime(df["event_time"])
    df["event_date"] = pd.to_datetime(df["event_date"]).dt.date
    df["hour"] = df["event_time"].dt.hour
    df["sector"] = df["symbol"].apply(get_sector)
    return df


def main() -> None:
    df = load_events()
    l2 = df[df["tier"] == "L_seg2_low_flat"].sort_values("event_time").reset_index(drop=True)
    print(f"L_seg2 total: {len(l2)}, sectors: {l2['sector'].value_counts().to_dict()}")

    HORIZONS = ["ret_6h", "ret_8h", "ret_10h", "ret_12h"]

    # =========================================================================
    # [A] Per-symbol net mean (no min_periods bug this time)
    # =========================================================================
    print("\n=== [A] Per-symbol net mean (all L_seg2 events) ===")
    rows = []
    for sym, sub in l2.groupby("symbol"):
        for h in HORIZONS:
            y = sub[h].to_numpy() - sub["cost_rt"].to_numpy()
            mu = float(np.nanmean(y))
            hit = float(np.nanmean(y > 0))
            rows.append({
                "symbol": sym, "sector": sub["sector"].iloc[0],
                "horizon": h, "n": len(sub),
                "mean_net": mu, "hit_rate": hit,
            })
    sym_df = pd.DataFrame(rows)
    sym_df.to_csv(OUT_DIR / "c3_symbol_net.csv", index=False)
    for h in HORIZONS:
        subh = sym_df[sym_df["horizon"] == h].dropna(subset=["mean_net"])
        pos = (subh["mean_net"] > 0).sum()
        tot = len(subh)
        med = float(np.nanmedian(subh["mean_net"]))
        print(f"  {h}: positive syms {pos}/{tot} = {pos/max(tot,1):.1%}, "
              f"median net={med:.6f}")

    # =========================================================================
    # [B] Sector retention
    # =========================================================================
    print("\n=== [B] Sector retention (mean net) ===")
    sec_rows = []
    for sec, sub in l2.groupby("sector"):
        for h in HORIZONS:
            y = sub[h].to_numpy() - sub["cost_rt"].to_numpy()
            mu, lo, hi, p, n = cluster_bootstrap_mean(y, sub["ce_key"].to_numpy())
            sec_rows.append({
                "sector": sec, "horizon": h, "n": n,
                "mean_net": mu, "ci_lo": lo, "ci_hi": hi, "p_two": p,
            })
    sec_df = pd.DataFrame(sec_rows)
    sec_df.to_csv(OUT_DIR / "c3_sector.csv", index=False)
    print(sec_df.to_string(index=False))

    # =========================================================================
    # [C] Leave-Group-Out (LGO) by sector · 10h net
    # =========================================================================
    print("\n=== [C] LGO by sector · 10h net (drop 1 sector, test on rest) ===")
    lgo_rows = []
    sectors = sorted(l2["sector"].unique())
    for drop_sec in sectors:
        sub = l2[l2["sector"] != drop_sec]
        for h in ["ret_8h", "ret_10h"]:
            y = sub[h].to_numpy() - sub["cost_rt"].to_numpy()
            mu, lo, hi, p, n = cluster_bootstrap_mean(y, sub["ce_key"].to_numpy())
            lgo_rows.append({
                "drop_sector": drop_sec, "horizon": h,
                "n": n, "mean_net": mu, "ci_lo": lo, "ci_hi": hi, "p_two": p,
            })
    lgo_df = pd.DataFrame(lgo_rows)
    lgo_df.to_csv(OUT_DIR / "c3_lgo.csv", index=False)
    print(lgo_df.to_string(index=False))
    pass_10h = ((lgo_df["horizon"] == "ret_10h") & (lgo_df["ci_lo"] > 0) & (lgo_df["p_two"] < 0.05)).sum()
    total_10h = (lgo_df["horizon"] == "ret_10h").sum()
    print(f"\nLGO 10h pass: {pass_10h}/{total_10h}")

    # =========================================================================
    # [D] Hour × horizon 交叉稳健
    # =========================================================================
    print("\n=== [D] Hour × horizon 8h/10h net ===")
    hh_rows = []
    for hour, sub in l2.groupby("hour"):
        if len(sub) < 15:
            continue
        for h in ["ret_6h", "ret_8h", "ret_10h", "ret_12h"]:
            y = sub[h].to_numpy() - sub["cost_rt"].to_numpy()
            mu, lo, hi, p, n = cluster_bootstrap_mean(y, sub["ce_key"].to_numpy())
            hh_rows.append({
                "hour": int(hour), "horizon": h, "n": n,
                "mean_net": mu, "ci_lo": lo, "ci_hi": hi, "p_two": p,
            })
    hh_df = pd.DataFrame(hh_rows)
    hh_df.to_csv(OUT_DIR / "c3_hour_horizon.csv", index=False)
    print(hh_df.to_string(index=False))

    # =========================================================================
    # [E] Drop-hour-11 稳健：把 11 点全删掉，看整体是否还通过
    # =========================================================================
    print("\n=== [E] Drop hour=11 · walk-forward · 10h net ===")
    l2_no11 = l2[l2["hour"] != 11].sort_values("event_time").reset_index(drop=True)
    print(f"After drop 11: {len(l2_no11)} events")
    split = int(len(l2_no11) * 0.8)
    for name, sub in [("train", l2_no11.iloc[:split]), ("test", l2_no11.iloc[split:])]:
        for h in ["ret_8h", "ret_10h", "ret_12h"]:
            y = sub[h].to_numpy() - sub["cost_rt"].to_numpy()
            mu, lo, hi, p, n = cluster_bootstrap_mean(y, sub["ce_key"].to_numpy())
            print(f"  {name} {h}: n={n}, net={mu:.6f} CI=[{lo:.6f},{hi:.6f}] p={p:.3f}")

    # =========================================================================
    # [F] 与"随机事件"对照：把 L_seg2 tier 时刻替换为随机同数量的 tier=none
    #     事件，跑相同 walk-forward，看是否也能通过——本质是"随机对照"
    # =========================================================================
    print("\n=== [F] Random baseline · 相同数量 tier=none 事件 · 10h net ===")
    none_df = df[df["tier"] == "none"].copy()
    rng = np.random.default_rng(20260714)
    baseline_rows = []
    for seed_run in range(5):
        pick_idx = rng.choice(len(none_df), size=len(l2), replace=False)
        rand_sub = none_df.iloc[pick_idx].sort_values("event_time").reset_index(drop=True)
        split_r = int(len(rand_sub) * 0.8)
        for name, sub in [("train", rand_sub.iloc[:split_r]),
                          ("test", rand_sub.iloc[split_r:])]:
            for h in ["ret_10h"]:
                y = sub[h].to_numpy() - sub["cost_rt"].to_numpy()
                mu, lo, hi, p, n = cluster_bootstrap_mean(y, sub["ce_key"].to_numpy())
                baseline_rows.append({
                    "seed_run": seed_run, "split": name, "horizon": h,
                    "n": n, "mean_net": mu, "ci_lo": lo, "ci_hi": hi, "p_two": p,
                })
    bl_df = pd.DataFrame(baseline_rows)
    bl_df.to_csv(OUT_DIR / "c3_random_baseline.csv", index=False)
    print(bl_df.to_string(index=False))
    passing = ((bl_df["ci_lo"] > 0) & (bl_df["p_two"] < 0.05)).sum()
    print(f"Random baseline pass rate: {passing}/{len(bl_df)} = {passing/len(bl_df):.1%}")

    print(f"\nAll outputs in: {OUT_DIR}")


if __name__ == "__main__":
    main()
