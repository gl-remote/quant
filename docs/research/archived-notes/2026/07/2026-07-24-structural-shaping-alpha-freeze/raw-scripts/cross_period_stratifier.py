"""跨周期归因分层器 · Cross-Period Stratifier (Stage 2b).

文件级元信息：
- 创建背景：主命题已在 5m 尺度下六维证伪。仍需回答阶段 2b 关键问题：
  **切换到 15m/1h 后，"远距 tail"随物理时间放大是否让塑形出现独立正 alpha？**
  或者反过来：FPT(λ=0) martingale 恒等式是否在 15m/1h 也同样精确成立？
  若跨周期一致 → 主命题彻底跨周期证伪；若长周期有反例 → 需局部深挖。
- 用途：一次性阶段 2b 研究脚本。读 5m/15m/1h 三份 boundary_explorer JSON 汇总，
  对齐 8 关键 combo 输出 P_win / E_gross / E_net / ΔP vs FPT / ν_implied / T*/T
  跨周期对比表。写入 cross_period_stratified_*.{json,csv}。
- 注意事项：每周期 σ_per_bar 不同（5m=0.289, 15m=0.5, 1h=1.0）——按同一 K_S/K_T
  在物理时间上 T* 会显著拉大。这正是 2b 想验证的："同 K_S 在长周期上物理时间放大"
  的机制。归档规则：主命题闭环后连同其他分层脚本一并归档。

研究命题（阶段 2b）：
    5m 下已证 martingale 精确成立。15m/1h 下：
    (a) FPT null 是否仍精确？
    (b) 是否有 combo 在长周期上 mean_gross 显著 > 0 且 ν_implied 显著正？
    (c) time_exit% 与 T*/T 关系跨周期是否一致？

方法：
    1. 读三份 boundary_explorer_realcost_{5m,15m,1h}_*.json（最新 timestamp）
    2. 对 8 关键 combo (K_S∈{1.0,1.5,2.5,4.0} × RR∈{1.0,2.0})，从每份 JSON 提取
       P_win_obs / E_net_obs / E_gross_obs / P_time_exit_obs / T_star / T_star_ratio
    3. 从 P_win_obs 反算 ν_implied（用该周期的 σ_per_bar）
    4. 输出跨周期对比表 + 归因摘要

用法：
    uv run python docs/research/themes/structural-shaping-alpha/raw-scripts/cross_period_stratifier.py
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime
from pathlib import Path

from data.output_paths import project_data_root
from scipy.optimize import brentq

# ────────────────────── 常量 ──────────────────────
KEY_K_S = [1.0, 1.5, 2.5, 4.0]
KEY_RR = [1.0, 2.0]
INTERVALS = ["5m", "15m", "1h"]

# 每 bar 波动率（与 boundary_explorer 保持一致）
SIGMA_PER_BAR_BY_INTERVAL: dict[str, float] = {
    "5m": 1.0 / math.sqrt(12),
    "15m": 1.0 / math.sqrt(4),
    "1h": 1.0,
}

# 每 bar 对应的小时数（用于把 T* 单位转成"小时"以便跨周期比较）
BAR_HOURS: dict[str, float] = {
    "5m": 5.0 / 60,
    "15m": 15.0 / 60,
    "1h": 1.0,
}


# ────────────────────── FPT 反算 ──────────────────────


def _p_win_infty(lam: float, K_S: float, K_T: float) -> float:  # noqa: N803
    tol = 1e-10
    if abs(lam) < tol:
        return K_S / (K_S + K_T)
    arg_s = -lam * K_S
    arg_t = lam * K_T
    if arg_t > 50 or arg_s > 50:
        return 1.0 if lam > 0 else 0.0
    if arg_t < -50 or arg_s < -50:
        return 0.0 if lam > 0 else 1.0
    num = math.exp(arg_t) * (1 - math.exp(arg_s))
    den = math.exp(arg_t) - math.exp(arg_s)
    if abs(den) < tol:
        return K_S / (K_S + K_T)
    return num / den


def _solve_implied_nu(
    p_win_obs: float,
    K_S: float,
    K_T: float,  # noqa: N803
    sigma_per_bar: float,
) -> float:
    if not (0 < p_win_obs < 1):
        return float("nan")
    try:

        def f(lam: float) -> float:
            return _p_win_infty(lam, K_S, K_T) - p_win_obs

        for expand_lo, expand_hi in [(-3.0, 3.0), (-5.0, 5.0), (-10.0, 10.0)]:
            if f(expand_lo) * f(expand_hi) < 0:
                lam = brentq(f, expand_lo, expand_hi, xtol=1e-10)
                return lam * sigma_per_bar**2 / 2
        return float("nan")
    except (ValueError, RuntimeError):
        return float("nan")


# ────────────────────── 主流程 ──────────────────────


def _latest_json(out_dir: Path, interval: str) -> Path:
    # 新格式: boundary_explorer_realcost_{interval}_*.json
    candidates = sorted(out_dir.glob(f"boundary_explorer_realcost_{interval}_*.json"))
    if candidates:
        return candidates[-1]
    # 兼容老 5m 命名（interval 未嵌入文件名，直接 boundary_explorer_realcost_YYYYMMDD_*.json）
    if interval == "5m":
        legacy = sorted(out_dir.glob("boundary_explorer_realcost_2*.json"))
        if legacy:
            return legacy[-1]
    raise SystemExit(f"[error] no boundary_explorer JSON for interval={interval} in {out_dir}")


def _load_combo_row(summary: dict, k_s: float, rr: float) -> dict | None:
    for r in summary["results"]:
        if abs(r["K_S"] - k_s) < 1e-9 and abs(r["RR"] - rr) < 1e-9:
            return r
    return None


def stratify(out_dir: Path) -> dict:
    summaries: dict[str, dict] = {}
    file_paths: dict[str, str] = {}
    for interval in INTERVALS:
        path = _latest_json(out_dir, interval)
        summaries[interval] = json.loads(path.read_text())
        file_paths[interval] = str(path)

    results: list[dict] = []
    for k_s in KEY_K_S:
        for rr in KEY_RR:
            k_t = rr * k_s
            p_fpt = k_s / (k_s + k_t)
            for interval in INTERVALS:
                r = _load_combo_row(summaries[interval], k_s, rr)
                if r is None:
                    continue
                sigma = SIGMA_PER_BAR_BY_INTERVAL[interval]
                bar_h = BAR_HOURS[interval]
                p_win_obs = r["P_win_obs"]
                n_events = r["n_events"]
                se_fpt = math.sqrt(p_fpt * (1 - p_fpt) / n_events) if n_events > 0 else float("nan")
                delta_p = p_win_obs - p_fpt
                z = delta_p / se_fpt if se_fpt > 0 else float("nan")
                nu_impl = _solve_implied_nu(p_win_obs, k_s, k_t, sigma)
                nu_over_sigma = nu_impl / sigma if not math.isnan(nu_impl) else float("nan")
                t_star_bars = r.get("T_star", float("nan"))
                t_star_hours = t_star_bars * bar_h
                t_over_t_star = r.get("T_star_ratio", float("nan"))  # max_bars / T_star

                results.append(
                    {
                        "K_S": k_s,
                        "K_T": k_t,
                        "RR": rr,
                        "interval": interval,
                        "sigma_per_bar": sigma,
                        "bar_hours": bar_h,
                        "n_events": n_events,
                        "P_win_obs": p_win_obs,
                        "P_win_fpt": p_fpt,
                        "delta_P": delta_p,
                        "SE_fpt": se_fpt,
                        "z_score": z,
                        "significant_2se": abs(z) > 2.0 if not math.isnan(z) else False,
                        "P_time_exit_obs": r["P_time_exit_obs"],
                        "E_net_obs": r["E_net_obs"],
                        "E_gross_obs": r["E_gross_obs"],
                        "nu_implied": nu_impl,
                        "nu_over_sigma": nu_over_sigma,
                        "T_star_bars": t_star_bars,
                        "T_star_hours": t_star_hours,
                        "T_over_T_star": t_over_t_star,  # max_bars / T_star (即 T / T*)
                    }
                )

    return {
        "config": {
            "intervals": INTERVALS,
            "key_K_S": KEY_K_S,
            "key_RR": KEY_RR,
            "sigma_per_bar_by_interval": SIGMA_PER_BAR_BY_INTERVAL,
            "bar_hours_by_interval": BAR_HOURS,
        },
        "source_files": file_paths,
        "results": results,
    }


def render_console(summary: dict) -> None:
    print(f"\n{'=' * 110}")
    print("跨周期归因 · 8 关键 combo × 3 周期 · FPT(λ=0) null 检验")
    print(f"{'=' * 110}")
    print("每周期 σ/bar： 5m=0.289, 15m=0.500, 1h=1.000")
    print()
    header = [
        "K_S",
        "RR",
        "interval",
        "n",
        "P_win",
        "FPT",
        "ΔP",
        "z",
        "2SE?",
        "time%",
        "E_gross",
        "E_net",
        "ν/σ",
        "T*(h)",
        "T/T*",
    ]
    fmt = "  " + " ".join(f"{h:>8}" for h in header)
    print(fmt)
    print("  " + " ".join("-" * 8 for _ in header))
    for r in summary["results"]:
        sig = "✗" if r["significant_2se"] else "✓"
        row = [
            f"{r['K_S']:.2f}",
            f"{r['RR']:.1f}",
            r["interval"],
            f"{r['n_events']}",
            f"{r['P_win_obs']:.4f}",
            f"{r['P_win_fpt']:.4f}",
            f"{r['delta_P']:+.4f}",
            f"{r['z_score']:+.2f}",
            sig,
            f"{r['P_time_exit_obs'] * 100:.2f}%",
            f"{r['E_gross_obs']:+.4f}",
            f"{r['E_net_obs']:+.4f}",
            f"{r['nu_over_sigma']:+.4f}",
            f"{r['T_star_hours']:.1f}",
            f"{r['T_over_T_star']:.2f}",
        ]
        print("  " + " ".join(f"{v:>8}" for v in row))

    print()
    # 归因摘要
    n_total = len(summary["results"])
    n_sig = sum(1 for r in summary["results"] if r["significant_2se"])
    n_pos_nu = sum(1 for r in summary["results"] if not math.isnan(r["nu_over_sigma"]) and r["nu_over_sigma"] > 0.10)
    n_neg_nu = sum(1 for r in summary["results"] if not math.isnan(r["nu_over_sigma"]) and r["nu_over_sigma"] < -0.10)
    print("归因摘要：")
    print(f"  |z| > 2 显著偏离: {n_sig}/{n_total}")
    print(f"  ν/σ > +0.10 显著正漂移: {n_pos_nu}/{n_total}")
    print(f"  ν/σ < −0.10 显著负漂移: {n_neg_nu}/{n_total}")

    # per-interval 摘要
    for interval in INTERVALS:
        subset = [r for r in summary["results"] if r["interval"] == interval]
        if not subset:
            continue
        n_short = sum(1 for r in subset if r["K_S"] <= 1.5)
        n_short_sig = sum(1 for r in subset if r["K_S"] <= 1.5 and r["significant_2se"])
        max_nu_abs = max(abs(r["nu_over_sigma"]) for r in subset if not math.isnan(r["nu_over_sigma"]))
        print(f"  [{interval}] 短期区显著偏离: {n_short_sig}/{n_short}, |ν/σ| 极值 = {max_nu_abs:.4f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="跨周期归因分层器")
    parser.add_argument(
        "--out-dir",
        type=str,
        default=None,
        help="boundary_explorer JSON 所在目录（默认 project_data/research/first_passage_boundary）",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir) if args.out_dir else project_data_root() / "research" / "first_passage_boundary"
    summary = stratify(out_dir)

    print("加载 JSON:")
    for interval, path in summary["source_files"].items():
        print(f"  [{interval}] {path}")

    render_console(summary)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"cross_period_stratified_{timestamp}.json"
    csv_path = out_dir / f"cross_period_stratified_{timestamp}.csv"
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
                "bar_hours",
                "n_events",
                "P_win_obs",
                "P_win_fpt",
                "delta_P",
                "SE_fpt",
                "z_score",
                "significant_2se",
                "P_time_exit_obs",
                "E_net_obs",
                "E_gross_obs",
                "nu_implied",
                "nu_over_sigma",
                "T_star_bars",
                "T_star_hours",
                "T_over_T_star",
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
                    f"{r['bar_hours']:.4f}",
                    r["n_events"],
                    f"{r['P_win_obs']:.6f}",
                    f"{r['P_win_fpt']:.6f}",
                    f"{r['delta_P']:+.6f}",
                    f"{r['SE_fpt']:.6f}",
                    f"{r['z_score']:+.4f}",
                    int(r["significant_2se"]),
                    f"{r['P_time_exit_obs']:.6f}",
                    f"{r['E_net_obs']:+.6f}",
                    f"{r['E_gross_obs']:+.6f}",
                    f"{r['nu_implied']:+.6f}",
                    f"{r['nu_over_sigma']:+.6f}",
                    f"{r['T_star_bars']:.4f}",
                    f"{r['T_star_hours']:.4f}",
                    f"{r['T_over_T_star']:.4f}",
                ]
            )

    print(f"\nJSON: {json_path}")
    print(f"CSV:  {csv_path}")


if __name__ == "__main__":
    main()
