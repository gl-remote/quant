"""
文件级元信息：
- 创建背景：固定阈值 |A3_skew|≥0.45 定"入场触发"，用贝叶斯后验估算
  P(ret_8h > 0) 决定是否真的入场。避免全部盲目跟触发，只在后验信心
  足够时才真交易。
- 用途：读 long_events.csv → 对每个合约按 event_time 时序遍历 DN 触发
  → 维护 Beta(α, β) 后验 → 用不同决策规则筛出"实际入场"事件
  → pooled + 分品种展示三档决策的 n / mean / hit
- 注意事项：
  - 无未来函数：t 时刻的入场决策只依赖 t 之前的观察
  - warmup=10 次触发前不入场
  - Prior Beta(1,1) = 无信息
  - RULE 1: posterior_mean > 0.5
  - RULE 2: posterior_mean - 1σ > 0.5（更严）
  - RULE 3: 只用最近 K=30 次观察做 rolling Beta
- 依赖：dedup_8h 应用在"触发列表"上，避免持仓重叠
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage1"
)
LONG_PATH = LOG_DIR / "long_events.csv"

WINDOW = "W1"
METRIC = "A3_skew"
HORIZON = "ret_8h"
FIXED_LO = -0.45
DEDUP_GAP_HOURS = 8.0
WARMUP_N = 10
ROLLING_K = 30
PRIOR_ALPHA = 1.0
PRIOR_BETA = 1.0


def dedup_gap_series(events: pd.DataFrame, min_gap_h: float) -> pd.DataFrame:
    ev = events.sort_values("event_time").reset_index(drop=True)
    kept = []
    last = None
    for i, row in ev.iterrows():
        if last is None or (row["event_time"] - last).total_seconds() / 3600 >= min_gap_h:
            kept.append(i)
            last = row["event_time"]
    return ev.loc[kept]


def bayesian_walkforward(triggers: pd.DataFrame) -> pd.DataFrame:
    """时序遍历触发事件，为每个事件标注四条决策规则的入场标记。

    返回列增加：
      - obs_win: 该事件 ret > 0 (观察值 · 用于更新 posterior，不用于当前决策)
      - post_mean_full: 使用全历史时的 posterior mean（决策前）
      - post_lower_full: post_mean - std
      - post_mean_roll: 用最近 K 次观察的 rolling posterior mean
      - enter_rule0: 全部入场
      - enter_rule1: post_mean_full > 0.5
      - enter_rule2: post_lower_full > 0.5
      - enter_rule3: post_mean_roll > 0.5
    """
    ev = triggers.sort_values("event_time").reset_index(drop=True).copy()
    ev["obs_win"] = (ev[HORIZON] > 0).astype(int)

    post_mean_full = np.full(len(ev), np.nan)
    post_lower_full = np.full(len(ev), np.nan)
    post_mean_roll = np.full(len(ev), np.nan)

    wins = 0
    losses = 0
    obs_series: list[int] = []
    for i in range(len(ev)):
        # 决策前的 posterior 只用 t 之前的观察
        n_seen = wins + losses
        if n_seen >= WARMUP_N:
            alpha = PRIOR_ALPHA + wins
            beta = PRIOR_BETA + losses
            mean = alpha / (alpha + beta)
            var = alpha * beta / ((alpha + beta) ** 2 * (alpha + beta + 1))
            std = math.sqrt(var)
            post_mean_full[i] = mean
            post_lower_full[i] = mean - std

            recent = obs_series[-ROLLING_K:] if len(obs_series) >= WARMUP_N else obs_series
            if len(recent) >= WARMUP_N:
                r_wins = sum(recent)
                r_losses = len(recent) - r_wins
                post_mean_roll[i] = (PRIOR_ALPHA + r_wins) / (
                    PRIOR_ALPHA + PRIOR_BETA + len(recent)
                )

        # 更新 posterior 用当前事件观察
        obs = int(ev.at[i, "obs_win"])
        obs_series.append(obs)
        if obs:
            wins += 1
        else:
            losses += 1

    ev["post_mean_full"] = post_mean_full
    ev["post_lower_full"] = post_lower_full
    ev["post_mean_roll"] = post_mean_roll
    ev["enter_rule0"] = True
    ev["enter_rule1"] = post_mean_full > 0.5
    ev["enter_rule2"] = post_lower_full > 0.5
    ev["enter_rule3"] = post_mean_roll > 0.5
    # warmup 前 rule 1-3 都 False（避免 NaN）
    for col in ["enter_rule1", "enter_rule2", "enter_rule3"]:
        ev[col] = ev[col].fillna(False).astype(bool)
    return ev


def summarize(events: pd.DataFrame, mask_col: str) -> tuple[int, float, float]:
    sub = events[events[mask_col]]
    r = sub[HORIZON].dropna() * 1e4
    if len(r) == 0:
        return 0, float("nan"), float("nan")
    return int(len(r)), float(r.mean()), float((r > 0).mean())


def main() -> None:
    df = pd.read_csv(LONG_PATH)
    df["event_time"] = pd.to_datetime(df["event_time"])
    sub = df[df["window"] == WINDOW].copy()

    contracts = sorted(sub["contract"].unique())
    all_enriched: list[pd.DataFrame] = []

    print("=== 分品种 · 固定阈值 |skew|≥0.45 + Bayesian 决策 · DN dedup_8h ===\n")
    print(f"{'contract':16s}  {'RULE0 all':>18s}   {'RULE1 mean>0.5':>18s}   "
          f"{'RULE2 lower>0.5':>18s}   {'RULE3 roll K=30':>18s}")
    print(f"{'':16s}  {'n':>4s} {'mean':>6s} {'hit':>5s}    {'n':>4s} {'mean':>6s} {'hit':>5s}    "
          f"{'n':>4s} {'mean':>6s} {'hit':>5s}    {'n':>4s} {'mean':>6s} {'hit':>5s}")
    print("-" * 110)

    per_sym_rows: list[dict] = []
    for c in contracts:
        ev = sub[sub["contract"] == c].copy()
        triggers = ev[ev[METRIC] <= FIXED_LO].copy()
        # dedup_8h 用触发时序
        triggers_dedup = dedup_gap_series(triggers, DEDUP_GAP_HOURS)
        enriched = bayesian_walkforward(triggers_dedup)
        enriched["contract"] = c
        all_enriched.append(enriched)

        n0, m0, h0 = summarize(enriched, "enter_rule0")
        n1, m1, h1 = summarize(enriched, "enter_rule1")
        n2, m2, h2 = summarize(enriched, "enter_rule2")
        n3, m3, h3 = summarize(enriched, "enter_rule3")

        print(f"{c:16s}  "
              f"{n0:>4d} {m0:>+6.1f} {h0:>5.1%}    "
              f"{n1:>4d} {m1:>+6.1f} {h1:>5.1%}    "
              f"{n2:>4d} {m2:>+6.1f} {h2:>5.1%}    "
              f"{n3:>4d} {m3:>+6.1f} {h3:>5.1%}")
        per_sym_rows.append({
            "contract": c,
            "rule0_n": n0, "rule0_mean": m0, "rule0_hit": h0,
            "rule1_n": n1, "rule1_mean": m1, "rule1_hit": h1,
            "rule2_n": n2, "rule2_mean": m2, "rule2_hit": h2,
            "rule3_n": n3, "rule3_mean": m3, "rule3_hit": h3,
        })

    per_sym = pd.DataFrame(per_sym_rows)
    per_sym_path = LOG_DIR / "bayesian_per_symbol.csv"
    per_sym.to_csv(per_sym_path, index=False)

    all_enriched_df = pd.concat(all_enriched, ignore_index=True)
    all_enriched_path = LOG_DIR / "bayesian_events.csv"
    all_enriched_df.to_csv(all_enriched_path, index=False)

    # Pooled
    print("\n=== Pooled（跨合约 pool 触发事件）===")
    for rule_col, name in [
        ("enter_rule0", "RULE0 · 全部入场（=plan A dedup_8h）"),
        ("enter_rule1", "RULE1 · Bayesian mean > 0.5"),
        ("enter_rule2", "RULE2 · Bayesian mean - 1σ > 0.5"),
        ("enter_rule3", f"RULE3 · rolling K={ROLLING_K} mean > 0.5"),
    ]:
        n, m, h = summarize(all_enriched_df, rule_col)
        # 估算频率（触发/合约/天）—— 用有效持有的合约天数
        print(f"  {name:45s}  n={n:>4d}  mean={m:>+6.2f} bps  hit={h:>5.1%}")

    baseline = sub[HORIZON].dropna() * 1e4
    print(f"  {'baseline · 全 events':45s}  n={len(baseline):>4d}  "
          f"mean={baseline.mean():>+6.2f} bps  hit={(baseline>0).mean():>5.1%}")

    # 分品种 net 估算（DN 做多）——用每合约实际成本
    print("\n=== 分品种 RULE1 (mean>0.5) · DN 做多 net ===")
    # 简化：使用之前 profit_space.py 里已算好的 single_side_cost_bps
    cost_path = LOG_DIR / "profit_space.csv"
    if cost_path.exists():
        cost_df = pd.read_csv(cost_path)
        cost_map = cost_df.drop_duplicates("contract").set_index("contract")["single_side_cost_bps"]
        for c in contracts:
            n1, m1, h1 = summarize(all_enriched_df[all_enriched_df["contract"] == c], "enter_rule1")
            cost = cost_map.get(c, float("nan"))
            net = m1 - cost if not math.isnan(m1) else float("nan")
            print(f"  {c:16s}  n={n1:>3d}  gross={m1:>+7.2f}  cost={cost:>5.2f}  net={net:>+7.2f} bps")

    print(f"\nOutputs:")
    print(f"  {per_sym_path}")
    print(f"  {all_enriched_path}")


if __name__ == "__main__":
    main()
