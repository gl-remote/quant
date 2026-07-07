"""
文件级元信息：
- 创建背景：§7 拓展探索的三层组合（趋势 × ATR × skew）只有 gross mean，没做
  显著性检验。本脚本对三大候选做 cluster bootstrap 5000 次 CI，验证是否过
  严格统计门槛（CI 排 0 · p<0.05）。
- 用途：读 daily_atr_events.csv（19 合约扩展表，含日线 ATR + 趋势字段）
    候选 1 · 多头主线增强 · DN + 上涨趋势 + 低 ATR_10 · 期望 mean +58
    候选 2 · 空头新线索 A · DN + 平段 + 高 ATR_10 · 期望 mean -43（做空 +43）
    候选 3 · 空头新线索 B · UP + 波动上升 · 期望 mean -16.5（做空 +16.5）
    候选 4 · 单层 · DN + 低 ATR_10（洞察 I 甜蜜点，同层对照）· 期望 +36
- 注意事项：cluster by contract 5000 次；ret 单位 bps；做空场景把 ret 翻符号
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage1"
)
DAILY_PATH = LOG_DIR / "daily_atr_events.csv"

BOOTSTRAP_N = 5000
RNG_SEED = 20260707


def cluster_bootstrap(events: pd.DataFrame, ret_col: str = "ret_bps",
                       n_boot: int = BOOTSTRAP_N, seed: int = RNG_SEED) -> dict:
    rng = np.random.default_rng(seed)
    contracts = events["contract"].unique().tolist()
    per_c = {c: events[events["contract"] == c][ret_col].to_numpy() for c in contracts}
    real_mean = events[ret_col].mean()

    boot_means = np.zeros(n_boot)
    for i in range(n_boot):
        picked = rng.choice(contracts, size=len(contracts), replace=True)
        all_r = np.concatenate([per_c[c] for c in picked])
        boot_means[i] = all_r.mean() if len(all_r) else np.nan
    valid = boot_means[~np.isnan(boot_means)]
    ci_lo = float(np.quantile(valid, 0.025))
    ci_hi = float(np.quantile(valid, 0.975))
    ci_lo_one_sided = float(np.quantile(valid, 0.05))  # 单侧 90% CI 下限
    p_two = 2 * min((valid <= 0).mean(), (valid >= 0).mean())
    p_one_pos = (valid <= 0).mean()  # H0: mean <= 0 的 p 值
    p_one_neg = (valid >= 0).mean()  # H0: mean >= 0 的 p 值
    return {
        "n_events": len(events),
        "n_contracts": len(contracts),
        "real_mean": real_mean,
        "ci_lo_95": ci_lo,
        "ci_hi_95": ci_hi,
        "ci_lo_90_one_sided": ci_lo_one_sided,
        "p_two": p_two,
        "p_one_pos": p_one_pos,  # 用于检验 mean > 0
        "p_one_neg": p_one_neg,  # 用于检验 mean < 0
    }


def report(label: str, mask: pd.Series, df: pd.DataFrame, ret_col: str = "ret_bps",
           short_view: bool = False) -> None:
    """跑 cluster bootstrap 并报告。short_view=True 时报告做空视角 pnl。"""
    sub = df[mask].dropna(subset=[ret_col])
    if len(sub) < 5:
        print(f"\n{label}\n  ⚠️ 样本不足 n={len(sub)}")
        return
    result = cluster_bootstrap(sub, ret_col=ret_col)
    hit_r = (sub[ret_col] > 0).mean()
    print(f"\n【{label}】")
    print(f"  n_events = {result['n_events']} (跨 {result['n_contracts']} 合约)")
    print(f"  raw mean = {result['real_mean']:+.2f} bps · hit(ret>0) = {hit_r:.1%}")
    if short_view:
        # 做空视角：pnl = -ret
        short_stats = cluster_bootstrap(
            sub.assign(short_pnl=-sub[ret_col]), ret_col="short_pnl")
        hit_short = (sub[ret_col] < 0).mean()
        print(f"  做空 pnl mean = {short_stats['real_mean']:+.2f} bps · "
              f"short win rate = {hit_short:.1%}")
        print(f"  做空 95% CI    = [{short_stats['ci_lo_95']:+.2f}, "
              f"{short_stats['ci_hi_95']:+.2f}]")
        print(f"  做空 90% CI 下限（单侧）= {short_stats['ci_lo_90_one_sided']:+.2f}")
        print(f"  做空 p_two = {short_stats['p_two']:.4f}  "
              f"p_one(mean>0) = {short_stats['p_one_pos']:.4f}")
        judge = "✅ 严格排 0" if short_stats['ci_lo_95'] > 0 else (
                "⚠️ 90% 单侧排 0" if short_stats['ci_lo_90_one_sided'] > 0 else "❌ CI 触 0")
        print(f"  判读: {judge}")
    else:
        print(f"  95% CI = [{result['ci_lo_95']:+.2f}, {result['ci_hi_95']:+.2f}]")
        print(f"  90% CI 下限（单侧）= {result['ci_lo_90_one_sided']:+.2f}")
        print(f"  p_two = {result['p_two']:.4f}  p_one(mean>0) = {result['p_one_pos']:.4f}")
        judge = "✅ 严格排 0" if result['ci_lo_95'] > 0 else (
                "⚠️ 90% 单侧排 0" if result['ci_lo_90_one_sided'] > 0 else "❌ CI 触 0")
        print(f"  判读: {judge}")


def main() -> None:
    print("加载 daily_atr_events.csv ...")
    df = pd.read_csv(DAILY_PATH)
    df["ret_bps"] = df["ret_8h"] * 1e4

    # 每合约内 rank
    for col in ["daily_atr_10_bps", "atr_ratio_short_long", "trend_ret_10d"]:
        df[f"{col}_rank"] = df.groupby("contract")[col].rank(pct=True)
    df["signed_skew_rank"] = df.groupby("contract")["A3_skew"].rank(pct=True)

    # skew group
    def q_skew(r: float) -> str:
        if r <= 0.10:
            return "DN"
        if r >= 0.90:
            return "UP"
        return "mid"
    df["skew_grp"] = df["signed_skew_rank"].apply(q_skew)

    # trend group
    def q_trend(r: float) -> str:
        if r <= 0.33:
            return "down"
        if r >= 0.67:
            return "up"
        return "flat"
    df["trend_grp"] = df["trend_ret_10d_rank"].apply(q_trend)

    # ATR_10 low/high split
    def q_atr(r: float) -> str:
        return "low" if r <= 0.5 else "high"
    df["atr10_grp"] = df["daily_atr_10_bps_rank"].apply(q_atr)

    # ATR ratio 变化率
    def q_ratio(r: float) -> str:
        if r >= 0.67:
            return "rising"
        if r <= 0.33:
            return "falling"
        return "stable"
    df["ratio_grp"] = df["atr_ratio_short_long_rank"].apply(q_ratio)

    # ========================================================================
    # 候选 1 · 多头主线增强
    # ========================================================================
    print("\n" + "=" * 90)
    print("候选 1 · 多头主线增强 · DN + 上涨趋势 + 低 ATR_10 (期望 +58 bps)")
    print("=" * 90)
    mask = (df["skew_grp"] == "DN") & (df["trend_grp"] == "up") & (df["atr10_grp"] == "low")
    report("DN + up + low ATR_10", mask, df, short_view=False)

    # ========================================================================
    # 候选 2 · 空头新线索 A · 反转信号
    # ========================================================================
    print("\n\n" + "=" * 90)
    print("候选 2 · 空头新线索 A · DN + 平段 + 高 ATR_10 反向做空 (期望 short +43 bps)")
    print("=" * 90)
    mask = (df["skew_grp"] == "DN") & (df["trend_grp"] == "flat") & (df["atr10_grp"] == "high")
    report("DN + flat + high ATR_10 (做空)", mask, df, short_view=True)

    # ========================================================================
    # 候选 3 · 空头新线索 B · UP + 波动上升做空
    # ========================================================================
    print("\n\n" + "=" * 90)
    print("候选 3 · 空头新线索 B · UP + 波动上升做空 (期望 short +16.5 bps)")
    print("=" * 90)
    mask = (df["skew_grp"] == "UP") & (df["ratio_grp"] == "rising")
    report("UP + rising vol (做空)", mask, df, short_view=True)

    # ========================================================================
    # 候选 4 · 单层对照 · DN + 低 ATR_10
    # ========================================================================
    print("\n\n" + "=" * 90)
    print("候选 4 · 单层对照 · DN + 低 ATR_10 (期望 +36 bps · 洞察 I 甜蜜点)")
    print("=" * 90)
    mask = (df["skew_grp"] == "DN") & (df["atr10_grp"] == "low")
    report("DN + low ATR_10", mask, df, short_view=False)

    # ========================================================================
    # 候选 5 · 多头简化版（无趋势 filter）· DN + 低 ATR_10 + 波动下降
    # ========================================================================
    print("\n\n" + "=" * 90)
    print("候选 5 · 多头简化 · DN + 波动下降 (期望 +25.7 bps · 洞察 §7.3)")
    print("=" * 90)
    mask = (df["skew_grp"] == "DN") & (df["ratio_grp"] == "falling")
    report("DN + falling vol", mask, df, short_view=False)

    print("\n\n" + "=" * 90)
    print("总结")
    print("=" * 90)
    print("  · ✅ 严格排 0    · 95% CI 排 0 · p_two < 0.05 · 阶段 1 完美收尾")
    print("  · ⚠️ 90% 单侧排 0 · 边缘显著 · 阶段 2 需扩样本验证")
    print("  · ❌ CI 触 0    · 描述性证据 · 需要更多样本或换特征")


if __name__ == "__main__":
    main()
