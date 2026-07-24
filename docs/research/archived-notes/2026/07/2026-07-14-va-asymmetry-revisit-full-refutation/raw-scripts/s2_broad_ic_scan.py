"""
文件级元信息：
- 创建背景：s1 特征缓存已完成（events_with_multi_skew.csv, 145 品种全部
  含 4h/8h/24h skew）。s2 是轻量版分析：直接算 Spearman IC + per-symbol
  sign consistency，跳过慢的 cluster bootstrap；先找 IC>0.03 的候选。
- 用途：Broad scan 所有 skew 派生维度（|skew| / 短窗 / Δskew / xs-rank /
  skew×trend / persistence-filtered）的 pooled IC，一次筛出 top-N。
- 注意事项：临时研究脚本，产物在 outputs/skew_wide/。若发现 IC>0.03
  的 top 候选，再单独深挖（跑 cluster bootstrap + walk-forward）。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

CACHE = Path(
    "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/skew_wide/events_with_multi_skew.csv"
)
OUT_DIR = Path(
    "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/skew_wide"
)


def ic(x: np.ndarray, y: np.ndarray) -> tuple[float, int]:
    m = ~(np.isnan(x) | np.isnan(y))
    if m.sum() < 100:
        return float("nan"), int(m.sum())
    r, _ = stats.spearmanr(x[m], y[m])
    return float(r), int(m.sum())


def main() -> None:
    print("Loading cache …", flush=True)
    df = pd.read_csv(CACHE)
    df["event_time"] = pd.to_datetime(df["event_time"])
    df["event_date"] = pd.to_datetime(df["event_date"]).dt.date
    print(f"rows={len(df)}, symbols={df['symbol'].nunique()}, "
          f"contracts={df['contract'].nunique()}")

    HORIZONS = [2, 4, 6, 8, 12]
    # 补齐派生特征
    df["abs_skew"] = df["A3_skew"].abs()
    df["skew_sq"] = df["A3_skew"] ** 2
    df = df.sort_values(["contract", "event_time"]).reset_index(drop=True)
    df["skew_lag1"] = df.groupby("contract")["A3_skew"].shift(1)
    df["skew_lag4"] = df.groupby("contract")["A3_skew"].shift(4)
    df["skew_delta_1h"] = df["A3_skew"] - df["skew_lag1"]
    df["skew_delta_4h"] = df["A3_skew"] - df["skew_lag4"]
    df["persist_1h"] = (np.sign(df["A3_skew"]) == np.sign(df["skew_lag1"])).astype(float)
    df["persist_4h"] = (np.sign(df["A3_skew"]) == np.sign(df["skew_lag4"])).astype(float)
    df["skew_xs_rank"] = df.groupby("event_time")["A3_skew"].transform(
        lambda s: s.rank(pct=True) if len(s) >= 3 else np.nan
    )
    df["skew_x_signtrend"] = df["A3_skew"] * np.sign(df["trend_intra"])
    df["abs_skew_4h"] = df["skew_4h"].abs()
    df["abs_skew_8h"] = df["skew_8h"].abs()
    df["abs_skew_24h"] = df["skew_24h"].abs()
    for h in HORIZONS:
        df[f"abs_ret_{h}h"] = df[f"ret_{h}h"].abs()
    df["future_min_ret"] = df[[f"ret_{h}h" for h in [2, 4, 6, 8, 12]]].min(axis=1)
    df["future_max_ret"] = df[[f"ret_{h}h" for h in [2, 4, 6, 8, 12]]].max(axis=1)
    df["future_range"] = df["future_max_ret"] - df["future_min_ret"]

    # =========================================================================
    # 大扫：各 (feature, target) 组合 pooled IC + per-symbol sign consistency
    # =========================================================================
    FEATURES_SIGNED = [
        "A3_skew", "skew_4h", "skew_8h", "skew_24h",
        "skew_delta_1h", "skew_delta_4h",
        "skew_x_signtrend", "skew_xs_rank",
    ]
    FEATURES_ABS = [
        "abs_skew", "skew_sq", "abs_skew_4h", "abs_skew_8h", "abs_skew_24h",
    ]
    TARGETS_SIGNED = [f"ret_{h}h" for h in HORIZONS]
    TARGETS_MAG = [f"abs_ret_{h}h" for h in HORIZONS] + ["future_range"]
    TARGETS_MIN = ["future_min_ret"]

    def scan(features: list[str], targets: list[str], label: str) -> pd.DataFrame:
        print(f"\n=== [{label}] Pooled IC + per-symbol sign consistency ===")
        rows = []
        for feat in features:
            for tgt in targets:
                r, n = ic(df[feat].to_numpy(), df[tgt].to_numpy())
                # per-symbol IC 分布
                ics_sym = []
                for sym, sub in df.groupby("symbol"):
                    if len(sub) < 100:
                        continue
                    ri, _ = ic(sub[feat].to_numpy(), sub[tgt].to_numpy())
                    if not np.isnan(ri):
                        ics_sym.append(ri)
                ics_sym = np.array(ics_sym)
                same_sign = (
                    int((np.sign(ics_sym) == np.sign(r)).sum())
                    if len(ics_sym) > 0 and not np.isnan(r) else 0
                )
                cons = same_sign / len(ics_sym) if len(ics_sym) > 0 else float("nan")
                rows.append({
                    "feature": feat, "target": tgt, "n": n, "ic": r,
                    "n_symbols": len(ics_sym), "consistency": cons,
                    "sym_ic_mean": float(np.nanmean(ics_sym)) if len(ics_sym) > 0 else float("nan"),
                    "sym_ic_std": float(np.nanstd(ics_sym)) if len(ics_sym) > 0 else float("nan"),
                })
        out = pd.DataFrame(rows).sort_values("ic", key=abs, ascending=False)
        print(out.to_string(index=False))
        return out

    signed_df = scan(FEATURES_SIGNED, TARGETS_SIGNED, "signed feats → signed ret")
    signed_df.to_csv(OUT_DIR / "s2_signed.csv", index=False)

    mag_df = scan(FEATURES_ABS, TARGETS_MAG, "|skew| feats → magnitude / range")
    mag_df.to_csv(OUT_DIR / "s2_magnitude.csv", index=False)

    min_df = scan(FEATURES_ABS, TARGETS_MIN, "|skew| → future_min_ret (drawdown proxy)")
    min_df.to_csv(OUT_DIR / "s2_drawdown.csv", index=False)

    # Persistence-filtered signed skew IC
    print("\n=== Persistence-filtered signed skew IC ===")
    rows = []
    for filt in ["persist_1h", "persist_4h"]:
        sub = df[df[filt] == 1.0]
        for tgt in TARGETS_SIGNED:
            r, n = ic(sub["A3_skew"].to_numpy(), sub[tgt].to_numpy())
            ics_sym = []
            for sym, sub2 in sub.groupby("symbol"):
                if len(sub2) < 50:
                    continue
                ri, _ = ic(sub2["A3_skew"].to_numpy(), sub2[tgt].to_numpy())
                if not np.isnan(ri):
                    ics_sym.append(ri)
            ics_sym = np.array(ics_sym)
            same = (
                int((np.sign(ics_sym) == np.sign(r)).sum())
                if len(ics_sym) > 0 and not np.isnan(r) else 0
            )
            rows.append({
                "filter": filt, "target": tgt, "n": n, "ic": r,
                "n_symbols": len(ics_sym),
                "consistency": same / len(ics_sym) if len(ics_sym) > 0 else float("nan"),
            })
    pers_df = pd.DataFrame(rows).sort_values("ic", key=abs, ascending=False)
    pers_df.to_csv(OUT_DIR / "s2_persistence.csv", index=False)
    print(pers_df.to_string(index=False))

    # 综合 top-30
    print("\n\n=== TOP-30 |IC| across all scans ===")
    all_ = pd.concat([
        signed_df.assign(scan="signed"),
        mag_df.assign(scan="magnitude"),
        min_df.assign(scan="drawdown"),
    ], ignore_index=True)
    top = all_.sort_values("ic", key=abs, ascending=False).head(30)
    print(top[["scan", "feature", "target", "n", "ic", "consistency", "n_symbols"]].to_string(index=False))
    top.to_csv(OUT_DIR / "s2_top30.csv", index=False)

    # 挑 pass 门槛：|IC|>0.03 且 consistency>=0.65
    ok = all_[(all_["ic"].abs() > 0.03) & (all_["consistency"] >= 0.65)]
    print(f"\n>>> Candidates with |IC|>0.03 AND consistency>=0.65: {len(ok)}")
    if not ok.empty:
        print(ok.to_string(index=False))
    ok.to_csv(OUT_DIR / "s2_passing_candidates.csv", index=False)


if __name__ == "__main__":
    main()
