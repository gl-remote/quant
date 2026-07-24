"""KF-15 分布拟合检验 · Fat tail vs GBM.

文件级元信息：
- 创建背景：#5 已证明 K_S=0.5/RR=5 三周期 ν/σ CI 排除 0。仍需回答：
  这个"真实非零漂移"是**真的 ν > 0**，还是**GBM 假设失效让 FPT 反算的 ν 出现系统偏差**？
  验证方式：对每笔 trade 提取 log-return 增量分布，做 Kolmogorov-Smirnov 与正态性
  Jarque-Bera 检验：若显著偏离正态 → 存在 fat-tail / skewness → GBM 假设失效 →
  KF-15 应重解释为"GBM 单一 σ 假设的边界失败"，而非"真实漂移发现"。
- 用途：一次性研究脚本。读三份 CSV 中 K_S=0.5/RR=5 通道 trades，
  提取每笔 gross_atr（相对入场的对数距离）；对每周期检验样本 GBM 拟合度。
  输出：KS test p-value、Jarque-Bera skew/kurtosis、Q-Q 分位比较。

注意事项：
  gross_atr 是"每笔完整 trade 收益"（barrier 触达时的对数收益），并非 K 线 bar 级增量。
  这里的检验是"完整 barrier 停时下的收益分布"vs "GBM barrier 停时下的期望正态"。
  若样本正态 → GBM 通过 → KF-15 是真实漂移；若显著偏离 → GBM 失败 → KF-15 是伪影。

用法：
    uv run python docs/research/themes/structural-shaping-alpha/raw-scripts/kf15_gbm_fit_test.py
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
from data.output_paths import project_data_root
from scipy import stats

# ────────────────────── 常量 ──────────────────────
TARGET_COMBOS = [(0.5, 5.0), (0.5, 8.0), (1.0, 1.0), (1.0, 2.0), (4.0, 2.0)]
INTERVALS = ["5m", "15m", "1h"]


def _latest_trades_csv(out_dir: Path, interval: str) -> Path:
    candidates = sorted(out_dir.glob(f"boundary_explorer_trades_realcost_{interval}_*.csv"))
    if candidates:
        return candidates[-1]
    if interval == "5m":
        legacy = sorted(out_dir.glob("boundary_explorer_trades_realcost_2*.csv"))
        if legacy:
            return legacy[-1]
    raise SystemExit(f"[error] no trades CSV for interval={interval}")


def _load_trades(csv_path: Path) -> dict[tuple[float, float], list[float]]:
    """按 (K_S, RR) 分组，返回每笔 gross_atr 列表。"""
    grouped: dict[tuple[float, float], list[float]] = defaultdict(list)
    with csv_path.open() as f:
        reader = csv.DictReader(f)
        for r in reader:
            k_s = float(r["K_S"])
            rr = float(r["RR"])
            if (k_s, rr) not in TARGET_COMBOS:
                continue
            grouped[(k_s, rr)].append(float(r["gross_atr"]))
    return grouped


def _fit_diagnostic(samples: np.ndarray) -> dict:
    """对样本做正态性检验 + skewness + kurtosis + Q-Q 分位。"""
    n = len(samples)
    mean = float(samples.mean())
    std = float(samples.std(ddof=1))
    skew = float(stats.skew(samples))
    excess_kurt = float(stats.kurtosis(samples, fisher=True))  # excess (=kurtosis - 3)

    # KS test vs 标准化 samples 与 N(0,1)
    z = (samples - mean) / std if std > 0 else samples
    ks_stat, ks_p = stats.kstest(z, "norm")

    # Jarque-Bera 联合正态性检验
    jb_stat, jb_p = stats.jarque_bera(samples)

    # Anderson-Darling
    ad = stats.anderson(samples, dist="norm")
    ad_stat = float(ad.statistic)

    # Q-Q 分位对比（观察 tail 是否肥）
    quantiles = [0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]
    obs_q = np.quantile(samples, quantiles)
    theo_q = mean + std * stats.norm.ppf(quantiles)

    return {
        "n": int(n),
        "mean": mean,
        "std": std,
        "skew": skew,
        "excess_kurtosis": excess_kurt,
        "ks_stat": float(ks_stat),
        "ks_p_value": float(ks_p),
        "jb_stat": float(jb_stat),
        "jb_p_value": float(jb_p),
        "anderson_darling_stat": ad_stat,
        "quantile_levels": quantiles,
        "observed_quantiles": [float(x) for x in obs_q],
        "theoretical_quantiles_gaussian": [float(x) for x in theo_q],
        "tail_deviation_pct": [
            float((o - t) / std * 100) if std > 0 else 0.0 for o, t in zip(obs_q, theo_q, strict=True)
        ],
    }


def stratify(out_dir: Path) -> dict:
    results: list[dict] = []
    source_files: dict[str, str] = {}
    for interval in INTERVALS:
        csv_path = _latest_trades_csv(out_dir, interval)
        source_files[interval] = str(csv_path)
        grouped = _load_trades(csv_path)
        for (k_s, rr), samples in grouped.items():
            arr = np.array(samples)
            if len(arr) < 30:
                continue
            diag = _fit_diagnostic(arr)
            results.append(
                {
                    "K_S": k_s,
                    "RR": rr,
                    "interval": interval,
                    **diag,
                }
            )

    return {
        "config": {"target_combos": TARGET_COMBOS, "intervals": INTERVALS},
        "source_files": source_files,
        "results": results,
    }


def render_console(summary: dict) -> None:
    print(f"\n{'=' * 120}")
    print("KF-15 分布拟合检验 · 每笔 gross_atr 是否偏离 GBM 期望正态")
    print(f"{'=' * 120}")
    header = ["K_S", "RR", "int", "n", "mean", "std", "skew", "kurt", "KS_p", "JB_p", "AD_stat", "verdict"]
    fmt = "  " + " ".join(f"{h:>10}" for h in header)
    print(fmt)
    print("  " + " ".join("-" * 10 for _ in header))
    for r in summary["results"]:
        # Anderson-Darling 临界值 (α=0.05): ~0.752
        ad_reject = r["anderson_darling_stat"] > 0.752
        ks_reject = r["ks_p_value"] < 0.05
        jb_reject = r["jb_p_value"] < 0.05
        n_reject = sum([ad_reject, ks_reject, jb_reject])
        verdict = ["GBM-OK", "边缘", "GBM-偏离", "GBM-拒绝"][n_reject]
        row = [
            f"{r['K_S']:.2f}",
            f"{r['RR']:.1f}",
            r["interval"],
            f"{r['n']}",
            f"{r['mean']:+.4f}",
            f"{r['std']:.4f}",
            f"{r['skew']:+.3f}",
            f"{r['excess_kurtosis']:+.3f}",
            f"{r['ks_p_value']:.4f}",
            f"{r['jb_p_value']:.4f}",
            f"{r['anderson_darling_stat']:.3f}",
            verdict,
        ]
        print("  " + " ".join(f"{v:>10}" for v in row))

    print()
    print(f"{'=' * 60}")
    print("解读")
    print(f"{'=' * 60}")
    print("  skew ≠ 0 → 分布非对称（无漂移下应 ≈ 0）")
    print("  excess kurt > 0 → 尾部比正态肥（fat tail）")
    print("  KS_p / JB_p < 0.05 → 拒绝正态假设 → GBM 单一 σ 假设失败")
    print("  AD_stat > 0.752（α=0.05）→ 拒绝正态假设")


def main() -> None:
    parser = argparse.ArgumentParser(description="KF-15 分布拟合检验")
    parser.add_argument("--out-dir", type=str, default=None)
    args = parser.parse_args()

    out_dir = Path(args.out_dir) if args.out_dir else project_data_root() / "research" / "first_passage_boundary"
    summary = stratify(out_dir)

    print("加载 trades CSV:")
    for interval, path in summary["source_files"].items():
        print(f"  [{interval}] {path}")
    render_console(summary)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"kf15_gbm_fit_{timestamp}.json"
    csv_path = out_dir / f"kf15_gbm_fit_{timestamp}.csv"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "K_S",
                "RR",
                "interval",
                "n",
                "mean",
                "std",
                "skew",
                "excess_kurtosis",
                "ks_stat",
                "ks_p_value",
                "jb_stat",
                "jb_p_value",
                "anderson_darling_stat",
            ]
        )
        for r in summary["results"]:
            writer.writerow(
                [
                    f"{r['K_S']:.2f}",
                    f"{r['RR']:.1f}",
                    r["interval"],
                    r["n"],
                    f"{r['mean']:+.6f}",
                    f"{r['std']:.6f}",
                    f"{r['skew']:+.6f}",
                    f"{r['excess_kurtosis']:+.6f}",
                    f"{r['ks_stat']:.6f}",
                    f"{r['ks_p_value']:.6f}",
                    f"{r['jb_stat']:.6f}",
                    f"{r['jb_p_value']:.6f}",
                    f"{r['anderson_darling_stat']:.6f}",
                ]
            )

    print(f"\nJSON: {json_path}")
    print(f"CSV:  {csv_path}")


if __name__ == "__main__":
    main()
