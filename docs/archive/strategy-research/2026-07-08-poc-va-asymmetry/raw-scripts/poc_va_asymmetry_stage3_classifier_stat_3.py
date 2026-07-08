"""
文件级元信息：
- 阶段 3 分类器严格性验证 · 脚本 3（E+F+G）
  E · 反事实基准（随机触发 vs 分类器）
  F · 8×8 组合独立性矩阵（Jaccard + Lift）
  G · Time-in-market 分析（触发覆盖率）
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
from poc_va_asymmetry_stage3_task3_regime_transition import (  # noqa: E402
    flag_regime_transition,
)

LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage3"
)


def get_mask(df, direction, sk, at, tr):
    if direction == "long":
        return ((df["signed_skew_rank_roll"] <= sk) &
                (df["atr_rank_roll"] <= at) &
                (df["trend_rank_roll"] >= tr))
    else:
        return ((df["signed_skew_rank_roll"] >= sk) &
                (df["atr_rank_roll"] > at) &
                (df["trend_rank_roll"] <= tr))


# ============================================
# E · 反事实基准
# ============================================
def run_counterfactual(df, name, mask, ret_col):
    """
    对比：
    - 分类器触发的 events（真实）
    - 随机在 df 中抽同样数量的 events（100 次）
    看真实 mean 相对随机 mean 的位置 · 计算 p-value
    """
    sub = df[mask].dropna(subset=[ret_col])
    all_pool = df.dropna(subset=[ret_col])
    if len(sub) < 20 or len(all_pool) < 200:
        return None

    real_mean = sub[ret_col].mean()
    n = len(sub)
    rng = np.random.default_rng(42)
    random_means = []
    for _ in range(1000):
        idx = rng.integers(0, len(all_pool), size=n)
        random_means.append(all_pool.iloc[idx][ret_col].mean())
    random_means = np.array(random_means)

    # p-value：随机 mean 中大于真实 mean 的比例（右侧）· 对于负期望 alpha 反之
    if real_mean > 0:
        p_one = (random_means >= real_mean).mean()
    else:
        p_one = (random_means <= real_mean).mean()

    return {
        "combo": name,
        "real_n": n,
        "real_mean": real_mean,
        "random_mean_median": np.median(random_means),
        "random_mean_p05": np.quantile(random_means, 0.05),
        "random_mean_p95": np.quantile(random_means, 0.95),
        "excess": real_mean - np.median(random_means),
        "p_vs_random": p_one,
    }


# ============================================
# F · 8×8 组合独立性矩阵
# ============================================
def get_event_ids(df, mask):
    sub = df[mask]
    return set(zip(sub["contract"], sub["event_time"]))


def run_independence(df, signals):
    print("\n" + "=" * 100)
    print("F · 组合独立性矩阵（Jaccard 相似度 + Lift）")
    print("=" * 100)

    combos = {}
    for name, direction, sk, at, tr, ret_col in signals:
        mask = get_mask(df, direction, sk, at, tr)
        combos[name] = get_event_ids(df, mask)
        # 稳定/转换拆分
        stable_mask = mask & (~df["transition_flag"])
        trans_mask = mask & df["transition_flag"]
        combos[f"{name}·稳定"] = get_event_ids(df, stable_mask)
        combos[f"{name}·转换"] = get_event_ids(df, trans_mask)

    keys = list(combos.keys())
    n_all = len(df)

    rows = []
    print(f"\n{'A':25s} {'B':25s} {'|A|':>6s} {'|B|':>6s} {'|A∩B|':>6s} "
          f"{'Jaccard':>8s} {'Lift':>8s}")
    for i, a in enumerate(keys):
        for b in keys[i+1:]:
            A = combos[a]; B = combos[b]
            inter = A & B
            union = A | B
            jaccard = len(inter) / len(union) if len(union) > 0 else 0
            pA = len(A) / n_all if n_all > 0 else 0
            pB = len(B) / n_all if n_all > 0 else 0
            pAB = len(inter) / n_all if n_all > 0 else 0
            lift = pAB / (pA * pB) if pA * pB > 0 else 0
            rows.append({
                "A": a, "B": b, "n_A": len(A), "n_B": len(B),
                "n_inter": len(inter), "jaccard": jaccard, "lift": lift,
            })
    # 只输出前 20 关联度最高的
    r_df = pd.DataFrame(rows).sort_values("jaccard", ascending=False)
    print("\n【jaccard 前 15（关联最强）】")
    for _, r in r_df.head(15).iterrows():
        print(f"{r['A']:25s} {r['B']:25s} {int(r['n_A']):>6d} {int(r['n_B']):>6d} "
              f"{int(r['n_inter']):>6d} {r['jaccard']:>8.3f} {r['lift']:>8.2f}")

    r_df.to_csv(LOG_DIR / "classifier_stat_3_independence.csv", index=False)
    return r_df


# ============================================
# G · Time-in-market
# ============================================
def run_time_in_market(df, signals):
    print("\n" + "=" * 100)
    print("G · Time-in-market · 触发覆盖率与频率")
    print("=" * 100)

    n_events = len(df)
    contracts = df["contract"].unique()
    n_contracts = len(contracts)
    time_range = (df["event_time"].max() - df["event_time"].min())
    n_days = time_range.days

    # 触发率 = n_触发 / n_总事件
    rows = []
    print(f"\n总事件: {n_events} · 合约: {n_contracts} · 时间跨度: {n_days} 天\n")
    print(f"{'组合':20s} {'期别':8s} {'n':>6s} {'触发率':>8s} "
          f"{'每合约/天':>10s} {'占用/天占比':>12s}")

    horizon_bars_map = {"long": 96, "short": 48}  # 8h vs 4h
    for name, direction, sk, at, tr, ret_col in signals:
        h_bars = horizon_bars_map[direction] * 5  # 分钟
        for period in ["full", "stable", "trans"]:
            mask = get_mask(df, direction, sk, at, tr)
            if period == "stable":
                mask = mask & (~df["transition_flag"])
            elif period == "trans":
                mask = mask & df["transition_flag"]
            n_trig = mask.sum()
            trigger_rate = n_trig / n_events if n_events > 0 else 0
            # 每合约每天触发次数
            per_ct_per_day = n_trig / n_contracts / n_days if n_contracts * n_days > 0 else 0
            # 占用天数比 = 每合约每天触发次数 * horizon 小时 / 24 · 假设不重叠
            hold_hours = 8 if direction == "long" else 4
            occupancy = per_ct_per_day * hold_hours / 24
            rows.append({
                "combo": name, "period": period, "n_trig": n_trig,
                "trigger_rate": trigger_rate,
                "per_contract_per_day": per_ct_per_day,
                "occupancy_ratio": occupancy,
            })
            print(f"{name:20s} {period:8s} {int(n_trig):>6d} "
                  f"{trigger_rate:>8.2%} {per_ct_per_day:>10.3f} {occupancy:>12.2%}")

    pd.DataFrame(rows).to_csv(LOG_DIR / "classifier_stat_3_time_in_market.csv", index=False)


def main():
    print("=" * 100)
    print("阶段 3 分类器严格性 · 脚本 3（E 反事实 + F 独立性 + G 覆盖率）")
    print("=" * 100)

    df = prepare_dataset()
    df = flag_regime_transition(df)

    signals = [
        ("多头首选", "long", 0.10, 0.70, 0.75, "ret_8h_bps"),
        ("多头宽松", "long", 0.30, 0.70, 0.75, "ret_8h_bps"),
        ("空头首选", "short", 0.70, 0.80, 0.20, "short_pnl_4h_bps"),
        ("空头宽松", "short", 0.70, 0.50, 0.20, "short_pnl_4h_bps"),
        ("空头收敛", "short", 0.70, 0.67, 0.20, "short_pnl_4h_bps"),
    ]

    # E · 反事实
    print("\n" + "=" * 100)
    print("E · 反事实基准（真实 vs 随机 · 1000 次抽样）")
    print("=" * 100)
    cf_rows = []
    for name, direction, sk, at, tr, ret_col in signals:
        mask = get_mask(df, direction, sk, at, tr)
        r = run_counterfactual(df, name, mask, ret_col)
        if r is not None:
            cf_rows.append(r)
            print(f"\n{name} · 真实 mean = {r['real_mean']:+.2f} vs 随机中位 {r['random_mean_median']:+.2f}")
            print(f"  超额 = {r['excess']:+.2f} bps · p (真实优于随机) = {r['p_vs_random']:.4f}")
            print(f"  随机 5-95%: [{r['random_mean_p05']:+.2f}, {r['random_mean_p95']:+.2f}]")

    pd.DataFrame(cf_rows).to_csv(LOG_DIR / "classifier_stat_3_counterfactual.csv", index=False)

    # F · 独立性
    run_independence(df, signals)

    # G · Time-in-market
    run_time_in_market(df, signals)

    print(f"\n所有输出：")
    print(f"  {LOG_DIR / 'classifier_stat_3_counterfactual.csv'}")
    print(f"  {LOG_DIR / 'classifier_stat_3_independence.csv'}")
    print(f"  {LOG_DIR / 'classifier_stat_3_time_in_market.csv'}")


if __name__ == "__main__":
    main()
