"""
文件级元信息：
- 创建背景：用户假设——稳定期 vs 转换期可能是"反转型 vs 顺势型"两种本质
  不同的机制 · 应各自适配不同的入场出场策略。
- 用途：
    (A) 分布形态对比：skew/kurt/payoff/hit
    (B) Horizon 敏感度对比：1/2/4/6/8/12h 兑现路径
    (E) 事后归因：MAE（最大不利偏移）/ TTP（达到最大盈利的时间）/ 走势轮廓
- 判据：
    * 反转型：短 horizon 兑现 · 尖峰厚尾 · 高 hit · V 型走势（先亏后赚）
    * 顺势型：长 horizon 累积 · 接近正态 · 中 hit · 一路走势（立刻赚）
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, "/Users/gaolei/Documents/src/quant/scripts/ai_tmp")
from poc_va_asymmetry_stage2_grid_search import (  # noqa: E402
    prepare_dataset, OOS_SYMBOLS, load_5m, compute_profile_skew,
    build_daily_features, rolling_pct_rank,
    ROLLING_EVENTS, ROLLING_DAYS, WARMUP_DAYS,
)
from poc_va_asymmetry_stage3_task3_regime_transition import (  # noqa: E402
    flag_regime_transition,
)

LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage3"
)


# ============================================
# A · 分布形态对比
# ============================================
def describe_distribution(x, label):
    x = np.asarray(x)
    if len(x) < 5:
        return {"label": label, "n": len(x), "mean": np.nan, "skew": np.nan}
    wins = x[x > 0]
    losses = x[x < 0]
    payoff = (wins.mean() / abs(losses.mean())) if len(losses) > 0 and losses.mean() != 0 else np.nan
    return {
        "label": label, "n": len(x), "mean": x.mean(), "median": np.median(x),
        "std": x.std(), "skew": stats.skew(x), "kurt": stats.kurtosis(x),
        "p05": np.quantile(x, 0.05), "p95": np.quantile(x, 0.95),
        "hit": (x > 0).mean(),
        "avg_win": wins.mean() if len(wins) else 0,
        "avg_loss": losses.mean() if len(losses) else 0,
        "payoff": payoff,
    }


def print_dist_compare(stable, trans, label):
    d_s = describe_distribution(stable, "稳定")
    d_t = describe_distribution(trans, "转换")
    print(f"\n{'指标':10s} {'稳定期':>10s} {'转换期':>10s} {'差异':>10s}")
    keys = [("n", "n"), ("mean", "mean"), ("std", "std"),
            ("skew", "偏度"), ("kurt", "峰度"),
            ("hit", "hit"), ("payoff", "payoff"),
            ("p05", "p05"), ("p95", "p95"),
            ("avg_win", "avg_win"), ("avg_loss", "avg_loss")]
    for k, lbl in keys:
        vs, vt = d_s.get(k, np.nan), d_t.get(k, np.nan)
        if k == "hit":
            print(f"{lbl:10s} {vs:>10.1%} {vt:>10.1%} {vs-vt:>+10.1%}")
        elif k == "n":
            print(f"{lbl:10s} {int(vs):>10d} {int(vt):>10d} {'-':>10s}")
        else:
            print(f"{lbl:10s} {vs:>+10.2f} {vt:>+10.2f} {vs-vt:>+10.2f}")
    return d_s, d_t


# ============================================
# B · Horizon 敏感度
# ============================================
def build_multi_horizon_events(symbol, tick):
    """构建含多 horizon 的事件表（用于 Horizon 敏感度分析）"""
    bars = load_5m(symbol)
    bars["date"] = bars["datetime"].dt.date
    mask = (bars["datetime"].dt.minute == 0) & (bars["datetime"].dt.second == 0)
    hourly_idx = bars.index[mask].to_list()
    rows = []
    for idx in hourly_idx:
        t = bars.loc[idx, "datetime"]
        close_t = bars.loc[idx, "close"]
        # 多 horizon
        horizons_bars = {"1h": 12, "2h": 24, "3h": 36, "4h": 48,
                         "6h": 72, "8h": 96, "12h": 144}
        h_rets = {}
        skip = False
        for h_name, h_b in horizons_bars.items():
            fut = idx + h_b
            if fut >= len(bars):
                skip = True
                break
            h_rets[f"ret_{h_name}"] = np.log(bars.loc[fut, "close"] / close_t)
        if skip:
            continue
        # profile
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
        # MAE/TTP · 8h 窗口内 · 5m 粒度
        window = bars.iloc[idx: idx + 96]  # 8h = 96 * 5m
        if len(window) < 96:
            continue
        # 用 close 序列
        prices = window["close"].values
        log_rets_seq = np.log(prices / close_t)  # 相对入场价的 log 收益路径
        rows.append({
            "contract": symbol, "event_time": t, "event_date": current_date,
            "event_hour": t.hour, "close_t": close_t, "A3_skew": sk, **h_rets,
            "path_min_bps": log_rets_seq.min() * 1e4,
            "path_max_bps": log_rets_seq.max() * 1e4,
            "ttp_bars_max": np.argmax(log_rets_seq),  # 最大盈利在第几个 bar
            "ttp_bars_min": np.argmin(log_rets_seq),  # 最大亏损在第几个 bar
            "ret_1h_bps_path": log_rets_seq[11] * 1e4,  # 1h 后的收益（用于路径）
            "ret_2h_bps_path": log_rets_seq[23] * 1e4,
            "ret_4h_bps_path": log_rets_seq[47] * 1e4,
        })
    return pd.DataFrame(rows)


# ============================================
# 主流程
# ============================================
def main():
    print("=" * 100)
    print("阶段 3 深挖 · 稳定期 vs 转换期 · 反转型 vs 顺势型验证")
    print("=" * 100)

    print("\n[准备数据] ...")
    df = prepare_dataset()
    df = flag_regime_transition(df)

    print("\n[构建多 horizon + 路径事件表 · 需 1-2 分钟] ...")
    all_ev = []
    for sym, tick in OOS_SYMBOLS.items():
        try:
            ev = build_multi_horizon_events(sym, tick)
            all_ev.append(ev)
        except FileNotFoundError:
            continue
    df_mh = pd.concat(all_ev, ignore_index=True)
    df_mh["event_time"] = pd.to_datetime(df_mh["event_time"])
    df_mh = df_mh.sort_values(["contract", "event_time"]).reset_index(drop=True)
    df_mh["signed_skew_rank_roll"] = df_mh.groupby("contract")["A3_skew"].transform(
        lambda s: rolling_pct_rank(s, ROLLING_EVENTS))
    for fc, rc in [("daily_atr_10_bps", "atr_rank_roll"),
                   ("trend_ret_10d", "trend_rank_roll")]:
        seg = []
        for c, g in df_mh.groupby("contract"):
            daily_feat = build_daily_features(c)
            g2 = g.merge(daily_feat, left_on="event_date", right_on="date", how="left")
            g2_daily = g2.drop_duplicates("event_date").sort_values("event_date").copy()
            g2_daily[rc] = rolling_pct_rank(g2_daily[fc], ROLLING_DAYS)
            seg.append(g2_daily[["contract", "event_date", rc]])
        seg_map = pd.concat(seg, ignore_index=True)
        df_mh = df_mh.merge(seg_map, on=["contract", "event_date"], how="left")
    # warmup 过滤
    keep = np.zeros(len(df_mh), dtype=bool)
    for c in df_mh["contract"].unique():
        idx = df_mh[df_mh["contract"] == c].sort_values("event_time").index
        dates = sorted(df_mh.loc[idx, "event_date"].unique())
        if len(dates) < WARMUP_DAYS:
            continue
        wend = dates[WARMUP_DAYS - 1]
        for i in idx:
            if df_mh.at[i, "event_date"] > wend:
                keep[df_mh.index.get_loc(i)] = True
    df_mh = df_mh[keep].dropna(subset=["signed_skew_rank_roll", "atr_rank_roll",
                                        "trend_rank_roll"])
    # 加 transition flag
    tf_map = df[["contract", "event_date", "transition_flag"]].drop_duplicates(
        ["contract", "event_date"])
    df_mh = df_mh.merge(tf_map, on=["contract", "event_date"], how="left")
    df_mh = df_mh.dropna(subset=["transition_flag"])
    print(f"  多 horizon 有效事件: n={len(df_mh)}")

    # 定义 4 主线（多头首选/宽松 · 空头首选/宽松）
    signals = [
        ("多头首选（skew≤0.10·atr≤0.70·trend≥0.75）",
         "long", 0.10, 0.70, 0.75),
        ("多头宽松（skew≤0.30·atr≤0.70·trend≥0.75）",
         "long", 0.30, 0.70, 0.75),
        ("空头首选（skew≥0.70·atr>0.80·trend≤0.20）",
         "short", 0.70, 0.80, 0.20),
        ("空头宽松（skew≥0.70·atr>0.50·trend≤0.20）",
         "short", 0.70, 0.50, 0.20),
    ]

    # =================================================================
    # A · 分布形态对比
    # =================================================================
    print("\n\n" + "=" * 100)
    print("A · 分布形态对比 · 稳定期 vs 转换期")
    print("=" * 100)

    all_dist_rows = []
    for name, direction, sk, at, tr in signals:
        print(f"\n{'='*90}\n【{name}】\n{'='*90}")
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
        sub = df[mask].dropna(subset=[ret_col, "transition_flag"])
        stable = sub[~sub["transition_flag"]][ret_col].values
        trans = sub[sub["transition_flag"]][ret_col].values

        if len(stable) < 10 or len(trans) < 10:
            print("样本不足 · 跳过")
            continue
        d_s, d_t = print_dist_compare(stable, trans, name)
        all_dist_rows.append({"signal": name, "type": "stable", **d_s})
        all_dist_rows.append({"signal": name, "type": "transition", **d_t})

    pd.DataFrame(all_dist_rows).to_csv(
        LOG_DIR / "deep_stable_vs_transition_dist.csv", index=False)

    # =================================================================
    # B · Horizon 敏感度对比
    # =================================================================
    print("\n\n" + "=" * 100)
    print("B · Horizon 敏感度对比 · 稳定期 vs 转换期")
    print("=" * 100)

    horizons = ["1h", "2h", "3h", "4h", "6h", "8h", "12h"]
    all_hz_rows = []
    for name, direction, sk, at, tr in signals:
        print(f"\n{'='*90}\n【{name}】\n{'='*90}")
        if direction == "long":
            mask_mh = ((df_mh["signed_skew_rank_roll"] <= sk) &
                       (df_mh["atr_rank_roll"] <= at) &
                       (df_mh["trend_rank_roll"] >= tr))
            sign = 1
        else:
            mask_mh = ((df_mh["signed_skew_rank_roll"] >= sk) &
                       (df_mh["atr_rank_roll"] > at) &
                       (df_mh["trend_rank_roll"] <= tr))
            sign = -1
        sub_mh = df_mh[mask_mh]
        stable_mh = sub_mh[~sub_mh["transition_flag"]]
        trans_mh = sub_mh[sub_mh["transition_flag"]]
        print(f"\n  样本: 稳定 n={len(stable_mh)} · 转换 n={len(trans_mh)}")
        if len(stable_mh) < 20 or len(trans_mh) < 20:
            print("  样本不足 · 跳过")
            continue

        print(f"\n  {'Horizon':10s} {'稳定 mean':>12s} {'转换 mean':>12s} {'稳定/4h%':>10s} {'转换/4h%':>10s}")
        stable_4h = stable_mh["ret_4h"].mean() * 1e4 * sign
        trans_4h = trans_mh["ret_4h"].mean() * 1e4 * sign
        for h in horizons:
            col = f"ret_{h}"
            s_m = stable_mh[col].mean() * 1e4 * sign
            t_m = trans_mh[col].mean() * 1e4 * sign
            s_p = s_m / stable_4h * 100 if stable_4h != 0 else np.nan
            t_p = t_m / trans_4h * 100 if trans_4h != 0 else np.nan
            print(f"  {h:10s} {s_m:>+12.2f} {t_m:>+12.2f} {s_p:>+10.1f} {t_p:>+10.1f}")
            all_hz_rows.append({
                "signal": name, "horizon": h,
                "stable_mean": s_m, "trans_mean": t_m,
                "stable_pct": s_p, "trans_pct": t_p,
            })

    pd.DataFrame(all_hz_rows).to_csv(
        LOG_DIR / "deep_stable_vs_transition_horizon.csv", index=False)

    # =================================================================
    # E · 事后归因（MAE/TTP/走势轮廓）
    # =================================================================
    print("\n\n" + "=" * 100)
    print("E · 事后归因 · MAE（最大不利偏移）/ TTP（最大盈利时点）")
    print("=" * 100)

    all_e_rows = []
    for name, direction, sk, at, tr in signals:
        print(f"\n{'='*90}\n【{name}】\n{'='*90}")
        if direction == "long":
            mask_mh = ((df_mh["signed_skew_rank_roll"] <= sk) &
                       (df_mh["atr_rank_roll"] <= at) &
                       (df_mh["trend_rank_roll"] >= tr))
            sign = 1
            # 多头视角：mae = min · mfe = max
            mae_col = "path_min_bps"
            mfe_col = "path_max_bps"
        else:
            mask_mh = ((df_mh["signed_skew_rank_roll"] >= sk) &
                       (df_mh["atr_rank_roll"] > at) &
                       (df_mh["trend_rank_roll"] <= tr))
            sign = -1
            # 空头视角：mae = max · mfe = min（取反）
            mae_col = "path_max_bps"  # 价格上涨对空头不利
            mfe_col = "path_min_bps"

        sub_mh = df_mh[mask_mh]
        stable_mh = sub_mh[~sub_mh["transition_flag"]]
        trans_mh = sub_mh[sub_mh["transition_flag"]]
        if len(stable_mh) < 20 or len(trans_mh) < 20:
            print("  样本不足 · 跳过")
            continue

        # MAE（单位：bps · 负数表示对头寸不利）
        if direction == "long":
            s_mae = stable_mh[mae_col].mean()  # 已经是负值（min log return）
            t_mae = trans_mh[mae_col].mean()
            s_mfe = stable_mh[mfe_col].mean()
            t_mfe = trans_mh[mfe_col].mean()
        else:
            s_mae = -stable_mh[mae_col].mean()  # max 是价格上涨 · 对空头是负收益
            t_mae = -trans_mh[mae_col].mean()
            s_mfe = -stable_mh[mfe_col].mean()  # min 是价格下跌 · 对空头是正收益
            t_mfe = -trans_mh[mfe_col].mean()

        # TTP（第几个 bar 达到最大盈利 · 5m 粒度 · 96 = 8h）
        if direction == "long":
            s_ttp = stable_mh["ttp_bars_max"].mean() / 12  # 转换为小时
            t_ttp = trans_mh["ttp_bars_max"].mean() / 12
            s_ttm = stable_mh["ttp_bars_min"].mean() / 12
            t_ttm = trans_mh["ttp_bars_min"].mean() / 12
        else:
            s_ttp = stable_mh["ttp_bars_min"].mean() / 12
            t_ttp = trans_mh["ttp_bars_min"].mean() / 12
            s_ttm = stable_mh["ttp_bars_max"].mean() / 12
            t_ttm = trans_mh["ttp_bars_max"].mean() / 12

        # 1h 内早期走势：入场后 1h 是否已经赚 · 还是先亏
        if direction == "long":
            s_early = stable_mh["ret_1h_bps_path"].mean()
            t_early = trans_mh["ret_1h_bps_path"].mean()
        else:
            s_early = -stable_mh["ret_1h_bps_path"].mean()
            t_early = -trans_mh["ret_1h_bps_path"].mean()

        print(f"\n  {'指标':20s} {'稳定期':>12s} {'转换期':>12s} {'差异':>10s}")
        print(f"  {'MAE bps (对头寸)':20s} {s_mae:>+12.2f} {t_mae:>+12.2f} {s_mae-t_mae:>+10.2f}")
        print(f"  {'MFE bps (对头寸)':20s} {s_mfe:>+12.2f} {t_mfe:>+12.2f} {s_mfe-t_mfe:>+10.2f}")
        print(f"  {'达最大盈利时间(h)':20s} {s_ttp:>12.2f} {t_ttp:>12.2f} {s_ttp-t_ttp:>+10.2f}")
        print(f"  {'达最大亏损时间(h)':20s} {s_ttm:>12.2f} {t_ttm:>12.2f} {s_ttm-t_ttm:>+10.2f}")
        print(f"  {'早期 1h 收益 bps':20s} {s_early:>+12.2f} {t_early:>+12.2f} {s_early-t_early:>+10.2f}")

        # 判读
        print(f"\n  判读:")
        if s_early < -5 and t_early > 5:
            print(f"    ✅ 稳定期先亏({s_early:.1f}) → 后赚（反转型）· 转换期立刻赚({t_early:.1f})（顺势型）")
        elif abs(s_mae) > abs(t_mae) * 1.3:
            print(f"    ⚠️ 稳定期 MAE 更深（{s_mae:.1f} vs {t_mae:.1f}）· 略反转特征")
        elif t_ttp < s_ttp * 0.7:
            print(f"    ✅ 转换期达峰更快（{t_ttp:.1f}h vs {s_ttp:.1f}h）· 顺势型")
        elif s_ttp < t_ttp * 0.7:
            print(f"    ✅ 稳定期达峰更快（{s_ttp:.1f}h vs {t_ttp:.1f}h）· 反转型（快回归）")
        else:
            print(f"    ⚠️ 两者形态相似 · 未见明显反转/顺势差异")

        all_e_rows.append({
            "signal": name, "s_mae": s_mae, "t_mae": t_mae,
            "s_mfe": s_mfe, "t_mfe": t_mfe,
            "s_ttp_h": s_ttp, "t_ttp_h": t_ttp,
            "s_ttm_h": s_ttm, "t_ttm_h": t_ttm,
            "s_early_1h": s_early, "t_early_1h": t_early,
        })

    pd.DataFrame(all_e_rows).to_csv(
        LOG_DIR / "deep_stable_vs_transition_attribution.csv", index=False)

    # =================================================================
    # 综合判读
    # =================================================================
    print("\n\n" + "=" * 100)
    print("综合判读 · 假设检验")
    print("=" * 100)
    print("""
假设：稳定期 = 反转型 · 转换期 = 顺势型
需要看到的证据：
  1. 稳定期偏度更正、峰度更高（尖峰厚尾 = 反转型）
  2. 稳定期 hit 更高、payoff 更高（反转型 · 高胜率）
  3. 稳定期 horizon 峰值早（4h 甜蜜）· 转换期 horizon 峰值晚（8-12h）
  4. 稳定期早期 1h 亏、TTP 晚（V 型）· 转换期早期立刻赚、TTP 早（一路）
""")

    print("\n输出文件：")
    print(f"  {LOG_DIR / 'deep_stable_vs_transition_dist.csv'}")
    print(f"  {LOG_DIR / 'deep_stable_vs_transition_horizon.csv'}")
    print(f"  {LOG_DIR / 'deep_stable_vs_transition_attribution.csv'}")


if __name__ == "__main__":
    main()
