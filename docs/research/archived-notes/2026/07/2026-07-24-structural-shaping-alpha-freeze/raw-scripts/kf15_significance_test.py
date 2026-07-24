"""KF-15 事件级 ν/σ 显著性检验 · Stratifier for KF-15 event-level significance.

文件级元信息：
- 创建背景：v8 §2.11 首次记录 ν/σ = 0.117 突破 KF-9 阈值 0.10（K_S=0.5/RR=5 @ 1h），
  但仅基于聚合级 P_win = 0.2188 与 FPT 0.1667 的二项检验。为决定 KF-15 命运，
  需要**事件级 cluster bootstrap** 验证 ν_impl 分布的 mean CI 是否排除 0：
  - CI 排除 0 → KF-15 强化为"真实漂移"发现
  - CI 覆盖 0 → KF-15 弱化为"P_win 随机波动"边界伪影
- 用途：一次性研究脚本。读三份周期 boundary_explorer_trades_realcost_{5m,15m,1h}_*.csv，
  对每个 (K_S, RR) 关键 combo × 三周期 = 若干行做 cluster bootstrap 5000 次，
  每次抽样重算 P_win 反算 ν_impl，输出 ν_impl mean / 95% CI / P(ν_impl > 0)。
  聚焦 K_S ∈ {0.5, 1.0, 1.5, 4.0} × RR ∈ {1.0, 2.0, 5.0, 8.0} 关键 combo。
- 注意事项：cluster bootstrap 按 symbol 聚类；每次 iter 有等概率抽样 20 品种 with replacement，
  然后重算 P_win 汇总。ν_impl 反算失败（P_win 极端）时跳过该 iter。

研究命题：
    KF-15 的 ν/σ = 0.117 是真实方向漂移还是 P_win 二项分布的随机波动？

方法：
    1. 读三份 trades CSV（15m/1h trades 由本轮新扫描产出，5m 用旧文件）
    2. 对每个 (K_S, RR, interval) combo，按 symbol 聚类抽 5000 次
    3. 每次 iter 抽 20 symbols with replacement，汇总 P_win，反算 ν_impl
    4. 输出 mean(ν_impl_boot) / CI / P(ν > 0) / cluster SE

用法：
    uv run python docs/research/themes/structural-shaping-alpha/raw-scripts/kf15_significance_test.py
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
KEY_COMBOS = [
    # (K_S, RR)
    (0.5, 5.0),  # KF-15 核心通道
    (0.5, 8.0),  # 相邻极端 RR 通道
    (1.0, 5.0),  # 常规 K_S + 极端 RR
    (1.0, 2.0),  # 主命题基准
    (1.0, 1.0),  # 对称 martingale 参照
    (4.0, 2.0),  # 长期区参照（KF-14）
]
INTERVALS = ["5m", "15m", "1h"]
BOOTSTRAP_ITER = 5000
SEED = 20260714

SIGMA_PER_BAR_BY_INTERVAL: dict[str, float] = {
    "5m": 1.0 / math.sqrt(12),
    "15m": 1.0 / math.sqrt(4),
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


def _solve_implied_nu(p_win: float, k_s: float, k_t: float, sigma_per_bar: float) -> float:
    if not (0 < p_win < 1):
        return float("nan")
    try:

        def f(lam: float) -> float:
            return _p_win_infty(lam, k_s, k_t) - p_win

        for expand_lo, expand_hi in [(-3.0, 3.0), (-5.0, 5.0), (-10.0, 10.0)]:
            if f(expand_lo) * f(expand_hi) < 0:
                lam = brentq(f, expand_lo, expand_hi, xtol=1e-10)
                return lam * sigma_per_bar**2 / 2
        return float("nan")
    except (ValueError, RuntimeError):
        return float("nan")


# ────────────────────── 主流程 ──────────────────────


def _latest_trades_csv(out_dir: Path, interval: str) -> Path:
    candidates = sorted(out_dir.glob(f"boundary_explorer_trades_realcost_{interval}_*.csv"))
    if candidates:
        return candidates[-1]
    # 兼容旧 5m 命名
    if interval == "5m":
        legacy = sorted(out_dir.glob("boundary_explorer_trades_realcost_2*.csv"))
        if legacy:
            return legacy[-1]
    raise SystemExit(f"[error] no trades CSV for interval={interval}")


def _load_trades(csv_path: Path, key_combos: list[tuple[float, float]]) -> dict:
    """按 (K_S, RR) 分组，每组按 symbol 聚合 exit_reason。"""
    grouped: dict[tuple[float, float], dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    with csv_path.open() as f:
        reader = csv.DictReader(f)
        for r in reader:
            k_s = float(r["K_S"])
            rr = float(r["RR"])
            if (k_s, rr) not in key_combos:
                continue
            grouped[(k_s, rr)][r["symbol"]].append(
                {
                    "exit_reason": r["exit_reason"],
                    "gross_atr": float(r["gross_atr"]),
                    "net_atr": float(r["net_atr"]),
                }
            )
    return grouped


def cluster_bootstrap_pwin_nu(
    bucket_by_sym: dict[str, list[dict]],
    k_s: float,
    k_t: float,
    sigma_per_bar: float,
    n_iter: int,
    rng: np.random.Generator,
) -> dict:
    """按 symbol 聚类抽样 with replacement，重算 P_win → 反算 ν_impl 分布。"""
    contracts = list(bucket_by_sym.keys())
    n_c = len(contracts)
    if n_c == 0:
        return {
            "nu_mean": float("nan"),
            "nu_ci_lo": float("nan"),
            "nu_ci_hi": float("nan"),
            "p_win_mean": float("nan"),
            "p_nu_gt_0": float("nan"),
            "nu_valid_iter": 0,
            "n_iter": n_iter,
        }

    nus = np.empty(n_iter)
    pwins = np.empty(n_iter)
    valid = 0
    for i in range(n_iter):
        idxs = rng.integers(0, n_c, size=n_c)
        n_wins = 0
        n_total = 0
        for idx in idxs:
            trades = bucket_by_sym[contracts[idx]]
            for t in trades:
                n_total += 1
                if t["exit_reason"] == "take":
                    n_wins += 1
        if n_total == 0:
            nus[i] = float("nan")
            pwins[i] = float("nan")
            continue
        p_win = n_wins / n_total
        pwins[i] = p_win
        nu = _solve_implied_nu(p_win, k_s, k_t, sigma_per_bar)
        nus[i] = nu
        if not math.isnan(nu):
            valid += 1

    nus_valid = nus[~np.isnan(nus)]
    pwins_valid = pwins[~np.isnan(pwins)]
    if len(nus_valid) < n_iter * 0.5:
        # 半数以上失败，不可靠
        return {
            "nu_mean": float("nan"),
            "nu_ci_lo": float("nan"),
            "nu_ci_hi": float("nan"),
            "p_win_mean": float(pwins_valid.mean()) if len(pwins_valid) > 0 else float("nan"),
            "p_nu_gt_0": float("nan"),
            "nu_valid_iter": int(valid),
            "n_iter": n_iter,
        }
    return {
        "nu_mean": float(nus_valid.mean()),
        "nu_ci_lo": float(np.quantile(nus_valid, 0.025)),
        "nu_ci_hi": float(np.quantile(nus_valid, 0.975)),
        "p_win_mean": float(pwins_valid.mean()),
        "p_nu_gt_0": float((nus_valid > 0).mean()),
        "nu_valid_iter": int(valid),
        "n_iter": n_iter,
    }


def stratify(out_dir: Path) -> dict:
    rng = np.random.default_rng(SEED)
    results: list[dict] = []
    source_files: dict[str, str] = {}

    for interval in INTERVALS:
        csv_path = _latest_trades_csv(out_dir, interval)
        source_files[interval] = str(csv_path)
        grouped = _load_trades(csv_path, KEY_COMBOS)
        sigma = SIGMA_PER_BAR_BY_INTERVAL[interval]

        for (k_s, rr), bucket_by_sym in grouped.items():
            k_t = rr * k_s
            p_fpt = k_s / (k_s + k_t)
            n_events = sum(len(v) for v in bucket_by_sym.values())
            n_wins = sum(1 for v in bucket_by_sym.values() for t in v if t["exit_reason"] == "take")
            p_win_point = n_wins / n_events if n_events > 0 else float("nan")
            nu_point = _solve_implied_nu(p_win_point, k_s, k_t, sigma)
            nu_over_sigma_point = nu_point / sigma if not math.isnan(nu_point) else float("nan")

            boot = cluster_bootstrap_pwin_nu(bucket_by_sym, k_s, k_t, sigma, BOOTSTRAP_ITER, rng)

            nu_over_sigma_mean = boot["nu_mean"] / sigma if not math.isnan(boot["nu_mean"]) else float("nan")
            nu_over_sigma_ci_lo = boot["nu_ci_lo"] / sigma if not math.isnan(boot["nu_ci_lo"]) else float("nan")
            nu_over_sigma_ci_hi = boot["nu_ci_hi"] / sigma if not math.isnan(boot["nu_ci_hi"]) else float("nan")

            results.append(
                {
                    "K_S": k_s,
                    "K_T": k_t,
                    "RR": rr,
                    "interval": interval,
                    "sigma_per_bar": sigma,
                    "n_events": n_events,
                    "P_win_fpt": p_fpt,
                    "P_win_obs": p_win_point,
                    "nu_point": nu_point,
                    "nu_over_sigma_point": nu_over_sigma_point,
                    "boot_nu_mean": boot["nu_mean"],
                    "boot_nu_ci_lo": boot["nu_ci_lo"],
                    "boot_nu_ci_hi": boot["nu_ci_hi"],
                    "boot_nu_over_sigma_mean": nu_over_sigma_mean,
                    "boot_nu_over_sigma_ci_lo": nu_over_sigma_ci_lo,
                    "boot_nu_over_sigma_ci_hi": nu_over_sigma_ci_hi,
                    "boot_p_win_mean": boot["p_win_mean"],
                    "boot_p_nu_gt_0": boot["p_nu_gt_0"],
                    "boot_valid_iter": boot["nu_valid_iter"],
                    "boot_ci_excludes_0": (not math.isnan(nu_over_sigma_ci_lo))
                    and (nu_over_sigma_ci_lo * nu_over_sigma_ci_hi > 0),
                }
            )

    return {
        "config": {
            "key_combos": KEY_COMBOS,
            "intervals": INTERVALS,
            "bootstrap_iter": BOOTSTRAP_ITER,
            "seed": SEED,
        },
        "source_files": source_files,
        "results": results,
    }


def render_console(summary: dict) -> None:
    print(f"\n{'=' * 120}")
    print("KF-15 事件级 ν/σ 显著性检验 · cluster bootstrap by symbol")
    print(f"{'=' * 120}")
    header = [
        "K_S",
        "RR",
        "int",
        "n",
        "P_win",
        "FPT",
        "ν/σ_pt",
        "ν/σ_boot_mean",
        "ν/σ_CI_lo",
        "ν/σ_CI_hi",
        "P(ν>0)",
        "CI_excl_0",
    ]
    fmt = "  " + " ".join(f"{h:>13}" for h in header)
    print(fmt)
    print("  " + " ".join("-" * 13 for _ in header))
    for r in summary["results"]:
        excl = "✓" if r["boot_ci_excludes_0"] else "✗"
        row = [
            f"{r['K_S']:.2f}",
            f"{r['RR']:.1f}",
            r["interval"],
            f"{r['n_events']}",
            f"{r['P_win_obs']:.4f}",
            f"{r['P_win_fpt']:.4f}",
            f"{r['nu_over_sigma_point']:+.4f}",
            f"{r['boot_nu_over_sigma_mean']:+.4f}",
            f"{r['boot_nu_over_sigma_ci_lo']:+.4f}",
            f"{r['boot_nu_over_sigma_ci_hi']:+.4f}",
            f"{r['boot_p_nu_gt_0']:.4f}",
            excl,
        ]
        print("  " + " ".join(f"{v:>13}" for v in row))

    print()
    print(f"{'=' * 60}")
    print("判据")
    print(f"{'=' * 60}")
    print("  CI_excl_0 = ✓ → 事件级 ν/σ 显著非零 → 支持真实漂移")
    print("  CI_excl_0 = ✗ → 事件级 ν/σ CI 覆盖 0 → 归零为 P_win 随机波动")
    n_excl = sum(1 for r in summary["results"] if r["boot_ci_excludes_0"])
    print(f"  → {n_excl}/{len(summary['results'])} 行 CI 排除 0")


def main() -> None:
    parser = argparse.ArgumentParser(description="KF-15 事件级 ν/σ 显著性检验")
    parser.add_argument("--out-dir", type=str, default=None)
    args = parser.parse_args()

    out_dir = Path(args.out_dir) if args.out_dir else project_data_root() / "research" / "first_passage_boundary"
    summary = stratify(out_dir)

    print("加载 trades CSV:")
    for interval, path in summary["source_files"].items():
        print(f"  [{interval}] {path}")
    render_console(summary)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"kf15_significance_{timestamp}.json"
    csv_path = out_dir / f"kf15_significance_{timestamp}.csv"
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
                "n_events",
                "P_win_fpt",
                "P_win_obs",
                "nu_point",
                "nu_over_sigma_point",
                "boot_nu_mean",
                "boot_nu_ci_lo",
                "boot_nu_ci_hi",
                "boot_nu_over_sigma_mean",
                "boot_nu_over_sigma_ci_lo",
                "boot_nu_over_sigma_ci_hi",
                "boot_p_win_mean",
                "boot_p_nu_gt_0",
                "boot_valid_iter",
                "boot_ci_excludes_0",
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
                    r["n_events"],
                    f"{r['P_win_fpt']:.6f}",
                    f"{r['P_win_obs']:.6f}",
                    f"{r['nu_point']:+.6f}",
                    f"{r['nu_over_sigma_point']:+.6f}",
                    f"{r['boot_nu_mean']:+.6f}",
                    f"{r['boot_nu_ci_lo']:+.6f}",
                    f"{r['boot_nu_ci_hi']:+.6f}",
                    f"{r['boot_nu_over_sigma_mean']:+.6f}",
                    f"{r['boot_nu_over_sigma_ci_lo']:+.6f}",
                    f"{r['boot_nu_over_sigma_ci_hi']:+.6f}",
                    f"{r['boot_p_win_mean']:.6f}",
                    f"{r['boot_p_nu_gt_0']:.6f}",
                    r["boot_valid_iter"],
                    int(r["boot_ci_excludes_0"]),
                ]
            )

    print(f"\nJSON: {json_path}")
    print(f"CSV:  {csv_path}")


if __name__ == "__main__":
    main()
