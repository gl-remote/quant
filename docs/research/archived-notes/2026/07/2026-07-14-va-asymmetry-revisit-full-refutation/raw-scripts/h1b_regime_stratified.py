"""
文件级元信息：
- 创建背景：H-1 pooled IC 判死后，按 quant-research-methodology KF-23 规矩
  下"过拟合"判决前必须先拆制度维度（波动率 / 趋势 / 时段）· 本脚本对
  signed A3_skew 做二阶检验：
  (1) intraday session-ATR 3 档 × signed A3_skew top/bottom 20% 分箱，
      检验 mean(ret_h) 是否显著 ≠ 0（cluster bootstrap CI）；
  (2) 极端 signed A3_skew 事件 → 按 sign 方向"下注"，扣 realistic cost
      后是否有正净收益；
  (3) 顺带跑 hour-of-day / τ_signed（H-11）稳健性作为并行线索。
- 用途：一次性完成 H-1 分层判决 + H-11 并行探索 + 最小策略骨架的可行性诊断。
- 注意事项：临时研究脚本，产物在
  docs/workbench/va-asymmetry-revisit/outputs/h1b/；复用同一份 long
  events 表；成本近似用固定 tick + slip 折算，与工程侧口径一致但简化。
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, "/Users/gaolei/Documents/src/quant/workspace")
from common.contract_specs import CONTRACT_SPECS  # noqa: E402

# ============================================================================
# 配置
# ============================================================================

OUT_DIR = Path(
    "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/h1b"
)
OUT_DIR.mkdir(parents=True, exist_ok=True)

LONG_PATH = Path(
    "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/h1/h1_long_events.csv"
)
CSV_DIR = Path("/Users/gaolei/Documents/src/quant/project_data/market_data/csv")

HORIZONS = [1, 2, 4, 6, 8, 12]
RNG_SEED = 20260714
BOOT_N = 2000

# skew 极端分位阈值（per-contract rank）
EXTREME_Q = 0.20  # top 20% 与 bottom 20%
ATR_QS = [1 / 3, 2 / 3]  # 三分位


# ============================================================================
# 辅助：加载 5m + 计算 hourly intraday-ATR + session hour 等元字段
# ============================================================================


def enrich_events_with_intraday_ctx(long_df: pd.DataFrame) -> pd.DataFrame:
    """给每个 event 补充：
    - session_atr_48（前 48 根 5m 的绝对 close 变化均值，即简化 ATR）
    - hour_of_day（0-23）
    - future_realized_vol_48（未来 48 根 5m 绝对 close 变化均值）
    """
    out_chunks: list[pd.DataFrame] = []
    for symbol, sub in long_df.groupby("symbol", sort=False):
        try:
            path = CSV_DIR / f"{symbol}.tqsdk.5m.csv"
            bars = pd.read_csv(path)
        except FileNotFoundError:
            print(f"[enrich] SKIP {symbol}: file missing", flush=True)
            continue
        bars["datetime"] = pd.to_datetime(bars["datetime"])
        bars = bars.sort_values("datetime").reset_index(drop=True)

        # 5m absolute close change
        bars["abs_dc"] = bars["close"].diff().abs()

        # session_atr_48 = 前 48 根 5m 的 abs_dc 均值
        bars["session_atr_48"] = bars["abs_dc"].rolling(48, min_periods=24).mean().shift(1)

        # 未来 48 根 5m 的 abs_dc 均值（用于比较"事件后波动率"）
        bars["future_absdc_48"] = bars["abs_dc"].shift(-1).rolling(48, min_periods=24).mean()

        dt_to_row = bars.set_index("datetime")
        # merge by event_time
        sub = sub.copy()
        sub["event_time"] = pd.to_datetime(sub["event_time"])
        sub["session_atr_48"] = sub["event_time"].map(dt_to_row["session_atr_48"])
        sub["future_absdc_48"] = sub["event_time"].map(dt_to_row["future_absdc_48"])
        sub["hour"] = sub["event_time"].dt.hour
        out_chunks.append(sub)
    return pd.concat(out_chunks, ignore_index=True)


# ============================================================================
# 分位 / bucket 生成
# ============================================================================


def per_contract_rank(df: pd.DataFrame, col: str) -> pd.Series:
    """按 contract 做百分比 rank ∈ [0,1]。"""
    return df.groupby("contract")[col].transform(lambda s: s.rank(pct=True))


def atr_bucket_per_contract(atr: pd.Series, contracts: pd.Series) -> pd.Series:
    """按 contract 内 ATR 三分位打标：low / mid / high。"""
    def _q(sub: pd.Series) -> pd.Series:
        q1 = sub.quantile(ATR_QS[0])
        q2 = sub.quantile(ATR_QS[1])
        return pd.cut(
            sub, bins=[-np.inf, q1, q2, np.inf], labels=["low", "mid", "high"]
        )
    return atr.groupby(contracts).transform(_q).astype(object)


# ============================================================================
# Cluster bootstrap for mean
# ============================================================================


def cluster_bootstrap_mean(
    y: np.ndarray,
    cluster_id: np.ndarray,
    n_boot: int = BOOT_N,
    rng: np.random.Generator | None = None,
) -> tuple[float, float, float, float, int]:
    """按 cluster 重抽样计算 mean 的 95% CI + 双侧 p（H0: mean=0）。"""
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

    # 预建 cluster → indices
    idx_by_c: list[np.ndarray] = []
    for c in uniq:
        idx_by_c.append(np.where(cluster_id == c)[0])

    obs = float(np.mean(y))
    boot = np.empty(n_boot)
    picks = rng.integers(0, n_c, size=(n_boot, n_c))
    for i in range(n_boot):
        idxs = np.concatenate([idx_by_c[j] for j in picks[i]])
        boot[i] = np.mean(y[idxs])
    lo, hi = np.percentile(boot, [2.5, 97.5])
    p_gt = float(np.mean(boot > 0))
    p_lt = float(np.mean(boot < 0))
    p_two = 2.0 * min(p_gt, p_lt)
    return obs, float(lo), float(hi), float(p_two), int(len(y))


# ============================================================================
# 主流程
# ============================================================================


def main() -> None:
    long_df = pd.read_csv(LONG_PATH)
    long_df["event_time"] = pd.to_datetime(long_df["event_time"])
    long_df["event_date"] = pd.to_datetime(long_df["event_date"]).dt.date
    print(f"Loaded long table: {len(long_df)} rows, "
          f"{long_df['contract'].nunique()} contracts, "
          f"{long_df['symbol'].nunique()} symbols", flush=True)

    long_df = enrich_events_with_intraday_ctx(long_df)
    print(f"After enrichment: {len(long_df)} rows", flush=True)

    # per-contract 分位
    long_df["skew_rank"] = per_contract_rank(long_df, "A3_skew")
    long_df["atr_bucket"] = atr_bucket_per_contract(
        long_df["session_atr_48"], long_df["contract"]
    )

    # 定义 signed_bet：skew_rank ≥ 1-EXTREME_Q → long; ≤ EXTREME_Q → short
    def signed_bet(row) -> float:
        if pd.isna(row["skew_rank"]):
            return np.nan
        if row["skew_rank"] >= (1 - EXTREME_Q):
            return 1.0
        if row["skew_rank"] <= EXTREME_Q:
            return -1.0
        return 0.0

    long_df["bet"] = long_df.apply(signed_bet, axis=1)

    # cluster key
    long_df["ce_key"] = long_df["contract"].astype(str) + "|" + long_df["event_date"].astype(str)

    # =========================================================================
    # ① 分层 mean-return：ATR bucket × bet_side × horizon
    # =========================================================================
    print("\n=== [1] 分层 mean-return ===", flush=True)
    strat_rows = []
    for atr_b in ["low", "mid", "high"]:
        for side_name, side_val in [("long", 1.0), ("short", -1.0)]:
            for h in HORIZONS:
                sub = long_df[(long_df["atr_bucket"] == atr_b) & (long_df["bet"] == side_val)]
                if len(sub) < 50:
                    strat_rows.append({
                        "atr_bucket": atr_b, "side": side_name, "horizon": f"ret_{h}h",
                        "n": len(sub), "mean_ret": float("nan"),
                        "ci_lo": float("nan"), "ci_hi": float("nan"), "p_two": float("nan"),
                    })
                    continue
                # signed return（多头方向：+ret；空头方向：-ret）
                y = sub[f"ret_{h}h"].to_numpy() * side_val
                obs, lo, hi, p, n = cluster_bootstrap_mean(
                    y, sub["ce_key"].to_numpy()
                )
                strat_rows.append({
                    "atr_bucket": atr_b, "side": side_name, "horizon": f"ret_{h}h",
                    "n": n, "mean_ret": obs, "ci_lo": lo, "ci_hi": hi, "p_two": p,
                })
    strat_df = pd.DataFrame(strat_rows)
    strat_df.to_csv(OUT_DIR / "h1b_stratified_mean.csv", index=False)
    print(strat_df.to_string(index=False))

    # =========================================================================
    # ② 极端 signed-skew "无过滤下注" 净收益：mean(sign * ret_h) - cost
    # =========================================================================
    print("\n\n=== [2] Extreme-skew 无过滤下注 净收益 ===", flush=True)
    # realistic single-side cost（bps of price 单位近似 = tick * slip_tick / price + comm/price/size）
    def one_side_cost_bps(row) -> float:
        spec = CONTRACT_SPECS.get_symbol(row["symbol"])
        if spec is None:
            return np.nan
        price = float(row["close_t"])
        # slip cost per contract = size × tick × slip_tick，per unit notional = tick*slip_tick/price
        slip_frac = (spec.tick * spec.slip_tick) / price
        # commission per contract = total_commission(price,1) / (size*price)
        try:
            comm_yuan = spec.total_commission(price, 1)
            comm_frac = comm_yuan / (spec.size * price) if spec.size > 0 else 0.0
        except Exception:
            comm_frac = 0.0
        return slip_frac + comm_frac  # 单边

    long_df["cost_one_side"] = long_df.apply(one_side_cost_bps, axis=1)
    long_df["cost_roundtrip"] = 2.0 * long_df["cost_one_side"]

    extreme = long_df[long_df["bet"] != 0.0].copy()
    print(f"Extreme events: {len(extreme)} (long {(extreme['bet']==1).sum()}, "
          f"short {(extreme['bet']==-1).sum()})", flush=True)

    net_rows = []
    for h in HORIZONS:
        y_gross = extreme[f"ret_{h}h"].to_numpy() * extreme["bet"].to_numpy()
        y_net = y_gross - extreme["cost_roundtrip"].to_numpy()
        for label, y in [("gross", y_gross), ("net", y_net)]:
            obs, lo, hi, p, n = cluster_bootstrap_mean(
                y, extreme["ce_key"].to_numpy()
            )
            net_rows.append({
                "cost": label, "horizon": f"ret_{h}h", "n": n,
                "mean": obs, "ci_lo": lo, "ci_hi": hi, "p_two": p,
            })
    net_df = pd.DataFrame(net_rows)
    net_df.to_csv(OUT_DIR / "h1b_extreme_signed_net.csv", index=False)
    print(net_df.to_string(index=False))

    # =========================================================================
    # ③ 极端-skew × ATR × 长度 决策 grid：找到"净 mean > 0 且 CI 排 0"的格子
    # =========================================================================
    print("\n\n=== [3] Extreme × ATR × horizon 净收益格子 ===", flush=True)
    grid_rows = []
    for atr_b in ["low", "mid", "high"]:
        for side_name, side_val in [("long", 1.0), ("short", -1.0)]:
            for h in HORIZONS:
                sub = long_df[(long_df["atr_bucket"] == atr_b) & (long_df["bet"] == side_val)]
                if len(sub) < 50:
                    grid_rows.append({
                        "atr_bucket": atr_b, "side": side_name, "horizon": f"ret_{h}h",
                        "n": len(sub), "gross_mean": float("nan"), "net_mean": float("nan"),
                        "ci_lo": float("nan"), "ci_hi": float("nan"), "p_two": float("nan"),
                    })
                    continue
                y_gross = sub[f"ret_{h}h"].to_numpy() * side_val
                y_net = y_gross - sub["cost_roundtrip"].to_numpy()
                obs, lo, hi, p, n = cluster_bootstrap_mean(
                    y_net, sub["ce_key"].to_numpy()
                )
                grid_rows.append({
                    "atr_bucket": atr_b, "side": side_name, "horizon": f"ret_{h}h",
                    "n": n, "gross_mean": float(np.nanmean(y_gross)),
                    "net_mean": obs, "ci_lo": lo, "ci_hi": hi, "p_two": p,
                })
    grid_df = pd.DataFrame(grid_rows)
    grid_df["passes"] = (grid_df["ci_lo"] > 0) & (grid_df["p_two"] < 0.05)
    grid_df.to_csv(OUT_DIR / "h1b_grid_decision.csv", index=False)
    print(grid_df.to_string(index=False))
    passes = grid_df[grid_df["passes"]]
    print(f"\n✅ 通过格数：{len(passes)}")
    if not passes.empty:
        print(passes.to_string(index=False))

    # =========================================================================
    # ④ 品种保留率（每个通过格中：多少个 symbol 的 net mean > 0）
    # =========================================================================
    print("\n=== [4] 品种保留率（若有通过格） ===", flush=True)
    retention_rows = []
    for _, r in grid_df.iterrows():
        atr_b, side_name, h_col = r["atr_bucket"], r["side"], r["horizon"]
        side_val = 1.0 if side_name == "long" else -1.0
        sub = long_df[(long_df["atr_bucket"] == atr_b) & (long_df["bet"] == side_val)]
        if len(sub) < 50:
            continue
        n_sym = int(sub["symbol"].nunique())
        pos = 0
        for sym, s2 in sub.groupby("symbol"):
            y = s2[h_col].to_numpy() * side_val - s2["cost_roundtrip"].to_numpy()
            if len(y) >= 30 and np.nanmean(y) > 0:
                pos += 1
        retention_rows.append({
            "atr_bucket": atr_b, "side": side_name, "horizon": h_col,
            "n_sym": n_sym, "n_sym_positive": pos,
            "retention": pos / n_sym if n_sym > 0 else float("nan"),
            "grid_passes": bool(r["passes"]),
        })
    ret_df = pd.DataFrame(retention_rows)
    ret_df.to_csv(OUT_DIR / "h1b_symbol_retention.csv", index=False)
    print(ret_df.to_string(index=False))

    # =========================================================================
    # ⑤ hour-of-day baseline scan（不用 skew）
    # =========================================================================
    print("\n=== [5] Hour-of-day baseline mean(ret_4h) ===", flush=True)
    hod_rows = []
    for h_of_d, sub in long_df.groupby("hour"):
        if len(sub) < 100:
            continue
        obs, lo, hi, p, n = cluster_bootstrap_mean(
            sub["ret_4h"].to_numpy(), sub["ce_key"].to_numpy()
        )
        hod_rows.append({
            "hour": int(h_of_d), "n": n, "mean_ret_4h": obs,
            "ci_lo": lo, "ci_hi": hi, "p_two": p,
        })
    hod_df = pd.DataFrame(hod_rows)
    hod_df.to_csv(OUT_DIR / "h1b_hour_of_day.csv", index=False)
    print(hod_df.to_string(index=False))

    print(f"\nAll outputs in: {OUT_DIR}")


if __name__ == "__main__":
    main()
