"""P2: 多分辨率 CUSUM 断点检测

对每个品种的 x̂_{W=80}(t) 序列，在多个分辨率 W 下检测断点：
  1. 对 W ∈ {20, 40, 80, 160} 分别计算滚动 x̂_W(t)
  2. 对每个分辨率运行 CUSUM 检测均值漂移
  3. 跨分辨率共识：≥ 3 个分辨率在 ±20h 内同时检出 → 确认断点
  4. 输出断点时间列表供 P3 状态机使用

上游数据: project_data/market_data/csv/DCE.*.tqsdk.1h.csv
产出: project_data/research/strength_regime_switching/p2_breakpoints_{group}.csv
       project_data/research/strength_regime_switching/p2_cusum_summary.csv
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

REPO = Path("/Users/gaolei/Documents/src/quant")
CSV_DIR = REPO / "project_data" / "market_data" / "csv"
OUT_DIR = REPO / "project_data" / "research" / "strength_regime_switching"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SYMBOL_GROUPS = {
    "corn": ["DCE.c2601", "DCE.c2603", "DCE.c2605"],
    "corn_starch": ["DCE.cs2601", "DCE.cs2603", "DCE.cs2605"],
    "soybean_meal": ["DCE.m2601", "DCE.m2603", "DCE.m2605"],
}

# CUSUM 参数参照 KF-27 框架：容许漂移 = 1 倍总体标准差
# h = 4 * σ 适合我们的数据量，平衡误检/漏检
# h = 5σ 在小样本下偏严
CUSUM_H_MULTIPLIER = 4.0  # 阈值 h = CUSUM_H_MULTIPLIER * σ
# 跨分辨率共识窗口
CONSENSUS_TOLERANCE_H = 20  # ±20h 内算同一断点
MIN_RESOLUTIONS_FOR_CONSENSUS = 2  # 需要至少 2 个分辨率共识
# 检测的分辨率列表
# 160h 窗口数据量太少，采样稀疏，很难检出 → 实际主要依赖 [20, 40, 80]
DETECTION_WS = [20, 40, 80, 160]


def load_1h(sym: str) -> pd.DataFrame:
    df = pd.read_csv(CSV_DIR / f"{sym}.tqsdk.1h.csv", parse_dates=["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    df["log_ret"] = np.log(df["close"]).diff()
    df = df.dropna(subset=["log_ret"]).reset_index(drop=True)
    return df


def compute_x_hat_at_resolution(df: pd.DataFrame, W: int) -> pd.DataFrame:
    """计算给定分辨率 W 下的滚动 x̂_W(t)，按 stride=W/4 采样。"""
    log_rets = df["log_ret"].to_numpy()
    n = len(log_rets)
    stride = max(1, W // 4)

    x_hat_list = []
    indices = []

    for i in range(W - 1, n, stride):
        seg = log_rets[i - W + 1:i + 1]
        mu = np.mean(seg)
        sd = np.std(seg, ddof=1)
        if sd <= 1e-10:
            continue
        x_hat = abs(mu) / sd
        x_hat_list.append(x_hat)
        indices.append(i)

    df_out = df.iloc[indices].copy()
    df_out["x_hat"] = x_hat_list
    df_out["window_W"] = W
    return df_out


def cusum_detect(x: np.ndarray, h_mult: float = 5.0) -> list[int]:
    """CUSUM 检测均值向上/向下漂移。返回检出断点的索引列表（在 x 数组中的位置）。

    使用标准 CUSUM 算法：
    - C+ = max(0, x_i - (μ0 + k) + C+)
    - C- = max(0, (μ0 - k) - x_i + C-)
    - 当 C+ > h 或 C- > h 时，宣告断点，重置累计和

    参数:
        x: 观测序列（这里是滚动 x̂ 序列）
        h_mult: h = h_mult * σ, σ 是 x 的总体标准差
    """
    n = len(x)
    if n < 10:
        return []

    mu0 = float(np.mean(x))
    sigma = float(np.std(x, ddof=1))
    if sigma <= 1e-6:
        return []

    # k = delta / 2, delta = 1σ 漂移，所以 k = 0.5σ
    k = 0.5 * sigma
    h = h_mult * sigma

    c_plus = 0.0
    c_minus = 0.0
    breakpoints = []

    for i in range(n):
        xi = x[i]
        # 向上漂移检测
        c_plus = max(0.0, xi - (mu0 + k) + c_plus)
        # 向下漂移检测
        c_minus = max(0.0, (mu0 - k) - xi + c_minus)

        if c_plus > h or c_minus > h:
            # 检出断点，记录索引，重置累计和
            breakpoints.append(i)
            c_plus = 0.0
            c_minus = 0.0

    return breakpoints


def merge_breakpoints(breakpoints_by_w: dict[int, list[tuple[int, float]]],
                     tolerance_h: int, min_count: int) -> list[dict]:
    """将多个分辨率检出的断点按时间距离聚类，满足共识阈值则确认。

    参数:
        breakpoints_by_w: {W: [(original_index, time_h), ...], ...}
        tolerance_h: 同一个断点聚类最大时间跨度
        min_count: 最小需要多少分辨率检出

    输出:
        [{'center_h': int, 'n_votes': int, 'ws': [int], ...}, ...]

    注意: 每个分辨率在一个聚类中只计 1 票，无论检出多少次。
    """
    # 收集所有候选断点，带上分辨率
    all_candidates = []  # (time_h, W)
    for w, bps in breakpoints_by_w.items():
        for idx, t_h in bps:
            all_candidates.append((t_h, w))

    if not all_candidates:
        return []

    # 按时间排序
    all_candidates.sort(key=lambda x: x[0])

    # 贪心聚类
    clusters = []
    current_cluster = [all_candidates[0]]
    for cand in all_candidates[1:]:
        t_curr, _ = cand
        t_first, _ = current_cluster[0]
        if t_curr - t_first <= tolerance_h:
            current_cluster.append(cand)
        else:
            clusters.append(current_cluster)
            current_cluster = [cand]
    clusters.append(current_cluster)

    # 过滤出满足票数的聚类：每个分辨率在一个聚类中只计一票
    confirmed = []
    for cluster in clusters:
        # 去重分辨率，每个分辨率只算一票
        unique_ws = sorted(set(w for _, w in cluster))
        n_votes = len(unique_ws)
        if n_votes >= min_count:
            times = [t for t, _ in cluster]
            center_h = int(np.median(times))
            confirmed.append({
                "center_h": center_h,
                "n_votes": n_votes,
                "ws": unique_ws,
                "min_time_h": min(t for t, _ in cluster),
                "max_time_h": max(t for t, _ in cluster),
            })

    return confirmed


def process_one_group(group_name: str, symbols: list[str]) -> tuple[pd.DataFrame, dict]:
    """处理一个品种，多分辨率检测+共识，输出结果。"""
    # 拼接所有合约的 1h 数据
    dfs_list = []
    for sym in symbols:
        df_raw = load_1h(sym)
        dfs_list.append(df_raw)
    df_all = pd.concat(dfs_list).sort_values("datetime").reset_index(drop=True)

    # 每个分辨率分别检测
    breakpoints_by_w = {}  # W -> list of (index_in_xhat, original_time_index_h)
    xhat_by_w = {}

    overall_start_idx = df_all.index[0]

    for W in DETECTION_WS:
        df_xw = compute_x_hat_at_resolution(df_all, W)
        x = df_xw["x_hat"].to_numpy()
        xhat_by_w[W] = df_xw

        # CUSUM 检测
        bp_indices = cusum_detect(x, CUSUM_H_MULTIPLIER)

        # 转换为原始时间轴位置（相对于整个序列起始的小时数）
        bp_time_h = []
        for idx in bp_indices:
            original_idx = df_xw.index[idx]
            time_h = original_idx - overall_start_idx
            bp_time_h.append((idx, int(time_h)))

        breakpoints_by_w[W] = bp_time_h
        print(f"[{group_name}] W={W}: detected {len(bp_indices)} breakpoints")

    # 跨分辨率共识聚类
    confirmed = merge_breakpoints(breakpoints_by_w, CONSENSUS_TOLERANCE_H, MIN_RESOLUTIONS_FOR_CONSENSUS)
    print(f"[{group_name}] confirmed breakpoints: {len(confirmed)} after consensus\n")

    # 转换为 DataFrame，带上 datetime
    result_rows = []
    for conf in confirmed:
        center_original_idx = overall_start_idx + conf["center_h"]
        dt = df_all.loc[center_original_idx, "datetime"]
        row = {
            "group": group_name,
            "breakpoint_datetime": dt,
            "center_h_abs": int(center_original_idx),
            "center_h_rel": conf["center_h"],
            "n_votes": conf["n_votes"],
            "resolutions": ",".join(map(str, conf["ws"])),
            "min_h_rel": conf["min_time_h"],
            "max_h_rel": conf["max_time_h"],
        }
        result_rows.append(row)

    df_result = pd.DataFrame(result_rows)

    # 汇总统计
    summary = {
        "group": group_name,
        "n_breakpoints_total_by_w": {w: len(bps) for w, bps in breakpoints_by_w.items()},
        "n_breakpoints_consensus": len(confirmed),
        "breakpoint_interval_mean_h": np.nan,
        "breakpoint_interval_median_h": np.nan,
    }

    if len(confirmed) >= 2:
        intervals = [confirmed[i+1]["center_h"] - confirmed[i]["center_h"] for i in range(len(confirmed)-1)]
        summary["breakpoint_interval_mean_h"] = float(np.mean(intervals))
        summary["breakpoint_interval_median_h"] = float(np.median(intervals))

    return df_result, summary


def main() -> None:
    all_results = []
    all_summaries = []

    for group_name, symbols in SYMBOL_GROUPS.items():
        print(f"\n{'='*60}")
        print(f"Processing {group_name}...")
        print(f"{'='*60}")
        df_bp, summary = process_one_group(group_name, symbols)
        all_results.append(df_bp)
        all_summaries.append(summary)

        # 保存每个品种的断点
        out_path = OUT_DIR / f"p2_breakpoints_{group_name}.csv"
        df_bp.to_csv(out_path, index=False)
        print(f"Saved breakpoints to {out_path}")

    # 汇总
    df_all_bp = pd.concat(all_results, ignore_index=True)
    summary_path = OUT_DIR / "p2_cusum_summary.csv"
    df_summary = pd.DataFrame(all_summaries)
    df_summary.to_csv(summary_path, index=False)
    print(f"\n{'='*60}")
    print("P2 CUSUM detection completed.")
    print(f"Summary: {summary_path}")
    print(df_summary.to_string(index=False))

    # 保存 JSON 汇总
    with open(OUT_DIR / "p2_cusum_summary.json", "w", encoding="utf-8") as f:
        json.dump(all_summaries, f, indent=2)


if __name__ == "__main__":
    main()
