"""
文件级元信息：
- 创建背景：s2 broad scan 未找到 |IC|>0.03 的候选，但 abs_skew_4h → future_range
  的 IC=-0.022 是所有派生特征中最强的（145 品种一致 55.6%，方向：高|skew|→
  未来 range 小）。本脚本对 top-3 magnitude 候选做深挖：
  (1) tercile 分桶 mean 对比（top vs bottom）
  (2) 分品种 mean_range 稳定性
  (3) 时序分段（8:2 walk-forward）验证方向稳定
- 用途：判断 |skew| 的信息在极端桶（top/bottom 30%）里是否有可用差异。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

CACHE = Path(
    "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/skew_wide/events_with_multi_skew.csv"
)
OUT_DIR = Path(
    "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/skew_wide"
)


def main() -> None:
    df = pd.read_csv(CACHE)
    df["event_time"] = pd.to_datetime(df["event_time"])
    df["abs_skew"] = df["A3_skew"].abs()
    df["abs_skew_4h"] = df["skew_4h"].abs()
    df["abs_skew_8h"] = df["skew_8h"].abs()
    df["abs_skew_24h"] = df["skew_24h"].abs()
    for h in [2, 4, 6, 8, 12]:
        df[f"abs_ret_{h}h"] = df[f"ret_{h}h"].abs()
    df["future_range"] = (
        df[[f"ret_{h}h" for h in [2, 4, 6, 8, 12]]].max(axis=1)
        - df[[f"ret_{h}h" for h in [2, 4, 6, 8, 12]]].min(axis=1)
    )
    df["future_min_ret"] = df[[f"ret_{h}h" for h in [2, 4, 6, 8, 12]]].min(axis=1)

    def per_contract_rank(col: str) -> pd.Series:
        return df.groupby("contract")[col].transform(lambda s: s.rank(pct=True))

    df["r_abs4h"] = per_contract_rank("abs_skew_4h")
    df["r_abs8h"] = per_contract_rank("abs_skew_8h")
    df["r_abs24h"] = per_contract_rank("abs_skew_24h")

    # =========================================================================
    # (1) Tercile 分桶对比 · 三档 mean(future_range) & mean(abs_ret_h)
    # =========================================================================
    print("=== [1] Tercile mean comparison ===")
    for feat_rank in ["r_abs4h", "r_abs8h", "r_abs24h"]:
        print(f"\n--- {feat_rank} ---")
        rows = []
        for tgt in ["future_range", "abs_ret_2h", "abs_ret_4h", "abs_ret_8h", "abs_ret_12h", "future_min_ret"]:
            for tier_name, mask in [
                ("bottom_30", df[feat_rank] <= 0.30),
                ("middle_40", (df[feat_rank] > 0.30) & (df[feat_rank] < 0.70)),
                ("top_30", df[feat_rank] >= 0.70),
            ]:
                y = df.loc[mask, tgt].dropna().to_numpy()
                rows.append({
                    "target": tgt, "bucket": tier_name,
                    "n": len(y), "mean": float(np.mean(y)),
                    "std": float(np.std(y)),
                })
        out = pd.DataFrame(rows)
        # pivot 一下
        piv = out.pivot(index="target", columns="bucket", values="mean")
        piv["top-bottom"] = piv["top_30"] - piv["bottom_30"]
        piv["ratio_top/bot"] = piv["top_30"] / piv["bottom_30"]
        print(piv.round(6).to_string())

    # =========================================================================
    # (2) Per-contract mean(future_range) top vs bottom
    # =========================================================================
    print("\n\n=== [2] Per-contract top-30 vs bottom-30 · future_range mean ===")
    per_c = []
    for c, sub in df.groupby("contract"):
        if len(sub) < 100:
            continue
        t = sub[sub["r_abs4h"] >= 0.70]["future_range"].mean()
        b = sub[sub["r_abs4h"] <= 0.30]["future_range"].mean()
        per_c.append({
            "contract": c, "n_top": (sub["r_abs4h"] >= 0.70).sum(),
            "top_mean": t, "bot_mean": b, "diff": t - b,
        })
    per_c_df = pd.DataFrame(per_c)
    per_c_df.to_csv(OUT_DIR / "s3_per_contract_range.csv", index=False)
    n_neg = (per_c_df["diff"] < 0).sum()
    print(f"contracts where top 30% |skew_4h| → smaller future_range: {n_neg}/{len(per_c_df)} = {n_neg/len(per_c_df):.1%}")
    print(f"mean diff: {per_c_df['diff'].mean():.6f}, median: {per_c_df['diff'].median():.6f}")

    # =========================================================================
    # (3) 8:2 时序切分下 top-30 vs bottom-30 mean 差是否稳定
    # =========================================================================
    print("\n\n=== [3] Walk-forward 8:2 · top-30 vs bottom-30 · future_range diff ===")
    df_sorted = df.sort_values("event_time").reset_index(drop=True)
    split = int(len(df_sorted) * 0.8)
    tr = df_sorted.iloc[:split]
    te = df_sorted.iloc[split:]
    print(f"train {len(tr)}, test {len(te)}")
    for name, sub in [("train", tr), ("test", te)]:
        # 需要在子样本内重新算 rank
        sub = sub.copy()
        sub["r_abs4h_sub"] = sub.groupby("contract")["abs_skew_4h"].transform(
            lambda s: s.rank(pct=True)
        )
        top = sub[sub["r_abs4h_sub"] >= 0.70]["future_range"]
        bot = sub[sub["r_abs4h_sub"] <= 0.30]["future_range"]
        diff = top.mean() - bot.mean()
        print(f"  [{name}] top_mean={top.mean():.6f}, bot_mean={bot.mean():.6f}, diff={diff:.6f}")

    # =========================================================================
    # (4) 换句话：用作 "range 收缩过滤器" —— 高 |skew|_4h 时 |ret|_h 是否显著小？
    #     这暗示"高 |skew| → 未来更低波动"，可能是波动率择时信号
    # =========================================================================
    print("\n\n=== [4] |ret|_h · top-30 vs bottom-30 · ratio ===")
    for h in [2, 4, 6, 8, 12]:
        top = df[df["r_abs4h"] >= 0.70][f"abs_ret_{h}h"].mean()
        bot = df[df["r_abs4h"] <= 0.30][f"abs_ret_{h}h"].mean()
        print(f"  abs_ret_{h}h: top={top:.6f}, bot={bot:.6f}, "
              f"ratio={top/bot:.3f}, diff_bps={(top-bot)*1e4:.2f}")

    # =========================================================================
    # (5) 用作交易信号：low |skew|_4h 时买波动率（等价：进场后 h 内波幅大）？
    #     反过来：high |skew|_4h 时短波 → 可否作为"平静市"过滤器叠加到其他策略？
    # =========================================================================
    print("\n\n=== [5] Bucket range mean(sigmoid check) 每档保留率 ===")
    print("check: bottom_30 |skew|_4h → future_range 差异 vs top_30 · per-symbol")
    per_sym = []
    for sym, sub in df.groupby("symbol"):
        if len(sub) < 200:
            continue
        # 用 per-symbol rank
        sub = sub.copy()
        sub["r_local"] = sub.groupby("contract")["abs_skew_4h"].transform(
            lambda s: s.rank(pct=True)
        )
        top = sub[sub["r_local"] >= 0.70]["future_range"].mean()
        bot = sub[sub["r_local"] <= 0.30]["future_range"].mean()
        per_sym.append({"symbol": sym, "top": top, "bot": bot, "diff": top - bot})
    per_sym_df = pd.DataFrame(per_sym)
    n_shrink = (per_sym_df["diff"] < 0).sum()
    print(f"symbols with top < bot (即|skew|高时range小): {n_shrink}/{len(per_sym_df)} = {n_shrink/len(per_sym_df):.1%}")
    print(f"mean diff = {per_sym_df['diff'].mean():.6f}, median = {per_sym_df['diff'].median():.6f}")


if __name__ == "__main__":
    main()
