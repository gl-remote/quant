"""Fourier 级数精确解 · 有限时间 FPT 归因（KF-15 定钉最后一层）.

文件级元信息：
- 创建背景：v10 已通过三重扎实化确认 KF-15 是"真实微 alpha 通道"。但所有 FPT null
  仍基于 T=∞ 无限时间近似 P_win = K_S/(K_S+K_T)。实测都是有限 T=80 bar，
  仍需回答：**KF-15 的 5.2% 超额中，有多少纯粹来自"有限时间修正"（GBM 在 T=80 下
  P_win_finiteT 与 P_win_∞ 的差），而不是真实漂移？**
- 用途：实现 §4.1 v2 遗留的 Fourier 级数精确解：
  P_win(T) = (2/π) Σ (-1)^{n+1}/n · sin(nπ K_S/L) · (1 - exp(-n²π²σ²T/(2L²)))
  P(τ>T) = (4/π) Σ_{n odd} sin(nπ K_S/L)/n · exp(-n²π²σ²T/(2L²))
  对关键 combo 输出 P_win_finiteT / P_win_∞ / P_win_obs 与 P(τ>T)_finiteT / P_time_exit_obs 对照。
- 注意事项：级数在 n → ∞ 时指数衰减，前 20 项足够 1e-10 精度。σ_per_bar 按周期查表
  与其他分层脚本一致（5m=1/√12, 15m=1/√4, 1h=1）。

研究命题：
    KF-15 的 5.2% (1h) / 6.4% (15m) / 2.4% (5m) P_win 超额，减掉有限时间修正后
    还剩多少？剩下部分才是真实微 alpha 的严格量化。

用法：
    uv run python docs/research/themes/structural-shaping-alpha/raw-scripts/fourier_finite_time_test.py
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime
from pathlib import Path

from data.output_paths import project_data_root

# ────────────────────── 常量 ──────────────────────
INTERVALS = ["5m", "15m", "1h"]
SIGMA_PER_BAR_BY_INTERVAL: dict[str, float] = {
    "5m": 1.0 / math.sqrt(12),
    "15m": 1.0 / math.sqrt(4),
    "1h": 1.0,
}
MAX_BARS = 80
N_TERMS = 100  # Fourier 级数截断项数

# 检验的 combo (与 KF-15 相关)
TARGET_COMBOS = [
    (0.5, 5.0),  # KF-15 核心通道
    (0.5, 8.0),  # 相邻极端 RR
    (1.0, 1.0),  # 对称 martingale 参照
    (1.0, 2.0),  # 常规基准
    (1.0, 5.0),  # 常规 K_S + 极端 RR
    (1.5, 2.0),  # 过渡区
    (2.5, 2.0),  # 长期区
    (4.0, 2.0),  # 深长期区
]


# ────────────────────── Fourier 精确解 ──────────────────────


def p_win_finite_t(k_s: float, k_t: float, sigma_per_bar: float, t_bars: int, n_terms: int = N_TERMS) -> float:
    """有限时间下触达上侧 barrier 的概率（Fourier 级数精确解）.

    P_win(T) = (2/π) Σ (-1)^{n+1}/n · sin(nπ K_S/L) · (1 - exp(-n²π²σ²T/(2L²)))
    """
    length = k_s + k_t
    lambda_prefactor = (math.pi**2) * (sigma_per_bar**2) * t_bars / (2 * length**2)
    total = 0.0
    for n in range(1, n_terms + 1):
        sign = 1 if n % 2 == 1 else -1
        term = (sign / n) * math.sin(n * math.pi * k_s / length) * (1 - math.exp(-(n**2) * lambda_prefactor))
        total += term
    return (2 / math.pi) * total


def p_tau_gt_t(k_s: float, k_t: float, sigma_per_bar: float, t_bars: int, n_terms: int = N_TERMS) -> float:
    """有限时间下未触达任一 barrier 的概率.

    P(τ>T) = (4/π) Σ_{n odd} sin(nπ K_S/L)/n · exp(-n²π²σ²T/(2L²))
    """
    length = k_s + k_t
    lambda_prefactor = (math.pi**2) * (sigma_per_bar**2) * t_bars / (2 * length**2)
    total = 0.0
    for n in range(1, n_terms + 1, 2):  # 奇数
        total += math.sin(n * math.pi * k_s / length) / n * math.exp(-(n**2) * lambda_prefactor)
    return (4 / math.pi) * total


def t_star_ratio(k_s: float, k_t: float, sigma_per_bar: float, t_bars: int) -> float:
    """T / T* ratio, T* = L²/σ² (barrier diffusion time)."""
    length = k_s + k_t
    t_star = length**2 / (sigma_per_bar**2)
    return t_bars / t_star


# ────────────────────── 主流程 ──────────────────────


def _latest_json(out_dir: Path, interval: str) -> Path:
    candidates = sorted(out_dir.glob(f"boundary_explorer_realcost_{interval}_*.json"))
    if candidates:
        return candidates[-1]
    if interval == "5m":
        legacy = sorted(out_dir.glob("boundary_explorer_realcost_2*.json"))
        if legacy:
            return legacy[-1]
    raise SystemExit(f"[error] no boundary_explorer JSON for interval={interval}")


def _load_obs(out_dir: Path) -> dict:
    """加载三周期最新 boundary_explorer 结果，索引到 (K_S, RR, interval)."""
    obs: dict[tuple[float, float, str], dict] = {}
    for interval in INTERVALS:
        path = _latest_json(out_dir, interval)
        summary = json.loads(path.read_text())
        for r in summary["results"]:
            key = (r["K_S"], r["RR"], interval)
            obs[key] = r
    return obs


def stratify(out_dir: Path) -> dict:
    obs = _load_obs(out_dir)
    results: list[dict] = []
    for k_s, rr in TARGET_COMBOS:
        k_t = rr * k_s
        p_win_infty = k_s / (k_s + k_t)
        for interval in INTERVALS:
            sigma = SIGMA_PER_BAR_BY_INTERVAL[interval]
            p_win_finite = p_win_finite_t(k_s, k_t, sigma, MAX_BARS)
            p_tau_gt = p_tau_gt_t(k_s, k_t, sigma, MAX_BARS)
            t_over_t_star = t_star_ratio(k_s, k_t, sigma, MAX_BARS)
            key = (k_s, rr, interval)
            row = obs.get(key)
            if row is None:
                continue
            p_win_obs = row["P_win_obs"]
            p_time_exit_obs = row["P_time_exit_obs"]

            # 有限时间修正贡献：P_win_finite - P_win_infty
            finite_correction = p_win_finite - p_win_infty
            # 实测偏离总量：P_win_obs - P_win_infty
            total_deviation = p_win_obs - p_win_infty
            # 剩余 alpha 归因：P_win_obs - P_win_finite
            residual_alpha = p_win_obs - p_win_finite

            results.append(
                {
                    "K_S": k_s,
                    "K_T": k_t,
                    "RR": rr,
                    "interval": interval,
                    "sigma_per_bar": sigma,
                    "T_bars": MAX_BARS,
                    "T_over_T_star": t_over_t_star,
                    "P_win_infty": p_win_infty,
                    "P_win_finiteT": p_win_finite,
                    "P_win_obs": p_win_obs,
                    "finite_correction": finite_correction,
                    "total_deviation": total_deviation,
                    "residual_alpha": residual_alpha,
                    "correction_pct_of_total": (finite_correction / total_deviation * 100)
                    if abs(total_deviation) > 1e-6
                    else float("nan"),
                    "P_tau_gt_T_theory": p_tau_gt,
                    "P_time_exit_obs": p_time_exit_obs,
                    "time_exit_deviation": p_time_exit_obs - p_tau_gt,
                }
            )

    return {
        "config": {
            "target_combos": TARGET_COMBOS,
            "intervals": INTERVALS,
            "max_bars": MAX_BARS,
            "n_terms": N_TERMS,
        },
        "results": results,
    }


def render_console(summary: dict) -> None:
    print(f"\n{'=' * 130}")
    print("Fourier 精确解归因 · P_win_∞ vs P_win_finiteT vs P_win_obs · 有限时间修正提取真实 alpha")
    print(f"{'=' * 130}")
    header = [
        "K_S",
        "RR",
        "int",
        "T/T*",
        "P_win_∞",
        "P_win_fT",
        "P_win_obs",
        "finite_c",
        "total_dev",
        "residual",
        "corr%tot",
        "τ>T_theo",
        "τ>T_obs",
    ]
    fmt = "  " + " ".join(f"{h:>10}" for h in header)
    print(fmt)
    print("  " + " ".join("-" * 10 for _ in header))
    for r in summary["results"]:
        row = [
            f"{r['K_S']:.2f}",
            f"{r['RR']:.1f}",
            r["interval"],
            f"{r['T_over_T_star']:.2f}",
            f"{r['P_win_infty']:.4f}",
            f"{r['P_win_finiteT']:.4f}",
            f"{r['P_win_obs']:.4f}",
            f"{r['finite_correction']:+.4f}",
            f"{r['total_deviation']:+.4f}",
            f"{r['residual_alpha']:+.4f}",
            f"{r['correction_pct_of_total']:+.1f}%" if not math.isnan(r["correction_pct_of_total"]) else "nan",
            f"{r['P_tau_gt_T_theory']:.4f}",
            f"{r['P_time_exit_obs']:.4f}",
        ]
        print("  " + " ".join(f"{v:>10}" for v in row))

    # KF-15 专项归因摘要
    print()
    print(f"{'=' * 60}")
    print("KF-15 有限时间修正归因（K_S=0.5, RR=5）")
    print(f"{'=' * 60}")
    kf15 = [r for r in summary["results"] if r["K_S"] == 0.5 and r["RR"] == 5.0]
    for r in kf15:
        print(f"  [{r['interval']:>4}] T/T* = {r['T_over_T_star']:5.2f}")
        print(f"         P_win_∞     = {r['P_win_infty']:.4f}  (理论无限时间)")
        print(f"         P_win_finiteT = {r['P_win_finiteT']:.4f}  (Fourier 有限时间修正)")
        print(f"         P_win_obs   = {r['P_win_obs']:.4f}  (实测)")
        print(f"         → 有限时间修正贡献 = {r['finite_correction']:+.4f}")
        print(f"         → 总偏离 (obs - ∞) = {r['total_deviation']:+.4f}")
        print(f"         → 残余真实 alpha   = {r['residual_alpha']:+.4f}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Fourier 精确解归因")
    parser.add_argument("--out-dir", type=str, default=None)
    args = parser.parse_args()

    out_dir = Path(args.out_dir) if args.out_dir else project_data_root() / "research" / "first_passage_boundary"
    summary = stratify(out_dir)
    render_console(summary)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"fourier_finite_time_{timestamp}.json"
    csv_path = out_dir / f"fourier_finite_time_{timestamp}.csv"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "K_S",
                "K_T",
                "RR",
                "interval",
                "sigma_per_bar",
                "T_bars",
                "T_over_T_star",
                "P_win_infty",
                "P_win_finiteT",
                "P_win_obs",
                "finite_correction",
                "total_deviation",
                "residual_alpha",
                "correction_pct_of_total",
                "P_tau_gt_T_theory",
                "P_time_exit_obs",
                "time_exit_deviation",
            ]
        )
        for r in summary["results"]:
            writer.writerow(
                [
                    f"{r['K_S']:.2f}",
                    f"{r['K_T']:.2f}",
                    f"{r['RR']:.1f}",
                    r["interval"],
                    f"{r['sigma_per_bar']:.4f}",
                    r["T_bars"],
                    f"{r['T_over_T_star']:.4f}",
                    f"{r['P_win_infty']:.6f}",
                    f"{r['P_win_finiteT']:.6f}",
                    f"{r['P_win_obs']:.6f}",
                    f"{r['finite_correction']:+.6f}",
                    f"{r['total_deviation']:+.6f}",
                    f"{r['residual_alpha']:+.6f}",
                    f"{r['correction_pct_of_total']:+.4f}" if not math.isnan(r["correction_pct_of_total"]) else "",
                    f"{r['P_tau_gt_T_theory']:.6f}",
                    f"{r['P_time_exit_obs']:.6f}",
                    f"{r['time_exit_deviation']:+.6f}",
                ]
            )

    print(f"\nJSON: {json_path}")
    print(f"CSV:  {csv_path}")


if __name__ == "__main__":
    main()
