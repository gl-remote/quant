"""
文件级元信息：
- 创建背景：跑完 poc_va_classifier_verify 后 · 需要在 144 tier 尺度上做样本分层
  与 profitable 分级 · 回答"是不是 144 个 tier 都在？大部分能用吗？"这一问题。
- 用途：读取 classifier_v31_tier_performance.csv · 按样本量分桶 · 按方向统计
  profitable tier 数 · 输出 A-/A/A+ 三级白名单清单。
- 注意事项：临时脚本 · 不落盘 · 只 stdout；一次性诊断用途 · 阶段 4 定型后可删。
"""

from __future__ import annotations

import pandas as pd


PERF_PATH = (
    "/Users/gaolei/Documents/src/quant/project_data/logs/"
    "poc_va_asymmetry_stage4/classifier_v31_tier_performance.csv"
)


def main() -> None:
    perf_df = pd.read_csv(PERF_PATH)
    pd.set_option("display.width", 200)

    print(f"总 tier 数：{len(perf_df)} (spec 上限 144)")
    print()

    buckets = [(0, 5), (5, 20), (20, 50), (50, 100), (100, 200), (200, 10000)]
    print("按样本量 n_events 分层：")
    for lo, hi in buckets:
        m = (perf_df.n_events >= lo) & (perf_df.n_events < hi)
        print(f"  n ∈ [{lo:>3d}, {hi:>5d})  count={int(m.sum()):>3d}")
    print()

    print("各方向 profitable (net>0) tier 数：")
    print(f"  L4 net>0 :  {int((perf_df.L4_net_bps > 0).sum())}/144")
    print(f"  L8 net>0 :  {int((perf_df.L8_net_bps > 0).sum())}/144")
    print(f"  S4 net>0 :  {int((perf_df.S4_net_bps > 0).sum())}/144")
    any_pos = (
        (perf_df.L4_net_bps > 0)
        | (perf_df.L8_net_bps > 0)
        | (perf_df.S4_net_bps > 0)
    )
    print(f"  任一方向 net>0:  {int(any_pos.sum())}/144")
    print()

    print("分级：")
    a_minus_L = perf_df[(perf_df.L4_net_bps > 0) & (perf_df.n_events >= 30)]
    a_minus_S = perf_df[(perf_df.S4_net_bps > 0) & (perf_df.n_events >= 30)]
    print(
        f"  A- 宽松 · net>0 & n>=30                        : "
        f"LONG {len(a_minus_L):>3d} tier / SHORT {len(a_minus_S):>3d} tier"
    )

    a_L = perf_df[
        (perf_df.L4_net_bps > 5)
        & (perf_df.L4_ir > 0.15)
        & (perf_df.n_events >= 50)
        & (perf_df.n_contracts >= 10)
    ]
    a_S = perf_df[
        (perf_df.S4_net_bps > 5)
        & (perf_df.S4_ir > 0.15)
        & (perf_df.n_events >= 50)
        & (perf_df.n_contracts >= 10)
    ]
    print(
        f"  A  中等 · net>5 & IR>0.15 & n>=50 & c>=10       : "
        f"LONG {len(a_L):>3d} tier / SHORT {len(a_S):>3d} tier"
    )

    a_plus_L = perf_df[
        (perf_df.L4_net_bps > 10)
        & (perf_df.L4_ir > 0.25)
        & (perf_df.n_events >= 80)
        & (perf_df.n_contracts >= 15)
        & (perf_df.n_dates >= 15)
    ]
    a_plus_S = perf_df[
        (perf_df.S4_net_bps > 10)
        & (perf_df.S4_ir > 0.25)
        & (perf_df.n_events >= 80)
        & (perf_df.n_contracts >= 15)
        & (perf_df.n_dates >= 15)
    ]
    print(
        f"  A+ 严格 · net>10 & IR>0.25 & n>=80 & c>=15 & d>=15: "
        f"LONG {len(a_plus_L):>3d} tier / SHORT {len(a_plus_S):>3d} tier"
    )
    print()

    print("=" * 110)
    print("A 级中等白名单 (net>5 & IR>0.15 & n>=50 & contracts>=10) · LONG")
    print("=" * 110)
    long_cols = [
        "tier", "n_events", "n_contracts", "n_dates",
        "L4_gross_bps", "L4_net_bps", "L4_ir", "L4_hit",
    ]
    print(a_L.sort_values("L4_net_bps", ascending=False)[long_cols].to_string(index=False))
    print(f"  Total: {len(a_L)} tiers")
    print()

    print("=" * 110)
    print("A 级中等白名单 · SHORT")
    print("=" * 110)
    short_cols = [
        "tier", "n_events", "n_contracts", "n_dates",
        "S4_gross_bps", "S4_net_bps", "S4_ir", "S4_hit",
    ]
    print(a_S.sort_values("S4_net_bps", ascending=False)[short_cols].to_string(index=False))
    print(f"  Total: {len(a_S)} tiers")


if __name__ == "__main__":
    main()
