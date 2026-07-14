"""KF-23/24/25 · 框架扩展实验：跳扩散修正 + σ时变 + trailing barrier Monte Carlo.

KF-23: 跳扩散修正 —— 从 5m 数据中检测 session gap，估计跳空穿透概率，
       计算 P_win 的 jump correction 项
KF-24: σ 时变分析 —— 计算持仓期间 ATR 的变化系数和自相关，
       量化"σ恒定"假设的误差量级
KF-25: trailing barrier Monte Carlo —— 对比 fixed barrier vs trailing barrier
       的 E_net, P_win, max drawdown

所有实验基于已有 5m trades 数据（boundary_explorer 输出）+ 原始 K 线数据。
"""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm
from scipy.optimize import brentq

from data.output_paths import market_csv_dir, project_data_root

# ────────────────────── 常量 ──────────────────────

SYMBOLS_5M = [
    ("rb2601", "SHFE.rb2601"), ("rb2605", "SHFE.rb2605"),
    ("i2601", "DCE.i2601"), ("i2509", "DCE.i2509"),
    ("cu2601", "SHFE.cu2601"), ("cu2509", "SHFE.cu2509"),
    ("al2601", "SHFE.al2601"), ("al2509", "SHFE.al2509"),
    ("sc2512", "INE.sc2512"), ("sc2509", "INE.sc2509"),
    ("TA601", "CZCE.TA601"), ("TA509", "CZCE.TA509"),
    ("m2601", "DCE.m2601"), ("m2605", "DCE.m2605"),
    ("p2601", "DCE.p2601"), ("p2605", "DCE.p2605"),
    ("SR601", "CZCE.SR601"), ("SR605", "CZCE.SR605"),
    ("CF601", "CZCE.CF601"), ("CF509", "CZCE.CF509"),
]

KEY_COMBOS = [(1.0, 1.0), (1.5, 2.0), (2.5, 1.0), (2.5, 2.0), (4.0, 1.0), (4.0, 2.0)]
SIGMA_5M = 1.0 / math.sqrt(12)
MAX_BARS = 80
EMA_WINDOW = 20
FOURIER_N_TERMS = 100
MC_N_PATHS = 5000
RANDOM_SEED = 20260715


# ────────────────────── FPT 核心方程 ──────────────────────

def p_win_infty(lam, K_S, K_T):
    if abs(lam) < 1e-8:
        return K_S / (K_S + K_T)
    e_KT = math.exp(lam * K_T)
    e_KS = math.exp(-lam * K_S)
    return (e_KT * (1 - e_KS)) / (e_KT - e_KS)


def e_gross_infty(lam, K_S, K_T):
    p = p_win_infty(lam, K_S, K_T)
    return p * K_T - (1 - p) * K_S


def p_tau_gt_t_fourier(K_S, K_T, sigma, T, n_terms=FOURIER_N_TERMS):
    L = K_S + K_T
    pref = (math.pi ** 2) * (sigma ** 2) * T / (2 * L ** 2)
    total = 0.0
    for n in range(1, n_terms + 1, 2):
        total += math.sin(n * math.pi * K_S / L) / n * math.exp(-n ** 2 * pref)
    return (4 / math.pi) * total


# ────────────────────── KF-23: 跳扩散修正 ──────────────────────

def detect_session_gaps_5m(df_5m: pd.DataFrame) -> pd.DataFrame:
    """检测 5m 数据中的 session 间隙（相邻 bar 间隔 > 30min 的 open vs prev_close）"""
    df = df_5m.copy().sort_values("datetime")
    df["prev_close"] = df["close"].shift(1)
    df["prev_time"] = df["datetime"].shift(1)
    df["time_diff_min"] = (df["datetime"] - df["prev_time"]).dt.total_seconds() / 60.0
    # Session gap: 相邻 bar 间隔 > 30 min（跨午休、隔夜）
    df["session_gap"] = df["open"] - df["prev_close"]
    df["is_session_gap"] = df["time_diff_min"] > 30
    return df


def run_kf23(csv_dir: Path) -> list[dict]:
    """KF-23: 估计跳空穿透概率并计算修正后的 P_win."""
    print("=" * 120)
    print("KF-23 · 跳扩散修正 — barrier 穿透概率")
    print("=" * 120)

    all_gap_atr = []
    per_symbol = {}

    for _short, full in SYMBOLS_5M:
        path = csv_dir / f"{full}.tqsdk.5m.csv"
        if not path.exists():
            continue
        df = pd.read_csv(path, parse_dates=["datetime"])
        atr = (df["high"] - df["low"]).ewm(span=20).mean()
        df = detect_session_gaps_5m(df)
        df["gap_atr"] = df["session_gap"] / atr
        gaps = df.loc[df["is_session_gap"], "gap_atr"].dropna()
        if len(gaps) > 0:
            all_gap_atr.extend(gaps.abs().tolist())
            per_symbol[full] = {
                "n_gaps": len(gaps),
                "mean_abs": gaps.abs().mean(),
                "std_abs": gaps.abs().std() if len(gaps) > 1 else 0,
                "max_abs": gaps.abs().max(),
            }

    gaps_arr = np.array(all_gap_atr) if all_gap_atr else np.array([0])
    sigma_jump = gaps_arr.std() if len(gaps_arr) > 1 else gaps_arr.mean() + 0.01

    print(f"\n跨 {len(per_symbol)} 品种 session gap 统计:")
    print(f"  总 gap 数: {len(gaps_arr)}")
    print(f"  |gap/ATR| 均值: {gaps_arr.mean():.4f}")
    print(f"  |gap/ATR| 标准差 (σ_jump): {sigma_jump:.4f}")
    print(f"  |gap/ATR| p95: {np.percentile(gaps_arr, 95):.4f}" if len(gaps_arr) > 10 else "")
    print(f"  |gap/ATR| p99: {np.percentile(gaps_arr, 99):.4f}" if len(gaps_arr) > 10 else "")

    # 跳空穿透概率: P(|jump| > K_S) = 2 × Φ(-K_S / σ_jump)
    # 修正: P_win_corrected = P_win_GBM × (1 - P_jump_through) + correction
    # 方向性跳空: P(jump through K_T in favorable direction) - P(jump through K_S in adverse direction)
    print(f"\n## 跳空穿透概率 vs K_S (σ_jump = {sigma_jump:.4f}):")
    print(f"{'K_S':>6} | {'P(穿透止损)':>12} | {'P(穿透止盈)':>12} | {'净穿透ΔP':>10} | {'P_win修正':>10} | {'相对误差':>8}")
    print("-" * 80)

    results = []
    for K_S, RR in KEY_COMBOS:
        K_T = K_S * RR
        # 穿透概率（正态近似）
        p_through_stop = 2 * norm.sf(K_S / sigma_jump) if sigma_jump > 0 else 0  # 双侧
        p_through_take = 2 * norm.sf(K_T / sigma_jump) if sigma_jump > 0 else 0  # 双侧
        # 方向性修正: 跳空穿透止损的方向是 50/50（随机），但已持仓的方向有 50% 概率
        # 净穿透: P(jump 穿过 K_S 的不利侧) - P(jump 穿过 K_T 的有利侧)
        # 实际上对称假设下: ΔP ≈ 0.5 × (p_through_take - p_through_stop)
        # 因为有利方向的跳空增加 P_win，不利方向的跳空减少 P_win
        # 但由于止损更近(K_S < K_T for RR>1 或 K_S > K_T for RR<1)，
        # 不利穿透概率更大
        net_penetration = 0.5 * (p_through_stop - p_through_take)  # 对 P_win 的净减
        # 更精确: 简化为单侧
        p_jump_hit_stop = norm.sf(K_S / sigma_jump) if sigma_jump > 0 else 0
        p_jump_hit_take = norm.sf(K_T / sigma_jump) if sigma_jump > 0 else 0

        p_win_gbm = p_win_infty(0, K_S, K_T)
        p_win_corrected = p_win_gbm * (1 - p_jump_hit_stop - p_jump_hit_take)
        rel_error = (p_win_corrected - p_win_gbm) / p_win_gbm * 100 if p_win_gbm > 0.01 else 0

        results.append({
            "K_S": K_S, "RR": RR, "K_T": K_T,
            "sigma_jump": round(sigma_jump, 4),
            "P_jump_hit_stop": round(p_jump_hit_stop, 6),
            "P_jump_hit_take": round(p_jump_hit_take, 6),
            "P_win_GBM": round(p_win_gbm, 4),
            "P_win_jump_corrected": round(p_win_corrected, 4),
            "correction_abs": round(p_win_corrected - p_win_gbm, 6),
            "correction_pct": round(rel_error, 2),
        })

        print(f"{K_S:>6.1f} | {p_jump_hit_stop:>12.6f} | {p_jump_hit_take:>12.6f} | "
              f"{(p_jump_hit_stop-p_jump_hit_take):>+10.6f} | {p_win_corrected:>10.4f} | {rel_error:>+7.2f}%")

    return results


# ────────────────────── KF-24: σ 时变分析 ──────────────────────

def run_kf24(csv_dir: Path) -> list[dict]:
    """KF-24: σ 时变分析 — 持仓期间 ATR 变化."""
    print("\n\n" + "=" * 120)
    print("KF-24 · σ 时变分析 — 持仓期间 ATR 的 CV 和自相关")
    print("=" * 120)

    results = []
    for _short, full in SYMBOLS_5M:
        path = csv_dir / f"{full}.tqsdk.5m.csv"
        if not path.exists():
            continue
        df = pd.read_csv(path, parse_dates=["datetime"]).sort_values("datetime")
        atr = (df["high"] - df["low"]).ewm(span=20).mean()
        # ATR 的 rolling CV (20-bar window)
        atr_mean = atr.rolling(80).mean()
        atr_std = atr.rolling(80).std()
        atr_cv = atr_std / atr_mean

        # ATR 的 1-lag autocorrelation (Series)
        atr_ret = atr.pct_change()
        atr_ac1_series = atr_ret.autocorr(lag=1)  # scalar, not Series

        # ATR range ratio (max/min over 80-bar window)
        atr_max = atr.rolling(80).max()
        atr_min = atr.rolling(80).min()
        atr_range_ratio = atr_max / atr_min

        valid_cv = atr_cv.dropna()
        valid_rr = atr_range_ratio.dropna()

        if len(valid_cv) < 20:
            continue

        results.append({
            "symbol": full,
            "ATR_mean": round(atr.mean(), 2),
            "ATR_cv_mean": round(valid_cv.mean(), 4),
            "ATR_cv_std": round(valid_cv.std(), 4),
            "ATR_cv_p95": round(valid_cv.quantile(0.95), 4),
            "ATR_autocorr_lag1": round(float(atr_ac1_series), 4) if not math.isnan(atr_ac1_series) else "nan",
            "ATR_range_ratio_mean": round(valid_rr.mean(), 3) if len(valid_rr) > 0 else "nan",
            "ATR_range_ratio_p95": round(valid_rr.quantile(0.95), 3) if len(valid_rr) > 0 else "nan",
        })

    # 汇总
    cv_vals = [r["ATR_cv_mean"] for r in results if isinstance(r["ATR_cv_mean"], (int, float))]
    ac1_vals = [r["ATR_autocorr_lag1"] for r in results if isinstance(r["ATR_autocorr_lag1"], (int, float))]
    rr_vals = [r["ATR_range_ratio_mean"] for r in results if isinstance(r["ATR_range_ratio_mean"], (int, float))]

    print(f"\n{len(results)} 品种 σ 时变统计汇总:")
    print(f"  ATR CV (80-bar window): 均值={np.mean(cv_vals):.4f}, 范围=[{min(cv_vals):.4f}, {max(cv_vals):.4f}]")
    if ac1_vals:
        print(f"  ATR 自相关 (lag-1): 均值={np.mean(ac1_vals):.4f}, 范围=[{min(ac1_vals):.4f}, {max(ac1_vals):.4f}]")
    if rr_vals:
        print(f"  ATR range ratio (max/min 80 bars): 均值={np.mean(rr_vals):.3f}, p95={np.percentile(rr_vals, 95):.3f}")

    # 对 K_S 的影响
    print(f"\n## σ 时变对 K_S 有效宽度的影响:")
    print(f"{'K_S':>6} | {'σ变异':>8} | {'K_S_有效(低CV)':>14} | {'K_S_有效(高CV)':>14} | {'有效宽度变化':>10}")
    print("-" * 70)
    for K_S, RR in KEY_COMBOS:
        K_T = K_S * RR
        cv_low, cv_high = 0.05, 0.25  # 低/高 CV
        # 有效 K_S = K_S × (1 ± CV)
        ks_eff_low = K_S * (1 - cv_low)
        ks_eff_high = K_S * (1 + cv_high)
        width_change = (ks_eff_high - ks_eff_low) / K_S * 100
        print(f"{K_S:>6.1f} | {np.mean(cv_vals):>8.4f} | {ks_eff_low:>14.2f} | {ks_eff_high:>14.2f} | {width_change:>9.0f}%")

    return results


# ────────────────────── KF-25: Trailing Barrier Monte Carlo ──────────────────────

def run_kf25() -> list[dict]:
    """KF-25: Trailing barrier Monte Carlo — fixed vs trailing."""
    print("\n\n" + "=" * 120)
    print("KF-25 · Trailing Barrier Monte Carlo — fixed vs trailing")
    print("=" * 120)

    rng = np.random.default_rng(RANDOM_SEED)
    sigma = SIGMA_5M
    dt = 1.0
    T = MAX_BARS

    results = []
    for K_S, RR in KEY_COMBOS:
        K_T_fixed = K_S * RR
        # Trailing: 止盈跟踪（最高点 - K_T_trail），止损固定
        K_T_trail = K_S * min(RR, 1.0)  # trailing 止盈不超过止损宽度

        for nu_over_sigma in [0.0, 0.03, 0.06]:
            nu = nu_over_sigma * sigma

            # MC simulation
            for barrier_type in ["fixed", "trailing"]:
                pnls = []
                exit_types = []
                max_dds = []

                for _ in range(MC_N_PATHS):
                    x = 0.0
                    x_max = 0.0
                    max_dd = 0.0
                    exited = False

                    for t in range(T):
                        x += nu * dt + sigma * math.sqrt(dt) * rng.standard_normal()
                        x_max = max(x_max, x)
                        dd = x_max - x
                        max_dd = max(max_dd, dd)

                        if barrier_type == "fixed":
                            if x <= -K_S:
                                pnls.append(-K_S)
                                exit_types.append("stop")
                                exited = True
                                break
                            elif x >= K_T_fixed:
                                pnls.append(K_T_fixed)
                                exit_types.append("take")
                                exited = True
                                break
                        else:  # trailing
                            if x <= -K_S:
                                pnls.append(-K_S)
                                exit_types.append("stop")
                                exited = True
                                break
                            elif (x_max - x) >= K_T_trail and x_max > K_T_trail * 0.5:
                                # Trailing stop triggered when drawdown from peak >= K_T_trail
                                pnl = x - (x_max - K_T_trail)
                                pnls.append(pnl)
                                exit_types.append("trail")
                                exited = True
                                break

                    if not exited:
                        pnls.append(x)
                        exit_types.append("time_exit")
                        max_dd = max(max_dd, x_max - x)

                    max_dds.append(max_dd)

                pnls = np.array(pnls)
                p_win = (pnls > 0).mean() if len(pnls) > 0 else 0
                e_gross = pnls.mean() if len(pnls) > 0 else 0
                e_tau = np.mean([i for i, et in enumerate(exit_types)]) if len(exit_types) > 0 else T
                max_dd_mean = np.mean(max_dds)

                results.append({
                    "K_S": K_S, "RR": RR, "nu_over_sigma": nu_over_sigma,
                    "barrier_type": barrier_type,
                    "P_win_MC": round(p_win, 4),
                    "E_gross_MC": round(e_gross, 4),
                    "E_tau_MC": round(e_tau, 1),
                    "max_drawdown_mean": round(max_dd_mean, 4),
                    "n_paths": MC_N_PATHS,
                })

            # 理论值对照
            lam = 2 * nu / (sigma ** 2)
            p_win_thy = p_win_infty(lam, K_S, K_T_fixed)
            eg_thy = e_gross_infty(lam, K_S, K_T_fixed)
            p_tau_gt = p_tau_gt_t_fourier(K_S, K_T_fixed, sigma, T)

    # 打印
    print(f"\n{'K_S':>5} {'RR':>4} {'ν/σ':>6} | {'类型':>8} {'P_win':>7} {'E_gross':>8} {'E[τ]':>6} {'max_dd':>7} | {'P_win_thy':>8} {'ΔP':>7}")
    print("-" * 110)

    for r in sorted(results, key=lambda x: (x["K_S"], x["nu_over_sigma"], x["barrier_type"])):
        thy_p = None
        delta_p = ""
        if r["barrier_type"] == "fixed":
            lam = 2 * (r["nu_over_sigma"] * SIGMA_5M) / (SIGMA_5M ** 2)
            thy_p = p_win_infty(lam, r["K_S"], r["K_S"] * r["RR"])
            delta_p = f"{r['P_win_MC'] - thy_p:>+7.4f}"

        thy_str = f"{thy_p:>8.4f}" if thy_p is not None else "        "

        print(f"{r['K_S']:>5.1f} {r['RR']:>4.1f} {r['nu_over_sigma']:>6.3f} | "
              f"{r['barrier_type']:>8} {r['P_win_MC']:>7.4f} {r['E_gross_MC']:>+8.4f} "
              f"{r['E_tau_MC']:>6.1f} {r['max_drawdown_mean']:>7.4f} | "
              f"{thy_str} {delta_p}")

    return results


# ────────────────────── 主函数 ──────────────────────

def main():
    csv_dir = market_csv_dir()

    r23 = run_kf23(csv_dir)
    r24 = run_kf24(csv_dir)
    r25 = run_kf25()

    # 保存
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = project_data_root() / "research" / "first_passage_boundary"

    for name, data in [
        ("kf23_jump_correction", r23),
        ("kf24_sigma_timevary", r24),
        ("kf25_trailing_barrier_mc", r25),
    ]:
        csv_path = out_dir / f"fpt_{name}_{timestamp}.csv"
        json_path = out_dir / f"fpt_{name}_{timestamp}.json"
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(data[0].keys()) if data else [])
            writer.writeheader()
            for r in data:
                writer.writerow(r)
        with json_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        print(f"\n{name}: {csv_path}")


if __name__ == "__main__":
    main()
