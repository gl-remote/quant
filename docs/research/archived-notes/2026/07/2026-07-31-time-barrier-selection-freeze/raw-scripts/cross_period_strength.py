"""
文件级元信息：
- 创建背景：time-barrier-selection 主题 Stage 2 跨周期 |s| 分布对比。
  旧 Stage 1（5m 形态扫描）已归档，本实验接续——
  在 1m/5m/15m/1h 四个自然周期上分别测量 |s| 分布,
  直接验证 structural-shaping-alpha 的 KF-14 跨周期不变性。
- 用途：复用 corn_1h_strength_three_views.py 的成熟口径
  (W=20/80, stride=4, ddof=1), 在多周期上批量产出 |s| 样本,
  拟合 FoldedNormal(mu_D, sigma_D), 给 KF-14 一致性判据。
- 关键注意事项：
  - 与 Stage 1 不同: 本实验的 |s| 估计量的窗口 W 是常数 (20 或 80 bar),
    改变的是"周期" (bar 时长) — 1m vs 5m vs 15m vs 1h;
  - 每个周期独立读自己的 CSV, 不做 5m→1m 重采样;
  - cluster bootstrap 粒度: 1m/5m 按日 cluster, 15m/1h 按周 cluster
    (沿用 archive:2026-07-31-time-barrier-selection-redirection/raw-scripts/market_strength_scan.py 的 KF-2 修正);
  - FoldedNormal 拟合用 MLE (scipy.stats.foldnorm.fit);
  - 3 合约 (c2601/c2603/c2605) × 4 周期 × 2 窗口 = 24 组数据;
  - 输出每窗口的 |s| 样本 (CSV) + 汇总统计 (CSV) + 拟合结果 (CSV/JSON),
    落到 docs/workbench/time-barrier-selection/outputs/。
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import foldnorm

REPO_ROOT = Path(__file__).resolve().parents[4]  # .../quant
CSV_DIR = REPO_ROOT / "project_data" / "market_data" / "csv"
OUTPUT_DIR = REPO_ROOT / "docs" / "workbench" / "time-barrier-selection" / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PERIODS = ["1m", "5m", "15m", "1h"]
CONTRACTS = ["c2601", "c2603", "c2605"]
WINDOWS = [20, 80]
STRIDE = 4
B_BOOT = 1000


@dataclass(frozen=True)
class PeriodResult:
    contract: str
    period: str
    W: int
    n_windows: int
    n_indep_clusters: int
    mean: float
    mean_ci_lo: float
    mean_ci_hi: float
    median: float
    median_ci_lo: float
    median_ci_hi: float
    p10: float
    p25: float
    p75: float
    p90: float
    mu_D: float          # FoldedNormal MLE
    sigma_D: float
    mu_D_ci_lo: float
    mu_D_ci_hi: float
    sigma_D_ci_lo: float
    sigma_D_ci_hi: float
    rho_1: float

    def to_row(self) -> dict:
        return {
            "contract": self.contract,
            "period": self.period,
            "W": self.W,
            "n_windows": self.n_windows,
            "n_indep_clusters": self.n_indep_clusters,
            "mean": self.mean,
            "mean_ci_lo": self.mean_ci_lo,
            "mean_ci_hi": self.mean_ci_hi,
            "median": self.median,
            "median_ci_lo": self.median_ci_lo,
            "median_ci_hi": self.median_ci_hi,
            "p10": self.p10,
            "p25": self.p25,
            "p75": self.p75,
            "p90": self.p90,
            "mu_D": self.mu_D,
            "sigma_D": self.sigma_D,
            "mu_D_ci_lo": self.mu_D_ci_lo,
            "mu_D_ci_hi": self.mu_D_ci_hi,
            "sigma_D_ci_lo": self.sigma_D_ci_lo,
            "sigma_D_ci_hi": self.sigma_D_ci_hi,
            "rho_1": self.rho_1,
        }


def load_period_csv(contract: str, period: str) -> pd.DataFrame:
    """读入某合约某周期的 CSV, 返回含 log_ret / cluster_id 的 DataFrame."""
    path = CSV_DIR / f"DCE.{contract}.tqsdk.{period}.csv"
    if not path.exists():
        raise FileNotFoundError(f"missing {path}")
    df = pd.read_csv(path)
    if "datetime" not in df.columns or "close" not in df.columns:
        raise ValueError(f"unexpected columns in {path}: {df.columns.tolist()}")
    df["datetime"] = pd.to_datetime(df["datetime"])
    df["log_close"] = np.log(df["close"].astype(float))
    df["log_ret"] = df["log_close"].diff()
    df = df.dropna(subset=["log_ret"]).reset_index(drop=True)
    df["date"] = df["datetime"].dt.strftime("%Y-%m-%d")
    iso = df["datetime"].dt.isocalendar()
    df["iso_year"] = iso["year"].astype(int)
    df["iso_week"] = iso["week"].astype(int)
    df["week_id"] = df["iso_year"].astype(str) + "-W" + df["iso_week"].astype(str).str.zfill(2)
    return df


def cluster_unit(period: str) -> str:
    """1m/5m 按日 cluster; 15m/1h 按周 cluster (沿用 KF-2 修正)."""
    return "date" if period in ("1m", "5m") else "week_id"


def compute_window_nuabs(
    log_ret: np.ndarray, W: int, stride: int = STRIDE
) -> np.ndarray:
    """对一段 log return 序列, 以 stride 滑动取 W-bar 窗口, 返回 |ν|/σ 数组.
    向量化实现: 用 cumsum 计算每窗口的 sum 和 sum², 避免 Python 循环.
    """
    n = len(log_ret)
    if n < W:
        return np.array([])
    indices = np.arange(0, n - W + 1, stride)
    n_w = len(indices)
    # 用 cumsum 在 O(n) 时间算所有窗口 sum 和 sum²
    cs = np.cumsum(log_ret)
    cs2 = np.cumsum(log_ret * log_ret)
    end_idx = indices + W - 1
    start_idx = indices - 1
    sum_w = cs[end_idx] - np.where(start_idx >= 0, cs[np.maximum(start_idx, 0)], 0.0)
    sum2_w = cs2[end_idx] - np.where(start_idx >= 0, cs2[np.maximum(start_idx, 0)], 0.0)
    # 修正: 第一个窗口 start_idx=-1, 应直接取 cs[end_idx] - 0
    sum_w = np.where(start_idx >= 0, cs[end_idx] - cs[start_idx], cs[end_idx])
    sum2_w = np.where(start_idx >= 0, cs2[end_idx] - cs2[start_idx], cs2[end_idx])
    mu = sum_w / W
    # 与 corn_1h_strength_three_views.py 口径一致: ddof=1
    var_ddof0 = sum2_w / W - mu * mu
    var_ddof0 = np.maximum(var_ddof0, 0.0)
    var = var_ddof0 * W / (W - 1)
    sigma = np.sqrt(np.maximum(var, 0.0))
    sigma = np.maximum(sigma, 1e-12)
    out = np.abs(mu) / sigma
    return out


def fit_folded_normal(samples: np.ndarray) -> tuple[float, float]:
    """对 |s| 样本做 FoldedNormal MLE 拟合, 返回 (mu_D, sigma_D).

    scipy.stats.foldnorm 的 loc + scale 是正态部分, c 是非负折叠的偏移.
    标准 FoldedNormal 写法: X = |N(0, sigma_D^2) + mu_D|, 即 c=mu_D/sigma_D, loc=0, scale=sigma_D.
    这里直接用 |N(μ, σ)| 的参数化: mu_D = loc 修正后等价于 c*scale.
    """
    samples = samples[np.isfinite(samples) & (samples > 0)]
    if len(samples) < 10:
        return math.nan, math.nan
    # scipy foldnorm: pdf(x) = norm.pdf(x, c, loc, scale) + norm.pdf(-x, c, loc, scale)
    # 默认 loc=0, scale=1, c = |μ|/σ. 拟合得到 (c, loc, scale) -> 我们要 (μ=loc, σ=scale)
    c, loc, scale = foldnorm.fit(samples, floc=0)
    mu_D = float(loc + c * scale)
    sigma_D = float(scale)
    return mu_D, sigma_D


def cluster_bootstrap_nuabs_stats(
    log_ret: np.ndarray,
    cluster_ids: np.ndarray,
    W: int,
    rng: np.random.Generator,
    n_boot: int = B_BOOT,
) -> tuple[float, float, float, float, float, float]:
    """按 cluster 重抽样, 每个 bootstrap 样本下重算 |s| 数组, 输出 (mean, median, p10, p25, p75, p90) 的 95% CI.
    返回 ((mean_lo, mean_hi), (median_lo, median_hi), (p10_lo, p10_hi), (p25_lo, p25_hi), (p75_lo, p75_hi), (p90_lo, p90_hi)).
    """
    unique_clusters = np.unique(cluster_ids)
    n_clusters = len(unique_clusters)
    cluster_idx_arr = np.array([{c: i for i, c in enumerate(unique_clusters)}[c] for c in cluster_ids])
    cluster_segments = [log_ret[cluster_idx_arr == i] for i in range(n_clusters)]

    mean_samples = np.empty(n_boot)
    median_samples = np.empty(n_boot)
    p10_samples = np.empty(n_boot)
    p25_samples = np.empty(n_boot)
    p75_samples = np.empty(n_boot)
    p90_samples = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, n_clusters, size=n_clusters)
        boot_segments = [cluster_segments[i] for i in idx]
        boot_log_ret = np.concatenate(boot_segments)
        nu_abs_boot = compute_window_nuabs(boot_log_ret, W)
        if len(nu_abs_boot) < 10:
            mean_samples[b] = math.nan
            median_samples[b] = math.nan
            p10_samples[b] = p25_samples[b] = p75_samples[b] = p90_samples[b] = math.nan
            continue
        mean_samples[b] = float(np.mean(nu_abs_boot))
        median_samples[b] = float(np.median(nu_abs_boot))
        q = np.quantile(nu_abs_boot, [0.10, 0.25, 0.75, 0.90])
        p10_samples[b] = float(q[0])
        p25_samples[b] = float(q[1])
        p75_samples[b] = float(q[2])
        p90_samples[b] = float(q[3])
    out = []
    for arr in (mean_samples, median_samples, p10_samples, p25_samples, p75_samples, p90_samples):
        arr = arr[np.isfinite(arr)]
        if len(arr) < 10:
            out.append((math.nan, math.nan))
        else:
            lo, hi = np.quantile(arr, [0.025, 0.975])
            out.append((float(lo), float(hi)))
    return tuple(out)  # type: ignore[return-value]


def cluster_bootstrap_folded_normal(
    log_ret: np.ndarray,
    cluster_ids: np.ndarray,
    W: int,
    rng: np.random.Generator,
    n_boot: int = B_BOOT,
    mu_D_init: float | None = None,
    sigma_D_init: float | None = None,
) -> tuple[float, float, float, float]:
    """按 cluster 重抽样, 每个 bootstrap 样本下重算 |s| 数组并拟合 FoldedNormal.
    返回 (mu_D_ci_lo, mu_D_ci_hi, sigma_D_ci_lo, sigma_D_ci_hi).
    用 MLE 拟合 (floc=0) — 注意 W 越大, foldnorm 拟合越慢, 可在 W 大时降频.
    """
    unique_clusters = np.unique(cluster_ids)
    n_clusters = len(unique_clusters)
    cluster_idx_arr = np.array([{c: i for i, c in enumerate(unique_clusters)}[c] for c in cluster_ids])
    cluster_segments = [log_ret[cluster_idx_arr == i] for i in range(n_clusters)]

    mu_D_samples = np.empty(n_boot)
    sigma_D_samples = np.empty(n_boot)
    # 降频: 1m 数据上 2 万 bar + MLE 太慢, 每 5 次 bootstrap 才拟合一次 FoldedNormal
    fit_every = 5 if W <= 20 else 2
    for b in range(n_boot):
        idx = rng.integers(0, n_clusters, size=n_clusters)
        boot_segments = [cluster_segments[i] for i in idx]
        boot_log_ret = np.concatenate(boot_segments)
        if b % fit_every == 0:
            nu_abs_boot = compute_window_nuabs(boot_log_ret, W)
            if len(nu_abs_boot) < 10:
                mu_D_samples[b] = math.nan
                sigma_D_samples[b] = math.nan
                continue
            mu_D, sigma_D = fit_folded_normal(nu_abs_boot)
            mu_D_samples[b] = mu_D
            sigma_D_samples[b] = sigma_D
        else:
            mu_D_samples[b] = mu_D_samples[b - 1] if b > 0 else (mu_D_init or math.nan)
            sigma_D_samples[b] = sigma_D_samples[b - 1] if b > 0 else (sigma_D_init or math.nan)
    mu_D_samples = mu_D_samples[np.isfinite(mu_D_samples)]
    sigma_D_samples = sigma_D_samples[np.isfinite(sigma_D_samples)]
    if len(mu_D_samples) < 10:
        return math.nan, math.nan, math.nan, math.nan
    mu_D_lo, mu_D_hi = np.quantile(mu_D_samples, [0.025, 0.975])
    sigma_D_lo, sigma_D_hi = np.quantile(sigma_D_samples, [0.025, 0.975])
    return float(mu_D_lo), float(mu_D_hi), float(sigma_D_lo), float(sigma_D_hi)


def scan_one(
    contract: str, period: str, W: int, n_boot: int, seed: int
) -> tuple[PeriodResult, np.ndarray]:
    """跑单 (合约, 周期, W) 组合, 返回 (PeriodResult, |s| 数组)."""
    rng = np.random.default_rng(seed)
    df = load_period_csv(contract, period)
    log_ret = df["log_ret"].to_numpy()
    cluster_col = cluster_unit(period)
    cluster_ids = df[cluster_col].to_numpy()
    n_indep_clusters = int(len(np.unique(cluster_ids)))

    # 一阶自相关
    rho_1 = float(np.corrcoef(log_ret[:-1], log_ret[1:])[0, 1]) if len(log_ret) > 1 else 0.0

    # 窗口级 |s| 数组
    nu_abs = compute_window_nuabs(log_ret, W)
    n_windows = len(nu_abs)

    if n_windows < 10:
        return (
            PeriodResult(
                contract=contract, period=period, W=W,
                n_windows=n_windows, n_indep_clusters=n_indep_clusters,
                mean=math.nan, mean_ci_lo=math.nan, mean_ci_hi=math.nan,
                median=math.nan, median_ci_lo=math.nan, median_ci_hi=math.nan,
                p10=math.nan, p25=math.nan, p75=math.nan, p90=math.nan,
                mu_D=math.nan, sigma_D=math.nan,
                mu_D_ci_lo=math.nan, mu_D_ci_hi=math.nan,
                sigma_D_ci_lo=math.nan, sigma_D_ci_hi=math.nan,
                rho_1=rho_1,
            ),
            nu_abs,
        )

    # 经验统计
    mean = float(np.mean(nu_abs))
    median = float(np.median(nu_abs))
    p10, p25, p75, p90 = (float(x) for x in np.quantile(nu_abs, [0.10, 0.25, 0.75, 0.90]))

    # FoldedNormal 拟合
    mu_D, sigma_D = fit_folded_normal(nu_abs)

    # mean / median CI (always)
    (mean_lo, mean_hi), (median_lo, median_hi), _, _, _, _ = cluster_bootstrap_nuabs_stats(
        log_ret, cluster_ids, W, rng, n_boot=n_boot
    )

    # FoldedNormal CI 仅 W >= 80 时跑 (W=20 的 foldnorm MLE 太慢且对结果不敏感)
    if W >= 80:
        mu_D_lo, mu_D_hi, sigma_D_lo, sigma_D_hi = cluster_bootstrap_folded_normal(
            log_ret, cluster_ids, W, rng, n_boot=n_boot,
            mu_D_init=mu_D, sigma_D_init=sigma_D,
        )
    else:
        mu_D_lo, mu_D_hi, sigma_D_lo, sigma_D_hi = math.nan, math.nan, math.nan, math.nan

    return (
        PeriodResult(
            contract=contract, period=period, W=W,
            n_windows=n_windows, n_indep_clusters=n_indep_clusters,
            mean=mean, mean_ci_lo=mean_lo, mean_ci_hi=mean_hi,
            median=median, median_ci_lo=median_lo, median_ci_hi=median_hi,
            p10=p10, p25=p25, p75=p75, p90=p90,
            mu_D=mu_D, sigma_D=sigma_D,
            mu_D_ci_lo=mu_D_lo, mu_D_ci_hi=mu_D_hi,
            sigma_D_ci_lo=sigma_D_lo, sigma_D_ci_hi=sigma_D_hi,
            rho_1=rho_1,
        ),
        nu_abs,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contracts", nargs="+", default=CONTRACTS)
    parser.add_argument("--periods", nargs="+", default=PERIODS)
    parser.add_argument("--windows", nargs="+", type=int, default=WINDOWS)
    parser.add_argument("--n-boot", type=int, default=B_BOOT)
    parser.add_argument("--seed", type=int, default=20260731)
    parser.add_argument("--out-prefix", default="cross_period")
    args = parser.parse_args()

    all_results: list[PeriodResult] = []
    all_samples: list[dict] = []

    for contract in args.contracts:
        for period in args.periods:
            for W in args.windows:
                tag = f"{contract}/{period}/W={W}"
                print(f"[scan] {tag}")
                try:
                    seed_offset = (
                        abs(hash(f"{contract}_{period}_{W}")) % (2**31)
                    )
                    res, nu_abs = scan_one(
                        contract, period, W, args.n_boot, args.seed + seed_offset
                    )
                except FileNotFoundError as e:
                    print(f"  [warn] {e}", file=sys.stderr)
                    continue
                all_results.append(res)
                # 保存 |s| 样本
                for v in nu_abs:
                    all_samples.append(
                        {"contract": contract, "period": period, "W": W, "nu_abs": float(v)}
                    )

    if not all_results:
        print("[err] no results")
        return 1

    # 汇总
    df_summary = pd.DataFrame([r.to_row() for r in all_results])
    summary_csv = OUTPUT_DIR / f"{args.out_prefix}_summary.csv"
    df_summary.to_csv(summary_csv, index=False)
    print(f"[done] wrote {summary_csv} ({len(df_summary)} rows)")

    # 样本
    df_samples = pd.DataFrame(all_samples)
    samples_csv = OUTPUT_DIR / f"{args.out_prefix}_samples.csv"
    df_samples.to_csv(samples_csv, index=False)
    print(f"[done] wrote {samples_csv} ({len(df_samples)} rows)")

    # JSON
    summary_json = OUTPUT_DIR / f"{args.out_prefix}_summary.json"
    summary_json.write_text(df_summary.to_json(orient="records", indent=2), encoding="utf-8")
    print(f"[done] wrote {summary_json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
