"""Stage 4: 把 c/m/rb × 5m/15m/1h 的 W=80 (μ_D, σ_D) 喂给 KF-27 优化器.

周期参数换算 (基于 corn_1h 标定 year_hours=1625, c_side=0.077):
  - 1h:  year_bars = 250 * 6.5 = 1625, c_side = 0.077 (ATR 归一化, 与周期无关)
  - 15m: year_bars = 1625 * 4 = 6500
  - 5m:  year_bars = 1625 * 12 = 19500
  - sigma_bar=1.0 (ATR 归一化后所有周期 σ_bar ≈ 1 / sqrt(bar_hours), 但我们输入
    的 |s| = |ν|/σ 已经是 σ-归一化的量, 与周期无关, sigma_bar 保留 1.0)

注意: c_side 是 ATR 归一化后的单边成本, 与周期无关 (ATR 本身随周期变, 归一化后 c_side 不变).
     year_bars 换成"每年多少根 bar" — 因为 E[τ] 在公式里是 bar 数.
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import numpy as np

REPO = Path("/Users/gaolei/Documents/src/quant")
sys.path.insert(0, str(REPO / "docs/research/archived-notes/2026/07/2026-07-24-structural-shaping-alpha-freeze/raw-scripts"))
from kf26_parameter_optimizer import FoldedNormal, optimize_all  # noqa: E402

SUMMARY_CSV = REPO / "docs/workbench/time-barrier-selection/outputs/cross_symbol_summary.csv"

# 周期 → year_bars
YEAR_BARS = {"5m": 19500, "15m": 6500, "1h": 1625}
C_SIDE = 0.077   # ATR 归一化单边成本 (与周期无关)
K_S_MIN = 1.0
K_S_MAX = 5.0
K_T_MAX = 12.0
SIGMA_BAR = 1.0


def main():
    df = pd.read_csv(SUMMARY_CSV)
    # 取 W=80, 聚合到品种×周期, 合约平均 (rb 含 rb2610 仅 5m 的自动排除, groupby mean 会忽略 nan)
    w80 = df[df["W"] == 80].copy()
    agg = w80.groupby(["symbol", "period"]).agg(
        mu_D=("mu_D", "mean"),
        sigma_D=("sigma_D", "mean"),
        rho_1=("rho_1", "mean"),
        n_contracts=("contract", "nunique"),
    ).reset_index()

    print("=== Stage 4 输入: c/m/rb × 5m/15m/1h, W=80 合约平均 (μ_D, σ_D) ===")
    print(agg.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print()

    rows = []
    for _, r in agg.iterrows():
        sym, period = r["symbol"], r["period"]
        mu_D, sigma_D = r["mu_D"], r["sigma_D"]
        if np.isnan(mu_D) or np.isnan(sigma_D) or mu_D < 0.001:
            print(f"[skip] {sym}/{period}: mu_D={mu_D:.4f} invalid")
            continue
        try:
            D = FoldedNormal(mu_D=mu_D, sd_D=sigma_D)
            D.fit()
        except Exception as e:
            print(f"[err] {sym}/{period}: fit failed {e}")
            continue

        year_bars = YEAR_BARS[period]
        best = optimize_all(D, C_SIDE, K_S_MIN, K_S_MAX, K_T_MAX,
                            SIGMA_BAR, year_bars, objective="sharpe_year")
        d = best["detail"]
        RR = d["K_T"] / d["K_S"] if d["K_S"] > 0 else float("nan")
        print(f"[{sym}/{period}] mu_D={mu_D:.3f} sigma_D={sigma_D:.3f}")
        print(f"  K_S*={d['K_S']:.2f}  K_T*={d['K_T']:.2f}  RR*={RR:.2f}  τ*={d['tau']:.3f}")
        print(f"  P(X≥τ)={d['P_ge_tau']:.3f}  N/年={d['n_year']:.1f}")
        print(f"  E_gross={d['E_gross']:+.3f}  E_net={d['E_net']:+.3f}  "
              f"Sharpe/年={d['sharpe_year']:+.2f}  年化@r=1%={d['ann_pct_r1']:+.2f}%")
        print()
        rows.append({
            "symbol": sym, "period": period,
            "mu_D": mu_D, "sigma_D": sigma_D, "rho_1": r["rho_1"],
            "K_S*": d["K_S"], "K_T*": d["K_T"], "RR*": RR, "tau*": d["tau"],
            "P_ge_tau": d["P_ge_tau"], "N_year": d["n_year"],
            "E_gross": d["E_gross"], "E_net": d["E_net"],
            "sharpe_year": d["sharpe_year"], "ann_pct": d["ann_pct_r1"],
        })

    # 基线: KF-27 标准玉米 1h (mu_D=0.198, sigma_D=0.108)
    print("=== 基线: KF-27 标准玉米 1h (μ_D=0.198, σ_D=0.108) ===")
    D0 = FoldedNormal(mu_D=0.198, sd_D=0.108)
    D0.fit()
    b0 = optimize_all(D0, C_SIDE, K_S_MIN, K_S_MAX, K_T_MAX, SIGMA_BAR, YEAR_BARS["1h"], objective="sharpe_year")
    d0 = b0["detail"]
    print(f"  K_S*={d0['K_S']:.2f}  K_T*={d0['K_T']:.2f}  RR*={d0['K_T']/d0['K_S']:.2f}  τ*={d0['tau']:.3f}")
    print(f"  E_net={d0['E_net']:+.3f}  Sharpe/年={d0['sharpe_year']:+.2f}  年化={d0['ann_pct_r1']:+.2f}%")
    print()

    out = pd.DataFrame(rows)
    out_path = REPO / "docs/workbench/time-barrier-selection/outputs/stage4_kf27_sweep.csv"
    out.to_csv(out_path, index=False)
    print(f"[done] wrote {out_path}")


if __name__ == "__main__":
    main()
