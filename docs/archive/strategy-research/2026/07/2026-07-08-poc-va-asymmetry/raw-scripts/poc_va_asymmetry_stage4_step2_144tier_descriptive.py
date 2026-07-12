"""
文件级元信息：
- 创建背景：experiment-plan v9 §4.3 · 阶段 4 · Step 2 · 144 tier 描述性扫描
- 用途：把 skew 4 段 × ATR 3 档 × trend 3 档 × 多空方向 × (stable/trans) = 144 tier
  完整拆分 · 输出每 tier 的 n / mean / hit / std / 品种分布 · 识别可进 Step 3
  严格验证的候选甜蜜点 · 找出需要 Step 4 数据回补的关键格子。
- 注意事项：
  * skew rank 单位 = per-contract（KF-22）· 由 prepare_dataset_full 提供
  * 严格互斥 · 边界规则见 SEG_* 定义
  * 中间 skew (0.30, 0.60) 属"未分类" · 不算 tier
  * Bonferroni family 冻结为 144 · 本脚本不做严格判决 · 只做描述性
  * 平稳期 trend (0.20, 0.75) 是 v9 新增探索维度
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

# ================================
# 三维分段定义（严格互斥）
# ================================
# 多头 skew 段（KF-23 §13）· 左开右闭 · 段1 特殊 · 用 [0, 0.09]
LONG_SKEW_SEGS = [
    ("L1", 0.00, 0.09, "left_closed"),   # 段1: [0.00, 0.09]
    ("L2", 0.09, 0.19, "left_open"),     # 段2: (0.09, 0.19]
    ("L3", 0.19, 0.25, "left_open"),     # 段3: (0.19, 0.25]  KF-23 甜蜜点
    ("L4", 0.25, 0.30, "left_open"),     # 段4: (0.25, 0.30]
]

# 空头 skew 段（KF-23 §13）· 段1 特殊 · 用 [0.91, 1.00]
SHORT_SKEW_SEGS = [
    ("S1", 0.91, 1.00, "right_closed"),  # 段1: [0.91, 1.00]
    ("S2", 0.81, 0.91, "left_open"),     # 段2: (0.81, 0.91]
    ("S3", 0.70, 0.81, "left_open"),     # 段3: (0.70, 0.81]
    ("S4", 0.60, 0.70, "left_open"),     # 段4: (0.60, 0.70]
]

# ATR 3 档
ATR_TIERS = [
    ("Alow",  0.00, 0.33, "left_closed"),  # 低: [0, 0.33]
    ("Amid",  0.33, 0.67, "both_open"),    # 中: (0.33, 0.67)
    ("Ahigh", 0.67, 1.01, "left_closed"),  # 高: [0.67, 1]
]

# Trend 3 档
TREND_TIERS = [
    ("Tdn",   0.00, 0.20, "left_closed"),  # 跌: [0, 0.20]
    ("Tflat", 0.20, 0.75, "both_open"),    # 平: (0.20, 0.75)
    ("Tup",   0.75, 1.01, "left_closed"),  # 涨: [0.75, 1]
]


def _range_mask(series: pd.Series, lo: float, hi: float, edge: str) -> pd.Series:
    """按边界策略生成区间掩码."""
    if edge == "left_closed":     # [lo, hi]
        return (series >= lo) & (series <= hi)
    if edge == "left_open":       # (lo, hi]
        return (series > lo) & (series <= hi)
    if edge == "both_open":       # (lo, hi)
        return (series > lo) & (series < hi)
    if edge == "right_closed":    # [lo, hi]  · 语义同 left_closed · 保留标签
        return (series >= lo) & (series <= hi)
    raise ValueError(f"unknown edge type: {edge}")


def build_tiers() -> list[dict]:
    """展开成 4 × 3 × 3 × 2 = 72 tier per direction · 合计 144 tier."""
    tiers = []
    for direction, skew_segs, ret_col in [
        ("long",  LONG_SKEW_SEGS,  "ret_8h_bps"),
        ("short", SHORT_SKEW_SEGS, "short_pnl_4h_bps"),
    ]:
        for sk_name, sk_lo, sk_hi, sk_edge in skew_segs:
            for at_name, at_lo, at_hi, at_edge in ATR_TIERS:
                for tr_name, tr_lo, tr_hi, tr_edge in TREND_TIERS:
                    tiers.append({
                        "tier_id": f"{sk_name}_{at_name}_{tr_name}",
                        "direction": direction,
                        "ret_col": ret_col,
                        "sk_lo": sk_lo, "sk_hi": sk_hi, "sk_edge": sk_edge,
                        "at_lo": at_lo, "at_hi": at_hi, "at_edge": at_edge,
                        "tr_lo": tr_lo, "tr_hi": tr_hi, "tr_edge": tr_edge,
                    })
    return tiers


def make_tier_mask(df: pd.DataFrame, tier: dict) -> pd.Series:
    """按 tier 定义生成三维互斥掩码."""
    m_skew  = _range_mask(df["signed_skew_rank_roll"], tier["sk_lo"], tier["sk_hi"], tier["sk_edge"])
    m_atr   = _range_mask(df["atr_rank_roll"],         tier["at_lo"], tier["at_hi"], tier["at_edge"])
    m_trend = _range_mask(df["trend_rank_roll"],       tier["tr_lo"], tier["tr_hi"], tier["tr_edge"])
    return m_skew & m_atr & m_trend


def verify_mutual_exclusive(df: pd.DataFrame, tiers: list[dict]) -> dict:
    """互斥性检查：同方向下每个 event 至多命中 1 个 tier."""
    long_hits = np.zeros(len(df), dtype=int)
    short_hits = np.zeros(len(df), dtype=int)
    for t in tiers:
        m = make_tier_mask(df, t).values.astype(int)
        if t["direction"] == "long":
            long_hits += m
        else:
            short_hits += m
    return {
        "long_max_hits": int(long_hits.max()),
        "long_multi_hit_events": int((long_hits > 1).sum()),
        "long_covered_events": int((long_hits > 0).sum()),
        "short_max_hits": int(short_hits.max()),
        "short_multi_hit_events": int((short_hits > 1).sum()),
        "short_covered_events": int((short_hits > 0).sum()),
        "n_total_events": len(df),
    }


def analyze_tier(df: pd.DataFrame, tier: dict) -> list[dict]:
    """对一个 tier · 分 full / stable / trans · 输出描述性统计."""
    mask = make_tier_mask(df, tier)
    ret_col = tier["ret_col"]
    sub = df[mask].dropna(subset=[ret_col, "transition_flag"]).copy()
    sub["event_date"] = pd.to_datetime(sub["event_time"]).dt.date

    rows = []
    for period, seg in [
        ("full",   sub),
        ("stable", sub[~sub["transition_flag"]]),
        ("trans",  sub[sub["transition_flag"]]),
    ]:
        n = len(seg)
        base = {
            "tier_id": tier["tier_id"],
            "direction": tier["direction"],
            "period": period,
            "sk_lo": tier["sk_lo"], "sk_hi": tier["sk_hi"],
            "at_lo": tier["at_lo"], "at_hi": tier["at_hi"],
            "tr_lo": tier["tr_lo"], "tr_hi": tier["tr_hi"],
        }
        if n == 0:
            base.update({
                "n_events": 0, "n_indep_days": 0, "n_symbols": 0,
                "mean_bps": np.nan, "hit_rate": np.nan, "std_bps": np.nan,
                "payoff": np.nan,
                "ir_single": np.nan,
                "top_symbol": "", "top_symbol_share": np.nan,
                "top3_symbols": "",
                "eligible_step3": False,
            })
            rows.append(base)
            continue

        ret = seg[ret_col]
        wins = ret[ret > 0]
        losses = ret[ret < 0]
        payoff = (wins.mean() / abs(losses.mean())) if (len(losses) > 0 and len(wins) > 0) else np.nan

        n_indep = seg["event_date"].nunique()
        sym_counts = seg["contract"].value_counts()
        top_sym = sym_counts.index[0] if len(sym_counts) > 0 else ""
        top_share = sym_counts.iloc[0] / n if n > 0 else np.nan
        top3 = ",".join(sym_counts.head(3).index.tolist())

        std = ret.std()
        ir_single = ret.mean() / std if std > 0 else np.nan

        base.update({
            "n_events": n,
            "n_indep_days": n_indep,
            "n_symbols": seg["contract"].nunique(),
            "mean_bps": ret.mean(),
            "hit_rate": (ret > 0).mean(),
            "std_bps": std,
            "payoff": payoff,
            "ir_single": ir_single,
            "top_symbol": top_sym,
            "top_symbol_share": top_share,
            "top3_symbols": top3,
            "eligible_step3": (n >= 15) and (n_indep >= 5),
        })
        rows.append(base)
    return rows


def print_summary_table(out_df: pd.DataFrame, period: str, direction: str,
                        top_n: int = 20) -> None:
    """按 period+direction 过滤 · 按 mean_bps 排序 · 只打印非空 tier."""
    sub = out_df[
        (out_df["period"] == period)
        & (out_df["direction"] == direction)
        & (out_df["n_events"] > 0)
    ].sort_values("mean_bps", ascending=(direction == "short_reverse"))
    # 多头/空头 · mean 越正越好（空头已经用 short_pnl · 正即赚）
    sub = sub.sort_values("mean_bps", ascending=False)
    print(f"\n[{direction.upper()} · {period}] top {top_n} tier (按 mean 降序)")
    print(f"{'tier_id':>16s} {'n':>5s} {'d':>4s} {'sym':>4s} "
          f"{'mean':>8s} {'hit':>6s} {'ir':>6s} {'pay':>5s} "
          f"{'top':>15s} {'▶Step3':>7s}")
    print("-" * 90)
    for _, r in sub.head(top_n).iterrows():
        mean = f"{r['mean_bps']:+.1f}"
        hit = f"{r['hit_rate']:.1%}"
        ir = f"{r['ir_single']:+.2f}" if not np.isnan(r['ir_single']) else "-"
        pay = f"{r['payoff']:.2f}" if not np.isnan(r['payoff']) else "-"
        eligible = "✅" if r["eligible_step3"] else "❌"
        print(f"{r['tier_id']:>16s} {int(r['n_events']):>5d} "
              f"{int(r['n_indep_days']):>4d} {int(r['n_symbols']):>4d} "
              f"{mean:>8s} {hit:>6s} {ir:>6s} {pay:>5s} "
              f"{r['top_symbol']:>15s} {eligible:>7s}")


def main():
    print("=" * 100)
    print("阶段 4 · Step 2 · 144 tier 描述性扫描（experiment-plan v9 §4.3）")
    print("=" * 100)

    # ================================
    # 1. 数据准备
    # ================================
    df = prepare_dataset_full()
    df = flag_regime_transition(df)
    print(f"\n数据规模：{len(df)} events · {df['contract'].nunique()} 合约 · "
          f"{pd.to_datetime(df['event_time']).min().date()} → "
          f"{pd.to_datetime(df['event_time']).max().date()}")

    tiers = build_tiers()
    print(f"tier 总数：{len(tiers)} = 4 skew段 × 3 ATR × 3 trend × 2 方向")

    # ================================
    # 2. 互斥性验证
    # ================================
    print("\n" + "─" * 100)
    print("Step 2a · 互斥性验证")
    print("─" * 100)
    ver = verify_mutual_exclusive(df, tiers)
    print(f"多头方向 · 覆盖 {ver['long_covered_events']} events / "
          f"最大命中 {ver['long_max_hits']} / 多命中 {ver['long_multi_hit_events']}")
    print(f"空头方向 · 覆盖 {ver['short_covered_events']} events / "
          f"最大命中 {ver['short_max_hits']} / 多命中 {ver['short_multi_hit_events']}")
    if ver["long_max_hits"] <= 1 and ver["short_max_hits"] <= 1:
        print("✅ 同方向内严格互斥")
    else:
        print("⚠️  存在同方向多命中 · 边界定义有 bug！")

    # ================================
    # 3. 每 tier 描述性统计
    # ================================
    print("\n" + "─" * 100)
    print("Step 2b · 遍历 144 tier × 3 period（full/stable/trans）= 432 行统计")
    print("─" * 100)
    all_rows: list[dict] = []
    for i, t in enumerate(tiers, 1):
        all_rows.extend(analyze_tier(df, t))
        if i % 24 == 0:
            print(f"  [{i:>3}/{len(tiers)}] done")

    out_df = pd.DataFrame(all_rows)
    out_path = LOG_DIR / "stage4_step2_144tier_descriptive.csv"
    out_df.to_csv(out_path, index=False)
    print(f"\n输出：{out_path}")

    # ================================
    # 4. 汇总表 · 分 direction × period
    # ================================
    print("\n" + "=" * 100)
    print("Step 2c · 各方向×期别的 top tier 排行")
    print("=" * 100)
    for direction in ["long", "short"]:
        for period in ["full", "stable", "trans"]:
            print_summary_table(out_df, period, direction, top_n=15)

    # ================================
    # 5. Step 3 候选清单
    # ================================
    print("\n" + "=" * 100)
    print("Step 2d · Step 3 严格验证候选（eligible=n≥15 ∧ n_indep≥5）")
    print("=" * 100)
    eligible = out_df[out_df["eligible_step3"] & (out_df["mean_bps"] > 0)]
    print(f"\n通过描述性门槛 · 且 mean_bps>0 的 (tier, period) 组合数：{len(eligible)}")

    # 分方向 × 期别统计
    stats = eligible.groupby(["direction", "period"]).agg(
        n=("tier_id", "count"),
        avg_n=("n_events", "mean"),
        avg_mean=("mean_bps", "mean"),
    ).round(1)
    print("\n各方向×期别通过组合数：")
    print(stats)

    # ================================
    # 6. 需要数据回补的关键 tier
    # ================================
    print("\n" + "=" * 100)
    print("Step 2e · 值得关注但样本不足（描述性 mean>=30 bps · 但 n<15 或 indep<5）")
    print("=" * 100)
    weak_sample = out_df[
        (out_df["period"] == "full")
        & (out_df["n_events"] > 0)
        & (~out_df["eligible_step3"])
        & (out_df["mean_bps"] >= 30)
    ].sort_values("mean_bps", ascending=False)
    print(f"\n候选 {len(weak_sample)} 个（Step 4 数据回补优先目标）")
    for _, r in weak_sample.head(20).iterrows():
        print(f"  {r['tier_id']:>16s} {r['direction']:>5s} "
              f"n={int(r['n_events']):>3d} indep={int(r['n_indep_days']):>3d} "
              f"mean={r['mean_bps']:+.1f} top={r['top_symbol']}")

    # ================================
    # 7. 平稳期（Tflat）新维度专项
    # ================================
    print("\n" + "=" * 100)
    print("Step 2f · 平稳期（Tflat）新维度专项（v9 新增探索）")
    print("=" * 100)
    flat = out_df[
        (out_df["tier_id"].str.contains("_Tflat"))
        & (out_df["period"] == "full")
        & (out_df["n_events"] > 0)
    ].sort_values("mean_bps", ascending=False)
    print(f"\n平稳期 tier 数（full · 非空）：{len(flat)}")
    print(f"{'tier_id':>16s} {'dir':>5s} {'n':>5s} {'indep':>5s} "
          f"{'mean':>8s} {'hit':>6s} {'ir':>6s} {'▶':>3s}")
    print("-" * 65)
    for _, r in flat.head(20).iterrows():
        mean = f"{r['mean_bps']:+.1f}"
        hit = f"{r['hit_rate']:.1%}"
        ir = f"{r['ir_single']:+.2f}" if not np.isnan(r['ir_single']) else "-"
        eligible = "✅" if r["eligible_step3"] else "❌"
        print(f"{r['tier_id']:>16s} {r['direction']:>5s} "
              f"{int(r['n_events']):>5d} {int(r['n_indep_days']):>5d} "
              f"{mean:>8s} {hit:>6s} {ir:>6s} {eligible:>3s}")

    # ================================
    # 8. 交叉 trend 专项：涨段做空 / 跌段做多
    # ================================
    print("\n" + "=" * 100)
    print("Step 2g · 交叉 trend 专项（涨段做空 · 跌段做多 · v9 新探索）")
    print("=" * 100)
    long_dn = out_df[
        (out_df["direction"] == "long")
        & (out_df["tier_id"].str.endswith("_Tdn"))
        & (out_df["period"] == "full")
        & (out_df["n_events"] > 0)
    ].sort_values("mean_bps", ascending=False)
    short_up = out_df[
        (out_df["direction"] == "short")
        & (out_df["tier_id"].str.endswith("_Tup"))
        & (out_df["period"] == "full")
        & (out_df["n_events"] > 0)
    ].sort_values("mean_bps", ascending=False)
    print(f"\n跌段做多（long · _Tdn）· {len(long_dn)} 个非空 tier：")
    for _, r in long_dn.head(10).iterrows():
        print(f"  {r['tier_id']:>16s} n={int(r['n_events']):>4d} "
              f"mean={r['mean_bps']:+.1f} hit={r['hit_rate']:.1%}")
    print(f"\n涨段做空（short · _Tup）· {len(short_up)} 个非空 tier：")
    for _, r in short_up.head(10).iterrows():
        print(f"  {r['tier_id']:>16s} n={int(r['n_events']):>4d} "
              f"mean={r['mean_bps']:+.1f} hit={r['hit_rate']:.1%}")

    print("\n" + "=" * 100)
    print("Step 2 描述性扫描完成 · 下一步：Step 3 · 对 eligible tier 跑 4 硬门槛")
    print(f"  · Bonferroni family = 144 · 阈值 p < {0.05/144:.4f}")
    print(f"  · 输出文件：{out_path}")
    print("=" * 100)


if __name__ == "__main__":
    main()
