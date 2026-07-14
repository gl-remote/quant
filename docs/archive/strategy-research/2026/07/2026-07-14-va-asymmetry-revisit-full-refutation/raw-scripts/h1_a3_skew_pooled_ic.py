"""
文件级元信息：
- 创建背景：va-asymmetry-revisit 主题 H-1 假设的最小验证脚本——signed
  A3_skew（W3 12h rolling volume-profile 三阶偏度）在 event 后 h∈{1,2,4,8,12}h
  内是否对方向收益有 pooled IC（不做 tier 分层）。原 archive stage1 已跑过 10
  合约 W1/W2/W3 × 4 指标 × 4 horizon 的 pooled IC，因证据混杂被作废；本脚本
  只做单一命题：W3 A3_skew × horizon 是否存在独立方向 alpha。
- 用途：加载 15 个品种（每品种最多 3 个历史合约，扩样）5m bar → hourly 事件 →
  W3 rolling profile → A3_skew → 未来 log return → cluster bootstrap
  pooled IC + per-symbol IC + sign consistency。含 N-0 截断法自检（对 W3
  profile 用 event_idx-1 vs event_idx 两种截断，验证特征值一致 = 无泄漏）。
- 注意事项：临时研究脚本，产物写到
  docs/workbench/va-asymmetry-revisit/outputs/h1/；主题稳定后随 archive
  批次搬走。所有假设符合 theme:va-asymmetry-revisit/hypothesis-inventory.md
  的 H-1 条目。
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

# 15 品种（含 stage1 的 10 + 扩样 5）——每品种取最多 3 个历史合约。
SYMBOL_POOL: dict[str, list[str]] = {
    "SHFE.rb": ["SHFE.rb2510", "SHFE.rb2601", "SHFE.rb2605"],
    "DCE.i": ["DCE.i2501", "DCE.i2509", "DCE.i2601"],
    "SHFE.cu": ["SHFE.cu2501", "SHFE.cu2509", "SHFE.cu2601"],
    "SHFE.al": ["SHFE.al2501", "SHFE.al2509", "SHFE.al2601"],
    "INE.sc": ["INE.sc2506", "INE.sc2509", "INE.sc2512"],
    "CZCE.TA": ["CZCE.TA501", "CZCE.TA509", "CZCE.TA601"],
    "DCE.m": ["DCE.m2509", "DCE.m2601", "DCE.m2605"],
    "DCE.p": ["DCE.p2509", "DCE.p2601", "DCE.p2605"],
    "CZCE.SR": ["CZCE.SR509", "CZCE.SR601", "CZCE.SR605"],
    "CZCE.CF": ["CZCE.CF509", "CZCE.CF601"],
    # 扩样：
    "DCE.y": ["DCE.y2509", "DCE.y2601"],
    "DCE.c": ["DCE.c2509", "DCE.c2601", "DCE.c2605"],
    "SHFE.hc": ["SHFE.hc2510", "SHFE.hc2601"],
    "SHFE.ag": ["SHFE.ag2509", "SHFE.ag2601"],
    "CZCE.RM": ["CZCE.RM509", "CZCE.RM601"],
}

TICK_SIZE: dict[str, float] = {
    "rb": 1.0, "i": 0.5, "cu": 10.0, "al": 5.0, "sc": 0.1,
    "TA": 2.0, "m": 1.0, "p": 2.0, "SR": 1.0, "CF": 5.0,
    "y": 1.0, "c": 1.0, "hc": 1.0, "ag": 1.0, "RM": 1.0,
}

CSV_DIR = Path("/Users/gaolei/Documents/src/quant/project_data/market_data/csv")
OUT_DIR = Path(
    "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/h1"
)
OUT_DIR.mkdir(parents=True, exist_ok=True)

VALUE_AREA_RATIO = 0.70
ROLLING_BARS_5M = 144  # 12h
FUTURE_HORIZONS_HOURS: list[int] = [1, 2, 4, 6, 8, 12]
BOOTSTRAP_N = 2000
RNG_SEED = 20260714


# ============================================================================
# 数据加载
# ============================================================================


def parse_prefix(symbol: str) -> str:
    _, contract = symbol.split(".")
    return "".join(c for c in contract if c.isalpha())


def load_5m(symbol: str) -> pd.DataFrame:
    path = CSV_DIR / f"{symbol}.tqsdk.5m.csv"
    df = pd.read_csv(path)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    df["date"] = df["datetime"].dt.date
    return df


# ============================================================================
# Volume Profile（复用 archive stage1 逻辑，只保留 A3_skew）
# ============================================================================


@dataclass(frozen=True)
class Profile:
    poc: float
    skew: float
    total_vol: float


def build_profile(bars: pd.DataFrame, tick: float) -> Profile | None:
    if len(bars) == 0:
        return None
    buckets = (np.round(bars["close"].to_numpy() / tick) * tick).astype(float)
    volumes = bars["volume"].to_numpy(dtype=float)
    profile_df = (
        pd.DataFrame({"price": buckets, "volume": volumes})
        .groupby("price", as_index=False)["volume"].sum()
        .sort_values("price").reset_index(drop=True)
    )
    if profile_df.empty:
        return None
    total = float(profile_df["volume"].sum())
    if total <= 0:
        return None
    prices = profile_df["price"].to_numpy()
    vols = profile_df["volume"].to_numpy()
    max_vol = vols.max()
    tied_idx = np.where(vols == max_vol)[0]
    last_close = float(bars["close"].iloc[-1])
    poc_idx = tied_idx[np.argmin(np.abs(prices[tied_idx] - last_close))]
    poc = float(prices[poc_idx])

    mean = float(np.average(prices, weights=vols))
    var = float(np.average((prices - mean) ** 2, weights=vols))
    std = math.sqrt(var) if var > 0 else 0.0
    skew = float(np.average(((prices - mean) / std) ** 3, weights=vols)) if std > 0 else 0.0
    return Profile(poc=poc, skew=skew, total_vol=total)


def build_w3_profile(
    bars_5m: pd.DataFrame, event_idx: int, tick: float, k: int = ROLLING_BARS_5M
) -> Profile | None:
    """W3 · 严格截止到 event_idx-1 的 rolling K 根 5m bar profile。"""
    lo = event_idx - k
    if lo < 0:
        return None
    window = bars_5m.iloc[lo:event_idx]  # 不含 event_idx 自身 = 无泄漏
    return build_profile(window, tick)


def sample_hourly_events(bars_5m: pd.DataFrame) -> pd.DataFrame:
    df = bars_5m.copy()
    return df[df["datetime"].dt.minute == 0].reset_index(drop=True)


# ============================================================================
# 截断法自检 (N-0)
# ============================================================================


def n0_truncation_selfcheck(bars: pd.DataFrame, tick: float, n_probes: int = 30) -> dict:
    """对随机选择的 event_idx，验证 W3 profile 使用完整 5m vs 截断到
    event_idx 前的 5m 两种数据，A3_skew 结果一致。若一致 → 无未来泄漏。
    """
    rng = np.random.default_rng(RNG_SEED)
    n = len(bars)
    valid_idx = [i for i in range(ROLLING_BARS_5M + 1, n) if i % 12 == 0]
    if len(valid_idx) < n_probes:
        return {"n_probed": 0, "n_agree": 0, "max_abs_diff": float("nan")}
    probes = rng.choice(valid_idx, size=n_probes, replace=False)
    diffs = []
    for eidx in probes:
        p_full = build_w3_profile(bars, eidx, tick)
        p_trunc = build_w3_profile(bars.iloc[:eidx].reset_index(drop=True), eidx, tick)
        if p_full is None or p_trunc is None:
            continue
        diffs.append(abs(p_full.skew - p_trunc.skew))
    diffs_arr = np.array(diffs)
    max_diff = float(diffs_arr.max()) if len(diffs_arr) > 0 else float("nan")
    n_agree = int((diffs_arr < 1e-9).sum())
    return {"n_probed": len(diffs_arr), "n_agree": n_agree, "max_abs_diff": max_diff}


# ============================================================================
# Per-contract 主流程
# ============================================================================


def process_contract(sector: str, symbol: str) -> pd.DataFrame | None:
    try:
        bars = load_5m(symbol)
    except FileNotFoundError:
        print(f"[{symbol}] SKIP: file not found", flush=True)
        return None
    prefix = parse_prefix(symbol)
    tick = TICK_SIZE.get(prefix)
    if tick is None:
        print(f"[{symbol}] SKIP: missing tick_size for {prefix}", flush=True)
        return None

    dt_to_idx = {row.datetime: i for i, row in bars.iterrows()}
    hourly = sample_hourly_events(bars)
    hourly = hourly.rename(columns={"close": "close_t"})
    print(f"[{symbol}] 5m rows={len(bars)}, hourly events={len(hourly)}", flush=True)

    records: list[dict] = []
    for _, row in hourly.iterrows():
        event_time = row["datetime"]
        event_idx = dt_to_idx.get(event_time)
        if event_idx is None:
            continue
        close_t = float(row["close_t"])
        p = build_w3_profile(bars, event_idx, tick)
        if p is None:
            continue

        rec = {
            "sector": sector,
            "symbol": symbol,
            "contract": symbol,
            "event_time": event_time,
            "event_date": row["date"],
            "close_t": close_t,
            "A3_skew": p.skew,
            "poc": p.poc,
        }
        for h in FUTURE_HORIZONS_HOURS:
            future_idx = event_idx + h * 12
            if future_idx >= len(bars):
                rec[f"ret_{h}h"] = float("nan")
            else:
                close_fut = float(bars.iloc[future_idx]["close"])
                rec[f"ret_{h}h"] = math.log(close_fut / close_t) if close_t > 0 else float("nan")
        records.append(rec)

    df = pd.DataFrame.from_records(records)
    print(f"[{symbol}] events with A3_skew = {len(df)}", flush=True)
    return df


# ============================================================================
# IC 分析
# ============================================================================

RET_COLS = [f"ret_{h}h" for h in FUTURE_HORIZONS_HOURS]


def spearman_ic(x: np.ndarray, y: np.ndarray) -> float:
    mask = ~(np.isnan(x) | np.isnan(y))
    if mask.sum() < 30:
        return float("nan")
    r, _ = stats.spearmanr(x[mask], y[mask])
    return float(r)


def cluster_bootstrap_ic(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    cluster_col: str,
    n_boot: int = BOOTSTRAP_N,
    rng: np.random.Generator | None = None,
) -> tuple[float, float, float, float, int]:
    if rng is None:
        rng = np.random.default_rng(RNG_SEED)
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
        return float("nan"), float("nan"), float("nan"), float("nan"), 0

    all_x = np.concatenate([a for a, _ in cluster_arrays])
    all_y = np.concatenate([b for _, b in cluster_arrays])
    n_obs = len(all_x)
    if n_obs < 30:
        return float("nan"), float("nan"), float("nan"), float("nan"), n_obs
    obs_r, _ = stats.spearmanr(all_x, all_y)
    obs = float(obs_r)

    boot_ics = np.empty(n_boot, dtype=np.float64)
    idx_choices = rng.integers(0, n_clusters, size=(n_boot, n_clusters))
    for i in range(n_boot):
        picked = idx_choices[i]
        xs = np.concatenate([cluster_arrays[j][0] for j in picked])
        ys = np.concatenate([cluster_arrays[j][1] for j in picked])
        r, _ = stats.spearmanr(xs, ys)
        boot_ics[i] = r if r is not None and not math.isnan(r) else np.nan
    valid = boot_ics[~np.isnan(boot_ics)]
    if len(valid) < 10:
        return obs, float("nan"), float("nan"), float("nan"), n_obs
    ci_lo, ci_hi = np.percentile(valid, [2.5, 97.5])
    p_gt = float(np.mean(valid > 0))
    p_lt = float(np.mean(valid < 0))
    p_two = 2.0 * min(p_gt, p_lt)
    return obs, float(ci_lo), float(ci_hi), p_two, n_obs


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    long_path = OUT_DIR / "h1_long_events.csv"
    n0_path = OUT_DIR / "h1_n0_selfcheck.csv"

    if long_path.exists():
        print(f"Reusing existing long table: {long_path}", flush=True)
        long_df = pd.read_csv(long_path)
        long_df["event_time"] = pd.to_datetime(long_df["event_time"])
        long_df["event_date"] = pd.to_datetime(long_df["event_date"]).dt.date
    else:
        # N-0 截断法自检：对每个 sector 抽 1 合约 30 个 event 做校验
        n0_rows: list[dict] = []
        per_dfs: list[pd.DataFrame] = []
        for sector, contracts in SYMBOL_POOL.items():
            first = contracts[0]
            prefix = parse_prefix(first)
            tick = TICK_SIZE.get(prefix)
            if tick is not None:
                try:
                    b = load_5m(first)
                    res = n0_truncation_selfcheck(b, tick)
                    n0_rows.append({"sector": sector, "symbol": first, **res})
                    print(
                        f"[N-0][{first}] probed={res['n_probed']} agree={res['n_agree']} "
                        f"max_abs_diff={res['max_abs_diff']:.2e}",
                        flush=True,
                    )
                except FileNotFoundError:
                    pass
            for c in contracts:
                df = process_contract(sector, c)
                if df is not None and len(df) > 0:
                    per_dfs.append(df)

        if n0_rows:
            n0_df = pd.DataFrame(n0_rows)
            n0_df.to_csv(n0_path, index=False)
            print(f"\nN-0 self-check written: {n0_path}")
            # 硬约束：全部通过（max_abs_diff < 1e-9）才继续
            worst = float(n0_df["max_abs_diff"].max())
            if worst > 1e-9:
                print(f"❌ N-0 self-check failed: max_abs_diff={worst:.2e} — abort.")
                return
            print(f"✅ N-0 self-check passed (max_abs_diff={worst:.2e})")

        if not per_dfs:
            print("No data loaded — abort.")
            return
        long_df = pd.concat(per_dfs, ignore_index=True)
        long_df.to_csv(long_path, index=False)
        print(f"\nLong table written: {long_path} rows={len(long_df)}", flush=True)

    # === 1. Pooled IC (cluster by contract) ===
    print("\n=== Pooled IC (cluster bootstrap by contract) ===", flush=True)
    rows = []
    for ret_col in RET_COLS:
        obs, ci_lo, ci_hi, p_val, n_obs = cluster_bootstrap_ic(
            long_df, "A3_skew", ret_col, "contract"
        )
        rows.append({
            "cluster": "contract",
            "horizon": ret_col,
            "n": n_obs,
            "ic": obs,
            "ci_lo": ci_lo,
            "ci_hi": ci_hi,
            "p_two": p_val,
        })

    # === 2. Pooled IC (cluster by (contract, event_date)) — N-1 严格口径 ===
    long_df["ce_key"] = long_df["contract"].astype(str) + "|" + long_df["event_date"].astype(str)
    print("\n=== Pooled IC (cluster by (contract, event_date)) ===", flush=True)
    for ret_col in RET_COLS:
        obs, ci_lo, ci_hi, p_val, n_obs = cluster_bootstrap_ic(
            long_df, "A3_skew", ret_col, "ce_key"
        )
        rows.append({
            "cluster": "contract_date",
            "horizon": ret_col,
            "n": n_obs,
            "ic": obs,
            "ci_lo": ci_lo,
            "ci_hi": ci_hi,
            "p_two": p_val,
        })
    pooled_df = pd.DataFrame(rows)
    pooled_df["bonf_reject_005"] = pooled_df["p_two"] < (0.05 / len(pooled_df))
    pooled_df.to_csv(OUT_DIR / "h1_pooled_ic.csv", index=False)
    print(pooled_df.to_string(index=False))

    # === 3. Per-symbol IC (sign consistency) ===
    print("\n=== Per-symbol IC ===", flush=True)
    per_rows = []
    for symbol, sub in long_df.groupby("symbol"):
        for ret_col in RET_COLS:
            ic = spearman_ic(sub["A3_skew"].to_numpy(), sub[ret_col].to_numpy())
            per_rows.append({
                "symbol": symbol,
                "horizon": ret_col,
                "n": int(sub[["A3_skew", ret_col]].dropna().shape[0]),
                "ic": ic,
            })
    per_df = pd.DataFrame(per_rows)
    per_df.to_csv(OUT_DIR / "h1_per_symbol_ic.csv", index=False)

    # === 4. Sign consistency vs pooled ===
    print("\n=== Cross-symbol sign consistency ===", flush=True)
    cons_rows = []
    for ret_col in RET_COLS:
        pooled_ic = float(
            pooled_df[
                (pooled_df["cluster"] == "contract_date")
                & (pooled_df["horizon"] == ret_col)
            ]["ic"].iloc[0]
        )
        sub = per_df[per_df["horizon"] == ret_col].dropna(subset=["ic"])
        n_sym = int(len(sub))
        if n_sym == 0 or math.isnan(pooled_ic) or pooled_ic == 0:
            same = 0
        else:
            same = int((np.sign(sub["ic"]) == np.sign(pooled_ic)).sum())
        cons_rows.append({
            "horizon": ret_col,
            "pooled_ic": pooled_ic,
            "n_symbols": n_sym,
            "n_same_sign": same,
            "consistency": (same / n_sym) if n_sym > 0 else float("nan"),
        })
    cons_df = pd.DataFrame(cons_rows)
    cons_df.to_csv(OUT_DIR / "h1_sign_consistency.csv", index=False)
    print(cons_df.to_string(index=False))

    print(f"\nAll outputs in: {OUT_DIR}")


if __name__ == "__main__":
    main()
