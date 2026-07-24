"""成本敏感性分层器 · Cost Sensitivity Stratifier.

文件级元信息：
- 创建背景：main story 已证明"结构塑形在五维网格下无独立 alpha"。仍需回答最后一个
  loose end：**如果成本减半 / 归零 / 加倍，结论是否翻转？** 即"证伪是否只是被实际
  成本淹没了？"若答案为否——所有 combo 的 E[gross] ≤ 0——则封死"低成本环境下塑形
  可能有 alpha"的最后一条替代解释。
- 用途：一次性研究脚本。读现成 boundary_explorer_trades_*.csv，反算每笔成本 c_side
  = (gross - net) / 2，然后按成本乘数 {0.0, 0.5, 1.0, 1.5, 2.0, 3.0} 重算 E_net；
  同时算 breakeven 乘数 m* 使 E_net(m*) = 0。输出 cost_sensitivity_*.{json,csv}。
- 注意事项：仅用于同一批 realistic-cost trades 的相对成本敏感性，不涉及重跑回测；
  聚焦 8 关键 combo 保持与 vol_regime / symbol_sector 一致口径。
  归档规则：主命题闭环后连同其他分层脚本一并归档。

研究命题（v3 补齐）：
    §2.7 / §2.8 已证 martingale 恒等式在 vol × sector × symbol 全部生效。
    本脚本回答："若成本减半或归零，是否任一 combo 有正期望？"
    若 mean_gross ≤ 0 across combos → 即使零成本也不盈利 → 主命题稳健于成本。

方法：
    1. 读 boundary_explorer_trades_*.csv（现成）
    2. 对每笔 trade：c_side_impl = (gross_atr - net_atr) / 2（反算隐含单边成本）
    3. 对 8 关键 combo，扫成本乘数 mult ∈ {0.0, 0.5, 1.0, 1.5, 2.0, 3.0}
       new_net = gross_atr - 2 · mult · c_side_impl
    4. 输出每 combo × 每乘数：mean_net / SE / bootstrap p_gt_0 / breakeven 乘数 m*

用法：
    uv run python docs/research/themes/structural-shaping-alpha/raw-scripts/cost_sensitivity_stratifier.py
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

# ────────────────────── 常量 ──────────────────────
KEY_K_S = [1.0, 1.5, 2.5, 4.0]
KEY_RR = [1.0, 2.0]
COST_MULTIPLIERS = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0]
MAX_BARS = 80
BOOTSTRAP_ITER = 5000
SEED = 20260714


def cluster_bootstrap_mean(
    values_by_sym: dict[str, list[float]], n_iter: int, rng: np.random.Generator
) -> tuple[float, float, float]:
    """按 symbol 聚类 bootstrap，返回 (mean, ci_lo, ci_hi)。"""
    contracts = list(values_by_sym.keys())
    if not contracts:
        return 0.0, 0.0, 0.0
    n_c = len(contracts)
    means = np.empty(n_iter)
    for i in range(n_iter):
        idxs = rng.integers(0, n_c, size=n_c)
        collected: list[float] = []
        for idx in idxs:
            collected.extend(values_by_sym[contracts[idx]])
        means[i] = float(np.mean(collected)) if collected else 0.0
    return float(means.mean()), float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def stratify(trades_csv: Path) -> dict:
    # 1. 加载并按 combo 分组 (仅关键 combo)
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    with trades_csv.open() as f:
        reader = csv.DictReader(f)
        for r in reader:
            k_s = float(r["K_S"])
            rr = float(r["RR"])
            if k_s not in KEY_K_S or rr not in KEY_RR:
                continue
            if int(r["max_bars"]) != MAX_BARS:
                continue
            gross = float(r["gross_atr"])
            net = float(r["net_atr"])
            c_side = (gross - net) / 2  # 反算单边成本
            grouped[(k_s, rr)].append(
                {
                    "symbol": r["symbol"],
                    "gross": gross,
                    "net": net,
                    "c_side": c_side,
                }
            )
    if not grouped:
        raise SystemExit(f"[error] no matching rows in {trades_csv}")

    rng = np.random.default_rng(SEED)
    results: list[dict] = []
    for k_s in KEY_K_S:
        for rr in KEY_RR:
            bucket = grouped.get((k_s, rr), [])
            if not bucket:
                continue
            grosses = np.array([b["gross"] for b in bucket])
            c_sides = np.array([b["c_side"] for b in bucket])
            mean_gross = float(grosses.mean())
            mean_c_side = float(c_sides.mean())

            per_mult: list[dict] = []
            for mult in COST_MULTIPLIERS:
                new_nets = grosses - 2 * mult * c_sides
                nets_by_sym: dict[str, list[float]] = defaultdict(list)
                for b, nn in zip(bucket, new_nets, strict=True):
                    nets_by_sym[b["symbol"]].append(float(nn))
                mean_net, ci_lo, ci_hi = cluster_bootstrap_mean(nets_by_sym, BOOTSTRAP_ITER, rng)
                per_mult.append(
                    {
                        "mult": mult,
                        "avg_c_side_atr": mean_c_side * mult,
                        "mean_net_atr": mean_net,
                        "ci_lo": ci_lo,
                        "ci_hi": ci_hi,
                        "significant_positive": ci_lo > 0,
                    }
                )

            # breakeven 乘数 m*：mean_net(m*) = 0 → mean_gross - 2 · m* · mean_c_side = 0
            #                    → m* = mean_gross / (2 · mean_c_side)
            m_star = mean_gross / (2 * mean_c_side) if mean_c_side > 1e-9 else float("nan")

            results.append(
                {
                    "K_S": k_s,
                    "K_T": rr * k_s,
                    "RR": rr,
                    "n_events": len(bucket),
                    "mean_gross_atr": mean_gross,
                    "mean_c_side_atr": mean_c_side,
                    "breakeven_mult_m_star": m_star,
                    "per_mult": per_mult,
                }
            )

    return {
        "config": {
            "trades_csv": str(trades_csv),
            "key_K_S": KEY_K_S,
            "key_RR": KEY_RR,
            "cost_multipliers": COST_MULTIPLIERS,
            "max_bars": MAX_BARS,
            "bootstrap_iter": BOOTSTRAP_ITER,
            "seed": SEED,
        },
        "results": results,
    }


def render_console(summary: dict) -> None:
    print(f"\n{'=' * 90}")
    print("成本敏感性扫描 · 8 关键 combo × 6 乘数 · cluster bootstrap CI")
    print(f"{'=' * 90}")

    # 主表
    header = [
        "K_S",
        "RR",
        "gross",
        "c_side",
        "m*",
        "net@0.0x",
        "net@0.5x",
        "net@1.0x",
        "net@1.5x",
        "net@2.0x",
        "net@3.0x",
    ]
    fmt = "  " + " ".join(f"{h:>10}" for h in header)
    print(fmt)
    print("  " + " ".join("-" * 10 for _ in header))
    for r in summary["results"]:
        row = [
            f"{r['K_S']:.2f}",
            f"{r['RR']:.1f}",
            f"{r['mean_gross_atr']:+.4f}",
            f"{r['mean_c_side_atr']:+.4f}",
            f"{r['breakeven_mult_m_star']:+.3f}" if not math.isnan(r["breakeven_mult_m_star"]) else "nan",
        ]
        for pm in r["per_mult"]:
            marker = "*" if pm["significant_positive"] else ""
            row.append(f"{pm['mean_net_atr']:+.3f}{marker}")
        print("  " + " ".join(f"{v:>10}" for v in row))

    # 归因摘要
    print()
    n_total = len(summary["results"])
    n_gross_positive = sum(1 for r in summary["results"] if r["mean_gross_atr"] > 0)
    n_gross_zero = sum(1 for r in summary["results"] if abs(r["mean_gross_atr"]) < 0.01)
    n_m_positive = sum(
        1 for r in summary["results"] if not math.isnan(r["breakeven_mult_m_star"]) and r["breakeven_mult_m_star"] > 0
    )
    n_m_ge_1 = sum(
        1 for r in summary["results"] if not math.isnan(r["breakeven_mult_m_star"]) and r["breakeven_mult_m_star"] >= 1
    )

    print("归因摘要：")
    print(f"  mean_gross > 0: {n_gross_positive}/{n_total} combo")
    print(f"  |mean_gross| < 0.01: {n_gross_zero}/{n_total} combo（martingale 精确）")
    print(f"  breakeven m* > 0（即使零成本仍需要 c* > 0 才盈利）: {n_m_positive}/{n_total}")
    print(f"  breakeven m* ≥ 1（当前实际成本已在盈亏线之下）: {n_m_ge_1}/{n_total}")

    # 显著正 net 的 (combo, mult) 组合
    sig_positives = []
    for r in summary["results"]:
        for pm in r["per_mult"]:
            if pm["significant_positive"]:
                sig_positives.append((r["K_S"], r["RR"], pm["mult"], pm["mean_net_atr"], pm["ci_lo"]))
    print(f"  显著正 mean_net（CI 下界 > 0）的 (combo, mult) 组合数: {len(sig_positives)}")
    if sig_positives:
        for ks, rr, m, mn, cl in sig_positives:
            print(f"    K_S={ks:.2f} RR={rr:.1f} mult={m:.1f}: net={mn:+.4f} (CI_lo={cl:+.4f})")


def main() -> None:
    parser = argparse.ArgumentParser(description="成本敏感性分层器")
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
    json_path = out_dir / f"cost_sensitivity_{timestamp}.json"
    csv_path = out_dir / f"cost_sensitivity_{timestamp}.csv"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "K_S",
                "K_T",
                "RR",
                "n_events",
                "mean_gross_atr",
                "mean_c_side_atr",
                "breakeven_mult_m_star",
                "cost_mult",
                "mean_net_atr",
                "ci_lo",
                "ci_hi",
                "significant_positive",
            ]
        )
        for r in summary["results"]:
            for pm in r["per_mult"]:
                writer.writerow(
                    [
                        f"{r['K_S']:.2f}",
                        f"{r['K_T']:.2f}",
                        f"{r['RR']:.1f}",
                        r["n_events"],
                        f"{r['mean_gross_atr']:+.6f}",
                        f"{r['mean_c_side_atr']:+.6f}",
                        f"{r['breakeven_mult_m_star']:+.4f}" if not math.isnan(r["breakeven_mult_m_star"]) else "",
                        f"{pm['mult']:.2f}",
                        f"{pm['mean_net_atr']:+.6f}",
                        f"{pm['ci_lo']:+.6f}",
                        f"{pm['ci_hi']:+.6f}",
                        int(pm["significant_positive"]),
                    ]
                )

    print(f"\nJSON: {json_path}")
    print(f"CSV:  {csv_path}")


if __name__ == "__main__":
    main()
