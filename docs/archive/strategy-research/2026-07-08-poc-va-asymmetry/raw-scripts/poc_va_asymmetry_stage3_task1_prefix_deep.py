"""
文件级元信息：
- 创建背景：阶段 3 任务 1 · 4 大主线分品种深挖对齐。阶段 2 洞察 M-深挖
  只做了旧空头 E · 新 sweet spot 需要同样深度覆盖。
- 用途：
    (1) 对 4 大主线（多头首选/多头宽松/空头首选/空头宽松）
        分别做分品种表：n / n_contracts / mean / hit / CI（cluster boot）
    (2) 计算每主线的品种保留度（正 mean 品种数 / 总品种数）
    (3) 判据：≥80% 品种保留 edge 且 CI 排 0 · 才认定"品种普适性"
- 注意事项：
    - 复用 stage2_grid_search 的事件表 · 严格无未来函数
    - 多头 8h horizon · 空头 4h horizon
    - 每品种 n < 5 事件的忽略
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "/Users/gaolei/Documents/src/quant/scripts/ai_tmp")
from poc_va_asymmetry_stage2_grid_search import (  # noqa: E402
    prepare_dataset, cluster_bootstrap, parse_prefix,
)

LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage3"
)
LOG_DIR.mkdir(parents=True, exist_ok=True)


def eval_prefix(sub, ret_col):
    """算某品种在某主线下的 mean/hit"""
    if len(sub) < 5:
        return None
    return {
        "n": len(sub),
        "n_contracts": sub["contract"].nunique(),
        "mean_bps": sub[ret_col].mean(),
        "hit": (sub[ret_col] > 0).mean(),
    }


def analyze_signal(df, name, mask, ret_col):
    print(f"\n{'='*90}")
    print(f"【{name}】")
    print("=" * 90)

    sub = df[mask].dropna(subset=[ret_col]).copy()
    sub["prefix"] = sub["contract"].apply(parse_prefix)

    # 分品种
    rows = []
    for prefix, g in sub.groupby("prefix"):
        r = eval_prefix(g, ret_col)
        if r is None:
            continue
        # 品种级 CI 只有单合约时不做 cluster · 直接 mean 分布
        rows.append({"prefix": prefix, **r})

    if not rows:
        print("  无有效品种")
        return None
    prefix_df = pd.DataFrame(rows).sort_values("mean_bps", ascending=False)

    print(f"\n{'品种':6s} {'合约数':>6s} {'事件':>6s} {'mean bps':>10s} {'hit':>7s}")
    n_positive = 0
    n_hit_over_55 = 0
    for _, r in prefix_df.iterrows():
        print(f"{r['prefix']:6s} {int(r['n_contracts']):>6d} {int(r['n']):>6d} "
              f"{r['mean_bps']:>+10.2f} {r['hit']:>7.1%}")
        if r["mean_bps"] > 0:
            n_positive += 1
        if r["hit"] >= 0.55:
            n_hit_over_55 += 1

    n_total = len(prefix_df)
    pos_ratio = n_positive / n_total
    hit_ratio = n_hit_over_55 / n_total
    print(f"\n正 mean 品种: {n_positive}/{n_total} = {pos_ratio:.1%}")
    print(f"hit ≥ 55% 品种: {n_hit_over_55}/{n_total} = {hit_ratio:.1%}")
    print(f"判据 ≥ 80% 保留 edge: {'✅' if pos_ratio >= 0.80 else '❌'}")

    # 全池 cluster CI
    r = cluster_bootstrap(sub, ret_col)
    print(f"\n全池 pooled:")
    print(f"  n={r['n_events']} · 合约={r['n_contracts']}")
    print(f"  mean={r['real_mean']:+.2f} · hit={(sub[ret_col]>0).mean():.1%}")
    print(f"  95% CI=[{r['ci_lo']:+.2f}, {r['ci_hi']:+.2f}] · p={r['p_two']:.4f}")

    return {
        "name": name,
        "n_total_prefixes": n_total,
        "n_positive": n_positive,
        "n_hit_over_55": n_hit_over_55,
        "pos_ratio": pos_ratio,
        "hit_ratio": hit_ratio,
        "pooled_mean": r["real_mean"],
        "pooled_ci_lo": r["ci_lo"],
        "pooled_ci_hi": r["ci_hi"],
        "pooled_p": r["p_two"],
        "prefix_df": prefix_df,
    }


def main():
    print("=" * 100)
    print("阶段 3 任务 1 · 4 大主线分品种深挖对齐")
    print("=" * 100)

    print("\n[准备数据] ...")
    df = prepare_dataset()
    print(f"  总事件: {len(df)} · 合约: {df['contract'].nunique()}")

    signals = [
        ("多头首选（skew≤0.10 · atr≤0.70 · trend≥0.75 · 8h）",
         "long", 0.10, 0.70, 0.75),
        ("多头宽松（skew≤0.30 · atr≤0.70 · trend≥0.75 · 8h）",
         "long", 0.30, 0.70, 0.75),
        ("空头首选（skew≥0.70 · atr>0.80 · trend≤0.20 · 4h）",
         "short", 0.70, 0.80, 0.20),
        ("空头宽松（skew≥0.70 · atr>0.50 · trend≤0.20 · 4h）",
         "short", 0.70, 0.50, 0.20),
    ]

    summary = []
    all_prefix_tables = []
    for name, direction, sk, at, tr in signals:
        if direction == "long":
            mask = ((df["signed_skew_rank_roll"] <= sk) &
                    (df["atr_rank_roll"] <= at) &
                    (df["trend_rank_roll"] >= tr))
            ret_col = "ret_8h_bps"
        else:
            mask = ((df["signed_skew_rank_roll"] >= sk) &
                    (df["atr_rank_roll"] > at) &
                    (df["trend_rank_roll"] <= tr))
            ret_col = "short_pnl_4h_bps"
        r = analyze_signal(df, name, mask, ret_col)
        if r is None:
            continue
        pfx = r.pop("prefix_df")
        pfx["signal"] = name
        all_prefix_tables.append(pfx)
        summary.append(r)

    print("\n" + "=" * 100)
    print("汇总 · 4 大主线品种保留度对比")
    print("=" * 100)
    print(f"\n{'主线':60s} {'品种':>5s} {'正':>4s} {'占比':>6s} "
          f"{'pooled':>8s} {'CI下':>7s} {'p':>7s} 判据")
    for s in summary:
        judge = "✅" if s["pos_ratio"] >= 0.80 else "❌"
        short_name = s["name"].split("（")[0]
        print(f"{short_name:60s} {s['n_total_prefixes']:>5d} {s['n_positive']:>4d} "
              f"{s['pos_ratio']:>6.1%} {s['pooled_mean']:>+8.2f} "
              f"{s['pooled_ci_lo']:>+7.2f} {s['pooled_p']:>7.4f}  {judge}")

    # 保存
    if all_prefix_tables:
        pd.concat(all_prefix_tables, ignore_index=True).to_csv(
            LOG_DIR / "task1_prefix_deep.csv", index=False)
    pd.DataFrame([{k: v for k, v in s.items() if k != "prefix_df"} for s in summary]).to_csv(
        LOG_DIR / "task1_summary.csv", index=False)

    print("\n输出：")
    print(f"  {LOG_DIR / 'task1_prefix_deep.csv'}")
    print(f"  {LOG_DIR / 'task1_summary.csv'}")


if __name__ == "__main__":
    main()
