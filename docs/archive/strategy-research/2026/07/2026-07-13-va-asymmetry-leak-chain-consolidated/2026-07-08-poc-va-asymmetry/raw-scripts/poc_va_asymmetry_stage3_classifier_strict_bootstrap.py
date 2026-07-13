"""
严格 cluster bootstrap · 修正因日内 event 共 W1 导致的相关性高估。

背景：
- 阶段 3 §12 用 cluster bootstrap by contract · 但同一 contract 同一天的 10 个 event
  共享同一 A3_skew_rank + atr_rank + trend_rank · 未来 8h 收益也高度重叠
- 真实独立 unit 是 (contract, date) · 不是 (contract)
- 用 (contract, date) 聚类会得到更宽的 CI · 更诚实的显著性

目的：不是"补精度"（精度就那么多）· 而是"揭露之前 CI 的虚高程度"。

输出：
- classifier_strict_bootstrap.csv · 每主线 × 期别 · 严格 CI + Bonferroni 结果
- 终端对比表：旧 CI vs 新 CI · SE 放大倍数 · Bonferroni 保留/剔除
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "/Users/gaolei/Documents/src/quant/scripts/ai_tmp")
from poc_va_asymmetry_stage2_grid_search import prepare_dataset  # noqa: E402
from poc_va_asymmetry_stage3_task3_regime_transition import flag_regime_transition  # noqa: E402

LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage3"
)

BOOT_N = 5000
BONF_ALPHA = 0.05 / 8  # 0.00625


def cluster_bootstrap_by_date(returns_bps, contract, date, n_boot=BOOT_N, seed=42):
    """按 (contract, date) unit 的 cluster bootstrap."""
    df = pd.DataFrame({
        "ret": np.asarray(returns_bps),
        "key": list(zip(np.asarray(contract), np.asarray(date))),
    })
    groups = df.groupby("key")
    keys = list(groups.groups.keys())
    n_clusters = len(keys)
    # 预抽 cluster 的 ret 数组 · 避免重复筛选
    cluster_rets = [df.loc[groups.groups[k], "ret"].values for k in keys]

    rng = np.random.default_rng(seed)
    boot_means = np.zeros(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, n_clusters, size=n_clusters)
        picked = [cluster_rets[j] for j in idx]
        boot_means[i] = np.concatenate(picked).mean()

    real_mean = df["ret"].mean()
    return {
        "n_events": len(df),
        "n_clusters_date": n_clusters,
        "mean": real_mean,
        "ci_lo_95": np.quantile(boot_means, 0.025),
        "ci_hi_95": np.quantile(boot_means, 0.975),
        "ci_lo_99": np.quantile(boot_means, 0.005),  # 99% CI (bonf-friendly)
        "ci_hi_99": np.quantile(boot_means, 0.995),
        "p_two": 2 * min((boot_means <= 0).mean(), (boot_means >= 0).mean()),
        "se_estimate": boot_means.std(),
    }


def cluster_bootstrap_by_contract(returns_bps, contract, n_boot=BOOT_N, seed=42):
    """旧口径 · 按 contract 聚类（对比用）."""
    df = pd.DataFrame({
        "ret": np.asarray(returns_bps),
        "contract": np.asarray(contract),
    })
    groups = df.groupby("contract")
    ks = list(groups.groups.keys())
    n_c = len(ks)
    per_c = [df.loc[groups.groups[k], "ret"].values for k in ks]

    rng = np.random.default_rng(seed)
    boot_means = np.zeros(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, n_c, size=n_c)
        picked = [per_c[j] for j in idx]
        boot_means[i] = np.concatenate(picked).mean()

    return {
        "n_clusters_contract": n_c,
        "ci_lo_95_old": np.quantile(boot_means, 0.025),
        "ci_hi_95_old": np.quantile(boot_means, 0.975),
        "p_two_old": 2 * min((boot_means <= 0).mean(), (boot_means >= 0).mean()),
        "se_old": boot_means.std(),
    }


def analyze_combo(df, name, mask, ret_col):
    sub = df[mask].dropna(subset=[ret_col, "transition_flag"]).copy()
    sub["event_date"] = pd.to_datetime(sub["event_time"]).dt.date

    stable = sub[~sub["transition_flag"]]
    trans = sub[sub["transition_flag"]]

    rows = []
    for tag, seg in [("full", sub), ("stable", stable), ("trans", trans)]:
        if len(seg) < 20:
            continue

        strict = cluster_bootstrap_by_date(seg[ret_col], seg["contract"], seg["event_date"])
        old = cluster_bootstrap_by_contract(seg[ret_col], seg["contract"])

        se_ratio = strict["se_estimate"] / old["se_old"] if old["se_old"] > 0 else np.nan

        rows.append({
            "combo": name,
            "period": tag,
            "n_events": strict["n_events"],
            "n_clusters_date": strict["n_clusters_date"],
            "n_clusters_contract": old["n_clusters_contract"],
            "mean_bps": strict["mean"],
            "ci_lo_95_old": old["ci_lo_95_old"],
            "ci_hi_95_old": old["ci_hi_95_old"],
            "ci_lo_95_strict": strict["ci_lo_95"],
            "ci_hi_95_strict": strict["ci_hi_95"],
            "ci_lo_99_strict": strict["ci_lo_99"],
            "p_old": old["p_two_old"],
            "p_strict": strict["p_two"],
            "se_ratio": se_ratio,
            "pass_bonf_old": old["p_two_old"] < BONF_ALPHA,
            "pass_bonf_strict": strict["p_two"] < BONF_ALPHA,
            "ci_excl_0_old": (old["ci_lo_95_old"] > 0) or (old["ci_hi_95_old"] < 0),
            "ci_excl_0_strict_95": (strict["ci_lo_95"] > 0) or (strict["ci_hi_95"] < 0),
            "ci_excl_0_strict_99": (strict["ci_lo_99"] > 0) or (strict["ci_hi_99"] < 0),
        })
    return rows


def main():
    print("=" * 110)
    print("严格 cluster bootstrap · 按 (contract, date) unit · 揭露旧口径虚高程度")
    print("=" * 110)
    print(f"\n参数：n_boot={BOOT_N} · Bonferroni α = {BONF_ALPHA:.5f} (family=8)")

    df = prepare_dataset()
    df = flag_regime_transition(df)

    signals = [
        ("多头首选", "long", 0.10, 0.70, 0.75, "ret_8h_bps"),
        ("多头宽松", "long", 0.30, 0.70, 0.75, "ret_8h_bps"),
        ("空头首选", "short", 0.70, 0.80, 0.20, "short_pnl_4h_bps"),
        ("空头宽松", "short", 0.70, 0.50, 0.20, "short_pnl_4h_bps"),
        ("空头收敛", "short", 0.70, 0.67, 0.20, "short_pnl_4h_bps"),
    ]

    all_rows = []
    for name, direction, sk, at, tr, ret_col in signals:
        if direction == "long":
            mask = ((df["signed_skew_rank_roll"] <= sk) &
                    (df["atr_rank_roll"] <= at) &
                    (df["trend_rank_roll"] >= tr))
        else:
            mask = ((df["signed_skew_rank_roll"] >= sk) &
                    (df["atr_rank_roll"] > at) &
                    (df["trend_rank_roll"] <= tr))
        all_rows.extend(analyze_combo(df, name, mask, ret_col))

    out_df = pd.DataFrame(all_rows)
    out_df.to_csv(LOG_DIR / "classifier_strict_bootstrap.csv", index=False)

    # ================================
    # 主表输出：旧 vs 新 CI 对比
    # ================================
    print(f"\n{'组合':10s} {'期别':8s} {'n_ev':>5s} {'n_contract':>10s} {'n_date':>8s} "
          f"{'mean':>8s} {'CI_old 95%':>22s} {'CI_strict 95%':>24s} "
          f"{'p_old':>10s} {'p_strict':>10s} {'SE 放大':>8s} "
          f"{'旧 Bonf':>8s} {'新 Bonf':>8s}")
    print("-" * 180)
    for _, r in out_df.iterrows():
        old_ci = f"[{r['ci_lo_95_old']:>+7.1f},{r['ci_hi_95_old']:>+7.1f}]"
        new_ci = f"[{r['ci_lo_95_strict']:>+7.1f},{r['ci_hi_95_strict']:>+7.1f}]"
        old_bonf = "✅" if r["pass_bonf_old"] else "❌"
        new_bonf = "✅" if r["pass_bonf_strict"] else "❌"
        print(f"{r['combo']:10s} {r['period']:8s} "
              f"{int(r['n_events']):>5d} {int(r['n_clusters_contract']):>10d} "
              f"{int(r['n_clusters_date']):>8d} "
              f"{r['mean_bps']:>+8.1f} {old_ci:>22s} {new_ci:>24s} "
              f"{r['p_old']:>10.4f} {r['p_strict']:>10.4f} "
              f"{r['se_ratio']:>8.2f} "
              f"{old_bonf:>8s} {new_bonf:>8s}")

    # ================================
    # 汇总：Bonferroni 保留 / 剔除
    # ================================
    print("\n" + "=" * 110)
    print("Bonferroni 严格性保留判决（p < 0.00625）")
    print("=" * 110)
    print(f"\n{'档位':20s} {'p_old':>10s} {'p_strict':>10s} {'旧':>6s} {'新':>6s} {'判读'}")
    for _, r in out_df.iterrows():
        key = f"{r['combo']}·{r['period']}"
        old_bonf = "✅" if r["pass_bonf_old"] else "❌"
        new_bonf = "✅" if r["pass_bonf_strict"] else "❌"
        if r["pass_bonf_old"] and r["pass_bonf_strict"]:
            verdict = "✅ 保留"
        elif r["pass_bonf_old"] and not r["pass_bonf_strict"]:
            verdict = "⚠️  旧过新不过 · 严格版剔除"
        elif not r["pass_bonf_old"] and r["pass_bonf_strict"]:
            verdict = "??? 新过旧不过 · 罕见"
        else:
            verdict = "❌ 均不过"
        print(f"{key:20s} {r['p_old']:>10.4f} {r['p_strict']:>10.4f} "
              f"{old_bonf:>6s} {new_bonf:>6s} {verdict}")

    # ================================
    # 汇总：CI 排 0 判决
    # ================================
    print("\n" + "=" * 110)
    print("95% CI 排 0 判决对比")
    print("=" * 110)
    print(f"\n{'档位':20s} {'CI_old 排 0':>15s} {'CI_strict 95% 排 0':>22s} "
          f"{'CI_strict 99% 排 0':>22s} {'判读'}")
    for _, r in out_df.iterrows():
        key = f"{r['combo']}·{r['period']}"
        o = "✅" if r["ci_excl_0_old"] else "❌"
        s95 = "✅" if r["ci_excl_0_strict_95"] else "❌"
        s99 = "✅" if r["ci_excl_0_strict_99"] else "❌"
        if r["ci_excl_0_strict_95"]:
            verdict = "✅ 严格 95% CI 排 0"
        elif r["ci_excl_0_old"] and not r["ci_excl_0_strict_95"]:
            verdict = "⚠️  旧排 0 · 严格版触 0"
        else:
            verdict = "❌ 旧新均触 0"
        print(f"{key:20s} {o:>15s} {s95:>22s} {s99:>22s} {verdict}")

    print(f"\n输出：{LOG_DIR / 'classifier_strict_bootstrap.csv'}")


if __name__ == "__main__":
    main()
