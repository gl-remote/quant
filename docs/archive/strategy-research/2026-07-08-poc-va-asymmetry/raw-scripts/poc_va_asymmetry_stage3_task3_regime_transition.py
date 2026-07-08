"""
文件级元信息：
- 创建背景：阶段 3 任务 3 · 极端制度切换（regime transition）下的信号衰减。
  验证 atr_rank_roll20d 在 ATR 快速切换时的滞后是否影响主线信号。
- 用途：
    (1) 识别 regime transition 日：atr_rank_roll 跨越 33% 或 67% 阈值的日子
    (2) 标注每个事件为 "regime_stable" 或 "regime_transition"（近 N 天有切换）
    (3) 对比 4 大主线在两类日子的 mean / hit / CI
    (4) 判定：转换日信号衰减是否 <20%
- 注意事项：
    - Transition window：定义前 3 交易日内是否发生 rank 跨越
    - 若信号衰减严重 · 标注"regime 转换日不触发"作为使用边界
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "/Users/gaolei/Documents/src/quant/scripts/ai_tmp")
from poc_va_asymmetry_stage2_grid_search import (  # noqa: E402
    prepare_dataset, cluster_bootstrap,
)

LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage3"
)


TRANSITION_WINDOW_DAYS = 3  # 判定"近几日"发生切换


def flag_regime_transition(df, window=TRANSITION_WINDOW_DAYS):
    """
    对每个事件标注：
    - is_transition: 前 window 交易日内 · atr rank 跨越了 33% 或 67% 阈值
    """
    # 先按合约按天取 atr_rank_roll · 判定当日是否跨越阈值
    daily = df.drop_duplicates(["contract", "event_date"]).sort_values(
        ["contract", "event_date"])
    daily["atr_bucket"] = daily["atr_rank_roll"].apply(
        lambda r: "L" if r <= 0.33 else ("H" if r >= 0.67 else "M"))
    daily["prev_bucket"] = daily.groupby("contract")["atr_bucket"].shift(1)
    daily["is_crossover"] = (daily["atr_bucket"] != daily["prev_bucket"]) & \
                             daily["prev_bucket"].notna()

    # 对每天判定：前 window 交易日内是否有 crossover
    def flag_window(g):
        g = g.sort_values("event_date").copy()
        g["transition_flag"] = False
        cross_dates = g[g["is_crossover"]]["event_date"].tolist()
        cross_dates = pd.to_datetime(cross_dates)
        dates = pd.to_datetime(g["event_date"])
        for cd in cross_dates:
            mask = (dates >= cd) & (dates <= cd + pd.Timedelta(days=window))
            g.loc[mask, "transition_flag"] = True
        return g[["event_date", "transition_flag"]]

    seg_list = []
    for c, g in daily.groupby("contract"):
        r = flag_window(g)
        r["contract"] = c
        seg_list.append(r)
    flag_seg = pd.concat(seg_list, ignore_index=True)
    df = df.merge(flag_seg, on=["contract", "event_date"], how="left")
    return df


def analyze(df, name, mask, ret_col):
    print(f"\n{'='*90}")
    print(f"【{name}】")
    print("=" * 90)

    sub = df[mask].dropna(subset=[ret_col, "transition_flag"])
    stable = sub[~sub["transition_flag"]]
    trans = sub[sub["transition_flag"]]

    print(f"\n总触发: n={len(sub)}")
    print(f"  regime 稳定日: n={len(stable)} ({len(stable)/max(1,len(sub)):.1%})")
    print(f"  regime 转换日: n={len(trans)} ({len(trans)/max(1,len(sub)):.1%})")

    if len(stable) < 20 or len(trans) < 10:
        print("  样本不足 · 跳过 CI")
        return None

    r_stable = cluster_bootstrap(stable, ret_col)
    r_trans = cluster_bootstrap(trans, ret_col)
    hit_s = (stable[ret_col] > 0).mean()
    hit_t = (trans[ret_col] > 0).mean()

    print(f"\n{'状态':15s} {'n':>5s} {'品种':>4s} {'mean':>8s} {'hit':>7s} "
          f"{'CI下':>8s} {'CI上':>8s} {'p':>7s} 判决")
    for lbl, r, hit in [("regime 稳定", r_stable, hit_s), ("regime 转换", r_trans, hit_t)]:
        pass_ = "✅" if r["ci_lo"] > 0 else "❌"
        print(f"{lbl:15s} {r['n_events']:>5d} {r['n_contracts']:>4d} "
              f"{r['real_mean']:>+8.2f} {hit:>7.1%} "
              f"{r['ci_lo']:>+8.2f} {r['ci_hi']:>+8.2f} "
              f"{r['p_two']:>7.4f}  {pass_}")

    diff = r_stable["real_mean"] - r_trans["real_mean"]
    diff_pct = diff / r_stable["real_mean"] * 100 if r_stable["real_mean"] != 0 else 0
    print(f"\nmean 差: 稳定 - 转换 = {diff:+.2f} bps · 衰减 {diff_pct:+.1f}%")
    if abs(diff_pct) <= 20:
        judge = "✅ 衰减 <20% · 转换日可保留触发"
    elif diff_pct > 20:
        judge = "⚠️ 转换日显著衰减 · 建议标注使用边界"
    else:
        judge = "❗ 转换日反而更强 · 需进一步分析"
    print(f"判定: {judge}")

    return {
        "signal": name,
        "n_stable": r_stable["n_events"],
        "n_trans": r_trans["n_events"],
        "mean_stable": r_stable["real_mean"],
        "mean_trans": r_trans["real_mean"],
        "hit_stable": hit_s,
        "hit_trans": hit_t,
        "ci_lo_stable": r_stable["ci_lo"],
        "ci_lo_trans": r_trans["ci_lo"],
        "p_stable": r_stable["p_two"],
        "p_trans": r_trans["p_two"],
        "diff_pct": diff_pct,
    }


def main():
    print("=" * 100)
    print(f"阶段 3 任务 3 · 极端制度切换（regime transition）信号衰减")
    print(f"transition window = 前 {TRANSITION_WINDOW_DAYS} 交易日发生 rank 跨越")
    print("=" * 100)

    print("\n[准备数据] ...")
    df = prepare_dataset()
    print(f"  总事件: {len(df)} · 合约: {df['contract'].nunique()}")

    print("\n[标注 regime transition] ...")
    df = flag_regime_transition(df)
    n_trans = df["transition_flag"].sum()
    n_stable = (~df["transition_flag"]).sum()
    print(f"  转换期事件: {n_trans} ({n_trans/len(df):.1%})")
    print(f"  稳定期事件: {n_stable} ({n_stable/len(df):.1%})")

    signals = [
        ("多头首选（skew≤0.10·atr≤0.70·trend≥0.75·8h）",
         "long", 0.10, 0.70, 0.75),
        ("多头宽松（skew≤0.30·atr≤0.70·trend≥0.75·8h）",
         "long", 0.30, 0.70, 0.75),
        ("空头首选（skew≥0.70·atr>0.80·trend≤0.20·4h）",
         "short", 0.70, 0.80, 0.20),
        ("空头宽松（skew≥0.70·atr>0.50·trend≤0.20·4h）",
         "short", 0.70, 0.50, 0.20),
    ]

    all_rows = []
    for name, direction, sk, at, tr in signals:
        if direction == "long":
            mask = ((df["signed_skew_rank_roll"] <= sk) &
                    (df["atr_rank_roll"] <= at) &
                    (df["trend_rank_roll"] >= tr))
            ret_col = "ret_8h_bps"
        else:
            mask = ((df["signed_skew_rank_roll"] >= sk) &
                    (df["atr_rank_roll"] > at) &
                    (df["trend_rank_roll"] <= tr))
            ret_col = "short_pnl_4h_bps"
        r = analyze(df, name, mask, ret_col)
        if r:
            all_rows.append(r)

    # 汇总
    print("\n" + "=" * 100)
    print("汇总 · 4 大主线 · regime 稳定 vs 转换")
    print("=" * 100)
    print(f"\n{'主线':50s} {'稳定 mean':>10s} {'转换 mean':>10s} {'衰减%':>8s} 判决")
    n_pass = 0
    for r in all_rows:
        short_name = r["signal"].split("（")[0]
        judge = "✅" if abs(r["diff_pct"]) <= 20 else ("⚠️" if r["diff_pct"] > 20 else "❗")
        print(f"{short_name:50s} {r['mean_stable']:>+10.2f} {r['mean_trans']:>+10.2f} "
              f"{r['diff_pct']:>+8.1f} {judge}")
        if abs(r["diff_pct"]) <= 20:
            n_pass += 1

    print(f"\n通过（衰减 <20%）: {n_pass}/{len(all_rows)}")
    if n_pass == len(all_rows):
        print("✅ 任务 3 判据全过 · regime 转换日可保留触发")
    elif n_pass >= len(all_rows) // 2 + 1:
        print("⚠️ 部分主线转换日衰减 · 需分主线标注使用边界")
    else:
        print("❗ 大多数主线转换日衰减严重 · 应标注'regime 转换日不触发'")

    pd.DataFrame(all_rows).to_csv(LOG_DIR / "task3_regime_transition.csv", index=False)
    print(f"\n输出：{LOG_DIR / 'task3_regime_transition.csv'}")


if __name__ == "__main__":
    main()
