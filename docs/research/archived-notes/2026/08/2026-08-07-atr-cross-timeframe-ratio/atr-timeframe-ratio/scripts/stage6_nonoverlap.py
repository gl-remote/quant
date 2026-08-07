"""
ATR 跨周期比值研究 · Stage 6: 扩大样本 + 非重叠抽样验证
======================================================

针对 Stage 5 暴露的问题：
- 1,197 个 H_only 实际只对应 32 个独立事件（每段取第一根）；
- 重叠样本可能高估显著性。

本阶段做三件事：
1. 利用 5m CSV 聚合成 15m，把样本范围扩展到所有同时有 1h 和 5m 的合约；
2. 实现三种非重叠抽样方案：
   - A: 每段连续 H_only 只取第一根（episode-first）；
   - B: 每个合约-交易日最多取一个 H_only（daily-dedup）；
   - C: 每段连续 confirmed 状态只取第一根；
3. 在三种非重叠样本上重跑 Stage 3/4/5 核心指标，并与原始重叠样本对比。

输出：outputs/stage6/
- stage6_expanded_panel.parquet
- stage6_sample_sizes.csv
- stage6_h_only_summary.csv
- stage6_confirmed_returns.csv
- stage6_strong_filter.csv
- stage6_vol_ratio.csv
- stage6_summary.json
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=RuntimeWarning)

# ---------- 路径 ----------
ROOT = Path(__file__).resolve().parents[5]
CSV_DIR = ROOT / "project_data" / "market_data" / "csv"
SCRIPT_DIR = Path(__file__).resolve().parents[1]
OUT_DIR = SCRIPT_DIR / "outputs" / "stage6"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------- 参数 ----------
H_SHORT, H_LONG = 14, 50
L_SHORT, L_LONG = 56, 200
ROLL_H, ROLL_L = 100, 400
BOOT_N = 1000
BOOT_SEED = 42
MIN_N = 10  # 非重叠样本小，阈值降低
FWD_RET = 20

# ---------- 板块映射（与 Stage 3 一致） ----------
SECTOR_MAP: dict[str, str] = {
    "sc": "能化", "TA": "能化", "MA": "能化", "FG": "能化",
    "RU": "能化", "FU": "能化", "bu": "能化", "eg": "能化", "pp": "能化",
    "cu": "有色", "al": "有色", "zn": "有色", "pb": "有色", "ni": "有色",
    "au": "贵金属", "ag": "贵金属",
    "rb": "黑色", "hc": "黑色", "i": "黑色", "j": "黑色", "jm": "黑色",
    "m": "农产品", "y": "农产品", "p": "农产品", "c": "农产品", "cs": "农产品",
    "a": "农产品", "b": "农产品",
    "CF": "农产品", "SR": "农产品", "RM": "农产品", "OI": "农产品",
}


def parse_symbol(sym: str) -> tuple[str, str, str]:
    exchange, code = sym.split(".", 1)
    product = ""
    for ch in code:
        if ch.isalpha():
            product += ch
        else:
            break
    return exchange, product, SECTOR_MAP.get(product, "其他")


# =====================================================================
# 1. 数据加载：15m 直接读，5m 聚合成 15m
# =====================================================================

def wilder_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def resample_5m_to_15m(df5: pd.DataFrame) -> pd.DataFrame:
    """把 5m bar 聚合成 15m bar（15m 收盘价对齐到 15m 时间戳）。"""
    # 5m bar 时间戳是 bar 开始时间；3 根 5m 合成 1 根 15m
    # 用 label='right' 让聚合标签落在 15m 结束时刻
    df5 = df5.sort_index()
    agg = df5.resample("15min", label="right", closed="right").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
        "amount": "sum",
        "open_oi": "first",
        "close_oi": "last",
    })
    # 只保留实际有交易的 bar（剔除全天停牌的空 15min）
    agg = agg.dropna(subset=["close"])
    return agg


def load_15m(sym: str) -> pd.DataFrame | None:
    """加载 15m 数据。优先直接读 15m CSV，否则从 5m 聚合。"""
    f15 = CSV_DIR / f"{sym}.tqsdk.15m.csv"
    f5 = CSV_DIR / f"{sym}.tqsdk.5m.csv"
    if f15.exists():
        df = pd.read_csv(f15, parse_dates=["datetime"]).set_index("datetime")
        return df[["open", "high", "low", "close", "volume", "open_oi", "close_oi"]]
    if f5.exists():
        df5 = pd.read_csv(f5, parse_dates=["datetime"]).set_index("datetime")
        return resample_5m_to_15m(df5)
    return None


def load_1h(sym: str) -> pd.DataFrame | None:
    f1h = CSV_DIR / f"{sym}.tqsdk.1h.csv"
    if not f1h.exists():
        return None
    return pd.read_csv(f1h, parse_dates=["datetime"]).set_index("datetime")


# =====================================================================
# 2. 因子计算（与 Stage 3 一致）
# =====================================================================

def compute_panel(df15: pd.DataFrame, df1h: pd.DataFrame, sym: str) -> pd.DataFrame:
    exchange, product, sector = parse_symbol(sym)
    df = pd.DataFrame(index=df1h.index)
    df["close"] = df1h["close"]

    H = wilder_atr(df1h["high"], df1h["low"], df1h["close"], H_SHORT)
    H_long = wilder_atr(df1h["high"], df1h["low"], df1h["close"], H_LONG)
    L_series = wilder_atr(df15["high"], df15["low"], df15["close"], L_SHORT)
    L_long_series = wilder_atr(df15["high"], df15["low"], df15["close"], L_LONG)

    l_df = pd.DataFrame({"L": L_series, "L_long": L_long_series, "time": df15.index})
    h_df = pd.DataFrame({"time": df1h.index})
    merged = pd.merge_asof(h_df, l_df, on="time", direction="backward")

    df["H"] = H.values
    df["L"] = merged["L"].values
    df["H_long"] = H_long.values
    df["L_long"] = merged["L_long"].values
    df["S_H"] = df["H"] / df["H_long"]
    df["S_L"] = df["L"] / df["L_long"]

    # state_S
    df["state_S"] = "other"
    df.loc[(df["S_H"] > 1) & (df["S_L"] > 1), "state_S"] = "co_expand"
    df.loc[(df["S_H"] > 1) & (df["S_L"] <= 1), "state_S"] = "H_only"
    df.loc[(df["S_H"] <= 1) & (df["S_L"] > 1), "state_S"] = "L_only"
    df.loc[(df["S_H"] <= 1) & (df["S_L"] <= 1), "state_S"] = "co_compress"

    # 前向响应
    df["fwd_ret_20"] = df["close"].shift(-FWD_RET) / df["close"] - 1
    df["fwd_abs_ret_20"] = df["fwd_ret_20"].abs()
    # 5 根后 S_L 是否抬升（confirmed 定义）
    df["fwd_S_L_5"] = df["S_L"].shift(-5)
    df["fwd_S_L_up_5"] = (df["fwd_S_L_5"] > 1).astype("float")

    # trend_strength: MADEV_60 绝对值的滚动分位
    ma60 = df["close"].rolling(60, min_periods=40).mean()
    std60 = df["close"].pct_change().rolling(60, min_periods=40).std()
    madev60 = (df["close"] - ma60) / (std60 * df["close"])
    df["MADEV_60"] = madev60
    df["trend_strength"] = madev60.abs().rolling(60, min_periods=40).rank(pct=True)

    # vol_ratio（用于验证 Stage 5 成交量因子）
    if "volume" in df1h.columns:
        v = df1h["volume"].astype(float)
        df["vol_ratio"] = v / v.rolling(20, min_periods=10).mean()

    # 标识
    df["symbol"] = sym
    df["exchange"] = exchange
    df["product"] = product
    df["sector"] = sector
    df["datetime"] = df.index
    df["date"] = df.index.normalize()
    df["year"] = df.index.year

    # H_only outcome
    df["H_only_outcome"] = "not_H_only"
    h_mask = df["state_S"] == "H_only"
    df.loc[h_mask & (df["fwd_S_L_up_5"] == 1), "H_only_outcome"] = "confirmed"
    df.loc[h_mask & (df["fwd_S_L_up_5"] == 0), "H_only_outcome"] = "failed"

    # 连续段 ID
    df["episode_id"] = (
        (df["state_S"] != df["state_S"].shift())
        | (df["symbol"] != df["symbol"].shift())
    ).cumsum()

    return df.dropna(subset=["S_H", "S_L", "fwd_ret_20"])


def build_expanded_panel() -> pd.DataFrame:
    """加载所有同时有 1h 和 15m（或可从 5m 聚合）的合约。"""
    syms_1h = {p.name.split(".tqsdk")[0] for p in CSV_DIR.glob("*.tqsdk.1h.csv")}
    frames = []
    coverage = []
    for sym in sorted(syms_1h):
        df15 = load_15m(sym)
        df1h = load_1h(sym)
        if df15 is None or df1h is None or len(df15) < 200 or len(df1h) < 100:
            coverage.append({"symbol": sym, "status": "skipped", "source": "none"})
            continue
        source = "15m_csv" if (CSV_DIR / f"{sym}.tqsdk.15m.csv").exists() else "5m_resampled"
        panel = compute_panel(df15, df1h, sym)
        frames.append(panel)
        coverage.append({
            "symbol": sym,
            "status": "ok",
            "source": source,
            "n_1h": len(df1h),
            "n_15m": len(df15),
            "n_panel": len(panel),
            "n_H_only": int((panel["state_S"] == "H_only").sum()),
        })
    result = pd.concat(frames, ignore_index=True)
    cov_df = pd.DataFrame(coverage)
    cov_df.to_csv(OUT_DIR / "stage6_data_coverage.csv", index=False)
    return result


# =====================================================================
# 3. 非重叠抽样
# =====================================================================

def episode_first(panel: pd.DataFrame, state: str = "H_only") -> pd.DataFrame:
    """方案 A：每段连续 state 只取第一根。"""
    sub = panel[panel["state_S"] == state].copy()
    return sub.groupby("episode_id", as_index=False).first()


def daily_dedup(panel: pd.DataFrame, state: str = "H_only") -> pd.DataFrame:
    """方案 B：每个 symbol-date 最多取一个 H_only（取当日最早）。"""
    sub = panel[panel["state_S"] == state].copy()
    return sub.sort_values("datetime").groupby(["symbol", "date"], as_index=False).first()


def confirmed_episode_first(panel: pd.DataFrame) -> pd.DataFrame:
    """方案 C：每段连续 confirmed 只取第一根。

    定义：从 H_only 开始，5 根内 S_L 抬升即为 confirmed。
    实现：按 episode_id 分组，对 H_only 段标记是否 confirmed，
    然后每段 confirmed 只取第一根。
    """
    sub = panel[panel["H_only_outcome"] == "confirmed"].copy()
    # 一个 episode 可能有多根 confirmed，取第一根
    return sub.groupby("episode_id", as_index=False).first()


# =====================================================================
# 4. 统计工具
# =====================================================================

def cluster_bootstrap_ci(values: np.ndarray, clusters: np.ndarray) -> tuple[float, float]:
    rng = np.random.default_rng(BOOT_SEED)
    mask = ~np.isnan(values)
    values, clusters = values[mask], clusters[mask]
    if len(values) == 0:
        return np.nan, np.nan
    uniq = np.unique(clusters)
    idx_map = {c: np.where(clusters == c)[0] for c in uniq}
    stats = np.empty(BOOT_N)
    for i in range(BOOT_N):
        sampled = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([idx_map[c] for c in sampled])
        stats[i] = values[idx].mean()
    lo, hi = np.nanpercentile(stats, [2.5, 97.5])
    return float(lo), float(hi)


def summarize_confirmed(df: pd.DataFrame, label: str) -> dict:
    """汇总 H_only confirmed 相关指标。"""
    n_h = (df["state_S"] == "H_only").sum()
    n_conf = (df["H_only_outcome"] == "confirmed").sum()
    n_fail = (df["H_only_outcome"] == "failed").sum()
    conf_rate = n_conf / max(n_h, 1)

    conf = df[df["H_only_outcome"] == "confirmed"]
    all_h = df[df["state_S"] == "H_only"]

    result = {
        "sample": label,
        "n_rows": len(df),
        "n_H_only": int(n_h),
        "n_confirmed": int(n_conf),
        "n_failed": int(n_fail),
        "confirm_rate": float(conf_rate),
        "n_episodes": int(df.loc[df["state_S"] == "H_only", "episode_id"].nunique()),
        "n_dates": int(all_h["date"].nunique()) if len(all_h) else 0,
        "n_symbols": int(all_h["symbol"].nunique()) if len(all_h) else 0,
    }

    for name, sub in [("all_H_only", all_h), ("confirmed", conf)]:
        if len(sub) >= MIN_N:
            vals = sub["fwd_ret_20"].values
            ci_lo, ci_hi = cluster_bootstrap_ci(vals, sub["date"].values)
            result[f"{name}_ret20_mean"] = float(np.nanmean(vals))
            result[f"{name}_ret20_median"] = float(np.nanmedian(vals))
            result[f"{name}_abs_ret20"] = float(np.nanmean(np.abs(vals)))
            result[f"{name}_ci_lo"] = ci_lo
            result[f"{name}_ci_hi"] = ci_hi
            # 胜率
            result[f"{name}_win_rate"] = float((vals > 0).mean())
        else:
            result[f"{name}_ret20_mean"] = float(sub["fwd_ret_20"].mean()) if len(sub) else np.nan
            result[f"{name}_ret20_median"] = float(sub["fwd_ret_20"].median()) if len(sub) else np.nan
            result[f"{name}_abs_ret20"] = float(sub["fwd_abs_ret_20"].mean()) if len(sub) else np.nan
            result[f"{name}_ci_lo"] = np.nan
            result[f"{name}_ci_hi"] = np.nan
            result[f"{name}_win_rate"] = float((sub["fwd_ret_20"] > 0).mean()) if len(sub) else np.nan

    return result


def strong_filter_summary(df: pd.DataFrame, label: str) -> dict:
    """Stage 4 最优组合：H_only + trend_strength=strong。"""
    if "trend_strength" not in df.columns:
        return {}
    h = df[df["state_S"] == "H_only"].copy()
    # 三分位 strong
    if len(h) < 30:
        return {"sample": label, "n_strong_H_only": 0}
    h["ts_q"] = pd.qcut(h["trend_strength"].rank(method="first"), 3, labels=["weak", "mid", "strong"])
    strong = h[h["ts_q"] == "strong"]
    strong_conf = strong[strong["H_only_outcome"] == "confirmed"]
    r = {
        "sample": label,
        "n_strong_H_only": int(len(strong)),
        "n_strong_confirmed": int(len(strong_conf)),
        "strong_confirm_rate": float(len(strong_conf) / max(len(strong), 1)),
    }
    for name, sub in [("strong_H_only", strong), ("strong_confirmed", strong_conf)]:
        if len(sub) >= MIN_N:
            r[f"{name}_ret20"] = float(sub["fwd_ret_20"].mean())
            ci_lo, ci_hi = cluster_bootstrap_ci(sub["fwd_ret_20"].values, sub["date"].values)
            r[f"{name}_ci_lo"] = ci_lo
            r[f"{name}_ci_hi"] = ci_hi
        elif len(sub) > 0:
            r[f"{name}_ret20"] = float(sub["fwd_ret_20"].mean())
            r[f"{name}_ci_lo"] = np.nan
            r[f"{name}_ci_hi"] = np.nan
        else:
            r[f"{name}_ret20"] = np.nan
            r[f"{name}_ci_lo"] = np.nan
            r[f"{name}_ci_hi"] = np.nan
    return r


def vol_ratio_summary(df: pd.DataFrame, label: str) -> dict:
    """Stage 5 最强单因子 vol_chg/vol_ratio 的效果。"""
    if "vol_ratio" not in df.columns:
        return {}
    h = df[df["state_S"] == "H_only"].dropna(subset=["vol_ratio"]).copy()
    if len(h) < 30:
        return {"sample": label, "n": len(h)}
    h["vol_q"] = pd.qcut(h["vol_ratio"].rank(method="first"), 3, labels=["low", "mid", "high"])
    high = h[h["vol_q"] == "high"]
    low = h[h["vol_q"] == "low"]
    return {
        "sample": label,
        "n": len(h),
        "high_vol_confirm_rate": float((high["H_only_outcome"] == "confirmed").mean()),
        "low_vol_confirm_rate": float((low["H_only_outcome"] == "confirmed").mean()),
        "high_vol_ret20": float(high["fwd_ret_20"].mean()),
        "low_vol_ret20": float(low["fwd_ret_20"].mean()),
    }


# =====================================================================
# 5. 主函数
# =====================================================================

def main() -> None:
    panel = build_expanded_panel()
    panel.to_parquet(OUT_DIR / "stage6_expanded_panel.parquet", index=False)
    print(f"扩大面板构建完成: {panel['symbol'].nunique()} 合约, {len(panel)} 行")
    print(f"  H_only: {(panel['state_S']=='H_only').sum()}")
    print(f"  confirmed: {(panel['H_only_outcome']=='confirmed').sum()}")

    # 数据来源统计
    cov = pd.read_csv(OUT_DIR / "stage6_data_coverage.csv")
    print("\n数据来源：")
    print(cov[cov["status"] == "ok"]["source"].value_counts())

    # 构造多个样本
    samples = {
        "full_overlap": panel,
        "episode_first": episode_first(panel),
        "daily_dedup": daily_dedup(panel),
        "confirmed_episode_first": confirmed_episode_first(panel),
    }

    # 样本量
    size_rows = []
    for label, df in samples.items():
        n_h = (df["state_S"] == "H_only").sum() if "state_S" in df.columns else len(df)
        size_rows.append({
            "sample": label,
            "n_rows": len(df),
            "n_H_only": int(n_h),
            "n_confirmed": int((df["H_only_outcome"] == "confirmed").sum()) if "H_only_outcome" in df.columns else 0,
            "n_episodes": int(df["episode_id"].nunique()) if "episode_id" in df.columns else 0,
            "n_dates": int(df["date"].nunique()) if "date" in df.columns else 0,
            "n_symbols": int(df["symbol"].nunique()),
        })
    size_df = pd.DataFrame(size_rows)
    size_df.to_csv(OUT_DIR / "stage6_sample_sizes.csv", index=False)
    print("\n=== 样本量对比 ===")
    print(size_df.to_string(index=False))

    # H_only 核心指标
    h_only_rows = []
    for label, df in samples.items():
        # 对 episode_first/daily_dedup 这些已经是 H_only 子集的，用全 df；
        # 对 full_overlap，需要在函数内筛 H_only
        h_only_rows.append(summarize_confirmed(df, label))
    h_only_df = pd.DataFrame(h_only_rows)
    h_only_df.to_csv(OUT_DIR / "stage6_h_only_summary.csv", index=False)
    print("\n=== H_only / confirmed 核心指标 ===")
    cols = ["sample", "n_H_only", "n_confirmed", "confirm_rate", "n_episodes",
            "confirmed_ret20_mean", "confirmed_ci_lo", "confirmed_ci_hi", "confirmed_win_rate"]
    print(h_only_df[cols].round(4).to_string(index=False))

    # Stage 4 strong 过滤
    strong_rows = []
    for label, df in samples.items():
        r = strong_filter_summary(df, label)
        if r:
            strong_rows.append(r)
    strong_df = pd.DataFrame(strong_rows)
    strong_df.to_csv(OUT_DIR / "stage6_strong_filter.csv", index=False)
    print("\n=== trend_strength=strong 过滤 ===")
    print(strong_df.round(4).to_string(index=False))

    # Stage 5 vol_ratio
    vol_rows = []
    for label, df in samples.items():
        r = vol_ratio_summary(df, label)
        if r:
            vol_rows.append(r)
    vol_df = pd.DataFrame(vol_rows)
    vol_df.to_csv(OUT_DIR / "stage6_vol_ratio.csv", index=False)
    print("\n=== vol_ratio 高/低组 ===")
    print(vol_df.round(4).to_string(index=False))

    # 按板块/年份（episode first 非重叠）
    ep_first = samples["episode_first"]
    by_sector = []
    for sec, s in ep_first.groupby("sector"):
        if len(s) < 5:
            continue
        conf = s[s["H_only_outcome"] == "confirmed"]
        by_sector.append({
            "sector": sec,
            "n_H_only": len(s),
            "n_confirmed": len(conf),
            "confirm_rate": len(conf) / len(s),
            "confirmed_ret20": conf["fwd_ret_20"].mean() if len(conf) else np.nan,
        })
    pd.DataFrame(by_sector).to_csv(OUT_DIR / "stage6_by_sector.csv", index=False)

    by_year = []
    for yr, s in ep_first.groupby("year"):
        if len(s) < 5:
            continue
        conf = s[s["H_only_outcome"] == "confirmed"]
        by_year.append({
            "year": int(yr),
            "n_H_only": len(s),
            "n_confirmed": len(conf),
            "confirm_rate": len(conf) / len(s),
            "confirmed_ret20": conf["fwd_ret_20"].mean() if len(conf) else np.nan,
        })
    pd.DataFrame(by_year).to_csv(OUT_DIR / "stage6_by_year.csv", index=False)

    # summary
    summary = {
        "n_symbols": int(panel["symbol"].nunique()),
        "n_rows": int(len(panel)),
        "n_H_only_full": int((panel["state_S"] == "H_only").sum()),
        "n_confirmed_full": int((panel["H_only_outcome"] == "confirmed").sum()),
        "n_episodes_first": int(size_df.loc[size_df["sample"] == "episode_first", "n_H_only"].iloc[0]),
        "n_daily_dedup": int(size_df.loc[size_df["sample"] == "daily_dedup", "n_H_only"].iloc[0]),
        "overlap_ratio": float(
            size_df.loc[size_df["sample"] == "full_overlap", "n_H_only"].iloc[0]
            / max(size_df.loc[size_df["sample"] == "episode_first", "n_H_only"].iloc[0], 1)
        ),
    }
    with open(OUT_DIR / "stage6_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    print(f"\nStage 6 输出已保存到 {OUT_DIR}")


if __name__ == "__main__":
    main()
