"""P4: 分层参数适配回测 —— 三 regime 各自 KF-27 最优参数

文件级元信息：
- 创建背景：P0-P3 完成后进入 P4，需要对每个 regime 分段分别计算 KF-27 最优参数。
- 用途：对比分层参数 vs 全时段静态参数，验证 regime 分层是否带来绩效提升。
- 注意事项：基于 P3 输出的 regime 分段，每个 regime 用自身强度分布拟合 FoldedNormal，
  然后 KF-27 优化得到最优 (K_S, K_T, τ)。LOW 强度不开仓。

实验设计：
1. 读取 P3 输出的 regime 分段（LOW/MID/HIGH）
2. 对每个品种的每个 regime：
   - 提取该分段内的所有 x_hat 观测
   - 计算经验均值 μ_D 和标准差 σ_D
   - 拟合 FoldedNormal 分布
   - KF-27 优化计算最优参数（目标：年化 Sharpe）
3. 对比：分层参数 vs 全时段静态参数
4. 输出：参数对照表、预期 Sharpe/年化对比表
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
# __file__ = .../docs/research/themes/strength-regime-switching/raw-scripts/p4...py
# 需要向上 4 级到项目根：raw-scripts(1) → strength-regime-switching(2) → themes(3) → research(4) → docs(5) → repo root(6)
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

# 处理的品种
GROUPS = [
    {"name": "corn", "symbols": ["DCE.c2601", "DCE.c2603", "DCE.c2605"]},
    {"name": "corn_starch", "symbols": ["DCE.cs2601", "DCE.cs2603", "DCE.cs2605"]},
    {"name": "soybean_meal", "symbols": ["DCE.m2601", "DCE.m2603", "DCE.m2605"]},
]


def load_xhat_timeseries(group_name: str) -> pd.DataFrame:
    """加载 P1 输出的 x_hat 时间序列

    注意：x_hat 是滚动窗口输出，W=80，步长=4h。
    CSV 中已经包含 datetime 列，我们可以按时间范围筛选。
    """
    x_path = CSV_DIR / f"p1_xhat_ts_{group_name}.csv"
    if not x_path.exists():
        raise FileNotFoundError(f"x_hat timeseries not found: {x_path}")
    df = pd.read_csv(x_path, parse_dates=["datetime"])
    # 按 datetime 排序确保顺序正确
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
    """从时间序列中提取特定 regime 的所有 x_hat 观测

    segment_df 中每个分段有 start_datetime 和 end_datetime，我们按时间范围筛选 x_hat。
    这比索引更可靠，因为两者都用 datetime 对齐。
    """
    # 获取该 regime 所有分段的索引范围
    # strip whitespace in case there's any CSV formatting issue
    regime_segments = segment_df[segment_df["regime"].str.strip() == regime.strip()]
    x_list = []
    for _, seg in regime_segments.iterrows():
        start_dt = pd.to_datetime(seg["start_datetime"])
        end_dt = pd.to_datetime(seg["end_datetime"])
        # 选出 datetime 在 [start_dt, end_dt] 范围内的 x_hat
        mask = (df_x["datetime"] >= start_dt) & (df_x["datetime"] <= end_dt)
        segment_x = df_x[mask]["x_hat"].to_numpy()
        if len(segment_x) > 0:
            x_list.append(segment_x)
    if not x_list:
        return np.array([])
    return np.concatenate(x_list)


def optimize_regime_parameters(x_array: np.ndarray, c_side: float = C_SIDE) -> dict | None:
    """对一个 regime 的 x 数组，用 KF-27 计算最优参数"""
    if len(x_array) < 10:
        # 样本太少，无法可靠估计分布
        return None

    mu_D = float(np.mean(x_array))
    sd_D = float(np.std(x_array, ddof=1))

    if mu_D <= 1e-6:
        return None

    # 拟合 FoldedNormal 分布
    dist = FoldedNormal(mu_D=mu_D, sd_D=sd_D)
    dist.fit()

    # KF-27 参数配置
    params = KF27Params(
        distribution=dist,
        c_side=c_side,
        sigma_bar=1.0,
        year_hours=YEAR_HOURS,
        k_s_min=1.0,
        k_s_max=6.0,
        k_t_max=12.0,
        rr_grid=(2.0, 2.5, 3.0, 3.5, 4.0),
        tau_grid=(0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90),
        k_s_step=0.25,
    )

    try:
        result = optimize_kf27(params, objective="sharpe_year")
    except RuntimeError:
        # 没有可行解（e_net 全 ≤ 0，分布过弱或成本过高）
        return None

    return {
        "n_obs": len(x_array),
        "mu_D": mu_D,
        "sd_D": sd_D,
        "k_s": result.k_s,
        "k_t": result.k_t,
        "rr": result.rr,
        "tau": result.tau,
        "x_star": result.x_star,
        "n_year": result.n_year,
        "e_net": result.e_net,
        "sharpe_year": result.sharpe_year,
        "ann_pct_r1": result.ann_pct_r1,
    }


def main():
    all_results = []

    for group in GROUPS:
        group_name = group["name"]
        print(f"\n{'='*70}")
        print(f"Processing {group_name} — KF-27 分层参数优化")
        print(f"{'='*70}")

        # 加载数据
        df_x = load_xhat_timeseries(group_name)
        segment_df = load_regime_segments(group_name)
        print(f"Loaded x_hat: {len(df_x)} points from {df_x['datetime'].min()} to {df_x['datetime'].max()}")
        print(f"Loaded segments: {len(segment_df)} total segments")

        # 全时段基准（静态参数）
        print("\n--- Full period (static baseline) ---")
        all_x_full = df_x["x_hat"].to_numpy()
        full_result = optimize_regime_parameters(all_x_full)
        if full_result:
            print(f"  n_obs: {full_result['n_obs']}")
            print(f"  mu_D: {full_result['mu_D']:.4f}, sd_D: {full_result['sd_D']:.4f}")
            print(f"  K_S*: {full_result['k_s']:.2f}, K_T*: {full_result['k_t']:.2f}, RR*: {full_result['rr']:.2f}")
            print(f"  tau*: {full_result['tau']:.2f}, sharpe_year: {full_result['sharpe_year']:.3f}")
            print(f"  ann_pct@r1%: {full_result['ann_pct_r1']:.2f}%")
        else:
            print("  NO feasible solution (all e_net ≤ 0)")
        all_results.append({
            "group": group_name,
            "regime": "FULL",
            **(full_result if full_result else {"n_obs": len(all_x_full), "mu_D": np.mean(all_x_full), "sd_D": np.std(all_x_full)}),
        })

        # 按 regime 分层优化
        for regime in ["LOW", "MID", "HIGH"]:
            print(f"\n--- Regime: {regime} ---")
            x_regime = extract_regime_x(df_x, segment_df, regime)
            if len(x_regime) == 0:
                print(f"  No observations for this regime → skipped")
                all_results.append({
                    "group": group_name,
                    "regime": regime,
                    "n_obs": 0,
                })
                continue

            result = optimize_regime_parameters(x_regime)
            if result:
                print(f"  n_obs: {result['n_obs']}")
                print(f"  mu_D: {result['mu_D']:.4f}, sd_D: {result['sd_D']:.4f}")
                print(f"  K_S*: {result['k_s']:.2f}, K_T*: {result['k_t']:.2f}, RR*: {result['rr']:.2f}")
                print(f"  tau*: {result['tau']:.2f}, sharpe_year: {result['sharpe_year']:.3f}")
                print(f"  ann_pct@r1%: {result['ann_pct_r1']:.2f}%")
            else:
                print(f"  n_obs: {len(x_regime)}, mu_D: {np.mean(x_regime):.4f} → NO feasible solution (e_net ≤ 0)")

            all_results.append({
                "group": group_name,
                "regime": regime,
                **(result if result else {"n_obs": len(x_regime), "mu_D": np.mean(x_regime), "sd_D": np.std(x_regime)}),
            })

    # 保存结果
    result_df = pd.DataFrame(all_results)
    out_path = OUT_DIR / "p4_kf27_layered_parameters.csv"
    result_df.to_csv(out_path, index=False, float_format="%.6f")
    print(f"\n{'='*70}")
    print(f"Saved complete results to: {out_path}")
    print(f"{'='*70}")

    # 打印汇总表格
    print("\n=== Summary Table ===")
    summary = result_df[["group", "regime", "n_obs", "mu_D", "k_s", "rr", "sharpe_year", "ann_pct_r1"]]
    print(summary.to_string(index=False, na_rep="-"))


if __name__ == "__main__":
    main()
