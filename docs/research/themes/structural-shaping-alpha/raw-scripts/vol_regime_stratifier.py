"""波动率制度分层器 · Volatility Regime Stratifier.

文件级元信息：
- 创建背景：first-passage-theory-and-evidence.md 已确认 FPT(λ=0) 在 20 品种聚合上
  精确成立（KF-10），但主命题「结构塑形无独立 alpha」仍是"平均意义证伪"。为把
  结论升级到"分层意义证伪"（排除"我们只是把 vol 档拉平均"这个 loose end），
  本脚本按 per-symbol entry_atr 分位切三档，检验各档 P_win 是否偏离 martingale。
- 用途：一次性阶段 2c 研究脚本。读现成 boundary_explorer_trades_*.csv，
  分档统计 P_win / E_net / SE / time_exit% / ν_implied，写入 vol_regime_stratified_*.{json,csv}。
- 注意事项：仅用于同一批 realistic-cost trades 的相对分层归因，不涉及重跑回测；
  分位切点采用 per-symbol 而非全品种，以消除品种间 ATR 绝对水平差异。
  归档规则：主命题闭环后连同 boundary_explorer 一并归档。

研究命题（阶段 2c）：
    结构塑形整体在 DirRandom no-signal baseline 下证伪（KF-1）；
    本脚本进一步检验：是否存在**某个波动率档位**下塑形反而偏离 martingale 恒等式，
    从而把主命题从"平均意义证伪"升级为"分层意义证伪"？

方法：
    1. 读 boundary_explorer_trades_*.csv（现成，无需重跑）
    2. 按 per-symbol entry_atr 的 33/67 分位切三档：低/中/高波
    3. 对每个关键 combo × 每档，统计 n / P_win / E_net / SE / time_exit% / ν_implied
    4. 对比 FPT null（1/(1+RR)），检查 |ΔP| 是否超 2·SE_FPT

关键 combo（覆盖短期区 / 过渡区 / 长期区）：
    K_S ∈ {1.0, 1.5, 2.5, 4.0} × RR ∈ {1.0, 2.0} = 8 combo × 3 档 = 24 行

用法：
    uv run python docs/research/themes/structural-shaping-alpha/raw-scripts/vol_regime_stratifier.py
    uv run python docs/research/themes/structural-shaping-alpha/raw-scripts/vol_regime_stratifier.py --trades path/to/trades.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
from data.output_paths import project_data_root
from scipy.optimize import brentq

# ────────────────────── 常量 ──────────────────────
KEY_K_S = [1.0, 1.5, 2.5, 4.0]
KEY_RR = [1.0, 2.0]
QUANTILE_CUTS = (0.333, 0.667)  # 三档分位切点
SIGMA_PER_BAR = 1.0 / math.sqrt(12)  # 与上游 boundary explorer 一致 (≈0.289)
MAX_BARS = 80  # 与上游一致
REGIME_LABELS = ("low", "mid", "high")


# ────────────────────── FPT 反算（复用 boundary_explorer 逻辑） ──────────────────────


def _p_win_infty(lam: float, K_S: float, K_T: float) -> float:  # noqa: N803  (与上游 boundary_explorer 保持大写符号一致)
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
    """从实测 P_win 反解 ν_implied（返回 nan 表示不收敛/超范围）。"""
    if not (0 < p_win_obs < 1):
        return float("nan")
    try:

        def f(lam: float) -> float:
            return _p_win_infty(lam, K_S, K_T) - p_win_obs

        lo, hi = -3.0, 3.0
        for expand_lo, expand_hi in [(-3.0, 3.0), (-5.0, 5.0), (-10.0, 10.0)]:
            if f(expand_lo) * f(expand_hi) < 0:
                lo, hi = expand_lo, expand_hi
                break
        else:
            return float("nan")
        lam = brentq(f, lo, hi, xtol=1e-10)
        return lam * sigma_per_bar**2 / 2
    except (ValueError, RuntimeError):
        return float("nan")


# ────────────────────── 主流程 ──────────────────────


def stratify(trades_csv: Path) -> dict:
    # 1. 加载
    rows: list[dict] = []
    with trades_csv.open() as f:
        reader = csv.DictReader(f)
        for r in reader:
            k_s = float(r["K_S"])
            rr = float(r["RR"])
            if k_s not in KEY_K_S or rr not in KEY_RR:
                continue
            if int(r["max_bars"]) != MAX_BARS:
                continue
            rows.append(
                {
                    "K_S": k_s,
                    "K_T": float(r["K_T"]),
                    "RR": rr,
                    "symbol": r["symbol"],
                    "sector": r["sector"],
                    "entry_atr": float(r["entry_atr"]),
                    "exit_reason": r["exit_reason"],
                    "net_atr": float(r["net_atr"]),
                }
            )
    if not rows:
        raise SystemExit(f"[error] no matching rows in {trades_csv}")

    # 2. per-symbol entry_atr 分位切点
    atr_by_symbol: dict[str, list[float]] = defaultdict(list)
    seen_events: dict[str, set] = defaultdict(set)  # 同一 symbol 下每 entry 只贡献一次
    for r in rows:
        # entry 唯一性：symbol + entry_atr 组合近似识别（同一 symbol 内 entry_atr 不完全重复）
        # 这里用 (symbol, entry_atr, side_marker) → 简化：直接用所有 combo 共享的 entry_atr 分布
        key = (r["symbol"], round(r["entry_atr"], 6))
        if key in seen_events[r["symbol"]]:
            continue
        seen_events[r["symbol"]].add(key)
        atr_by_symbol[r["symbol"]].append(r["entry_atr"])

    cuts_by_symbol: dict[str, tuple[float, float]] = {}
    for sym, atrs in atr_by_symbol.items():
        arr = np.asarray(atrs)
        q_lo = float(np.quantile(arr, QUANTILE_CUTS[0]))
        q_hi = float(np.quantile(arr, QUANTILE_CUTS[1]))
        cuts_by_symbol[sym] = (q_lo, q_hi)

    def classify(sym: str, atr: float) -> str:
        q_lo, q_hi = cuts_by_symbol[sym]
        if atr <= q_lo:
            return "low"
        if atr <= q_hi:
            return "mid"
        return "high"

    # 3. 分组统计
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        regime = classify(r["symbol"], r["entry_atr"])
        grouped[(r["K_S"], r["RR"], regime)].append(r)

    results: list[dict] = []
    for k_s in KEY_K_S:
        for rr in KEY_RR:
            k_t = rr * k_s
            p_fpt = k_s / (k_s + k_t)  # = 1/(1+RR)
            for regime in REGIME_LABELS:
                bucket = grouped.get((k_s, rr, regime), [])
                n = len(bucket)
                if n == 0:
                    continue
                n_win = sum(1 for x in bucket if x["exit_reason"] == "take")
                n_time = sum(1 for x in bucket if x["exit_reason"] in ("time_exit", "data_end"))
                p_win = n_win / n
                p_time = n_time / n
                e_net = float(np.mean([x["net_atr"] for x in bucket]))
                # 二项 SE 基于 FPT null
                se_fpt = math.sqrt(p_fpt * (1 - p_fpt) / n) if n > 0 else float("nan")
                delta = p_win - p_fpt
                z_score = delta / se_fpt if se_fpt > 0 else float("nan")
                nu_impl = _solve_implied_nu(p_win, k_s, k_t, SIGMA_PER_BAR)
                nu_over_sigma = nu_impl / SIGMA_PER_BAR if not math.isnan(nu_impl) else float("nan")
                results.append(
                    {
                        "K_S": k_s,
                        "K_T": k_t,
                        "RR": rr,
                        "regime": regime,
                        "n_events": n,
                        "P_win_obs": p_win,
                        "P_win_fpt": p_fpt,
                        "delta_P": delta,
                        "SE_fpt": se_fpt,
                        "z_score": z_score,
                        "significant_2se": abs(z_score) > 2.0 if not math.isnan(z_score) else False,
                        "P_time_exit": p_time,
                        "E_net_obs": e_net,
                        "nu_implied": nu_impl,
                        "nu_over_sigma": nu_over_sigma,
                    }
                )

    return {
        "config": {
            "trades_csv": str(trades_csv),
            "key_K_S": KEY_K_S,
            "key_RR": KEY_RR,
            "quantile_cuts": QUANTILE_CUTS,
            "regime_labels": REGIME_LABELS,
            "sigma_per_bar": SIGMA_PER_BAR,
            "max_bars": MAX_BARS,
            "n_symbols": len(cuts_by_symbol),
        },
        "cuts_by_symbol": {s: {"q33": q[0], "q67": q[1]} for s, q in cuts_by_symbol.items()},
        "results": results,
    }


def render_console(summary: dict) -> None:
    print(f"\n{'=' * 80}")
    print("波动率制度分层结果 · 8 combo × 3 档 · FPT(λ=0) null 检验")
    print(f"{'=' * 80}")
    print(f"品种数: {summary['config']['n_symbols']}, 分位切点: 33% / 67% (per-symbol entry_atr)")
    print(f"σ_per_bar: {summary['config']['sigma_per_bar']:.4f}")
    print()
    header = ("K_S", "RR", "regime", "n", "P_win", "FPT", "ΔP", "z", "2SE?", "time%", "E_net", "ν/σ")
    print(
        f"  {header[0]:>5} {header[1]:>4} {header[2]:>6} {header[3]:>5} "
        f"{header[4]:>7} {header[5]:>7} {header[6]:>8} {header[7]:>6} {header[8]:>5} "
        f"{header[9]:>7} {header[10]:>8} {header[11]:>7}"
    )
    print(
        f"  {'-' * 5} {'-' * 4} {'-' * 6} {'-' * 5} {'-' * 7} {'-' * 7} {'-' * 8} {'-' * 6} {'-' * 5} "
        f"{'-' * 7} {'-' * 8} {'-' * 7}"
    )
    for r in summary["results"]:
        sig_flag = "✗" if r["significant_2se"] else "✓"
        print(
            f"  {r['K_S']:>5.2f} {r['RR']:>4.1f} {r['regime']:>6} {r['n_events']:>5d} "
            f"{r['P_win_obs']:>7.4f} {r['P_win_fpt']:>7.4f} {r['delta_P']:>+8.4f} "
            f"{r['z_score']:>+6.2f} {sig_flag:>5} "
            f"{r['P_time_exit'] * 100:>6.2f}% {r['E_net_obs']:>+8.4f} {r['nu_over_sigma']:>+7.4f}"
        )

    print()
    # 归因摘要
    n_total = len(summary["results"])
    n_sig = sum(1 for r in summary["results"] if r["significant_2se"])
    print(f"结论摘要: {n_sig}/{n_total} 行超出 2·SE_FPT 显著性阈值")
    sig_rows = [r for r in summary["results"] if r["significant_2se"]]
    if sig_rows:
        print("显著偏离行:")
        for r in sig_rows:
            direction = "+ν" if r["nu_over_sigma"] > 0 else "-ν"
            print(
                f"  K_S={r['K_S']:.2f} RR={r['RR']:.1f} {r['regime']:>4}: "
                f"ΔP={r['delta_P']:+.4f} (z={r['z_score']:+.2f}), "
                f"time%={r['P_time_exit'] * 100:.1f}%, ν/σ={r['nu_over_sigma']:+.4f} ({direction})"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="波动率制度分层器")
    parser.add_argument(
        "--trades",
        type=str,
        default=None,
        help="trades CSV 路径（默认取最新的 boundary_explorer_trades_realcost_*.csv）",
    )
    args = parser.parse_args()

    out_dir = project_data_root() / "research" / "first_passage_boundary"
    if args.trades:
        trades_csv = Path(args.trades)
    else:
        candidates = sorted(out_dir.glob("boundary_explorer_trades_realcost_*.csv"))
        if not candidates:
            raise SystemExit(f"[error] no trades CSV found in {out_dir}")
        trades_csv = candidates[-1]

    print(f"读取: {trades_csv}")
    summary = stratify(trades_csv)

    render_console(summary)

    # 写文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"vol_regime_stratified_{timestamp}.json"
    csv_path = out_dir / f"vol_regime_stratified_{timestamp}.csv"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "K_S",
                "K_T",
                "RR",
                "regime",
                "n_events",
                "P_win_obs",
                "P_win_fpt",
                "delta_P",
                "SE_fpt",
                "z_score",
                "significant_2se",
                "P_time_exit",
                "E_net_obs",
                "nu_implied",
                "nu_over_sigma",
            ]
        )
        for r in summary["results"]:
            writer.writerow(
                [
                    f"{r['K_S']:.2f}",
                    f"{r['K_T']:.2f}",
                    f"{r['RR']:.1f}",
                    r["regime"],
                    r["n_events"],
                    f"{r['P_win_obs']:.6f}",
                    f"{r['P_win_fpt']:.6f}",
                    f"{r['delta_P']:+.6f}",
                    f"{r['SE_fpt']:.6f}",
                    f"{r['z_score']:+.4f}",
                    int(r["significant_2se"]),
                    f"{r['P_time_exit']:.6f}",
                    f"{r['E_net_obs']:+.6f}",
                    f"{r['nu_implied']:+.6f}",
                    f"{r['nu_over_sigma']:+.6f}",
                ]
            )

    print(f"\nJSON: {json_path}")
    print(f"CSV:  {csv_path}")


if __name__ == "__main__":
    main()
