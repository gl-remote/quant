"""
细粒度阈值扫描 · 找到"严格创新高"到"打到前高附近"的最优过渡点

假设：
- 阈值 0.10 = 严格创新低（前 10 日最低）
- 阈值 0.15-0.20 = 打到前低附近（前 10 日最低 2-3 名）
- 阈值 >0.20 = 明显稀释

测试：
1. skew 阈值扫描 0.05-0.25（每 0.02 一档）· 看 mean/CI/触发次数
2. 空头对称 · skew 阈值扫描 0.60-0.90
3. 找到"性价比最好的阈值"（mean × sqrt(n) 或 Sharpe 代理）
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "/Users/gaolei/Documents/src/quant/scripts/ai_tmp")
from poc_va_asymmetry_stage2_grid_search import prepare_dataset  # noqa: E402
from poc_va_asymmetry_stage3_task3_regime_transition import flag_regime_transition  # noqa: E402
from poc_va_asymmetry_stage3_classifier_strict_bootstrap import (  # noqa: E402
    cluster_bootstrap_by_date, BONF_ALPHA,
)


def scan_thresholds(df, atr_thr, atr_op, trend_thr, trend_op, skew_thrs, direction, ret_col):
    """扫描 skew 阈值范围 · 每个阈值算 mean/CI/n/Sharpe 代理."""
    rows = []
    for sk in skew_thrs:
        if direction == "long":
            mask = ((df["signed_skew_rank_roll"] <= sk) &
                    (df["atr_rank_roll"] <= atr_thr) &
                    (df["trend_rank_roll"] >= trend_thr))
        else:
            mask = ((df["signed_skew_rank_roll"] >= sk) &
                    (df["atr_rank_roll"] > atr_thr) &
                    (df["trend_rank_roll"] <= trend_thr))

        sub = df[mask].dropna(subset=[ret_col, "transition_flag"]).copy()
        sub["event_date"] = pd.to_datetime(sub["event_time"]).dt.date

        if len(sub) < 20:
            continue

        # Bootstrap
        b = cluster_bootstrap_by_date(sub[ret_col], sub["contract"], sub["event_date"], n_boot=3000)

        # Sharpe 代理（按天聚合 · sqrt(252)）
        daily = sub.groupby("event_date")[ret_col].sum()
        # 补 0 天
        idx = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
        daily_full = daily.reindex(idx, fill_value=0.0)
        sharpe = (daily_full.mean() / daily_full.std() * np.sqrt(252)
                  if daily_full.std() > 0 else 0)

        rows.append({
            "skew_thr": sk,
            "n_events": b["n_events"],
            "n_dates": b["n_clusters_date"],
            "mean_bps": b["mean"],
            "hit": (sub[ret_col] > 0).mean(),
            "ci_lo": b["ci_lo_95"],
            "ci_hi": b["ci_hi_95"],
            "p_two": b["p_two"],
            "sharpe_annual": sharpe,
            "ir_per_trade": sub[ret_col].mean() / sub[ret_col].std() if sub[ret_col].std() > 0 else 0,
            "pass_bonf": b["p_two"] < BONF_ALPHA,
            "score_mean_sqrt_n": b["mean"] * np.sqrt(b["n_events"]),  # 综合评分
        })
    return pd.DataFrame(rows)


def main():
    print("=" * 110)
    print('细粒度 skew 阈值扫描 · 找 "严格创新高" vs "打到前高附近" 的最优点')
    print("=" * 110)

    df = prepare_dataset()
    df = flag_regime_transition(df)

    # 只用稳定期（更清晰）
    df = df[~df["transition_flag"]].copy()

    print(f"\n数据（仅稳定期）：{len(df)} events\n")

    # ==============================================
    # 多头首选（trend≥0.75 · atr≤0.70）· skew 从 0.05 到 0.25 扫描
    # ==============================================
    print("=" * 110)
    print("多头首选·稳定期 · skew 阈值扫描（每 0.02 一档）")
    print("固定 atr≤0.70 · trend≥0.75 · horizon 8h")
    print("=" * 110)
    skew_thrs_long = np.arange(0.05, 0.26, 0.02).round(2)
    long_scan = scan_thresholds(df, 0.70, "<=", 0.75, ">=", skew_thrs_long, "long", "ret_8h_bps")
    long_scan["combo"] = "多头稳定"

    print(f"\n{'skew阈值':>8s} {'n_ev':>5s} {'n_days':>7s} {'mean':>8s} {'hit':>6s} "
          f"{'95% CI':>22s} {'p':>10s} {'Sharpe':>8s} {'IR':>7s} {'Bonf':>6s} {'评分':>8s}")
    print("-" * 130)
    for _, r in long_scan.iterrows():
        ci = f"[{r['ci_lo']:>+6.1f},{r['ci_hi']:>+6.1f}]"
        bonf = "✅" if r["pass_bonf"] else "❌"
        marker = ""
        if r["skew_thr"] in [0.10]:
            marker = " ← 当前紧"
        elif r["skew_thr"] in [0.30]:
            marker = " ← 当前松"
        print(f"{r['skew_thr']:>8.2f} {int(r['n_events']):>5d} {int(r['n_dates']):>7d} "
              f"{r['mean_bps']:>+8.1f} {r['hit']:>5.1%} {ci:>22s} "
              f"{r['p_two']:>10.4f} {r['sharpe_annual']:>+8.2f} "
              f"{r['ir_per_trade']:>+7.3f} {bonf:>6s} {r['score_mean_sqrt_n']:>+8.1f}{marker}")

    # ==============================================
    # 空头收敛（trend≤0.20 · atr>0.67）· skew 从 0.60 到 0.85 扫描
    # ==============================================
    print("\n" + "=" * 110)
    print("空头收敛·稳定期 · skew 阈值扫描（每 0.02 一档）")
    print("固定 atr>0.67 · trend≤0.20 · horizon 4h")
    print("=" * 110)
    skew_thrs_short = np.arange(0.60, 0.87, 0.02).round(2)
    short_scan = scan_thresholds(df, 0.67, ">", 0.20, "<=", skew_thrs_short, "short", "short_pnl_4h_bps")
    short_scan["combo"] = "空头收敛稳定"

    print(f"\n{'skew阈值':>8s} {'n_ev':>5s} {'n_days':>7s} {'mean':>8s} {'hit':>6s} "
          f"{'95% CI':>22s} {'p':>10s} {'Sharpe':>8s} {'IR':>7s} {'Bonf':>6s} {'评分':>8s}")
    print("-" * 130)
    for _, r in short_scan.iterrows():
        ci = f"[{r['ci_lo']:>+6.1f},{r['ci_hi']:>+6.1f}]"
        bonf = "✅" if r["pass_bonf"] else "❌"
        marker = ""
        if r["skew_thr"] in [0.70]:
            marker = " ← 当前"
        print(f"{r['skew_thr']:>8.2f} {int(r['n_events']):>5d} {int(r['n_dates']):>7d} "
              f"{r['mean_bps']:>+8.1f} {r['hit']:>5.1%} {ci:>22s} "
              f"{r['p_two']:>10.4f} {r['sharpe_annual']:>+8.2f} "
              f"{r['ir_per_trade']:>+7.3f} {bonf:>6s} {r['score_mean_sqrt_n']:>+8.1f}{marker}")

    # ==============================================
    # 找最优点
    # ==============================================
    print("\n" + "=" * 110)
    print("最优阈值分析 · 综合 mean/CI/n/Sharpe")
    print("=" * 110)

    print("\n【多头首选·稳定】· 各指标 top 3：")
    for metric in ["mean_bps", "sharpe_annual", "score_mean_sqrt_n", "ir_per_trade"]:
        top3 = long_scan.nlargest(3, metric)
        print(f"  {metric:>25s}: " + " · ".join([
            f"skew≤{r['skew_thr']:.2f} ({r[metric]:.2f})"
            for _, r in top3.iterrows()
        ]))

    print("\n【空头收敛·稳定】· 各指标 top 3：")
    for metric in ["mean_bps", "sharpe_annual", "score_mean_sqrt_n", "ir_per_trade"]:
        top3 = short_scan.nlargest(3, metric)
        print(f"  {metric:>25s}: " + " · ".join([
            f"skew≥{r['skew_thr']:.2f} ({r[metric]:.2f})"
            for _, r in top3.iterrows()
        ]))

    # 保存
    LOG_DIR = Path("/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage3")
    pd.concat([long_scan, short_scan]).to_csv(
        LOG_DIR / "classifier_threshold_scan.csv", index=False,
    )
    print(f"\n输出：{LOG_DIR / 'classifier_threshold_scan.csv'}")


if __name__ == "__main__":
    main()
