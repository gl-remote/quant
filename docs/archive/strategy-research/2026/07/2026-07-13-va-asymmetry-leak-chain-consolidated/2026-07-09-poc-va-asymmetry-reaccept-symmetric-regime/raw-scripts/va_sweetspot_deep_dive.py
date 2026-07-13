#!/usr/bin/env python3
"""
甜蜜区 A/B 深挖验证
===================
甜蜜区 A: sk_mild × tr_stable × atr_hi （用户先验假设）
甜蜜区 B: sk_xsym × tr_unstable × atr_hi （意外发现，样本更大）

四层验证：
  1. B=2000 精细 bootstrap（CI 收缩后是否仍排 0）
  2. 安慰剂 shuffle 验证（500 次随机打乱 trigger 标签，看真信号 vs 零假设分布）
  3. 品种集中度（Top-5 合约贡献占比）
  4. 持有期形状（H2/H4/H8 × flat/real）
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

N_BOOT = 2000
N_PLACEBO = 500
SEED = 20260709
FLAT_COST_ATR = 0.05
HOLD_TAGS = ["H2", "H4", "H8"]

# 甜蜜区定义
ZONES = {
    "A": {
        "desc": "sk_mild × tr_stable × atr_hi (用户先验)",
        "skew_lo": 0.10, "skew_hi": 0.20,   # abs_skew ∈ [0.10, 0.20)
        "trend_lo": 0.35, "trend_hi": 0.65, "trend_inside": True,
        "atr_lo": 0.67, "atr_hi": 1.01,
    },
    "B": {
        "desc": "sk_xsym × tr_unstable × atr_hi (意外发现)",
        "skew_lo": 0.00, "skew_hi": 0.10,
        "trend_lo": 0.35, "trend_hi": 0.65, "trend_inside": False,
        "atr_lo": 0.67, "atr_hi": 1.01,
    },
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
    df["close_diff_atr"] = (
        df["close_diff"] / df["close_t"].replace(0, np.nan) * 10000
        / df["daily_atr_10_bps"].replace(0, np.nan)
    )
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
    return df


def apply_zone_mask(df, zone):
    m = df["abs_skew"].between(zone["skew_lo"], zone["skew_hi"], inclusive="left")
    m &= df["atr_rank_roll"].between(zone["atr_lo"], zone["atr_hi"], inclusive="right")
    trend_in = df["trend_rank_roll"].between(zone["trend_lo"], zone["trend_hi"], inclusive="both")
    m &= trend_in if zone["trend_inside"] else ~trend_in
    return m


def pair_up(sub, df, rng):
    trig = sub[sub["is_trigger"]]
    no_trig = sub[~sub["is_trigger"]]
    if len(trig) == 0 or len(no_trig) == 0:
        return pd.DataFrame()
    rows = []
    for c in trig["contract"].dropna().unique():
        nt_c = no_trig[no_trig["contract"] == c]
        if len(nt_c) == 0:
            continue
        for side in ["L", "S"]:
            t_c = trig[(trig["contract"] == c) & (trig["trigger_side"] == side)]
            if len(t_c) == 0 or len(nt_c) < len(t_c):
                continue
            nt_avail = nt_c["close_diff_atr"].values
            nt_index = nt_c.index.values
            used = np.zeros(len(nt_avail), dtype=bool)
            sign = 1.0 if side == "L" else -1.0
            for _, row in t_c.iterrows():
                x = row["close_diff_atr"]
                if pd.isna(x):
                    continue
                d = np.abs(nt_avail - x)
                d[used] = np.inf
                pick = int(np.argmin(d))
                if not np.isfinite(d[pick]):
                    continue
                used[pick] = True
                nt_row = df.loc[nt_index[pick]]
                r = {"contract": c, "event_date": row["event_date"], "side": side}
                for h, rc in zip(HOLD_TAGS, ["ret_2h_bps", "ret_4h_bps", "ret_8h_bps"]):
                    for ct in ["flat", "real"]:
                        cost_col = f"cost_{ct}_bps"
                        r[f"trig_{h}_{ct}"] = sign * row[rc] - row[cost_col]
                        r[f"nt_{h}_{ct}"] = sign * nt_row[rc] - nt_row[cost_col]
                rows.append(r)
    if not rows:
        return pd.DataFrame()
    pdf = pd.DataFrame(rows)
    for h in HOLD_TAGS:
        for ct in ["flat", "real"]:
            pdf[f"diff_{h}_{ct}"] = pdf[f"trig_{h}_{ct}"] - pdf[f"nt_{h}_{ct}"]
    return pdf


def cluster_boot(pdf, col, n_boot, rng):
    clusters = pdf.groupby(["contract", "event_date"]).indices
    keys = list(clusters.keys())
    n = len(keys)
    arr = pdf[col].values
    boot = np.empty(n_boot)
    for b in range(n_boot):
        sampled = rng.choice(n, size=n, replace=True)
        idx = []
        for k in sampled:
            idx.extend(clusters[keys[k]])
        boot[b] = np.nanmean(arr[idx])
    return boot


def placebo_test(sub, df, n_placebo, rng):
    """随机打乱 is_trigger + trigger_side，重跑配对，看均值分布"""
    obs_indices = sub.index.values
    is_trig_orig = sub["is_trigger"].values.copy()
    side_orig = sub["trigger_side"].values.copy()
    n_trig = is_trig_orig.sum()

    placebo_means = []
    for p in range(n_placebo):
        # shuffle trigger 位置
        perm = rng.permutation(len(sub))
        new_is_trig = is_trig_orig[perm]
        new_side = side_orig[perm]
        # 修改 df 副本的这些列（只在 sub 索引上）
        sub_p = sub.copy()
        sub_p["is_trigger"] = new_is_trig
        sub_p["trigger_side"] = new_side
        pdf_p = pair_up(sub_p, df, rng)
        if pdf_p.empty:
            continue
        placebo_means.append(pdf_p["diff_H4_real"].mean())
    return np.array(placebo_means)


def analyze_zone(df, zone_id, zone, rng):
    print(f"\n{'=' * 76}")
    print(f"甜蜜区 {zone_id}: {zone['desc']}")
    print("=" * 76)
    mask = apply_zone_mask(df, zone)
    sub = df.loc[mask].copy()
    print(f"[filter] n_sub={len(sub)}, "
          f"triggers L={sub['trigger_side'].eq('L').sum()}, "
          f"S={sub['trigger_side'].eq('S').sum()}, "
          f"contracts={sub['contract'].nunique()}, "
          f"dates={sub['event_date'].nunique()}")

    pdf = pair_up(sub, df, rng)
    if pdf.empty:
        print("⚠️ 无配对")
        return None
    n_pairs = len(pdf)
    n_clusters = pdf.groupby(["contract", "event_date"]).ngroups
    print(f"[pairs] n_pairs={n_pairs}, n_clusters={n_clusters}, "
          f"n_contracts={pdf['contract'].nunique()}")

    # 层 1 · B=2000 精细 bootstrap
    print(f"\n[层 1] B={N_BOOT} 精细 bootstrap")
    results_layer1 = {}
    for h in HOLD_TAGS:
        for ct in ["flat", "real"]:
            col = f"diff_{h}_{ct}"
            obs = pdf[col].mean()
            boot = cluster_boot(pdf, col, N_BOOT, rng)
            ci_lo, ci_hi = np.quantile(boot, [0.025, 0.975])
            p_le0 = (boot <= 0).mean()
            results_layer1[f"{h}_{ct}"] = dict(mean=obs, ci_lo=ci_lo, ci_hi=ci_hi, p=p_le0)
            print(f"  {h:>3s} {ct:>4s}: mean={obs:+7.2f}  "
                  f"CI95=[{ci_lo:+7.2f}, {ci_hi:+7.2f}]  "
                  f"p(≤0)={p_le0:.3f}  {'✅' if ci_lo > 0 else '❌'}")

    # 层 2 · 安慰剂
    print(f"\n[层 2] 安慰剂 shuffle 验证（{N_PLACEBO} 次随机打乱 trigger 标签）")
    placebo = placebo_test(sub, df, N_PLACEBO, rng)
    if len(placebo) > 0:
        obs_h4_real = pdf["diff_H4_real"].mean()
        pct_ge_obs = (placebo >= obs_h4_real).mean()
        print(f"  安慰剂 n={len(placebo)}")
        print(f"  安慰剂均值分布: mean={placebo.mean():+.2f}, std={placebo.std():.2f}, "
              f"5%={np.percentile(placebo, 5):+.2f}, 95%={np.percentile(placebo, 95):+.2f}")
        print(f"  真实观测: {obs_h4_real:+.2f} bps")
        print(f"  安慰剂 >= 真实观测 比例（单侧 p）: {pct_ge_obs:.3f}")
        placebo_verdict = "✅ 显著" if pct_ge_obs < 0.05 else "❌ 与噪声不可区分"
        print(f"  {placebo_verdict}")

    # 层 3 · 品种集中度
    print(f"\n[层 3] 品种集中度")
    per_c = pdf.groupby("contract").agg(
        n_pairs=("side", "count"),
        mean_diff=("diff_H4_real", "mean"),
        sum_diff=("diff_H4_real", "sum"),
    ).sort_values("sum_diff", ascending=False)
    total_diff = per_c["sum_diff"].sum()
    per_c["contribution_pct"] = per_c["sum_diff"] / total_diff * 100
    print(f"  合约总数: {len(per_c)}")
    print(f"  正贡献合约: {(per_c['sum_diff'] > 0).sum()} ({(per_c['sum_diff'] > 0).mean()*100:.1f}%)")
    top5 = per_c.head(5)
    print(f"  Top 5 合约（按 sum_diff）：")
    print(top5.round(2).to_string())
    top5_pct = top5["contribution_pct"].sum()
    print(f"  Top 5 贡献占比: {top5_pct:.1f}%")
    top10 = per_c.head(10)
    top10_pct = top10["contribution_pct"].sum()
    print(f"  Top 10 贡献占比: {top10_pct:.1f}%")
    concentration_verdict = ("⚠️  过度集中（>60%）" if top5_pct > 60
                             else "✅ 分散良好" if top5_pct < 40 else "🟡 中等集中")
    print(f"  {concentration_verdict}")

    # 层 4 · 持有期形状（已在层 1 输出，这里聚合）
    print(f"\n[层 4] 持有期形状（H2 → H4 → H8 · real 成本）")
    for h in HOLD_TAGS:
        m = results_layer1[f"{h}_real"]["mean"]
        lo = results_layer1[f"{h}_real"]["ci_lo"]
        print(f"  {h}: mean={m:+7.2f}  CI_lo={lo:+7.2f}")

    return {
        "zone_id": zone_id, "n_pairs": n_pairs, "n_clusters": n_clusters,
        "n_contracts": pdf["contract"].nunique(),
        "results": results_layer1,
        "placebo_p": pct_ge_obs if len(placebo) > 0 else None,
        "top5_pct": top5_pct,
        "top10_pct": top10_pct,
        "positive_symbol_pct": (per_c["sum_diff"] > 0).mean(),
    }


def main():
    t0 = time.time()
    print("=" * 76)
    print("甜蜜区 A/B 深挖验证 · B=2000 bootstrap + 500 次安慰剂")
    print("=" * 76)
    df = pd.read_parquet(DATASET_PATH)
    df = preprocess(df)
    print(f"[preprocess] {len(df)} rows, elapsed={time.time()-t0:.1f}s")

    rng = np.random.RandomState(SEED)
    summary = []
    for zone_id, zone in ZONES.items():
        res = analyze_zone(df, zone_id, zone, rng)
        if res:
            summary.append(res)

    print(f"\n{'=' * 76}")
    print("A/B 对比总表")
    print("=" * 76)
    for r in summary:
        print(f"\n甜蜜区 {r['zone_id']}: n_pairs={r['n_pairs']}, contracts={r['n_contracts']}")
        for k in ["H2_real", "H4_real", "H8_real"]:
            v = r["results"][k]
            print(f"  {k}: mean={v['mean']:+7.2f}  CI=[{v['ci_lo']:+7.2f}, {v['ci_hi']:+7.2f}]  p={v['p']:.3f}")
        print(f"  安慰剂 p: {r['placebo_p']:.3f}" if r['placebo_p'] is not None else "  安慰剂: N/A")
        print(f"  Top-5 品种贡献: {r['top5_pct']:.1f}%")
        print(f"  正贡献合约占比: {r['positive_symbol_pct']*100:.1f}%")

    print(f"\n[total] elapsed = {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
