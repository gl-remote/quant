"""玉米 1h 三档漂移强度探针

对 c2601 / c2603 / c2605 三份 1h 数据，分别测量：

1. ν_dir/σ  —— DirRandom 混合方向（主题标准，多空对消后的"净"漂移）
2. |ν|/σ    —— 事后取绝对值的"绝对漂移强度"（客观机会密度上限）
3. ν_aligned/σ —— 1h EMA20 aligned 分组后的方向筛选漂移

用滑动窗口而非 barrier 触达（避免条件化伪影），窗口长度 = 80h（对应 MAX_BARS）
以及 20h（对应 E[τ]）。
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd


REPO = Path("/Users/gaolei/Documents/src/quant")
CSV_DIR = REPO / "project_data" / "market_data" / "csv"
SYMBOLS = ["DCE.c2601", "DCE.c2603", "DCE.c2605"]

WINDOWS_HOURS = [20, 80]   # 对应 E[τ] 和 MAX_BARS
EMA_SPAN = 20
STRIDE = 4


def load_1h(sym: str) -> pd.DataFrame:
    df = pd.read_csv(CSV_DIR / f"{sym}.tqsdk.1h.csv", parse_dates=["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    df["log_ret"] = np.log(df["close"]).diff()
    df["ema20"] = df["close"].ewm(span=EMA_SPAN, adjust=False).mean()
    df["trend_up"] = (df["close"] > df["ema20"]).astype(int)  # 1=上行, 0=下行
    return df.dropna(subset=["log_ret"]).reset_index(drop=True)


def scan_window(df: pd.DataFrame, W: int) -> pd.DataFrame:
    """按滑动窗口测量每段的 ν_bar / σ_bar 与 aligned/opposed 分方向指标。"""
    rows = []
    for i in range(0, len(df) - W, STRIDE):
        seg = df["log_ret"].iloc[i : i + W].to_numpy()
        if len(seg) < 5:
            continue
        mu_bar = float(np.mean(seg))
        sd_bar = float(np.std(seg, ddof=1))
        if sd_bar <= 0:
            continue
        # 1h 一 bar，σ_bar 就是 1h/√h 归一化
        nu_dir = mu_bar / sd_bar             # 主题口径（有正负）
        nu_abs = abs(mu_bar) / sd_bar        # 绝对强度
        # aligned：段起点的 EMA20 方向作为方向信号
        entry_up = int(df["trend_up"].iat[i])
        direction = +1 if entry_up == 1 else -1
        nu_aligned = direction * mu_bar / sd_bar
        rows.append(
            {
                "start": df["datetime"].iat[i],
                "nu_dir": nu_dir,
                "nu_abs": nu_abs,
                "nu_aligned": nu_aligned,
                "direction": direction,
            }
        )
    return pd.DataFrame(rows)


def report(df: pd.DataFrame, W: int, label: str) -> None:
    if df.empty:
        return
    n = len(df)
    print(f"\n===== {label}  W={W}h  n={n} =====")
    for col, name in [
        ("nu_dir", "ν_dir/σ  (DirRandom 净)"),
        ("nu_abs", "|ν|/σ   (绝对强度)"),
        ("nu_aligned", "ν_aligned/σ (EMA20 方向筛选)"),
    ]:
        s = df[col]
        p10, p25, p50, p75, p90 = s.quantile([0.10, 0.25, 0.50, 0.75, 0.90])
        mean = s.mean()
        # 分档比例（用 sign-aware 阈值 0.10）
        strong_pos = (s >= 0.10).mean() * 100
        strong_neg = (s <= -0.10).mean() * 100
        flat = (s.abs() < 0.03).mean() * 100
        # 对绝对强度，只关心 ≥ 阈值
        strong_abs = (s.abs() >= 0.10).mean() * 100
        print(f"  {name}")
        print(f"    mean={mean:+.3f}  p10={p10:+.3f}  p50={p50:+.3f}  p90={p90:+.3f}")
        print(f"    强正≥+0.10: {strong_pos:5.1f}%   平坦|.|<0.03: {flat:5.1f}%   "
              f"强负≤−0.10: {strong_neg:5.1f}%   |强|≥0.10: {strong_abs:5.1f}%")


def main() -> None:
    all_frames = {W: [] for W in WINDOWS_HOURS}
    for sym in SYMBOLS:
        df = load_1h(sym)
        print(f"[{sym}] bars={len(df)}  "
              f"[{df['datetime'].iat[0]} .. {df['datetime'].iat[-1]}]")
        for W in WINDOWS_HOURS:
            out = scan_window(df, W)
            report(out, W, sym)
            all_frames[W].append(out)

    for W, frames in all_frames.items():
        merged = pd.concat(frames, ignore_index=True)
        report(merged, W, "全玉米合并")
        out_dir = REPO / "project_data" / "research" / "first_passage_boundary"
        out_dir.mkdir(parents=True, exist_ok=True)
        merged.to_csv(out_dir / f"corn_1h_strength_W{W}.csv", index=False)


if __name__ == "__main__":
    main()
