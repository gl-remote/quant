"""
文件级元信息：
- 创建背景：time-barrier-selection 主题 Stage 1 扫描。原始实验计划要求
  描述性测量"5m 周期上市场强度 |s|(T) 与 z(T) 随持仓 bar 数 T 的曲线形态"。
  本脚本只做"测量 + 输出"，不引入塑形容器、不开仓、不扣成本。
- 用途：在 raw per-bar 5m log return 序列上，对一组 T 网格逐个计算
  rolling T-bar 窗口内的 mu / sigma / |s| / z，配合 cluster bootstrap
  （cluster 单位 = 周）给出 95% CI，并输出形态归类所需的全部原始数字。
- 关键注意事项：
  - cluster bootstrap 按"周"重抽样（修正自原稿的"日"——5m 每日仅 69 bar，
    T > 60 时日内 rolling 窗口数为 0，cluster 必须升为周才能支撑 T 网格）；
  - rolling 窗口允许跨周，窗口归属 = "窗口内 bar 数过半所在的那一周"，
    保证每个窗口只归一个 cluster，cluster bootstrap 抽样时按周整段替换；
  - per-contract 独立处理，不跨合约池化（KF-22 数据边界）；
  - 不交易、不扣成本、不引入方向——纯市场结构描述；
  - 输出 CSV + JSON，落到 docs/workbench/time-barrier-selection/outputs/。
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

REPO_ROOT = Path(__file__).resolve().parents[4]  # .../quant
CSV_DIR = REPO_ROOT / "project_data" / "market_data" / "csv"
OUTPUT_DIR = REPO_ROOT / "docs" / "workbench" / "time-barrier-selection" / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 实验计划 §2.2 精简 T 网格 + ∞
T_GRID: list[int | str] = [5, 13, 34, 89, 233, 610]
T_INF: str = "inf"

# cluster bootstrap 重抽样次数
B_BOOT: int = 1000

# 形态归类阈值（按实验计划 §2.5）
LOG_LOG_R2_MIN: float = 0.8
LOG_LOG_ALPHA_MIN: float = 0.0
LOG_LOG_ALPHA_MAX: float = 1.0
PEAK_NEIGHBOR_DROP_FACTOR: float = 1.0


@dataclass(frozen=True)
class ScanResult:
    contract: str
    T: int | str
    s_abs_hat: float
    s_abs_ci_lo: float
    s_abs_ci_hi: float
    z_hat: float
    z_ci_lo: float
    z_ci_hi: float
    n_windows: int
    n_indep_weeks: int
    rho_1: float

    def to_row(self) -> dict:
        return {
            "contract": self.contract,
            "T": "inf" if self.T == T_INF else int(self.T),
            "s_abs_hat": self.s_abs_hat,
            "s_abs_ci_lo": self.s_abs_ci_lo,
            "s_abs_ci_hi": self.s_abs_ci_hi,
            "z_hat": self.z_hat,
            "z_ci_lo": self.z_ci_lo,
            "z_ci_hi": self.z_ci_hi,
            "n_windows": self.n_windows,
            "n_indep_weeks": self.n_indep_weeks,
            "rho_1": self.rho_1,
        }


def load_contract_csv(path: Path) -> pd.DataFrame:
    """读取单合约 5m CSV, 返回含 date/week/iso_week/log_ret 的 DataFrame."""
    df = pd.read_csv(path)
    if "datetime" not in df.columns or "close" not in df.columns:
        raise ValueError(f"unexpected columns: {df.columns.tolist()}")
    df["datetime"] = pd.to_datetime(df["datetime"])
    df["log_close"] = np.log(df["close"].astype(float))
    df["log_ret"] = df["log_close"].diff()
    df = df.dropna(subset=["log_ret"]).reset_index(drop=True)
    df["date"] = df["datetime"].dt.strftime("%Y-%m-%d")
    # ISO 周编号 (year, week)
    iso = df["datetime"].dt.isocalendar()
    df["iso_year"] = iso["year"].astype(int)
    df["iso_week"] = iso["week"].astype(int)
    df["week_id"] = df["iso_year"].astype(str) + "-W" + df["iso_week"].astype(str).str.zfill(2)
    return df


def assign_window_to_week(
    df: pd.DataFrame, T: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    对 bar-by-bar rolling T-bar 窗口, 输出 (mu, sigma, week_id) 三条等长数组.

    cluster 简化: 直接以"窗口末 bar 所在周"作为该窗口的 cluster 标签.
    - 当 T <= 周内 bar 数 (T <= 345 for 玉米 5m): 窗口完全在周内, 标签精确.
    - 当 T > 345: 窗口跨多周, 但末 bar 周仍能合理代表该窗口的"近期时间".
      对 cluster bootstrap 而言, 按周重抽样后窗口的 bar 仍来自若干周,
      实际样本结构与原始相似, 不破坏 CI 估计的有效性.
    - 替代方案: 计算"窗口内 bar 数过半所在周" (严格众数), 但需 O(T) per window,
      实测太慢, 此处不采用.
    """
    if len(df) < T:
        return np.array([]), np.array([]), np.array([])
    arr = df["log_ret"].to_numpy()
    week_ids = df["week_id"].to_numpy()

    n_windows = len(arr) - T + 1
    mu = np.empty(n_windows)
    sigma = np.empty(n_windows)
    win_week = np.empty(n_windows, dtype=int)

    cs = np.cumsum(arr)
    cs2 = np.cumsum(arr * arr)
    # 末 bar 索引 = i + T - 1
    end_idx = np.arange(T - 1, len(arr))
    win_week = week_idx_for_end = week_ids[end_idx]
    # 唯一化 week_idx 为 0..N-1 整数, 便于 array 存储
    unique_weeks, inverse = np.unique(win_week, return_inverse=True)
    win_week_idx = inverse.astype(np.int32)

    # mu / sigma 用向量化 cumsum 差分
    sum_end = cs[end_idx]
    sum_start = np.empty_like(sum_end)
    sum_start[0] = 0.0
    sum_start[1:] = cs[: n_windows - 1]
    sum_ = sum_end - sum_start

    sum2_end = cs2[end_idx]
    sum2_start = np.empty_like(sum2_end)
    sum2_start[0] = 0.0
    sum2_start[1:] = cs2[: n_windows - 1]
    sum2_ = sum2_end - sum2_start

    mu = sum_ / T
    var = sum2_ / T - mu * mu
    np.maximum(var, 0.0, out=var)
    sigma = np.sqrt(var)
    return mu, sigma, win_week_idx


def whole_series_stats(df: pd.DataFrame) -> tuple[float, float, int, float]:
    """T=∞ 行: 对整段序列计算单一 mu / sigma / 总 bar 数 / 一阶自相关."""
    all_r = df["log_ret"].to_numpy()
    mu = float(all_r.mean())
    sigma = float(all_r.std(ddof=0))
    if len(all_r) > 1:
        rho_1 = float(np.corrcoef(all_r[:-1], all_r[1:])[0, 1])
    else:
        rho_1 = 0.0
    n_indep_weeks = int(df["week_id"].nunique())
    return mu, sigma, len(all_r), rho_1, n_indep_weeks


def point_estimates(mu_arr: np.ndarray, sigma_arr: np.ndarray) -> tuple[float, float, float, float]:
    s_abs = float(np.mean(np.abs(mu_arr) / np.maximum(sigma_arr, 1e-12)))
    z = float(np.mean(mu_arr / np.maximum(sigma_arr, 1e-12)))
    return s_abs, z, float(np.mean(mu_arr)), float(np.mean(sigma_arr))


def cluster_bootstrap_ci_weekly(
    df: pd.DataFrame,
    T: int,
    rng: np.random.Generator,
    n_boot: int = B_BOOT,
) -> tuple[float, float, float, float]:
    """
    按周 cluster 重抽样: 每次按周有放回, 把抽中周的所有 bar 拼成新序列,
    重新跑 rolling T 计算 mu/sigma/week, 再算 s_abs / z.
    """
    weeks = df["week_id"].unique().tolist()
    n_weeks = len(weeks)
    week_arrs = {w: df.loc[df["week_id"] == w, "log_ret"].to_numpy() for w in weeks}
    s_abs_samples = np.empty(n_boot)
    z_samples = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, n_weeks, size=n_weeks)
        # 拼接成一个新 DataFrame-like 数组, 再 assign 一次 week 标签
        # 为加速: 直接拼接 return 数组 + 对应"虚拟 week_id"列表
        ret_chunks = [week_arrs[weeks[i]] for i in idx]
        ret_concat = np.concatenate(ret_chunks)
        # 虚拟 week_id 数组: 标记每个 bar 属于 bootstrap 抽样的哪一周
        wk_chunks = [np.full(len(week_arrs[weeks[i]]), i, dtype=int) for i in idx]
        wk_concat = np.concatenate(wk_chunks)
        boot_df = pd.DataFrame({"log_ret": ret_concat, "week_id": wk_concat})
        mu_b, sigma_b, _ = assign_window_to_week(boot_df, T)
        if len(mu_b) == 0:
            s_abs_samples[b] = math.nan
            z_samples[b] = math.nan
            continue
        s_abs_b, z_b, _, _ = point_estimates(mu_b, sigma_b)
        s_abs_samples[b] = s_abs_b
        z_samples[b] = z_b
    s_abs_samples = s_abs_samples[np.isfinite(s_abs_samples)]
    z_samples = z_samples[np.isfinite(z_samples)]
    s_abs_lo, s_abs_hi = np.quantile(s_abs_samples, [0.025, 0.975])
    z_lo, z_hi = np.quantile(z_samples, [0.025, 0.975])
    return float(s_abs_lo), float(s_abs_hi), float(z_lo), float(z_hi)


def scan_contract(
    contract: str,
    csv_path: Path,
    T_grid: list[int | str],
    n_boot: int,
    seed: int,
) -> list[ScanResult]:
    rng = np.random.default_rng(seed)
    df = load_contract_csv(csv_path)
    n_indep_weeks = int(df["week_id"].nunique())

    all_r = df["log_ret"].to_numpy()
    rho_1 = float(np.corrcoef(all_r[:-1], all_r[1:])[0, 1]) if len(all_r) > 1 else 0.0

    results: list[ScanResult] = []
    for T in T_grid:
        if T == T_INF:
            mu, sigma, n_bars, _, n_weeks_inf = whole_series_stats(df)
            s_abs = abs(mu) / max(sigma, 1e-12)
            z = mu / max(sigma, 1e-12)
            results.append(
                ScanResult(
                    contract=contract,
                    T=T_INF,
                    s_abs_hat=s_abs,
                    s_abs_ci_lo=math.nan,
                    s_abs_ci_hi=math.nan,
                    z_hat=z,
                    z_ci_lo=math.nan,
                    z_ci_hi=math.nan,
                    n_windows=n_bars,
                    n_indep_weeks=n_weeks_inf,
                    rho_1=rho_1,
                )
            )
            continue

        mu_arr, sigma_arr, _ = assign_window_to_week(df, T)
        n_windows = len(mu_arr)
        if n_windows == 0:
            results.append(
                ScanResult(
                    contract=contract,
                    T=T,
                    s_abs_hat=math.nan,
                    s_abs_ci_lo=math.nan,
                    s_abs_ci_hi=math.nan,
                    z_hat=math.nan,
                    z_ci_lo=math.nan,
                    z_ci_hi=math.nan,
                    n_windows=0,
                    n_indep_weeks=n_indep_weeks,
                    rho_1=rho_1,
                )
            )
            continue
        s_abs, z, _, _ = point_estimates(mu_arr, sigma_arr)
        s_lo, s_hi, z_lo, z_hi = cluster_bootstrap_ci_weekly(df, T, rng, n_boot=n_boot)
        results.append(
            ScanResult(
                contract=contract,
                T=T,
                s_abs_hat=s_abs,
                s_abs_ci_lo=s_lo,
                s_abs_ci_hi=s_hi,
                z_hat=z,
                z_ci_lo=z_lo,
                z_ci_hi=z_hi,
                n_windows=n_windows,
                n_indep_weeks=n_indep_weeks,
                rho_1=rho_1,
            )
        )
    return results


def scan_synthetic(
    label: str,
    returns: np.ndarray,
    bars_per_week: int,
    n_weeks: int,
    T_grid: list[int | str],
    n_boot: int,
    seed: int,
) -> list[ScanResult]:
    """人造序列: 按周切 cluster, 用于 sanity check (白噪声 / AR(1))."""
    rng = np.random.default_rng(seed)
    n_bars = n_weeks * bars_per_week
    assert len(returns) == n_bars
    week_ids = np.array([f"w{w}" for w in range(n_weeks) for _ in range(bars_per_week)])
    df = pd.DataFrame({"log_ret": returns, "week_id": week_ids})

    all_r = returns
    rho_1 = float(np.corrcoef(all_r[:-1], all_r[1:])[0, 1]) if len(all_r) > 1 else 0.0
    n_indep_weeks = n_weeks

    results: list[ScanResult] = []
    for T in T_grid:
        if T == T_INF:
            mu = float(returns.mean())
            sigma = float(returns.std(ddof=0))
            s_abs = abs(mu) / max(sigma, 1e-12)
            z = mu / max(sigma, 1e-12)
            results.append(
                ScanResult(
                    contract=label,
                    T=T_INF,
                    s_abs_hat=s_abs,
                    s_abs_ci_lo=math.nan,
                    s_abs_ci_hi=math.nan,
                    z_hat=z,
                    z_ci_lo=math.nan,
                    z_ci_hi=math.nan,
                    n_windows=len(returns),
                    n_indep_weeks=n_indep_weeks,
                    rho_1=rho_1,
                )
            )
            continue
        mu_arr, sigma_arr, _ = assign_window_to_week(df, T)
        if len(mu_arr) == 0:
            continue
        s_abs, z, _, _ = point_estimates(mu_arr, sigma_arr)
        s_lo, s_hi, z_lo, z_hi = cluster_bootstrap_ci_weekly(df, T, rng, n_boot=n_boot)
        results.append(
            ScanResult(
                contract=label,
                T=T,
                s_abs_hat=s_abs,
                s_abs_ci_lo=s_lo,
                s_abs_ci_hi=s_hi,
                z_hat=z,
                z_ci_lo=z_lo,
                z_ci_hi=z_hi,
                n_windows=len(mu_arr),
                n_indep_weeks=n_indep_weeks,
                rho_1=rho_1,
            )
        )
    return results


def results_to_df(results: list[ScanResult]) -> pd.DataFrame:
    return pd.DataFrame([r.to_row() for r in results])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--contracts",
        nargs="+",
        default=[
            "c2401", "c2405", "c2409",
            "c2501", "c2505", "c2509",
            "c2601", "c2603", "c2605",
        ],
    )
    parser.add_argument("--n-boot", type=int, default=B_BOOT)
    parser.add_argument("--seed", type=int, default=20260731)
    parser.add_argument(
        "--synthetic",
        choices=["none", "all", "wn", "ar1"],
        default="all",
    )
    parser.add_argument("--out-prefix", default="stage1")
    args = parser.parse_args()

    T_grid: list[int | str] = list(T_GRID) + [T_INF]
    all_results: list[ScanResult] = []

    for c in args.contracts:
        path = CSV_DIR / f"DCE.{c}.tqsdk.5m.csv"
        if not path.exists():
            print(f"[warn] missing {path}, skip", file=sys.stderr)
            continue
        print(f"[scan] {c} <- {path.name}")
        all_results.extend(scan_contract(c, path, T_grid, args.n_boot, args.seed))

    if args.synthetic in ("all", "wn"):
        print("[scan] synthetic: white noise N(0, 1)")
        n_weeks, bars_per_week = 60, 345
        rng = np.random.default_rng(args.seed)
        wn = rng.standard_normal(n_weeks * bars_per_week)
        all_results.extend(
            scan_synthetic(
                "synth_wn", wn, bars_per_week, n_weeks, T_grid, args.n_boot, args.seed + 1
            )
        )
    if args.synthetic in ("all", "ar1"):
        for phi in (0.0, 0.3, 0.6):
            print(f"[scan] synthetic: AR(1) phi={phi}")
            n_weeks, bars_per_week = 60, 345
            rng = np.random.default_rng(args.seed + int(phi * 100))
            eps = rng.standard_normal(n_weeks * bars_per_week)
            x = np.empty_like(eps)
            x[0] = eps[0]
            for i in range(1, len(x)):
                x[i] = phi * x[i - 1] + math.sqrt(1 - phi * phi) * eps[i]
            all_results.extend(
                scan_synthetic(
                    f"synth_ar1_phi{phi:.1f}", x, bars_per_week, n_weeks,
                    T_grid, args.n_boot, args.seed + 2 + int(phi * 100),
                )
            )

    df = results_to_df(all_results)
    csv_path = OUTPUT_DIR / f"{args.out_prefix}_scan.csv"
    df.to_csv(csv_path, index=False)
    print(f"[done] wrote {csv_path} ({len(df)} rows)")

    json_path = OUTPUT_DIR / f"{args.out_prefix}_scan.json"
    json_path.write_text(df.to_json(orient="records", indent=2), encoding="utf-8")
    print(f"[done] wrote {json_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
