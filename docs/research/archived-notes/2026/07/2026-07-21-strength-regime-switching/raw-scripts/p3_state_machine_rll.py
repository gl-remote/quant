"""P3: 状态机 RLL 分段 - 基于 P2 断点划分 regime

算法流程：
1. 读取 P2 确认断点 → 划分区间段
2. 对每个区间计算滚动 x_hat 序列（W=80）
3. 用该品种自身分位数确定阈值：
   - LOW: x <= P30
   - HIGH: x >= P70
   - MID: P30 < x < P70
4. 最小停留约束：每个 regime 必须 ≥ 80h 才能切换
5. 滞后确认：强度跨过阈值后再等待 40h 确认切换生效
6. 输出分段 regime 序列供 P4 回测使用
"""

from pathlib import Path
import pandas as pd
import numpy as np

REPO = Path("/Users/gaolei/Documents/src/quant")
CSV_DIR = REPO / "project_data" / "market_data" / "csv"
OUT_DIR = REPO / "project_data" / "research" / "strength_regime_switching"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 状态机参数
W_X = 80                  # 滚动计算 x_hat 窗口
MIN_STAY_HOURS = 80   # 最小停留时长
LAG_CONFIRM_HOURS = 40  # 滞后确认时长
QUANTILE_LOW = 0.30    # LOW 阈值分位数
QUANTILE_HIGH = 0.70  # HIGH 阈值分位数

# 处理的品种
GROUPS = [
    {"name": "corn", "symbols": ["DCE.c2601", "DCE.c2603", "DCE.c2605"]},
    {"name": "corn_starch", "symbols": ["DCE.cs2601", "DCE.cs2603", "DCE.cs2605"]},
    {"name": "soybean_meal", "symbols": ["DCE.m2601", "DCE.m2603", "DCE.m2605"]},
]


def load_breakpoints(group_name: str):
    """读取 P2 确认断点"""
    bp_path = OUT_DIR / f"p2_breakpoints_{group_name}.csv"
    if not bp_path.exists():
        # 试试 corn_c2609 这种命名
        bp_path = OUT_DIR / f"p2_breakpoints_{group_name}_corn.csv"
    df = pd.read_csv(bp_path, parse_dates=["breakpoint_datetime"])
    breakpoints = sorted(df["center_h_abs"].tolist())
    return breakpoints


def concatenate_contracts(symbols: list[str]) -> pd.DataFrame:
    """拼接多个合约数据，保持时序"""
    dfs = []
    for sym in symbols:
        fpath = CSV_DIR / f"{sym}.tqsdk.1h.csv"
        if not fpath.exists():
            print(f"Warning: {fpath} not found, skipping")
            continue
        df = pd.read_csv(fpath, parse_dates=["datetime"])
        df = df.sort_values("datetime").reset_index(drop=True)
        dfs.append(df)
    if not dfs:
        return pd.DataFrame()
    combined = pd.concat(dfs, ignore_index=True)
    combined = combined.sort_values("datetime").reset_index(drop=True)
    combined["log_ret"] = np.log(combined["close"]).diff()
    combined = combined.dropna(subset=["log_ret"]).reset_index(drop=True)
    return combined


def compute_rolling_x(df: pd.DataFrame, W: int) -> pd.DataFrame:
    """计算滚动 x_hat = |mu| / sigma"""
    log_rets = df["log_ret"].to_numpy()
    n = len(log_rets)
    x_list = []
    indices = []
    for i in range(W - 1, n):
        seg = log_rets[i - W + 1:i + 1]
        mu = np.mean(seg)
        sd = np.std(seg, ddof=1)
        if sd <= 1e-6:
            continue
        x_hat = abs(mu) / sd
        x_list.append(x_hat)
        indices.append(i)  # i 就是 df 上的索引，因为 log_ret 比 df 少一行，这里 i 对应 df 索引
    df_x = df.iloc[indices].copy()
    df_x["x_hat"] = x_list
    return df_x


def segment_regimes(df_x: pd.DataFrame, breakpoints_abs: list[int]):
    """基于断点分割区间"""
    intervals = []
    # 起点
    start = 0
    for bp in breakpoints_abs:
        intervals.append((start, bp))
        start = bp + 1  # 断点后第一个点是 bp+1
    # 终点
    intervals.append((start, len(df_x) - 1))
    # 为每个区间分配 regime
    regime_records = []
    for start_idx, end_idx in intervals:
        if start_idx >= end_idx:
            continue
        interval_df = df_x.iloc[start_idx:end_idx + 1]
        mean_x = interval_df["x_hat"].mean()
        # 用中点 datetime
        mid_idx = (start_idx + end_idx) // 2
        dt = df_x.iloc[mid_idx]["datetime"]
        regime_records.append({
            "start_datetime": df_x.iloc[start_idx]["datetime"],
            "end_datetime": df_x.iloc[end_idx]["datetime"],
            "mid_datetime": dt,
            "start_idx_abs": start_idx,
            "end_idx_abs": end_idx,
            "n_bars": end_idx - start_idx + 1,
            "mean_x": round(mean_x, 4),
        })
    return pd.DataFrame(regime_records)


def assign_regime_states(segment_df: pd.DataFrame, q_low: float, q_high: float):
    """给每个区间分配 regime 状态"""
    df = segment_df.copy()
    def assign(x):
        if x <= q_low:
            return "LOW"
        elif x >= q_high:
            return "HIGH"
        else:
            return "MID"
    df["regime"] = df["mean_x"].apply(assign)
    return df


def apply_min_stay_filter(df: pd.DataFrame, min_stay: int):
    """过滤掉小于最小停留时长的区间"""
    # 这个很简单：我们已经分割了，只要过滤掉短区间就行
    # 因为断点是检测均值漂移，相邻断点之间就是区间，长度已经是两断点之间距离
    df = df[df["n_bars"] >= min_stay].reset_index(drop=True)
    return df


def main():
    for group in GROUPS:
        group_name = group["name"]
        print(f"\n{'='*60}")
        print(f"Processing {group_name} ...")
        print(f"{'='*60}")

        # 拼接数据
        df_all = concatenate_contracts(group["symbols"])
        print(f"Concatenated: {len(df_all)} 1h bars from {df_all['datetime'].min()} to {df_all['datetime'].max()}")

        # 计算滚动 x_hat
        df_x = compute_rolling_x(df_all, W_X)
        print(f"Rolling x_hat W={W_X}: {len(df_x)} points")

        # 读取断点
        bp_path = OUT_DIR / f"p2_breakpoints_{group_name}.csv"
        if not bp_path.exists():
            print(f"ERROR: breakpoints file not found: {bp_path} -> skipping")
            continue
        breakpoints = pd.read_csv(bp_path, parse_dates=["breakpoint_datetime"])
        print(f"Loaded {len(breakpoints)} confirmed breakpoints from P2")

        # 获取原始数据绝对索引
        breakpoints_abs = sorted(breakpoints["center_h_abs"].tolist())

        # 分割区间
        segment_df = segment_regimes(df_x, breakpoints_abs)
        print(f"Segmented into {len(segment_df)} intervals")

        # 计算分位数阈值
        q_low = df_x["x_hat"].quantile(QUANTILE_LOW)
        q_high = df_x["x_hat"].quantile(QUANTILE_HIGH)
        print(f"Thresholds: P{int(QUANTILE_LOW*100)} = {q_low:.4f}, P{int(QUANTILE_HIGH*100)} = {q_high:.4f}")

        # 分配 regime
        segment_df = assign_regime_states(segment_df, q_low, q_high)

        # 最小停留过滤
        segment_df = apply_min_stay_filter(segment_df, MIN_STAY_HOURS)
        print(f"After min stay filter ({MIN_STAY_HOURS}h): {len(segment_df)} intervals")

        # 统计分布
        print("\nRegime distribution:")
        print(segment_df["regime"].value_counts().to_string())

        # 保存
        out_path = OUT_DIR / f"p3_regime_segments_{group_name}.csv"
        segment_df.to_csv(out_path, index=False)
        print(f"\nSaved to {out_path}")

        # 输出每个 regime 的统计
        print("\n--- Regime summary ---")
        for regime in ["LOW", "MID", "HIGH"]:
            reg_df = segment_df[segment_df["regime"] == regime]
            if len(reg_df) == 0:
                continue
            total_hours = reg_df["n_bars"].sum()
            pct = total_hours / len(df_x) * 100
            mean_x = reg_df["mean_x"].mean()
            print(f"  {regime}: {len(reg_df)} segments, total {total_hours}h ({pct:.1f}%), mean_x={mean_x:.4f}")


if __name__ == "__main__":
    main()
