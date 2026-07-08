"""
方案 C · 品种前缀分组 rank · 快速验证是否显著改善分类器质量

改动：
- 原来 rank 按 (contract) 分组 · 每个合约月份独立
- 现在 rank 按 (prefix) 分组 · 同品种不同月份合约合并（e.g. rb2410 + rb2510 + rb2601 合成 rb）
- 同品种数据合并 · 每个 rank 样本量 x2-x5

对比项：
1. 5 主线严格 date-cluster bootstrap CI + Bonferroni
2. 触发事件数（前缀池化后更早 warmup · 应该增加）
3. 结论方向是否与原 per-contract 一致
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "/Users/gaolei/Documents/src/quant/scripts/ai_tmp")
from poc_va_asymmetry_stage2_grid_search import (  # noqa: E402
    prepare_dataset, ROLLING_EVENTS, ROLLING_DAYS,
)
from poc_va_asymmetry_stage3_task3_regime_transition import flag_regime_transition  # noqa: E402
from poc_va_asymmetry_stage3_classifier_strict_bootstrap import (  # noqa: E402
    cluster_bootstrap_by_date, BONF_ALPHA,
)


def rolling_pct_rank_series(s: pd.Series, window: int) -> pd.Series:
    """rolling window 的严格小于分位排名."""
    def _rank(w):
        if len(w) < 2:
            return np.nan
        return (w < w.iloc[-1]).sum() / len(w)
    return s.rolling(window, min_periods=2).apply(_rank, raw=False)


def prepare_dataset_with_prefix_rank():
    """加载数据 · 用 prefix 分组重算 rank."""
    df = prepare_dataset()
    df["prefix"] = df["contract"].str.extract(r"^([A-Za-z]+\.?[A-Za-z]+)")
    # 从 contract 名 · 提取品种前缀（去掉月份数字）· 例如 SHFE.rb2601 -> SHFE.rb
    df["prefix"] = df["contract"].apply(lambda x: "".join([c for c in x if not c.isdigit()]))

    # 按 (prefix, event_time) 排序 · 用 prefix 分组 rank
    df = df.sort_values(["prefix", "event_time"]).reset_index(drop=True)

    # 新版 rank · 按 prefix 分组
    df["signed_skew_rank_prefix"] = df.groupby("prefix")["A3_skew"].transform(
        lambda s: rolling_pct_rank_series(s, ROLLING_EVENTS)
    )

    # atr / trend 也需要按 prefix 分组
    # 但注意：atr / trend 是日线级别 · 同一日期同 prefix 可能多合约 · 需要去重
    for col in ["daily_atr_10_bps", "trend_ret_10d"]:
        # 每个 (prefix, date) 只保留 1 个值（首个合约的值）· 然后按 prefix 排序 rank
        # 简化：直接用 rolling · 但要小心 · rank window 是 events 单位
        # 更严谨：先按 date 去重 · 再 rank
        daily = df.groupby(["prefix", "event_date"])[col].first().reset_index()
        daily = daily.sort_values(["prefix", "event_date"])
        daily[f"{col}_rank_prefix"] = daily.groupby("prefix")[col].transform(
            lambda s: rolling_pct_rank_series(s, ROLLING_DAYS)
        )
        df = df.merge(
            daily[["prefix", "event_date", f"{col}_rank_prefix"]],
            on=["prefix", "event_date"], how="left",
        )

    return df


def analyze_combo(df, name, mask, ret_col, rank_type=""):
    sub = df[mask].dropna(subset=[ret_col, "transition_flag"]).copy()
    sub["event_date"] = pd.to_datetime(sub["event_time"]).dt.date
    stable = sub[~sub["transition_flag"]]

    rows = []
    for tag, seg in [("full", sub), ("stable", stable)]:
        if len(seg) < 20:
            continue
        result = cluster_bootstrap_by_date(
            seg[ret_col], seg["contract"], seg["event_date"], n_boot=3000, seed=42,
        )
        n_prefix = seg["prefix"].nunique() if "prefix" in seg.columns else -1
        rows.append({
            "rank_type": rank_type,
            "combo": name,
            "period": tag,
            "n_events": result["n_events"],
            "n_clusters_date": result["n_clusters_date"],
            "n_prefix": n_prefix,
            "mean_bps": result["mean"],
            "ci_lo_95": result["ci_lo_95"],
            "ci_hi_95": result["ci_hi_95"],
            "p_two": result["p_two"],
            "pass_bonf": result["p_two"] < BONF_ALPHA,
        })
    return rows


def run_signals(df, rank_type):
    """用给定的 rank 列跑 5 主线."""
    signals = [
        ("多头首选", "long", 0.10, 0.70, 0.75, "ret_8h_bps"),
        ("多头宽松", "long", 0.30, 0.70, 0.75, "ret_8h_bps"),
        ("空头首选", "short", 0.70, 0.80, 0.20, "short_pnl_4h_bps"),
        ("空头宽松", "short", 0.70, 0.50, 0.20, "short_pnl_4h_bps"),
        ("空头收敛", "short", 0.70, 0.67, 0.20, "short_pnl_4h_bps"),
    ]

    if rank_type == "per_contract":
        skew_col, atr_col, trend_col = "signed_skew_rank_roll", "atr_rank_roll", "trend_rank_roll"
    else:  # prefix
        skew_col, atr_col, trend_col = (
            "signed_skew_rank_prefix",
            "daily_atr_10_bps_rank_prefix",
            "trend_ret_10d_rank_prefix",
        )

    rows = []
    for name, direction, sk, at, tr, ret_col in signals:
        if direction == "long":
            mask = ((df[skew_col] <= sk) &
                    (df[atr_col] <= at) &
                    (df[trend_col] >= tr))
        else:
            mask = ((df[skew_col] >= sk) &
                    (df[atr_col] > at) &
                    (df[trend_col] <= tr))
        rows.extend(analyze_combo(df, name, mask, ret_col, rank_type=rank_type))
    return rows


def main():
    print("=" * 100)
    print("方案 C · 品种前缀分组 rank · vs 原 per-contract rank 对比")
    print("=" * 100)

    df = prepare_dataset_with_prefix_rank()
    df = flag_regime_transition(df)

    # 统计每个 prefix 的合约数
    prefix_counts = df.groupby("prefix")["contract"].nunique().sort_values(ascending=False)
    print(f"\nPrefix 分布 · 前 10：")
    for p, n in prefix_counts.head(10).items():
        events = (df["prefix"] == p).sum()
        print(f"  {p:15s} {n} 合约 · {events} events")

    print(f"\n总数：{df['prefix'].nunique()} prefix · {df['contract'].nunique()} 合约")

    print("\n" + "=" * 100)
    print("A · 原 per-contract rank（严格 date bootstrap）")
    print("=" * 100)
    old_rows = run_signals(df, rank_type="per_contract")

    print(f"\n{'组合':10s} {'期别':8s} {'n':>5s} {'n_date':>7s} "
          f"{'mean':>8s} {'95% CI':>22s} {'p':>10s} {'Bonf'}")
    for r in old_rows:
        ci = f"[{r['ci_lo_95']:>+7.1f},{r['ci_hi_95']:>+7.1f}]"
        bonf = "✅" if r["pass_bonf"] else "❌"
        print(f"{r['combo']:10s} {r['period']:8s} {int(r['n_events']):>5d} "
              f"{int(r['n_clusters_date']):>7d} {r['mean_bps']:>+8.1f} {ci:>22s} "
              f"{r['p_two']:>10.4f} {bonf}")

    print("\n" + "=" * 100)
    print("B · 品种前缀分组 rank（严格 date bootstrap）")
    print("=" * 100)
    new_rows = run_signals(df, rank_type="prefix")

    print(f"\n{'组合':10s} {'期别':8s} {'n':>5s} {'n_date':>7s} {'n_prefix':>8s} "
          f"{'mean':>8s} {'95% CI':>22s} {'p':>10s} {'Bonf'}")
    for r in new_rows:
        ci = f"[{r['ci_lo_95']:>+7.1f},{r['ci_hi_95']:>+7.1f}]"
        bonf = "✅" if r["pass_bonf"] else "❌"
        print(f"{r['combo']:10s} {r['period']:8s} {int(r['n_events']):>5d} "
              f"{int(r['n_clusters_date']):>7d} {int(r['n_prefix']):>8d} "
              f"{r['mean_bps']:>+8.1f} {ci:>22s} "
              f"{r['p_two']:>10.4f} {bonf}")

    print("\n" + "=" * 100)
    print("对比 · per-contract vs prefix")
    print("=" * 100)
    df_old = pd.DataFrame(old_rows).set_index(["combo", "period"])
    df_new = pd.DataFrame(new_rows).set_index(["combo", "period"])

    print(f"\n{'组合':10s} {'期别':8s} "
          f"{'n_ev 旧':>8s} {'n_ev 新':>8s} {'Δn %':>8s} "
          f"{'mean 旧':>8s} {'mean 新':>8s} "
          f"{'CI 旧宽':>8s} {'CI 新宽':>8s} "
          f"{'Bonf 旧':>7s} {'Bonf 新':>7s}")
    for idx in df_old.index:
        if idx not in df_new.index:
            continue
        o = df_old.loc[idx]
        n = df_new.loc[idx]
        dn_pct = (n["n_events"] - o["n_events"]) / o["n_events"] * 100
        w_o = o["ci_hi_95"] - o["ci_lo_95"]
        w_n = n["ci_hi_95"] - n["ci_lo_95"]
        bo = "✅" if o["pass_bonf"] else "❌"
        bn = "✅" if n["pass_bonf"] else "❌"
        print(f"{idx[0]:10s} {idx[1]:8s} "
              f"{int(o['n_events']):>8d} {int(n['n_events']):>8d} {dn_pct:>+7.1f}% "
              f"{o['mean_bps']:>+8.1f} {n['mean_bps']:>+8.1f} "
              f"{w_o:>8.1f} {w_n:>8.1f} "
              f"{bo:>7s} {bn:>7s}")

    LOG_DIR = Path("/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage3")
    pd.concat([pd.DataFrame(old_rows), pd.DataFrame(new_rows)]).to_csv(
        LOG_DIR / "classifier_prefix_rank_comparison.csv", index=False,
    )


if __name__ == "__main__":
    main()
