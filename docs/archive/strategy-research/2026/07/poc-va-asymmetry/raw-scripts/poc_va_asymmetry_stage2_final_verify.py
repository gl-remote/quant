"""
文件级元信息：
- 创建背景：阶段 2 收尾 · 用新 sweet spot（洞察 N 网格搜索定型的 4 档主线）
  重跑 KF-9 ν_implied 与 KF-7 跨周期护栏，确保严格收尾。
- 用途：
    (1) 多头首选 · 空头首选 · 多头高频 · 空头高频 四档主线
    (2) 每档跑 ν_implied（mean - σ²/2）· cluster CI
    (3) 每档跑跨周期护栏（15m / 30m / 1h / 2h）
    (4) Bonferroni 校正 · 96 组合 family-wise error
- 注意事项：
    - 复用 stage2_grid_search 的事件表（已含 rolling rank · 严格无未来函数）
    - 多头 8h horizon · 空头 4h horizon
    - Bonferroni 阈值 = 0.05 / 96 ≈ 0.00052
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# 复用 grid_search 的准备逻辑
import sys
sys.path.insert(0, "/Users/gaolei/Documents/src/quant/scripts/ai_tmp")
from poc_va_asymmetry_stage2_grid_search import (  # noqa: E402
    prepare_dataset, cluster_bootstrap, OOS_SYMBOLS, load_5m,
    compute_profile_skew, build_daily_features, rolling_pct_rank,
    ROLLING_EVENTS, ROLLING_DAYS, WARMUP_DAYS,
)

LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage2"
)


def eval_signal(df, mask, ret_col, label):
    sub = df[mask].dropna(subset=[ret_col])
    if len(sub) < 20:
        return None
    r = cluster_bootstrap(sub, ret_col=ret_col)
    hit = (sub[ret_col] > 0).mean()
    # ν_implied = mean - σ²/2（σ²/2 = 0.5 * var(ret_col) / 1e4 因为 ret 是 bps）
    ret_arr = sub[ret_col].to_numpy() / 1e4  # 转 log ret
    ito_correction = 0.5 * np.var(ret_arr) * 1e4  # 转回 bps
    nu = r["real_mean"] - ito_correction
    return {
        "label": label,
        "n": r["n_events"],
        "n_contracts": r["n_contracts"],
        "mean_bps": r["real_mean"],
        "ito_bps": ito_correction,
        "nu_bps": nu,
        "hit": hit,
        "ci_lo": r["ci_lo"],
        "ci_hi": r["ci_hi"],
        "p_two": r["p_two"],
        "pass_ci": r["ci_lo"] > 0,
        "pass_bonf": r["p_two"] < 0.05 / 96,
    }


def main():
    print("=" * 100)
    print("阶段 2 收尾 · 新 sweet spot 主线 ν_implied + 跨周期护栏")
    print("=" * 100)

    print("\n[准备数据 · 1h 主时钟] ...")
    df = prepare_dataset()
    print(f"  总事件: {len(df)} · 合约: {df['contract'].nunique()}")

    signals = [
        # 多头 4 档
        ("多头首选 · skew≤0.10 · atr≤0.70 · trend≥0.75",
         "long", 0.10, 0.70, 0.75),
        ("多头高频 · skew≤0.30 · atr≤0.70 · trend≥0.75",
         "long", 0.30, 0.70, 0.75),
        # 空头 4 档
        ("空头首选 · skew≥0.70 · atr>0.80 · trend≤0.20",
         "short", 0.70, 0.80, 0.20),
        ("空头高频 · skew≥0.70 · atr>0.50 · trend≤0.20",
         "short", 0.70, 0.50, 0.20),
    ]

    print("\n" + "=" * 100)
    print("KF-9 ν_implied 验证 · 新 sweet spot 全部主线")
    print("=" * 100)
    print(f"\nBonferroni 阈值 p < 0.05/96 = {0.05/96:.5f}")

    rows = []
    for name, direction, sk, at, tr in signals:
        if direction == "long":
            mask = ((df["signed_skew_rank_roll"] <= sk) &
                    (df["atr_rank_roll"] <= at) &
                    (df["trend_rank_roll"] >= tr))
            ret_col = "ret_8h_bps"
        else:
            mask = ((df["signed_skew_rank_roll"] >= sk) &
                    (df["atr_rank_roll"] > at) &
                    (df["trend_rank_roll"] <= tr))
            ret_col = "short_pnl_4h_bps"
        r = eval_signal(df, mask, ret_col, name)
        if r is None:
            print(f"\n{name}: n<20 跳过")
            continue
        rows.append(r)
        print(f"\n【{name}】")
        print(f"  n={r['n']} · 品种={r['n_contracts']} · hit={r['hit']:.1%}")
        print(f"  mean         = {r['mean_bps']:+.2f} bps")
        print(f"  Itô σ²/2     = {r['ito_bps']:+.2f} bps")
        print(f"  ν_implied    = {r['nu_bps']:+.2f} bps")
        print(f"  95% CI       = [{r['ci_lo']:+.2f}, {r['ci_hi']:+.2f}]")
        print(f"  p_two        = {r['p_two']:.4f}")
        print(f"  CI 排 0      = {'✅' if r['pass_ci'] else '❌'}")
        print(f"  Bonferroni   = {'✅ 严格通过' if r['pass_bonf'] else '⚠️ 未过'} "
              f"(需 p < {0.05/96:.5f})")

    pd.DataFrame(rows).to_csv(LOG_DIR / "final_signal_nu_implied.csv", index=False)

    # ============================================
    # 跨周期护栏 · 重构不同时钟事件
    # ============================================
    print("\n" + "=" * 100)
    print("KF-7 跨周期护栏 · 新 sweet spot 主线")
    print("=" * 100)

    def build_events_with_clock(symbol, tick, clock_min, horizon_bars):
        bars = load_5m(symbol)
        bars["date"] = bars["datetime"].dt.date
        mask = (bars["datetime"].dt.minute % clock_min == 0) & \
               (bars["datetime"].dt.second == 0)
        idxs = bars.index[mask].to_list()
        rows_c = []
        for i in idxs:
            fut = i + horizon_bars
            if fut >= len(bars):
                continue
            t = bars.loc[i, "datetime"]
            close_t = bars.loc[i, "close"]
            close_fut = bars.loc[fut, "close"]
            ret = np.log(close_fut / close_t)
            current_date = t.date()
            prev = bars[bars["date"] < current_date]
            if len(prev) == 0:
                continue
            pd_date = prev["date"].max()
            w1 = prev[prev["date"] == pd_date]
            if len(w1) < 20:
                continue
            sk = compute_profile_skew(w1, tick)
            if np.isnan(sk):
                continue
            rows_c.append({
                "contract": symbol, "event_time": t, "event_date": current_date,
                "close_t": close_t, "A3_skew": sk, "ret": ret,
            })
        return pd.DataFrame(rows_c)

    def prep_alt_clock(clock_min, horizon_bars):
        all_ev = []
        for sym, tick in OOS_SYMBOLS.items():
            try:
                ev = build_events_with_clock(sym, tick, clock_min, horizon_bars)
                daily = build_daily_features(sym)
                ev = ev.merge(daily, left_on="event_date", right_on="date", how="left")
                all_ev.append(ev)
            except FileNotFoundError:
                continue
        d = pd.concat(all_ev, ignore_index=True)
        d["event_time"] = pd.to_datetime(d["event_time"])
        d = d.sort_values(["contract", "event_time"]).reset_index(drop=True)
        d["signed_skew_rank_roll"] = d.groupby("contract")["A3_skew"].transform(
            lambda s: rolling_pct_rank(s, ROLLING_EVENTS))
        for fc, rc in [("daily_atr_10_bps", "atr_rank_roll"),
                        ("trend_ret_10d", "trend_rank_roll")]:
            seg = []
            for c, g in d.groupby("contract"):
                daily = g.drop_duplicates("event_date").sort_values("event_date").copy()
                daily[rc] = rolling_pct_rank(daily[fc], ROLLING_DAYS)
                seg.append(daily[["contract", "event_date", rc]])
            d = d.merge(pd.concat(seg, ignore_index=True),
                        on=["contract", "event_date"], how="left")
        keep = np.zeros(len(d), dtype=bool)
        for c in d["contract"].unique():
            idx = d[d["contract"] == c].sort_values("event_time").index
            dates = sorted(d.loc[idx, "event_date"].unique())
            if len(dates) < WARMUP_DAYS:
                continue
            wend = dates[WARMUP_DAYS - 1]
            for i in idx:
                if d.at[i, "event_date"] > wend:
                    keep[d.index.get_loc(i)] = True
        d = d[keep].dropna(subset=["signed_skew_rank_roll", "atr_rank_roll",
                                     "trend_rank_roll"])
        d["ret_bps"] = d["ret"] * 1e4
        d["short_bps"] = -d["ret"] * 1e4
        return d

    # 每个主线在不同时钟测一次
    tf_rows = []
    for name, direction, sk, at, tr in signals:
        print(f"\n【{name}】")
        print(f"  {'时钟':6s} {'n':>5s} {'品种':>4s} {'mean':>8s} {'hit':>7s} "
              f"{'CI下':>8s} {'CI上':>8s} {'p':>7s} 判决")
        # 1h 是主时钟 · 8h 或 4h horizon
        h_bars = 96 if direction == "long" else 48  # 8h vs 4h
        ret_col = "ret_bps" if direction == "long" else "short_bps"
        # 1h 直接用主数据
        if direction == "long":
            mask_1h = ((df["signed_skew_rank_roll"] <= sk) &
                        (df["atr_rank_roll"] <= at) &
                        (df["trend_rank_roll"] >= tr))
            sub_1h = df[mask_1h].dropna(subset=["ret_8h_bps"])
            r = cluster_bootstrap(sub_1h, "ret_8h_bps")
        else:
            mask_1h = ((df["signed_skew_rank_roll"] >= sk) &
                        (df["atr_rank_roll"] > at) &
                        (df["trend_rank_roll"] <= tr))
            sub_1h = df[mask_1h].dropna(subset=["short_pnl_4h_bps"])
            r = cluster_bootstrap(sub_1h, "short_pnl_4h_bps")
        hit = (sub_1h.iloc[:, -1] > 0).mean() if len(sub_1h) else 0
        pass_ = "✅" if r["ci_lo"] > 0 else "❌"
        print(f"  {'1h':6s} {r['n_events']:>5d} {r['n_contracts']:>4d} "
              f"{r['real_mean']:>+8.2f} {hit:>7.1%} "
              f"{r['ci_lo']:>+8.2f} {r['ci_hi']:>+8.2f} "
              f"{r['p_two']:>7.4f}  {pass_}")
        tf_rows.append({"signal": name, "clock": "1h", **r, "hit": hit})

        # 15m / 30m / 2h
        for clock_min, clock_name, hb in [(15, "15m", h_bars),
                                             (30, "30m", h_bars),
                                             (120, "2h", h_bars)]:
            d_alt = prep_alt_clock(clock_min, hb)
            if direction == "long":
                mask = ((d_alt["signed_skew_rank_roll"] <= sk) &
                        (d_alt["atr_rank_roll"] <= at) &
                        (d_alt["trend_rank_roll"] >= tr))
                sub = d_alt[mask].dropna(subset=["ret_bps"])
                if len(sub) < 20:
                    print(f"  {clock_name:6s} 样本不足 n={len(sub)}")
                    continue
                r = cluster_bootstrap(sub, "ret_bps")
                hit = (sub["ret_bps"] > 0).mean()
            else:
                mask = ((d_alt["signed_skew_rank_roll"] >= sk) &
                        (d_alt["atr_rank_roll"] > at) &
                        (d_alt["trend_rank_roll"] <= tr))
                sub = d_alt[mask].dropna(subset=["short_bps"])
                if len(sub) < 20:
                    print(f"  {clock_name:6s} 样本不足 n={len(sub)}")
                    continue
                r = cluster_bootstrap(sub, "short_bps")
                hit = (sub["short_bps"] > 0).mean()
            pass_ = "✅" if r["ci_lo"] > 0 else "❌"
            print(f"  {clock_name:6s} {r['n_events']:>5d} {r['n_contracts']:>4d} "
                  f"{r['real_mean']:>+8.2f} {hit:>7.1%} "
                  f"{r['ci_lo']:>+8.2f} {r['ci_hi']:>+8.2f} "
                  f"{r['p_two']:>7.4f}  {pass_}")
            tf_rows.append({"signal": name, "clock": clock_name, **r, "hit": hit})

    pd.DataFrame(tf_rows).to_csv(LOG_DIR / "final_signal_timeframes.csv", index=False)

    print("\n" + "=" * 100)
    print("阶段 2 收尾输出：")
    print(f"  {LOG_DIR / 'final_signal_nu_implied.csv'}")
    print(f"  {LOG_DIR / 'final_signal_timeframes.csv'}")


if __name__ == "__main__":
    main()
