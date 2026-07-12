#!/usr/bin/env python3
"""
快速分布诊断：三维 rank 的分布 + 持有期收益曲线
为收窄分组设计提供数据依据
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workspace"))

import numpy as np
import pandas as pd

DATASET_PATH = Path("project_data/logs/poc_va_asymmetry_stage4/dataset_full.parquet")
OUT_DIR = Path("project_data/ai_tmp")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    print("=" * 70)
    print("三维分布诊断 & 持有期敏感性分析")
    print("=" * 70)

    df = pd.read_parquet(DATASET_PATH).copy()
    df["event_time"] = pd.to_datetime(df["event_time"])
    print(f"\n[0] 样本：{len(df)} rows, {df['contract'].nunique()} contracts")

    # ---------------------------------------------------------------
    # 1. 三维 rank 的分布（按分位数）
    # ---------------------------------------------------------------
    print("\n[1] 三维 rank 分布分位数表")
    cols = ["signed_skew_rank_roll", "atr_rank_roll", "trend_rank_roll"]
    qs = [0.00, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 0.95, 1.00]
    dist_df = pd.DataFrame({q: df[c].quantile(q) for q in qs} for c in cols)
    dist_df.index = cols
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 50)
    print(dist_df.round(3).to_string())

    # ---------------------------------------------------------------
    # 2. 推荐分桶方案（基于分位数，保证每组样本量接近）
    # ---------------------------------------------------------------
    print("\n[2] 推荐收窄分桶（按分位数切，保证组内样本量均衡）")
    for c, tag, short in [
        ("signed_skew_rank_roll", "signed_skew (skew neutral 收窄)", "skew"),
        ("atr_rank_roll", "atr (中高波动 拆细)", "atr"),
        ("trend_rank_roll", "trend (趋势平稳 拆细)", "trend"),
    ]:
        bins_5 = df[c].quantile([0.0, 0.2, 0.4, 0.6, 0.8, 1.0]).values.tolist()
        bins_4 = df[c].quantile([0.0, 0.25, 0.50, 0.75, 1.0]).values.tolist()
        bins_3 = df[c].quantile([0.0, 1/3, 2/3, 1.0]).values.tolist()
        print(f"\n  维度：{tag}")
        print(f"    5 分位桶（20% 每桶）：{[round(x,3) for x in bins_5]}")
        print(f"    4 分位桶（25% 每桶）：{[round(x,3) for x in bins_4]}")
        print(f"    3 分位桶（33% 每桶）：{[round(x,3) for x in bins_3]}")

        # 当前 gatekeeper 使用的范围对应的实际覆盖比例
        if tag.startswith("signed"):
            lo, hi = 0.30, 0.70
        elif tag.startswith("atr"):
            lo, hi = 0.33, 1.00
        else:
            lo, hi = 0.20, 0.80
        cov = ((df[c] >= lo) & (df[c] <= hi)).mean() * 100
        print(f"    原 Gatekeeper 范围 [{lo}, {hi}] 实际覆盖：{cov:.1f}%")

    # ---------------------------------------------------------------
    # 3. 持有期收益敏感性：ret_4h vs ret_8h 在子池内的对比
    # ---------------------------------------------------------------
    print("\n[3] 持有期收益敏感性（原三维子池内）")
    sk_lo, sk_hi = 0.30, 0.70
    at_lo, at_hi = 0.33, 1.00
    tr_lo, tr_hi = 0.20, 0.80
    sub_mask = (
        df["signed_skew_rank_roll"].between(sk_lo, sk_hi)
        & df["atr_rank_roll"].between(at_lo, at_hi, inclusive="right")
        & df["trend_rank_roll"].between(tr_lo, tr_hi)
    )
    sub = df[sub_mask].copy()
    print(f"  子池样本：{len(sub)} ({len(sub)/len(df)*100:.1f}%)")

    # ret 基本统计
    for col, tag in [("ret_4h", "4h"), ("ret_8h", "8h")]:
        bps_col = col + "_bps" if (col + "_bps") in sub.columns else col
        # dataset 中有 ret_8h_bps 但 ret_4h 是原倍数？检查一下
        if col == "ret_4h" and "ret_4h_bps" not in sub.columns:
            # ret_4h 可能是未转 bps 的原始收益
            raw = sub["ret_4h"].dropna()
            if raw.abs().mean() < 0.1:  # 看起来是小数
                vals = raw * 10000
            else:
                vals = raw
        else:
            vals = sub[bps_col].dropna() if bps_col in sub.columns else sub[col].dropna() * 10000
        print(f"\n  --- {tag} 持有期 ---")
        print(f"    均值：{vals.mean():+.2f} bps")
        print(f"    中位数：{vals.median():+.2f} bps")
        print(f"    标准差：{vals.std():.1f} bps")
        print(f"    胜率：{(vals > 0).mean()*100:.1f}%")
        print(f"    非零样本：{vals.notna().sum()}")

    # 4h/8h 比率（同一事件有两者的话）
    has_both = sub["ret_4h"].notna() & sub["ret_8h_bps"].notna()
    if has_both.sum() > 100:
        r4 = sub.loc[has_both, "ret_4h"]
        r8 = sub.loc[has_both, "ret_8h_bps"]
        if r4.abs().mean() < 0.1:
            r4 = r4 * 10000
        ratio = (r4.abs() / r8.abs().replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).dropna()
        print(f"\n  4h/8h 绝对收益比：mean={ratio.mean():.2f}, median={ratio.median():.2f} "
              f"(≈预期 0.5 如果线性衰减，实际说明 alpha 集中在前半段还是后半段)")

    # ---------------------------------------------------------------
    # 4. rank20 触发后不同持有窗口的收益衰减曲线
    # ---------------------------------------------------------------
    print("\n[4] rank20 触发事件在子池内的持有窗口衰减（代理版）")
    # 先算 rank20
    sub = sub.sort_values(["contract", "event_time"]).reset_index(drop=True)
    sub["rank20"] = sub.groupby("contract")["close_t"].transform(
        lambda s: s.rolling(20, min_periods=10).rank(pct=True)
    )
    sub["close_diff"] = sub.groupby("contract")["close_t"].diff(1)

    cond_long = sub["rank20"].notna() & sub["close_diff"].notna() & (sub["rank20"] <= 0.20) & (sub["close_diff"] > 0)
    cond_short = sub["rank20"].notna() & sub["close_diff"].notna() & (sub["rank20"] >= 0.80) & (sub["close_diff"] < 0)
    sub["side"] = np.where(cond_long, "L", np.where(cond_short, "S", None))

    trig = sub[sub["side"].notna()].copy()
    print(f"  触发事件：{len(trig)} (L={cond_long.sum()}, S={cond_short.sum()})")

    if len(trig) > 50:
        # 方向对齐：做多用正收益，做空用负收益
        sign = np.where(trig["side"] == "L", 1.0, -1.0)
        # ret_4h bps 转换
        r4_raw = trig["ret_4h"].values
        if np.abs(np.nanmean(r4_raw)) < 0.1:
            r4 = r4_raw * 10000
        else:
            r4 = r4_raw
        r8 = trig["ret_8h_bps"].values
        pnl4 = sign * r4
        pnl8 = sign * r8
        # 粗略估算 1h, 2h 收益（假设 4h 内线性近似衰减，用 ret_4h 的 1/4 和 1/2，不精确但定性够用）
        pnl1 = sign * r4 / 4.0
        pnl2 = sign * r4 / 2.0

        print(f"\n  不同持有窗口的均值 + 胜率（方向对齐，未扣成本）：")
        for name, arr in [("~1h (线性估)", pnl1), ("~2h (线性估)", pnl2), ("4h", pnl4), ("8h", pnl8)]:
            v = arr[~np.isnan(arr)]
            if len(v) == 0:
                continue
            print(f"    {name:>12s}: mean={np.mean(v):+7.2f} bps, 胜率={(v>0).mean()*100:.1f}%, n={len(v)}")

        # 额外：扣一个粗略的扁平成本后（持有越短成本越高因为换手，但为了同口径统一用 0.05 ATR）
        cost = (trig["daily_atr_10_bps"] * 0.05).values
        print(f"\n  扣统一扁平成本 (≈0.05 ATR 双边) 后的净值：")
        for name, arr in [("~1h", pnl1-cost), ("~2h", pnl2-cost), ("4h", pnl4-cost), ("8h", pnl8-cost)]:
            v = arr[~np.isnan(arr)]
            if len(v) == 0:
                continue
            print(f"    {name:>6s}: mean={np.mean(v):+7.2f} bps, 胜率={(v>0).mean()*100:.1f}%, t={np.mean(v)/np.std(v)*np.sqrt(len(v)):.2f}")

    # ---------------------------------------------------------------
    # 5. 推荐分组矩阵（打印）
    # ---------------------------------------------------------------
    print("\n" + "=" * 70)
    print("[5] 推荐收窄分组扫描方案（基于分布数据）")
    print("=" * 70)
    print("""
  原范围太宽问题：
    - skew [0.3, 0.7] 覆盖 40% 全样本 = 实际 44.6%
    - trend [0.2, 0.8] 覆盖 60% 全样本 = 实际 ~60%
    - atr (0.33, 1.0] 覆盖 67%，但中/高没分开

  建议分组矩阵（3 维度 × 细分档位，做条件组合扫描）：
  """)

    print("  A. skew 维度（symmetry 精确化）：")
    skew_bins = [0.0, 0.30, 0.40, 0.50, 0.60, 0.70, 1.0]
    skew_labels = ["强负倾(Q1-Q30)", "弱负倾(Q30-Q40)", "极度中性(Q40-Q50)",
                   "弱正倾(Q50-Q60)", "强正倾(Q60-Q70)", "强正倾外(Q70+)"]
    for lo, hi, lab in zip(skew_bins[:-1], skew_bins[1:], skew_labels):
        n = ((df["signed_skew_rank_roll"] >= lo) & (df["signed_skew_rank_roll"] < hi)).sum()
        print(f"    [{lo:.2f},{hi:.2f}) → {lab:20s}  样本≈{n:>5d} ({n/len(df)*100:.1f}%)")

    print("\n  B. trend 维度（trend-stable 精确化，核心收窄对象）：")
    trend_bins = [0.0, 0.35, 0.45, 0.55, 0.65, 1.0]
    trend_labels = ["趋势偏弱端(Q0-Q35)", "横盘下界(Q35-Q45)", "核心横盘(Q45-Q55)",
                    "横盘上界(Q55-Q65)", "趋势偏强端(Q65+)"]
    for lo, hi, lab in zip(trend_bins[:-1], trend_bins[1:], trend_labels):
        n = ((df["trend_rank_roll"] >= lo) & (df["trend_rank_roll"] < hi)).sum()
        print(f"    [{lo:.2f},{hi:.2f}) → {lab:20s}  样本≈{n:>5d} ({n/len(df)*100:.1f}%)")

    print("\n  C. atr 维度（中/高波动拆开看）：")
    atr_bins = [0.0, 0.33, 0.50, 0.67, 1.0]
    atr_labels = ["低波动 excl", "中波动(Q33-Q50)", "中高波动(Q50-Q67)", "高波动(Q67+)"]
    for lo, hi, lab in zip(atr_bins[:-1], atr_bins[1:], atr_labels):
        inclusive = "right" if hi == 1.0 else None
        if inclusive == "right":
            mask = (df["atr_rank_roll"] > lo) & (df["atr_rank_roll"] <= hi)
        else:
            mask = (df["atr_rank_roll"] > lo) & (df["atr_rank_roll"] < hi)
        n = mask.sum()
        print(f"    ({lo:.2f},{hi:.2f}] → {lab:20s}  样本≈{n:>5d} ({n/len(df)*100:.1f}%)")

    print("\n  D. 持有期维度：4 档（重点看 2h 和 4h 是否优于 8h）")
    print("    H1 ~ 1h  （ret_4h / 4 线性估，仅参考形状）")
    print("    H2 ~ 2h  （ret_4h / 2 线性估）")
    print("    H4 = 4h  （实际 ret_4h）")
    print("    H8 = 8h  （实际 ret_8h）")

    total_combos = (len(skew_bins)-1) * (len(trend_bins)-1) * (len(atr_bins)-1) * 4
    print(f"\n  总组合数：{len(skew_bins)-1} skew × {len(trend_bins)-1} trend "
          f"× {len(atr_bins)-1} atr × 4 holding = {total_combos} 组")
    print(f"  建议：先跑 atr 只取中高+高（2档）× holding 只取 H2/H4/H8（3档）"
          f" = {4*5*2*3} = {4*5*2*3} 组，再看是否值得拆细 skew/trend")

    # 保存分布表
    dist_df.to_csv(OUT_DIR / "va_sym_3d_rank_distribution.csv")
    print(f"\n[save] 分布表 -> {OUT_DIR / 'va_sym_3d_rank_distribution.csv'}")


if __name__ == "__main__":
    main()
