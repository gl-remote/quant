"""
ATR 跨周期比值研究 · Stage 3: state_S 四象限未来路径检验
=========================================================

前置：stage1_eda.py 已完成分布描述，stage1-distribution.md 第 9 节提出假设。
待办：stage3-todo.md

目标：
- H1  状态转移矩阵（1/3/5/20 步）
- H2  co_compress 后波动扩张
- H3  co_expand 后均值回归
- H4  H_only 确认/失败（最关键）
- H5  L_only 衰减
- H6  R_bar × state_S 联合分层
- H7  稳健性：板块、年份、LOPO、聚类 bootstrap

输出：outputs/stage3/ 下的多张 CSV 和一个 summary JSON。
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
OUT_DIR = Path(__file__).resolve().parents[1] / "outputs" / "stage3"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------- 参数（与 Stage 1 一致，不在本阶段优化） ----------
H_SHORT, H_LONG = 14, 50
L_SHORT, L_LONG = 56, 200
ROLL_H, ROLL_L = 100, 400
FWD_HORIZONS = (5, 20, 100)
STATES = ["co_compress", "co_expand", "H_only", "L_only"]
BOOT_N = 1000
BOOT_SEED = 42
MIN_N = 30

# ---------- 板块映射 ----------
SECTOR_MAP: dict[str, str] = {
    # 能化
    "sc": "能化", "TA": "能化", "MA": "能化", "FG": "能化",
    "RU": "能化", "FU": "能化", "bu": "能化", "eg": "能化", "pp": "能化",
    # 有色 / 贵金属
    "cu": "有色", "al": "有色", "zn": "有色", "pb": "有色", "ni": "有色",
    "au": "贵金属", "ag": "贵金属",
    # 黑色
    "rb": "黑色", "hc": "黑色", "i": "黑色", "j": "黑色", "jm": "黑色",
    # 农产品
    "m": "农产品", "y": "农产品", "p": "农产品", "c": "农产品", "cs": "农产品",
    "a": "农产品", "b": "农产品",
    "CF": "农产品", "SR": "农产品", "RM": "农产品", "OI": "农产品",
}


def parse_symbol(sym: str) -> tuple[str, str, str]:
    """从合约代码解析 (exchange, product, sector)。

    例：DCE.c2601 -> ("DCE", "c", "农产品")
        CZCE.TA509 -> ("CZCE", "TA", "能化")
        INE.sc2509 -> ("INE", "sc", "能化")
    """
    exchange, code = sym.split(".", 1)
    # CZCE 品种可能是 2 个字母（TA/MA/SR/RM/OI/CF/FG），其余取首字母
    if exchange == "CZCE":
        # 取前导字母
        product = ""
        for ch in code:
            if ch.isalpha():
                product += ch
            else:
                break
    else:
        product = ""
        for ch in code:
            if ch.isalpha():
                product += ch
            else:
                break
    sector = SECTOR_MAP.get(product, "其他")
    return exchange, product, sector


# =====================================================================
# 1. 因子计算（复用 Stage 1 逻辑，并扩展 E/F 组）
# =====================================================================

def wilder_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def load_symbol(sym: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    df15 = pd.read_csv(CSV_DIR / f"{sym}.tqsdk.15m.csv", parse_dates=["datetime"]).set_index("datetime")
    df1h = pd.read_csv(CSV_DIR / f"{sym}.tqsdk.1h.csv", parse_dates=["datetime"]).set_index("datetime")
    return df15, df1h


def _state_duration(state: pd.Series) -> pd.Series:
    """当前 state 已连续出现的 bar 数。"""
    grp = (state != state.shift()).cumsum()
    return state.groupby(grp).cumcount() + 1


def _vel_sign(diff_series: pd.Series, window: int) -> pd.Series:
    """E 组：ATR 一阶差分移动平均的符号。"""
    ma = diff_series.rolling(window, min_periods=max(3, window // 2)).mean()
    return np.sign(ma)


def compute_panel(df15: pd.DataFrame, df1h: pd.DataFrame, sym: str) -> pd.DataFrame:
    """计算单个合约的完整面板（t 时刻因子 + 前置趋势 + 前向响应 + 分组标签）。"""
    exchange, product, sector = parse_symbol(sym)
    df = pd.DataFrame(index=df1h.index)
    df["close"] = df1h["close"]

    # ---- ATR ----
    H = wilder_atr(df1h["high"], df1h["low"], df1h["close"], H_SHORT)
    H_long = wilder_atr(df1h["high"], df1h["low"], df1h["close"], H_LONG)
    L_series = wilder_atr(df15["high"], df15["low"], df15["close"], L_SHORT)
    L_long_series = wilder_atr(df15["high"], df15["low"], df15["close"], L_LONG)

    l_df = pd.DataFrame({"L": L_series, "L_long": L_long_series, "time": df15.index})
    h_df = pd.DataFrame({"time": df1h.index})
    merged = pd.merge_asof(h_df, l_df, on="time", direction="backward")
    L = pd.Series(merged["L"].values, index=df.index)
    L_long = pd.Series(merged["L_long"].values, index=df.index)

    df["H"] = H
    df["L"] = L
    df["H_long"] = H_long
    df["L_long"] = L_long

    # ---- A. 跨周期比值 ----
    df["R_bar"] = H / L
    df["log_R_bar"] = np.log(df["R_bar"])
    df["R_clock"] = H / L_long
    df["log_R_clock"] = np.log(df["R_clock"])
    df["R_bar_pct"] = df["R_bar"].rolling(ROLL_H, min_periods=50).rank(pct=True)
    df["R_bar_z"] = (
        (df["R_bar"] - df["R_bar"].rolling(ROLL_H, min_periods=50).mean())
        / df["R_bar"].rolling(ROLL_H, min_periods=50).std()
    )
    df["R_bar_excess"] = df["log_R_bar"] - df["log_R_bar"].rolling(ROLL_H, min_periods=50).median()

    # ---- B. 单周期水平 ----
    df["H_pct"] = H.rolling(ROLL_H, min_periods=50).rank(pct=True)
    df["L_pct"] = L_series.rolling(ROLL_L, min_periods=100).rank(pct=True).reindex(df.index, method="ffill")
    df["H_norm"] = H / df["close"]
    df["L_norm"] = L / df["close"]
    df["common_vol"] = np.sqrt(df["H_norm"] * df["L_norm"])

    # ---- C. 同周期短长比 + state_S ----
    df["S_H"] = H / H_long
    df["S_L"] = L / L_long
    df["S_H_pct"] = df["S_H"].rolling(ROLL_H, min_periods=50).rank(pct=True)
    df["S_L_pct"] = df["S_L"].rolling(ROLL_H, min_periods=50).rank(pct=True)
    df["S_diff"] = df["S_H_pct"] - df["S_L_pct"]
    df["S_ratio"] = np.log(df["S_H"] / df["S_L"])

    df["state_S"] = "other"
    df.loc[(df["S_H"] > 1) & (df["S_L"] > 1), "state_S"] = "co_expand"
    df.loc[(df["S_H"] > 1) & (df["S_L"] <= 1), "state_S"] = "H_only"
    df.loc[(df["S_H"] <= 1) & (df["S_L"] > 1), "state_S"] = "L_only"
    df.loc[(df["S_H"] <= 1) & (df["S_L"] <= 1), "state_S"] = "co_compress"
    df["state_duration"] = _state_duration(df["state_S"])

    # ---- D. 累计变化 ----
    for k in (5, 20):
        df[f"dLogH_{k}"] = np.log(H / H.shift(k))
        df[f"dLogL_{k}"] = np.log(L / L.shift(k))
        df[f"dLogR_{k}"] = df[f"dLogH_{k}"] - df[f"dLogL_{k}"]

    # ---- E. 变化速度（备选） ----
    dH = H.diff()
    dL = L.diff()
    for k in (5, 20):
        df[f"vel_sign_H_{k}"] = _vel_sign(dH, k)
        df[f"vel_sign_L_{4*k}"] = _vel_sign(dL, 4 * k)

    # ---- F. 持续性 ----
    df["R_rank_chg_5"] = df["R_bar_pct"] - df["R_bar_pct"].shift(5)
    df["R_vs_MA20"] = df["R_bar"] / df["R_bar"].rolling(20, min_periods=10).mean() - 1

    # ---- 2.3 前置趋势字段 ----
    df["ret_20"] = df["close"].pct_change(20)
    df["ret_60"] = df["close"].pct_change(60)
    ma20 = df["close"].rolling(20, min_periods=15).mean()
    ma60 = df["close"].rolling(60, min_periods=40).mean()
    std20 = df["close"].pct_change().rolling(20, min_periods=15).std()
    df["MADEV_20"] = (df["close"] - ma20) / (std20 * df["close"])
    std60 = df["close"].pct_change().rolling(60, min_periods=40).std()
    df["MADEV_60"] = (df["close"] - ma60) / (std60 * df["close"])
    df["trend_strength"] = df["MADEV_60"].abs().rolling(60, min_periods=40).rank(pct=True)
    df["prev_state"] = df["state_S"].shift(1)

    # compress_duration：进入当前非 compress 状态前的 compress 持续 bar 数
    is_compress = (df["state_S"] == "co_compress").astype(int)
    compress_run = is_compress.groupby((is_compress != is_compress.shift()).cumsum()).cumcount() + 1
    compress_run = compress_run.where(is_compress == 1, 0)
    df["compress_duration"] = compress_run.shift(1).fillna(0)

    # ---- 2.4 前向响应 ----
    # 前向收益
    for k in FWD_HORIZONS:
        df[f"fwd_ret_{k}"] = df["close"].shift(-k) / df["close"] - 1
        df[f"fwd_abs_ret_{k}"] = df[f"fwd_ret_{k}"].abs()

    # 20 根内最高/最低收盘价相对当前
    future_close = df["close"].shift(-1)
    fwd_max_20 = future_close[::-1].rolling(20, min_periods=5).max()[::-1]
    fwd_min_20 = future_close[::-1].rolling(20, min_periods=5).min()[::-1]
    df["fwd_max_ret_20"] = fwd_max_20 / df["close"] - 1
    df["fwd_min_ret_20"] = fwd_min_20 / df["close"] - 1

    # 5 根内最大单根 |ret|
    fwd_ret_1 = df["close"].pct_change().shift(-1)
    df["fwd_max_abs_ret_5"] = fwd_ret_1.abs()[::-1].rolling(5, min_periods=3).max()[::-1]

    # 前向 ATR / 状态 / 比值
    for k in (5, 20):
        df[f"fwd_H_{k}"] = H.shift(-k)
        df[f"fwd_L_{k}"] = L.shift(-k)
        df[f"fwd_S_H_{k}"] = df["S_H"].shift(-k)
        df[f"fwd_S_L_{k}"] = df["S_L"].shift(-k)
        df[f"fwd_R_bar_{k}"] = df["R_bar"].shift(-k)
        df[f"fwd_state_{k}"] = df["state_S"].shift(-k)
    df["fwd_state_1"] = df["state_S"].shift(-1)
    df["fwd_state_3"] = df["state_S"].shift(-3)

    # H_only 确认标志
    df["fwd_S_L_up_3"] = (df["S_L"].shift(-3) > 1).astype("float")
    df["fwd_S_L_up_5"] = (df["S_L"].shift(-5) > 1).astype("float")
    df["fwd_ATR_expand_5"] = (
        (H.shift(-5) > H) & (L.shift(-5) > L)
    ).astype("float")

    # ---- 2.5 分组标签（每合约内部） ----
    df["R_bar_tercile"] = pd.qcut(
        df["R_bar"], 3, labels=["low", "mid", "high"]
    )
    df["S_diff_tercile"] = pd.qcut(
        df["S_diff"].rank(method="first"), 3, labels=["low", "mid", "high"]
    )
    df["H_pct_tercile"] = pd.qcut(
        df["H_pct"].rank(method="first"), 3, labels=["low", "mid", "high"]
    )
    # trend_group：MADEV_60 方向 × 强度三分位
    m60_sign = np.sign(df["MADEV_60"])
    m60_abs_pct = df["MADEV_60"].abs().rolling(60, min_periods=40).rank(pct=True)
    df["trend_group"] = "flat"
    df.loc[(m60_sign > 0) & (m60_abs_pct > 2 / 3), "trend_group"] = "uptrend_strong"
    df.loc[(m60_sign > 0) & (m60_abs_pct <= 2 / 3), "trend_group"] = "uptrend_weak"
    df.loc[(m60_sign < 0) & (m60_abs_pct > 2 / 3), "trend_group"] = "downtrend_strong"
    df.loc[(m60_sign < 0) & (m60_abs_pct <= 2 / 3), "trend_group"] = "downtrend_weak"

    df["state_combo"] = df["R_bar_tercile"].astype(str) + "_" + df["state_S"].astype(str)

    # H_only outcome
    df["H_only_outcome"] = "not_H_only"
    h_only_mask = df["state_S"] == "H_only"
    confirmed = h_only_mask & (df["fwd_S_L_up_5"] == 1)
    failed = h_only_mask & (df["fwd_S_L_up_5"] == 0)
    df.loc[confirmed, "H_only_outcome"] = "confirmed"
    df.loc[failed, "H_only_outcome"] = "failed"

    # ---- 2.1 基础标识 ----
    df["symbol"] = sym
    df["exchange"] = exchange
    df["product"] = product
    df["sector"] = sector
    df["datetime"] = df.index
    df["date"] = df.index.normalize()
    df["year"] = df.index.year
    # 交易时段：21:00 后到次日 02:30 视为夜盘
    hour = df.index.hour
    df["session"] = np.where((hour >= 21) | (hour < 3), "night", "day")

    # 剔除预热期
    valid_cols = ["R_bar", "S_H", "S_L", "state_S", "fwd_ret_20"]
    df = df.dropna(subset=valid_cols)
    return df


def build_panel() -> pd.DataFrame:
    syms_15 = {p.name.split(".tqsdk")[0] for p in CSV_DIR.glob("*.tqsdk.15m.csv")}
    syms_1h = {p.name.split(".tqsdk")[0] for p in CSV_DIR.glob("*.tqsdk.1h.csv")}
    syms = sorted(syms_15 & syms_1h)
    frames = []
    for sym in syms:
        df15, df1h = load_symbol(sym)
        frames.append(compute_panel(df15, df1h, sym))
    panel = pd.concat(frames, ignore_index=True)
    print(f"面板构建完成: {len(syms)} 合约, {len(panel)} 行")
    return panel


# =====================================================================
# 2. 统计工具
# =====================================================================

def cluster_bootstrap_ci(
    values: np.ndarray,
    clusters: np.ndarray,
    n_boot: int = BOOT_N,
    seed: int = BOOT_SEED,
) -> tuple[float, float]:
    """按 cluster（symbol-date）重采样的 95% bootstrap CI。

    自动剔除 values 中的 NaN，并同步过滤 clusters。
    """
    rng = np.random.default_rng(seed)
    values = np.asarray(values, dtype=float)
    clusters = np.asarray(clusters)
    mask = ~np.isnan(values)
    values = values[mask]
    clusters = clusters[mask]
    if len(values) == 0:
        return np.nan, np.nan
    unique_clusters = np.unique(clusters)
    cluster_to_idx = {c: np.where(clusters == c)[0] for c in unique_clusters}
    stats = np.empty(n_boot)
    for i in range(n_boot):
        sampled = rng.choice(unique_clusters, size=len(unique_clusters), replace=True)
        idx = np.concatenate([cluster_to_idx[c] for c in sampled])
        stats[i] = values[idx].mean()
    lo, hi = np.nanpercentile(stats, [2.5, 97.5])
    return float(lo), float(hi)


def summarize_by_group(
    panel: pd.DataFrame,
    group_col: str,
    value_col: str,
) -> pd.DataFrame:
    """按 group_col 分组，报告 count、mean、median、95% CI、独立日数。"""
    rows = []
    for name, sub in panel.groupby(group_col):
        # 同步剔除 NaN，保证 values 与 clusters 长度一致
        sub_valid = sub.dropna(subset=[value_col])
        vals = sub_valid[value_col].values
        if len(vals) < 1:
            continue
        n = len(vals)
        mean_v = float(np.nanmean(vals))
        med_v = float(np.nanmedian(vals))
        n_days = sub_valid["date"].nunique()
        n_syms = sub_valid["symbol"].nunique()
        ci_lo, ci_hi = (np.nan, np.nan)
        if n >= MIN_N:
            ci_lo, ci_hi = cluster_bootstrap_ci(vals, sub_valid["date"].values)
        rows.append({
            "group": name,
            "n": n,
            "n_days": n_days,
            "n_symbols": n_syms,
            "mean": mean_v,
            "median": med_v,
            "ci_lo": ci_lo,
            "ci_hi": ci_hi,
            "sufficient": n >= MIN_N,
        })
    return pd.DataFrame(rows).sort_values("mean", ascending=False)


def binom_direction_test(panel: pd.DataFrame, group_col: str, ret_col: str = "fwd_ret_20") -> pd.DataFrame:
    """各组方向胜率及二项检验 p-value（对比 50%）。"""
    from scipy.stats import binomtest
    rows = []
    for name, sub in panel.groupby(group_col):
        vals = sub[ret_col].dropna()
        if len(vals) < MIN_N:
            rows.append({"group": name, "n": len(vals), "pct_pos": np.nan, "p_value": np.nan})
            continue
        n_pos = int((vals > 0).sum())
        pct = n_pos / len(vals)
        p = binomtest(n_pos, len(vals), 0.5).pvalue
        rows.append({"group": name, "n": len(vals), "pct_pos": pct, "p_value": p})
    return pd.DataFrame(rows)


# =====================================================================
# 3. H1：状态转移矩阵
# =====================================================================

def h1_transition_matrices(panel: pd.DataFrame) -> None:
    print("\n=== H1: 状态转移矩阵 ===")
    rows = []
    for step in (1, 3, 5, 20):
        for from_s in STATES:
            sub = panel[panel["state_S"] == from_s]
            col = f"fwd_state_{step}"
            if col not in sub.columns:
                continue
            counts = sub[col].value_counts()
            total = counts.sum()
            for to_s in STATES:
                n = int(counts.get(to_s, 0))
                rows.append({
                    "step": step, "from": from_s, "to": to_s,
                    "count": n, "prob": n / total if total else np.nan,
                })
    trans = pd.DataFrame(rows)
    trans.to_csv(OUT_DIR / "stage3_transition_matrix.csv", index=False)

    # H1.2/H1.3 关键条件概率
    pivot5 = trans[trans["step"] == 5].pivot(index="from", columns="to", values="prob")
    print("5 步转移概率：")
    print(pivot5.round(3))

    # H1.5 路径频率：compress -> H_only / L_only -> expand
    # 用连续 3 根的状态序列统计
    panel_sorted = panel.sort_values(["symbol", "datetime"]).copy()
    s0 = panel_sorted["state_S"]
    s1 = panel_sorted.groupby("symbol")["state_S"].shift(-1)
    s2 = panel_sorted.groupby("symbol")["state_S"].shift(-2)
    path_mask = (s0 == "co_compress")
    h_path = path_mask & (s1 == "H_only") & (s2 == "co_expand")
    l_path = path_mask & (s1 == "L_only") & (s2 == "co_expand")
    n_compress = int(path_mask.sum())
    path_df = pd.DataFrame([
        {"path": "compress->H_only->expand", "count": int(h_path.sum()), "rate": h_path.sum() / max(n_compress, 1)},
        {"path": "compress->L_only->expand", "count": int(l_path.sum()), "rate": l_path.sum() / max(n_compress, 1)},
    ])
    path_df.to_csv(OUT_DIR / "stage3_path_frequency.csv", index=False)
    print("\n路径频率：")
    print(path_df)


# =====================================================================
# 4. H2–H5：各象限基础收益与波动
# =====================================================================

def h2_to_h5_state_returns(panel: pd.DataFrame) -> None:
    print("\n=== H2-H5: 各象限未来收益 ===")
    all_rows = []
    for ret_col in [f"fwd_ret_{k}" for k in FWD_HORIZONS] + [f"fwd_abs_ret_{k}" for k in FWD_HORIZONS]:
        tbl = summarize_by_group(panel, "state_S", ret_col)
        tbl["metric"] = ret_col
        all_rows.append(tbl)
    result = pd.concat(all_rows, ignore_index=True)
    result.to_csv(OUT_DIR / "stage3_state_returns.csv", index=False)

    # 方向胜率
    dir_tests = binom_direction_test(panel, "state_S")
    dir_tests.to_csv(OUT_DIR / "stage3_state_direction.csv", index=False)
    print("\nfwd_ret_20 方向胜率：")
    print(dir_tests.round(4))

    # H2.2: 各象限后 ATR 扩张概率
    expand_prob = panel.groupby("state_S").agg(
        n=("fwd_ATR_expand_5", "size"),
        expand_rate=("fwd_ATR_expand_5", "mean"),
    ).reset_index()
    expand_prob.to_csv(OUT_DIR / "stage3_atr_expand_prob.csv", index=False)
    print("\n5 根后双周期 ATR 扩张概率：")
    print(expand_prob.round(4))


def h2_state_duration(panel: pd.DataFrame) -> None:
    """H2.5 / H5.2：各象限持续时间分布。"""
    print("\n=== 状态持续时间分布 ===")
    dur = panel.groupby("state_S")["state_duration"].describe(
        percentiles=[0.25, 0.5, 0.75, 0.9]
    ).reset_index()
    dur.to_csv(OUT_DIR / "stage3_state_duration.csv", index=False)
    print(dur.round(2))


def h2_compress_depth(panel: pd.DataFrame) -> None:
    """H2.3：co_compress 按 S_H×S_L 深度分组的后续 |r|。"""
    print("\n=== H2.3: 压缩深度与后续波动 ===")
    sub = panel[panel["state_S"] == "co_compress"].copy()
    sub["depth"] = (1 - sub["S_H"]) * (1 - sub["S_L"])  # 越深越大
    sub["depth_q"] = pd.qcut(sub["depth"].rank(method="first"), 3, labels=["shallow", "mid", "deep"])
    tbl = summarize_by_group(sub, "depth_q", "fwd_abs_ret_20")
    tbl.to_csv(OUT_DIR / "stage3_compress_depth.csv", index=False)
    print(tbl.round(4))


def h3_expand_sdiff(panel: pd.DataFrame) -> None:
    """H3.3/H3.4：co_expand 按 S_diff 分组。"""
    print("\n=== H3: co_expand 按 S_diff 分组 ===")
    sub = panel[panel["state_S"] == "co_expand"].copy()
    sub["sd_group"] = pd.qcut(sub["S_diff"].rank(method="first"), 3, labels=["L_led", "balanced", "H_led"])
    rows = []
    for metric in ["fwd_ret_5", "fwd_ret_20", "fwd_ret_100", "fwd_abs_ret_20"]:
        t = summarize_by_group(sub, "sd_group", metric)
        t["metric"] = metric
        rows.append(t)
    result = pd.concat(rows, ignore_index=True)
    result.to_csv(OUT_DIR / "stage3_expand_sdiff.csv", index=False)
    print(result.pivot(index="group", columns="metric", values="mean").round(4))


def h4_h_only_outcomes(panel: pd.DataFrame) -> None:
    """H4：H_only 确认/失败专项（最关键）。"""
    print("\n=== H4: H_only 确认/失败 ===")
    sub = panel[panel["state_S"] == "H_only"].copy()
    # 确认率
    conf_rate_5 = sub["fwd_S_L_up_5"].mean()
    conf_rate_3 = sub["fwd_S_L_up_3"].mean()
    print(f"H_only 后 3 根 S_L>1 概率: {conf_rate_3:.3f}")
    print(f"H_only 后 5 根 S_L>1 概率: {conf_rate_5:.3f}")

    # 确认 vs 失败的后续收益
    rows = []
    for outcome in ["confirmed", "failed"]:
        s = sub[sub["H_only_outcome"] == outcome]
        if len(s) < MIN_N:
            continue
        for metric in ["fwd_ret_5", "fwd_ret_20", "fwd_abs_ret_20", "fwd_max_ret_20", "fwd_min_ret_20"]:
            vals = s[metric].dropna().values
            ci_lo, ci_hi = cluster_bootstrap_ci(vals, s["date"].values)
            rows.append({
                "outcome": outcome,
                "n": len(s),
                "metric": metric,
                "mean": float(np.nanmean(vals)),
                "median": float(np.nanmedian(vals)),
                "ci_lo": ci_lo,
                "ci_hi": ci_hi,
            })
    result = pd.DataFrame(rows)
    result.to_csv(OUT_DIR / "stage3_h_only_outcomes.csv", index=False)
    print("\nH_only confirmed vs failed：")
    if not result.empty:
        pivot = result.pivot(index="outcome", columns="metric", values="mean")
        print(pivot.round(4))

    # H4.5: H_only + R_bar 高 + dLogL_5 转正
    sub["combo_hit"] = (
        (sub["R_bar_tercile"] == "high") & (sub["dLogL_5"] > 0)
    ).astype(int)
    combo_rows = []
    for hit, s in sub.groupby("combo_hit"):
        if len(s) < MIN_N:
            continue
        for metric in ["fwd_ret_20", "fwd_abs_ret_20"]:
            vals = s[metric].dropna().values
            ci_lo, ci_hi = cluster_bootstrap_ci(vals, s["date"].values)
            combo_rows.append({
                "combo": "H_only+Rhigh+dLogL5pos" if hit else "other_H_only",
                "n": len(s),
                "metric": metric,
                "mean": float(np.nanmean(vals)),
                "ci_lo": ci_lo,
                "ci_hi": ci_hi,
            })
    combo_df = pd.DataFrame(combo_rows)
    combo_df.to_csv(OUT_DIR / "stage3_h_only_combo.csv", index=False)
    print("\nH4.5 组合信号：")
    print(combo_df.round(4))

    # H4.6: dLogL_5 与未来 S_L 变化的相关性
    sub["fwd_dSL_5"] = sub["fwd_S_L_5"] - sub["S_L"]
    corr = sub[["dLogL_5", "fwd_dSL_5", "fwd_S_L_up_5"]].corr()
    corr.to_csv(OUT_DIR / "stage3_h_only_dlogl_corr.csv")
    print(f"\ndLogL_5 与 fwd_S_L 变化相关: {corr.loc['dLogL_5', 'fwd_dSL_5']:.3f}")


def h5_l_only_decay(panel: pd.DataFrame) -> None:
    """H5：L_only 衰减。"""
    print("\n=== H5: L_only 衰减 ===")
    sub = panel[panel["state_S"] == "L_only"].copy()

    # 按持续时间分组
    sub["dur_group"] = pd.cut(
        sub["state_duration"], bins=[0, 2, 5, 100], labels=["1-2", "3-5", "5+"]
    )
    rows = []
    for dur_g, s in sub.groupby("dur_group", observed=True):
        if len(s) < MIN_N:
            continue
        # 5 步后升级为 co_expand 的概率
        upgrade = (s["fwd_state_5"] == "co_expand").mean()
        revert = (s["fwd_state_5"] == "co_compress").mean()
        rows.append({
            "duration": str(dur_g),
            "n": len(s),
            "upgrade_to_expand": upgrade,
            "revert_to_compress": revert,
            "fwd_abs_ret_20_mean": s["fwd_abs_ret_20"].mean(),
        })
    dur_df = pd.DataFrame(rows)
    dur_df.to_csv(OUT_DIR / "stage3_l_only_decay.csv", index=False)
    print(dur_df.round(4))

    # H5.3: 按前置 compress 持续时间分组
    sub["pre_compress_group"] = pd.cut(
        sub["compress_duration"], bins=[-1, 5, 20, 1000], labels=["short", "mid", "long"]
    )
    pre_rows = []
    for pc, s in sub.groupby("pre_compress_group", observed=True):
        if len(s) < MIN_N:
            continue
        pre_rows.append({
            "pre_compress": str(pc),
            "n": len(s),
            "upgrade_to_expand_5": (s["fwd_state_5"] == "co_expand").mean(),
            "fwd_abs_ret_20": s["fwd_abs_ret_20"].mean(),
        })
    pre_df = pd.DataFrame(pre_rows)
    pre_df.to_csv(OUT_DIR / "stage3_l_only_prestate.csv", index=False)
    print("\n按前置 compress 持续时间：")
    print(pre_df.round(4))


# =====================================================================
# 5. H6：R_bar × state_S 联合分层
# =====================================================================

def h6_rbar_state_combo(panel: pd.DataFrame) -> None:
    print("\n=== H6: R_bar × state_S 联合分层 ===")
    rows = []
    for combo, sub in panel.groupby("state_combo"):
        if len(sub) < MIN_N:
            continue
        for metric in ["fwd_ret_20", "fwd_abs_ret_20", "fwd_ret_5"]:
            vals = sub[metric].dropna().values
            ci_lo, ci_hi = (np.nan, np.nan)
            if len(vals) >= MIN_N:
                ci_lo, ci_hi = cluster_bootstrap_ci(vals, sub["date"].values)
            rows.append({
                "combo": combo,
                "n": len(sub),
                "n_days": sub["date"].nunique(),
                "metric": metric,
                "mean": float(np.nanmean(vals)),
                "median": float(np.nanmedian(vals)),
                "ci_lo": ci_lo,
                "ci_hi": ci_hi,
            })
    result = pd.DataFrame(rows)
    result.to_csv(OUT_DIR / "stage3_Rbar_state_combo.csv", index=False)

    # H6.5: 同 state_S 内 R_bar 高/低差异
    inc_rows = []
    for state, sub in panel.groupby("state_S"):
        high = sub[sub["R_bar_tercile"] == "high"]
        low = sub[sub["R_bar_tercile"] == "low"]
        if len(high) < MIN_N or len(low) < MIN_N:
            continue
        for metric in ["fwd_ret_20", "fwd_abs_ret_20"]:
            inc_rows.append({
                "state_S": state,
                "metric": metric,
                "high_R_mean": high[metric].mean(),
                "low_R_mean": low[metric].mean(),
                "diff": high[metric].mean() - low[metric].mean(),
                "n_high": len(high),
                "n_low": len(low),
            })
    inc_df = pd.DataFrame(inc_rows)
    inc_df.to_csv(OUT_DIR / "stage3_rbar_incremental.csv", index=False)
    print("\n同 state_S 内 R_bar 高/低差异（fwd_ret_20）：")
    print(inc_df[inc_df["metric"] == "fwd_ret_20"].round(4))


# =====================================================================
# 6. H7：稳健性
# =====================================================================

def _core_metrics(panel: pd.DataFrame) -> dict:
    """计算核心指标，供 LOPO / 分组使用。"""
    metrics = {}
    # H_only 5 根确认率
    h_only = panel[panel["state_S"] == "H_only"]
    metrics["H_only_n"] = len(h_only)
    metrics["H_only_confirm_rate_5"] = float(h_only["fwd_S_L_up_5"].mean()) if len(h_only) else np.nan
    # co_compress 后 fwd_abs_ret_20
    cc = panel[panel["state_S"] == "co_compress"]
    metrics["co_compress_n"] = len(cc)
    metrics["co_compress_abs_ret_20"] = float(cc["fwd_abs_ret_20"].mean()) if len(cc) else np.nan
    # 无条件 fwd_abs_ret_20
    metrics["uncond_abs_ret_20"] = float(panel["fwd_abs_ret_20"].mean())
    # 各象限 fwd_ret_20
    for s in STATES:
        sub = panel[panel["state_S"] == s]
        metrics[f"{s}_ret_20"] = float(sub["fwd_ret_20"].mean()) if len(sub) else np.nan
        metrics[f"{s}_abs_ret_20"] = float(sub["fwd_abs_ret_20"].mean()) if len(sub) else np.nan
    return metrics


def h7_by_sector(panel: pd.DataFrame) -> None:
    print("\n=== H7.1: 按板块 ===")
    rows = []
    for sector, sub in panel.groupby("sector"):
        m = _core_metrics(sub)
        m["sector"] = sector
        rows.append(m)
    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "stage3_by_sector.csv", index=False)
    print(df.round(4).to_string())


def h7_by_year(panel: pd.DataFrame) -> None:
    print("\n=== H7.2: 按年份 ===")
    rows = []
    for year, sub in panel.groupby("year"):
        m = _core_metrics(sub)
        m["year"] = int(year)
        rows.append(m)
    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "stage3_by_year.csv", index=False)
    print(df.round(4).to_string())


def h7_lopo(panel: pd.DataFrame) -> None:
    """H7.3：Leave-One-Symbol-Out。"""
    print("\n=== H7.3: LOPO ===")
    syms = sorted(panel["symbol"].unique())
    full = _core_metrics(panel)
    rows = []
    for sym in syms:
        sub = panel[panel["symbol"] != sym]
        m = _core_metrics(sub)
        m["excluded"] = sym
        m["H_only_confirm_delta"] = m["H_only_confirm_rate_5"] - full["H_only_confirm_rate_5"]
        m["co_compress_abs_delta"] = m["co_compress_abs_ret_20"] - full["co_compress_abs_ret_20"]
        rows.append(m)
    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "stage3_lopo.csv", index=False)
    # 报告最有影响力的合约
    print("H_only 确认率 LOPO 波动：")
    print(f"  全样本: {full['H_only_confirm_rate_5']:.4f}")
    print(f"  LOPO min/max: {df['H_only_confirm_rate_5'].min():.4f} / {df['H_only_confirm_rate_5'].max():.4f}")
    biggest = df.loc[df["H_only_confirm_delta"].abs().idxmax()]
    print(f"  影响最大: 排除 {biggest['excluded']} -> delta {biggest['H_only_confirm_delta']:+.4f}")


# =====================================================================
# 7. 主函数
# =====================================================================

def main() -> None:
    panel = build_panel()

    # 保存面板供后续分析复用
    panel.to_parquet(OUT_DIR / "stage3_panel.parquet", index=False)
    print(f"面板已保存: {OUT_DIR / 'stage3_panel.parquet'}")

    # 按执行顺序运行各假设
    h1_transition_matrices(panel)
    h2_to_h5_state_returns(panel)
    h2_state_duration(panel)
    h2_compress_depth(panel)
    h3_expand_sdiff(panel)
    h4_h_only_outcomes(panel)
    h5_l_only_decay(panel)
    h6_rbar_state_combo(panel)

    # 稳健性
    h7_by_sector(panel)
    h7_by_year(panel)
    h7_lopo(panel)

    # 汇总 summary
    summary = {
        "n_rows": len(panel),
        "n_symbols": panel["symbol"].nunique(),
        "n_dates": panel["date"].nunique(),
        "date_range": [str(panel["datetime"].min()), str(panel["datetime"].max())],
        "state_counts": panel["state_S"].value_counts().to_dict(),
        "core_metrics": _core_metrics(panel),
        "params": {
            "H_SHORT": H_SHORT, "H_LONG": H_LONG,
            "L_SHORT": L_SHORT, "L_LONG": L_LONG,
            "FWD_HORIZONS": list(FWD_HORIZONS),
            "BOOT_N": BOOT_N, "MIN_N": MIN_N,
        },
    }
    with open(OUT_DIR / "stage3_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    print(f"\nStage 3 输出已保存到 {OUT_DIR}")


if __name__ == "__main__":
    main()
