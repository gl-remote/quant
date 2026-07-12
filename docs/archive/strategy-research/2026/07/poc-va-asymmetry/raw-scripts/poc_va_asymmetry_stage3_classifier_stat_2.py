"""
文件级元信息：
- 创建背景：阶段 3 分类器严格性验证 · 脚本 2（C+D）
  C · 分类器性能指标（Sharpe / IR / MDD · 通过 cluster bootstrap 生成路径分布）
  D · 8 组合 × 品种保留率矩阵
- 输出：
    - classifier_stat_2_perf.csv（Sharpe/IR/MDD）
    - classifier_stat_2_symbol_matrix.csv（品种矩阵）
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "/Users/gaolei/Documents/src/quant/scripts/ai_tmp")
from poc_va_asymmetry_stage2_grid_search import (  # noqa: E402
    prepare_dataset, parse_prefix,
)
from poc_va_asymmetry_stage3_task3_regime_transition import (  # noqa: E402
    flag_regime_transition,
)

LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage3"
)

N_BOOT = 3000  # 路径 bootstrap


# ============================================
# C · 分类器性能（Sharpe / IR / MDD）
# ============================================
def path_metrics(returns_bps, seed=42):
    """
    通过 cluster bootstrap 生成 5000 条模拟"年度路径" · 每条路径按时序假设 · 计算：
    - Sharpe（年化 · assume 250 交易日）
    - MDD（累计路径的最大回撤）
    - Info Ratio（相对无 alpha baseline · 假设 baseline mean = 0）
    """
    if len(returns_bps) < 20:
        return None
    r = returns_bps.values / 1e4  # bps → log return
    n = len(r)
    rng = np.random.default_rng(seed)

    # 假设一年触发次数：现有事件 * (250 天 / 60 天) · 保守估算
    yearly_events = int(n * 250 / 60)

    sharpes = []
    mdds = []
    for _ in range(N_BOOT):
        # 从事件池里有放回抽样
        idx = rng.integers(0, n, size=yearly_events)
        path_r = r[idx]
        cum = np.cumsum(path_r)  # 累计 log return
        # Sharpe（简单：mean/std * sqrt(N)· 因每次交易独立）
        sh = path_r.mean() / path_r.std() * np.sqrt(yearly_events) if path_r.std() > 0 else 0
        sharpes.append(sh)
        # MDD
        run_max = np.maximum.accumulate(cum)
        dd = run_max - cum
        mdds.append(dd.max())

    return {
        "n_events": n,
        "yearly_events_est": yearly_events,
        "sharpe_mean": np.mean(sharpes),
        "sharpe_median": np.median(sharpes),
        "sharpe_p05": np.quantile(sharpes, 0.05),
        "sharpe_p95": np.quantile(sharpes, 0.95),
        "mdd_bps_mean": np.mean(mdds) * 1e4,
        "mdd_bps_median": np.median(mdds) * 1e4,
        "mdd_bps_p95": np.quantile(mdds, 0.95) * 1e4,  # 95% worst case MDD
        # IR：相对 baseline=0 · 就是 Sharpe · 这里给条件 IR = mean / std（未年化）
        "ir_per_trade": r.mean() / r.std() if r.std() > 0 else 0,
    }


def run_perf(df, name, mask, ret_col):
    sub = df[mask].dropna(subset=[ret_col, "transition_flag"])
    stable = sub[~sub["transition_flag"]]
    trans = sub[sub["transition_flag"]]

    rows = []
    for tag, seg in [("full", sub), ("stable", stable), ("trans", trans)]:
        if len(seg) < 20:
            continue
        pm = path_metrics(seg[ret_col], seed=42)
        if pm is None:
            continue
        pm["combo"] = name
        pm["period"] = tag
        rows.append(pm)
    return rows


# ============================================
# D · 8 组合 × 品种保留率矩阵
# ============================================
def run_symbol_matrix(df, name, mask, ret_col):
    sub = df[mask].dropna(subset=[ret_col, "transition_flag"])
    sub = sub.copy()
    sub["prefix"] = sub["contract"].apply(parse_prefix)

    rows = []
    for tag, seg in [("full", sub),
                     ("stable", sub[~sub["transition_flag"]]),
                     ("trans", sub[sub["transition_flag"]])]:
        if len(seg) == 0:
            continue
        for p, gp in seg.groupby("prefix"):
            if len(gp) < 5:
                continue
            rows.append({
                "combo": name,
                "period": tag,
                "prefix": p,
                "n": len(gp),
                "mean_bps": gp[ret_col].mean(),
                "hit": (gp[ret_col] > 0).mean(),
                "positive": 1 if gp[ret_col].mean() > 0 else 0,
            })
    return rows


def main():
    print("=" * 100)
    print("阶段 3 分类器严格性 · 脚本 2（C 性能 + D 品种矩阵）")
    print("=" * 100)

    df = prepare_dataset()
    df = flag_regime_transition(df)

    signals = [
        ("多头首选", "long", 0.10, 0.70, 0.75, "ret_8h_bps"),
        ("多头宽松", "long", 0.30, 0.70, 0.75, "ret_8h_bps"),
        ("空头首选", "short", 0.70, 0.80, 0.20, "short_pnl_4h_bps"),
        ("空头宽松", "short", 0.70, 0.50, 0.20, "short_pnl_4h_bps"),
        ("空头收敛", "short", 0.70, 0.67, 0.20, "short_pnl_4h_bps"),
    ]

    perf_rows = []
    matrix_rows = []
    for name, direction, sk, at, tr, ret_col in signals:
        if direction == "long":
            mask = ((df["signed_skew_rank_roll"] <= sk) &
                    (df["atr_rank_roll"] <= at) &
                    (df["trend_rank_roll"] >= tr))
        else:
            mask = ((df["signed_skew_rank_roll"] >= sk) &
                    (df["atr_rank_roll"] > at) &
                    (df["trend_rank_roll"] <= tr))
        perf_rows.extend(run_perf(df, name, mask, ret_col))
        matrix_rows.extend(run_symbol_matrix(df, name, mask, ret_col))

    # C · Sharpe / MDD 输出
    print("\n" + "=" * 100)
    print("C · 分类器性能（Sharpe · MDD · Info Ratio）")
    print("=" * 100)
    perf_df = pd.DataFrame(perf_rows)
    perf_df.to_csv(LOG_DIR / "classifier_stat_2_perf.csv", index=False)

    print(f"\n{'组合':12s} {'期别':8s} {'n':>5s} {'年触发':>8s} "
          f"{'Sharpe':>8s} {'Sh p05':>8s} {'Sh p95':>8s} {'MDD bps':>10s} {'IR/tr':>8s}")
    for _, r in perf_df.iterrows():
        print(f"{r['combo']:12s} {r['period']:8s} "
              f"{int(r['n_events']):>5d} {int(r['yearly_events_est']):>8d} "
              f"{r['sharpe_mean']:>+8.2f} {r['sharpe_p05']:>+8.2f} {r['sharpe_p95']:>+8.2f} "
              f"{r['mdd_bps_mean']:>10.1f} {r['ir_per_trade']:>+8.3f}")

    # D · 品种矩阵
    print("\n" + "=" * 100)
    print("D · 8 组合 × 品种保留率矩阵")
    print("=" * 100)
    matrix_df = pd.DataFrame(matrix_rows)
    matrix_df.to_csv(LOG_DIR / "classifier_stat_2_symbol_matrix.csv", index=False)

    for name, _, _, _, _, _ in signals:
        print(f"\n【{name}】")
        for period in ["full", "stable", "trans"]:
            seg = matrix_df[(matrix_df["combo"] == name) &
                            (matrix_df["period"] == period)]
            if len(seg) < 3:
                continue
            n_total = len(seg)
            n_pos = seg["positive"].sum()
            top3 = seg.nlargest(3, "mean_bps")[["prefix", "n", "mean_bps"]]
            bot3 = seg.nsmallest(3, "mean_bps")[["prefix", "n", "mean_bps"]]
            print(f"  {period:8s} 保留 {n_pos}/{n_total} ({n_pos/n_total:.1%})")
            print(f"    top3: " + " · ".join(
                [f"{r['prefix']}({int(r['n'])})={r['mean_bps']:+.1f}" for _, r in top3.iterrows()]))
            print(f"    bot3: " + " · ".join(
                [f"{r['prefix']}({int(r['n'])})={r['mean_bps']:+.1f}" for _, r in bot3.iterrows()]))

    # 汇总保留率表格
    print("\n" + "=" * 100)
    print("D 汇总 · 品种保留率")
    print("=" * 100)
    print(f"\n{'组合':12s} {'全事件':>10s} {'稳定期':>10s} {'转换期':>10s}")
    for name, _, _, _, _, _ in signals:
        row = f"{name:12s} "
        for period in ["full", "stable", "trans"]:
            seg = matrix_df[(matrix_df["combo"] == name) &
                            (matrix_df["period"] == period)]
            if len(seg) < 3:
                row += f"{'-':>10s} "
                continue
            n_pos = seg["positive"].sum()
            n_total = len(seg)
            row += f"{n_pos}/{n_total}({n_pos/n_total:.0%})".rjust(10) + " "
        print(row)

    print(f"\n输出：")
    print(f"  {LOG_DIR / 'classifier_stat_2_perf.csv'}")
    print(f"  {LOG_DIR / 'classifier_stat_2_symbol_matrix.csv'}")


if __name__ == "__main__":
    main()
