"""
文件级元信息：
- 创建背景：方案 B · 按 trend 拆 3 表 · cell 数值 = 该 tier 通过的 period 数
- 用途：为 workbench 文档提供数据
- 注意事项：临时脚本
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd

CSV = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage4/stage4_step3_144tier_verification.csv"
)

SKEW_ORDER = ["1", "2", "3", "4"]
ATR_ORDER = ["Alow", "Amid", "Ahigh"]
TREND_ORDER = ["Tup", "Tflat", "Tdn"]
PERIOD_ORDER = ["full", "stable", "trans"]


def parse_tier(tid: str) -> dict:
    parts = tid.split("_")
    return {"seg": parts[0], "atr": parts[1], "trend": parts[2]}


def main():
    df = pd.read_csv(CSV)
    df = df[~df["skipped"].fillna(False)].copy()
    parsed = df["tier_id"].apply(parse_tier).apply(pd.Series)
    df = pd.concat([df, parsed], axis=1)
    df["passed"] = df["grade"].isin(["A", "A-"])

    total_passed = df["passed"].sum()
    print(f"总 (tier,period) 通过数：{int(total_passed)}")

    for trend in TREND_ORDER:
        sub = df[df["trend"] == trend]
        trend_label = {"Tup": "涨段", "Tflat": "平稳", "Tdn": "跌段"}[trend]

        table = pd.DataFrame(
            index=[f"ATR{a[1:]}" for a in ATR_ORDER],
            columns=[f"skew段{s}" for s in SKEW_ORDER],
        )
        detail = pd.DataFrame(
            index=[f"ATR{a[1:]}" for a in ATR_ORDER],
            columns=[f"skew段{s}" for s in SKEW_ORDER],
        )
        for seg_num in SKEW_ORDER:
            for atr_key in ATR_ORDER:
                long_group = sub[(sub["seg"] == f"L{seg_num}") & (sub["atr"] == atr_key)]
                short_group = sub[(sub["seg"] == f"S{seg_num}") & (sub["atr"] == atr_key)]
                n_long_pass = int(long_group["passed"].sum())
                n_short_pass = int(short_group["passed"].sum())
                row = f"ATR{atr_key[1:]}"
                col = f"skew段{seg_num}"
                if n_long_pass == 0 and n_short_pass == 0:
                    table.loc[row, col] = ""
                    detail.loc[row, col] = ""
                else:
                    val = n_long_pass - n_short_pass
                    table.loc[row, col] = val
                    parts = []
                    if n_long_pass > 0:
                        pd_list = long_group[long_group["passed"]]["period"].tolist()
                        max_mean = long_group[long_group["passed"]]["mean_bps"].max()
                        parts.append(f"+L{seg_num} {n_long_pass}p [{','.join(pd_list)}] max_mean={max_mean:+.0f}")
                    if n_short_pass > 0:
                        pd_list = short_group[short_group["passed"]]["period"].tolist()
                        max_mean = short_group[short_group["passed"]]["mean_bps"].max()
                        parts.append(f"-S{seg_num} {n_short_pass}p [{','.join(pd_list)}] max_mean={max_mean:+.0f}")
                    detail.loc[row, col] = " | ".join(parts)

        print("\n" + "=" * 80)
        print(f"表：{trend_label}（trend={trend}）")
        print("=" * 80)
        print("数值 = 多头通过 period 数 - 空头通过 period 数（∈ [-3, +3]）")
        print(table.fillna("").to_string())
        print("\n详细：")
        for r in detail.index:
            for c in detail.columns:
                v = detail.loc[r, c]
                if v:
                    print(f"  {r} × {c}: {v}")


if __name__ == "__main__":
    main()
