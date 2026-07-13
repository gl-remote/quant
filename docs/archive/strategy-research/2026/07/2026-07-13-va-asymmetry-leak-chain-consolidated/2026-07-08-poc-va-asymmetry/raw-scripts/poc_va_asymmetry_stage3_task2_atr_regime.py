"""
文件级元信息：
- 创建背景：阶段 3 任务 2 · 3-way ATR 制度独立 CI。洞察 I 已用 2×2 交叉表
  证明 A3_skew ⊥ ATR · 但未做"低/中/高" 3 档独立 CI 深挖。
- 用途：
    (1) 对 4 大主线剥离 ATR filter · 只保留 skew + trend filter
    (2) 在剥离后的事件集合上按 ATR 3 档（低≤0.33 / 中 0.33-0.67 / 高≥0.67）
        独立算 mean / hit / CI
    (3) 验证假设：多头是否只在低 ATR 有效 · 空头是否只在高 ATR 有效
    (4) 判据：至少 2 大主线的 ATR 制度依赖性明确成立
- 注意事项：
    - 剥离 ATR filter 后要保留其他 filter · 才能对比"同条件下不同 ATR 的表现"
    - 多头 8h · 空头 4h
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
LOG_DIR.mkdir(parents=True, exist_ok=True)


def eval_atr_regime(df, base_mask, ret_col, name):
    """base_mask = skew + trend 条件（不含 ATR）"""
    sub = df[base_mask].dropna(subset=[ret_col])
    print(f"\n【{name}】· 剥离 ATR filter 后 · n={len(sub)}")

    if len(sub) < 30:
        print("  样本太少 · 跳过")
        return None

    # 3 档 ATR
    rows = []
    for regime, atr_mask in [
        ("低 ATR (rank ≤ 0.33)", sub["atr_rank_roll"] <= 0.33),
        ("中 ATR (0.33 - 0.67)", (sub["atr_rank_roll"] > 0.33) & (sub["atr_rank_roll"] < 0.67)),
        ("高 ATR (rank ≥ 0.67)", sub["atr_rank_roll"] >= 0.67),
    ]:
        seg = sub[atr_mask]
        if len(seg) < 20:
            rows.append({"regime": regime, "n": len(seg), "reason": "n<20"})
            continue
        r = cluster_bootstrap(seg, ret_col)
        hit = (seg[ret_col] > 0).mean()
        pass_ = r["ci_lo"] > 0
        rows.append({
            "regime": regime,
            "n": r["n_events"],
            "n_contracts": r["n_contracts"],
            "mean": r["real_mean"],
            "hit": hit,
            "ci_lo": r["ci_lo"],
            "ci_hi": r["ci_hi"],
            "p": r["p_two"],
            "pass": pass_,
        })

    print(f"\n{'ATR 制度':30s} {'n':>5s} {'品种':>4s} {'mean':>8s} {'hit':>7s} "
          f"{'CI下':>8s} {'CI上':>8s} {'p':>7s} 判决")
    for r in rows:
        if "reason" in r:
            print(f"{r['regime']:30s} {r['n']:>5d}   -- {r['reason']}")
            continue
        judge = "✅" if r["pass"] else "❌"
        print(f"{r['regime']:30s} {r['n']:>5d} {r['n_contracts']:>4d} "
              f"{r['mean']:>+8.2f} {r['hit']:>7.1%} "
              f"{r['ci_lo']:>+8.2f} {r['ci_hi']:>+8.2f} "
              f"{r['p']:>7.4f}  {judge}")

    return rows


def main():
    print("=" * 100)
    print("阶段 3 任务 2 · 3-way ATR 制度独立 CI")
    print("=" * 100)

    print("\n[准备数据] ...")
    df = prepare_dataset()
    print(f"  总事件: {len(df)} · 合约: {df['contract'].nunique()}")

    # 剥离 ATR filter 的四大主线基础条件
    signals = [
        ("多头首选（skew≤0.10 · trend≥0.75）",
         ((df["signed_skew_rank_roll"] <= 0.10) & (df["trend_rank_roll"] >= 0.75)),
         "ret_8h_bps", "long"),
        ("多头宽松（skew≤0.30 · trend≥0.75）",
         ((df["signed_skew_rank_roll"] <= 0.30) & (df["trend_rank_roll"] >= 0.75)),
         "ret_8h_bps", "long"),
        ("空头首选（skew≥0.70 · trend≤0.20）",
         ((df["signed_skew_rank_roll"] >= 0.70) & (df["trend_rank_roll"] <= 0.20)),
         "short_pnl_4h_bps", "short"),
        ("空头宽松（skew≥0.70 · trend≤0.20）",
         ((df["signed_skew_rank_roll"] >= 0.70) & (df["trend_rank_roll"] <= 0.20)),
         "short_pnl_4h_bps", "short"),
    ]

    all_rows = []
    for name, mask, ret_col, direction in signals:
        results = eval_atr_regime(df, mask, ret_col, name)
        if results:
            for r in results:
                if "reason" in r:
                    continue
                r["signal"] = name
                r["direction"] = direction
                all_rows.append(r)

    # 汇总判据
    print("\n" + "=" * 100)
    print("汇总 · ATR 制度依赖性判据")
    print("=" * 100)

    summary_df = pd.DataFrame(all_rows)
    summary_df.to_csv(LOG_DIR / "task2_atr_regime.csv", index=False)

    print(f"\n{'主线':40s} {'低 ATR mean':>12s} {'中 ATR mean':>12s} {'高 ATR mean':>12s}")
    signals_check = {}
    for name, mask, ret_col, direction in signals:
        short = name.split("（")[0]
        row = summary_df[summary_df["signal"] == name]
        if len(row) == 0:
            continue
        low = row[row["regime"].str.contains("低")]["mean"].values
        mid = row[row["regime"].str.contains("中")]["mean"].values
        high = row[row["regime"].str.contains("高")]["mean"].values
        low_v = low[0] if len(low) else np.nan
        mid_v = mid[0] if len(mid) else np.nan
        high_v = high[0] if len(high) else np.nan
        print(f"{short:40s} {low_v:>+12.2f} {mid_v:>+12.2f} {high_v:>+12.2f}")
        signals_check[short] = {
            "low": low_v, "mid": mid_v, "high": high_v, "direction": direction
        }

    print("\n判据检验：")
    print("  多头假设：低 ATR 显著强于高 ATR")
    print("  空头假设：高 ATR 显著强于低 ATR")

    n_pass = 0
    for short, v in signals_check.items():
        if v["direction"] == "long":
            passed = (v["low"] > 0) and (v["low"] > v["high"] + 5)
            reason = f"低={v['low']:+.1f} vs 高={v['high']:+.1f}"
        else:
            passed = (v["high"] > 0) and (v["high"] > v["low"] + 5)
            reason = f"高={v['high']:+.1f} vs 低={v['low']:+.1f}"
        mark = "✅" if passed else "❌"
        print(f"  {short:40s} · {reason}  {mark}")
        if passed:
            n_pass += 1

    print(f"\n通过：{n_pass}/{len(signals_check)}")
    print(f"任务 2 判据（至少 2 大主线制度依赖性成立）：{'✅ 通过' if n_pass >= 2 else '❌ 未过'}")

    print(f"\n输出：{LOG_DIR / 'task2_atr_regime.csv'}")


if __name__ == "__main__":
    main()
