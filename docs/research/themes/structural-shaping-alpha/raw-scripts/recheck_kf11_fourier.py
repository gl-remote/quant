"""KF-11 Fourier 精确 null 重检 · 用 Fourier 精确解修正波动率制度分层归因.

文件级元信息：
- 创建背景：KF-11 原结论基于 T=∞ 近似 P_fpt = K_S/(K_S+K_T)，把长期区 (K_S≥2.5) 的
  P_win_obs < P_fpt 归给"time_exit% 主导"。Fourier 精确解显示：这些格点的 P_win_finiteT
  远低于 P_win_∞（比如 K_S=4/RR=2 @ 5m: P_win_finiteT = 0.006 vs P_∞ = 0.333）。
  因此原"负 z" 可能是相对错误 null 而言，重新以 P_win_finiteT 为 null 计算 z_new。
- 用途：一次性研究脚本。读 vol_regime_stratified_*.json + 三份 boundary_explorer JSON
  推 σ_per_bar，对每 vol 档实 combo 重算 Fourier P_win_finiteT，输出 delta_new = obs - finiteT。
- 注意事项：vol_regime_stratifier 用的是 5m 数据（entry_atr 分位切档），所以 σ 用 5m 值。

研究命题：
    KF-11 「波动率制度分层无正 alpha」在 Fourier 精确 null 下是否仍成立？
    是否有 combo 在 T=∞ null 下 z<0 但在 finiteT null 下 z>0（隐藏正漂移）？

用法：
    uv run python docs/research/themes/structural-shaping-alpha/raw-scripts/recheck_kf11_fourier.py
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime
from pathlib import Path

from data.output_paths import project_data_root

SIGMA_5M = 1.0 / math.sqrt(12)
MAX_BARS = 80
N_TERMS = 100


def p_win_finite_t(k_s: float, k_t: float, sigma: float, t_bars: int) -> float:
    length = k_s + k_t
    a = (math.pi**2) * (sigma**2) * t_bars / (2 * length**2)
    total = 0.0
    for n in range(1, N_TERMS + 1):
        sign = 1 if n % 2 == 1 else -1
        total += (sign / n) * math.sin(n * math.pi * k_s / length) * (1 - math.exp(-(n**2) * a))
    return (2 / math.pi) * total


def _latest_vol_json(out_dir: Path) -> Path:
    candidates = sorted(out_dir.glob("vol_regime_stratified_*.json"))
    if not candidates:
        raise SystemExit("[error] no vol_regime_stratified JSON")
    return candidates[-1]


def stratify(out_dir: Path) -> dict:
    path = _latest_vol_json(out_dir)
    summary = json.loads(path.read_text())
    results: list[dict] = []
    for r in summary["results"]:
        k_s = r["K_S"]
        k_t = r["K_T"]
        rr = r["RR"]
        regime = r["regime"]
        n = r["n_events"]
        p_win_obs = r["P_win_obs"]
        p_time_exit = r["P_time_exit"]

        p_win_infty = k_s / (k_s + k_t)
        p_win_finite = p_win_finite_t(k_s, k_t, SIGMA_5M, MAX_BARS)

        delta_old = p_win_obs - p_win_infty  # 原口径
        delta_new = p_win_obs - p_win_finite  # Fourier 口径

        pwf_clipped = max(1e-9, min(1 - 1e-9, p_win_finite))
        se_new = math.sqrt(pwf_clipped * (1 - pwf_clipped) / n) if n > 0 else float("nan")
        z_new = delta_new / se_new if se_new > 0 else float("nan")

        pinf_clipped = max(1e-9, min(1 - 1e-9, p_win_infty))
        se_old = math.sqrt(pinf_clipped * (1 - pinf_clipped) / n) if n > 0 else float("nan")
        z_old = delta_old / se_old if se_old > 0 else float("nan")

        # 隐藏正漂移：old delta<0 but new delta>0
        sign_flip = (delta_old < 0) and (delta_new > 0)

        results.append({
            "K_S": k_s, "K_T": k_t, "RR": rr, "regime": regime,
            "n_events": n,
            "P_win_obs": p_win_obs,
            "P_win_infty": p_win_infty, "P_win_finiteT": p_win_finite,
            "delta_old": delta_old, "z_old": z_old,
            "delta_new": delta_new, "z_new": z_new,
            "sign_flip": sign_flip,
            "P_time_exit": p_time_exit,
        })

    return {"source_file": str(path), "results": results}


def render_console(summary: dict) -> None:
    print(f"\n{'=' * 120}")
    print("KF-11 Fourier 精确 null 重检 · 24 行波动率制度归因")
    print(f"{'=' * 120}")
    header = ["K_S", "RR", "regime", "n", "P_win", "P_∞", "P_fT",
              "Δ_old", "z_old", "Δ_new", "z_new", "flip?"]
    fmt = "  " + " ".join(f"{h:>9}" for h in header)
    print(fmt)
    print("  " + " ".join("-" * 9 for _ in header))
    for r in summary["results"]:
        flip = "SIGN!" if r["sign_flip"] else ""
        row = [
            f"{r['K_S']:.2f}", f"{r['RR']:.1f}", r["regime"], f"{r['n_events']}",
            f"{r['P_win_obs']:.4f}", f"{r['P_win_infty']:.4f}", f"{r['P_win_finiteT']:.4f}",
            f"{r['delta_old']:+.4f}", f"{r['z_old']:+.2f}",
            f"{r['delta_new']:+.4f}", f"{r['z_new']:+.2f}",
            flip,
        ]
        print("  " + " ".join(f"{v:>9}" for v in row))

    # 统计
    print()
    n_flip = sum(1 for r in summary["results"] if r["sign_flip"])
    n_new_pos_sig = sum(1 for r in summary["results"] if r["delta_new"] > 0 and r["z_new"] > 2)
    n_new_neg_sig = sum(1 for r in summary["results"] if r["delta_new"] < 0 and r["z_new"] < -2)
    n_old_neg_sig = sum(1 for r in summary["results"] if r["delta_old"] < 0 and r["z_old"] < -2)
    print("KF-11 重检摘要:")
    print(f"  符号翻转 (old<0 变 new>0): {n_flip}/24 行 → 隐藏正漂移证据")
    print(f"  Fourier null 下新显著正 (z_new > 2): {n_new_pos_sig}/24")
    print(f"  Fourier null 下新显著负 (z_new < -2): {n_new_neg_sig}/24")
    print(f"  原 T=∞ null 下显著负 (z_old < -2): {n_old_neg_sig}/24")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=str, default=None)
    args = parser.parse_args()
    out_dir = Path(args.out_dir) if args.out_dir else project_data_root() / "research" / "first_passage_boundary"
    summary = stratify(out_dir)
    print(f"加载: {summary['source_file']}")
    render_console(summary)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"recheck_kf11_fourier_{timestamp}.json"
    csv_path = out_dir / f"recheck_kf11_fourier_{timestamp}.csv"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "K_S", "K_T", "RR", "regime", "n_events",
            "P_win_obs", "P_win_infty", "P_win_finiteT",
            "delta_old", "z_old", "delta_new", "z_new", "sign_flip", "P_time_exit",
        ])
        for r in summary["results"]:
            writer.writerow([
                f"{r['K_S']:.2f}", f"{r['K_T']:.2f}", f"{r['RR']:.1f}", r["regime"], r["n_events"],
                f"{r['P_win_obs']:.6f}", f"{r['P_win_infty']:.6f}", f"{r['P_win_finiteT']:.6f}",
                f"{r['delta_old']:+.6f}", f"{r['z_old']:+.4f}",
                f"{r['delta_new']:+.6f}", f"{r['z_new']:+.4f}",
                int(r["sign_flip"]), f"{r['P_time_exit']:.6f}",
            ])

    print(f"\nJSON: {json_path}")
    print(f"CSV:  {csv_path}")


if __name__ == "__main__":
    main()
