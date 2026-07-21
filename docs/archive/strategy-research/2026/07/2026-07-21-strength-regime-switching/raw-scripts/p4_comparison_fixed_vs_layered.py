"""P4 对比实验：全时段固定参数 vs regime 分层自适应

对比两种策略：
1. **全时段固定参数**：不区分 regime，全时段用同一组 KF-27 参数
2. **regime 分层自适应**：每个 regime 用自己优化的参数

验证："全时段都用高止损" vs "根据 regime 调整" 哪个好。
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
REPO = Path(__file__).parent
for _ in range(5):
    REPO = REPO.parent
sys.path.insert(0, str(REPO))

import pandas as pd
import numpy as np

from workspace.research.distribution import FoldedNormal
from workspace.research.optimizer import KF27Params, optimize_kf27

CSV_DIR = REPO / "project_data" / "research" / "strength_regime_switching"
OUT_DIR = REPO / "project_data" / "research" / "strength_regime_switching"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 单边交易成本（固定 0.077 ATR，与 KF-27 基准一致）
C_SIDE = 0.077
# 年化交易小时数（1h K线）
YEAR_HOURS = 1625.0

GROUPS = [
    {"name": "corn", "symbols": ["DCE.c2601", "DCE.c2603", "DCE.c2605"]},
    {"name": "corn_starch", "symbols": ["DCE.cs2601", "DCE.cs2603", "DCE.cs2605"]},
    {"name": "soybean_meal", "symbols": ["DCE.m2601", "DCE.m2603", "DCE.m2605"]},
]


def load_xhat_timeseries(group_name: str) -> pd.DataFrame:
    """加载 P1 输出的 x_hat 时间序列"""
    x_path = CSV_DIR / f"p1_xhat_ts_{group_name}.csv"
    if not x_path.exists():
        raise FileNotFoundError(f"x_hat timeseries not found: {x_path}")
    df = pd.read_csv(x_path, parse_dates=["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    return df


def load_regime_segments(group_name: str) -> pd.DataFrame:
    """加载 P3 输出的 regime 分段"""
    seg_path = CSV_DIR / f"p3_regime_segments_{group_name}.csv"
    if not seg_path.exists():
        raise FileNotFoundError(f"regime segments not found: {seg_path}")
    df = pd.read_csv(seg_path, parse_dates=["start_datetime", "end_datetime"])
    return df


def extract_regime_x(df_x: pd.DataFrame, segment_df: pd.DataFrame, regime: str) -> np.ndarray:
    """按时间范围提取特定 regime 的所有 x_hat 观测"""
    regime_segments = segment_df[segment_df["regime"].str.strip() == regime.strip()]
    x_list = []
    for _, seg in regime_segments.iterrows():
        start_dt = pd.to_datetime(seg["start_datetime"])
        end_dt = pd.to_datetime(seg["end_datetime"])
        mask = (df_x["datetime"] >= start_dt) & (df_x["datetime"] <= end_dt)
        segment_x = df_x[mask]["x_hat"].to_numpy()
        if len(segment_x) > 0:
            x_list.append(segment_x)
    if not x_list:
        return np.array([])
    return np.concatenate(x_list)


def optimize_parameters(x_array: np.ndarray, k_s_fixed: float = None, rr_fixed: float = None) -> dict | None:
    """对 x 数组优化 KF-27 参数

    Args:
        x_array: x_hat 数组
        k_s_fixed: 如果固定 K_S 则传入值，None 表示自由优化
        rr_fixed: 如果固定 RR 则传入值，None 表示自由优化
    """
    if len(x_array) < 10:
        return None

    mu_D = float(np.mean(x_array))
    sd_D = float(np.std(x_array, ddof=1))

    if mu_D <= 1e-6:
        return None

    dist = FoldedNormal(mu_D=mu_D, sd_D=sd_D)
    dist.fit()

    params = KF27Params(
        distribution=dist,
        c_side=C_SIDE,
        sigma_bar=1.0,
        year_hours=YEAR_HOURS,
        k_s_min=1.0,
        k_s_max=6.0,
        k_t_max=12.0,
        rr_grid=(2.0, 2.5, 3.0, 3.5, 4.0),
        tau_grid=(0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90),
        k_s_step=0.25,
    )

    # 如果固定 K_S 和 RR，就只在给定值上搜索 tau
    if k_s_fixed is not None and rr_fixed is not None:
        k_t_fixed = k_s_fixed * rr_fixed
        best_result = None
        best_value = -np.inf
        for tau in params.tau_grid:
            result = None
            try:
                from workspace.research.optimizer import _evaluate
                result = _evaluate(params, k_s_fixed, k_t_fixed, tau)
            except Exception:
                continue
            if result is None or result.e_net <= 0:
                continue
            value = result.sharpe_year
            if value > best_value:
                best_value = value
                best_result = result
        return best_result

    try:
        result = optimize_kf27(params, objective="sharpe_year")
    except RuntimeError:
        return None

    return result


def calculate_combined_performance(
    df_x: pd.DataFrame,
    segment_df: pd.DataFrame,
    param_full: dict,
    param_by_regime: dict,
) -> dict:
    """计算分层策略的综合预期绩效：按时间加权平均

    每个分段用该分段 regime 的参数，计算该分段的预期 sharpe，
    然后按该分段的观测数加权得到整体预期。
    """
    total_obs = 0
    weighted_sharpe = 0.0
    weighted_ann_pct = 0.0

    for _, seg in segment_df.iterrows():
        regime = seg["regime"].strip()
        start_dt = pd.to_datetime(seg["start_datetime"])
        end_dt = pd.to_datetime(seg["end_datetime"])
        mask = (df_x["datetime"] >= start_dt) & (df_x["datetime"] <= end_dt)
        n_obs = int(mask.sum())
        total_obs += n_obs

        if regime in param_by_regime and param_by_regime[regime] is not None:
            sharpe = param_by_regime[regime].sharpe_year
            ann_pct = param_by_regime[regime].ann_pct_r1
        else:
            # LOW regime 不开仓，贡献 0
            sharpe = 0.0
            ann_pct = 0.0

        weighted_sharpe += n_obs * sharpe
        weighted_ann_pct += n_obs * ann_pct

    if total_obs == 0:
        return {"combined_sharpe": 0, "combined_ann_pct": 0, "total_obs": 0}

    return {
        "combined_sharpe": weighted_sharpe / total_obs,
        "combined_ann_pct": weighted_ann_pct / total_obs,
        "total_obs": total_obs,
    }


def main():
    print("=" * 80)
    print("P4 对比实验：全时段固定高止损 vs regime 分层自适应")
    print("=" * 80)
    print("\n对比方案：")
    print("  A. 全时段固定参数：K_S=3.0, RR=4.0（你说的'全时段都用高止损'）")
    print("  B. regime 分层自适应：每个 regime 独立优化")
    print("  C. 全时段自由优化（基准）")
    print()

    all_results = []

    for group in GROUPS:
        group_name = group["name"]
        print(f"\n{'='*80}")
        print(f"品种: {group_name}")
        print(f"{'-'*80}")

        df_x = load_xhat_timeseries(group_name)
        segment_df = load_regime_segments(group_name)
        print(f"Loaded: {len(df_x)} x_hat points, {len(segment_df)} segments")

        # ========== 方案 C: 全时段自由优化（基准） ==========
        print("\n[方案 C] 全时段自由优化（基准）")
        x_full = df_x["x_hat"].to_numpy()
        result_c = optimize_parameters(x_full)
        if result_c:
            print(f"  n_obs: {len(x_full)}, mu_D: {np.mean(x_full):.4f}")
            print(f"  K_S*: {result_c.k_s:.2f}, K_T*: {result_c.k_t:.2f}, RR*: {result_c.rr:.2f}")
            print(f"  tau*: {result_c.tau:.2f}, sharpe_year: {result_c.sharpe_year:.3f}")
        else:
            print("  NO feasible solution")

        # ========== 方案 A: 全时段固定高止损（你的猜想：K_S=3, RR=4 固定） ==========
        print("\n[方案 A] 全时段固定高止损 (K_S=3.0, RR=4.0)")
        result_a = optimize_parameters(x_full, k_s_fixed=3.0, rr_fixed=4.0)
        if result_a:
            print(f"  n_obs: {len(x_full)}, mu_D: {np.mean(x_full):.4f}")
            print(f"  K_S: {result_a.k_s:.2f}, K_T: {result_a.k_t:.2f}, RR: {result_a.rr:.2f}")
            print(f"  tau*: {result_a.tau:.2f}, sharpe_year: {result_a.sharpe_year:.3f}")
        else:
            print("  NO feasible solution")

        # ========== 方案 B: regime 分层自适应 ==========
        print("\n[方案 B] regime 分层自适应（每个 regime 独立优化 K_S/RR/tau）")
        result_b_by_regime = {}
        for regime in ["LOW", "MID", "HIGH"]:
            x_reg = extract_regime_x(df_x, segment_df, regime)
            if len(x_reg) == 0:
                result_b_by_regime[regime] = None
                print(f"  {regime}: 0 observations → skipped")
                continue
            result_b = optimize_parameters(x_reg)
            result_b_by_regime[regime] = result_b
            if result_b:
                print(f"  {regime}: n_obs={len(x_reg)}, mu_D={np.mean(x_reg):.4f} "
                      f"→ K_S={result_b.k_s:.2f}, RR={result_b.rr:.2f}, "
                      f"tau={result_b.tau:.2f}, sharpe={result_b.sharpe_year:.3f}")
            else:
                print(f"  {regime}: n_obs={len(x_reg)}, mu_D={np.mean(x_reg):.4f} → NO feasible")

        # 计算综合绩效
        combined = calculate_combined_performance(df_x, segment_df, result_c, result_b_by_regime)
        print(f"\n  [方案 B 综合绩效] (按观测数加权):")
        print(f"  combined sharpe_year: {combined['combined_sharpe']:.3f}")
        print(f"  combined ann_pct@r1%: {combined['combined_ann_pct']:.3f}%")

        # 保存结果
        all_results.append({
            "group": group_name,
            "C_sharpe": result_c.sharpe_year if result_c else None,
            "C_ann_pct": result_c.ann_pct_r1 if result_c else None,
            "C_k_s": result_c.k_s if result_c else None,
            "C_rr": result_c.rr if result_c else None,
            "C_tau": result_c.tau if result_c else None,
            "A_sharpe": result_a.sharpe_year if result_a else None,
            "A_ann_pct": result_a.ann_pct_r1 if result_a else None,
            "A_tau": result_a.tau if result_a else None,
            "B_combined_sharpe": combined["combined_sharpe"],
            "B_combined_ann_pct": combined["combined_ann_pct"],
        })

    # 输出汇总表格
    print("\n" + "=" * 80)
    print("=== 最终汇总 ===")
    print("=" * 80)
    print(f"\n{'品种':<12} {'方案':<10} {'K_S':<6} {'RR':<6} {'tau':<6} {'sharpe':<8} {'ann_pct%':<8}")
    print("-" * 60)
    for res in all_results:
        group = res["group"]
        # 方案 C
        if res["C_sharpe"] is not None:
            print(f"{group:<12} {'C-自由优化':<10} {res['C_k_s']:<.2f} {res['C_rr']:<.2f} {res['C_tau']:<.2f} {res['C_sharpe']:<.3f} {res['C_ann_pct']:<.3f}")
        # 方案 A
        if res["A_sharpe"] is not None:
            print(f"{group:<12} {'A-固定KS=3':<10} 3.00  4.00  {res['A_tau']:<.2f} {res['A_sharpe']:<.3f} {res['A_ann_pct']:<.3f}")
        # 方案 B
        print(f"{group:<12} {'B-分层自适应':<10}  -     -     -    {res['B_combined_sharpe']:<.3f} {res['B_combined_ann_pct']:<.3f}")
        print("-" * 60)

    # 保存结果到 CSV
    result_df = pd.DataFrame(all_results)
    out_path = OUT_DIR / "p4_comparison_fixed_vs_layered.csv"
    result_df.to_csv(out_path, index=False, float_format="%.6f")
    print(f"\nSaved comparison results to: {out_path}")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
