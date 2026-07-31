"""
文件级元信息：
- 创建背景：time-barrier-selection 主题 Stage 3 跨品种 |s| 分布对比。
  Stage 2 (跨周期，玉米 c) 已完成 mean(|s|) 随周期单调递增、ρ_1 收敛、
  KF-14 量级一致部分成立。本实验在豆粕 m / 螺纹钢 rb 上重复 5m/15m/1h
  三周期扫描，验证上述结论是否品种无关。
- 设计：
  - 复用 cross_period_strength.py 的核心函数 (compute_window_nuabs,
    fit_folded_normal, cluster_bootstrap_nuabs_stats, cluster_bootstrap_folded_normal);
  - 增加交易所前缀处理：DCE.c/m/i/y/p, SHFE.rb;
  - 周期只扫 5m/15m/1h，跳过 1m (用户指示效率优先);
  - 品种 × 合约矩阵：
      c (玉米 DCE) : c2601, c2603, c2605
      m (豆粕 DCE) : m2601, m2603, m2605
      rb (螺纹钢 SHFE): rb2601, rb2605 (缺 rb2603，用 rb2610 5m 补)
  - W=20/80、stride=4、ddof=1、cluster bootstrap 1000 次 (同 Stage 2 口径);
  - FoldedNormal CI 仅 W>=80 跑 (W=20 MLE 退化)。
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

REPO_ROOT = Path(__file__).resolve().parents[4]
CSV_DIR = REPO_ROOT / "project_data" / "market_data" / "csv"
OUTPUT_DIR = REPO_ROOT / "docs" / "workbench" / "time-barrier-selection" / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 品种 → 交易所映射
EXCHANGE = {
    "c": "DCE", "m": "DCE", "i": "DCE", "y": "DCE", "p": "DCE", "cs": "DCE",
    "rb": "SHFE", "hc": "SHFE",
}

# 品种 → 合约列表 (用户选择: c 对照, m 豆粕, rb 螺纹钢)
# rb 缺 2603 的 15m/1h 数据，rb2610 仅 5m，跨品种聚合时按可用合约平均
SYMBOL_CONTRACTS = {
    "c": ["c2601", "c2603", "c2605"],
    "m": ["m2601", "m2603", "m2605"],
    "rb": ["rb2601", "rb2605"],  # rb2610 仅 5m，单独处理
}

PERIODS = ["5m", "15m", "1h"]
WINDOWS = [20, 80]
STRIDE = 4
B_BOOT = 1000


@dataclass(frozen=True)
class ScanResult:
    symbol: str
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
    mu_D: float
    sigma_D: float
    mu_D_ci_lo: float
    mu_D_ci_hi: float
    sigma_D_ci_lo: float
    sigma_D_ci_hi: float
    rho_1: float

    def to_row(self) -> dict:
        return {
            "symbol": self.symbol,
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


def csv_path_for(contract: str, period: str) -> Path:
    prefix = "rb" if contract.startswith("rb") else ("hc" if contract.startswith("hc") else contract[0])
    exch = EXCHANGE[prefix]
    return CSV_DIR / f"{exch}.{contract}.tqsdk.{period}.csv"


def load_csv(contract: str, period: str) -> pd.DataFrame:
    path = csv_path_for(contract, period)
    if not path.exists():
        raise FileNotFoundError(f"missing {path}")
    df = pd.read_csv(path)
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
    return "date" if period == "5m" else "week_id"


def compute_window_nuabs(log_ret: np.ndarray, W: int, stride: int = STRIDE) -> np.ndarray:
    n = len(log_ret)
    if n < W:
        return np.array([])
    indices = np.arange(0, n - W + 1, stride)
    cs = np.cumsum(log_ret)
    cs2 = np.cumsum(log_ret * log_ret)
    end_idx = indices + W - 1
    start_idx = indices - 1
    sum_w = np.where(start_idx >= 0, cs[end_idx] - cs[start_idx], cs[end_idx])
    sum2_w = np.where(start_idx >= 0, cs2[end_idx] - cs2[start_idx], cs2[end_idx])
    mu = sum_w / W
    var_ddof0 = np.maximum(sum2_w / W - mu * mu, 0.0)
    var = var_ddof0 * W / (W - 1)
    sigma = np.maximum(np.sqrt(np.maximum(var, 0.0)), 1e-12)
    return np.abs(mu) / sigma


def fit_folded_normal(samples: np.ndarray) -> tuple[float, float]:
    samples = samples[np.isfinite(samples) & (samples > 0)]
    if len(samples) < 10:
        return math.nan, math.nan
    c, loc, scale = foldnorm.fit(samples, floc=0)
    return float(loc + c * scale), float(scale)


def cluster_bootstrap_nuabs_stats(
    log_ret: np.ndarray, cluster_ids: np.ndarray, W: int,
    rng: np.random.Generator, n_boot: int,
) -> tuple:
    unique_clusters = np.unique(cluster_ids)
    n_clusters = len(unique_clusters)
    idx_map = {c: i for i, c in enumerate(unique_clusters)}
    cluster_idx_arr = np.array([idx_map[c] for c in cluster_ids])
    cluster_segments = [log_ret[cluster_idx_arr == i] for i in range(n_clusters)]

    arrs = {k: np.empty(n_boot) for k in ("mean", "median", "p10", "p25", "p75", "p90")}
    for b in range(n_boot):
        idx = rng.integers(0, n_clusters, size=n_clusters)
        boot = np.concatenate([cluster_segments[i] for i in idx])
        nu = compute_window_nuabs(boot, W)
        if len(nu) < 10:
            for v in arrs.values():
                v[b] = math.nan
            continue
        arrs["mean"][b] = np.mean(nu)
        arrs["median"][b] = np.median(nu)
        q = np.quantile(nu, [0.10, 0.25, 0.75, 0.90])
        arrs["p10"][b], arrs["p25"][b], arrs["p75"][b], arrs["p90"][b] = q
    out = []
    for v in arrs.values():
        v = v[np.isfinite(v)]
        out.append((float(np.quantile(v, 0.025)), float(np.quantile(v, 0.975))) if len(v) >= 10 else (math.nan, math.nan))
    return tuple(out)


def cluster_bootstrap_folded_normal(
    log_ret: np.ndarray, cluster_ids: np.ndarray, W: int,
    rng: np.random.Generator, n_boot: int,
    mu_D_init: float | None = None, sigma_D_init: float | None = None,
) -> tuple[float, float, float, float]:
    unique_clusters = np.unique(cluster_ids)
    n_clusters = len(unique_clusters)
    idx_map = {c: i for i, c in enumerate(unique_clusters)}
    cluster_idx_arr = np.array([idx_map[c] for c in cluster_ids])
    cluster_segments = [log_ret[cluster_idx_arr == i] for i in range(n_clusters)]

    mu_arr = np.empty(n_boot)
    sig_arr = np.empty(n_boot)
    fit_every = 5 if W <= 20 else 2
    for b in range(n_boot):
        idx = rng.integers(0, n_clusters, size=n_clusters)
        if b % fit_every == 0:
            boot = np.concatenate([cluster_segments[i] for i in idx])
            nu = compute_window_nuabs(boot, W)
            if len(nu) < 10:
                mu_arr[b] = sig_arr[b] = math.nan
            else:
                mu_arr[b], sig_arr[b] = fit_folded_normal(nu)
        else:
            mu_arr[b] = mu_arr[b - 1] if b > 0 else (mu_D_init or math.nan)
            sig_arr[b] = sig_arr[b - 1] if b > 0 else (sigma_D_init or math.nan)
    mu_arr = mu_arr[np.isfinite(mu_arr)]
    sig_arr = sig_arr[np.isfinite(sig_arr)]
    if len(mu_arr) < 10:
        return math.nan, math.nan, math.nan, math.nan
    return (float(np.quantile(mu_arr, 0.025)), float(np.quantile(mu_arr, 0.975)),
            float(np.quantile(sig_arr, 0.025)), float(np.quantile(sig_arr, 0.975)))


def scan_one(symbol: str, contract: str, period: str, W: int, n_boot: int, seed: int) -> tuple[ScanResult, np.ndarray]:
    rng = np.random.default_rng(seed)
    df = load_csv(contract, period)
    log_ret = df["log_ret"].to_numpy()
    cluster_col = cluster_unit(period)
    cluster_ids = df[cluster_col].to_numpy()
    n_indep_clusters = int(len(np.unique(cluster_ids)))

    rho_1 = float(np.corrcoef(log_ret[:-1], log_ret[1:])[0, 1]) if len(log_ret) > 1 else 0.0
    nu_abs = compute_window_nuabs(log_ret, W)
    n_windows = len(nu_abs)

    if n_windows < 10:
        empty = ScanResult(
            symbol=symbol, contract=contract, period=period, W=W,
            n_windows=n_windows, n_indep_clusters=n_indep_clusters,
            **{k: math.nan for k in ["mean","mean_ci_lo","mean_ci_hi","median","median_ci_lo","median_ci_hi",
                                      "p10","p25","p75","p90","mu_D","sigma_D",
                                      "mu_D_ci_lo","mu_D_ci_hi","sigma_D_ci_lo","sigma_D_ci_hi"]},
            rho_1=rho_1,
        )
        return empty, nu_abs

    mean = float(np.mean(nu_abs))
    median = float(np.median(nu_abs))
    p10, p25, p75, p90 = (float(x) for x in np.quantile(nu_abs, [0.10, 0.25, 0.75, 0.90]))
    mu_D, sigma_D = fit_folded_normal(nu_abs)

    (mean_lo, mean_hi), (median_lo, median_hi), _, _, _, _ = cluster_bootstrap_nuabs_stats(
        log_ret, cluster_ids, W, rng, n_boot
    )

    if W >= 80:
        mu_D_lo, mu_D_hi, sigma_D_lo, sigma_D_hi = cluster_bootstrap_folded_normal(
            log_ret, cluster_ids, W, rng, n_boot, mu_D_init=mu_D, sigma_D_init=sigma_D,
        )
    else:
        mu_D_lo = mu_D_hi = sigma_D_lo = sigma_D_hi = math.nan

    res = ScanResult(
        symbol=symbol, contract=contract, period=period, W=W,
        n_windows=n_windows, n_indep_clusters=n_indep_clusters,
        mean=mean, mean_ci_lo=mean_lo, mean_ci_hi=mean_hi,
        median=median, median_ci_lo=median_lo, median_ci_hi=median_hi,
        p10=p10, p25=p25, p75=p75, p90=p90,
        mu_D=mu_D, sigma_D=sigma_D,
        mu_D_ci_lo=mu_D_lo, mu_D_ci_hi=mu_D_hi,
        sigma_D_ci_lo=sigma_D_lo, sigma_D_ci_hi=sigma_D_hi,
        rho_1=rho_1,
    )
    return res, nu_abs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", nargs="+", default=list(SYMBOL_CONTRACTS.keys()))
    parser.add_argument("--periods", nargs="+", default=PERIODS)
    parser.add_argument("--windows", nargs="+", type=int, default=WINDOWS)
    parser.add_argument("--n-boot", type=int, default=B_BOOT)
    parser.add_argument("--seed", type=int, default=20260731)
    parser.add_argument("--out-prefix", default="cross_symbol")
    args = parser.parse_args()

    all_results: list[ScanResult] = []
    all_samples: list[dict] = []

    # rb2610 只扫 5m 作为额外补充
    extra = [("rb", "rb2610", "5m")]

    jobs = []
    for sym in args.symbols:
        for contract in SYMBOL_CONTRACTS[sym]:
            for period in args.periods:
                jobs.append((sym, contract, period))
    jobs.extend(extra)

    for sym, contract, period in jobs:
        for W in args.windows:
            tag = f"{sym}/{contract}/{period}/W={W}"
            print(f"[scan] {tag}", flush=True)
            try:
                seed_off = abs(hash(f"{sym}_{contract}_{period}_{W}")) % (2**31)
                res, nu = scan_one(sym, contract, period, W, args.n_boot, args.seed + seed_off)
            except FileNotFoundError as e:
                print(f"  [warn] {e}", file=sys.stderr)
                continue
            all_results.append(res)
            for v in nu:
                all_samples.append({"symbol": sym, "contract": contract, "period": period, "W": W, "nu_abs": float(v)})

    if not all_results:
        print("[err] no results")
        return 1

    df = pd.DataFrame([r.to_row() for r in all_results])
    out = OUTPUT_DIR / f"{args.out_prefix}_summary.csv"
    df.to_csv(out, index=False)
    print(f"[done] wrote {out} ({len(df)} rows)")

    df_s = pd.DataFrame(all_samples)
    out_s = OUTPUT_DIR / f"{args.out_prefix}_samples.csv"
    df_s.to_csv(out_s, index=False)
    print(f"[done] wrote {out_s} ({len(df_s)} rows)")

    out_j = OUTPUT_DIR / f"{args.out_prefix}_summary.json"
    out_j.write_text(df.to_json(orient="records", indent=2), encoding="utf-8")
    print(f"[done] wrote {out_j}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
