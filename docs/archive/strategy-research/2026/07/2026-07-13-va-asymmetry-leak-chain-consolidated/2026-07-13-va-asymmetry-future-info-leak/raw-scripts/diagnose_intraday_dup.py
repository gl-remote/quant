#!/usr/bin/env python3
"""
文件级元信息：
- 场景：用户怀疑研究侧日内多信号（重复）导致 980 笔虚高，策略应当日 1 笔。
- 作用：统计两侧 (contract, entry_date) 日度入场笔数分布，对研究侧日内重复做
  tier/方向拆解，并对研究侧日度去重后重新计算信号覆盖率。
- 输入：compare-r-e 目录下已落盘的 research_trades.parquet、engine_paired_trades.parquet
- 输出：日度笔数分布、日内重复样本、去重后真实覆盖率
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[4]
OUT_DIR = REPO / "docs/workbench/va-asymmetry-composite/outputs/compare-r-e"
DMAP = {1: "L", -1: "S"}


def block(t):
    print()
    print("=" * 100)
    print(f"  {t}")
    print("=" * 100)


def daily_dist(df: pd.DataFrame, name: str, contract_col="contract", date_col="_entry_date",
                entry_ts="entry_bar", tier_col="tier", dir_col="direction") -> pd.DataFrame:
    t = df.copy()
    if date_col not in t.columns:
        t[date_col] = pd.to_datetime(t[entry_ts]).dt.date
    d = t.groupby([contract_col, date_col], as_index=False).agg(
        n=(contract_col, "size"),
        tiers=(tier_col, lambda s: "|".join(sorted(s.astype(str).unique()))),
        directions=(dir_col, lambda s: "|".join(sorted(s.astype(float).map(DMAP).fillna("?").unique()))),
        first_entry=(entry_ts, "min"),
    ).sort_values(["n", contract_col], ascending=[False, True])
    print(f"\n  {name} · 日度入场笔数分布：")
    print(f"  {'笔数/天':>8}{'合约-日 数量':>14}{'占合约日%':>12}{'占总交易笔%':>16}")
    total_cd = int(d.shape[0])
    total_trades = int(df.shape[0])
    for cnt, grp in d.groupby("n"):
        cd_n = int(grp.shape[0])
        tr_n = int(grp["n"].sum())
        print(f"  {cnt:>8}{cd_n:>14,}{cd_n/total_cd*100:>11.1f}%{tr_n/total_trades*100:>15.1f}%")
    print(f"  {'Σ':>8}{total_cd:>14,}{100:>11.1f}%{100:>15.1f}%  (总交易笔={total_trades:,})")
    return d


def dedup_first_bar(df: pd.DataFrame, date_col="_entry_date", entry_ts="entry_bar") -> pd.DataFrame:
    """日内重复 → 仅保留当日首个入场时间戳的第一笔（不做 tier 选择）。"""
    t = df.copy()
    if date_col not in t.columns:
        t[date_col] = pd.to_datetime(t[entry_ts]).dt.date
    return t.sort_values(entry_ts).groupby(["contract", date_col], as_index=False).head(1)


def main() -> None:
    r = pd.read_parquet(OUT_DIR / "research_trades.parquet")
    e = pd.read_parquet(OUT_DIR / "engine_paired_trades.parquet")

    # 工程侧 direction 是 int(1/-1)，研究侧是 float(1.0/-1.0)，统一显示
    r["_entry_date"] = pd.to_datetime(r["entry_bar"]).dt.date
    e["_entry_date"] = pd.to_datetime(e["entry_bar"]).dt.date

    block("A. 研究侧 vs 工程侧 · (合约, 入场日) 入场笔数分布")
    rd = daily_dist(r, "研究侧(R)")
    ed = daily_dist(e, "工程侧(E)")

    block("B. 研究侧日内重复样本（n≥2 的合约-日，按笔数降序 Top 50）")
    dup = rd[rd["n"] >= 2].copy()
    dup["n_tiers"] = dup["tiers"].str.count(r"\|") + 1
    dup["n_dirs"] = dup["directions"].str.count(r"\|") + 1
    print(f"  研究侧 n≥2 共 {dup.shape[0]:,} 个合约日，涉及 {int(dup['n'].sum()):,} 笔交易"
          f"（占 R 总笔 {int(dup['n'].sum())}/{int(r.shape[0])} = "
          f"{int(dup['n'].sum())/int(r.shape[0])*100:.1f}%）")
    print(f"  其中同日多方向的合约日占: {(dup['n_dirs']>=2).sum()}/{dup.shape[0]} "
          f"= {(dup['n_dirs']>=2).mean()*100:.1f}%")
    print(f"  其中同日多 tier  的合约日占: {(dup['n_tiers']>=2).sum()}/{dup.shape[0]} "
          f"= {(dup['n_tiers']>=2).mean()*100:.1f}%")
    cols_show = ["contract", "_entry_date" if "_entry_date" in rd.columns else list(rd.columns)[1],
                 "n", "n_tiers", "n_dirs", "tiers", "directions"]
    col_rename = {list(rd.columns)[1]: "_entry_date"}
    dup_top = dup.rename(columns=col_rename).head(50)
    with pd.option_context("display.width", 200, "display.max_colwidth", 80, "display.max_columns", 15):
        print(dup_top.to_string(index=False))

    block("C. 研究侧日内重复的 tier 组合 Top-20（多 tier 同日命中的模式）")
    multi_tier = dup[dup["n_tiers"] >= 2]["tiers"].value_counts().head(20)
    if len(multi_tier):
        print(f"  {'Tier组合':<55}{'合约日数':>12}")
        print("  " + "-" * 70)
        for k, v in multi_tier.items():
            print(f"  {k:<55}{int(v):>12,}")
    else:
        print("  无多 tier 样本。")

    block("D. 研究侧日内重复的 方向组合（同日开多笔且方向冲突）")
    cross_dir = dup[dup["n_dirs"] >= 2]["directions"].value_counts()
    if len(cross_dir):
        print(f"  {'方向组合':<20}{'合约日数':>12}")
        print("  " + "-" * 34)
        for k, v in cross_dir.items():
            print(f"  {k:<20}{int(v):>12,}")
    else:
        print("  无多方向样本（所有重复入场同向）。")

    block("E. 去重后真实信号规模 vs 覆盖率（日内仅保留当日首笔入场）")
    r_dedup = dedup_first_bar(r)
    e_dedup = dedup_first_bar(e)
    print(f"  R 原始入场笔数             = {len(r):>7,}")
    print(f"  R 去重后入场笔数(日-合约)  = {len(r_dedup):>7,}  ← 减少 {len(r)-len(r_dedup):,} 笔"
          f" ({(len(r)-len(r_dedup))/len(r)*100:.1f}%)")
    print(f"  E 原始入场笔数             = {len(e):>7,}")
    print(f"  E 去重后入场笔数(日-合约)  = {len(e_dedup):>7,}")
    # 注意 E/FIFO 配对后其实已经保证 1 合约日至多 1 open/1 close（除非日间平了又开）
    # 所以 E 的去重基本不掉笔。
    # 真实覆盖率：E 去重 / R 去重
    coverage_real = len(e_dedup) / max(len(r_dedup), 1) * 100
    coverage_raw = len(e) / max(len(r), 1) * 100
    print()
    print(f"  原始  E/R 入场覆盖率 = {coverage_raw:>6.2f}%  ({len(e)}/{len(r)})")
    print(f"  去重后 E/R 入场覆盖率 = {coverage_real:>6.2f}%  ({len(e_dedup)}/{len(r_dedup)})")

    # 额外：R 的 980 笔里，如果允许"每天每合约最多 1 笔"，那理论 R 是 r_dedup.shape[0]
    # 我们要回答：研究侧多出来的 968 笔（R 相对 E 的缺口 + E-only 420）有多少是日内重复？
    gap_raw = int(len(r) - len(e))
    gap_after_repeat_removed = int(len(r_dedup) - len(e))
    repeat_contribution_to_gap = max(0, gap_raw - gap_after_repeat_removed)
    print()
    print(f"  R 原始 − E 原始 入场笔数差 = {gap_raw:+,} 笔 (R多)")
    print(f"  R 去重 − E 原始 入场笔数差 = {gap_after_repeat_removed:+,} 笔")
    print(f"  ⇒ 研究侧多出来的笔数中，日内重复贡献了 {repeat_contribution_to_gap:,} / {max(gap_raw,1):,} 笔"
          f" = {repeat_contribution_to_gap/max(gap_raw,1)*100:.1f}%")


if __name__ == "__main__":
    main()
