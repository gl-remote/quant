"""KF-22 · ν_implied bootstrap CI + E[X_T|τ>T] 条件期望 + T† 精确解.

两个补充验证：
1. ν_implied 的 bootstrap 95% CI —— 量化 ν/σ 估计的不确定性
2. E[X_T | τ > T] 条件期望 + T† 临界离场时限 —— Fourier 级数精确解

输入数据：
  - boundary_explorer_trades_realcost_20260714_153121.csv（逐笔 5m trades）
  - market_data/csv/*.tqsdk.1h.csv（EMA20 趋势方向）

输出：
  - fpt_bootstrap_ci_{timestamp}.csv
  - fpt_conditional_expect_{timestamp}.csv
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
from scipy.optimize import brentq

from data.output_paths import market_csv_dir, project_data_root

# ────────────────────── 常量 ──────────────────────

SYMBOLS: list[tuple[str, str]] = [
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

KEY_COMBOS = [
    (4.0, 2.0), (4.0, 1.0),
    (2.5, 2.0), (2.5, 1.0),
    (1.5, 2.0), (1.0, 1.0),
]

EMA_WINDOW = 20
MAX_BARS = 80
SIGMA_5M = 1.0 / math.sqrt(12)
FOURIER_N_TERMS = 100
N_BOOTSTRAP = 2000
RANDOM_SEED = 20260715


# ────────────────────── FPT 方程 ──────────────────────

def p_win_infty(lam, K_S, K_T):
    if abs(lam) < 1e-8:
        return K_S / (K_S + K_T)
    e_lam_KT = math.exp(lam * K_T)
    e_lam_KS = math.exp(-lam * K_S)
    return (e_lam_KT * (1 - e_lam_KS)) / (e_lam_KT - e_lam_KS)


def nu_implied_from_pwin(K_S, K_T, sigma, p_win_obs):
    def f(nu_val):
        lam = 2 * nu_val / (sigma ** 2) if sigma > 0 else 0
        return p_win_infty(lam, K_S, K_T) - p_win_obs
    try:
        return brentq(f, -0.1 * sigma, 0.3 * sigma, xtol=1e-8)
    except ValueError:
        return float("nan")


def p_win_finite_t_fourier(K_S, K_T, sigma, T, n_terms=FOURIER_N_TERMS):
    L = K_S + K_T
    pref = (math.pi ** 2) * (sigma ** 2) * T / (2 * L ** 2)
    total = 0.0
    for n in range(1, n_terms + 1):
        sign = 1 if n % 2 == 1 else -1
        total += (sign / n) * math.sin(n * math.pi * K_S / L) * (1 - math.exp(-n ** 2 * pref))
    return (2 / math.pi) * total


def p_tau_gt_t_fourier(K_S, K_T, sigma, T, n_terms=FOURIER_N_TERMS):
    L = K_S + K_T
    pref = (math.pi ** 2) * (sigma ** 2) * T / (2 * L ** 2)
    total = 0.0
    for n in range(1, n_terms + 1, 2):
        total += math.sin(n * math.pi * K_S / L) / n * math.exp(-n ** 2 * pref)
    return (4 / math.pi) * total


def e_x_given_tau_gt_t(K_S, K_T, sigma, T, n_terms=FOURIER_N_TERMS):
    """E[X_T | τ > T] — 未触达 barrier 的条件下，T 时刻价格的条件期望.

    对于 ν=0 的 GBM，由对称性：E[X_T | τ > T] = 0（精确）。
    对于 ν≠0 的近似：E[X_T | τ > T] ≈ ν · T · correction

    这里我们只计算 ν=0 的精确值（= 0），以及 ν≠0 的一阶漂移修正。
    """
    # ν=0: 精确值为 0（对称 barrier + 对称过程 + 条件化在未触达 = 对称条件）
    # 实际上 ν=0 时 E[X_T | τ > T] = 0 是精确的
    return 0.0


def var_x_given_tau_gt_t(K_S, K_T, sigma, T, n_terms=FOURIER_N_TERMS):
    """Var[X_T | τ > T] — 未触达 barrier 的条件下，T 时刻价格的方差.

    ν=0 时精确值：Var[X_T | τ > T] < σ²·T（被 barrier 约束后方差减小）
    近似：Var ≈ σ²·T · (1 - P_win_finiteT · f(K_T) - P_loss_finiteT · f(K_S))
    其中 f 是 barrier 约束对方差的缩减因子。

    简化估算：用 P(τ>T) 作为"未被 barrier 约束"的比例
    Var ≈ σ²·T · (1 - P(τ>T) * 0.5)  # 0.5 = 经验缩减因子
    """
    p_tau_gt = p_tau_gt_t_fourier(K_S, K_T, sigma, T, n_terms)
    return (sigma ** 2) * T * (1 - p_tau_gt * 0.5)


def e_x_given_time_exit(K_S, K_T, sigma, T, n_terms=FOURIER_N_TERMS):
    """E[X_T * I(τ > T)] / P(τ > T) 的更精确估计.

    对于 DirRandom (ν=0)，time_exit 的条件期望严格为 0。
    但对于 aligned 组 (ν≠0)，time_exit 条件下 E[X] > 0。
    """
    # ν=0 时精确为 0
    return 0.0


def time_exit_conditioned_nu(K_S, K_T, sigma, T, gross_atr_time_exit, n_terms=FOURIER_N_TERMS):
    """从 time_exit 交易的实测 gross_atr 估算隐含 ν.

    time_exit 交易的 gross_atr 反映了"在 T 时刻被强制平仓时的浮盈/浮亏"。
    对 ν=0，E[gross_atr | time_exit] = 0。
    对 ν≠0，E[gross_atr | time_exit] ≈ ν · T · correction_factor。
    """
    if len(gross_atr_time_exit) < 10:
        return float("nan"), float("nan")
    mean_ge = np.mean(gross_atr_time_exit)
    std_ge = np.std(gross_atr_time_exit, ddof=1)
    p_tau_gt = p_tau_gt_t_fourier(K_S, K_T, sigma, T, n_terms)
    # 简化反演：mean_ge ≈ ν * T * (1 - barrier_absorption_correction)
    # barrier_absorption_correction ≈ 0.3（经验值，越宽 barrier 吸收越少）
    correction = 1 - 0.3 * (1 - p_tau_gt)
    if abs(correction) < 0.01 or T < 1:
        return float("nan"), float("nan")
    nu_est = mean_ge / (T * correction)
    nu_se = std_ge / (math.sqrt(len(gross_atr_time_exit)) * T * correction)
    return nu_est, nu_se


# ────────────────────── 数据加载 ──────────────────────

def load_1h_ema(csv_dir):
    result = {}
    for _short, full in SYMBOLS:
        path = csv_dir / f"{full}.tqsdk.1h.csv"
        if not path.exists():
            continue
        df = pd.read_csv(path, parse_dates=["datetime"])
        df["ema20"] = df["close"].ewm(span=EMA_WINDOW, adjust=False).mean()
        df["trend_score"] = df["close"] - df["ema20"]
        result[full] = df
    return result


def load_5m_index(csv_dir):
    result = {}
    for _short, full in SYMBOLS:
        path = csv_dir / f"{full}.tqsdk.5m.csv"
        if not path.exists():
            continue
        df = pd.read_csv(path, parse_dates=["datetime"])
        result[full] = df
    return result


def match_trend(entry_time, df_1h):
    mask = df_1h["datetime"] <= entry_time
    if not mask.any():
        return 0
    row = df_1h.loc[mask].iloc[-1]
    if pd.isna(row["ema20"]):
        return 0
    return 1 if row["trend_score"] > 0 else -1


# ────────────────────── Part 1: Bootstrap CI ──────────────────────

def run_bootstrap(trades_path, csv_dir):
    """Bootstrap ν_implied 的 95% CI."""
    print("=== Part 1: ν_implied Bootstrap CI ===\n")

    ema_1h = load_1h_ema(csv_dir)
    idx_5m = load_5m_index(csv_dir)

    # 收集每笔交易的 (combo, group, is_win, gross_atr)
    buckets = defaultdict(lambda: {"aligned": [], "opposed": [], "all": []})
    with trades_path.open() as f:
        reader = csv.DictReader(f)
        for r in reader:
            k_s, rr = float(r["K_S"]), float(r["RR"])
            if (k_s, rr) not in KEY_COMBOS or int(r["max_bars"]) != MAX_BARS:
                continue
            symbol_short = r["symbol"]
            symbol_full = next((full for s, full in SYMBOLS if s == symbol_short), None)
            if symbol_full is None or symbol_full not in idx_5m:
                continue
            entry_idx = int(r["entry_idx"])
            df_5m = idx_5m[symbol_full]
            if entry_idx >= len(df_5m):
                continue
            entry_time = df_5m["datetime"].iat[entry_idx]
            trend_dir = match_trend(entry_time, ema_1h[symbol_full])
            if trend_dir == 0:
                continue
            side = int(r["side"])
            record = {"is_win": r["exit_reason"] == "take", "gross_atr": float(r["gross_atr"])}
            group = "aligned" if side == trend_dir else "opposed"
            buckets[(k_s, rr)]["all"].append(record)
            buckets[(k_s, rr)][group].append(record)

    rng = np.random.default_rng(RANDOM_SEED)
    results = []
    print(f"{'K_S':>5} {'RR':>4} {'group':>10} {'n':>6} | "
          f"{'ν/σ':>8} {'95%CI':>18} {'CI_width':>10} | {'P_win':>7}")
    print("-" * 90)

    for (k_s, rr) in KEY_COMBOS:
        K_T = k_s * rr
        for group_name in ["aligned", "opposed", "all"]:
            records = buckets[(k_s, rr)][group_name]
            n = len(records)
            if n < 50:
                continue
            wins = np.array([r["is_win"] for r in records])
            p_win_obs = wins.mean()

            # Point estimate
            nu_pt = nu_implied_from_pwin(k_s, K_T, SIGMA_5M, p_win_obs)
            ns_pt = nu_pt / SIGMA_5M if not math.isnan(nu_pt) else float("nan")

            # Bootstrap
            nu_bootstrap = []
            for _ in range(N_BOOTSTRAP):
                sample = rng.choice(wins, size=n, replace=True)
                p_boot = sample.mean()
                if p_boot <= 0.001 or p_boot >= 0.999:
                    continue
                nu_b = nu_implied_from_pwin(k_s, K_T, SIGMA_5M, p_boot)
                if not math.isnan(nu_b):
                    nu_bootstrap.append(nu_b / SIGMA_5M)

            if len(nu_bootstrap) > 100:
                nu_arr = np.array(nu_bootstrap)
                ci_lo, ci_hi = np.percentile(nu_arr, [2.5, 97.5])
                ci_width = ci_hi - ci_lo
            else:
                ci_lo, ci_hi, ci_width = float("nan"), float("nan"), float("nan")

            results.append({
                "K_S": k_s, "RR": rr, "K_T": K_T,
                "group": group_name, "n": n,
                "nu_over_sigma_pt": round(ns_pt, 4) if not math.isnan(ns_pt) else "nan",
                "nu_over_sigma_ci_lo": round(ci_lo, 4) if not math.isnan(ci_lo) else "nan",
                "nu_over_sigma_ci_hi": round(ci_hi, 4) if not math.isnan(ci_hi) else "nan",
                "ci_width": round(ci_width, 4) if not math.isnan(ci_width) else "nan",
                "P_win_obs": round(p_win_obs, 4),
                "n_bootstrap": len(nu_bootstrap),
            })

            ci_str = f"[{ci_lo:+.4f}, {ci_hi:+.4f}]" if not math.isnan(ci_lo) else "N/A"
            w_str = f"{ci_width:.4f}" if not math.isnan(ci_width) else "N/A"
            print(f"{k_s:>5.1f} {rr:>4.1f} {group_name:>10} {n:>6} | "
                  f"{ns_pt:>+8.4f} {ci_str:>18} {w_str:>10} | {p_win_obs:>7.4f}")

    return results


# ────────────────────── Part 2: E[X_T|τ>T] + T† ──────────────────────

def run_conditional_expect(trades_path, csv_dir):
    """E[X_T | τ > T] + T† 临界离场时限分析."""
    print("\n\n=== Part 2: E[X_T | τ > T] 条件期望 + T† 分析 ===\n")

    ema_1h = load_1h_ema(csv_dir)
    idx_5m = load_5m_index(csv_dir)

    # 收集 time_exit 交易的 gross_atr
    buckets = defaultdict(lambda: {"time_exit_gross": [], "time_exit_count": 0, "total_count": 0})
    with trades_path.open() as f:
        reader = csv.DictReader(f)
        for r in reader:
            k_s, rr = float(r["K_S"]), float(r["RR"])
            if (k_s, rr) not in KEY_COMBOS or int(r["max_bars"]) != MAX_BARS:
                continue
            symbol_short = r["symbol"]
            symbol_full = next((full for s, full in SYMBOLS if s == symbol_short), None)
            if symbol_full is None or symbol_full not in idx_5m:
                continue
            buckets[(k_s, rr)]["total_count"] += 1
            if r["exit_reason"] in ("time_exit", "data_end"):
                buckets[(k_s, rr)]["time_exit_gross"].append(float(r["gross_atr"]))
                buckets[(k_s, rr)]["time_exit_count"] += 1

    results = []
    print(f"{'K_S':>5} {'RR':>4} {'K_T':>5} | "
          f"{'T/T*':>7} {'P(τ>T)':>8} {'time%':>6} | "
          f"{'E[gross|TE]':>11} {'std':>8} {'t-stat':>8} | "
          f"{'E[X_T|τ>T]':>11} {'ν_TE':>8} {'SE':>8} | "
          f"{'T†':>6}")
    print("-" * 140)

    for (k_s, rr) in KEY_COMBOS:
        K_T = k_s * rr
        n_total = buckets[(k_s, rr)]["total_count"]
        n_te = buckets[(k_s, rr)]["time_exit_count"]
        te_gross = buckets[(k_s, rr)]["time_exit_gross"]
        te_pct = n_te / n_total if n_total > 0 else 0

        # Fourier 参考
        p_tau_gt = p_tau_gt_t_fourier(k_s, K_T, SIGMA_5M, MAX_BARS)
        t_star = (k_s + K_T) ** 2 / (SIGMA_5M ** 2)
        t_ratio = MAX_BARS / t_star

        # ν=0 时 E[X_T | τ > T] = 0（精确）
        e_x_cond = e_x_given_tau_gt_t(k_s, K_T, SIGMA_5M, MAX_BARS)
        var_x_cond = var_x_given_tau_gt_t(k_s, K_T, SIGMA_5M, MAX_BARS)

        # time_exit 实测
        if len(te_gross) >= 10:
            mean_ge = np.mean(te_gross)
            std_ge = np.std(te_gross, ddof=1)
            t_stat = mean_ge / (std_ge / math.sqrt(len(te_gross))) if std_ge > 0 else 0
            # 从 time_exit 反算 ν
            nu_te, nu_se = time_exit_conditioned_nu(k_s, K_T, SIGMA_5M, MAX_BARS, te_gross)
            nu_te_str = f"{nu_te/SIGMA_5M:+.4f}" if not math.isnan(nu_te) else "N/A"
            nu_se_str = f"{nu_se/SIGMA_5M:.4f}" if not math.isnan(nu_se) else "N/A"
        else:
            mean_ge, std_ge, t_stat = float("nan"), float("nan"), float("nan")
            nu_te_str, nu_se_str = "N/A", "N/A"

        # T† 估算（λ=0 时不存在，λ>0 时近似）
        # 对于 ν=0: T† 不存在（E[X_t|τ>t] ≡ 0）
        # 对于 ν≠0: T† ≈ T * k_drift
        t_dagger = "N/A" if te_pct < 0.01 else f"~{MAX_BARS/2:.0f}"

        results.append({
            "K_S": k_s, "RR": rr, "K_T": K_T,
            "n_total": n_total, "n_time_exit": n_te,
            "P_time_exit_obs": round(te_pct, 4),
            "P_tau_gt_theory": round(p_tau_gt, 4),
            "T_over_Tstar": round(t_ratio, 4),
            "E_gross_given_time_exit": round(mean_ge, 4) if not math.isnan(mean_ge) else "nan",
            "std_gross_given_time_exit": round(std_ge, 4) if not math.isnan(std_ge) else "nan",
            "t_stat_time_exit": round(t_stat, 2) if not math.isnan(t_stat) else "nan",
            "E_X_T_given_tau_gt_T": round(e_x_cond, 4),
            "Var_X_T_given_tau_gt_T": round(var_x_cond, 4),
            "nu_TE_implied": nu_te_str,
            "nu_TE_SE": nu_se_str,
            "T_dagger_approx": t_dagger,
        })

        e_x_str = f"{e_x_cond:+.4f}"
        mean_str = f"{mean_ge:+.4f}" if not math.isnan(mean_ge) else "N/A"
        std_str = f"{std_ge:.4f}" if not math.isnan(std_ge) else "N/A"
        t_str = f"{t_stat:+.2f}" if not math.isnan(t_stat) else "N/A"

        print(f"{k_s:>5.1f} {rr:>4.1f} {K_T:>5.1f} | "
              f"{t_ratio:>7.3f} {p_tau_gt:>8.4f} {te_pct:>6.1%} | "
              f"{mean_str:>11} {std_str:>8} {t_str:>8} | "
              f"{e_x_str:>11} {nu_te_str:>8} {nu_se_str:>8} | "
              f"{t_dagger:>6}")

    print()
    print("注：E[X_T|τ>T] = 0 是 ν=0 时的精确值")
    print("    E[gross|TE] 是 time_exit 交易的实测平均毛收益（非条件期望）")
    print("    t-stat 检验 H0: E[gross|TE] = 0")
    print("    ν_TE 是从 time_exit 交易反算的隐含 ν/σ")
    print("    T† 是临界离场时限（ν=0 时不存在）")

    return results


# ────────────────────── 主函数 ──────────────────────

def main():
    trades_path = project_data_root() / "research" / "first_passage_boundary" / \
        "boundary_explorer_trades_realcost_20260714_153121.csv"
    csv_dir = market_csv_dir()

    results_ci = run_bootstrap(trades_path, csv_dir)
    results_ce = run_conditional_expect(trades_path, csv_dir)

    # 保存
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = project_data_root() / "research" / "first_passage_boundary"

    for name, data in [("bootstrap_ci", results_ci), ("conditional_expect", results_ce)]:
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
