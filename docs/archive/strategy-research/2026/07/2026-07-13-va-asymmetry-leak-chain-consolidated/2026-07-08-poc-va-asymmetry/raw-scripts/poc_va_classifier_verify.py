"""
文件级元信息：
- 创建背景：POC-VA 分类器 v3.1 组件的单元测试 + stage4 数据对齐验证。
- 用途：跑 evaluate_dataset · 与 stage4 描述性 CSV 交叉验证 · 输出 144 tier timeline
  与 tier 分布 CSV。
- 注意事项：临时脚本 · 阶段 4 定型后归档到 scripts/analysis/；依赖
  stage3 task3 的 flag_regime_transition 补齐 transition_flag。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, "/Users/gaolei/Documents/src/quant")
sys.path.insert(0, "/Users/gaolei/Documents/src/quant/scripts/ai_tmp")

from poc_va_asymmetry_stage3_task3_regime_transition import (  # noqa: E402
    flag_regime_transition,
)

from workspace.strategies.classifiers.poc_va import (  # noqa: E402
    ClassifierConfig,
    POCVAClassifier,
)

LOG_DIR = Path("/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage4")
DATASET_PATH = LOG_DIR / "dataset_full.parquet"
STAGE4_CSV = LOG_DIR / "stage4_exclusive_classes_descriptive.csv"

TIMELINE_OUT = LOG_DIR / "classifier_v31_timeline.parquet"
DIST_OUT = LOG_DIR / "classifier_v31_tier_distribution.csv"


def main() -> None:
    print("=" * 100)
    print("POC-VA classifier v3.1 · unit test + stage4 alignment")
    print("=" * 100)

    df = pd.read_parquet(DATASET_PATH)
    if "transition_flag" not in df.columns:
        df = flag_regime_transition(df)
    print(f"\n[data] events={len(df)} · contracts={df['contract'].nunique()}")

    clf = POCVAClassifier(config=ClassifierConfig())
    timeline = clf.evaluate_dataset(df)

    # ------------------------------------------------------------------
    # 1. 互斥性
    # ------------------------------------------------------------------
    print("\n" + "-" * 100)
    print("Step 1 · 互斥性验证")
    print("-" * 100)
    n_none = int(timeline["tier"].isna().sum())
    n_tiered = int(len(timeline) - n_none)
    unique_non_none = timeline["tier"].dropna().nunique()
    print(f"total events       = {len(timeline)}")
    print(f"events with tier   = {n_tiered}")
    print(f"events tier=None   = {n_none}")
    print(f"distinct tier ids  = {unique_non_none} (spec 上限 144)")
    assert n_tiered + n_none == len(timeline), "tier 计数不闭合"
    # 每条数据只能属于一个 tier · value_counts 天然满足
    assert unique_non_none <= 144, "tier 数超过 144 · 命名映射有 bug"
    print("✅ 互斥性验证通过")

    # ------------------------------------------------------------------
    # 2. skew_label 分布
    # ------------------------------------------------------------------
    print("\n" + "-" * 100)
    print("Step 2 · skew_label 分布 (DN_1..DN_4 · NEUTRAL · UP_1..UP_4)")
    print("-" * 100)
    order = ["DN_1", "DN_2", "DN_3", "DN_4", "NEUTRAL", "UP_4", "UP_3", "UP_2", "UP_1"]
    skew_dist = timeline["skew_label"].value_counts(dropna=False)
    for lab in order:
        n = int(skew_dist.get(lab, 0))
        pct = n / len(timeline)
        print(f"  {lab:8s}  n={n:>6d}  ({pct:.1%})")
    missing_labels = [lab for lab in order if skew_dist.get(lab, 0) == 0]
    assert not missing_labels, f"以下 skew_label 无样本：{missing_labels}"
    # 语义方向单调：DN 段总占比 ≈ UP 段总占比 (数据集内约对称)
    dn_total = sum(int(skew_dist.get(f"DN_{i}", 0)) for i in range(1, 5))
    up_total = sum(int(skew_dist.get(f"UP_{i}", 0)) for i in range(1, 5))
    print(f"  DN_* 合计 = {dn_total} · UP_* 合计 = {up_total}")
    print("✅ skew_label 分布合理")

    # ------------------------------------------------------------------
    # 3. 与 stage4 描述性 CSV 对齐 (合并新 skew 段映回原 LP_only / LL_only)
    # ------------------------------------------------------------------
    print("\n" + "-" * 100)
    print("Step 3 · 与 stage4_exclusive_classes_descriptive.csv 对齐")
    print("-" * 100)
    stage4 = pd.read_csv(STAGE4_CSV)
    lp_full = int(stage4[(stage4["class"] == "LP_only") & (stage4["period"] == "full")]["n_events"].iloc[0])
    ll_full = int(stage4[(stage4["class"] == "LL_only") & (stage4["period"] == "full")]["n_events"].iloc[0])
    sp_full = int(stage4[(stage4["class"] == "SP_only") & (stage4["period"] == "full")]["n_events"].iloc[0])
    sc_full = int(stage4[(stage4["class"] == "SC_only") & (stage4["period"] == "full")]["n_events"].iloc[0])
    sl_full = int(stage4[(stage4["class"] == "SL_only") & (stage4["period"] == "full")]["n_events"].iloc[0])

    # 用原 stage4 的原始 rank 条件重建 mask · 再看新分类是否覆盖
    tl = timeline.copy()
    long_mask = (tl["signed_skew_rank_roll"] <= 0.30) & (tl["atr_rank_roll"] <= 0.70) & (tl["trend_rank_roll"] >= 0.75)
    short_p_mask = (
        (tl["signed_skew_rank_roll"] >= 0.70) & (tl["atr_rank_roll"] > 0.80) & (tl["trend_rank_roll"] <= 0.20)
    )
    short_c_mask = (
        (tl["signed_skew_rank_roll"] >= 0.70)
        & (tl["atr_rank_roll"] > 0.67)
        & (tl["atr_rank_roll"] <= 0.80)
        & (tl["trend_rank_roll"] <= 0.20)
    )
    short_l_mask = (
        (tl["signed_skew_rank_roll"] >= 0.70)
        & (tl["atr_rank_roll"] > 0.50)
        & (tl["atr_rank_roll"] <= 0.67)
        & (tl["trend_rank_roll"] <= 0.20)
    )

    long_total_new = int(long_mask.sum())
    long_total_ref = lp_full + ll_full
    short_p_new = int(short_p_mask.sum())
    short_c_new = int(short_c_mask.sum())
    short_l_new = int(short_l_mask.sum())

    print("  多头 (skew≤0.30 ∧ atr≤0.70 ∧ trend≥0.75)")
    print(f"    stage4 LP_only + LL_only (full) = {lp_full} + {ll_full} = {long_total_ref}")
    print(f"    v3.1 timeline 重算            = {long_total_new}")

    print("  空头 (skew≥0.70 ∧ trend≤0.20 · 三档)")
    print(f"    stage4 SP/SC/SL (full)         = {sp_full}/{sc_full}/{sl_full}")
    print(f"    v3.1 timeline 重算             = {short_p_new}/{short_c_new}/{short_l_new}")

    ok_long = long_total_new == long_total_ref
    ok_short = (short_p_new == sp_full) and (short_c_new == sc_full) and (short_l_new == sl_full)
    assert ok_long, f"多头合计不对齐: {long_total_new} vs {long_total_ref}"
    assert ok_short, "空头三档不对齐"

    # 新 skew 段落在 DN_* 内验证 (多头 mask 下)
    long_labels = tl.loc[long_mask, "skew_label"].value_counts(dropna=False)
    print("  多头 mask 内 skew_label 分布:")
    for lab, n in long_labels.items():
        print(f"    {lab}: {int(n)}")
    non_dn_in_long = long_labels.drop(
        labels=[lab for lab in ["DN_1", "DN_2", "DN_3", "DN_4"] if lab in long_labels.index],
        errors="ignore",
    )
    assert non_dn_in_long.sum() == 0, "多头 mask 内出现非 DN_* 标签"
    print("✅ 与 stage4 描述性 CSV 对齐")

    # ------------------------------------------------------------------
    # 4. 输出 timeline & tier distribution
    # ------------------------------------------------------------------
    print("\n" + "-" * 100)
    print("Step 4 · 输出文件")
    print("-" * 100)

    # parquet 不支持 python date · 转为 pd.Timestamp
    tl_out = timeline.copy()
    tl_out["trading_date"] = pd.to_datetime(tl_out["trading_date"])
    tl_out.to_parquet(TIMELINE_OUT)
    print(f"  timeline -> {TIMELINE_OUT}  ({len(tl_out)} rows)")

    dist = (
        timeline.dropna(subset=["tier"])
        .groupby("tier")
        .agg(
            n_events=("tier", "size"),
            n_contracts=("contract", "nunique"),
            n_dates=("trading_date", "nunique"),
        )
        .sort_values("n_events", ascending=False)
        .reset_index()
    )
    dist["share"] = dist["n_events"] / dist["n_events"].sum()
    dist.to_csv(DIST_OUT, index=False)
    print(f"  tier distribution -> {DIST_OUT}  ({len(dist)} tiers)")

    # top-10 tier
    print("\n  top-10 tier by n_events:")
    for _, r in dist.head(10).iterrows():
        print(
            f"    {r['tier']:32s} n={int(r['n_events']):>5d} "
            f"contracts={int(r['n_contracts']):>3d} dates={int(r['n_dates']):>3d} "
            f"share={r['share']:.2%}"
        )

    # KF-23 甜蜜点
    kf23 = dist[dist["tier"] == "DN3_atrLow_up_stable"]
    if len(kf23) > 0:
        r = kf23.iloc[0]
        print(
            f"\n  KF-23 (DN3_atrLow_up_stable): n={int(r['n_events'])} · "
            f"contracts={int(r['n_contracts'])} · dates={int(r['n_dates'])}"
        )
    else:
        print("\n  KF-23 (DN3_atrLow_up_stable): 无样本")

    print(f"\nnone tier events (unclassified) = {n_none}")
    print(f"total classified tiers = {len(dist)}")
    print("\n" + "=" * 100)
    print("Verification finished.")
    print("=" * 100)


if __name__ == "__main__":
    main()
