#!/usr/bin/env python3
"""
轻量版 Gatekeeper：VA 对称子环境 reaccept 验证（速度优先，定性够用）
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workspace"))

import numpy as np
import pandas as pd
from common.contract_specs import CONTRACT_SPECS

DATASET_PATH = Path("project_data/logs/poc_va_asymmetry_stage4/dataset_full.parquet")
OUT_DIR = Path("project_data/ai_tmp")
OUT_DIR.mkdir(parents=True, exist_ok=True)

SKEW_NEUTRAL = (0.30, 0.70)
ATR_MIDHIGH = (0.33, 1.00)
TREND_STABLE = (0.20, 0.80)
HOLD_BARS = 8
N_BOOTSTRAP = 200
SEED = 20260709

def main():
    print("=" * 70)
    print("轻量 Gatekeeper：VA 对称 + 中高波动 + 趋势平稳 · Reaccept")
    print("=" * 70)

    # 0. 加载
    df = pd.read_parquet(DATASET_PATH).copy()
    df["event_time"] = pd.to_datetime(df["event_time"])
    df["event_date"] = pd.to_datetime(df["event_date"]).dt.date
    print(f"\n[0] 数据加载：{len(df)} 行，{df['contract'].nunique()} 合约")

    # 1. 三维筛选
    mask = (
        df["signed_skew_rank_roll"].between(*SKEW_NEUTRAL, inclusive="both")
        & df["atr_rank_roll"].between(*ATR_MIDHIGH, inclusive="right")
        & df["trend_rank_roll"].between(*TREND_STABLE, inclusive="both")
    )
    df["pool"] = np.where(mask, "sub", "gbl")
    n_sub = mask.sum()
    print(f"[1] 三维筛选：sub pool = {n_sub} ({n_sub/len(df)*100:.1f}%)，"
          f"合约数 = {df.loc[mask, 'contract'].nunique()}，"
          f"日期数 = {df.loc[mask, 'event_date'].nunique()}")

    # 2. 制度土壤：子池 vs 全局
    def soil(tag):
        sub = df[df["pool"] == tag]
        r = sub["ret_8h_bps"].dropna()
        sub_sorted = sub.sort_values(["contract", "event_time"])
        autoc = sub_sorted.groupby("contract")["ret_8h_bps"].apply(
            lambda s: s.autocorr(1) if s.notna().sum() > 10 else np.nan
        ).mean()
        return {
            "n": len(sub),
            "mean_8h": float(r.mean()),
            "std_8h": float(r.std()),
            "hit": float((r > 0).mean()),
            "atr_mean": float(sub["daily_atr_10_bps"].mean()),
            "autocorr_lag1": float(autoc),
        }

    gbl = soil("gbl")
    sub = soil("sub")
    print(f"\n[2] 制度土壤检查")
    print(f"  全局  : mean_8h={gbl['mean_8h']:+.2f}bps, hit={gbl['hit']*100:.1f}%, "
          f"atr={gbl['atr_mean']:.1f}bps, autocorr={gbl['autocorr_lag1']:+.3f}")
    print(f"  子池  : mean_8h={sub['mean_8h']:+.2f}bps, hit={sub['hit']*100:.1f}%, "
          f"atr={sub['atr_mean']:.1f}bps, autocorr={sub['autocorr_lag1']:+.3f}")
    diff_mean = sub["mean_8h"] - gbl["mean_8h"]
    print(f"  差值  : Δmean={diff_mean:+.2f}bps (子池更{'乐观' if diff_mean > 0 else '悲观'})")
    # 反转土壤：自相关越负，均值回归越强 → reaccept 越有戏
    if sub["autocorr_lag1"] < gbl["autocorr_lag1"]:
        print(f"  ✅ 反转土壤：子池自相关更低（{sub['autocorr_lag1']:+.3f} vs {gbl['autocorr_lag1']:+.3f}），支持 reaccept 假设")
    else:
        print(f"  ❌ 反转土壤：子池自相关不低，不支持均值回归型 reaccept")

    # 3. 触发器代理 & 配对
    sub_df = df[df["pool"] == "sub"].copy().sort_values(["contract", "event_time"]).reset_index(drop=True)

    # 向量化：rank20 + close_diff
    sub_df["rank20"] = sub_df.groupby("contract")["close_t"].transform(
        lambda s: s.rolling(20, min_periods=10).rank(pct=True)
    )
    sub_df["close_diff"] = sub_df.groupby("contract")["close_t"].diff(1)
    sub_df["close_diff_atr"] = (
        sub_df["close_diff"] / sub_df["close_t"].replace(0, np.nan) * 10000
        / sub_df["daily_atr_10_bps"].replace(0, np.nan)
    )

    # 触发器（向量化，非逐行 apply）
    cond_long = sub_df["rank20"].notna() & sub_df["close_diff"].notna() & (sub_df["rank20"] <= 0.20) & (sub_df["close_diff"] > 0)
    cond_short = sub_df["rank20"].notna() & sub_df["close_diff"].notna() & (sub_df["rank20"] >= 0.80) & (sub_df["close_diff"] < 0)
    sub_df["trigger_side"] = np.where(cond_long, "long", np.where(cond_short, "short", None))
    sub_df["is_trigger"] = sub_df["trigger_side"].notna()

    n_trig = sub_df["is_trigger"].sum()
    n_long = cond_long.sum()
    n_short = cond_short.sum()
    print(f"\n[3] 触发器代理（粗糙版·仅定性）")
    print(f"  触发总数：{n_trig}（L={n_long}, S={n_short}），触发率={n_trig/len(sub_df)*100:.2f}%")

    if n_trig < 30:
        print("  ⚠️  触发器太少（<30），代理规则可能过严，结论仅供参考")

    # 成本：扁平成本近似（向量化，不用 apply）
    sub_df["cost_flat_bps"] = sub_df["daily_atr_10_bps"] * 0.05
    # 真实成本：向量化快速估算
    def fast_real_cost_vec(contracts, prices):
        uniq = contracts.unique()
        out = np.full(len(contracts), np.nan)
        for c in uniq:
            spec = CONTRACT_SPECS.get_symbol(c)
            if spec is None:
                continue
            m = contracts == c
            p = prices[m]
            size = spec.size
            comm = spec.total_commission_np(p, 1) if hasattr(spec, 'total_commission_np') else np.array([spec.total_commission(price=float(x), lots=1) for x in p])
            slip = spec.slippage_np(1) if hasattr(spec, 'slippage_np') else spec.slippage(lots=1)
            total = 2 * (comm + slip)
            notional = p * size
            out[m] = total / notional * 10000
        return out
    sub_df["cost_real_bps"] = fast_real_cost_vec(sub_df["contract"].values, sub_df["close_t"].values)

    # 方向 PnL（向量化）
    sign = np.where(sub_df["trigger_side"] == "long", 1.0,
                    np.where(sub_df["trigger_side"] == "short", -1.0, np.nan))
    for ct in ["flat", "real"]:
        sub_df[f"pnl_{ct}"] = sign * sub_df["ret_8h_bps"] - sub_df[f"cost_{ct}_bps"]

    # 快速配对：简化版（同 contract + 同 side，按 close_diff_atr 分桶，不放回 1:1）
    rng = np.random.RandomState(SEED)
    pairs_data = []
    for contract in sub_df["contract"].dropna().unique():
        cdf = sub_df[sub_df["contract"] == contract].reset_index(drop=True)
        for side in ["long", "short"]:
            trig = cdf[cdf["is_trigger"] & (cdf["trigger_side"] == side)].copy()
            no_trig = cdf[~cdf["is_trigger"]].copy()
            if len(trig) == 0 or len(no_trig) < len(trig):
                continue
            # 分桶
            all_vals = pd.concat([trig["close_diff_atr"], no_trig["close_diff_atr"]]).dropna()
            if len(all_vals) < 10:
                continue
            try:
                bins = np.quantile(all_vals, np.linspace(0, 1, 6))
                bins = np.unique(bins)
                trig["bin"] = pd.cut(trig["close_diff_atr"], bins=bins, labels=False, include_lowest=True)
                no_trig = no_trig.copy()
                no_trig["bin"] = pd.cut(no_trig["close_diff_atr"], bins=bins, labels=False, include_lowest=True)
            except Exception:
                continue
            used = set()
            for i, row in trig.iterrows():
                b = row["bin"]
                if pd.isna(b):
                    continue
                cands = no_trig[no_trig["bin"].isin([b-1, b, b+1]) & ~no_trig.index.isin(used)]
                if len(cands) == 0:
                    continue
                diff = (cands["close_diff_atr"] - row["close_diff_atr"]).abs()
                minv = diff.min()
                match_idx = diff[diff <= minv * 1.0001].index.tolist()
                pick = cands.loc[rng.choice(match_idx)]
                used.add(pick.name)
                pid = f"{contract}_{side}_{len(pairs_data)//2}"
                s = 1.0 if side == "long" else -1.0
                pairs_data.append({
                    "pair_id": pid, "role": "reaccept", "side": side,
                    "contract": contract, "event_date": row["event_date"],
                    "pnl_flat": row["pnl_flat"], "pnl_real": row["pnl_real"],
                    "ret_8h": row["ret_8h_bps"],
                })
                pairs_data.append({
                    "pair_id": pid, "role": "no_trigger", "side": side,
                    "contract": contract, "event_date": pick["event_date"],
                    "pnl_flat": s * pick["ret_8h_bps"] - pick["cost_flat_bps"],
                    "pnl_real": s * pick["ret_8h_bps"] - pick["cost_real_bps"],
                    "ret_8h": pick["ret_8h_bps"],
                })

    if not pairs_data:
        print("\n  ⚠️  未形成任何配对，跳过 bootstrap")
        print("\n=== 快速判决 ===")
        print("结论：❌ 数据层面不支持（无配对样本），该子假设暂不成立")
        return

    pdf = pd.DataFrame(pairs_data)
    # pair 级 pivot
    piv = pdf.pivot_table(index="pair_id", columns="role", values=["pnl_flat", "pnl_real"], aggfunc="first")
    piv.columns = [f"{a}_{b}" for a, b in piv.columns]
    meta = pdf.groupby("pair_id")[["contract", "event_date", "side"]].first()
    merged = piv.join(meta).reset_index()
    for ct in ["flat", "real"]:
        merged[f"diff_{ct}"] = merged[f"pnl_{ct}_reaccept"] - merged[f"pnl_{ct}_no_trigger"]

    n_pairs = len(merged)
    print(f"  配对数：{n_pairs}（{merged['contract'].nunique()} 合约 × {merged['event_date'].nunique()} 天）")

    # Cluster bootstrap
    cluster_keys = merged.groupby(["contract", "event_date"]).size().reset_index()[["contract", "event_date"]].values.tolist()
    n_clusters = len(cluster_keys)
    print(f"  聚类数：(contract,date) = {n_clusters}")

    rng2 = np.random.RandomState(SEED)
    boot_result = {}
    for ct in ["flat", "real"]:
        boot_diffs = []
        for _ in range(N_BOOTSTRAP):
            idx = rng2.choice(n_clusters, size=n_clusters, replace=True)
            sel_rows = []
            for k in idx:
                c, d = cluster_keys[k]
                sel = merged[(merged["contract"] == c) & (merged["event_date"] == d)]
                sel_rows.append(sel)
            if not sel_rows:
                continue
            bdf = pd.concat(sel_rows)
            if len(bdf) == 0:
                continue
            boot_diffs.append(bdf[f"diff_{ct}"].mean())
        if not boot_diffs:
            continue
        arr = np.array(boot_diffs)
        obs_diff = merged[f"diff_{ct}"].mean()
        obs_re = merged[f"pnl_{ct}_reaccept"].mean()
        obs_nt = merged[f"pnl_{ct}_no_trigger"].mean()
        ci_lo, ci_hi = float(np.quantile(arr, 0.025)), float(np.quantile(arr, 0.975))
        p_le0 = float((arr <= 0).mean())
        # 品种保留率
        per_c = merged.groupby("contract")[f"diff_{ct}"].mean()
        sym_ret = float((per_c > 0).mean())
        hit_re = float((merged[f"pnl_{ct}_reaccept"] > 0).mean())
        hit_nt = float((merged[f"pnl_{ct}_no_trigger"] > 0).mean())
        boot_result[ct] = {
            "re_mean": obs_re, "nt_mean": obs_nt, "diff_mean": obs_diff,
            "ci_lo": ci_lo, "ci_hi": ci_hi, "p_le0": p_le0,
            "sym_retention": sym_ret, "n_contracts": int(per_c.notna().sum()),
            "hit_re": hit_re, "hit_nt": hit_nt,
        }
        print(f"\n  --- {ct} 成本 ---")
        print(f"    reaccept:  mean={obs_re:+.2f}bps, hit={hit_re*100:.1f}%")
        print(f"    no_trigger: mean={obs_nt:+.2f}bps, hit={hit_nt*100:.1f}%")
        print(f"    配对差:    mean={obs_diff:+.2f}bps, CI95=[{ci_lo:+.2f}, {ci_hi:+.2f}], p(diff<=0)={p_le0:.3f}")
        print(f"    品种保留率: {sym_ret*100:.1f}% (n={per_c.notna().sum()})")
        print(f"    CI 排 0？{'✅' if ci_lo > 0 else '❌'}  品保≥60%？{'✅' if sym_ret >= 0.60 else '❌'}")

    # 保存
    summary = {
        "soil_global": gbl, "soil_subset": sub,
        "n_triggers": int(n_trig), "n_pairs": int(n_pairs),
        **{f"boot_{ct}": v for ct, v in boot_result.items()},
    }
    import json
    with open(OUT_DIR / "va_sym_reaccept_fast_result.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\n[save] -> {OUT_DIR / 'va_sym_reaccept_fast_result.json'}")

    # 最终判决
    print("\n" + "=" * 70)
    print("=== Gatekeeper 综合判决 ===")
    print("=" * 70)
    flat_ok = (boot_result.get("flat", {}).get("ci_lo", -999) > 0 and
               boot_result.get("flat", {}).get("sym_retention", 0) >= 0.60)
    real_ok = (boot_result.get("real", {}).get("ci_lo", -999) > 0 and
               boot_result.get("real", {}).get("sym_retention", 0) >= 0.60)
    soil_ok = sub["autocorr_lag1"] < gbl["autocorr_lag1"]

    if flat_ok and real_ok and soil_ok:
        print("✅ PASS：三维子环境 + 触发器增量均显著，子假设通过")
        verdict = "PASS"
    elif flat_ok and not real_ok:
        print("⚠️  PARTIAL：扁平成本通过，真实成本失败 → 成本吃掉全部增量")
        verdict = "PARTIAL_FLAT_ONLY"
    elif not flat_ok and not real_ok:
        print("❌ FAIL：CI 未排 0 或品保不足，子假设不成立")
        verdict = "FAIL"
    else:
        print("⚠️  边界情况，需人工复核")
        verdict = "BORDERLINE"
    print(f"\nverdict={verdict}")

if __name__ == "__main__":
    main()
