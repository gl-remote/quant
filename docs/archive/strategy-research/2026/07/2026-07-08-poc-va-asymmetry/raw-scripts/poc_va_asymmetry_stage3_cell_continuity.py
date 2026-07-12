"""
12 格相邻格子的连续性验证：
1. 同一分位段 · ATR 低→中→高 · mean 是否单调或凸/凹
2. 同一 ATR 制度 · 段1→段4 · mean 是否单调或凸/凹
3. 相邻格子的 mean 差异（跳变检测）
4. 方向一致性（正/负）
"""
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "/Users/gaolei/Documents/src/quant/scripts/ai_tmp")
from poc_va_asymmetry_stage2_grid_search import prepare_dataset  # noqa: E402
from poc_va_asymmetry_stage3_task3_regime_transition import flag_regime_transition  # noqa: E402


LONG_BANDS = [
    ("段1", 0.00, 0.09),
    ("段2", 0.09, 0.19),
    ("段3", 0.19, 0.25),
    ("段4", 0.25, 0.30),
]
SHORT_BANDS = [
    ("段1", 0.91, 1.01),
    ("段2", 0.81, 0.91),
    ("段3", 0.75, 0.81),
    ("段4", 0.70, 0.75),
]
ATR_REGIMES = [
    ("低", 0.00, 0.33),
    ("中", 0.33, 0.67),
    ("高", 0.67, 1.00),
]


def long_mask(df, band_lo, band_hi, atr_lo, atr_hi):
    return (
        (df["signed_skew_rank_roll"] > band_lo) &
        (df["signed_skew_rank_roll"] <= band_hi) &
        (df["atr_rank_roll"] > atr_lo) &
        (df["atr_rank_roll"] <= atr_hi) &
        (df["trend_rank_roll"] >= 0.75) &
        (~df["transition_flag"])
    )


def short_mask(df, band_lo, band_hi, atr_lo, atr_hi):
    return (
        (df["signed_skew_rank_roll"] >= band_lo) &
        (df["signed_skew_rank_roll"] < band_hi) &
        (df["atr_rank_roll"] > atr_lo) &
        (df["atr_rank_roll"] <= atr_hi) &
        (df["trend_rank_roll"] <= 0.20) &
        (~df["transition_flag"])
    )


def get_mean(df, mask, ret_col):
    sub = df[mask].dropna(subset=[ret_col])
    if len(sub) < 3:
        return None
    return sub[ret_col].mean()


def main():
    print("=" * 100)
    print("12 格相邻格子连续性验证")
    print("=" * 100)

    df = prepare_dataset()
    df = flag_regime_transition(df)

    # 构建 mean 矩阵
    print("\n【多头 mean 矩阵】")
    long_mat = np.full((4, 3), np.nan)
    for i, (bn, blo, bhi) in enumerate(LONG_BANDS):
        for j, (an, alo, ahi) in enumerate(ATR_REGIMES):
            m = get_mean(df, long_mask(df, blo, bhi, alo, ahi), "ret_8h_bps")
            if m is not None:
                long_mat[i, j] = m

    print(f"\n{'':10s} {'ATR低':>10s} {'ATR中':>10s} {'ATR高':>10s}")
    for i, (bn, _, _) in enumerate(LONG_BANDS):
        row = f"{bn:10s} "
        for j in range(3):
            v = long_mat[i, j]
            row += f"{v:>+10.1f}" if not np.isnan(v) else f"{'-':>10s}"
        print(row)

    print("\n【空头 mean 矩阵】")
    short_mat = np.full((4, 3), np.nan)
    for i, (bn, blo, bhi) in enumerate(SHORT_BANDS):
        for j, (an, alo, ahi) in enumerate(ATR_REGIMES):
            m = get_mean(df, short_mask(df, blo, bhi, alo, ahi), "short_pnl_4h_bps")
            if m is not None:
                short_mat[i, j] = m

    print(f"\n{'':10s} {'ATR低':>10s} {'ATR中':>10s} {'ATR高':>10s}")
    for i, (bn, _, _) in enumerate(SHORT_BANDS):
        row = f"{bn:10s} "
        for j in range(3):
            v = short_mat[i, j]
            row += f"{v:>+10.1f}" if not np.isnan(v) else f"{'-':>10s}"
        print(row)

    # ========================
    # 连续性检验
    # ========================
    def check_direction(mat, name):
        print(f"\n{'=' * 80}")
        print(f"{name} · 相邻格子方向一致性")
        print(f"{'=' * 80}")
        total = 0
        same_dir = 0
        cross_zero = 0
        for i in range(4):
            for j in range(3):
                if np.isnan(mat[i, j]):
                    continue
                # 右邻居
                if j < 2 and not np.isnan(mat[i, j + 1]):
                    total += 1
                    if np.sign(mat[i, j]) == np.sign(mat[i, j + 1]):
                        same_dir += 1
                    if mat[i, j] * mat[i, j + 1] < 0:
                        cross_zero += 1
                        print(f"  ⚠️ 跨零点：{i+1}段·ATR{j} → {i+1}段·ATR{j+1}"
                              f" · {mat[i,j]:+.1f} → {mat[i,j+1]:+.1f}")
                # 下邻居
                if i < 3 and not np.isnan(mat[i + 1, j]):
                    total += 1
                    if np.sign(mat[i, j]) == np.sign(mat[i + 1, j]):
                        same_dir += 1
                    if mat[i, j] * mat[i + 1, j] < 0:
                        cross_zero += 1
                        print(f"  ⚠️ 跨零点：{i+1}段·ATR{j} → {i+2}段·ATR{j}"
                              f" · {mat[i,j]:+.1f} → {mat[i+1,j]:+.1f}")
        print(f"\n  相邻对总数：{total}")
        print(f"  同方向（含 0）：{same_dir}/{total} = {same_dir/max(1,total):.1%}")
        print(f"  跨零点（一正一负）：{cross_zero}/{total} = {cross_zero/max(1,total):.1%}")

    check_direction(long_mat, "多头")
    check_direction(short_mat, "空头")

    # ========================
    # 相邻格子 mean 跳变分析
    # ========================
    def check_gradient(mat, name):
        print(f"\n{'=' * 80}")
        print(f"{name} · 相邻格子 mean 跳变（|Δmean|）")
        print(f"{'=' * 80}")
        deltas_atr = []  # 同分位段 · ATR 变化
        deltas_band = []  # 同 ATR · 分位段变化
        for i in range(4):
            for j in range(3):
                if np.isnan(mat[i, j]):
                    continue
                if j < 2 and not np.isnan(mat[i, j + 1]):
                    deltas_atr.append(abs(mat[i, j] - mat[i, j + 1]))
                if i < 3 and not np.isnan(mat[i + 1, j]):
                    deltas_band.append(abs(mat[i, j] - mat[i + 1, j]))

        if deltas_atr:
            print(f"  ATR 方向跳变（同 skew · 变 ATR）：")
            print(f"    均值={np.mean(deltas_atr):.1f} · 中位={np.median(deltas_atr):.1f} · max={max(deltas_atr):.1f}")
        if deltas_band:
            print(f"  分位段跳变（同 ATR · 变 skew）：")
            print(f"    均值={np.mean(deltas_band):.1f} · 中位={np.median(deltas_band):.1f} · max={max(deltas_band):.1f}")

    check_gradient(long_mat, "多头")
    check_gradient(short_mat, "空头")


if __name__ == "__main__":
    main()
