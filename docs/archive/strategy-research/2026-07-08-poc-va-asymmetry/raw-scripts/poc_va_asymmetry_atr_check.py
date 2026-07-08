"""
文件级元信息：
- 创建背景：需要判断 A3_skew 是不是 ATR 的近亲。做两个检验：
    A · A3_skew 与前一日 ATR 的 Spearman 相关系数
    B · (A3_skew_extreme, ATR_extreme) 2×2 交叉分组，看哪部分贡献增量 alpha
- 用途：读取 extended_long_events.csv → 补算每个事件的 entry_atr（用事件时刻
  之前 12 根 5m bar 的 True Range 平均），然后：
    (1) Spearman(A3_skew, ATR) 全局 + 分合约
    (2) 分位 2x2 交叉：|skew| top 20% vs mid  ×  ATR top 20% vs mid
        看每格的 mean_ret_8h · n
    (3) 判读：A3_skew 是否 ≈ ATR
- 注意事项：需要重新读 5m bar 算 ATR（每合约独立）；ret_8h 单位 bps
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

CSV_DIR = Path("/Users/gaolei/Documents/src/quant/project_data/market_data/csv")
LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage1"
)
EVENTS_PATH = LOG_DIR / "extended_long_events.csv"

ATR_LOOKBACK_5M = 12  # 12 根 5m bar ≈ 1 小时 ATR


def add_atr(events: pd.DataFrame) -> pd.DataFrame:
    """给每个事件补算 entry_atr（事件时刻之前 12 根 5m bar 的 TR 平均）。"""
    events = events.copy()
    events["event_time"] = pd.to_datetime(events["event_time"])
    events["entry_atr"] = np.nan

    for sym, g in events.groupby("contract"):
        try:
            bars = pd.read_csv(CSV_DIR / f"{sym}.tqsdk.5m.csv")
        except FileNotFoundError:
            continue
        bars["datetime"] = pd.to_datetime(bars["datetime"])
        bars = bars.sort_values("datetime").reset_index(drop=True)
        # True Range
        prev_close = bars["close"].shift(1)
        tr = np.maximum.reduce([
            (bars["high"] - bars["low"]).to_numpy(),
            (bars["high"] - prev_close).abs().to_numpy(),
            (bars["low"] - prev_close).abs().to_numpy(),
        ])
        bars["tr"] = tr
        bars["atr"] = bars["tr"].rolling(ATR_LOOKBACK_5M).mean()

        # 用 datetime 精确匹配事件（事件的 close_t 在 bar 的 close 上）
        bars_indexed = bars.set_index("datetime")
        for i, row in g.iterrows():
            t = row["event_time"]
            if t in bars_indexed.index:
                events.at[i, "entry_atr"] = bars_indexed.at[t, "atr"]

    return events


def main() -> None:
    print("加载事件表 + 补算 ATR ...")
    df = pd.read_csv(EVENTS_PATH)
    df = add_atr(df)
    df = df.dropna(subset=["A3_skew", "entry_atr", "ret_8h"])
    print(f"合并后事件数: {len(df)} · 合约数: {df['contract'].nunique()}")

    df["abs_skew"] = df["A3_skew"].abs()
    # 每合约内归一化 ATR 到分位（避免跨合约 ATR 量级差异）
    df["atr_rank"] = df.groupby("contract")["entry_atr"].rank(pct=True)
    df["abs_skew_rank"] = df.groupby("contract")["abs_skew"].rank(pct=True)
    df["signed_skew_rank"] = df.groupby("contract")["A3_skew"].rank(pct=True)
    df["ret_bps"] = df["ret_8h"] * 1e4

    # ========================================================================
    # 检验 A · 相关系数
    # ========================================================================
    print("\n" + "=" * 90)
    print("检验 A · A3_skew ↔ ATR 相关性")
    print("=" * 90)

    print("\n【全 pool】")
    p_abs = stats.spearmanr(df["abs_skew"], df["entry_atr"])
    p_signed = stats.spearmanr(df["A3_skew"], df["entry_atr"])
    print(f"  Spearman(|A3_skew|, ATR) = {p_abs.statistic:+.3f}  p={p_abs.pvalue:.2e}")
    print(f"  Spearman(A3_skew,   ATR) = {p_signed.statistic:+.3f}  p={p_signed.pvalue:.2e}")
    print(f"  分位归一化后:")
    p_abs_r = stats.spearmanr(df["abs_skew_rank"], df["atr_rank"])
    p_sgn_r = stats.spearmanr(df["signed_skew_rank"], df["atr_rank"])
    print(f"  Spearman(|A3_skew|_rank, ATR_rank) = {p_abs_r.statistic:+.3f}")
    print(f"  Spearman(A3_skew_rank,   ATR_rank) = {p_sgn_r.statistic:+.3f}")

    print(f"\n【分合约】")
    print(f"{'contract':16s} {'n':>5s} {'|skew|↔ATR':>12s} {'skew↔ATR':>10s}")
    for c, g in df.groupby("contract"):
        rho1 = stats.spearmanr(g["abs_skew"], g["entry_atr"]).statistic
        rho2 = stats.spearmanr(g["A3_skew"], g["entry_atr"]).statistic
        print(f"{c:16s} {len(g):>5d} {rho1:>+12.3f} {rho2:>+10.3f}")

    # ========================================================================
    # 检验 B · 2×2 交叉分组
    # ========================================================================
    print("\n\n" + "=" * 90)
    print("检验 B · (A3_skew, ATR) 2x2 交叉分组")
    print("=" * 90)

    # DN 侧：signed_skew_rank ≤ 10%  =  skew 极端负（底厚）
    # 非事件对照：signed_skew_rank 在 [0.4, 0.6]（中段）
    print("\n【DN 侧 · signed skew rank】")
    print("  低 = rank ≤ 10% (最负 · 底厚) · 中 = 40%~60% · 高 = ≥ 90% (最正 · 顶厚)")
    print("  ATR: 低 = rank ≤ 20% · 中 = 40%~60% · 高 = ≥ 80%")

    def q_label(rank: float, low: float = 0.20, high: float = 0.80) -> str:
        if rank <= low:
            return "low"
        if rank >= high:
            return "high"
        if 0.40 <= rank <= 0.60:
            return "mid"
        return "other"

    df["skew_grp"] = df["signed_skew_rank"].apply(lambda r: q_label(r, 0.10, 0.90))
    df["atr_grp"] = df["atr_rank"].apply(lambda r: q_label(r, 0.20, 0.80))

    print(f"\n{'skew_grp':10s} × {'atr_grp':8s}  {'n':>6s} {'mean_bps':>10s} "
          f"{'median':>10s} {'hit%':>7s}")
    for sg in ["low", "mid", "high"]:
        for ag in ["low", "mid", "high"]:
            sub = df[(df["skew_grp"] == sg) & (df["atr_grp"] == ag)]
            if len(sub) < 5:
                continue
            r = sub["ret_bps"]
            print(f"{sg:10s}   {ag:8s}  {len(sub):>6d} {r.mean():>+10.2f} "
                  f"{r.median():>+10.2f} {(r>0).mean():>7.1%}")

    # 对照：全 baseline
    r_all = df["ret_bps"]
    print(f"\n{'baseline':10s}   {'all':8s}  {len(r_all):>6d} {r_all.mean():>+10.2f} "
          f"{r_all.median():>+10.2f} {(r_all>0).mean():>7.1%}")

    # ========================================================================
    # 检验 C · 单独 A3_skew vs 单独 ATR vs 二者组合的对未来收益的解释
    # ========================================================================
    print("\n\n" + "=" * 90)
    print("检验 C · 只看单一维度触发")
    print("=" * 90)

    print(f"\n【单独 DN 触发（skew rank ≤ 10%，不看 ATR）】")
    only_dn = df[df["signed_skew_rank"] <= 0.10]
    print(f"  n={len(only_dn)}, mean={only_dn['ret_bps'].mean():+.2f}, "
          f"hit={(only_dn['ret_bps']>0).mean():.1%}")

    print(f"\n【单独 高 ATR 触发（ATR rank ≥ 80%，不看 skew）】")
    only_atr = df[df["atr_rank"] >= 0.80]
    print(f"  n={len(only_atr)}, mean={only_atr['ret_bps'].mean():+.2f}, "
          f"hit={(only_atr['ret_bps']>0).mean():.1%}")

    print(f"\n【组合触发（skew rank ≤ 10% AND ATR rank ≥ 80%）】")
    both = df[(df["signed_skew_rank"] <= 0.10) & (df["atr_rank"] >= 0.80)]
    print(f"  n={len(both)}, mean={both['ret_bps'].mean():+.2f}, "
          f"hit={(both['ret_bps']>0).mean():.1%}")

    print(f"\n【DN AND 低 ATR】")
    low_atr_dn = df[(df["signed_skew_rank"] <= 0.10) & (df["atr_rank"] <= 0.20)]
    print(f"  n={len(low_atr_dn)}, mean={low_atr_dn['ret_bps'].mean():+.2f}, "
          f"hit={(low_atr_dn['ret_bps']>0).mean():.1%}")

    df.to_csv(LOG_DIR / "atr_vs_skew_events.csv", index=False)
    print(f"\nOutput: {LOG_DIR / 'atr_vs_skew_events.csv'}")


if __name__ == "__main__":
    main()
