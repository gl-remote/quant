"""
文件级元信息：
- 创建背景：确定 A3_skew 的分布形态 → 用分布百分位定阈值（避免早熟调参）。
  假设 A3_skew ≈ N(0, σ²) 时，|skew|>1σ 对应尾部 ~32%，与经验 q=16% 吻合。
- 用途：
  (1) 每个合约的 A3_skew 分布摘要（mean/std/skew/kurt/QQ 参照正态）
  (2) 正态 vs Student's t 拟合 · 报告 df / loc / scale
  (3) Jarque-Bera 正态性检验
  (4) k∈{0.5, 1, 1.5, 2} 各档 σ 阈值下每合约的实际事件率与 DN mean_ret_8h
  → 输出决策报告：分布是否稳定、该取几个 σ
- 注意事项：临时研究脚本。σ 估算用全样本，属于"轻度未来函数"；下一步
  可换成 warm-up 或 rolling σ 消除。
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage1"
)
LONG_PATH = LOG_DIR / "long_events.csv"

WINDOW = "W1"
METRIC = "A3_skew"
HORIZON = "ret_8h"
DEDUP_GAP_HOURS = 8.0
K_LEVELS = [0.5, 1.0, 1.5, 2.0]


def dedup_gap(events: pd.DataFrame, min_gap_h: float) -> pd.DataFrame:
    ev = events.sort_values("event_time").reset_index(drop=True)
    kept = []
    last = None
    for i, row in ev.iterrows():
        if last is None or (row["event_time"] - last).total_seconds() / 3600 >= min_gap_h:
            kept.append(i)
            last = row["event_time"]
    return ev.loc[kept]


def main() -> None:
    df = pd.read_csv(LONG_PATH)
    df["event_time"] = pd.to_datetime(df["event_time"])
    sub = df[df["window"] == WINDOW].copy()
    contracts = sorted(sub["contract"].unique())

    # =============== (1) 分布摘要 ===============
    print("=" * 100)
    print(f"=== 分布摘要 · {WINDOW} × {METRIC} ===\n")
    print(f"{'contract':16s} {'n':>5s} {'mean':>7s} {'std':>7s} {'skew':>7s} {'kurt':>7s} "
          f"{'JB stat':>10s} {'JB p':>10s} {'t_df':>7s} {'t_scale':>8s} {'normal?':>10s}")
    print("-" * 100)

    dist_rows: list[dict] = []
    for c in contracts:
        x = sub[sub["contract"] == c][METRIC].dropna().to_numpy()
        if len(x) < 30:
            continue
        m, s = float(x.mean()), float(x.std())
        sk = float(stats.skew(x))
        kt = float(stats.kurtosis(x))  # excess kurtosis
        jb_stat, jb_p = stats.jarque_bera(x)
        # 拟合 t 分布
        t_df, t_loc, t_scale = stats.t.fit(x)
        normal_ok = "✓" if jb_p > 0.05 else "✗"
        print(f"{c:16s} {len(x):>5d} {m:>+7.3f} {s:>7.3f} {sk:>+7.3f} {kt:>+7.3f} "
              f"{jb_stat:>10.2f} {jb_p:>10.4f} {t_df:>7.2f} {t_scale:>8.3f} {normal_ok:>10s}")
        dist_rows.append({
            "contract": c, "n": len(x), "mean": m, "std": s, "skew": sk, "kurt": kt,
            "jb_stat": jb_stat, "jb_p": jb_p, "t_df": t_df, "t_scale": t_scale,
        })

    # pooled
    all_x = sub[METRIC].dropna().to_numpy()
    m_all, s_all = float(all_x.mean()), float(all_x.std())
    sk_all, kt_all = float(stats.skew(all_x)), float(stats.kurtosis(all_x))
    jb_a, jbp_a = stats.jarque_bera(all_x)
    t_df_a, t_loc_a, t_scale_a = stats.t.fit(all_x)
    print("-" * 100)
    print(f"{'POOLED':16s} {len(all_x):>5d} {m_all:>+7.3f} {s_all:>7.3f} {sk_all:>+7.3f} "
          f"{kt_all:>+7.3f} {jb_a:>10.2f} {jbp_a:>10.4f} {t_df_a:>7.2f} "
          f"{t_scale_a:>8.3f} {'✓' if jbp_a > 0.05 else '✗':>10s}")

    dist_df = pd.DataFrame(dist_rows)
    dist_df.to_csv(LOG_DIR / "distribution_fit.csv", index=False)

    # =============== (2) QQ 表格：empirical 分位 vs 理论正态分位 ===============
    print("\n" + "=" * 100)
    print("=== POOLED empirical 分位 vs 理论正态 N(mean, std) 分位 ===\n")
    print(f"{'quantile':>10s} {'empirical':>12s} {'normal':>12s} {'diff':>12s}")
    for q in [0.01, 0.05, 0.10, 0.16, 0.25, 0.50, 0.75, 0.84, 0.90, 0.95, 0.99]:
        emp = float(np.quantile(all_x, q))
        norm_q = float(stats.norm.ppf(q, loc=m_all, scale=s_all))
        print(f"{q:>10.2%} {emp:>+12.3f} {norm_q:>+12.3f} {emp - norm_q:>+12.3f}")

    # =============== (3) k×σ 阈值 → 事件率 & DN mean ===============
    print("\n" + "=" * 100)
    print("=== k×σ 阈值扫描（σ 用每合约自身全样本 std）· DN dedup_8h ===\n")
    # 表头：k / 每合约 (n, mean, hit)
    header = f"{'k':>4s} {'k×σ  阈值范围':>16s}   {'理论覆盖(单侧)':>13s}   "
    for c in contracts:
        header += f"{c.split('.')[-1][:6]:>7s}"
    header += f"   {'POOL n':>7s} {'POOL mean':>10s} {'POOL hit':>10s}"
    print(header)
    print("-" * len(header))

    rows_k: list[dict] = []
    for k in K_LEVELS:
        line = f"{k:>4.1f}"
        theoretical_tail = stats.norm.sf(k)  # P(Z > k) 单侧
        # 阈值范围只是给个参考（跨合约 σ 不一样，这里给 pooled σ 参考）
        line += f"   ±{k*s_all:>13.3f}"
        line += f"   {theoretical_tail:>13.4%}"

        pooled_events: list[pd.DataFrame] = []
        for c in contracts:
            ev = sub[sub["contract"] == c].copy()
            std_c = ev[METRIC].std()
            thr = k * std_c
            dn = ev[ev[METRIC] <= -thr]
            dn = dedup_gap(dn, DEDUP_GAP_HOURS)
            pooled_events.append(dn)
            if not dn.empty:
                r = dn[HORIZON].dropna() * 1e4
                line += f"{len(r):>3d}:{r.mean():>+3.0f}"
            else:
                line += f"     -"
            rows_k.append({
                "k": k, "contract": c, "std_c": std_c, "threshold": -thr,
                "n": len(dn), "mean_ret_bps": r.mean() if not dn.empty and len(r) > 0 else float("nan"),
                "hit_pos": (r > 0).mean() if not dn.empty and len(r) > 0 else float("nan"),
            })
        # pooled
        pool_df = pd.concat(pooled_events, ignore_index=True)
        r = pool_df[HORIZON].dropna() * 1e4
        line += f"   {len(r):>7d} {r.mean():>+10.2f} {(r>0).mean():>10.1%}"
        print(line)

    pd.DataFrame(rows_k).to_csv(LOG_DIR / "threshold_by_sigma.csv", index=False)

    print("\n" + "=" * 100)
    print("=== 判断 ===")
    if jbp_a < 0.05:
        print(f"✗ POOLED A3_skew 显著偏离正态 (JB p={jbp_a:.4g})，excess kurt={kt_all:+.2f}")
        if t_df_a < 30:
            print(f"  拟合 t 分布 df={t_df_a:.1f} 说明有重尾；用 t 分布分位取阈值更准确")
        else:
            print(f"  t_df={t_df_a:.1f} 已很接近正态")
    else:
        print(f"✓ POOLED A3_skew 未显著偏离正态 (JB p={jbp_a:.4g}) → k×σ 阈值可直接对应正态分位")
    print("\nOutputs:")
    print(f"  {LOG_DIR / 'distribution_fit.csv'}")
    print(f"  {LOG_DIR / 'threshold_by_sigma.csv'}")


if __name__ == "__main__":
    main()
