"""
文件级元信息：
- 创建背景：阶段 2 门槛 2 · 计算主线三档信号的 ν_implied = μ - σ²/2
  （Itô 修正下的几何期望），并做 cluster bootstrap CI 验证是否显著 > 0。
- 用途：读取 multilayer_no_lookahead_events.csv（阶段 1 严格无未来函数版）
  对三档主线信号：
    (1) DN 单层
    (2) DN + 低 ATR_10
    (3) DN + 涨段 + 低 ATR_10
  分别计算：
    - μ = mean(ret_8h)      单位：bps
    - σ = std(ret_8h)       单位：bps
    - ν = μ - σ²/2 / 1e4    Itô 修正（σ 要转回 log ret 后再平方，然后除以 2）
    - cluster bootstrap 5000 次的 ν CI
  判据：ν CI 严格排 0 → KF-9 硬门槛通过
- 注意事项：σ²/2 的单位需要跟 μ 一致；bootstrap 每次重算 ν 不是 μ；
  对数收益单位是 bps，σ² 单位是 bps²，σ²/2 也是 bps²，需要除以 1e4
  才能转回 log 层面的 σ²/2（相当于 log ret²/2）
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage1"
)
EVENTS_PATH = LOG_DIR / "multilayer_no_lookahead_events.csv"

BOOTSTRAP_N = 5000
RNG_SEED = 20260707


def compute_nu(ret_bps: np.ndarray) -> float:
    """ν = μ - σ²/2. 输入 bps, 返回 bps.
    σ² 在 log 单位下是 (ret_bps/1e4)^2, 除以 2 后再乘 1e4 转回 bps."""
    mu_bps = ret_bps.mean()
    sigma_log_squared = (ret_bps / 1e4).std() ** 2
    ito_correction_bps = (sigma_log_squared / 2) * 1e4
    nu_bps = mu_bps - ito_correction_bps
    return nu_bps


def cluster_bootstrap_nu(events: pd.DataFrame, ret_col: str = "ret_bps",
                          n_boot: int = BOOTSTRAP_N, seed: int = RNG_SEED) -> dict:
    """cluster bootstrap 计算 ν 的 CI。"""
    rng = np.random.default_rng(seed)
    contracts = events["contract"].unique().tolist()
    per_c = {c: events[events["contract"] == c][ret_col].to_numpy() for c in contracts}

    real_ret = events[ret_col].to_numpy()
    real_mu = real_ret.mean()
    real_sigma = real_ret.std()
    real_ito = (real_ret / 1e4).std() ** 2 * 1e4 / 2
    real_nu = compute_nu(real_ret)

    boot_mu = np.zeros(n_boot)
    boot_sigma = np.zeros(n_boot)
    boot_nu = np.zeros(n_boot)
    for i in range(n_boot):
        picked = rng.choice(contracts, size=len(contracts), replace=True)
        all_r = np.concatenate([per_c[c] for c in picked])
        boot_mu[i] = all_r.mean()
        boot_sigma[i] = all_r.std()
        boot_nu[i] = compute_nu(all_r)

    def ci_p(arr, val_null=0.0):
        lo = float(np.quantile(arr, 0.025))
        hi = float(np.quantile(arr, 0.975))
        p_two = 2 * min((arr <= val_null).mean(), (arr >= val_null).mean())
        return lo, hi, p_two

    mu_ci = ci_p(boot_mu)
    nu_ci = ci_p(boot_nu)

    return {
        "n_events": len(events),
        "n_contracts": len(contracts),
        "real_mu": real_mu,
        "real_sigma": real_sigma,
        "real_ito_correction_bps": real_ito,
        "real_nu": real_nu,
        "mu_ci": mu_ci,
        "nu_ci": nu_ci,
    }


def report(label: str, mask: pd.Series, df: pd.DataFrame) -> None:
    sub = df[mask].dropna(subset=["ret_bps"])
    if len(sub) < 10:
        print(f"\n【{label}】样本太少 n={len(sub)}")
        return
    r = cluster_bootstrap_nu(sub)
    print(f"\n【{label}】")
    print(f"  n={r['n_events']} events · {r['n_contracts']} contracts")
    print(f"  μ (mean_ret_8h)     = {r['real_mu']:+.2f} bps")
    print(f"  σ (std_ret_8h)      = {r['real_sigma']:.2f} bps")
    print(f"  Itô 修正 σ²/2      = {r['real_ito_correction_bps']:+.2f} bps")
    print(f"  ν = μ − σ²/2        = {r['real_nu']:+.2f} bps")
    print(f"  μ 的 95% CI = [{r['mu_ci'][0]:+.2f}, {r['mu_ci'][1]:+.2f}] · p_two={r['mu_ci'][2]:.4f}")
    print(f"  ν 的 95% CI = [{r['nu_ci'][0]:+.2f}, {r['nu_ci'][1]:+.2f}] · p_two={r['nu_ci'][2]:.4f}")
    judge_mu = "✅" if r['mu_ci'][0] > 0 else "❌"
    judge_nu = "✅" if r['nu_ci'][0] > 0 else "❌"
    print(f"  μ CI 排 0: {judge_mu}  ·  ν CI 排 0: {judge_nu}")
    if r['real_nu'] > 0 and r['nu_ci'][0] > 0:
        print(f"  ⭐ KF-9 通过: ν = +{r['real_nu']:.1f} bps · CI 排 0 · p={r['nu_ci'][2]:.4f}")
    elif r['real_nu'] > 0:
        print(f"  ⚠️ ν > 0 但 CI 触 0 · 边缘")
    else:
        print(f"  ❌ ν ≤ 0 · 主线 alpha 被 Itô 修正吃掉")


def main() -> None:
    df = pd.read_csv(EVENTS_PATH)
    print(f"加载 · {len(df)} 事件 · {df['contract'].nunique()} 合约")

    # 沿用阶段 1 洞察 K 的分组
    print("\n" + "=" * 90)
    print("阶段 2 · 门槛 2 · ν_implied 反算（KF-9 硬门槛）")
    print("=" * 90)

    print("\n" + "-" * 90)
    print("档位 1 · DN 单层（A3_skew ≤ -1.5×σ_roll · dedup_8h）")
    print("-" * 90)
    mask = df["skew_grp"] == "DN"
    report("DN 单层", mask, df)

    print("\n" + "-" * 90)
    print("档位 2 · DN + 低日线 ATR_10")
    print("-" * 90)
    mask = (df["skew_grp"] == "DN") & (df["atr10_grp"] == "low")
    report("DN + 低 ATR_10", mask, df)

    print("\n" + "-" * 90)
    print("档位 3 · DN + 涨段 + 低日线 ATR_10 (主线)")
    print("-" * 90)
    mask = (df["skew_grp"] == "DN") & (df["trend_grp"] == "up") & (df["atr10_grp"] == "low")
    report("DN + up + 低 ATR_10 (主线)", mask, df)

    print("\n" + "=" * 90)
    print("KF-9 判据说明")
    print("=" * 90)
    print("  ν > 0 且 CI 排 0 → μ 提供的 alpha 足以覆盖 Itô 凸性衰减 → 可交易")
    print("  ν ≤ 0 → 复利后 alpha 消失 → 只是波动放大，不是真信号")
    print("  ν > 0 但 CI 触 0 → 边缘 · 阶段 3 通过扩样本 CI 稳健化后判决")


if __name__ == "__main__":
    main()
