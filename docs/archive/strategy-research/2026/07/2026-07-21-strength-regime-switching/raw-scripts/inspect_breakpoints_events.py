"""检查断点前后发生了什么：打印价格和强度变化"""

from pathlib import Path
import pandas as pd
import numpy as np

REPO = Path("/Users/gaolei/Documents/src/quant")
CSV_DIR = REPO / "project_data" / "market_data" / "csv"
OUT_DIR = REPO / "project_data" / "research" / "strength_regime_switching"

# 断点信息
BREAKPOINTS = [
    {"group": "corn", "datetime": "2025-11-24 21:00:00", "symbols": ["DCE.c2601", "DCE.c2603", "DCE.c2605", "DCE.c2609"]},
    {"group": "corn_starch", "datetime": "2025-11-24 21:00:00", "symbols": ["DCE.cs2601", "DCE.cs2603", "DCE.cs2605"]},
    {"group": "corn_starch", "datetime": "2025-11-27 22:00:00", "symbols": ["DCE.cs2601", "DCE.cs2603", "DCE.cs2605"]},
    {"group": "soybean_meal", "datetime": "2026-01-07 22:00:00", "symbols": ["DCE.m2601", "DCE.m2603", "DCE.m2605"]},
    {"group": "soybean_meal", "datetime": "2026-02-04 09:00:00", "symbols": ["DCE.m2601", "DCE.m2603", "DCE.m2605"]},
    # 新增 c2609 - 完整数据从头开始跑 CUSUM
]

WINDOW_BEFORE = 20  # 断点前多少小时
WINDOW_AFTER = 20   # 断点后多少小时


def load_and_extract(sym: str, bp_datetime: str) -> pd.DataFrame | None:
    """加载合约，提取断点前后窗口"""
    fpath = CSV_DIR / f"{sym}.tqsdk.1h.csv"
    if not fpath.exists():
        print(f"File not found: {fpath}")
        return None
    df = pd.read_csv(fpath, parse_dates=["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)

    # 找到断点时间对应的索引
    bp_dt = pd.to_datetime(bp_datetime)
    idx = df[df["datetime"] == bp_dt].index
    if len(idx) == 0:
        # 找最接近的
        df["diff"] = abs(df["datetime"] - bp_dt)
        idx = [df["diff"].idxmin()]
        print(f"  {sym}: closest to {df.loc[idx[0], 'datetime']}")

    center_idx = idx[0]
    start_idx = max(0, center_idx - WINDOW_BEFORE)
    end_idx = min(len(df), center_idx + WINDOW_AFTER + 1)

    result = df.iloc[start_idx:end_idx].copy()
    result["symbol"] = sym
    result["rel_h"] = result.index - center_idx
    return result


def compute_x_hat(window: pd.DataFrame) -> float:
    """计算该窗口的 x_hat"""
    log_rets = np.log(window["close"]).diff().dropna().to_numpy()
    if len(log_rets) < 10:
        return np.nan
    mu = np.mean(log_rets)
    sd = np.std(log_rets, ddof=1)
    if sd <= 1e-6:
        return np.nan
    return abs(mu) / sd


def analyze_breakpoint(bp: dict) -> None:
    print(f"\n{'='*70}")
    print(f"断点: {bp['group']} @ {bp['datetime']}")
    print(f"{'='*70}")

    all_results = []
    for sym in bp["symbols"]:
        df_window = load_and_extract(sym, bp["datetime"])
        if df_window is None:
            continue
        all_results.append(df_window)

        # 打印价格变化
        print(f"\n--- {sym} ---")
        first_close = df_window.iloc[0]["close"]
        bp_close = df_window[df_window["rel_h"] == 0].iloc[0]["close"]
        last_close = df_window.iloc[-1]["close"]
        print(f"  窗口起始({df_window.iloc[0]['rel_h']}h): {first_close:.2f}")
        print(f"  断点位置(  0h): {bp_close:.2f}")
        print(f"  窗口结束({df_window.iloc[-1]['rel_h']}h): {last_close:.2f}")
        print(f"  断点后变化(0→+{WINDOW_AFTER}h): {(last_close - bp_close)/bp_close*100:+.2f}%")

        # 计算滚动 x_hat 变化 (W=80)
        # 用前 80h 和后 80h 对比
        # 需要扩展范围，这里简单看方向
        if len(df_window) >= 10:
            x_before = compute_x_hat(df_window[df_window["rel_h"] < 0])
            x_after = compute_x_hat(df_window[df_window["rel_h"] >= 0])
            print(f"  窗口内平均 x_hat 变化: 前={x_before:.4f} → 后={x_after:.4f}  (Δ={x_after - x_before:+.4f})")

    print()


def main():
    for bp in BREAKPOINTS:
        analyze_breakpoint(bp)


if __name__ == "__main__":
    main()
