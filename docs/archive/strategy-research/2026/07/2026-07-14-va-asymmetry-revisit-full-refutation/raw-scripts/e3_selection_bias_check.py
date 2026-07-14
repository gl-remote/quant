"""
文件级元信息：
- 创建背景：扩样 145 合约后 L_seg2 alpha 消失（Full Sharpe 0.12），但原 40
  合约版本 Sharpe 1.48。本脚本检验：原 40 合约是否是"事后选取到 alpha 友好
  的子集"造成的假阳性。做法：从 145 合约中随机抽 40 个合约，跑相同管线，
  统计"随机 40 合约"下 L_seg2 Sharpe 分布，看 1.48 是否落在其分布内。
- 用途：判定 c1-c5 报告的 L_seg2 alpha 是"真候选衰减" vs "假阳性挑样"。
- 注意事项：临时研究脚本，产物在 outputs/e3/。
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/scripts")
from h1b_regime_stratified import cluster_bootstrap_mean  # noqa: E402

OUT_DIR = Path(
    "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/e3"
)
OUT_DIR.mkdir(parents=True, exist_ok=True)

EXPAND_EVENTS = Path(
    "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/expand/events_with_tier.csv"
)

# 原 c1 使用的 40 合约（h1_a3_skew_pooled_ic.SYMBOL_POOL 展开）
ORIGINAL_40 = [
    "SHFE.rb2510", "SHFE.rb2601", "SHFE.rb2605",
    "DCE.i2501", "DCE.i2509", "DCE.i2601",
    "SHFE.cu2501", "SHFE.cu2509", "SHFE.cu2601",
    "SHFE.al2501", "SHFE.al2509", "SHFE.al2601",
    "INE.sc2506", "INE.sc2509", "INE.sc2512",
    "CZCE.TA501", "CZCE.TA509", "CZCE.TA601",
    "DCE.m2509", "DCE.m2601", "DCE.m2605",
    "DCE.p2509", "DCE.p2601", "DCE.p2605",
    "CZCE.SR509", "CZCE.SR601", "CZCE.SR605",
    "CZCE.CF509", "CZCE.CF601",
    "DCE.y2509", "DCE.y2601",
    "DCE.c2509", "DCE.c2601", "DCE.c2605",
    "SHFE.hc2510", "SHFE.hc2601",
    "SHFE.ag2509", "SHFE.ag2601",
    "CZCE.RM509", "CZCE.RM601",
]


def performance(pnl: pd.Series, dt: pd.Series) -> tuple[float, float, float, int]:
    df = pd.DataFrame({"pnl": pnl.to_numpy(), "date": pd.to_datetime(dt).dt.date})
    daily = df.groupby("date")["pnl"].sum()
    daily.index = pd.to_datetime(daily.index)
    idx = pd.date_range(daily.index.min(), daily.index.max(), freq="B")
    daily = daily.reindex(idx, fill_value=0.0)
    ann = daily.mean() * 252
    vol = daily.std() * np.sqrt(252)
    sh = ann / vol if vol > 0 else float("nan")
    dd = (daily.cumsum() - daily.cumsum().cummax()).min()
    return float(ann), float(sh), float(dd), len(daily)


def main() -> None:
    df = pd.read_csv(EXPAND_EVENTS)
    df["event_time"] = pd.to_datetime(df["event_time"])
    df["event_date"] = pd.to_datetime(df["event_date"]).dt.date
    l2 = df[df["tier"] == "L_seg2_low_flat"].reset_index(drop=True)
    print(f"L_seg2 events total (145 contracts): {len(l2)}")

    all_contracts = sorted(l2["contract"].unique())
    print(f"L_seg2-hitting contracts: {len(all_contracts)}")

    # 原 40 合约在 L_seg2 中的表现
    orig_l2 = l2[l2["contract"].isin(ORIGINAL_40)]
    print(f"\n=== 原 40 合约 · L_seg2 net 10h ===")
    y = orig_l2["ret_10h"].to_numpy() - orig_l2["cost_rt"].to_numpy()
    mu, lo, hi, p, n = cluster_bootstrap_mean(y, orig_l2["ce_key"].to_numpy())
    ann, sh, dd, days = performance(pd.Series(y), orig_l2["event_time"])
    print(f"  n={n}, mean_net={mu:.6f}, CI=[{lo:.6f},{hi:.6f}], p={p:.3f}")
    print(f"  ann={ann*100:.2f}%, sharpe={sh:.2f}, DD={dd*100:.2f}%")

    # 全 145 合约 · L_seg2
    print(f"\n=== 全 145 合约 · L_seg2 net 10h ===")
    y = l2["ret_10h"].to_numpy() - l2["cost_rt"].to_numpy()
    mu, lo, hi, p, n = cluster_bootstrap_mean(y, l2["ce_key"].to_numpy())
    ann, sh, dd, days = performance(pd.Series(y), l2["event_time"])
    print(f"  n={n}, mean_net={mu:.6f}, CI=[{lo:.6f},{hi:.6f}], p={p:.3f}")
    print(f"  ann={ann*100:.2f}%, sharpe={sh:.2f}, DD={dd*100:.2f}%")

    # 随机 40 合约 × 200 次 → Sharpe 分布
    print(f"\n=== 随机抽 40 合约 · 200 次 · Sharpe 分布 ===")
    rng = np.random.default_rng(20260714)
    sharpes = []
    for i in range(200):
        picked = rng.choice(all_contracts, size=40, replace=False)
        sub = l2[l2["contract"].isin(picked)]
        y = sub["ret_10h"].to_numpy() - sub["cost_rt"].to_numpy()
        if len(y) < 50:
            continue
        _, sh, _, _ = performance(pd.Series(y), sub["event_time"])
        sharpes.append(sh)
    sharpes = np.array(sharpes)
    orig_sh = 1.48  # 报告过的 c5 数字
    orig_actual = performance(
        pd.Series(orig_l2["ret_10h"].to_numpy() - orig_l2["cost_rt"].to_numpy()),
        orig_l2["event_time"],
    )[1]
    print(f"  Random 40-contract Sharpe:")
    print(f"    mean={np.mean(sharpes):.3f}, std={np.std(sharpes):.3f}")
    print(f"    p05={np.percentile(sharpes, 5):.3f}, p50={np.percentile(sharpes, 50):.3f}, "
          f"p95={np.percentile(sharpes, 95):.3f}")
    print(f"  原 40-contract Sharpe (c5 报告 1.48):")
    print(f"    在扩样数据上重算 = {orig_actual:.3f}")
    quantile = float(np.mean(sharpes < orig_actual))
    print(f"  原 40-contract 排名在随机分布的 {quantile*100:.1f}% 分位")

    pd.DataFrame({"sharpe_random_40": sharpes}).to_csv(OUT_DIR / "random_40_sharpes.csv", index=False)

    print(f"\nAll outputs: {OUT_DIR}")


if __name__ == "__main__":
    main()
