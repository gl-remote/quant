"""
ATR 跨周期比值研究 · Stage 5: H_only confirmed 前瞻指标筛选
==========================================================

前置：
- stage3_state_paths.py 生成的 stage3_panel.parquet
- stage4_trend_context.py 确认 trend_strength=strong 的过滤效果

待办：stage5-todo.md

目标：
- H1  成交量水平与变化
- H2  量价方向配合
- H3  持仓量水平与变化
- H4  量×OI 四象限
- H5  跳空
- H6  多变量预测力（logistic regression AUC）
- H7  稳健性：板块、年份、LOPO、非重叠、成本

输出：outputs/stage5/ 下的多张 CSV 和一个 summary JSON。
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore", category=RuntimeWarning)

# ---------- 路径 ----------
ROOT = Path(__file__).resolve().parents[5]
CSV_DIR = ROOT / "project_data" / "market_data" / "csv"
SCRIPT_DIR = Path(__file__).resolve().parents[1]
PANEL_PATH = SCRIPT_DIR / "outputs" / "stage3" / "stage3_panel.parquet"
OUT_DIR = SCRIPT_DIR / "outputs" / "stage5"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------- 参数 ----------
BOOT_N = 1000
BOOT_SEED = 42
MIN_N = 30
OI_MISSING_THRESHOLD = 0.5  # OI 缺失率 > 50% 的合约剔除
COST_BPS = [0, 1, 2, 3]  # 双边成本（bp）

# 候选前瞻指标（用于多变量模型）
CANDIDATE_PREDICTORS = [
    "vol_ratio",
    "vol_ratio_5",
    "vol_pct_100",
    "vol_chg_1",
    "vol_slope_5",
    "oi_pct_100",
    "dLogOI_5",
    "dLogOI_20",
    "oi_chg_bar",
    "gap_atr",
    "gap_filled",
]


# =====================================================================
# 1. 数据准备
# =====================================================================

def load_raw_1h(sym: str) -> pd.DataFrame:
    """加载 1h CSV，保留 volume / open_oi / close_oi。"""
    df = pd.read_csv(
        CSV_DIR / f"{sym}.tqsdk.1h.csv",
        parse_dates=["datetime"],
    ).set_index("datetime")
    return df[["open", "high", "low", "close", "volume", "open_oi", "close_oi"]]


def compute_volume_factors(df1h: pd.DataFrame) -> pd.DataFrame:
    """计算成交量因子。"""
    v = df1h["volume"].astype(float)
    out = pd.DataFrame(index=df1h.index)
    out["volume"] = v
    out["vol_ma_5"] = v.rolling(5, min_periods=3).mean()
    out["vol_ma_20"] = v.rolling(20, min_periods=10).mean()
    out["vol_ratio"] = v / out["vol_ma_20"]
    out["vol_ratio_5"] = v / out["vol_ma_5"]
    out["vol_pct_100"] = v.rolling(100, min_periods=50).rank(pct=True)
    out["vol_std_20"] = v.rolling(20, min_periods=10).std()
    out["vol_z_100"] = (v - v.rolling(100, min_periods=50).mean()) / out["vol_std_20"]
    out["vol_chg_1"] = v.pct_change(1)
    out["vol_chg_5"] = v.pct_change(5)
    # 线性回归斜率
    out["vol_slope_5"] = (
        v.rolling(5, min_periods=3).apply(
            lambda x: np.polyfit(range(len(x)), x.values, 1)[0] / x.mean()
            if x.mean() > 0 else np.nan,
            raw=False,
        )
    )
    return out


def compute_oi_factors(df1h: pd.DataFrame) -> pd.DataFrame:
    """计算持仓量因子。"""
    out = pd.DataFrame(index=df1h.index)
    # 用 close_oi，若缺失用 open_oi
    oi = df1h["close_oi"].copy()
    oi_open = df1h["open_oi"].copy()
    out["oi"] = oi
    out["oi_open"] = oi_open
    out["oi_chg_bar"] = oi - oi_open
    out["oi_ma_20"] = oi.rolling(20, min_periods=10).mean()
    out["oi_ma_60"] = oi.rolling(60, min_periods=30).mean()
    out["oi_pct_100"] = oi.rolling(100, min_periods=50).rank(pct=True)
    oi_std = oi.rolling(100, min_periods=50).std()
    out["oi_z_100"] = (oi - oi.rolling(100, min_periods=50).mean()) / oi_std
    out["dLogOI_5"] = np.log(oi / oi.shift(5))
    out["dLogOI_20"] = np.log(oi / oi.shift(20))
    out["oi_norm"] = oi / out["oi_ma_60"]
    # OI 斜率
    out["oi_slope_5"] = (
        oi.rolling(5, min_periods=3).apply(
            lambda x: np.polyfit(range(len(x)), x.values, 1)[0] / x.mean()
            if x.mean() > 0 else np.nan,
            raw=False,
        )
    )
    return out


def compute_gap_factors(df1h: pd.DataFrame, H: pd.Series) -> pd.DataFrame:
    """计算跳空因子。H 是 1h ATR(14)。"""
    out = pd.DataFrame(index=df1h.index)
    prev_close = df1h["close"].shift(1)
    out["gap"] = df1h["open"] / prev_close - 1
    out["gap_abs"] = out["gap"].abs()
    out["gap_atr"] = out["gap_abs"] / H
    out["gap_direction"] = np.sign(out["gap"])
    # 当根是否回补跳空
    out["gap_filled"] = (
        (out["gap"] > 0) & (df1h["low"] <= prev_close)
        | (out["gap"] < 0) & (df1h["high"] >= prev_close)
    ).astype(float)
    # 是否为 session 开盘根（与前一根时间差 > 2 小时）
    time_diff = df1h.index.to_series().diff().dt.total_seconds() / 3600
    out["is_session_open"] = (time_diff > 2).astype(float)
    # 隔夜跳空（21:00 开盘根）
    out["is_overnight"] = ((df1h.index.hour == 21) & (time_diff > 2)).astype(float)
    # 盘中跳空（session 内连续 bar，gap 应接近 0）
    out["gap_intraday"] = out["gap"].where(out["is_session_open"] == 0, 0.0)
    out["gap_session"] = out["gap"].where(out["is_session_open"] == 1, 0.0)
    return out


def build_enriched_panel() -> pd.DataFrame:
    """加载 Stage 3 面板，合并 volume / OI / gap 因子。"""
    panel = pd.read_parquet(PANEL_PATH)
    panel["datetime"] = pd.to_datetime(panel["datetime"])
    panel = panel.sort_values(["symbol", "datetime"]).reset_index(drop=True)

    # 重新加载 1h 原始数据并计算因子
    enriched_frames = []
    oi_coverage_rows = []

    for sym in sorted(panel["symbol"].unique()):
        sym_panel = panel[panel["symbol"] == sym].copy()
        df1h = load_raw_1h(sym)

        # 重新计算 H（ATR_1h(14)）用于 gap_atr
        # 从 stage3 面板直接取 H 即可，但需要按 datetime 对齐
        h_series = sym_panel.set_index("datetime")["H"]

        vol_fac = compute_volume_factors(df1h)
        oi_fac = compute_oi_factors(df1h)
        gap_fac = compute_gap_factors(df1h, h_series)

        # 合并
        combined = vol_fac.join(oi_fac, how="outer").join(gap_fac, how="outer")
        combined = combined.reindex(sym_panel["datetime"].values)
        combined.index = sym_panel.index
        sym_panel = pd.concat([sym_panel, combined], axis=1)

        # OI 覆盖率统计
        oi_coverage = 1 - sym_panel["oi"].isna().mean()
        oi_coverage_rows.append({
            "symbol": sym,
            "oi_coverage": oi_coverage,
            "n": len(sym_panel),
            "n_oi_valid": int(sym_panel["oi"].notna().sum()),
        })
        enriched_frames.append(sym_panel)

    result = pd.concat(enriched_frames, ignore_index=True)

    # 剔除 OI 覆盖率 < 50% 的合约
    coverage_df = pd.DataFrame(oi_coverage_rows)
    bad_syms = coverage_df[coverage_df["oi_coverage"] < OI_MISSING_THRESHOLD]["symbol"].tolist()
    if bad_syms:
        print(f"OI 覆盖率 < {OI_MISSING_THRESHOLD*100:.0f}% 的合约: {bad_syms}")
        result = result[~result["symbol"].isin(bad_syms)].copy()
    coverage_df.to_csv(OUT_DIR / "stage5_oi_coverage.csv", index=False)

    # 量×OI 组合字段
    result["vol_high"] = (result["vol_ratio"] > result.groupby("symbol")["vol_ratio"].transform("median")).astype(int)
    result["oi_up"] = (result["dLogOI_5"] > 0).astype(int)
    result["vol_oi_state"] = (
        result["vol_high"].astype(str) + "_" + result["oi_up"].astype(str)
    )
    result["vol_oi_state"] = result["vol_oi_state"].map({
        "1_1": "vol_up_oi_up",
        "1_0": "vol_up_oi_down",
        "0_1": "vol_down_oi_up",
        "0_0": "vol_down_oi_down",
    })
    # 量价方向
    result["ret_1"] = result["close"].pct_change(1)
    result["vol_price_state"] = np.where(
        (result["ret_1"] > 0) & (result["vol_chg_1"] > 0), "vol_up_price_up",
        np.where(
            (result["ret_1"] > 0) & (result["vol_chg_1"] <= 0), "vol_down_price_up",
            np.where(
                (result["ret_1"] <= 0) & (result["vol_chg_1"] > 0), "vol_up_price_down",
                "vol_down_price_down",
            ),
        ),
    )
    # 恐慌平仓 / 新资金
    result["capitulation"] = (
        (result["MADEV_60"] < 0)
        & (result["vol_ratio"] > 1.2)
        & (result["dLogOI_5"] < 0)
    ).astype(int)
    result["new_money"] = (
        (result["vol_ratio"] > 1.2) & (result["dLogOI_5"] > 0)
    ).astype(int)

    print(f"富集面板构建完成: {result['symbol'].nunique()} 合约, {len(result)} 行")
    return result


# =====================================================================
# 2. 统计工具
# =====================================================================

def cluster_bootstrap_ci(
    values: np.ndarray,
    clusters: np.ndarray,
    n_boot: int = BOOT_N,
) -> tuple[float, float]:
    rng = np.random.default_rng(BOOT_SEED)
    values = np.asarray(values, dtype=float)
    clusters = np.asarray(clusters)
    mask = ~np.isnan(values)
    values, clusters = values[mask], clusters[mask]
    if len(values) == 0:
        return np.nan, np.nan
    uniq = np.unique(clusters)
    idx_map = {c: np.where(clusters == c)[0] for c in uniq}
    stats = np.empty(n_boot)
    for i in range(n_boot):
        sampled = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([idx_map[c] for c in sampled])
        stats[i] = values[idx].mean()
    lo, hi = np.nanpercentile(stats, [2.5, 97.5])
    return float(lo), float(hi)


def mann_whitney_test(x: np.ndarray, y: np.ndarray) -> float:
    """Mann-Whitney U 检验 p 值。"""
    x = x[~np.isnan(x)]
    y = y[~np.isnan(y)]
    if len(x) < 5 or len(y) < 5:
        return np.nan
    return float(mannwhitneyu(x, y, alternative="two-sided").pvalue)


def safe_auc(y_true: np.ndarray, score: np.ndarray) -> float:
    """ROC AUC（封装 sklearn，自动处理 NaN 和单类）。"""
    mask = ~np.isnan(score) & ~np.isnan(y_true)
    y_true = y_true[mask]
    score = score[mask]
    if len(y_true) < 10 or len(np.unique(y_true)) < 2:
        return np.nan
    return float(roc_auc_score(y_true, score))


# =====================================================================
# 3. H1–H2: 成交量分析
# =====================================================================

def h1_volume_univariate(h_only: pd.DataFrame) -> pd.DataFrame:
    """单变量：成交量指标在 confirmed vs failed 的对比及 AUC。"""
    print("\n=== H1/H2: 成交量单变量 ===")
    y = (h_only["H_only_outcome"] == "confirmed").astype(int).values
    metrics = [
        "vol_ratio", "vol_ratio_5", "vol_pct_100", "vol_z_100",
        "vol_chg_1", "vol_chg_5", "vol_slope_5",
    ]
    rows = []
    conf = h_only[h_only["H_only_outcome"] == "confirmed"]
    fail = h_only[h_only["H_only_outcome"] == "failed"]
    for m in metrics:
        auc = safe_auc(y, h_only[m].values)
        p = mann_whitney_test(conf[m].values, fail[m].values)
        rows.append({
            "factor": m,
            "confirmed_mean": conf[m].mean(),
            "failed_mean": fail[m].mean(),
            "diff": conf[m].mean() - fail[m].mean(),
            "auc": auc,
            "mw_p": p,
        })
    df = pd.DataFrame(rows).sort_values("auc", key=lambda s: s.abs(), ascending=False)
    df.to_csv(OUT_DIR / "stage5_vol_univariate.csv", index=False)
    print(df.round(4).to_string(index=False))
    return df


def h1_volume_groups(h_only: pd.DataFrame) -> None:
    """vol_ratio 三分位 × outcome。"""
    print("\n=== H1: vol_ratio 三分位 × outcome ===")
    h_only = h_only.copy()
    h_only["vol_q"] = pd.qcut(
        h_only["vol_ratio"].rank(method="first"), 3, labels=["low", "mid", "high"]
    )
    rows = []
    for q, s in h_only.groupby("vol_q", observed=True):
        n_conf = (s["H_only_outcome"] == "confirmed").sum()
        n_total = len(s)
        for metric in ["fwd_ret_20", "fwd_abs_ret_20", "fwd_max_ret_20", "fwd_min_ret_20"]:
            conf_s = s[s["H_only_outcome"] == "confirmed"]
            r = {
                "vol_q": q,
                "n": n_total,
                "confirm_rate": n_conf / n_total if n_total else np.nan,
                "metric": metric,
                "confirmed_mean": conf_s[metric].mean() if len(conf_s) else np.nan,
                "all_mean": s[metric].mean(),
            }
            if len(conf_s) >= MIN_N:
                r["confirmed_ci_lo"], r["confirmed_ci_hi"] = cluster_bootstrap_ci(
                    conf_s[metric].values, conf_s["date"].values
                )
            rows.append(r)
    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "stage5_vol_groups.csv", index=False)
    pivot = df[df["metric"] == "fwd_ret_20"][
        ["vol_q", "n", "confirm_rate", "confirmed_mean", "all_mean"]
    ]
    print(pivot.round(4).to_string(index=False))


# =====================================================================
# 4. H3: OI 分析
# =====================================================================

def h3_oi_univariate(h_only: pd.DataFrame) -> pd.DataFrame:
    print("\n=== H3: OI 单变量 ===")
    y = (h_only["H_only_outcome"] == "confirmed").astype(int).values
    metrics = [
        "oi_pct_100", "oi_z_100", "dLogOI_5", "dLogOI_20",
        "oi_chg_bar", "oi_norm", "oi_slope_5",
    ]
    rows = []
    conf = h_only[h_only["H_only_outcome"] == "confirmed"]
    fail = h_only[h_only["H_only_outcome"] == "failed"]
    for m in metrics:
        auc = safe_auc(y, h_only[m].values)
        p = mann_whitney_test(conf[m].values, fail[m].values)
        rows.append({
            "factor": m,
            "confirmed_mean": conf[m].mean(),
            "failed_mean": fail[m].mean(),
            "diff": conf[m].mean() - fail[m].mean(),
            "auc": auc,
            "mw_p": p,
        })
    df = pd.DataFrame(rows).sort_values("auc", key=lambda s: s.abs(), ascending=False)
    df.to_csv(OUT_DIR / "stage5_oi_univariate.csv", index=False)
    print(df.round(4).to_string(index=False))
    return df


def h3_oi_groups(h_only: pd.DataFrame) -> None:
    """dLogOI_5 三分位 × outcome。"""
    print("\n=== H3: dLogOI_5 三分位 × outcome ===")
    h_only = h_only.copy()
    h_only["oi_q"] = pd.qcut(
        h_only["dLogOI_5"].rank(method="first"), 3, labels=["down", "flat", "up"]
    )
    rows = []
    for q, s in h_only.groupby("oi_q", observed=True):
        n_conf = (s["H_only_outcome"] == "confirmed").sum()
        conf_s = s[s["H_only_outcome"] == "confirmed"]
        r = {
            "oi_q": q,
            "n": len(s),
            "confirm_rate": n_conf / len(s),
            "confirmed_ret20": conf_s["fwd_ret_20"].mean() if len(conf_s) else np.nan,
            "all_ret20": s["fwd_ret_20"].mean(),
        }
        rows.append(r)
    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "stage5_oi_groups.csv", index=False)
    print(df.round(4).to_string(index=False))


# =====================================================================
# 5. H4: 量×OI 四象限
# =====================================================================

def h4_vol_oi_quadrant(h_only: pd.DataFrame) -> None:
    print("\n=== H4: 量×OI 四象限 ===")
    rows = []
    for state, s in h_only.groupby("vol_oi_state"):
        n_conf = (s["H_only_outcome"] == "confirmed").sum()
        conf_s = s[s["H_only_outcome"] == "confirmed"]
        r = {
            "vol_oi_state": state,
            "n": len(s),
            "confirm_rate": n_conf / len(s) if len(s) else np.nan,
            "confirmed_n": len(conf_s),
            "confirmed_ret20": conf_s["fwd_ret_20"].mean() if len(conf_s) else np.nan,
            "all_ret20": s["fwd_ret_20"].mean(),
            "all_abs_ret20": s["fwd_abs_ret_20"].mean(),
        }
        if len(conf_s) >= MIN_N:
            r["ci_lo"], r["ci_hi"] = cluster_bootstrap_ci(
                conf_s["fwd_ret_20"].values, conf_s["date"].values
            )
        rows.append(r)
    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "stage5_vol_oi_quadrant.csv", index=False)
    print(df.round(4).to_string(index=False))

    # capitulation / new_money
    print("\n=== H4: capitulation / new_money 标志 ===")
    for flag in ["capitulation", "new_money"]:
        for val in (1, 0):
            s = h_only[h_only[flag] == val]
            n_conf = (s["H_only_outcome"] == "confirmed").sum()
            print(
                f"  {flag}={val}: n={len(s):4d}  confirm_rate={n_conf/max(len(s),1):.3f}  "
                f"ret20={s['fwd_ret_20'].mean():.4f}"
            )


# =====================================================================
# 6. H5: 跳空
# =====================================================================

def h5_gap_univariate(h_only: pd.DataFrame) -> pd.DataFrame:
    print("\n=== H5: 跳空单变量 ===")
    y = (h_only["H_only_outcome"] == "confirmed").astype(int).values
    metrics = ["gap_atr", "gap_abs", "gap", "gap_filled", "gap_session", "gap_intraday"]
    rows = []
    conf = h_only[h_only["H_only_outcome"] == "confirmed"]
    fail = h_only[h_only["H_only_outcome"] == "failed"]
    for m in metrics:
        auc = safe_auc(y, h_only[m].values)
        p = mann_whitney_test(conf[m].values, fail[m].values)
        rows.append({
            "factor": m,
            "confirmed_mean": conf[m].mean(),
            "failed_mean": fail[m].mean(),
            "auc": auc,
            "mw_p": p,
        })
    df = pd.DataFrame(rows).sort_values("auc", key=lambda s: s.abs(), ascending=False)
    df.to_csv(OUT_DIR / "stage5_gap_univariate.csv", index=False)
    print(df.round(4).to_string(index=False))
    return df


def h5_gap_groups(h_only: pd.DataFrame) -> None:
    """gap_atr 分组 × trend 方向。"""
    print("\n=== H5: gap_atr × MADEV_60 方向 ===")
    h_only = h_only.copy()
    h_only["gap_q"] = pd.qcut(
        h_only["gap_atr"].rank(method="first"), 3, labels=["small", "mid", "large"]
    )
    h_only["trend_dir"] = np.where(h_only["MADEV_60"] > 0, "up", "down")
    rows = []
    for (gap_q, tdir), s in h_only.groupby(["gap_q", "trend_dir"], observed=True):
        n_conf = (s["H_only_outcome"] == "confirmed").sum()
        conf_s = s[s["H_only_outcome"] == "confirmed"]
        r = {
            "gap_q": gap_q, "trend_dir": tdir,
            "n": len(s), "confirm_rate": n_conf / len(s) if len(s) else np.nan,
            "confirmed_ret20": conf_s["fwd_ret_20"].mean() if len(conf_s) else np.nan,
            "all_ret20": s["fwd_ret_20"].mean(),
        }
        rows.append(r)
    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "stage5_gap_direction.csv", index=False)
    print(df.round(4).to_string(index=False))


# =====================================================================
# 7. H6: 多变量模型
# =====================================================================

def h6_multivariate(h_only: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    """L2 正则 logistic regression（sklearn），5-fold CV AUC。"""
    print("\n=== H6: 多变量 logistic regression (sklearn) ===")
    data = h_only.dropna(subset=CANDIDATE_PREDICTORS + ["H_only_outcome"]).copy()
    y = (data["H_only_outcome"] == "confirmed").astype(int).values
    X = data[CANDIDATE_PREDICTORS].values

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # 5-fold CV AUC
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=BOOT_SEED)
    aucs = []
    for train_idx, test_idx in skf.split(X_scaled, y):
        model = LogisticRegression(C=1.0, max_iter=1000, solver="lbfgs")
        model.fit(X_scaled[train_idx], y[train_idx])
        pred = model.predict_proba(X_scaled[test_idx])[:, 1]
        aucs.append(roc_auc_score(y[test_idx], pred))
    print(f"  5-fold CV AUC: {np.mean(aucs):.4f} ± {np.std(aucs):.4f}")

    # 全样本系数
    model = LogisticRegression(C=1.0, max_iter=1000, solver="lbfgs")
    model.fit(X_scaled, y)
    coef_df = pd.DataFrame({
        "factor": CANDIDATE_PREDICTORS,
        "coef": model.coef_[0],
        "abs_coef": np.abs(model.coef_[0]),
    }).sort_values("abs_coef", ascending=False)
    coef_df.to_csv(OUT_DIR / "stage5_multivariate_coef.csv", index=False)
    print("\n  系数（按绝对值排序）：")
    print(coef_df.round(4).to_string(index=False))

    # 全样本 AUC
    pred_all = model.predict_proba(X_scaled)[:, 1]
    full_auc = roc_auc_score(y, pred_all)
    print(f"\n  全样本 AUC: {full_auc:.4f}")

    # 预测概率分组：top quintile 的 confirmed 率和收益
    data["pred_prob"] = pred_all
    data["pred_q"] = pd.qcut(data["pred_prob"], 5, labels=["Q1", "Q2", "Q3", "Q4", "Q5"])
    rows = []
    for q, s in data.groupby("pred_q", observed=True):
        n_conf = (s["H_only_outcome"] == "confirmed").sum()
        rows.append({
            "pred_quintile": q,
            "n": len(s),
            "confirm_rate": n_conf / len(s),
            "ret20_mean": s["fwd_ret_20"].mean(),
            "abs_ret20_mean": s["fwd_abs_ret_20"].mean(),
            "pred_prob_mean": s["pred_prob"].mean(),
        })
    result = pd.DataFrame(rows)
    result.to_csv(OUT_DIR / "stage5_multivariate.csv", index=False)
    print("\n  预测概率五分位：")
    print(result.round(4).to_string(index=False))

    cv_summary = {
        "cv_auc_mean": float(np.mean(aucs)),
        "cv_auc_std": float(np.std(aucs)),
        "full_auc": float(full_auc),
        "n_samples": int(len(data)),
        "n_confirmed": int(y.sum()),
        "n_failed": int(len(y) - y.sum()),
    }
    return cv_summary, data


def h6_combo_filter(data: pd.DataFrame) -> None:
    """最优前瞻组合：pred_prob top quintile + trend_strength=strong。"""
    print("\n=== H6.4: 最优组合过滤 ===")
    strong = data[data["trend_strength_q"] == "strong"].copy() if "trend_strength_q" in data.columns else data
    # 如果 trend_strength 没有分位，直接用 > 2/3
    if "trend_strength_q" not in data.columns:
        data["trend_strength_q"] = pd.qcut(
            data["trend_strength"].rank(method="first"), 3, labels=["weak", "mid", "strong"]
        )
        strong = data[data["trend_strength_q"] == "strong"].copy()

    rows = []
    for label, subset in [
        ("all_H_only", data),
        ("top_quintile", data[data["pred_q"] == "Q5"]),
        ("strong_only", data[data["trend_strength_q"] == "strong"]),
        ("topQ_and_strong", data[(data["pred_q"] == "Q5") & (data["trend_strength_q"] == "strong")]),
    ]:
        n_conf = (subset["H_only_outcome"] == "confirmed").sum()
        conf_s = subset[subset["H_only_outcome"] == "confirmed"]
        r = {
            "filter": label,
            "n": len(subset),
            "n_confirmed": int(n_conf),
            "confirm_rate": n_conf / len(subset) if len(subset) else np.nan,
            "all_ret20": subset["fwd_ret_20"].mean(),
            "confirmed_ret20": conf_s["fwd_ret_20"].mean() if len(conf_s) else np.nan,
        }
        if len(conf_s) >= MIN_N:
            r["ci_lo"], r["ci_hi"] = cluster_bootstrap_ci(
                conf_s["fwd_ret_20"].values, conf_s["date"].values
            )
        rows.append(r)
    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "stage5_combo_filter.csv", index=False)
    print(df.round(4).to_string(index=False))


# =====================================================================
# 8. H7: 稳健性
# =====================================================================

def h7_by_sector_year(h_only: pd.DataFrame) -> None:
    """按板块/年份拆分核心指标。"""
    print("\n=== H7.1: 按板块（confirmed fwd_ret_20）===")
    rows = []
    for sec, s in h_only.groupby("sector"):
        conf = s[s["H_only_outcome"] == "confirmed"]
        if len(conf) < MIN_N:
            continue
        r = {
            "sector": sec,
            "n_H_only": len(s),
            "n_confirmed": len(conf),
            "confirm_rate": len(conf) / len(s),
            "confirmed_ret20": conf["fwd_ret_20"].mean(),
        }
        r["ci_lo"], r["ci_hi"] = cluster_bootstrap_ci(
            conf["fwd_ret_20"].values, conf["date"].values
        )
        rows.append(r)
    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "stage5_by_sector.csv", index=False)
    print(df.round(4).to_string(index=False))

    print("\n=== H7.2: 按年份 ===")
    rows = []
    for yr, s in h_only.groupby("year"):
        conf = s[s["H_only_outcome"] == "confirmed"]
        if len(conf) < MIN_N:
            continue
        r = {
            "year": int(yr),
            "n_H_only": len(s),
            "n_confirmed": len(conf),
            "confirm_rate": len(conf) / len(s),
            "confirmed_ret20": conf["fwd_ret_20"].mean(),
        }
        rows.append(r)
    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "stage5_by_year.csv", index=False)
    print(df.round(4).to_string(index=False))


def h7_lopo(h_only: pd.DataFrame) -> None:
    """Leave-One-Symbol-Out：用 sklearn LR 预测 confirmed。"""
    print("\n=== H7.3: LOPO ===")
    pred_vars = ["vol_ratio", "dLogOI_5", "gap_atr"]
    data = h_only.dropna(subset=pred_vars + ["H_only_outcome"]).copy()
    y_all = (data["H_only_outcome"] == "confirmed").astype(int).values
    X_all_raw = data[pred_vars].values

    syms = sorted(data["symbol"].unique())
    rows = []
    for sym in syms:
        train_mask = data["symbol"].values != sym
        test_mask = ~train_mask
        if test_mask.sum() < 5 or train_mask.sum() < 20:
            continue
        y_train = y_all[train_mask]
        if len(np.unique(y_train)) < 2:
            continue
        scaler = StandardScaler()
        X_tr = scaler.fit_transform(X_all_raw[train_mask])
        X_te = scaler.transform(X_all_raw[test_mask])
        model = LogisticRegression(C=1.0, max_iter=1000, solver="lbfgs")
        model.fit(X_tr, y_train)
        pred = model.predict_proba(X_te)[:, 1]
        y_test = y_all[test_mask]
        if len(np.unique(y_test)) < 2:
            auc = np.nan
        else:
            auc = float(roc_auc_score(y_test, pred))
        rows.append({"excluded": sym, "auc": auc, "n_test": int(test_mask.sum())})
    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "stage5_lopo.csv", index=False)
    print(f"  LOPO AUC: mean={df['auc'].mean():.4f}, min={df['auc'].min():.4f}, max={df['auc'].max():.4f}")


def h7_nonoverlap(h_only: pd.DataFrame) -> None:
    """非重叠抽样：每个 H_only 连续段只取第一根。"""
    print("\n=== H7.4: 非重叠抽样（每段 H_only 取第一根）===")
    h_only_sorted = h_only.sort_values(["symbol", "datetime"]).copy()
    is_new = (
        (h_only_sorted["symbol"] != h_only_sorted["symbol"].shift())
        | (h_only_sorted["state_S"] != h_only_sorted["state_S"].shift())
    )
    first_bars = h_only_sorted[is_new].copy()
    print(f"  原始 H_only: {len(h_only_sorted)}, 非重叠: {len(first_bars)}")

    n_conf = (first_bars["H_only_outcome"] == "confirmed").sum()
    conf = first_bars[first_bars["H_only_outcome"] == "confirmed"]
    r = {
        "n": len(first_bars),
        "n_confirmed": int(n_conf),
        "confirm_rate": n_conf / len(first_bars),
        "confirmed_ret20": conf["fwd_ret_20"].mean() if len(conf) else np.nan,
        "all_ret20": first_bars["fwd_ret_20"].mean(),
    }
    if len(conf) >= MIN_N:
        r["ci_lo"], r["ci_hi"] = cluster_bootstrap_ci(
            conf["fwd_ret_20"].values, conf["date"].values
        )
    df = pd.DataFrame([r])
    df.to_csv(OUT_DIR / "stage5_nonoverlap.csv", index=False)
    print(df.round(4).to_string(index=False))


def h7_cost_sensitivity(data: pd.DataFrame) -> None:
    """成本敏感性：topQ_and_strong 组合扣成本后的净收益。"""
    print("\n=== H7.5: 成本敏感性 ===")
    if "trend_strength_q" not in data.columns:
        data["trend_strength_q"] = pd.qcut(
            data["trend_strength"].rank(method="first"), 3, labels=["weak", "mid", "strong"]
        )
    subset = data[(data["pred_q"] == "Q5") & (data["trend_strength_q"] == "strong")].copy()
    rows = []
    for bp in COST_BPS:
        cost = bp / 10000.0
        net = subset["fwd_ret_20"] - cost
        conf = subset[subset["H_only_outcome"] == "confirmed"]
        net_conf = conf["fwd_ret_20"] - cost
        rows.append({
            "cost_bp": bp,
            "n": len(subset),
            "all_net_ret20": net.mean(),
            "confirmed_net_ret20": net_conf.mean() if len(conf) else np.nan,
            "win_rate": (net > 0).mean(),
        })
    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "stage5_cost_sensitivity.csv", index=False)
    print(df.round(6).to_string(index=False))


# =====================================================================
# 9. 主函数
# =====================================================================

def main() -> None:
    panel = build_enriched_panel()

    # 保存富集面板
    panel.to_parquet(OUT_DIR / "stage5_panel.parquet", index=False)

    # 提取 H_only 子样本
    h_only = panel[panel["state_S"] == "H_only"].copy()
    # 确保 outcome 有效
    h_only = h_only[h_only["H_only_outcome"].isin(["confirmed", "failed"])].copy()
    print(f"\nH_only 有效样本: {len(h_only)}")
    print(f"  confirmed: {(h_only['H_only_outcome']=='confirmed').sum()}")
    print(f"  failed:    {(h_only['H_only_outcome']=='failed').sum()}")

    # trend_strength 三分位
    h_only["trend_strength_q"] = pd.qcut(
        h_only["trend_strength"].rank(method="first"), 3, labels=["weak", "mid", "strong"]
    )

    # H1–H2 成交量
    h1_volume_univariate(h_only)
    h1_volume_groups(h_only)

    # H3 OI
    h3_oi_univariate(h_only)
    h3_oi_groups(h_only)

    # H4 量×OI
    h4_vol_oi_quadrant(h_only)

    # H5 跳空
    h5_gap_univariate(h_only)
    h5_gap_groups(h_only)

    # H6 多变量
    cv_summary, scored_data = h6_multivariate(h_only)
    h6_combo_filter(scored_data)

    # H7 稳健性
    h7_by_sector_year(h_only)
    h7_lopo(h_only)
    h7_nonoverlap(h_only)
    h7_cost_sensitivity(scored_data)

    # 汇总
    summary = {
        "n_panel": len(panel),
        "n_H_only": len(h_only),
        "n_confirmed": int((h_only["H_only_outcome"] == "confirmed").sum()),
        "n_failed": int((h_only["H_only_outcome"] == "failed").sum()),
        "cv_auc": cv_summary,
        "candidate_predictors": CANDIDATE_PREDICTORS,
    }
    with open(OUT_DIR / "stage5_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    print(f"\nStage 5 输出已保存到 {OUT_DIR}")


if __name__ == "__main__":
    main()
