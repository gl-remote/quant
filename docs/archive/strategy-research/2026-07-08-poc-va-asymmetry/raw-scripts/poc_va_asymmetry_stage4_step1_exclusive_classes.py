"""
阶段 4 · Step 1 · 互斥分类器 v3.0 · 描述性统计

目标：把阶段 3 的 5 主线 × 稳定/转换 = 10 tier 拆成 10 个互斥类别 · 再报告
描述性统计。

互斥定义（方案 γ · 从 5 主线嵌套拆成互斥）：

多头（skew ≤ 0.30 ∧ atr ≤ 0.70 ∧ trend ≥ 0.75）:
  LP_only:  skew ∈ [0, 0.10]                (原 LP)
  LL_only:  skew ∈ (0.10, 0.30]             (原 LL \ LP)

空头（skew ≥ 0.70 ∧ trend ≤ 0.20）:
  SP_only:  atr > 0.80                       (原 SP)
  SC_only:  atr ∈ (0.67, 0.80]               (原 SC \ SP)
  SL_only:  atr ∈ (0.50, 0.67]               (原 SL \ SC)

× 稳定/转换 = 10 互斥类别 + 未分类

输出：
- stage4_exclusive_classes_descriptive.csv
- 终端表：每类的 n / mean / hit / 独立日 / 主导品种 / 品种数
- 验证：∑ 各类 n = 原 LL_all + SL_all（互斥性检验）
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "/Users/gaolei/Documents/src/quant/scripts/ai_tmp")
from poc_va_asymmetry_stage4_data_full import prepare_dataset_full  # noqa: E402
from poc_va_asymmetry_stage3_task3_regime_transition import flag_regime_transition  # noqa: E402

LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage4"
)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 互斥类别定义
CLASSES = [
    # (类别名, 方向, skew_low, skew_high, atr_low, atr_high, trend_low, trend_high, ret_col)
    ("LP_only", "long",  0.00, 0.10,  0.00, 0.70,  0.75, 1.01, "ret_8h_bps"),
    ("LL_only", "long",  0.10, 0.30,  0.00, 0.70,  0.75, 1.01, "ret_8h_bps"),
    ("SP_only", "short", 0.70, 1.01,  0.80, 1.01,  0.00, 0.20, "short_pnl_4h_bps"),
    ("SC_only", "short", 0.70, 1.01,  0.67, 0.80,  0.00, 0.20, "short_pnl_4h_bps"),
    ("SL_only", "short", 0.70, 1.01,  0.50, 0.67,  0.00, 0.20, "short_pnl_4h_bps"),
]


def make_class_mask(df, sk_lo, sk_hi, at_lo, at_hi, tr_lo, tr_hi, direction):
    """
    skew: [sk_lo, sk_hi]                  -- 左闭右开 (最后一个用 <= 1.01 涵盖 1.0)
    atr:  (at_lo, at_hi] · 但对 LP/LL 用 [0, at_hi]  -- 因为下界是自然 0
    trend: [tr_lo, tr_hi]

    实现时用严格区间：LP_only 的 skew ∈ [0, 0.10] · LL_only ∈ (0.10, 0.30]
    """
    skew = df["signed_skew_rank_roll"]
    atr = df["atr_rank_roll"]
    trend = df["trend_rank_roll"]

    # skew 区间处理：多头（sk_lo=0 或 0.10）· 空头（sk_lo=0.70）
    # 关键 · 让类别互斥：LP_only 用 ≤ 0.10 · LL_only 用 > 0.10 且 ≤ 0.30
    if direction == "long":
        if sk_lo == 0.00:  # LP_only
            m_skew = skew <= sk_hi
        else:  # LL_only
            m_skew = (skew > sk_lo) & (skew <= sk_hi)
    else:  # short
        if at_lo == 0.80:  # SP_only · atr > 0.80
            m_skew = skew >= sk_lo
        else:  # SC_only / SL_only
            m_skew = skew >= sk_lo

    # atr 区间处理
    if direction == "long":
        m_atr = atr <= at_hi
    else:
        # 空头 · 用严格 > lo 且 ≤ hi 让 SP/SC/SL 互斥
        if at_lo == 0.80:  # SP_only · atr > 0.80
            m_atr = atr > at_lo
        elif at_lo == 0.67:  # SC_only · atr ∈ (0.67, 0.80]
            m_atr = (atr > at_lo) & (atr <= at_hi)
        elif at_lo == 0.50:  # SL_only · atr ∈ (0.50, 0.67]
            m_atr = (atr > at_lo) & (atr <= at_hi)
        else:
            m_atr = atr > at_lo

    # trend 区间处理
    if direction == "long":
        m_trend = trend >= tr_lo
    else:
        m_trend = trend <= tr_hi

    return m_skew & m_atr & m_trend


def analyze_class(df, name, mask, ret_col):
    """对一个互斥类别 · 分 stable / trans · 输出描述性统计."""
    sub = df[mask].dropna(subset=[ret_col, "transition_flag"]).copy()
    sub["event_date"] = pd.to_datetime(sub["event_time"]).dt.date

    rows = []
    for tag, seg in [
        ("full", sub),
        ("stable", sub[~sub["transition_flag"]]),
        ("trans", sub[sub["transition_flag"]]),
    ]:
        n = len(seg)
        if n == 0:
            rows.append({
                "class": name, "period": tag,
                "n_events": 0, "n_indep_days": 0, "n_symbols": 0,
                "mean_bps": np.nan, "hit_rate": np.nan, "payoff": np.nan,
                "top_symbol": "", "top_symbol_share": np.nan,
                "top3_symbols": "",
                "eligible_step2": False,
            })
            continue

        ret = seg[ret_col]
        wins = ret[ret > 0]
        losses = ret[ret < 0]
        payoff = (wins.mean() / abs(losses.mean())) if len(losses) > 0 and len(wins) > 0 else np.nan

        n_indep = seg["event_date"].nunique()

        sym_counts = seg["contract"].value_counts()
        top_sym = sym_counts.index[0] if len(sym_counts) > 0 else ""
        top_share = sym_counts.iloc[0] / n if n > 0 else np.nan
        top3 = ",".join(sym_counts.head(3).index.tolist())

        rows.append({
            "class": name, "period": tag,
            "n_events": n,
            "n_indep_days": n_indep,
            "n_symbols": seg["contract"].nunique(),
            "mean_bps": ret.mean(),
            "hit_rate": (ret > 0).mean(),
            "payoff": payoff,
            "top_symbol": top_sym,
            "top_symbol_share": top_share,
            "top3_symbols": top3,
            "eligible_step2": (n >= 15) and (n_indep >= 5),
        })
    return rows


def verify_mutual_exclusive(df, classes):
    """检查互斥性 · 每个 event 至多属于 1 个类别."""
    hit_matrix = pd.DataFrame(index=df.index)
    for name, direction, sk_lo, sk_hi, at_lo, at_hi, tr_lo, tr_hi, _ in classes:
        hit_matrix[name] = make_class_mask(
            df, sk_lo, sk_hi, at_lo, at_hi, tr_lo, tr_hi, direction
        )

    hits_per_event = hit_matrix.sum(axis=1)
    max_hits = hits_per_event.max()
    n_multi = (hits_per_event > 1).sum()

    return {
        "max_hits_per_event": int(max_hits),
        "n_multi_hit_events": int(n_multi),
        "n_total_events": len(df),
        "n_class_hits_total": int(hit_matrix.sum().sum()),
    }


def main():
    print("=" * 100)
    print("阶段 4 · Step 1 · 互斥分类器 v3.0 · 描述性统计")
    print("=" * 100)

    df = prepare_dataset_full()
    df = flag_regime_transition(df)
    print(f"\n数据规模：{len(df)} events · {df['contract'].nunique()} 品种")

    # ================================
    # 1. 验证互斥性
    # ================================
    print("\n" + "─" * 100)
    print("Step 1a · 互斥性验证")
    print("─" * 100)
    ver = verify_mutual_exclusive(df, CLASSES)
    print(f"事件总数：{ver['n_total_events']}")
    print(f"各类命中总数：{ver['n_class_hits_total']}")
    print(f"最大命中数（应=1 表示严格互斥）：{ver['max_hits_per_event']}")
    print(f"多命中事件数（应=0）：{ver['n_multi_hit_events']}")

    if ver["max_hits_per_event"] > 1:
        print("⚠️  警告：存在多命中事件 · 互斥定义有 bug！")
    else:
        print("✅ 严格互斥 · 每个 event 至多属于 1 个类别")

    # ================================
    # 2. 描述性统计
    # ================================
    print("\n" + "─" * 100)
    print("Step 1b · 每类描述性统计（含 stable / trans 拆分）")
    print("─" * 100)

    all_rows = []
    for name, direction, sk_lo, sk_hi, at_lo, at_hi, tr_lo, tr_hi, ret_col in CLASSES:
        mask = make_class_mask(df, sk_lo, sk_hi, at_lo, at_hi, tr_lo, tr_hi, direction)
        rows = analyze_class(df, name, mask, ret_col)
        all_rows.extend(rows)

    out_df = pd.DataFrame(all_rows)
    out_df.to_csv(LOG_DIR / "stage4_exclusive_classes_descriptive.csv", index=False)

    # 主表输出
    print(f"\n{'类别':10s} {'期别':7s} {'n':>5s} {'独立日':>6s} {'品种':>4s} "
          f"{'mean':>8s} {'hit':>6s} {'payoff':>7s} "
          f"{'top3':>25s} {'≥Step2':>8s}")
    print("-" * 110)
    for _, r in out_df.iterrows():
        if r["n_events"] == 0:
            print(f"{r['class']:10s} {r['period']:7s} {'0':>5s} {'0':>6s} {'0':>4s} "
                  f"{'-':>8s} {'-':>6s} {'-':>7s} {'':>25s} {'-':>8s}")
            continue
        mean = f"{r['mean_bps']:+.1f}"
        hit = f"{r['hit_rate']:.1%}"
        payoff = f"{r['payoff']:.2f}" if not np.isnan(r['payoff']) else "-"
        eligible = "✅" if r["eligible_step2"] else "❌"
        print(f"{r['class']:10s} {r['period']:7s} "
              f"{int(r['n_events']):>5d} {int(r['n_indep_days']):>6d} {int(r['n_symbols']):>4d} "
              f"{mean:>8s} {hit:>6s} {payoff:>7s} "
              f"{r['top3_symbols']:>25s} {eligible:>8s}")

    # ================================
    # 3. 汇总：几类通过 Step 2 门槛
    # ================================
    print("\n" + "=" * 100)
    print("Step 1c · Step 2 门槛（n≥15 ∧ n_indep_days≥5）")
    print("=" * 100)
    eligible_df = out_df[out_df["eligible_step2"]]
    non_eligible_df = out_df[~out_df["eligible_step2"] & (out_df["n_events"] > 0)]

    print(f"\n✅ 通过门槛可进 Step 2 严格验证的类别（{len(eligible_df)} 个）：")
    for _, r in eligible_df.iterrows():
        print(f"  {r['class']}·{r['period']:7s} · n={int(r['n_events']):>4d}"
              f" · mean {r['mean_bps']:+.1f} · hit {r['hit_rate']:.1%}")

    print(f"\n❌ 未通过门槛的类别（{len(non_eligible_df)} 个 · n<15 或 n_indep_days<5）：")
    for _, r in non_eligible_df.iterrows():
        print(f"  {r['class']}·{r['period']:7s} · n={int(r['n_events']):>4d}"
              f" · n_indep_days={int(r['n_indep_days']):>3d}")

    empty_df = out_df[out_df["n_events"] == 0]
    if len(empty_df) > 0:
        print(f"\n⚠️  0 事件类别（{len(empty_df)} 个）：")
        for _, r in empty_df.iterrows():
            print(f"  {r['class']}·{r['period']}")

    # ================================
    # 4. 与阶段 3 tier 对比（sanity check）
    # ================================
    print("\n" + "=" * 100)
    print("Step 1d · 与阶段 3 tier 数量对照")
    print("=" * 100)
    # 阶段 3 · LL_all n=? · 应等于 LP_only + LL_only
    print("\n多头对照（互斥总和 vs 原 LL_all）：")
    lp_full = out_df[(out_df["class"] == "LP_only") & (out_df["period"] == "full")]["n_events"].iloc[0]
    ll_full = out_df[(out_df["class"] == "LL_only") & (out_df["period"] == "full")]["n_events"].iloc[0]
    print(f"  LP_only(full) + LL_only(full) = {lp_full} + {ll_full} = {lp_full + ll_full}")
    print(f"  参考 · 阶段 3 LL_all n=471（LP=142 + LL_extended=329）")

    print("\n空头对照（互斥总和 vs 原 SL_all）：")
    sp_full = out_df[(out_df["class"] == "SP_only") & (out_df["period"] == "full")]["n_events"].iloc[0]
    sc_full = out_df[(out_df["class"] == "SC_only") & (out_df["period"] == "full")]["n_events"].iloc[0]
    sl_full = out_df[(out_df["class"] == "SL_only") & (out_df["period"] == "full")]["n_events"].iloc[0]
    print(f"  SP_only(full) + SC_only(full) + SL_only(full) = {sp_full} + {sc_full} + {sl_full} = {sp_full + sc_full + sl_full}")
    print(f"  参考 · 阶段 3 SL_all（含 SC 和 SP）")

    # ================================
    # 5. 关键判断：LL_only 减去 LP 后还剩多少 alpha
    # ================================
    print("\n" + "=" * 100)
    print("Step 1e · 关键诊断：LL_only 独立 alpha 是否仍在？")
    print("=" * 100)
    for period in ["full", "stable", "trans"]:
        lp = out_df[(out_df["class"] == "LP_only") & (out_df["period"] == period)]
        ll = out_df[(out_df["class"] == "LL_only") & (out_df["period"] == period)]
        if len(lp) == 0 or len(ll) == 0 or lp["n_events"].iloc[0] == 0 or ll["n_events"].iloc[0] == 0:
            continue
        lp_mean = lp["mean_bps"].iloc[0]
        ll_mean = ll["mean_bps"].iloc[0]
        print(f"  {period}: LP_only mean = {lp_mean:+.1f} · LL_only mean = {ll_mean:+.1f} "
              f"· LL/LP 比 {ll_mean/lp_mean:.2f}"
              if lp_mean != 0 else f"  {period}: LP_only mean = {lp_mean:+.1f} · LL_only mean = {ll_mean:+.1f}")

    print("\n空头三档独立 alpha 分布：")
    for period in ["full", "stable", "trans"]:
        sp = out_df[(out_df["class"] == "SP_only") & (out_df["period"] == period)]
        sc = out_df[(out_df["class"] == "SC_only") & (out_df["period"] == period)]
        sl = out_df[(out_df["class"] == "SL_only") & (out_df["period"] == period)]
        if len(sp) == 0 or sp["n_events"].iloc[0] == 0:
            continue
        print(f"  {period}: SP_only {sp['mean_bps'].iloc[0]:+.1f} (n={int(sp['n_events'].iloc[0])}) "
              f"· SC_only {sc['mean_bps'].iloc[0]:+.1f} (n={int(sc['n_events'].iloc[0])}) "
              f"· SL_only {sl['mean_bps'].iloc[0]:+.1f} (n={int(sl['n_events'].iloc[0])})")

    print(f"\n输出：{LOG_DIR / 'stage4_exclusive_classes_descriptive.csv'}")


if __name__ == "__main__":
    main()
