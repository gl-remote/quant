"""极端盈亏比归因分层器 · Extreme RR Stratifier.

文件级元信息：
- 创建背景：主命题已在 K_S × RR ∈ {0.5..4.0} × {0.5..3.0} 的常规网格下彻底证伪。
  仍需回答最后一个补漏：**当盈亏比放大到 RR ∈ {5.0, 8.0} 极端区间时，
  是否有 combo 出现真实正 alpha？** 直觉理由：极端 RR 让 T* 二次方拉大，
  time_exit% 应飙升，反向压低 P_win_obs——但会不会某个 K_S 出现"胜率虽低
  但赢时极大"的正 mean 结构？此脚本对齐三周期 × 6 K_S × 2 极端 RR 归因。
- 用途：一次性研究脚本。读三份 boundary_explorer_realcost_{5m,15m,1h}_*.json
  的**指定 timestamp**（避免与之前默认 5×2 RR 网格 JSON 混淆），聚焦 RR ∈
  {5.0, 8.0}，输出 6 K_S × 2 RR × 3 周期 = 36 行 P_win / SE / z / time% /
  E_gross / E_net / ν/σ / T*(h) / T/T*。
- 注意事项：脚本按 timestamp 参数或"最新"策略读 JSON；若之前跑过 5×2 网格
  会导致最新 JSON 只有那 5×2——因此本轮跑扩展网格后 timestamp 是最新的。
  归档规则：主命题闭环后连同其他分层脚本一并归档。

研究命题：
    常规 RR ∈ [0.5, 3.0] 已证 martingale 恒等式跨维度稳健成立。
    极端 RR ∈ {5.0, 8.0} 下：
    (a) FPT null 是否仍精确？
    (b) 是否有 (K_S, RR, 周期) combo 出现 mean_net > 0 CI 排除 0？
    (c) time_exit% 是否符合 T/T* < 1 时的剪切预测？

用法：
    uv run python docs/research/themes/structural-shaping-alpha/raw-scripts/extreme_rr_stratifier.py
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
EXTREME_RR = [5.0, 8.0]
K_S_ALL = [0.5, 1.0, 1.5, 2.0, 2.5, 4.0]
INTERVALS = ["5m", "15m", "1h"]

SIGMA_PER_BAR_BY_INTERVAL: dict[str, float] = {
    "5m": 1.0 / math.sqrt(12),
    "15m": 1.0 / math.sqrt(4),
    "1h": 1.0,
}

BAR_HOURS: dict[str, float] = {
    "5m": 5.0 / 60,
    "15m": 15.0 / 60,
    "1h": 1.0,
}


# ────────────────────── FPT 反算 ──────────────────────


def _p_win_infty(lam: float, k_s: float, k_t: float) -> float:
    tol = 1e-10
    if abs(lam) < tol:
        return k_s / (k_s + k_t)
    arg_s = -lam * k_s
    arg_t = lam * k_t
    if arg_t > 50 or arg_s > 50:
        return 1.0 if lam > 0 else 0.0
    if arg_t < -50 or arg_s < -50:
        return 0.0 if lam > 0 else 1.0
    num = math.exp(arg_t) * (1 - math.exp(arg_s))
    den = math.exp(arg_t) - math.exp(arg_s)
    if abs(den) < tol:
        return k_s / (k_s + k_t)
    return num / den


def _solve_implied_nu(p_win_obs: float, k_s: float, k_t: float, sigma_per_bar: float) -> float:
    if not (0 < p_win_obs < 1):
        return float("nan")
    try:

        def f(lam: float) -> float:
            return _p_win_infty(lam, k_s, k_t) - p_win_obs

        for expand_lo, expand_hi in [(-3.0, 3.0), (-5.0, 5.0), (-10.0, 10.0)]:
            if f(expand_lo) * f(expand_hi) < 0:
                lam = brentq(f, expand_lo, expand_hi, xtol=1e-10)
                return lam * sigma_per_bar**2 / 2
        return float("nan")
    except (ValueError, RuntimeError):
        return float("nan")


# ────────────────────── 主流程 ──────────────────────


def _latest_json(out_dir: Path, interval: str) -> Path:
    candidates = sorted(out_dir.glob(f"boundary_explorer_realcost_{interval}_*.json"))
    if not candidates:
        raise SystemExit(f"[error] no boundary_explorer JSON for interval={interval}")
    return candidates[-1]


def _load_row(summary: dict, k_s: float, rr: float) -> dict | None:
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

    # 校验 timestamp 一致（都必须包含 RR 5/8）
    for interval, path in file_paths.items():
        rr_list = sorted({r["RR"] for r in summaries[interval]["results"]})
        if 5.0 not in rr_list or 8.0 not in rr_list:
            raise SystemExit(
                f"[error] {path} does not contain RR 5/8. "
                f"Please run boundary_explorer with --rr-grid including 5,8 first. "
                f"Found RR: {rr_list}"
            )

    results: list[dict] = []
    for k_s in K_S_ALL:
        for rr in EXTREME_RR:
            k_t = rr * k_s
            p_fpt = k_s / (k_s + k_t)
            for interval in INTERVALS:
                r = _load_row(summaries[interval], k_s, rr)
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
                t_over_t_star = r.get("T_star_ratio", float("nan"))
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
                        "T_over_T_star": t_over_t_star,
                    }
                )

    return {
        "config": {
            "extreme_RR": EXTREME_RR,
            "K_S_all": K_S_ALL,
            "intervals": INTERVALS,
            "sigma_per_bar_by_interval": SIGMA_PER_BAR_BY_INTERVAL,
        },
        "source_files": file_paths,
        "results": results,
    }


def render_console(summary: dict) -> None:
    print(f"\n{'=' * 110}")
    print("极端盈亏比归因 · 6 K_S × 2 RR × 3 周期 = 36 行 · FPT(λ=0) null 检验")
    print(f"{'=' * 110}")
    header = [
        "K_S",
        "RR",
        "int",
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
            f"{r['P_time_exit_obs'] * 100:.1f}%",
            f"{r['E_gross_obs']:+.4f}",
            f"{r['E_net_obs']:+.4f}",
            f"{r['nu_over_sigma']:+.4f}",
            f"{r['T_star_hours']:.0f}",
            f"{r['T_over_T_star']:.2f}",
        ]
        print("  " + " ".join(f"{v:>8}" for v in row))

    # 归因摘要
    print()
    print(f"{'=' * 60}")
    print("归因摘要")
    print(f"{'=' * 60}")
    n_total = len(summary["results"])
    n_sig = sum(1 for r in summary["results"] if r["significant_2se"])
    n_e_gross_pos = sum(1 for r in summary["results"] if r["E_gross_obs"] > 0)
    n_e_net_pos = sum(1 for r in summary["results"] if r["E_net_obs"] > 0)
    n_pos_nu = sum(1 for r in summary["results"] if not math.isnan(r["nu_over_sigma"]) and r["nu_over_sigma"] > 0.10)
    n_neg_nu = sum(1 for r in summary["results"] if not math.isnan(r["nu_over_sigma"]) and r["nu_over_sigma"] < -0.10)
    max_time_exit = max(r["P_time_exit_obs"] for r in summary["results"]) * 100
    min_ttratio = min(r["T_over_T_star"] for r in summary["results"])

    print(f"  |z| > 2 显著偏离 FPT: {n_sig}/{n_total}")
    print(f"  E_gross > 0: {n_e_gross_pos}/{n_total}")
    print(f"  E_net > 0（扣成本后仍正）: {n_e_net_pos}/{n_total}")
    print(f"  ν/σ > +0.10 显著正漂移: {n_pos_nu}/{n_total}")
    print(f"  ν/σ < −0.10 显著负漂移: {n_neg_nu}/{n_total}")
    print(f"  time_exit% 极值: {max_time_exit:.1f}%")
    print(f"  T/T* 极值 (min): {min_ttratio:.3f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="极端盈亏比归因分层器")
    parser.add_argument("--out-dir", type=str, default=None)
    args = parser.parse_args()

    out_dir = Path(args.out_dir) if args.out_dir else project_data_root() / "research" / "first_passage_boundary"
    summary = stratify(out_dir)

    print("加载 JSON:")
    for interval, path in summary["source_files"].items():
        print(f"  [{interval}] {path}")
    render_console(summary)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"extreme_rr_stratified_{timestamp}.json"
    csv_path = out_dir / f"extreme_rr_stratified_{timestamp}.csv"
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
