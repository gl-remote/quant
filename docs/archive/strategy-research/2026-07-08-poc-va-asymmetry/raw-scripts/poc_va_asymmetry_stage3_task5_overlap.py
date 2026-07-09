"""
文件级元信息：
- 创建背景：阶段 3 任务 5 · 4 大主线触发时刻互斥性 / 嵌套分析。
  验证 experiment-plan §3.2 任务 5 的 3 条判据：
    (1) 多头首选 vs 多头宽松：宽松是否是首选的超集（P(首选|宽松)）
    (2) 多头 vs 空头：同时触发的概率（应接近 0 · 因为 skew 方向相反）
    (3) 精选 vs 宽松组合的实际"信号密度"
- 用途：为阶段 4 组合策略做数据准备
    * 明确 4 主线的事件关系（重叠 vs 独立）
    * 若首选严格 ⊂ 宽松 · 组合权重设计更简单
    * 多空同时触发的处理策略（净头寸？对冲？）
- 注意事项：
    - 复用 stage2_grid_search 事件表
    - 计算 Jaccard / P(A|B) / Lift
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "/Users/gaolei/Documents/src/quant/scripts/ai_tmp")
from poc_va_asymmetry_stage2_grid_search import (  # noqa: E402
    prepare_dataset,
)

LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage3"
)
LOG_DIR.mkdir(parents=True, exist_ok=True)


def compute_overlap(mask_a, mask_b, name_a, name_b, total):
    n_a = int(mask_a.sum())
    n_b = int(mask_b.sum())
    n_both = int((mask_a & mask_b).sum())
    n_either = int((mask_a | mask_b).sum())
    p_a = n_a / total
    p_b = n_b / total
    p_both = n_both / total
    p_a_given_b = n_both / n_b if n_b > 0 else 0
    p_b_given_a = n_both / n_a if n_a > 0 else 0
    jaccard = n_both / n_either if n_either > 0 else 0
    lift = p_a_given_b / p_a if p_a > 0 else 0
    return {
        "pair": f"{name_a} vs {name_b}",
        "n_a": n_a, "n_b": n_b, "n_both": n_both, "n_either": n_either,
        "P(A)": p_a, "P(B)": p_b, "P(both)": p_both,
        "P(A|B)": p_a_given_b, "P(B|A)": p_b_given_a,
        "Jaccard": jaccard, "Lift": lift,
        "A_is_subset_of_B": (n_both == n_a),
        "B_is_subset_of_A": (n_both == n_b),
    }


def main():
    print("=" * 100)
    print("阶段 3 任务 5 · 4 大主线触发时刻互斥性 / 嵌套分析")
    print("=" * 100)

    print("\n[准备数据] ...")
    df = prepare_dataset()
    print(f"  总事件: {len(df)} · 合约: {df['contract'].nunique()}")

    total = len(df)

    # 4 主线 mask
    long_selected = ((df["signed_skew_rank_roll"] <= 0.10) &
                     (df["atr_rank_roll"] <= 0.70) &
                     (df["trend_rank_roll"] >= 0.75))
    long_loose = ((df["signed_skew_rank_roll"] <= 0.30) &
                  (df["atr_rank_roll"] <= 0.70) &
                  (df["trend_rank_roll"] >= 0.75))
    short_selected = ((df["signed_skew_rank_roll"] >= 0.70) &
                      (df["atr_rank_roll"] > 0.80) &
                      (df["trend_rank_roll"] <= 0.20))
    short_loose = ((df["signed_skew_rank_roll"] >= 0.70) &
                   (df["atr_rank_roll"] > 0.50) &
                   (df["trend_rank_roll"] <= 0.20))

    print(f"\n各主线触发数:")
    print(f"  多头首选: n={long_selected.sum()} · 触发率 {long_selected.sum()/total:.2%}")
    print(f"  多头宽松: n={long_loose.sum()} · 触发率 {long_loose.sum()/total:.2%}")
    print(f"  空头首选: n={short_selected.sum()} · 触发率 {short_selected.sum()/total:.2%}")
    print(f"  空头宽松: n={short_loose.sum()} · 触发率 {short_loose.sum()/total:.2%}")

    # =========================================
    # 判据 1 · 首选 ⊂ 宽松 嵌套关系
    # =========================================
    print("\n" + "=" * 100)
    print("判据 1 · 首选 ⊂ 宽松 嵌套关系")
    print("=" * 100)

    rows = []

    r = compute_overlap(long_selected, long_loose, "多头首选", "多头宽松", total)
    rows.append(r)
    print(f"\n【多头首选 vs 多头宽松】")
    print(f"  多头首选 n={r['n_a']} · 多头宽松 n={r['n_b']} · 交集 n={r['n_both']}")
    print(f"  P(多头首选|多头宽松) = {r['P(A|B)']:.2%}")
    print(f"  P(多头宽松|多头首选) = {r['P(B|A)']:.2%}")
    print(f"  Jaccard = {r['Jaccard']:.3f}")
    print(f"  首选严格 ⊂ 宽松? {'✅ 是' if r['A_is_subset_of_B'] else '❌ 否'}")

    r = compute_overlap(short_selected, short_loose, "空头首选", "空头宽松", total)
    rows.append(r)
    print(f"\n【空头首选 vs 空头宽松】")
    print(f"  空头首选 n={r['n_a']} · 空头宽松 n={r['n_b']} · 交集 n={r['n_both']}")
    print(f"  P(空头首选|空头宽松) = {r['P(A|B)']:.2%}")
    print(f"  P(空头宽松|空头首选) = {r['P(B|A)']:.2%}")
    print(f"  Jaccard = {r['Jaccard']:.3f}")
    print(f"  首选严格 ⊂ 宽松? {'✅ 是' if r['A_is_subset_of_B'] else '❌ 否'}")

    # =========================================
    # 判据 2 · 多空同时触发
    # =========================================
    print("\n" + "=" * 100)
    print("判据 2 · 多空同时触发（应接近 0 · skew 方向相反）")
    print("=" * 100)

    pairs = [
        ("多头首选", long_selected, "空头首选", short_selected),
        ("多头首选", long_selected, "空头宽松", short_loose),
        ("多头宽松", long_loose, "空头首选", short_selected),
        ("多头宽松", long_loose, "空头宽松", short_loose),
    ]
    for na, ma, nb, mb in pairs:
        r = compute_overlap(ma, mb, na, nb, total)
        rows.append(r)
        print(f"\n【{na} vs {nb}】")
        print(f"  {na} n={r['n_a']} · {nb} n={r['n_b']} · 同时触发 n={r['n_both']}")
        print(f"  Jaccard = {r['Jaccard']:.4f} · P(both) = {r['P(both)']:.4%}")
        conclusion = "✅ 完全互斥" if r['n_both'] == 0 else "⚠️ 有交集"
        print(f"  判决: {conclusion}")

    # =========================================
    # 判据 3 · 组合信号密度
    # =========================================
    print("\n" + "=" * 100)
    print("判据 3 · 组合信号密度")
    print("=" * 100)

    # 各种组合
    any_long = long_selected | long_loose
    any_short = short_selected | short_loose
    any_signal = long_selected | long_loose | short_selected | short_loose

    print(f"\n信号触发率（相对总事件数 n={total}）:")
    print(f"  多头（宽松∪首选）: n={int(any_long.sum())} · {any_long.sum()/total:.2%}")
    print(f"  空头（宽松∪首选）: n={int(any_short.sum())} · {any_short.sum()/total:.2%}")
    print(f"  任一方向: n={int(any_signal.sum())} · {any_signal.sum()/total:.2%}")

    # 每合约日均触发
    # 假设 43 合约 · 每合约每交易日约 24 事件（每小时整点 · 日盘+夜盘）
    n_contracts = df["contract"].nunique()
    events_per_day_per_contract = total / n_contracts  # 总事件数 / 合约数
    # 更准确：每合约的独立日
    n_days_avg = df.groupby("contract")["event_date"].nunique().mean()
    events_per_day = df.groupby("contract").apply(
        lambda g: len(g) / g["event_date"].nunique(), include_groups=False).mean()
    print(f"\n每合约样本平均 {n_days_avg:.0f} 交易日 · 每日约 {events_per_day:.1f} 事件")

    # 每合约每日触发概率
    trigger_per_day = {
        "多头首选": long_selected.sum() / n_contracts / n_days_avg,
        "多头宽松": long_loose.sum() / n_contracts / n_days_avg,
        "空头首选": short_selected.sum() / n_contracts / n_days_avg,
        "空头宽松": short_loose.sum() / n_contracts / n_days_avg,
        "任一方向": any_signal.sum() / n_contracts / n_days_avg,
    }
    print(f"\n每合约每交易日触发次数:")
    for name, v in trigger_per_day.items():
        interval = 1 / v if v > 0 else np.inf
        print(f"  {name:10s} : {v:.3f} 次/日 · 相当于每 {interval:.1f} 天 1 次")

    # =========================================
    # 阶段 4 组合策略启示
    # =========================================
    print("\n" + "=" * 100)
    print("阶段 4 组合策略启示")
    print("=" * 100)

    print("""
1. 首选 ⊂ 宽松：**嵌套关系**
   - 阶段 4 组合时可以"分层加仓"：首选触发时加大仓位 · 宽松触发时减仓
   - 或者做"分档触发"：首选=1x 单位 · 宽松-首选=0.5x 单位

2. 多空互斥：**完全或近乎完全互斥**
   - 同一时刻不会同时做多做空同一品种
   - 阶段 4 净头寸管理简单：直接看方向 · 无对冲需要
   - 跨品种时可以自然形成多空对冲

3. 组合信号密度：
   - 任一方向触发约每合约每日 X 次
   - 若跨 43 合约同时监控 · 全天可能 M 次触发
   - 频率是可控的（不会过密）
""")

    # 保存
    pd.DataFrame(rows).to_csv(LOG_DIR / "task5_overlap.csv", index=False)
    print(f"输出：{LOG_DIR / 'task5_overlap.csv'}")


if __name__ == "__main__":
    main()
