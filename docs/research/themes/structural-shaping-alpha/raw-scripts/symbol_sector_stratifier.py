"""品种 / 板块归因分层器 · Symbol × Sector Attribution Stratifier.

文件级元信息：
- 创建背景：first-passage-theory-and-evidence.md §2.6.2 曾留下"per-symbol 分析列入 v2"
  的欠账——现有实证是 20 品种聚合级 (n=4922)，仍需回答"是否有单一品种大幅背离
  martingale 恒等式主导了聚合结果？"以及"5 大板块是否结论一致？"。若答案都是否定的，
  主命题从"分层证伪 (vol × K_S × RR)"再升级为"品种一致证伪"。
- 用途：一次性研究脚本。读现成 boundary_explorer_trades_*.csv，按 (K_S, RR, symbol)
  与 (K_S, RR, sector) 分组统计 n / P_win / SE_FPT / z-score / time_exit% / ν_implied，
  输出 symbol_sector_stratified_*.{json,csv}。
- 注意事项：仅用于同一批 realistic-cost trades 的相对分层归因，不涉及重跑回测；
  聚焦 8 关键 combo (与 vol_regime 保持一致口径) 避免 65 combo × 20 品种 = 1300 行淹没信号；
  归档规则：主命题闭环后连同 boundary_explorer / vol_regime_stratifier 一并归档。

研究命题（v2 补齐）：
    §2.7 已确认波动率制度不改变主命题；本脚本回答：
    (a) 20 个单一品种是否都遵守 martingale 恒等式？
    (b) 5 大板块（black / metals / energy_chem / agri_dce / agri_czce）结论是否一致？

方法：
    1. 读 boundary_explorer_trades_*.csv（现成）
    2. 对 8 关键 combo：K_S ∈ {1.0, 1.5, 2.5, 4.0} × RR ∈ {1.0, 2.0}
    3. 分两层：
       - 板块级：按 sector 分组，输出 5 sectors × 8 combo = 40 行
       - 品种级：按 symbol 分组，输出 20 symbols × 8 combo = 160 行
    4. 每行输出 n / P_win / SE_FPT / z / time_exit% / ν_implied
    5. 判据：|z| > 2 视为显著偏离 FPT null

用法：
    uv run python docs/research/themes/structural-shaping-alpha/raw-scripts/symbol_sector_stratifier.py
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from data.output_paths import project_data_root
from scipy.optimize import brentq

# ────────────────────── 常量 ──────────────────────
KEY_K_S = [1.0, 1.5, 2.5, 4.0]
KEY_RR = [1.0, 2.0]
SIGMA_PER_BAR = 1.0 / math.sqrt(12)  # 与上游 boundary explorer 一致 (≈0.289)
MAX_BARS = 80


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


def stratify(trades_csv: Path) -> dict:
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
                    "exit_reason": r["exit_reason"],
                }
            )
    if not rows:
        raise SystemExit(f"[error] no matching rows in {trades_csv}")

    # 按 (K_S, RR, symbol) 与 (K_S, RR, sector) 分组
    by_symbol: dict[tuple, list[dict]] = defaultdict(list)
    by_sector: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        by_symbol[(r["K_S"], r["RR"], r["symbol"])].append(r)
        by_sector[(r["K_S"], r["RR"], r["sector"])].append(r)

    def summarize(bucket: list[dict], k_s: float, rr: float) -> dict:
        k_t = rr * k_s
        p_fpt = k_s / (k_s + k_t)
        n = len(bucket)
        n_win = sum(1 for x in bucket if x["exit_reason"] == "take")
        n_time = sum(1 for x in bucket if x["exit_reason"] in ("time_exit", "data_end"))
        p_win = n_win / n if n > 0 else float("nan")
        p_time = n_time / n if n > 0 else float("nan")
        se_fpt = math.sqrt(p_fpt * (1 - p_fpt) / n) if n > 0 else float("nan")
        delta = p_win - p_fpt
        z_score = delta / se_fpt if se_fpt > 0 else float("nan")
        nu_impl = _solve_implied_nu(p_win, k_s, k_t, SIGMA_PER_BAR)
        return {
            "n_events": n,
            "P_win_obs": p_win,
            "P_win_fpt": p_fpt,
            "delta_P": delta,
            "SE_fpt": se_fpt,
            "z_score": z_score,
            "significant_2se": abs(z_score) > 2.0 if not math.isnan(z_score) else False,
            "P_time_exit": p_time,
            "nu_implied": nu_impl,
            "nu_over_sigma": nu_impl / SIGMA_PER_BAR if not math.isnan(nu_impl) else float("nan"),
        }

    sector_results: list[dict] = []
    for k_s in KEY_K_S:
        for rr in KEY_RR:
            sectors = {r["sector"] for r in rows}
            for sector in sorted(sectors):
                bucket = by_sector.get((k_s, rr, sector), [])
                if not bucket:
                    continue
                sector_results.append(
                    {
                        "K_S": k_s,
                        "K_T": rr * k_s,
                        "RR": rr,
                        "sector": sector,
                        **summarize(bucket, k_s, rr),
                    }
                )

    symbol_results: list[dict] = []
    for k_s in KEY_K_S:
        for rr in KEY_RR:
            symbol_sector = {(r["symbol"], r["sector"]) for r in rows}
            for symbol, sector in sorted(symbol_sector):
                bucket = by_symbol.get((k_s, rr, symbol), [])
                if not bucket:
                    continue
                symbol_results.append(
                    {
                        "K_S": k_s,
                        "K_T": rr * k_s,
                        "RR": rr,
                        "symbol": symbol,
                        "sector": sector,
                        **summarize(bucket, k_s, rr),
                    }
                )

    return {
        "config": {
            "trades_csv": str(trades_csv),
            "key_K_S": KEY_K_S,
            "key_RR": KEY_RR,
            "sigma_per_bar": SIGMA_PER_BAR,
            "max_bars": MAX_BARS,
        },
        "sector_results": sector_results,
        "symbol_results": symbol_results,
    }


def render_console(summary: dict) -> None:
    print(f"\n{'=' * 80}")
    print("板块级归因（5 sectors × 8 combo）· FPT(λ=0) null 检验")
    print(f"{'=' * 80}")
    print(
        f"  {'K_S':>5} {'RR':>4} {'sector':>13} {'n':>5} "
        f"{'P_win':>7} {'FPT':>7} {'ΔP':>8} {'z':>6} {'2SE?':>5} "
        f"{'time%':>7} {'ν/σ':>7}"
    )
    print(
        f"  {'-' * 5} {'-' * 4} {'-' * 13} {'-' * 5} {'-' * 7} {'-' * 7} {'-' * 8} "
        f"{'-' * 6} {'-' * 5} {'-' * 7} {'-' * 7}"
    )
    for r in summary["sector_results"]:
        sig = "✗" if r["significant_2se"] else "✓"
        print(
            f"  {r['K_S']:>5.2f} {r['RR']:>4.1f} {r['sector']:>13} {r['n_events']:>5d} "
            f"{r['P_win_obs']:>7.4f} {r['P_win_fpt']:>7.4f} {r['delta_P']:>+8.4f} "
            f"{r['z_score']:>+6.2f} {sig:>5} "
            f"{r['P_time_exit'] * 100:>6.2f}% {r['nu_over_sigma']:>+7.4f}"
        )

    # 品种级：仅打印显著偏离行
    print()
    print(f"{'=' * 80}")
    print("品种级归因（20 symbols × 8 combo = 160 行）· 仅列出显著偏离")
    print(f"{'=' * 80}")
    sig_syms = [r for r in summary["symbol_results"] if r["significant_2se"]]
    if not sig_syms:
        print("  (无任何品种级显著偏离)")
    else:
        print(
            f"  {'K_S':>5} {'RR':>4} {'symbol':>10} {'sector':>13} {'n':>4} "
            f"{'P_win':>7} {'ΔP':>8} {'z':>6} {'time%':>7} {'ν/σ':>7}"
        )
        for r in sig_syms:
            print(
                f"  {r['K_S']:>5.2f} {r['RR']:>4.1f} {r['symbol']:>10} {r['sector']:>13} {r['n_events']:>4d} "
                f"{r['P_win_obs']:>7.4f} {r['delta_P']:>+8.4f} {r['z_score']:>+6.2f} "
                f"{r['P_time_exit'] * 100:>6.2f}% {r['nu_over_sigma']:>+7.4f}"
            )

    # 统计
    print()
    sect_total = len(summary["sector_results"])
    sect_sig = sum(1 for r in summary["sector_results"] if r["significant_2se"])
    sym_total = len(summary["symbol_results"])
    sym_sig = sum(1 for r in summary["symbol_results"] if r["significant_2se"])
    print(f"板块级: {sect_sig}/{sect_total} 显著偏离")
    print(f"品种级: {sym_sig}/{sym_total} 显著偏离")

    # 短期区（K_S ≤ 1.5）分层证伪核对
    short_sect = [r for r in summary["sector_results"] if r["K_S"] <= 1.5]
    short_sect_sig = sum(1 for r in short_sect if r["significant_2se"])
    short_sym = [r for r in summary["symbol_results"] if r["K_S"] <= 1.5]
    short_sym_sig = sum(1 for r in short_sym if r["significant_2se"])
    print(f"  短期区 (K_S ≤ 1.5): 板块 {short_sect_sig}/{len(short_sect)} · 品种 {short_sym_sig}/{len(short_sym)}")

    # ν 极值
    nus = [r["nu_over_sigma"] for r in summary["symbol_results"] if not math.isnan(r["nu_over_sigma"])]
    if nus:
        print(
            f"  品种级 |ν/σ| 极值: max={max(abs(x) for x in nus):.4f}, "
            f"|ν/σ| ≤ 0.10 的比例: {sum(1 for x in nus if abs(x) <= 0.10) / len(nus) * 100:.1f}%"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="品种 / 板块归因分层器")
    parser.add_argument(
        "--trades", type=str, default=None, help="trades CSV 路径（默认取最新 boundary_explorer_trades_realcost_*.csv）"
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

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"symbol_sector_stratified_{timestamp}.json"
    sect_csv = out_dir / f"symbol_sector_stratified_sector_{timestamp}.csv"
    sym_csv = out_dir / f"symbol_sector_stratified_symbol_{timestamp}.csv"

    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    with sect_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "K_S",
                "K_T",
                "RR",
                "sector",
                "n_events",
                "P_win_obs",
                "P_win_fpt",
                "delta_P",
                "SE_fpt",
                "z_score",
                "significant_2se",
                "P_time_exit",
                "nu_implied",
                "nu_over_sigma",
            ]
        )
        for r in summary["sector_results"]:
            writer.writerow(
                [
                    f"{r['K_S']:.2f}",
                    f"{r['K_T']:.2f}",
                    f"{r['RR']:.1f}",
                    r["sector"],
                    r["n_events"],
                    f"{r['P_win_obs']:.6f}",
                    f"{r['P_win_fpt']:.6f}",
                    f"{r['delta_P']:+.6f}",
                    f"{r['SE_fpt']:.6f}",
                    f"{r['z_score']:+.4f}",
                    int(r["significant_2se"]),
                    f"{r['P_time_exit']:.6f}",
                    f"{r['nu_implied']:+.6f}",
                    f"{r['nu_over_sigma']:+.6f}",
                ]
            )
    with sym_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "K_S",
                "K_T",
                "RR",
                "symbol",
                "sector",
                "n_events",
                "P_win_obs",
                "P_win_fpt",
                "delta_P",
                "SE_fpt",
                "z_score",
                "significant_2se",
                "P_time_exit",
                "nu_implied",
                "nu_over_sigma",
            ]
        )
        for r in summary["symbol_results"]:
            writer.writerow(
                [
                    f"{r['K_S']:.2f}",
                    f"{r['K_T']:.2f}",
                    f"{r['RR']:.1f}",
                    r["symbol"],
                    r["sector"],
                    r["n_events"],
                    f"{r['P_win_obs']:.6f}",
                    f"{r['P_win_fpt']:.6f}",
                    f"{r['delta_P']:+.6f}",
                    f"{r['SE_fpt']:.6f}",
                    f"{r['z_score']:+.4f}",
                    int(r["significant_2se"]),
                    f"{r['P_time_exit']:.6f}",
                    f"{r['nu_implied']:+.6f}",
                    f"{r['nu_over_sigma']:+.6f}",
                ]
            )

    print(f"\nJSON:       {json_path}")
    print(f"Sector CSV: {sect_csv}")
    print(f"Symbol CSV: {sym_csv}")


if __name__ == "__main__":
    main()
