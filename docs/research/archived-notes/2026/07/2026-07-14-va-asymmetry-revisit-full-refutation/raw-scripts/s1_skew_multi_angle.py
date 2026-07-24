"""
文件级元信息：
- 创建背景：用户直觉——成交量峰度不可能不含任何信息。前几轮只测了 signed skew
  → 未来 signed return（一阶方向），本脚本系统扫 7 类 skew 派生假设：
  1) skew → 未来波动率（|ret|）
  2) |skew|（对称性缺失强度）→ 未来实现波动 / 回撤 / 尾部
  3) 短窗 skew（4h/8h/24h 而非默认 12h）→ 方向 / 波动
  4) skew persistence（skew_t vs skew_{t-K}）→ 稳定性质量标签
  5) Δskew（skew 变化率）→ 方向 / 波动
  6) cross-sectional rank（跨品种同 event_hour 内相对 skew）→ 相对方向
  7) skew × trend 交互（同向共振 / 反向 divergence）
- 用途：广度扫描"skew 有没有信息"的所有派生形式，找到 IC>0.03 且方向稳定
  的信号后再深挖。
- 注意事项：使用扩样表 outputs/expand/events_with_tier.csv 作为基础
  （已含 A3_skew, atr_intra, trend_intra, ret_2h~12h, cost_rt, ce_key, hour）。
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, "/Users/gaolei/Documents/src/quant/workspace")
sys.path.insert(0, "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/scripts")

from common.contract_specs import CONTRACT_SPECS  # noqa: E402
from h1b_regime_stratified import cluster_bootstrap_mean  # noqa: E402

EXPAND_EVENTS = Path(
    "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/expand/events_with_tier.csv"
)
CSV_DIR = Path("/Users/gaolei/Documents/src/quant/project_data/market_data/csv")

OUT_DIR = Path(
    "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/skew_wide"
)
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 与 h1 相同的品种 tick
from h1_a3_skew_pooled_ic import TICK_SIZE, build_profile, parse_prefix  # noqa: E402

HORIZONS = [2, 4, 6, 8, 12]


def spearman_ic(x: np.ndarray, y: np.ndarray) -> tuple[float, int]:
    mask = ~(np.isnan(x) | np.isnan(y))
    if mask.sum() < 100:
        return float("nan"), int(mask.sum())
    r, _ = stats.spearmanr(x[mask], y[mask])
    return float(r), int(mask.sum())


def cluster_bootstrap_ic(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    cluster_col: str = "ce_key",
    n_boot: int = 1000,
    rng: np.random.Generator | None = None,
) -> tuple[float, float, float, float, int]:
    if rng is None:
        rng = np.random.default_rng(20260714)
    arrays = []
    for _, sub in df.groupby(cluster_col, sort=False):
        x = sub[x_col].to_numpy()
        y = sub[y_col].to_numpy()
        m = ~(np.isnan(x) | np.isnan(y))
        if m.sum() == 0:
            continue
        arrays.append((x[m], y[m]))
    n_c = len(arrays)
    if n_c < 5:
        return float("nan"), float("nan"), float("nan"), float("nan"), 0
    all_x = np.concatenate([a for a, _ in arrays])
    all_y = np.concatenate([b for _, b in arrays])
    if len(all_x) < 100:
        return float("nan"), float("nan"), float("nan"), float("nan"), len(all_x)
    obs, _ = stats.spearmanr(all_x, all_y)
    obs = float(obs)
    picks = rng.integers(0, n_c, size=(n_boot, n_c))
    boot = np.empty(n_boot)
    for i in range(n_boot):
        idxs = picks[i]
        xs = np.concatenate([arrays[j][0] for j in idxs])
        ys = np.concatenate([arrays[j][1] for j in idxs])
        r, _ = stats.spearmanr(xs, ys)
        boot[i] = r if r is not None and not math.isnan(r) else np.nan
    valid = boot[~np.isnan(boot)]
    if len(valid) < 10:
        return obs, float("nan"), float("nan"), float("nan"), len(all_x)
    lo, hi = np.percentile(valid, [2.5, 97.5])
    p_gt = float(np.mean(valid > 0))
    p_lt = float(np.mean(valid < 0))
    return obs, float(lo), float(hi), 2.0 * min(p_gt, p_lt), int(len(all_x))


# ============================================================================
# Compute additional volume-profile skews at different window sizes 4h/8h/24h
# ============================================================================


def compute_multi_window_skews(long_df: pd.DataFrame) -> pd.DataFrame:
    """For each event, compute A3_skew_4h (48 bars), A3_skew_8h (96), A3_skew_24h (288).
    默认 A3_skew 已是 12h (144 bars)。"""
    long_df = long_df.copy()
    for col in ["skew_4h", "skew_8h", "skew_24h"]:
        long_df[col] = np.nan

    windows = {"skew_4h": 48, "skew_8h": 96, "skew_24h": 288}

    processed = 0
    total_syms = long_df["symbol"].nunique()
    for symbol, sub in long_df.groupby("symbol", sort=False):
        path = CSV_DIR / f"{symbol}.tqsdk.5m.csv"
        if not path.exists():
            continue
        spec = CONTRACT_SPECS.get_symbol(symbol)
        if spec is None:
            continue
        tick = spec.tick
        bars = pd.read_csv(path)
        bars["datetime"] = pd.to_datetime(bars["datetime"])
        bars = bars.sort_values("datetime").reset_index(drop=True)
        dt_to_idx = {dt: i for i, dt in enumerate(bars["datetime"])}
        sub = sub.copy()
        sub["event_time"] = pd.to_datetime(sub["event_time"])
        for col, w in windows.items():
            vals = []
            for _, row in sub.iterrows():
                ei = dt_to_idx.get(row["event_time"])
                if ei is None or ei - w < 0:
                    vals.append(np.nan)
                    continue
                bars_window = bars.iloc[ei - w:ei]
                p = build_profile(bars_window, tick)
                vals.append(p.skew if p is not None else np.nan)
            long_df.loc[sub.index, col] = vals
        processed += 1
        print(f"  [{symbol}] ({processed}/{total_syms}) skews computed", flush=True)
    return long_df


# ============================================================================
# Compute future |ret| (realized vol proxy)
# ============================================================================


def add_future_absret(long_df: pd.DataFrame) -> pd.DataFrame:
    for h in HORIZONS:
        long_df[f"abs_ret_{h}h"] = long_df[f"ret_{h}h"].abs()
    return long_df


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    print("[1/8] Loading expand events_with_tier.csv ...", flush=True)
    df = pd.read_csv(EXPAND_EVENTS)
    df["event_time"] = pd.to_datetime(df["event_time"])
    df["event_date"] = pd.to_datetime(df["event_date"]).dt.date
    df["hour"] = df["event_time"].dt.hour
    print(f"  rows={len(df)}, symbols={df['symbol'].nunique()}, "
          f"contracts={df['contract'].nunique()}")

    # 检查缓存
    cache_path = OUT_DIR / "events_with_multi_skew.csv"
    if cache_path.exists():
        print(f"[2/8] Reuse cache: {cache_path}")
        df_ms = pd.read_csv(cache_path)
        df_ms["event_time"] = pd.to_datetime(df_ms["event_time"])
    else:
        print("[2/8] Computing multi-window skews (4h/8h/24h) ...", flush=True)
        df_ms = compute_multi_window_skews(df)
        df_ms.to_csv(cache_path, index=False)
        print(f"  saved: {cache_path}")

    df_ms = add_future_absret(df_ms)

    # 主特征
    df_ms["abs_skew"] = df_ms["A3_skew"].abs()
    df_ms["skew_sq"] = df_ms["A3_skew"] ** 2
    # persistence: skew_t vs skew_{t-1}, group-by contract
    df_ms = df_ms.sort_values(["contract", "event_time"]).reset_index(drop=True)
    df_ms["A3_skew_lag1"] = df_ms.groupby("contract")["A3_skew"].shift(1)
    df_ms["A3_skew_lag4"] = df_ms.groupby("contract")["A3_skew"].shift(4)  # 前 4 小时
    df_ms["skew_delta_1h"] = df_ms["A3_skew"] - df_ms["A3_skew_lag1"]
    df_ms["skew_delta_4h"] = df_ms["A3_skew"] - df_ms["A3_skew_lag4"]
    df_ms["skew_persist_sign_1h"] = (np.sign(df_ms["A3_skew"]) == np.sign(df_ms["A3_skew_lag1"])).astype(float)
    df_ms["skew_persist_sign_4h"] = (np.sign(df_ms["A3_skew"]) == np.sign(df_ms["A3_skew_lag4"])).astype(float)

    # Cross-sectional rank per event_time (rank across symbols)
    df_ms["skew_xs_rank"] = df_ms.groupby("event_time")["A3_skew"].transform(
        lambda s: s.rank(pct=True) if len(s) >= 3 else np.nan
    )

    # trend interaction: skew * sign(trend_intra)
    df_ms["skew_x_trend"] = df_ms["A3_skew"] * np.sign(df_ms["trend_intra"])

    print(f"[3/8] Feature preview:\n{df_ms[['A3_skew','abs_skew','skew_4h','skew_8h','skew_24h','skew_delta_1h','skew_xs_rank']].describe().round(4)}")

    # =========================================================================
    # 假设 A: skew → 未来 |ret|（波动率预测）
    # =========================================================================
    print("\n=== [A] |A3_skew| → 未来 |ret|（realized vol proxy） ===")
    rows = []
    for h in HORIZONS:
        y_col = f"abs_ret_{h}h"
        for x_col in ["A3_skew", "abs_skew", "skew_sq", "skew_4h", "skew_8h", "skew_24h"]:
            obs, lo, hi, p, n = cluster_bootstrap_ic(df_ms, x_col, y_col)
            rows.append({
                "target": y_col, "feature": x_col,
                "n": n, "ic": obs, "ci_lo": lo, "ci_hi": hi, "p_two": p,
            })
    A_df = pd.DataFrame(rows)
    A_df.to_csv(OUT_DIR / "A_vol_prediction.csv", index=False)
    print(A_df.to_string(index=False))

    # =========================================================================
    # 假设 B: 短窗 skew → signed future ret（不同窗口 lookback 效应）
    # =========================================================================
    print("\n\n=== [B] short-window skew (4h/8h/24h) → signed future ret ===")
    rows = []
    for h in HORIZONS:
        y_col = f"ret_{h}h"
        for x_col in ["A3_skew", "skew_4h", "skew_8h", "skew_24h"]:
            obs, lo, hi, p, n = cluster_bootstrap_ic(df_ms, x_col, y_col)
            rows.append({
                "target": y_col, "feature": x_col,
                "n": n, "ic": obs, "ci_lo": lo, "ci_hi": hi, "p_two": p,
            })
    B_df = pd.DataFrame(rows)
    B_df.to_csv(OUT_DIR / "B_short_window_ic.csv", index=False)
    print(B_df.to_string(index=False))

    # =========================================================================
    # 假设 C: Δskew（skew 变化率）→ signed future ret
    # =========================================================================
    print("\n\n=== [C] Δskew → signed future ret ===")
    rows = []
    for h in HORIZONS:
        y_col = f"ret_{h}h"
        for x_col in ["skew_delta_1h", "skew_delta_4h"]:
            obs, lo, hi, p, n = cluster_bootstrap_ic(df_ms, x_col, y_col)
            rows.append({
                "target": y_col, "feature": x_col,
                "n": n, "ic": obs, "ci_lo": lo, "ci_hi": hi, "p_two": p,
            })
    C_df = pd.DataFrame(rows)
    C_df.to_csv(OUT_DIR / "C_delta_skew.csv", index=False)
    print(C_df.to_string(index=False))

    # =========================================================================
    # 假设 D: Cross-sectional skew rank → future ret（相对方向）
    # =========================================================================
    print("\n\n=== [D] Cross-sectional skew rank (per event_time) → signed future ret ===")
    rows = []
    for h in HORIZONS:
        y_col = f"ret_{h}h"
        obs, lo, hi, p, n = cluster_bootstrap_ic(df_ms, "skew_xs_rank", y_col)
        rows.append({
            "target": y_col, "feature": "skew_xs_rank",
            "n": n, "ic": obs, "ci_lo": lo, "ci_hi": hi, "p_two": p,
        })
    D_df = pd.DataFrame(rows)
    D_df.to_csv(OUT_DIR / "D_xs_rank.csv", index=False)
    print(D_df.to_string(index=False))

    # =========================================================================
    # 假设 E: skew × trend 共振 / 背离
    # =========================================================================
    print("\n\n=== [E] skew × sign(trend) 交互 → signed future ret ===")
    rows = []
    for h in HORIZONS:
        y_col = f"ret_{h}h"
        obs, lo, hi, p, n = cluster_bootstrap_ic(df_ms, "skew_x_trend", y_col)
        rows.append({
            "target": y_col, "feature": "skew_x_trend",
            "n": n, "ic": obs, "ci_lo": lo, "ci_hi": hi, "p_two": p,
        })
    E_df = pd.DataFrame(rows)
    E_df.to_csv(OUT_DIR / "E_skew_x_trend.csv", index=False)
    print(E_df.to_string(index=False))

    # =========================================================================
    # 假设 F: persistence-filtered signed skew（skew 需连续同号才下注）
    # =========================================================================
    print("\n\n=== [F] Persistence-filtered skew → future ret ===")
    rows = []
    for filter_name in ["persist_1h", "persist_4h"]:
        col = f"skew_persist_sign_{'1h' if filter_name=='persist_1h' else '4h'}"
        for h in HORIZONS:
            y_col = f"ret_{h}h"
            # 仅在 persist=1 的样本中做 IC (skew → future ret)
            sub = df_ms[df_ms[col] == 1.0]
            if len(sub) < 200:
                continue
            obs, lo, hi, p, n = cluster_bootstrap_ic(sub, "A3_skew", y_col)
            rows.append({
                "filter": filter_name, "target": y_col, "feature": "A3_skew(persist)",
                "n": n, "ic": obs, "ci_lo": lo, "ci_hi": hi, "p_two": p,
            })
    F_df = pd.DataFrame(rows)
    F_df.to_csv(OUT_DIR / "F_persistence.csv", index=False)
    print(F_df.to_string(index=False))

    # =========================================================================
    # 假设 G: |skew| → future max drawdown (proxy: max_negret_within_h)
    # 需要 5m 数据算 max drawdown 于 event 后 h 小时，简化用 min(ret_1h..ret_hH)
    # 这里用现成 ret_2h/4h/6h/8h/12h，用其在符号池内的 min value 作为 proxy
    # =========================================================================
    print("\n\n=== [G] |skew| → future min ret (drawdown proxy, using min of ret_2h/4h/...) ===")
    df_ms["future_min_ret"] = df_ms[[f"ret_{h}h" for h in [2,4,6,8,12]]].min(axis=1)
    rows = []
    for x_col in ["abs_skew", "skew_sq"]:
        obs, lo, hi, p, n = cluster_bootstrap_ic(df_ms, x_col, "future_min_ret")
        rows.append({
            "target": "future_min_ret", "feature": x_col,
            "n": n, "ic": obs, "ci_lo": lo, "ci_hi": hi, "p_two": p,
        })
    G_df = pd.DataFrame(rows)
    G_df.to_csv(OUT_DIR / "G_drawdown_proxy.csv", index=False)
    print(G_df.to_string(index=False))

    # =========================================================================
    # 综合 ranking
    # =========================================================================
    print("\n\n=== [SUMMARY] All results ranked by |IC| ===")
    all_dfs = []
    for cat, dfx in [("A_vol", A_df), ("B_short_window", B_df), ("C_delta", C_df),
                    ("D_xs_rank", D_df), ("E_skew_x_trend", E_df), ("F_persist", F_df),
                    ("G_drawdown", G_df)]:
        dfx = dfx.copy()
        dfx["category"] = cat
        all_dfs.append(dfx)
    merged = pd.concat(all_dfs, ignore_index=True)
    merged["abs_ic"] = merged["ic"].abs()
    merged["pass_ci"] = (merged["ci_lo"] > 0) | (merged["ci_hi"] < 0)
    top = merged.sort_values("abs_ic", ascending=False).head(20)
    print(top[["category", "target", "feature", "n", "ic", "ci_lo", "ci_hi", "p_two", "pass_ci"]].to_string(index=False))
    merged.to_csv(OUT_DIR / "all_ranked.csv", index=False)

    print(f"\nAll outputs: {OUT_DIR}")


if __name__ == "__main__":
    main()
