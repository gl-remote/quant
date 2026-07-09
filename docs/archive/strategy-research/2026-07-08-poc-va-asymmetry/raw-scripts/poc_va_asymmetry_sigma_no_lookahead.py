"""
文件级元信息：
- 创建背景：阶段 1 唯一未闭合的方法论隐患：当前 k×σ 阈值用了全样本 std 估算，
  属"轻度未来函数"。本脚本验证换成无未来函数的 σ 估算后事件率与 pooled mean
  是否保持稳定。
- 用途：读 long_events.csv (W1 × A3_skew) → 每合约独立计算三种 σ：
    (1) sigma_full        : 全样本 std（当前口径 · 含未来函数）
    (2) sigma_warmup      : 前 30 交易日事件的 std（固定 σ · 半含未来函数）
    (3) sigma_rolling200  : 每个事件前 200 事件的滚动 std（严格无未来函数）
  三种 σ 分别用 k=1.5 生成 DN 事件（含 dedup_8h），比较：
    - n_events
    - pooled DN mean bps
    - pooled hit rate
    - cluster bootstrap 95% CI（复用 poc_va_asymmetry_cluster_bootstrap 逻辑）
- 注意事项：只用原 10 合约主表（long_events.csv 已存在），避免重跑 profile；
  ret_8h 单位 bps；warm-up 期本身不参与事件评估（前 30 天事件被视为估算期）
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage1"
)
LONG_PATH = LOG_DIR / "long_events.csv"

WINDOW = "W1"
METRIC = "A3_skew"
K_SIGMA = 1.5
DEDUP_GAP_HOURS = 8.0
WARMUP_DAYS = 30
ROLLING_EVENTS = 200
BOOTSTRAP_N = 5000
RNG_SEED = 20260707


def dedup_gap(events: pd.DataFrame, min_gap_h: float) -> pd.DataFrame:
    ev = events.sort_values("event_time").reset_index(drop=True)
    kept = []
    last = None
    for i, row in ev.iterrows():
        if last is None or (row["event_time"] - last).total_seconds() / 3600 >= min_gap_h:
            kept.append(i)
            last = row["event_time"]
    return ev.loc[kept]


def cluster_bootstrap_ci(events: pd.DataFrame, n_boot: int = BOOTSTRAP_N,
                          seed: int = RNG_SEED) -> tuple[float, float, float, float]:
    """按 contract 聚类重抽样，返回 (mean, ci_low, ci_high, p_two)。"""
    rng = np.random.default_rng(seed)
    contracts = events["contract"].unique().tolist()
    per_c = {c: events[events["contract"] == c]["ret_bps"].to_numpy() for c in contracts}
    real_mean = events["ret_bps"].mean()

    boot_means = np.zeros(n_boot)
    for i in range(n_boot):
        picked = rng.choice(contracts, size=len(contracts), replace=True)
        all_r = np.concatenate([per_c[c] for c in picked])
        boot_means[i] = all_r.mean()
    ci_lo = float(np.quantile(boot_means, 0.025))
    ci_hi = float(np.quantile(boot_means, 0.975))
    # 双边 p 值：以 0 为参考的极端度
    p_two = 2 * min((boot_means <= 0).mean(), (boot_means >= 0).mean())
    return real_mean, ci_lo, ci_hi, p_two


def process_contract(g: pd.DataFrame) -> dict:
    """给某合约事件序列，构建三种 σ 下的 DN 事件（dedup_8h）。"""
    g = g.copy().sort_values("event_time").reset_index(drop=True)
    g["event_time"] = pd.to_datetime(g["event_time"])
    g["date"] = g["event_time"].dt.date

    # 三种 σ
    sigma_full = g[METRIC].std()

    # warm-up：前 30 交易日 std（固定）
    all_dates = sorted(g["date"].unique())
    if len(all_dates) < WARMUP_DAYS + 5:
        return None
    warmup_end = all_dates[WARMUP_DAYS - 1]
    warmup = g[g["date"] <= warmup_end]
    sigma_warmup = warmup[METRIC].std()

    # rolling K=200 事件的 std（每行独立）
    g["sigma_rolling"] = g[METRIC].shift(1).rolling(ROLLING_EVENTS, min_periods=50).std()

    # 事件切片（三种）
    def collect_dn(sigma_series_or_val, mask_start_date=None) -> pd.DataFrame:
        thr = -K_SIGMA * sigma_series_or_val if not isinstance(sigma_series_or_val, pd.Series) \
              else -K_SIGMA * sigma_series_or_val
        sub = g.copy()
        if isinstance(thr, pd.Series):
            dn_mask = sub[METRIC] <= thr
        else:
            dn_mask = sub[METRIC] <= thr
        # 排除 warm-up 期（无未来函数版本才需要）
        if mask_start_date is not None:
            dn_mask &= sub["date"] > mask_start_date
        dn = sub[dn_mask].dropna(subset=["ret_8h"])
        dn = dedup_gap(dn, DEDUP_GAP_HOURS)
        return dn

    # 三个版本
    dn_full = collect_dn(sigma_full)  # 用全样本 σ · 所有事件都算
    dn_warmup = collect_dn(sigma_warmup, mask_start_date=warmup_end)  # 排除 warm-up 期
    dn_rolling = collect_dn(g["sigma_rolling"], mask_start_date=None)
    dn_rolling = dn_rolling.dropna(subset=["sigma_rolling"])  # 前 50 事件没有 rolling σ

    return {
        "sigma_full": sigma_full,
        "sigma_warmup": sigma_warmup,
        "sigma_rolling_median": g["sigma_rolling"].median(),
        "dn_full": dn_full,
        "dn_warmup": dn_warmup,
        "dn_rolling": dn_rolling,
        "warmup_end": warmup_end,
    }


def main() -> None:
    df = pd.read_csv(LONG_PATH)
    sub = df[df["window"] == WINDOW].copy()

    results_by_contract = {}
    print(f"{'contract':16s} {'σ_full':>8s} {'σ_warmup':>10s} {'σ_roll_med':>10s} "
          f"{'n_full':>6s} {'n_warmup':>8s} {'n_roll':>6s}")
    for c, g in sub.groupby("contract"):
        r = process_contract(g)
        if r is None:
            continue
        results_by_contract[c] = r
        print(f"{c:16s} {r['sigma_full']:>8.3f} {r['sigma_warmup']:>10.3f} "
              f"{r['sigma_rolling_median']:>10.3f} "
              f"{len(r['dn_full']):>6d} {len(r['dn_warmup']):>8d} "
              f"{len(r['dn_rolling']):>6d}")

    # Pooled 汇总
    def pool_dn(key: str) -> pd.DataFrame:
        rows = []
        for c, r in results_by_contract.items():
            df_c = r[key].copy()
            df_c["contract"] = c
            df_c["ret_bps"] = df_c["ret_8h"] * 1e4
            rows.append(df_c)
        return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()

    print("\n\n" + "=" * 90)
    print("Pooled DN 事件对比（k=1.5×σ · dedup_8h）")
    print("=" * 90)
    print(f"\n{'σ 估算方式':30s} {'n':>6s} {'mean_bps':>10s} {'hit':>7s} "
          f"{'95% CI':>22s} {'p_two':>7s}")

    for key, label in [
        ("dn_full", "sigma_full（含未来函数）"),
        ("dn_warmup", "sigma_warmup（前 30 天）"),
        ("dn_rolling", "sigma_rolling200（严格无未来函数）"),
    ]:
        pool = pool_dn(key)
        if len(pool) == 0:
            continue
        r = pool["ret_bps"]
        mean, lo, hi, p = cluster_bootstrap_ci(pool)
        print(f"{label:30s} {len(pool):>6d} {r.mean():>+10.2f} "
              f"{(r>0).mean():>7.1%}  [{lo:>+7.2f}, {hi:>+7.2f}]  {p:>7.4f}")

    # 分品种表格 for warmup vs full
    print("\n\n" + "=" * 90)
    print("分品种 σ_warmup vs σ_full 差异")
    print("=" * 90)
    print(f"\n{'contract':16s} {'σ_full':>8s} {'σ_warmup':>10s} {'σ差异%':>10s} "
          f"{'n_full':>6s} {'n_warmup':>8s} {'mean_full':>10s} {'mean_warmup':>12s}")
    for c, r in results_by_contract.items():
        sf, sw = r["sigma_full"], r["sigma_warmup"]
        diff_pct = (sw - sf) / sf * 100 if sf > 0 else 0
        mf = r["dn_full"]["ret_8h"].mean() * 1e4 if len(r["dn_full"]) else float("nan")
        mw = r["dn_warmup"]["ret_8h"].mean() * 1e4 if len(r["dn_warmup"]) else float("nan")
        print(f"{c:16s} {sf:>8.3f} {sw:>10.3f} {diff_pct:>+9.1f}% "
              f"{len(r['dn_full']):>6d} {len(r['dn_warmup']):>8d} "
              f"{mf:>+10.2f} {mw:>+12.2f}")

    print("\n判读:")
    print("  · 若 sigma_warmup / sigma_rolling200 版本的 pooled mean 与 sigma_full 差异 < 20%，")
    print("    且 cluster CI 仍排 0 → σ 估算无未来函数版本可用 → 阶段 1 完全闭环")
    print("  · 若 mean 幅度掉一半以上 或 CI 触 0 → 需要更多 warm-up 或换特征")


if __name__ == "__main__":
    main()
