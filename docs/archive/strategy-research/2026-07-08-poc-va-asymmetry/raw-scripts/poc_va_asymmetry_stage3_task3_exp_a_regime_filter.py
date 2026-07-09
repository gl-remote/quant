"""
文件级元信息：
- 创建背景：阶段 3 任务 3 后置实验 · 检验"加 regime 稳定 filter"是否能改善
  4 大主线信号。目标是回答洞察 R 提出的问题：transition 期衰减 · 加过滤后
  能否恢复？
- 用途：
    (1) 复用任务 3 的 transition_flag（前 3 交易日 rank 跨越 33/67 判定）
    (2) 4 大主线上 "全事件" vs "仅 regime 稳定日"
    (3) 计算 CI · 对比 mean 提升 · n 损失
    (4) 判定：是否值得作为"背景标签使用说明书"的强化过滤
- 假设：
    * 若稳定日 mean 提升 >20% 且 CI 依然排 0 → 强化过滤有价值
    * 若稳定日 mean 提升 <10% → 说明衰减是"边缘事件问题"·filter 无意义
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "/Users/gaolei/Documents/src/quant/scripts/ai_tmp")
from poc_va_asymmetry_stage2_grid_search import (  # noqa: E402
    prepare_dataset, cluster_bootstrap,
)
from poc_va_asymmetry_stage3_task3_regime_transition import (  # noqa: E402
    flag_regime_transition,
)

LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage3"
)


def analyze(df, name, mask, ret_col):
    print(f"\n{'='*90}")
    print(f"【{name}】")
    print("=" * 90)

    sub = df[mask].dropna(subset=[ret_col, "transition_flag"])
    full = sub
    stable = sub[~sub["transition_flag"]]

    print(f"\n全事件: n={len(full)}")
    print(f"仅稳定日: n={len(stable)} ({len(stable)/max(1,len(full)):.1%})")

    if len(full) < 20 or len(stable) < 20:
        print("样本不足 · 跳过")
        return None

    r_full = cluster_bootstrap(full, ret_col)
    r_stable = cluster_bootstrap(stable, ret_col)
    hit_f = (full[ret_col] > 0).mean()
    hit_s = (stable[ret_col] > 0).mean()

    print(f"\n{'版本':15s} {'n':>5s} {'品种':>4s} {'mean':>8s} {'hit':>7s} "
          f"{'CI下':>8s} {'CI上':>8s} {'p':>7s} 判决")
    for lbl, r, hit in [("全事件", r_full, hit_f), ("仅稳定日", r_stable, hit_s)]:
        pass_ = "✅" if r["ci_lo"] > 0 else "❌"
        print(f"{lbl:15s} {r['n_events']:>5d} {r['n_contracts']:>4d} "
              f"{r['real_mean']:>+8.2f} {hit:>7.1%} "
              f"{r['ci_lo']:>+8.2f} {r['ci_hi']:>+8.2f} "
              f"{r['p_two']:>7.4f}  {pass_}")

    gain = r_stable["real_mean"] - r_full["real_mean"]
    gain_pct = gain / abs(r_full["real_mean"]) * 100 if r_full["real_mean"] != 0 else 0
    n_loss = 1 - len(stable) / len(full)
    print(f"\nmean 提升: {gain:+.2f} bps · 增益 {gain_pct:+.1f}%")
    print(f"n 损失: {n_loss:.1%} (从 {len(full)} 掉到 {len(stable)})")

    # 判据
    if gain_pct >= 20 and r_stable["ci_lo"] > 0:
        judge = "✅ 强化过滤有价值 · 建议作为默认边界"
    elif gain_pct >= 10:
        judge = "⚠️ 有一定提升 · 视具体主线权衡"
    else:
        judge = "❌ 无显著提升 · 衰减是边缘事件问题 · filter 无价值"
    print(f"判定: {judge}")

    return {
        "signal": name,
        "n_full": r_full["n_events"],
        "n_stable": r_stable["n_events"],
        "mean_full": r_full["real_mean"],
        "mean_stable": r_stable["real_mean"],
        "hit_full": hit_f,
        "hit_stable": hit_s,
        "ci_lo_full": r_full["ci_lo"],
        "ci_lo_stable": r_stable["ci_lo"],
        "gain_pct": gain_pct,
        "n_loss": n_loss,
    }


def main():
    print("=" * 100)
    print("阶段 3 任务 3 后置实验 A · Regime 稳定 filter 效果检验")
    print("=" * 100)

    print("\n[准备数据 + 标注 regime transition] ...")
    df = prepare_dataset()
    df = flag_regime_transition(df)
    print(f"  总事件: {len(df)}")
    print(f"  稳定日: {(~df['transition_flag']).sum()} ({(~df['transition_flag']).mean():.1%})")
    print(f"  转换日: {df['transition_flag'].sum()} ({df['transition_flag'].mean():.1%})")

    signals = [
        ("多头首选（skew≤0.10·atr≤0.70·trend≥0.75·8h）",
         "long", 0.10, 0.70, 0.75),
        ("多头宽松（skew≤0.30·atr≤0.70·trend≥0.75·8h）",
         "long", 0.30, 0.70, 0.75),
        ("空头首选（skew≥0.70·atr>0.80·trend≤0.20·4h）",
         "short", 0.70, 0.80, 0.20),
        ("空头宽松（skew≥0.70·atr>0.50·trend≤0.20·4h）",
         "short", 0.70, 0.50, 0.20),
        ("空头收敛（skew≥0.70·atr>0.67·trend≤0.20·4h · 洞察 Q 建议）",
         "short", 0.70, 0.67, 0.20),
    ]

    all_rows = []
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
        r = analyze(df, name, mask, ret_col)
        if r:
            all_rows.append(r)

    # 汇总
    print("\n" + "=" * 100)
    print("汇总 · 5 主线 · 全事件 vs 仅稳定日")
    print("=" * 100)
    print(f"\n{'主线':60s} {'全事件 mean':>10s} {'稳定 mean':>10s} {'增益%':>8s} {'n 损失':>7s} 判决")
    n_good = 0
    for r in all_rows:
        short_name = r["signal"].split("（")[0]
        judge = "✅" if r["gain_pct"] >= 20 else ("⚠️" if r["gain_pct"] >= 10 else "❌")
        print(f"{short_name:60s} {r['mean_full']:>+10.2f} {r['mean_stable']:>+10.2f} "
              f"{r['gain_pct']:>+8.1f} {r['n_loss']:>7.1%} {judge}")
        if r["gain_pct"] >= 20:
            n_good += 1

    print(f"\n显著改善（增益>20%）: {n_good}/{len(all_rows)}")
    if n_good >= 3:
        print("✅ 大多数主线适合 regime 稳定过滤")
    elif n_good >= 1:
        print("⚠️ 部分主线适合 · 需分主线决策")
    else:
        print("❌ regime 稳定 filter 意义有限 · 衰减多为边缘事件问题")

    pd.DataFrame(all_rows).to_csv(LOG_DIR / "task3_experiment_a_regime_filter.csv", index=False)
    print(f"\n输出：{LOG_DIR / 'task3_experiment_a_regime_filter.csv'}")


if __name__ == "__main__":
    main()
