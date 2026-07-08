"""
文件级元信息：
- 创建背景：把 Step 3 FDR 验证结果按 (regime × trend) × (skew × ATR) 聚合成 6 表
- 用途：为 workbench 文档提供数据 · 一次性分析脚本
- 注意事项：临时脚本 · 输出汇总在终端
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

CSV = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage4/stage4_step3_144tier_verification.csv"
)

# tier_id 解析：{L|S}{1..4}_A{low|mid|high}_T{dn|flat|up}
SKEW_ORDER = ["1", "2", "3", "4"]
ATR_ORDER = ["Alow", "Amid", "Ahigh"]
TREND_ORDER = ["Tup", "Tflat", "Tdn"]  # 对应表：涨/平/跌
PERIOD_ORDER = ["stable", "trans"]


def parse_tier(tid: str) -> dict:
    """L3_Amid_Tflat → dict(seg='L3', atr='Amid', trend='Tflat')."""
    parts = tid.split("_")
    return {"seg": parts[0], "atr": parts[1], "trend": parts[2]}


def build_tables(df: pd.DataFrame) -> None:
    """按 (period × trend) 做 6 表 · 每表横轴 skew · 纵轴 ATR · 内容 = 通过数量（多头正/空头负）."""
    df = df[~df["skipped"].fillna(False)].copy()
    parsed = df["tier_id"].apply(parse_tier).apply(pd.Series)
    df = pd.concat([df, parsed], axis=1)

    # 每 cell 的评级："A"/"A-"/"fail"/"skip"
    # 通过 = A 或 A- （硬门槛全过）
    df["passed"] = df["grade"].isin(["A", "A-"])

    # 6 表：period ∈ {stable, trans} × trend ∈ {Tup, Tflat, Tdn}
    for period in PERIOD_ORDER:
        for trend in TREND_ORDER:
            sub = df[(df["period"] == period) & (df["trend"] == trend)]
            # 分方向汇总
            # cell 内容 = long 通过数（正） + short 通过数（负） · 未过留空
            table = pd.DataFrame(
                index=[f"ATR{a}" for a in ["low", "mid", "high"]],
                columns=[f"skew段{s}" for s in SKEW_ORDER],
            )
            detail = pd.DataFrame(
                index=[f"ATR{a}" for a in ["low", "mid", "high"]],
                columns=[f"skew段{s}" for s in SKEW_ORDER],
            )
            for seg_num in SKEW_ORDER:
                for atr_key in ATR_ORDER:
                    atr_short = atr_key.replace("A", "ATR")
                    # 多头：L{seg}
                    long_hit = sub[(sub["seg"] == f"L{seg_num}") & (sub["atr"] == atr_key) & sub["passed"]]
                    short_hit = sub[(sub["seg"] == f"S{seg_num}") & (sub["atr"] == atr_key) & sub["passed"]]
                    row = f"ATR{atr_key[1:]}"
                    col = f"skew段{seg_num}"
                    n_long = len(long_hit)
                    n_short = len(short_hit)
                    val = n_long - n_short
                    if n_long == 0 and n_short == 0:
                        table.loc[row, col] = ""
                        detail.loc[row, col] = ""
                    else:
                        table.loc[row, col] = val
                        # 详细信息：具体 tier 和 mean
                        parts = []
                        for _, r in long_hit.iterrows():
                            g = r["grade"]
                            parts.append(f"+L{seg_num}·{g} mean={r['mean_bps']:+.0f}")
                        for _, r in short_hit.iterrows():
                            g = r["grade"]
                            parts.append(f"-S{seg_num}·{g} mean={r['mean_bps']:+.0f}")
                        detail.loc[row, col] = " | ".join(parts)

            trend_label = {"Tup": "涨段", "Tflat": "平稳", "Tdn": "跌段"}[trend]
            print("\n" + "=" * 80)
            print(f"表：{period} · {trend_label}（trend={trend}）")
            print("=" * 80)
            print("数值 = 多头通过数 - 空头通过数（正=多头 · 负=空头 · 0=中性）")
            print(table.fillna("").to_string())
            print("\n详细：")
            for r in detail.index:
                for c in detail.columns:
                    v = detail.loc[r, c]
                    if v:
                        print(f"  {r} × {c}: {v}")


def main():
    df = pd.read_csv(CSV)
    print(f"加载 {len(df)} 行 · 非 skipped {(~df['skipped'].fillna(False)).sum()}")

    # 概要
    grade_counts = df[~df["skipped"].fillna(False)].groupby("grade").size()
    print("\n评级分布：")
    print(grade_counts)

    build_tables(df)


if __name__ == "__main__":
    main()
