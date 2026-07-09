"""
文件级元信息：
- 创建背景：poc-value-area-asymmetry 主题阶段 1 gatekeeper 测量脚本。
- 用途：读取 5m 期货 CSV → 为每个 1h 时刻构建三种 volume profile（W1 前一天 /
  W2 前一周 / W3 rolling）→ 计算四种不对称度量（A1 volume ratio / A2 距离
  ratio / A3 skewness / A4 重心距离比）→ 与未来 1/2/4/8 小时对数收益做
  pooled / per-symbol Spearman IC + cluster bootstrap（按 contract 聚类）
  + Bonferroni 校正。
- 注意事项：临时研究脚本，不进入 workspace/。计算完成后输出到
  project_data/logs/poc_va_asymmetry_stage1/ 下的 CSV，供 workbench 报告
  引用；主题稳定后随 archive 批次搬走。所有假设符合 experiment-plan §0-1。
  单跑，Python 3.11+ / pandas / numpy / scipy。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

# ============================================================================
# 常量与配置
# ============================================================================

# 20 合约清单：沿用 structural-shaping-alpha stage1 gatekeeper 已验证的实际
# 落库集合（sc2601 不存在 → 用 sc2512 替代；每板块取 2 主力合约）。
SYMBOLS: list[tuple[str, str]] = [
    ("black", "SHFE.rb2601"),
    ("black", "DCE.i2601"),
    ("metals", "SHFE.cu2601"),
    ("metals", "SHFE.al2601"),
    ("energy_chem", "INE.sc2512"),
    ("energy_chem", "CZCE.TA601"),
    ("agri_dce", "DCE.m2601"),
    ("agri_dce", "DCE.p2601"),
    ("agri_czce", "CZCE.SR601"),
    ("agri_czce", "CZCE.CF601"),
]

# tick_size 表：沿用 rolling_reacceptance_stage1_direction.py 与
# workspace/common/contract_specs.py。
TICK_SIZE: dict[str, float] = {
    "rb": 1.0,
    "i": 0.5,
    "cu": 10.0,
    "al": 5.0,
    "sc": 0.1,
    "TA": 2.0,
    "m": 1.0,
    "p": 2.0,
    "SR": 1.0,
    "CF": 5.0,
}

CSV_DIR = Path("/Users/gaolei/Documents/src/quant/project_data/market_data/csv")
OUT_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage1"
)
OUT_DIR.mkdir(parents=True, exist_ok=True)

VALUE_AREA_RATIO = 0.70
ROLLING_BARS_5M = 144  # ≈12 小时的 5m bar 数；阶段 2 再做 K 敏感度扫描
FUTURE_HORIZONS_HOURS: list[int] = [1, 2, 4, 8]
BOOTSTRAP_N = 5000
RNG_SEED = 20260707


# ============================================================================
# 数据加载
# ============================================================================


def parse_prefix(symbol: str) -> str:
    """从 EXCHANGE.CONTRACT 解析品种前缀（去除数字部分）。"""
    _, contract = symbol.split(".")
    return "".join(c for c in contract if c.isalpha())


def load_5m(symbol: str) -> pd.DataFrame:
    """加载 5m bar，返回带 datetime index 的 DataFrame。"""
    path = CSV_DIR / f"{symbol}.tqsdk.5m.csv"
    df = pd.read_csv(path)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    df["date"] = df["datetime"].dt.date
    return df


# ============================================================================
# Volume Profile 构建
# ============================================================================


@dataclass(frozen=True)
class Profile:
    poc: float
    vah: float
    val: float
    # 上下侧 volume 与重心（在 VA 内）
    vol_upper: float  # POC < price ≤ VAH
    vol_lower: float  # VAL ≤ price < POC
    e_upper: float  # 上侧价格 volume 重心
    e_lower: float  # 下侧价格 volume 重心
    # 整个 profile 的加权 skewness（不限 VA）
    skew: float
    # 分箱结果（价格 → volume），主要给 diagnostics
    total_vol: float


def build_profile(bars: pd.DataFrame, tick: float) -> Profile | None:
    """close-based bucketing 构建 volume profile。

    - 按 tick 分箱：bucket_price = round(close / tick) * tick
    - POC = argmax(volume_by_bucket)，同频取距离最近的 close 那一侧
    - VA = 从 POC 双向贪心扩展直到累计 ≥ VALUE_AREA_RATIO * total
    - 计算上下侧 volume / 重心 / 全 profile 加权 skewness
    """
    if len(bars) == 0:
        return None
    buckets = (np.round(bars["close"].to_numpy() / tick) * tick).astype(float)
    volumes = bars["volume"].to_numpy(dtype=float)
    profile_df = (
        pd.DataFrame({"price": buckets, "volume": volumes})
        .groupby("price", as_index=False)["volume"]
        .sum()
        .sort_values("price")
        .reset_index(drop=True)
    )
    if profile_df.empty:
        return None
    total = float(profile_df["volume"].sum())
    if total <= 0:
        return None
    # POC
    max_vol = profile_df["volume"].max()
    tied = profile_df[profile_df["volume"] == max_vol].copy()
    last_close = float(bars["close"].iloc[-1])
    tied["dist"] = (tied["price"] - last_close).abs()
    poc = float(tied.sort_values(["dist", "price"]).iloc[0]["price"])

    # VA 双向贪心
    prices = profile_df["price"].to_numpy()
    vols = profile_df["volume"].to_numpy()
    poc_idx = int(np.where(prices == poc)[0][0])
    lo, hi = poc_idx, poc_idx
    acc = float(vols[poc_idx])
    target = VALUE_AREA_RATIO * total
    while acc < target and (lo > 0 or hi < len(prices) - 1):
        left_v = float(vols[lo - 1]) if lo > 0 else -1.0
        right_v = float(vols[hi + 1]) if hi < len(prices) - 1 else -1.0
        if right_v >= left_v and hi < len(prices) - 1:
            hi += 1
            acc += float(vols[hi])
        elif lo > 0:
            lo -= 1
            acc += float(vols[lo])
        else:
            break
    val = float(prices[lo])
    vah = float(prices[hi])

    # 上下侧 volume（POC 严格不参与）
    upper_mask = prices > poc
    lower_mask = prices < poc
    va_mask = (prices >= val) & (prices <= vah)
    vol_upper = float(vols[upper_mask & va_mask].sum())
    vol_lower = float(vols[lower_mask & va_mask].sum())
    e_upper = _weighted_mean(prices[upper_mask & va_mask], vols[upper_mask & va_mask])
    e_lower = _weighted_mean(prices[lower_mask & va_mask], vols[lower_mask & va_mask])

    # 加权 skewness（整 profile）
    mean = float(np.average(prices, weights=vols))
    var = float(np.average((prices - mean) ** 2, weights=vols))
    std = math.sqrt(var) if var > 0 else 0.0
    if std > 0:
        skew = float(np.average(((prices - mean) / std) ** 3, weights=vols))
    else:
        skew = 0.0

    return Profile(
        poc=poc,
        vah=vah,
        val=val,
        vol_upper=vol_upper,
        vol_lower=vol_lower,
        e_upper=e_upper,
        e_lower=e_lower,
        skew=skew,
        total_vol=total,
    )


def _weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    if len(values) == 0 or weights.sum() <= 0:
        return float("nan")
    return float(np.average(values, weights=weights))


# ============================================================================
# 不对称度量 A1-A4
# ============================================================================


def compute_asymmetry(p: Profile, tick: float) -> dict[str, float]:
    """四种度量。log ratio 类度量对完全对称取值 0。"""
    eps = 1e-9
    # A1 · Volume 比例（VA 内上下侧）
    a1 = math.log(max(p.vol_upper, eps) / max(p.vol_lower, eps))
    # A2 · 距离比例
    up_dist = p.vah - p.poc
    dn_dist = p.poc - p.val
    a2 = math.log(max(up_dist, eps) / max(dn_dist, eps))
    # A3 · profile skewness（无变换）
    a3 = p.skew
    # A4 · 重心距离比
    if not (math.isnan(p.e_upper) or math.isnan(p.e_lower)):
        up_d = p.e_upper - p.poc
        dn_d = p.poc - p.e_lower
        a4 = math.log(max(up_d, eps) / max(dn_d, eps))
    else:
        a4 = float("nan")
    return {"A1_vol_ratio": a1, "A2_dist_ratio": a2, "A3_skew": a3, "A4_centroid_ratio": a4}


# ============================================================================
# 三种窗口的 profile 生成
# ============================================================================


def sample_hourly_events(bars_5m: pd.DataFrame) -> pd.DataFrame:
    """从 5m bar 中挑出每个整点的 close（作为 1h 时刻）。

    使用 pd.Timedelta.total_seconds() 判断 minute == 0 的 bar。
    """
    df = bars_5m.copy()
    df["hour_flag"] = df["datetime"].dt.minute == 0
    hourly = df[df["hour_flag"]].copy()
    return hourly.reset_index(drop=True)


def build_w1_profile(bars_5m: pd.DataFrame, event_date, tick: float) -> Profile | None:
    """W1 · 前一交易日 profile。"""
    dates = sorted(bars_5m["date"].unique())
    if event_date not in dates:
        return None
    idx = dates.index(event_date)
    if idx == 0:
        return None
    prev_date = dates[idx - 1]
    day_bars = bars_5m[bars_5m["date"] == prev_date]
    return build_profile(day_bars, tick)


def build_w2_profile(bars_5m: pd.DataFrame, event_date, tick: float) -> Profile | None:
    """W2 · 前 5 个交易日 profile。"""
    dates = sorted(bars_5m["date"].unique())
    if event_date not in dates:
        return None
    idx = dates.index(event_date)
    if idx < 5:
        return None
    week_dates = dates[idx - 5 : idx]
    week_bars = bars_5m[bars_5m["date"].isin(week_dates)]
    return build_profile(week_bars, tick)


def build_w3_profile(
    bars_5m: pd.DataFrame, event_idx: int, tick: float, k: int = ROLLING_BARS_5M
) -> Profile | None:
    """W3 · 截止到事件时刻的 rolling K 根 5m bar profile。

    event_idx 指向 hourly event 在原始 5m 序列的位置；rolling window 取
    event_idx-k .. event_idx-1（严格不含 event_idx 自身，避免 leakage）。
    """
    lo = event_idx - k
    if lo < 0:
        return None
    window = bars_5m.iloc[lo:event_idx]
    return build_profile(window, tick)


# ============================================================================
# Per-symbol 主流程
# ============================================================================


def process_symbol(sector: str, symbol: str) -> pd.DataFrame:
    """输出 per-event 长表：event_time × window × metric × horizon × ret_norm。

    返回 DataFrame 列：
    - sector / symbol / contract / event_time
    - window (W1/W2/W3)
    - A1_vol_ratio / A2_dist_ratio / A3_skew / A4_centroid_ratio
    - ret_1h / ret_2h / ret_4h / ret_8h（对数收益）
    """
    print(f"[{symbol}] loading …", flush=True)
    bars = load_5m(symbol)
    prefix = parse_prefix(symbol)
    tick = TICK_SIZE.get(prefix)
    if tick is None:
        raise KeyError(f"missing tick_size for {prefix}")

    # 索引 5m bar 的时间点
    dt_to_idx = {row.datetime: i for i, row in bars.iterrows()}

    hourly = sample_hourly_events(bars)
    hourly = hourly.rename(columns={"close": "close_t"})
    print(f"[{symbol}] 5m rows={len(bars)}, hourly events={len(hourly)}", flush=True)

    records: list[dict] = []
    for _, row in hourly.iterrows():
        event_time = row["datetime"]
        event_date = row["date"]
        event_idx = dt_to_idx.get(event_time)
        if event_idx is None:
            continue
        close_t = float(row["close_t"])

        # 未来收益（对数收益）
        rets: dict[str, float] = {}
        for h in FUTURE_HORIZONS_HOURS:
            future_idx = event_idx + h * 12  # 12 根 5m = 1h
            if future_idx >= len(bars):
                rets[f"ret_{h}h"] = float("nan")
            else:
                close_fut = float(bars.iloc[future_idx]["close"])
                rets[f"ret_{h}h"] = math.log(close_fut / close_t) if close_t > 0 else float("nan")

        # 三种窗口 profile
        for win_name, p in [
            ("W1", build_w1_profile(bars, event_date, tick)),
            ("W2", build_w2_profile(bars, event_date, tick)),
            ("W3", build_w3_profile(bars, event_idx, tick)),
        ]:
            if p is None:
                continue
            metrics = compute_asymmetry(p, tick)
            records.append(
                {
                    "sector": sector,
                    "symbol": symbol,
                    "contract": symbol,
                    "event_time": event_time,
                    "window": win_name,
                    "close_t": close_t,
                    **metrics,
                    **rets,
                }
            )
    df = pd.DataFrame.from_records(records)
    print(f"[{symbol}] events × windows = {len(df)}", flush=True)
    return df


# ============================================================================
# IC 分析与 bootstrap
# ============================================================================

METRIC_COLS = ["A1_vol_ratio", "A2_dist_ratio", "A3_skew", "A4_centroid_ratio"]
RET_COLS = [f"ret_{h}h" for h in FUTURE_HORIZONS_HOURS]


def spearman_ic(x: np.ndarray, y: np.ndarray) -> float:
    """带 NaN 剔除的 Spearman rank correlation。"""
    mask = ~(np.isnan(x) | np.isnan(y))
    if mask.sum() < 30:
        return float("nan")
    r, _ = stats.spearmanr(x[mask], y[mask])
    return float(r)


def cluster_bootstrap_ic(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    cluster_col: str = "contract",
    n_boot: int = BOOTSTRAP_N,
    rng: np.random.Generator | None = None,
) -> tuple[float, float, float, float]:
    """按 cluster_col 重抽样计算 IC 的 95% CI 与双侧 p-value（H0: IC=0）。

    优化：预先对每个 cluster 提取 (x, y) numpy 数组并 dropna；bootstrap 时
    只用 np.concatenate 拼接对应索引的数组，然后一次 spearmanr，避免每次
    重建 DataFrame。返回 (obs_ic, ci_lo, ci_hi, p_two_sided)。
    """
    if rng is None:
        rng = np.random.default_rng(RNG_SEED)
    # 预先按 cluster 分组，缓存 numpy 数组
    cluster_arrays: list[tuple[np.ndarray, np.ndarray]] = []
    for _, sub in df.groupby(cluster_col, sort=False):
        x = sub[x_col].to_numpy()
        y = sub[y_col].to_numpy()
        mask = ~(np.isnan(x) | np.isnan(y))
        if mask.sum() == 0:
            continue
        cluster_arrays.append((x[mask], y[mask]))
    n_clusters = len(cluster_arrays)
    if n_clusters < 2:
        return (spearman_ic(df[x_col].to_numpy(), df[y_col].to_numpy()), float("nan"), float("nan"), float("nan"))

    # 观测 IC
    all_x = np.concatenate([a for a, _ in cluster_arrays])
    all_y = np.concatenate([b for _, b in cluster_arrays])
    if len(all_x) < 30:
        return float("nan"), float("nan"), float("nan"), float("nan")
    obs_r, _ = stats.spearmanr(all_x, all_y)
    obs = float(obs_r)

    # bootstrap
    boot_ics = np.empty(n_boot, dtype=np.float64)
    idx_choices = rng.integers(0, n_clusters, size=(n_boot, n_clusters))
    for i in range(n_boot):
        picked = idx_choices[i]
        xs = np.concatenate([cluster_arrays[j][0] for j in picked])
        ys = np.concatenate([cluster_arrays[j][1] for j in picked])
        if len(xs) < 30:
            boot_ics[i] = np.nan
            continue
        r, _ = stats.spearmanr(xs, ys)
        boot_ics[i] = r if not (r is None or (isinstance(r, float) and math.isnan(r))) else np.nan
    valid = boot_ics[~np.isnan(boot_ics)]
    if len(valid) < 10:
        return obs, float("nan"), float("nan"), float("nan")
    ci_lo, ci_hi = np.percentile(valid, [2.5, 97.5])
    p_gt = float(np.mean(valid > 0))
    p_lt = float(np.mean(valid < 0))
    p_two = 2.0 * min(p_gt, p_lt)
    return obs, float(ci_lo), float(ci_hi), p_two


def bonferroni_reject(p_values: pd.Series, alpha: float = 0.05) -> pd.Series:
    """按整个 family（当前 p_values 的长度）做 Bonferroni 校正。"""
    return p_values < (alpha / len(p_values))


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    long_path = OUT_DIR / "long_events.csv"
    # 1. Per-symbol 主流程（若 long_events.csv 已存在则复用，加快迭代）
    if long_path.exists():
        print(f"Reusing existing long table: {long_path}", flush=True)
        long_df = pd.read_csv(long_path)
        long_df["event_time"] = pd.to_datetime(long_df["event_time"])
    else:
        per_symbol_dfs: list[pd.DataFrame] = []
        for sector, symbol in SYMBOLS:
            try:
                df = process_symbol(sector, symbol)
                per_symbol_dfs.append(df)
            except FileNotFoundError as exc:
                print(f"[{symbol}] SKIP: {exc}", flush=True)
        if not per_symbol_dfs:
            print("No data loaded — abort.")
            return
        long_df = pd.concat(per_symbol_dfs, ignore_index=True)
        long_df.to_csv(long_path, index=False)
        print(f"\nLong table written: {long_path} rows={len(long_df)}", flush=True)

    # 2. 逐 (window, metric, horizon) 计算 pooled IC + cluster bootstrap
    print("\n=== Pooled IC (cluster bootstrap by contract) ===", flush=True)
    rows: list[dict] = []
    for win in ["W1", "W2", "W3"]:
        sub = long_df[long_df["window"] == win]
        for metric in METRIC_COLS:
            for ret_col in RET_COLS:
                obs, ci_lo, ci_hi, p_val = cluster_bootstrap_ic(sub, metric, ret_col)
                rows.append(
                    {
                        "window": win,
                        "metric": metric,
                        "horizon": ret_col,
                        "n": int(sub[[metric, ret_col]].dropna().shape[0]),
                        "ic": obs,
                        "ci_lo": ci_lo,
                        "ci_hi": ci_hi,
                        "p_two": p_val,
                    }
                )
    pooled_df = pd.DataFrame(rows)
    # Bonferroni 校正 · family = 3 × 4 × 4 = 48
    pooled_df["bonf_reject_005"] = pooled_df["p_two"] < (0.05 / len(pooled_df))
    pooled_path = OUT_DIR / "pooled_ic.csv"
    pooled_df.to_csv(pooled_path, index=False)
    print(pooled_df.to_string(index=False))
    print(f"\nPooled IC written: {pooled_path}")

    # 3. Per-symbol IC（简单 Spearman，不做 bootstrap）
    print("\n=== Per-symbol IC ===", flush=True)
    per_rows: list[dict] = []
    for (win, symbol), sub in long_df.groupby(["window", "symbol"]):
        for metric in METRIC_COLS:
            for ret_col in RET_COLS:
                ic = spearman_ic(sub[metric].to_numpy(), sub[ret_col].to_numpy())
                per_rows.append(
                    {
                        "window": win,
                        "symbol": symbol,
                        "metric": metric,
                        "horizon": ret_col,
                        "n": int(sub[[metric, ret_col]].dropna().shape[0]),
                        "ic": ic,
                    }
                )
    per_df = pd.DataFrame(per_rows)
    per_path = OUT_DIR / "per_symbol_ic.csv"
    per_df.to_csv(per_path, index=False)
    print(f"Per-symbol IC written: {per_path} rows={len(per_df)}")

    # 4. 跨品种一致性（sign agreement）
    print("\n=== Cross-symbol consistency ===", flush=True)
    consistency_rows: list[dict] = []
    for (win, metric, horizon), grp in per_df.groupby(["window", "metric", "horizon"]):
        ics = grp["ic"].dropna()
        n_sym = int(len(ics))
        if n_sym == 0:
            continue
        pooled_row = pooled_df[
            (pooled_df["window"] == win)
            & (pooled_df["metric"] == metric)
            & (pooled_df["horizon"] == horizon)
        ]
        if pooled_row.empty:
            continue
        pooled_ic = float(pooled_row["ic"].iloc[0])
        if math.isnan(pooled_ic) or pooled_ic == 0:
            same_sign = 0
        else:
            same_sign = int((np.sign(ics) == np.sign(pooled_ic)).sum())
        consistency_rows.append(
            {
                "window": win,
                "metric": metric,
                "horizon": horizon,
                "pooled_ic": pooled_ic,
                "n_symbols": n_sym,
                "n_same_sign": same_sign,
                "consistency": same_sign / n_sym if n_sym > 0 else float("nan"),
            }
        )
    cons_df = pd.DataFrame(consistency_rows)
    cons_path = OUT_DIR / "cross_symbol_consistency.csv"
    cons_df.to_csv(cons_path, index=False)
    print(cons_df.to_string(index=False))
    print(f"\nConsistency written: {cons_path}")

    # 5. 组合判据：pooled Bonferroni 显著 & 跨品种 ≥60% 同号
    print("\n=== Gatekeeper decision (阶段 1 判据) ===", flush=True)
    decision = pooled_df.merge(
        cons_df[["window", "metric", "horizon", "consistency", "n_symbols"]],
        on=["window", "metric", "horizon"],
        how="left",
    )
    decision["pass_bonf"] = decision["p_two"] < (0.05 / len(decision))
    decision["pass_consistency_60"] = decision["consistency"] >= 0.6
    decision["gatekeeper_pass"] = decision["pass_bonf"] & decision["pass_consistency_60"]
    dec_path = OUT_DIR / "gatekeeper_decision.csv"
    decision.to_csv(dec_path, index=False)
    passes = decision[decision["gatekeeper_pass"]].copy()
    if passes.empty:
        print("❌ 无任何 (window, metric, horizon) 组合通过 gatekeeper。")
    else:
        print("✅ 通过 gatekeeper 的组合：")
        print(
            passes[
                ["window", "metric", "horizon", "n", "ic", "ci_lo", "ci_hi", "p_two", "consistency"]
            ].to_string(index=False)
        )
    print(f"\nDecision written: {dec_path}")


if __name__ == "__main__":
    main()
