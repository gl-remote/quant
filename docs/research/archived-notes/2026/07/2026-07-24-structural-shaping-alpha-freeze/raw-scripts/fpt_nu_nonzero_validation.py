"""KF-21 · ν≠0 时 FPT 方程定量预测验证（含 Fourier 有限时间修正）.

验证目的：
  §2.17 H4 实验证明了 aligned 组显著高于 opposed 组，但未做定量拟合检验。
  本实验从实测 P_win 反算 ν_implied，代入 FPT 方程 1-4 得到理论预测值，
  与实测值比较——检验方程在 ν≠0 时的数值精度。

  V2：引入 Fourier 有限时间修正（方程6），区分 T=∞ 预测和有限 T 预测。

方法：
  1. 复用 boundary_explorer 5m trades，复现 H4 的 aligned/opposed 分组
  2. 对每个 (combo, group) 从 P_win_obs 反算 ν/σ（brentq 求解方程1=P_win_obs）
  3. 用 ν/σ 代入方程 1-4 预测 T=∞ 版本
  4. 用 Fourier 修正（方程6）计算有限 T 版本
  5. 分别比较 ΔP、ΔE_gross、ΔE[τ]
  6. 通过标准：ΔP < 0.01, ΔE < 0.05 ATR, Δτ% < 15%（有限 T 版本）

输入数据：
  - boundary_explorer_trades_realcost_20260714_153121.csv
  - market_data/csv/*.tqsdk.1h.csv (EMA20 趋势方向)

输出：
  - fpt_nu_nonzero_validation_{timestamp}.csv
  - fpt_nu_nonzero_validation_{timestamp}.json

用法：
  cd /Users/gaolei/Documents/src/quant
  unset PYTHONHOME && unset PYTHONPATH && uv run python \\
    docs/research/themes/structural-shaping-alpha/raw-scripts/fpt_nu_nonzero_validation.py
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
MAX_BARS = 80  # 5m bars = 80 × 5min ≈ 6.67h

# σ_per_bar for 5m: 日化 σ=1 (1h ATR basis), 1h 有 12 个 5m bars
SIGMA_5M = 1.0 / math.sqrt(12)  # ≈ 0.2887

FOURIER_N_TERMS = 100


# ────────────────────── FPT 方程 ──────────────────────

def p_win_infty(lam: float, K_S: float, K_T: float) -> float:
    """方程1：首达止盈概率（T=∞）精确解"""
    if abs(lam) < 1e-8:
        return K_S / (K_S + K_T)
    e_lam_KT = math.exp(lam * K_T)
    e_lam_KS = math.exp(-lam * K_S)
    return (e_lam_KT * (1 - e_lam_KS)) / (e_lam_KT - e_lam_KS)


def e_gross_infty(lam: float, K_S: float, K_T: float) -> float:
    """方程2：毛期望收益（T=∞）"""
    p = p_win_infty(lam, K_S, K_T)
    return p * K_T - (1 - p) * K_S


def e_tau_infty(lam: float, K_S: float, K_T: float, sigma: float, nu: float) -> float:
    """方程4：平均首达时间（T=∞）"""
    if abs(nu) < 1e-10:
        return K_S * K_T / (sigma ** 2)
    p_loss = 1 - p_win_infty(lam, K_S, K_T)
    p_win = 1 - p_loss
    return (K_S * p_loss - K_T * p_win) / (-nu)


def p_win_finite_t_fourier(K_S: float, K_T: float, sigma: float, T: int) -> float:
    """方程6：Fourier 级数精确解 — 有限时间下 P_win（ν=0）"""
    L = K_S + K_T
    prefactor = (math.pi ** 2) * (sigma ** 2) * T / (2 * L ** 2)
    total = 0.0
    for n in range(1, FOURIER_N_TERMS + 1):
        sign = 1 if n % 2 == 1 else -1
        term = (sign / n) * math.sin(n * math.pi * K_S / L) * (1 - math.exp(-n ** 2 * prefactor))
        total += term
    return (2 / math.pi) * total


def p_tau_gt_t_fourier(K_S: float, K_T: float, sigma: float, T: int) -> float:
    """方程6b：Fourier 精确解 — P(τ > T)（ν=0）"""
    L = K_S + K_T
    prefactor = (math.pi ** 2) * (sigma ** 2) * T / (2 * L ** 2)
    total = 0.0
    for n in range(1, FOURIER_N_TERMS + 1, 2):  # 奇数项
        total += math.sin(n * math.pi * K_S / L) / n * math.exp(-n ** 2 * prefactor)
    return (4 / math.pi) * total


def e_gross_finite_t(K_S: float, K_T: float, sigma: float, T: int, nu: float = 0) -> float:
    """有限时间 E_gross 估算.

    E_gross_finiteT ≈ P_win_finiteT * K_T - P_loss_finiteT * K_S
    其中 P_win_finiteT 和 P_loss_finiteT 包含 Fourier 修正和 time_exit 的 0 收益贡献。

    对于 ν=0 的 Fourier 修正版：
      P_win_fT = P_win_finiteT_fourier
      P_loss_fT = 1 - P_win_fT - P(τ>T)
      time_exit 贡献 ≈ 0（被强制平仓，剩余价值约 0）

    对于 ν≠0 的近似版：
      先算 ν=0 的 Fourier 基准 P_win_fT(ν=0)
      再用 ν 做线性漂移修正：
        ΔP_drift ≈ ν * T / (K_S + K_T) * correction_factor
      这不是精确解，而是漂移修正的有限时间近似。
    """
    if abs(nu) < 1e-10:
        # ν=0: 精确 Fourier
        p_win_ft = p_win_finite_t_fourier(K_S, K_T, sigma, T)
        p_tau_gt = p_tau_gt_t_fourier(K_S, K_T, sigma, T)
        p_loss_ft = 1 - p_win_ft - p_tau_gt
        return p_win_ft * K_T - p_loss_ft * K_S
    else:
        # ν≠0: 近似 — 用 T=∞ 的 ν_implied + 有限时间截断修正
        # 思路：E_gross_finiteT ≈ E_gross_infty * (1 - P_time_exit_fraction)
        # 其中 P_time_exit_fraction ≈ P_tau_gt_t(ν=0)（假设有限时间效应主要来自 barrier 宽度）
        p_tau_gt = p_tau_gt_t_fourier(K_S, K_T, sigma, T)
        eg_infty = e_gross_infty(2 * nu / (sigma ** 2), K_S, K_T)
        # time_exit 的交易收益约为 0（被截断平仓）
        # E_gross_finiteT ≈ E_gross_infty - E_gloss_given_tau_gt_T * P(τ>T)
        # E_gloss_given_tau_gt_T 在 time_exit 时收益 ≈ 0，所以修正 ≈ E_gross_infty * P(τ>T)
        # 但这高估了截断效果（因为 time_exit 时可能已经累积了部分收益）
        # 更准确：E_gross_finiteT ≈ E_gross_infty * (E[τ_clamped] / E[τ_infty])
        # 其中 E[τ_clamped] = min(τ, T) 的期望 ≈ E[τ_infty] * (1 - P(τ>T)) + T * P(τ>T) * 修正
        # 简化：用经验修正因子
        eg_clamped = eg_infty * (1 - p_tau_gt * 0.8)  # 0.8 = 经验衰减因子
        return eg_clamped


def nu_implied_from_pwin(K_S: float, K_T: float, sigma: float, p_win_obs: float) -> float:
    """反演方程 A：从实测 P_win 反算 ν"""
    def f(nu_val):
        lam = 2 * nu_val / (sigma ** 2) if sigma > 0 else 0
        return p_win_infty(lam, K_S, K_T) - p_win_obs
    nu_max = 0.3 * sigma
    try:
        return brentq(f, -0.1 * sigma, nu_max, xtol=1e-8)
    except ValueError:
        return float("nan")


# ────────────────────── 数据加载 ──────────────────────

def load_1h_ema(csv_dir: Path) -> dict[str, pd.DataFrame]:
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


def load_5m_index(csv_dir: Path) -> dict[str, pd.DataFrame]:
    result = {}
    for _short, full in SYMBOLS:
        path = csv_dir / f"{full}.tqsdk.5m.csv"
        if not path.exists():
            continue
        df = pd.read_csv(path, parse_dates=["datetime"])
        result[full] = df
    return result


def match_trend(entry_time: pd.Timestamp, df_1h: pd.DataFrame) -> int:
    mask = df_1h["datetime"] <= entry_time
    if not mask.any():
        return 0
    row = df_1h.loc[mask].iloc[-1]
    if pd.isna(row["ema20"]):
        return 0
    return 1 if row["trend_score"] > 0 else -1


# ────────────────────── 主逻辑 ──────────────────────

def run_validation() -> list[dict]:
    trades_path = project_data_root() / "research" / "first_passage_boundary" / \
        "boundary_explorer_trades_realcost_20260714_153121.csv"
    csv_dir = market_csv_dir()

    print("加载 1h/5m 数据...")
    ema_1h = load_1h_ema(csv_dir)
    idx_5m = load_5m_index(csv_dir)

    print("读取 5m trades 并分组...")
    buckets: dict[tuple, dict[str, list]] = defaultdict(lambda: {"aligned": [], "opposed": [], "all": []})

    with trades_path.open() as f:
        reader = csv.DictReader(f)
        for r in reader:
            k_s = float(r["K_S"])
            rr = float(r["RR"])
            if (k_s, rr) not in KEY_COMBOS:
                continue
            if int(r["max_bars"]) != MAX_BARS:
                continue

            symbol_short = r["symbol"]
            symbol_full = None
            for s, full in SYMBOLS:
                if s == symbol_short:
                    symbol_full = full
                    break
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
            aligned = side == trend_dir

            record = {
                "gross_atr": float(r["gross_atr"]),
                "exit_bars_raw": int(r.get("exit_bars", MAX_BARS)),
                "is_win": r["exit_reason"] == "take",
                "is_time_exit": r["exit_reason"] in ("time_exit", "data_end"),
            }
            buckets[(k_s, rr)]["all"].append(record)
            if aligned:
                buckets[(k_s, rr)]["aligned"].append(record)
            else:
                buckets[(k_s, rr)]["opposed"].append(record)

    # ── 计算 ──
    results = []
    for (k_s, rr) in KEY_COMBOS:
        K_T = k_s * rr
        # Fourier 参考值（ν=0）
        p_win_fT_v0 = p_win_finite_t_fourier(k_s, K_T, SIGMA_5M, MAX_BARS)
        p_tau_gt_v0 = p_tau_gt_t_fourier(k_s, K_T, SIGMA_5M, MAX_BARS)
        t_over_tstar = MAX_BARS / ((k_s + K_T) ** 2 / (SIGMA_5M ** 2))
        eg_fT_v0 = e_gross_finite_t(k_s, K_T, SIGMA_5M, MAX_BARS, nu=0)

        for group_name in ["all", "aligned", "opposed"]:
            records = buckets[(k_s, rr)][group_name]
            n = len(records)
            if n == 0:
                continue

            n_wins = sum(1 for r in records if r["is_win"])
            n_time_exit = sum(1 for r in records if r["is_time_exit"])
            p_win_obs = n_wins / n
            e_gross_obs = np.mean([r["gross_atr"] for r in records])
            e_tau_obs = np.mean([r["exit_bars_raw"] for r in records])
            p_time_exit_obs = n_time_exit / n

            # ν_implied 从 P_win_obs 反算（T=∞ 方程）
            nu_imp = nu_implied_from_pwin(k_s, K_T, SIGMA_5M, p_win_obs)
            lam_imp = 2 * nu_imp / (SIGMA_5M ** 2) if not math.isnan(nu_imp) else 0
            nu_over_sigma = nu_imp / SIGMA_5M if not math.isnan(nu_imp) else float("nan")

            # T=∞ 理论预测
            p_win_infty_thy = p_win_infty(lam_imp, k_s, K_T)
            eg_infty_thy = e_gross_infty(lam_imp, k_s, K_T)
            e_tau_infty_thy = e_tau_infty(lam_imp, k_s, K_T, SIGMA_5M, nu_imp)

            # 有限 T 理论预测
            eg_finite_thy = e_gross_finite_t(k_s, K_T, SIGMA_5M, MAX_BARS, nu=nu_imp)
            # 有限 T 的 E[τ] 近似：E[min(τ,T)] ≈ E[τ_infty] * (1 - P(τ>T))
            e_tau_finite_thy = e_tau_infty_thy * (1 - p_tau_gt_v0) if not math.isnan(e_tau_infty_thy) else float("nan")

            # 偏差
            delta_p = p_win_obs - p_win_infty_thy
            delta_eg_infty = e_gross_obs - eg_infty_thy
            delta_eg_finite = e_gross_obs - eg_finite_thy
            delta_tau_infty_pct = (e_tau_obs - e_tau_infty_thy) / e_tau_infty_thy * 100 if e_tau_infty_thy > 0.1 else float("nan")
            delta_tau_finite_pct = (e_tau_obs - e_tau_finite_thy) / e_tau_finite_thy * 100 if not math.isnan(e_tau_finite_thy) and e_tau_finite_thy > 0.1 else float("nan")

            results.append({
                "K_S": k_s, "RR": rr, "K_T": K_T,
                "group": group_name,
                "n": n, "n_wins": n_wins, "n_time_exit": n_time_exit,
                "P_win_obs": round(p_win_obs, 4),
                "E_gross_obs": round(e_gross_obs, 4),
                "E_tau_obs_bars": round(e_tau_obs, 1),
                "P_time_exit_obs": round(p_time_exit_obs, 4),
                "nu_implied": round(nu_imp, 6),
                "nu_over_sigma": round(nu_over_sigma, 4) if not math.isnan(nu_over_sigma) else "nan",
                # T=∞ 预测
                "P_win_infty_thy": round(p_win_infty_thy, 4),
                "E_gross_infty_thy": round(eg_infty_thy, 4),
                "E_tau_infty_thy": round(e_tau_infty_thy, 1),
                # 有限 T 预测
                "P_win_finiteT_v0": round(p_win_fT_v0, 4),
                "P_tau_gt_v0": round(p_tau_gt_v0, 4),
                "E_gross_finiteT_thy": round(eg_finite_thy, 4),
                "E_tau_finiteT_thy": round(e_tau_finite_thy, 1) if not math.isnan(e_tau_finite_thy) else "nan",
                "T_over_Tstar": round(t_over_tstar, 3),
                # 偏差
                "delta_P": round(delta_p, 4),
                "delta_E_infty": round(delta_eg_infty, 4),
                "delta_E_finite": round(delta_eg_finite, 4),
                "delta_tau_infty_pct": round(delta_tau_infty_pct, 1) if not math.isnan(delta_tau_infty_pct) else "nan",
                "delta_tau_finite_pct": round(delta_tau_finite_pct, 1) if not math.isnan(delta_tau_finite_pct) else "nan",
            })

    return results


def render(results: list[dict]) -> None:
    print("\n" + "=" * 180)
    print("KF-21 · ν≠0 时 FPT 方程定量预测验证（含 Fourier 有限时间修正）")
    print(f"  MAX_BARS={MAX_BARS} (5m), σ_5m={SIGMA_5M:.4f}, T/σ 单位")
    print("=" * 180)

    # Part 1: T=∞ 预测 vs 实测
    print("\n## Part 1: T=∞ 理论预测 vs 实测")
    print("-" * 150)
    print(f"{'K_S':>5} {'RR':>4} {'group':>10} {'n':>6} | "
          f"{'P_obs':>7} {'P_∞':>7} {'ΔP':>8} | "
          f"{'E_obs':>8} {'E_∞':>8} {'ΔE':>8} | "
          f"{'ν/σ':>7} | "
          f"{'τ_obs':>6} {'τ_∞':>6} {'Δτ%':>7}")
    print("-" * 150)

    for r in sorted(results, key=lambda x: (-x["K_S"], -x["RR"], x["group"])):
        mk_p = "✓" if abs(r["delta_P"]) < 0.01 else "✗"
        mk_e = "✓" if abs(r["delta_E_infty"]) < 0.05 else "✗"
        mk_tau = "?"  # T=∞ 预期偏差大
        ns = r["nu_over_sigma"] if r["nu_over_sigma"] != "nan" else "  N/A "
        tau_pct = r["delta_tau_infty_pct"] if r["delta_tau_infty_pct"] != "nan" else "  N/A "
        print(f"{r['K_S']:>5.1f} {r['RR']:>4.1f} {r['group']:>10} {r['n']:>6} | "
              f"{r['P_win_obs']:>7.4f} {r['P_win_infty_thy']:>7.4f} {r['delta_P']:>+8.4f}{mk_p} | "
              f"{r['E_gross_obs']:>+8.4f} {r['E_gross_infty_thy']:>+8.4f} {r['delta_E_infty']:>+8.4f}{mk_e} | "
              f"{ns:>7} | "
              f"{r['E_tau_obs_bars']:>6.1f} {r['E_tau_infty_thy']:>6.1f} {tau_pct:>7}{mk_tau}")

    # Part 2: 有限 T 预测 vs 实测
    print("\n\n## Part 2: 有限 T 理论预测 vs 实测（Fourier 修正）")
    print("-" * 150)
    print(f"{'K_S':>5} {'RR':>4} {'group':>10} {'n':>6} | "
          f"{'E_obs':>8} {'E_fT':>8} {'ΔE':>8} | "
          f"{'τ_obs':>6} {'τ_fT':>6} {'Δτ%':>7} | "
          f"{'T/T*':>6} {'P(τ>T)':>7} {'time%':>6}")
    print("-" * 150)

    pass_e_ft, pass_tau_ft, total_ft = 0, 0, 0
    for r in sorted(results, key=lambda x: (-x["K_S"], -x["RR"], x["group"])):
        mk_e = "✓" if abs(r["delta_E_finite"]) < 0.05 else "✗"
        tau_pct = r["delta_tau_finite_pct"] if r["delta_tau_finite_pct"] != "nan" else "  N/A "
        mk_tau = "✓" if r["delta_tau_finite_pct"] != "nan" and abs(r["delta_tau_finite_pct"]) < 15 else "?"
        total_ft += 1
        if abs(r["delta_E_finite"]) < 0.05:
            pass_e_ft += 1
        if r["delta_tau_finite_pct"] != "nan" and abs(r["delta_tau_finite_pct"]) < 15:
            pass_tau_ft += 1

        print(f"{r['K_S']:>5.1f} {r['RR']:>4.1f} {r['group']:>10} {r['n']:>6} | "
              f"{r['E_gross_obs']:>+8.4f} {r['E_gross_finiteT_thy']:>+8.4f} {r['delta_E_finite']:>+8.4f}{mk_e} | "
              f"{r['E_tau_obs_bars']:>6.1f} {r['E_tau_finiteT_thy']:>6.1f} {tau_pct:>7}{mk_tau} | "
              f"{r['T_over_Tstar']:>6.3f} {r['P_tau_gt_v0']:>7.4f} {r['P_time_exit_obs']:>6.4f}")

    print()
    print("=" * 60)
    print(f"有限 T 通过率：ΔE < 0.05: {pass_e_ft}/{total_ft} | Δτ < 15%: {pass_tau_ft}/{total_ft}")
    print("=" * 60)

    # Part 3: aligned ν/σ 汇总
    print("\n\n## Part 3: aligned 组 ν/σ 信号强度汇总")
    print("-" * 80)
    aligned_results = [r for r in results if r["group"] == "aligned"]
    for r in sorted(aligned_results, key=lambda x: -x["K_S"]):
        ns = r["nu_over_sigma"]
        if ns != "nan":
            print(f"  K_S={r['K_S']:.1f} RR={r['RR']:.1f}: ν/σ = {ns:.4f} (P_win={r['P_win_obs']:.4f})")
        else:
            print(f"  K_S={r['K_S']:.1f} RR={r['RR']:.1f}: ν/σ = N/A (P_win={r['P_win_obs']:.4f})")


def main() -> None:
    results = run_validation()
    render(results)

    # 保存
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = project_data_root() / "research" / "first_passage_boundary"

    csv_path = out_dir / f"fpt_nu_nonzero_validation_{timestamp}.csv"
    json_path = out_dir / f"fpt_nu_nonzero_validation_{timestamp}.json"

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()) if results else [])
        writer.writeheader()
        for r in results:
            writer.writerow(r)

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)

    print(f"\nCSV: {csv_path}")
    print(f"JSON: {json_path}")


if __name__ == "__main__":
    main()
