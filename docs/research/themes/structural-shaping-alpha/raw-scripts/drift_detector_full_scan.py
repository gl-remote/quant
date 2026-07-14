"""P(τ>T) 独立漂移探测器全 combo 扫描.

文件级元信息：
- 创建背景：§2.13.6 提出了"P(τ>T)_theory vs P_time_exit_obs 差可作独立漂移探测器"
  的方法，但只在 §2.13 举了 5 个例子。本脚本把它扩到全 65 combo × 3 周期 = 195 行，
  作为 P_win 通道的**并行验证**，让下游主题有双通道校准表。
- 用途：一次性研究脚本。读三份完整 65 combo boundary_explorer JSON（timestamp 显式），
  对每行计算：
    (a) P_win 通道: ΔP = P_win_obs - P_win_finiteT（Fourier 精确 null）
    (b) time_exit 通道: Δτ = P_time_exit_obs - P(τ>T)_theory
  两通道方向若一致 → 强漂移信号；若相反 → 归因异常需审视。
- 注意事项：完整 65 combo 数据在 21:10/21:15 时段（不含极端 RR），5m 用 15:31 老 JSON
  （包含完整 K_S 0.5-8.0 × RR 0.5-3.0 网格）。

研究命题：
    是否存在 combo 在 P_win 上不显著但在 P(τ>T) 差上显著？
    是否存在方向相反的 combo（P_win 抬高但 time_exit 也抬高，或反之）？

用法：
    uv run python docs/research/themes/structural-shaping-alpha/raw-scripts/drift_detector_full_scan.py
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
N_TERMS = 100

# 显式指定完整 65 combo JSON (2026-07-14 21:10-21:15 时段扫描)
DEFAULT_FULL_JSON: dict[str, str] = {
    "5m": "boundary_explorer_realcost_20260714_153121.json",
    "15m": "boundary_explorer_realcost_15m_20260714_211025.json",
    "1h": "boundary_explorer_realcost_1h_20260714_211513.json",
}


# ────────────────────── Fourier 精确解 ──────────────────────


def p_win_finite_t(k_s: float, k_t: float, sigma: float, t_bars: int) -> float:
    length = k_s + k_t
    a = (math.pi**2) * (sigma**2) * t_bars / (2 * length**2)
    total = 0.0
    for n in range(1, N_TERMS + 1):
        sign = 1 if n % 2 == 1 else -1
        total += (sign / n) * math.sin(n * math.pi * k_s / length) * (1 - math.exp(-(n**2) * a))
    return (2 / math.pi) * total


def p_tau_gt_t(k_s: float, k_t: float, sigma: float, t_bars: int) -> float:
    length = k_s + k_t
    a = (math.pi**2) * (sigma**2) * t_bars / (2 * length**2)
    total = 0.0
    for n in range(1, N_TERMS + 1, 2):
        total += math.sin(n * math.pi * k_s / length) / n * math.exp(-(n**2) * a)
    return (4 / math.pi) * total


# ────────────────────── 主流程 ──────────────────────


def stratify(out_dir: Path) -> dict:
    all_results: list[dict] = []
    source_files: dict[str, str] = {}
    for interval in INTERVALS:
        json_path = out_dir / DEFAULT_FULL_JSON[interval]
        if not json_path.exists():
            raise SystemExit(f"[error] missing full-grid JSON: {json_path}")
        source_files[interval] = str(json_path)
        summary = json.loads(json_path.read_text())
        sigma = SIGMA_PER_BAR_BY_INTERVAL[interval]

        for r in summary["results"]:
            k_s = r["K_S"]
            k_t = r["K_T"]
            rr = r["RR"]
            if int(r.get("max_bars", MAX_BARS)) != MAX_BARS:
                continue
            n_events = r["n_events"]
            p_win_infty = k_s / (k_s + k_t)
            p_win_finite = p_win_finite_t(k_s, k_t, sigma, MAX_BARS)
            p_tau_theory = p_tau_gt_t(k_s, k_t, sigma, MAX_BARS)
            p_win_obs = r["P_win_obs"]
            p_time_exit_obs = r["P_time_exit_obs"]

            # 两通道
            delta_p_win = p_win_obs - p_win_finite  # 通道 A: 正 = 漂移拉升胜率
            delta_p_time = p_time_exit_obs - p_tau_theory  # 通道 B: 负 = 漂移减少 time_exit

            # 通道 A 的 SE (对 FPT null 使用 std of Binomial)
            pwf_clipped = max(1e-9, min(1 - 1e-9, p_win_finite))
            se_a = math.sqrt(pwf_clipped * (1 - pwf_clipped) / n_events) if n_events > 0 else float("nan")
            z_a = delta_p_win / se_a if se_a > 0 else float("nan")

            # 通道 B 的 SE
            pt_clipped = max(1e-9, min(1 - 1e-9, p_tau_theory))
            se_b = math.sqrt(pt_clipped * (1 - pt_clipped) / n_events) if n_events > 0 else float("nan")
            z_b = delta_p_time / se_b if se_b > 0 else float("nan")

            # 一致性检验：漂移应让 A 变正、B 变负
            drift_consistent = (delta_p_win > 0 and delta_p_time < 0) or (delta_p_win < 0 and delta_p_time > 0)
            channel_a_sig = abs(z_a) > 2.0 if not math.isnan(z_a) else False
            channel_b_sig = abs(z_b) > 2.0 if not math.isnan(z_b) else False

            all_results.append(
                {
                    "K_S": k_s,
                    "K_T": k_t,
                    "RR": rr,
                    "interval": interval,
                    "n_events": n_events,
                    "P_win_infty": p_win_infty,
                    "P_win_finiteT": p_win_finite,
                    "P_win_obs": p_win_obs,
                    "delta_A": delta_p_win,
                    "z_A": z_a,
                    "channel_A_sig": channel_a_sig,
                    "P_tau_gt_T_theory": p_tau_theory,
                    "P_time_exit_obs": p_time_exit_obs,
                    "delta_B": delta_p_time,
                    "z_B": z_b,
                    "channel_B_sig": channel_b_sig,
                    "drift_consistent": drift_consistent,
                    "T_over_T_star": t_star_ratio_val(k_s, k_t, sigma, MAX_BARS),
                }
            )

    return {
        "config": {
            "intervals": INTERVALS,
            "max_bars": MAX_BARS,
            "n_terms": N_TERMS,
        },
        "source_files": source_files,
        "results": all_results,
    }


def t_star_ratio_val(k_s: float, k_t: float, sigma: float, t_bars: int) -> float:
    return t_bars * sigma**2 / (k_s + k_t) ** 2


def render_console(summary: dict) -> None:
    print(f"\n{'=' * 60}")
    print("双通道漂移探测器 · 全 65 combo × 3 周期 = 195 行")
    print(f"{'=' * 60}")
    n_total = len(summary["results"])
    n_a_sig = sum(1 for r in summary["results"] if r["channel_A_sig"])
    n_b_sig = sum(1 for r in summary["results"] if r["channel_B_sig"])
    n_both = sum(1 for r in summary["results"] if r["channel_A_sig"] and r["channel_B_sig"])
    n_a_only = sum(1 for r in summary["results"] if r["channel_A_sig"] and not r["channel_B_sig"])
    n_b_only = sum(1 for r in summary["results"] if not r["channel_A_sig"] and r["channel_B_sig"])
    n_consistent = sum(1 for r in summary["results"] if r["drift_consistent"])
    n_a_pos = sum(1 for r in summary["results"] if r["channel_A_sig"] and r["delta_A"] > 0)
    n_a_neg = sum(1 for r in summary["results"] if r["channel_A_sig"] and r["delta_A"] < 0)
    n_b_neg = sum(1 for r in summary["results"] if r["channel_B_sig"] and r["delta_B"] < 0)
    n_b_pos = sum(1 for r in summary["results"] if r["channel_B_sig"] and r["delta_B"] > 0)

    print(f"\n总行数: {n_total}")
    print(f"通道 A (P_win) 显著: {n_a_sig} (正 {n_a_pos}, 负 {n_a_neg})")
    print(f"通道 B (P(τ>T)) 显著: {n_b_sig} (负 {n_b_neg} → 漂移压缩 time_exit, 正 {n_b_pos} → 漂移拉长)")
    print(f"两通道都显著: {n_both}")
    print(f"仅通道 A 显著: {n_a_only}")
    print(f"仅通道 B 显著: {n_b_only}")
    print(f"漂移方向一致 (A>0 且 B<0 或反之): {n_consistent}")

    # 通道 A 显著但 B 不显著（可能是 P_win 采样偏差）
    print(f"\n【异常组】通道 A 显著但 B 不显著（{n_a_only} 行）:")
    for r in [x for x in summary["results"] if x["channel_A_sig"] and not x["channel_B_sig"]][:12]:
        print(
            f"  K_S={r['K_S']:.2f} RR={r['RR']:.1f} {r['interval']:>3} "
            f"ΔA={r['delta_A']:+.4f} zA={r['z_A']:+.2f} | ΔB={r['delta_B']:+.4f} zB={r['z_B']:+.2f}"
        )

    # 通道 B 显著但 A 不显著（漂移探测器独立捕获）
    print(f"\n【新发现】通道 B 显著但 A 不显著（{n_b_only} 行）:")
    for r in [x for x in summary["results"] if x["channel_B_sig"] and not x["channel_A_sig"]][:12]:
        print(
            f"  K_S={r['K_S']:.2f} RR={r['RR']:.1f} {r['interval']:>3} "
            f"ΔA={r['delta_A']:+.4f} zA={r['z_A']:+.2f} | ΔB={r['delta_B']:+.4f} zB={r['z_B']:+.2f}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=str, default=None)
    args = parser.parse_args()

    out_dir = Path(args.out_dir) if args.out_dir else project_data_root() / "research" / "first_passage_boundary"
    summary = stratify(out_dir)

    print("加载完整 65 combo JSON:")
    for interval, path in summary["source_files"].items():
        print(f"  [{interval}] {path}")

    render_console(summary)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"drift_detector_full_scan_{timestamp}.json"
    csv_path = out_dir / f"drift_detector_full_scan_{timestamp}.csv"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "K_S",
                "K_T",
                "RR",
                "interval",
                "n_events",
                "T_over_T_star",
                "P_win_infty",
                "P_win_finiteT",
                "P_win_obs",
                "delta_A",
                "z_A",
                "channel_A_sig",
                "P_tau_gt_T_theory",
                "P_time_exit_obs",
                "delta_B",
                "z_B",
                "channel_B_sig",
                "drift_consistent",
            ]
        )
        for r in summary["results"]:
            writer.writerow(
                [
                    f"{r['K_S']:.2f}",
                    f"{r['K_T']:.2f}",
                    f"{r['RR']:.1f}",
                    r["interval"],
                    r["n_events"],
                    f"{r['T_over_T_star']:.4f}",
                    f"{r['P_win_infty']:.6f}",
                    f"{r['P_win_finiteT']:.6f}",
                    f"{r['P_win_obs']:.6f}",
                    f"{r['delta_A']:+.6f}",
                    f"{r['z_A']:+.4f}",
                    int(r["channel_A_sig"]),
                    f"{r['P_tau_gt_T_theory']:.6f}",
                    f"{r['P_time_exit_obs']:.6f}",
                    f"{r['delta_B']:+.6f}",
                    f"{r['z_B']:+.4f}",
                    int(r["channel_B_sig"]),
                    int(r["drift_consistent"]),
                ]
            )

    print(f"\nJSON: {json_path}")
    print(f"CSV:  {csv_path}")


if __name__ == "__main__":
    main()
