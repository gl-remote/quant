"""
文件级元信息：
- 创建背景：阶段 2 补充研究 · 探明空头方向。多头主线已通过阶段 2 三门槛
  （CI 排 0 · +25 bps · hit 68.5%），但阶段 1 洞察 F/G 显示 UP 组无独立
  空头信号（"顶厚→跌"对称假设未成立）。本次用扩展 44 合约样本外数据
  重新验证 6 个空头候选组合，判断是否真的不可救药。
- 用途：
    (1) 复用 stage2_oos.py 的事件构建 + rolling rank 逻辑
    (2) 定义 6 个空头候选组合（A-F）
    (3) 每个组合分别在样本内 · 样本外两个数据源上跑 5000 次 cluster
        bootstrap CI · 记录 mean / hit / CI / p_two
    (4) 对通过 CI 排 0 的候选与多头主线做分布形态对比（payoff / skew /
        kurt / top-N% 贡献）
    (5) 输出洞察 M · 空头研究表 · 阶段 2 补充完成
- 注意事项：
    - ret 全部取 -ret_8h（做空视角 · 正值表示空头赚）
    - warmup / rolling rank / dedup 参数继承阶段 2 主线
    - horizon 默认 8h · 组合 F 探索短 horizon（2h/4h）
    - 判据：样本外 CI 排 0 = 通过；否则记录冻结原因
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

CSV_DIR = Path("/Users/gaolei/Documents/src/quant/project_data/market_data/csv")
LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage2"
)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 复用样本外合约清单
OOS_SYMBOLS: dict[str, float] = {
    "SHFE.rb2401": 1.0, "SHFE.rb2405": 1.0, "SHFE.rb2410": 1.0,
    "SHFE.rb2501": 1.0, "SHFE.rb2505": 1.0, "SHFE.rb2510": 1.0,
    "SHFE.rb2605": 1.0, "SHFE.rb2610": 1.0,
    "SHFE.cu2509": 10.0,
    "DCE.m2401": 1.0, "DCE.m2405": 1.0, "DCE.m2409": 1.0,
    "DCE.m2501": 1.0, "DCE.m2505": 1.0, "DCE.m2509": 1.0,
    "DCE.m2603": 1.0, "DCE.m2605": 1.0, "DCE.m2607": 1.0, "DCE.m2609": 1.0,
    "DCE.p2405": 2.0, "DCE.p2409": 2.0, "DCE.p2501": 2.0,
    "DCE.p2505": 2.0, "DCE.p2509": 2.0, "DCE.p2605": 2.0,
    "CZCE.SR401": 1.0, "CZCE.SR405": 1.0, "CZCE.SR409": 1.0,
    "CZCE.SR501": 1.0, "CZCE.SR505": 1.0, "CZCE.SR509": 1.0,
    "CZCE.SR605": 1.0, "CZCE.SR609": 1.0,
    "CZCE.CF509": 5.0,
    "CZCE.TA509": 2.0,
    "DCE.c2603": 1.0, "DCE.c2605": 1.0,
    "DCE.cs2603": 1.0, "DCE.cs2605": 1.0,
    "DCE.y2509": 1.0,
    "SHFE.ag2509": 1.0, "SHFE.al2509": 5.0,
    "INE.sc2509": 0.1, "SHFE.hc2505": 1.0,
}

# 参数
VALUE_AREA_RATIO = 0.70
DEDUP_GAP_HOURS = 8.0
ROLLING_EVENTS = 100
ROLLING_DAYS = 20
WARMUP_DAYS = 20
BOOTSTRAP_N = 5000
RNG_SEED = 20260707


def parse_prefix(symbol: str) -> str:
    _, contract = symbol.split(".")
    return "".join(c for c in contract if c.isalpha())


def load_5m(symbol: str) -> pd.DataFrame:
    path = CSV_DIR / f"{symbol}.tqsdk.5m.csv"
    df = pd.read_csv(path)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    return df


def compute_profile_skew(bars: pd.DataFrame, tick: float) -> float:
    if len(bars) == 0 or bars["volume"].sum() <= 0:
        return np.nan
    buckets = (bars["close"] / tick).round() * tick
    grouped = bars.groupby(buckets)["volume"].sum()
    prices = grouped.index.to_numpy()
    vols = grouped.to_numpy()
    total = vols.sum()
    if total <= 0:
        return np.nan
    w = vols / total
    mean = (prices * w).sum()
    var = ((prices - mean) ** 2 * w).sum()
    if var <= 0:
        return np.nan
    std = np.sqrt(var)
    skew = (((prices - mean) / std) ** 3 * w).sum()
    return skew


def build_events(symbol: str, tick: float, horizons: list[int]) -> pd.DataFrame:
    """构建事件表 · 支持多 horizon"""
    bars = load_5m(symbol)
    bars["date"] = bars["datetime"].dt.date

    hourly_mask = (bars["datetime"].dt.minute == 0) & (bars["datetime"].dt.second == 0)
    hourly_idx = bars.index[hourly_mask].to_list()

    rows = []
    for idx in hourly_idx:
        t = bars.loc[idx, "datetime"]
        close_t = bars.loc[idx, "close"]

        # 各 horizon 未来收益
        horizon_rets = {}
        skip = False
        for h in horizons:
            fut_idx = idx + h * 12
            if fut_idx >= len(bars):
                skip = True
                break
            close_fut = bars.loc[fut_idx, "close"]
            horizon_rets[f"ret_{h}h"] = np.log(close_fut / close_t)
        if skip:
            continue

        current_date = t.date()
        prev_bars = bars[bars["date"] < current_date]
        if len(prev_bars) == 0:
            continue
        prev_date = prev_bars["date"].max()
        w1_bars = prev_bars[prev_bars["date"] == prev_date]
        if len(w1_bars) < 20:
            continue
        skew = compute_profile_skew(w1_bars, tick)
        if np.isnan(skew):
            continue

        # 短期动量（近 5 日 log ret）
        row = {
            "contract": symbol,
            "event_time": t,
            "event_date": current_date,
            "close_t": close_t,
            "A3_skew": skew,
        }
        row.update(horizon_rets)
        rows.append(row)

    return pd.DataFrame(rows)


def build_daily_features(symbol: str) -> pd.DataFrame:
    bars = load_5m(symbol)
    bars["date"] = bars["datetime"].dt.date
    daily = bars.groupby("date").agg(
        high=("high", "max"), low=("low", "min"),
        close=("close", "last"), open=("open", "first"),
    ).reset_index().sort_values("date").reset_index(drop=True)

    prev_close = daily["close"].shift(1)
    tr = np.maximum.reduce([
        (daily["high"] - daily["low"]).to_numpy(),
        (daily["high"] - prev_close).abs().to_numpy(),
        (daily["low"] - prev_close).abs().to_numpy(),
    ])
    daily["daily_tr"] = tr
    daily["daily_atr_10"] = daily["daily_tr"].rolling(10).mean()
    daily["daily_atr_10_bps"] = daily["daily_atr_10"] / daily["close"] * 1e4
    # ATR 变化率（当前 5d 均 vs 前 20d 均）
    daily["daily_atr_5"] = daily["daily_tr"].rolling(5).mean()
    daily["atr_change"] = daily["daily_atr_5"] / daily["daily_atr_10"].shift(1) - 1
    daily["trend_ret_10d"] = np.log(daily["close"] / daily["close"].shift(10)) * 1e4
    # 短期动量（5 日）
    daily["mom_5d"] = np.log(daily["close"] / daily["close"].shift(5)) * 1e4
    return daily[["date", "daily_atr_10_bps", "trend_ret_10d", "mom_5d", "atr_change"]]


def rolling_pct_rank(series: pd.Series, window: int) -> pd.Series:
    def rank_last(x):
        if len(x) < 2:
            return np.nan
        current = x.iloc[-1]
        past = x.iloc[:-1]
        return (past <= current).sum() / len(past)
    return series.rolling(window, min_periods=10).apply(rank_last, raw=False)


def cluster_bootstrap(events: pd.DataFrame, ret_col: str = "short_pnl_bps",
                       n_boot: int = BOOTSTRAP_N, seed: int = RNG_SEED) -> dict:
    rng = np.random.default_rng(seed)
    contracts = events["contract"].unique().tolist()
    per_c = {c: events[events["contract"] == c][ret_col].to_numpy() for c in contracts}
    real_mean = events[ret_col].mean()

    boot_means = np.zeros(n_boot)
    for i in range(n_boot):
        picked = rng.choice(contracts, size=len(contracts), replace=True)
        all_r = np.concatenate([per_c[c] for c in picked])
        boot_means[i] = all_r.mean() if len(all_r) else np.nan
    valid = boot_means[~np.isnan(boot_means)]
    ci_lo = float(np.quantile(valid, 0.025))
    ci_hi = float(np.quantile(valid, 0.975))
    p_two = 2 * min((valid <= 0).mean(), (valid >= 0).mean())
    return {
        "n_events": len(events),
        "n_contracts": len(contracts),
        "real_mean": real_mean,
        "ci_lo_95": ci_lo,
        "ci_hi_95": ci_hi,
        "p_two": p_two,
    }


def prepare_dataset(symbols: dict[str, float], horizons: list[int]) -> pd.DataFrame:
    all_events = []
    for i, (sym, tick) in enumerate(symbols.items()):
        try:
            ev = build_events(sym, tick, horizons)
            daily = build_daily_features(sym)
            ev = ev.merge(daily, left_on="event_date", right_on="date", how="left")
            all_events.append(ev)
        except FileNotFoundError:
            continue
        except Exception as e:
            print(f"  ERR {sym}: {e}")
    df = pd.concat(all_events, ignore_index=True)
    df["event_time"] = pd.to_datetime(df["event_time"])
    df = df.sort_values(["contract", "event_time"]).reset_index(drop=True)

    # Rolling ranks
    df["signed_skew_rank_roll"] = df.groupby("contract")["A3_skew"].transform(
        lambda s: rolling_pct_rank(s, ROLLING_EVENTS))

    for feat_col, roll_col in [
        ("daily_atr_10_bps", "atr_rank_roll"),
        ("trend_ret_10d", "trend_rank_roll"),
        ("mom_5d", "mom5d_rank_roll"),
        ("atr_change", "atr_change_rank_roll"),
    ]:
        seg_list = []
        for c, g in df.groupby("contract"):
            daily = g.drop_duplicates("event_date").sort_values("event_date").copy()
            daily[roll_col] = rolling_pct_rank(daily[feat_col], ROLLING_DAYS)
            seg_list.append(daily[["contract", "event_date", roll_col]])
        seg_map = pd.concat(seg_list, ignore_index=True)
        df = df.merge(seg_map, on=["contract", "event_date"], how="left")

    # Warmup 排除
    keep_mask = np.zeros(len(df), dtype=bool)
    for c in df["contract"].unique():
        idx = df[df["contract"] == c].sort_values("event_time").index
        c_dates = sorted(df.loc[idx, "event_date"].unique())
        if len(c_dates) < WARMUP_DAYS:
            continue
        warmup_end = c_dates[WARMUP_DAYS - 1]
        for i in idx:
            if df.at[i, "event_date"] > warmup_end:
                keep_mask[df.index.get_loc(i)] = True
    df = df[keep_mask].reset_index(drop=True)
    df = df.dropna(subset=["signed_skew_rank_roll", "atr_rank_roll",
                            "trend_rank_roll", "mom5d_rank_roll"])

    # 分组
    df["skew_grp"] = df["signed_skew_rank_roll"].apply(
        lambda r: "DN" if r <= 0.10 else ("UP" if r >= 0.90 else "mid"))
    df["trend_grp"] = df["trend_rank_roll"].apply(
        lambda r: "down" if r <= 0.33 else ("up" if r >= 0.67 else "flat"))
    df["atr10_grp"] = df["atr_rank_roll"].apply(
        lambda r: "low" if r <= 0.5 else "high")
    df["mom5d_grp"] = df["mom5d_rank_roll"].apply(
        lambda r: "down" if r <= 0.33 else ("up" if r >= 0.67 else "flat"))
    df["atr_up_grp"] = df["atr_change_rank_roll"].apply(
        lambda r: "up" if r >= 0.67 else ("down" if r <= 0.33 else "flat")
        if not np.isnan(r) else "flat")

    return df


def eval_combo(df: pd.DataFrame, name: str, mask, ret_col: str = "short_pnl_bps"):
    sub = df[mask].dropna(subset=[ret_col])
    if len(sub) < 20:
        return None
    r = cluster_bootstrap(sub, ret_col=ret_col)
    hit = (sub[ret_col] > 0).mean()
    return {
        "name": name,
        "n_events": r["n_events"],
        "n_contracts": r["n_contracts"],
        "mean": r["real_mean"],
        "hit": hit,
        "ci_lo": r["ci_lo_95"],
        "ci_hi": r["ci_hi_95"],
        "p_two": r["p_two"],
        "pass": r["ci_lo_95"] > 0,
    }


def main() -> None:
    print("=" * 90)
    print("阶段 2 补充 · 空头方向探索 · 6 组合 × 2 样本 × horizons")
    print("=" * 90)

    horizons = [2, 4, 8]

    # 样本外
    print("\n[样本外 44 合约] 构建事件表 ...")
    df_oos = prepare_dataset(OOS_SYMBOLS, horizons)
    print(f"  warmup 后事件数: {len(df_oos)} · 合约数: {df_oos['contract'].nunique()}")

    # 各 horizon 的做空 pnl
    for h in horizons:
        df_oos[f"short_pnl_{h}h_bps"] = -df_oos[f"ret_{h}h"] * 1e4

    combos = [
        # 组合 A · 简单对称（baseline · 已知失败）
        ("A · 简单对称 · UP+跌+低ATR",
         (df_oos["skew_grp"] == "UP") & (df_oos["trend_grp"] == "down") &
         (df_oos["atr10_grp"] == "low")),
        # 组合 B · 波动突增触发
        ("B · UP + 波动上升（无趋势）",
         (df_oos["skew_grp"] == "UP") & (df_oos["atr_up_grp"] == "up")),
        # 组合 C · 反向利用 DN + 平段 + 高 ATR（阶段 1 候选 2 严格版）
        ("C · 反向 DN + 平段 + 高ATR",
         (df_oos["skew_grp"] == "DN") & (df_oos["trend_grp"] == "flat") &
         (df_oos["atr10_grp"] == "high")),
        # 组合 D · 顶厚 + 短期动量转空
        ("D · UP + 短期动量负",
         (df_oos["skew_grp"] == "UP") & (df_oos["mom5d_grp"] == "down")),
        # 组合 E · 崩盘前奏 · 跌段 + 顶厚 + 高ATR
        ("E · UP + 跌段 + 高ATR",
         (df_oos["skew_grp"] == "UP") & (df_oos["trend_grp"] == "down") &
         (df_oos["atr10_grp"] == "high")),
        # 组合 F · 简单 UP（无 filter · baseline）
        ("F · UP 单层（对照）",
         df_oos["skew_grp"] == "UP"),
    ]

    for horizon in horizons:
        ret_col = f"short_pnl_{horizon}h_bps"
        print(f"\n{'='*90}")
        print(f"Horizon = {horizon}h  ·  做空 pnl（正 = 空头赚）")
        print("=" * 90)
        print(f"\n{'组合':45s} {'n':>5s} {'品种':>4s} {'mean':>7s} {'hit':>7s} "
              f"{'CI下':>7s} {'CI上':>7s} {'p':>7s} 判决")
        rows = []
        for name, mask in combos:
            res = eval_combo(df_oos, name, mask, ret_col=ret_col)
            if res is None:
                print(f"{name:45s}  样本不足")
                continue
            judge = "✅" if res["pass"] else "❌"
            print(f"{name:45s} {res['n_events']:>5d} {res['n_contracts']:>4d} "
                  f"{res['mean']:>+7.2f} {res['hit']:>7.1%} "
                  f"{res['ci_lo']:>+7.2f} {res['ci_hi']:>+7.2f} "
                  f"{res['p_two']:>7.4f}  {judge}")
            res["horizon"] = horizon
            rows.append(res)

        if horizon == 8:
            # 主 horizon 保存详情
            summary = pd.DataFrame(rows)
            summary.to_csv(LOG_DIR / "short_scan_8h.csv", index=False)

    # 分布形态对比（若有过关组合 · 用 8h horizon）
    print(f"\n{'='*90}")
    print("分布形态对比 · 空头候选 vs 多头主线（8h · 样本外）")
    print("=" * 90)

    # 多头主线
    df_oos["long_ret_8h_bps"] = df_oos["ret_8h"] * 1e4
    long_mask = ((df_oos["skew_grp"] == "DN") & (df_oos["trend_grp"] == "up") &
                 (df_oos["atr10_grp"] == "low"))
    long_sub = df_oos[long_mask].dropna(subset=["long_ret_8h_bps"])

    def describe_dist(sub, col):
        r = sub[col].to_numpy()
        wins = r[r > 0]
        losses = r[r < 0]
        payoff = (wins.mean() / abs(losses.mean())) if len(losses) > 0 and losses.mean() != 0 else np.nan
        top5 = np.quantile(r, 0.95)
        top5_contrib = r[r >= top5].sum() / r.sum() if r.sum() > 0 else np.nan
        return {
            "n": len(sub),
            "mean": r.mean(),
            "hit": (r > 0).mean(),
            "payoff": payoff,
            "skewness": stats.skew(r),
            "kurtosis": stats.kurtosis(r),
            "p95": np.quantile(r, 0.95),
            "p05": np.quantile(r, 0.05),
        }

    print(f"\n{'档位':30s} {'n':>5s} {'mean':>7s} {'hit':>7s} "
          f"{'payoff':>7s} {'skew':>7s} {'kurt':>7s} {'p95':>7s} {'p05':>7s}")
    d = describe_dist(long_sub, "long_ret_8h_bps")
    print(f"{'多头主线（DN+涨+低ATR）':30s} {d['n']:>5d} {d['mean']:>+7.2f} {d['hit']:>7.1%} "
          f"{d['payoff']:>7.2f} {d['skewness']:>+7.2f} {d['kurtosis']:>+7.2f} "
          f"{d['p95']:>+7.0f} {d['p05']:>+7.0f}")

    for name, mask in combos:
        sub = df_oos[mask].dropna(subset=["short_pnl_8h_bps"])
        if len(sub) < 20:
            continue
        d = describe_dist(sub, "short_pnl_8h_bps")
        short_name = name.split("·")[0].strip()
        print(f"{'空头 '+short_name:30s} {d['n']:>5d} {d['mean']:>+7.2f} {d['hit']:>7.1%} "
              f"{d['payoff']:>7.2f} {d['skewness']:>+7.2f} {d['kurtosis']:>+7.2f} "
              f"{d['p95']:>+7.0f} {d['p05']:>+7.0f}")

    # 保存
    df_oos.to_csv(LOG_DIR / "short_scan_events.csv", index=False)
    print(f"\n输出:")
    print(f"  {LOG_DIR / 'short_scan_events.csv'}")
    print(f"  {LOG_DIR / 'short_scan_8h.csv'}")


if __name__ == "__main__":
    main()
