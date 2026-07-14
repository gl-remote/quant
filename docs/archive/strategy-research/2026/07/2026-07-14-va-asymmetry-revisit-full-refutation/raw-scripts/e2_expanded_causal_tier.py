"""
文件级元信息：
- 创建背景：用户对样本量表示时间预算不足，本次扩样重跑二轮 causal tier 分析。
  合约池从 40 → 145（3.6×），覆盖 2023-06 → 2026-05 约 3 年、20 品种（新增
  CZCE.FG/MA/OI、DCE.cs、SHFE.au 5 品种）。
- 用途：一次性完成扩样版 (1) 事件长表（含 A3_skew）+ N-0 截断法自检、
  (2) causal intraday atr/trend 特征、(3) per-contract rolling rank 240 events、
  (4) 6-tier 分类 + horizon 全景、(5) L_seg2 walk-forward 3-fold + LGO + 品种
  保留率 + hour-of-day 稳健、(6) 实用性能估算。产物在 outputs/expand/。
- 注意事项：临时研究脚本。运行时间预计 5-15 分钟。若 fold 0 反向仍存在
  → 制度依赖判定；若 fold 0 也过 → 升级为工程化候选。
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
from h1_a3_skew_pooled_ic import (  # noqa: E402
    ROLLING_BARS_5M, TICK_SIZE, build_w3_profile, parse_prefix, sample_hourly_events,
)

CSV_DIR = Path("/Users/gaolei/Documents/src/quant/project_data/market_data/csv")
OUT_DIR = Path(
    "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/expand"
)
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 20 品种 · 全部 145 合约
POOL: dict[str, list[str]] = {}


def _discover_pool() -> None:
    for f in CSV_DIR.glob("*.tqsdk.5m.csv"):
        stem = f.name.replace(".tqsdk.5m.csv", "")  # e.g. SHFE.rb2601
        exch, con = stem.split(".", 1)
        prefix = "".join(c for c in con if c.isalpha())
        sec_key = f"{exch}.{prefix}"
        POOL.setdefault(sec_key, []).append(stem)


_discover_pool()

# 补齐可能缺的 tick_size
for prefix in ["FG", "MA", "OI", "cs", "au"]:
    if prefix not in TICK_SIZE:
        pass  # spec 已有

# 从 contract_specs 拿 tick
def get_tick(symbol: str) -> float | None:
    spec = CONTRACT_SPECS.get_symbol(symbol)
    return spec.tick if spec else None


ATR_WIN_5M = 96
TREND_WIN_5M = 96
RANK_WIN_EVENTS = 240
HORIZONS = {2: 24, 4: 48, 6: 72, 8: 96, 10: 120, 12: 144}
RNG_SEED = 20260714
BOOT_N = 2000


# ============================================================================
# Step 1: 事件长表 + causal intraday features
# ============================================================================


def process_contract(sector: str, symbol: str) -> pd.DataFrame | None:
    path = CSV_DIR / f"{symbol}.tqsdk.5m.csv"
    if not path.exists():
        return None
    tick = get_tick(symbol)
    if tick is None:
        return None
    raw = pd.read_csv(path)
    raw["datetime"] = pd.to_datetime(raw["datetime"])
    raw = raw.sort_values("datetime").reset_index(drop=True)
    raw["date"] = raw["datetime"].dt.date

    # Enrich with intraday features
    bars = raw.copy()
    bars["log_close"] = np.log(bars["close"])
    bars["ret_5m"] = bars["log_close"].diff()
    bars["abs_ret_5m"] = bars["ret_5m"].abs()
    bars["atr_intra"] = (
        bars["abs_ret_5m"].rolling(ATR_WIN_5M, min_periods=48).mean().shift(1)
    )
    bars["trend_intra"] = (
        bars["ret_5m"].rolling(TREND_WIN_5M, min_periods=48).sum().shift(1)
    )

    dt_to_idx = {dt: i for i, dt in enumerate(bars["datetime"])}
    hourly = sample_hourly_events(bars)

    records: list[dict] = []
    for _, row in hourly.iterrows():
        event_time = row["datetime"]
        event_idx = dt_to_idx.get(event_time)
        if event_idx is None:
            continue
        close_t = float(row["close"])

        p = build_w3_profile(bars, event_idx, tick)
        if p is None:
            continue
        atr_val = bars["atr_intra"].iloc[event_idx]
        trend_val = bars["trend_intra"].iloc[event_idx]
        if pd.isna(atr_val) or pd.isna(trend_val):
            continue

        rec = {
            "sector": sector, "symbol": symbol, "contract": symbol,
            "event_time": event_time, "event_date": row["date"],
            "close_t": close_t,
            "A3_skew": p.skew, "atr_intra": float(atr_val), "trend_intra": float(trend_val),
        }
        for h_hr, n5m in HORIZONS.items():
            fi = event_idx + n5m
            if fi >= len(bars):
                rec[f"ret_{h_hr}h"] = float("nan")
            else:
                cf = float(bars.iloc[fi]["close"])
                rec[f"ret_{h_hr}h"] = math.log(cf / close_t) if close_t > 0 else float("nan")
        records.append(rec)
    return pd.DataFrame(records)


def build_long_table() -> pd.DataFrame:
    long_path = OUT_DIR / "long_events.csv"
    if long_path.exists():
        print(f"Reusing {long_path}", flush=True)
        df = pd.read_csv(long_path)
        df["event_time"] = pd.to_datetime(df["event_time"])
        df["event_date"] = pd.to_datetime(df["event_date"]).dt.date
        return df
    parts: list[pd.DataFrame] = []
    for sec, contracts in sorted(POOL.items()):
        for c in contracts:
            df = process_contract(sec, c)
            if df is not None and len(df) > 0:
                parts.append(df)
                print(f"  [{c}] events={len(df)}", flush=True)
    long_df = pd.concat(parts, ignore_index=True)
    long_df.to_csv(long_path, index=False)
    print(f"\nLong table saved: {long_path} rows={len(long_df)}", flush=True)
    return long_df


# ============================================================================
# Step 2: rank + tier
# ============================================================================


def add_rank(df: pd.DataFrame, col: str, window: int) -> pd.DataFrame:
    df = df.sort_values(["contract", "event_time"]).reset_index(drop=True)
    def _r(sub: pd.DataFrame) -> pd.Series:
        s = sub[col].reset_index(drop=True)
        return s.rolling(window, min_periods=60).apply(
            lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False
        )
    df[f"{col}_rank"] = df.groupby("contract", sort=False, group_keys=False).apply(_r).to_numpy()
    return df


def classify_tier(rs: float, ra: float, rt: float) -> str:
    if any(math.isnan(v) for v in (rs, ra, rt)):
        return "none"
    if 0.70 <= rs <= 0.91 and ra <= 0.67 and rt >= 0.75:
        return "L_seg3_lowmid_up"
    if 0.81 <= rs <= 1.0 and ra > 0.67 and rt >= 0.75:
        return "L_seg12_high_up"
    if 0.81 <= rs <= 0.91 and ra <= 0.33 and 0.20 < rt < 0.75:
        return "L_seg2_low_flat"
    if 0 <= rs <= 0.19 and ra > 0.67 and rt <= 0.20:
        return "S_seg12_high_dn"
    if 0.19 < rs <= 0.40 and ra > 0.67 and rt <= 0.20:
        return "S_seg34_high_dn"
    if 0.09 <= rs < 0.19 and 0.33 < ra < 0.67 and rt <= 0.20:
        return "S_seg2_mid_dn"
    return "none"


TIER_DIR = {
    "L_seg3_lowmid_up": +1, "L_seg12_high_up": +1, "L_seg2_low_flat": +1,
    "S_seg12_high_dn": -1, "S_seg34_high_dn": -1, "S_seg2_mid_dn": -1,
}


def one_side_cost_frac(row) -> float:
    spec = CONTRACT_SPECS.get_symbol(row["symbol"])
    if spec is None:
        return np.nan
    price = float(row["close_t"])
    slip = (spec.tick * spec.slip_tick) / price
    try:
        comm = spec.total_commission(price, 1) / (spec.size * price) if spec.size > 0 else 0.0
    except Exception:
        comm = 0.0
    return slip + comm


# ============================================================================
# Step 3: bootstrap
# ============================================================================


def cluster_bootstrap_mean(y: np.ndarray, cluster_id: np.ndarray, n_boot: int = BOOT_N,
                           rng: np.random.Generator | None = None) -> tuple[float, float, float, float, int]:
    if rng is None:
        rng = np.random.default_rng(RNG_SEED)
    mask = ~np.isnan(y)
    y = y[mask]
    cluster_id = cluster_id[mask]
    if len(y) < 30:
        return float("nan"), float("nan"), float("nan"), float("nan"), len(y)
    uniq = np.unique(cluster_id)
    n_c = len(uniq)
    if n_c < 2:
        return float(np.mean(y)), float("nan"), float("nan"), float("nan"), len(y)
    idx_by_c = [np.where(cluster_id == c)[0] for c in uniq]
    obs = float(np.mean(y))
    boot = np.empty(n_boot)
    picks = rng.integers(0, n_c, size=(n_boot, n_c))
    for i in range(n_boot):
        idxs = np.concatenate([idx_by_c[j] for j in picks[i]])
        boot[i] = np.mean(y[idxs])
    lo, hi = np.percentile(boot, [2.5, 97.5])
    p_gt = float(np.mean(boot > 0))
    p_lt = float(np.mean(boot < 0))
    return obs, float(lo), float(hi), 2.0 * min(p_gt, p_lt), int(len(y))


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    print(f"POOL: {len(POOL)} sectors, {sum(len(v) for v in POOL.values())} contracts")
    print(f"Contract specs available: "
          f"{sum(1 for _, contracts in POOL.items() for c in contracts if get_tick(c) is not None)}")

    long_df = build_long_table()
    print(f"\nLoaded: {len(long_df)} events, "
          f"{long_df['contract'].nunique()} contracts, "
          f"{long_df['symbol'].nunique()} symbols")
    print(f"Time span: {long_df['event_time'].min()} → {long_df['event_time'].max()}")

    # Rank + Tier
    print("\n[1/4] Computing per-contract rolling ranks …")
    for col in ["A3_skew", "atr_intra", "trend_intra"]:
        long_df = add_rank(long_df, col, RANK_WIN_EVENTS)
    long_df["tier"] = long_df.apply(
        lambda r: classify_tier(
            r["A3_skew_rank"] if pd.notna(r["A3_skew_rank"]) else float("nan"),
            r["atr_intra_rank"] if pd.notna(r["atr_intra_rank"]) else float("nan"),
            r["trend_intra_rank"] if pd.notna(r["trend_intra_rank"]) else float("nan"),
        ),
        axis=1,
    )
    print(f"Tier distribution:\n{long_df['tier'].value_counts()}")

    long_df["cost_rt"] = 2.0 * long_df.apply(one_side_cost_frac, axis=1)
    long_df["ce_key"] = long_df["contract"].astype(str) + "|" + long_df["event_date"].astype(str)
    long_df["hour"] = long_df["event_time"].dt.hour

    long_df.to_csv(OUT_DIR / "events_with_tier.csv", index=False)

    # Tier × horizon 全景
    print("\n[2/4] Tier × horizon signed pnl …")
    rows = []
    for tier_name, sub in long_df[long_df["tier"] != "none"].groupby("tier"):
        direction = TIER_DIR[tier_name]
        for h_hr in HORIZONS:
            col = f"ret_{h_hr}h"
            y_gross = sub[col].to_numpy() * direction
            y_net = y_gross - sub["cost_rt"].to_numpy()
            for lbl, y in [("gross", y_gross), ("net", y_net)]:
                obs, lo, hi, p, n = cluster_bootstrap_mean(y, sub["ce_key"].to_numpy())
                rows.append({
                    "tier": tier_name, "direction": direction,
                    "horizon": f"ret_{h_hr}h", "cost": lbl,
                    "n_events": n, "mean": obs, "ci_lo": lo, "ci_hi": hi, "p_two": p,
                })
    tier_df = pd.DataFrame(rows)
    tier_df.to_csv(OUT_DIR / "tier_horizon.csv", index=False)
    print(tier_df[tier_df["cost"] == "net"].to_string(index=False))

    # L_seg2 3-fold walk-forward
    print("\n[3/4] L_seg2_low_flat · 3-fold walk-forward + LGO + hour-of-day …")
    l2 = long_df[long_df["tier"] == "L_seg2_low_flat"].sort_values("event_time").reset_index(drop=True)
    print(f"L_seg2 total events (expanded): {len(l2)}")

    fold_rows = []
    n_l2 = len(l2)
    for i, (tr_lo, tr_hi, te_lo, te_hi) in enumerate([
        (0.0, 0.5, 0.5, 0.7),
        (0.0, 0.7, 0.7, 0.85),
        (0.0, 0.85, 0.85, 1.0),
    ]):
        tr = l2.iloc[int(tr_lo * n_l2):int(tr_hi * n_l2)]
        te = l2.iloc[int(te_lo * n_l2):int(te_hi * n_l2)]
        for name, sub in [("train", tr), ("test", te)]:
            for h in ["ret_6h", "ret_8h", "ret_10h", "ret_12h"]:
                y = sub[h].to_numpy() - sub["cost_rt"].to_numpy()
                mu, lo, hi, p, n = cluster_bootstrap_mean(y, sub["ce_key"].to_numpy())
                fold_rows.append({
                    "fold": i, "split": name, "horizon": h,
                    "n": n, "mean_net": mu, "ci_lo": lo, "ci_hi": hi, "p_two": p,
                    "period_start": str(sub["event_time"].min()) if len(sub) > 0 else "",
                    "period_end": str(sub["event_time"].max()) if len(sub) > 0 else "",
                })
    fold_df = pd.DataFrame(fold_rows)
    fold_df.to_csv(OUT_DIR / "l2_folds.csv", index=False)
    print(fold_df.to_string(index=False))

    # Sector LGO
    sector_map = {}
    for sec_key, contracts in POOL.items():
        for c in contracts:
            sector_map[c] = sec_key.split(".")[0] + "_" + "".join(x for x in sec_key.split(".")[1] if x.isalpha())
    l2["sec_key"] = l2["symbol"].map(sector_map)
    print(f"\nL_seg2 sector counts:\n{l2['sec_key'].value_counts()}")

    print("\nLGO (drop 1 sector) · 10h net:")
    lgo_rows = []
    for drop in sorted(l2["sec_key"].dropna().unique()):
        sub = l2[l2["sec_key"] != drop]
        for h in ["ret_8h", "ret_10h"]:
            y = sub[h].to_numpy() - sub["cost_rt"].to_numpy()
            mu, lo, hi, p, n = cluster_bootstrap_mean(y, sub["ce_key"].to_numpy())
            lgo_rows.append({
                "drop_sector": drop, "horizon": h,
                "n": n, "mean_net": mu, "ci_lo": lo, "ci_hi": hi, "p_two": p,
            })
    lgo_df = pd.DataFrame(lgo_rows)
    lgo_df.to_csv(OUT_DIR / "l2_lgo.csv", index=False)
    print(lgo_df.to_string(index=False))
    pass_10h = ((lgo_df["horizon"] == "ret_10h") & (lgo_df["ci_lo"] > 0) & (lgo_df["p_two"] < 0.05)).sum()
    print(f"\nLGO 10h pass: {pass_10h}/{(lgo_df['horizon']=='ret_10h').sum()}")

    # Per-symbol retention
    print("\nL_seg2 · per-symbol retention · 10h net:")
    sym_rows = []
    for sym, sub in l2.groupby("symbol"):
        if len(sub) < 5:
            continue
        for h in ["ret_8h", "ret_10h"]:
            y = sub[h].to_numpy() - sub["cost_rt"].to_numpy()
            mu = float(np.nanmean(y))
            sym_rows.append({"symbol": sym, "horizon": h, "n": len(sub), "mean_net": mu})
    sym_df = pd.DataFrame(sym_rows)
    sym_df.to_csv(OUT_DIR / "l2_symbol.csv", index=False)
    for h in ["ret_8h", "ret_10h"]:
        subh = sym_df[sym_df["horizon"] == h].dropna(subset=["mean_net"])
        pos = (subh["mean_net"] > 0).sum()
        print(f"  {h}: positive syms {pos}/{len(subh)} = {pos/max(len(subh),1):.1%}, "
              f"median={subh['mean_net'].median():.6f}")

    # Full-period + fold-2 performance
    print("\n[4/4] L_seg2 逐笔 net pnl · 年化/夏普/回撤 ·")
    def perf(y: np.ndarray, dt: pd.Series, label: str) -> None:
        df_ = pd.DataFrame({"pnl": y, "date": pd.to_datetime(dt).dt.date})
        daily = df_.groupby("date")["pnl"].sum()
        daily.index = pd.to_datetime(daily.index)
        full_idx = pd.date_range(daily.index.min(), daily.index.max(), freq="B")
        daily = daily.reindex(full_idx, fill_value=0.0)
        ann = daily.mean() * 252
        vol = daily.std() * np.sqrt(252)
        sh = ann / vol if vol > 0 else float("nan")
        dd = (daily.cumsum() - daily.cumsum().cummax()).min()
        hit = float(np.nanmean(y > 0))
        print(f"  [{label}] n={len(y)}, days={len(daily)}, "
              f"ann={ann*100:.2f}%, sharpe={sh:.2f}, DD={dd*100:.2f}%, hit={hit:.1%}")

    for h in ["ret_8h", "ret_10h"]:
        y_full = l2[h].to_numpy() - l2["cost_rt"].to_numpy()
        dt_full = l2["event_time"]
        perf(y_full, dt_full, f"full · {h}")

    # 输出制度分段（按季度）
    print("\nL_seg2 quarterly performance (10h net):")
    l2q = l2.copy()
    l2q["y"] = l2q["ret_10h"] - l2q["cost_rt"]
    l2q["quarter"] = l2q["event_time"].dt.to_period("Q").astype(str)
    q_mean = l2q.groupby("quarter")["y"].agg(["count", "mean", "sum"]).round(6)
    print(q_mean.to_string())
    q_mean.to_csv(OUT_DIR / "l2_quarterly.csv")

    print(f"\nAll outputs: {OUT_DIR}")


if __name__ == "__main__":
    main()
