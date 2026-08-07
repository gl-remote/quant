"""
ATR 跨周期比值研究 · 四象限市场环境画像（全周期版）
====================================================

基于所有可用 1h 数据（2022-2026，含牛/熊/震荡），重新生成四象限画像。
与 profile_quadrants.py 的区别：
- 数据覆盖 2022-2026 全周期，不只牛市；
- 加入牛/熊市场环境对比；
- 重点是描述性统计（波动率、趋势、板块/时间分布、状态转换）；
- 不做方向收益判断（已证明方向信号都是 beta）；
- 关注前向波动率而非方向收益。
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=RuntimeWarning)

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti TC", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parents[5]
SCRIPT_DIR = Path(__file__).resolve().parents[1]
CSV_DIR = ROOT / "project_data" / "market_data" / "csv"
OUT_DIR = SCRIPT_DIR / "outputs" / "profile_full"
FIG_DIR = OUT_DIR / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)

STATE_ORDER = ["co_compress", "H_only", "L_only", "co_expand"]
STATE_LABELS = {
    "co_compress": "双周期压缩", "H_only": "高周期独扩",
    "L_only": "低周期独扩", "co_expand": "共振扩张",
}
STATE_COLORS = {
    "co_compress": "#4C72B0", "H_only": "#DD8452",
    "L_only": "#55A868", "co_expand": "#C44E52",
}


def wilder_atr(df, length=14):
    h, l, c = df["high"], df["low"], df["close"]
    pc = c.shift(1)
    tr = pd.concat([(h-l), (h-pc).abs(), (l-pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/length, adjust=False, min_periods=length).mean()


def classify_sector(sym):
    if sym.startswith("SHFE."):
        code = sym[5:]
        if code.startswith(("cu", "al", "zn", "pb", "ni", "sn", "au", "ag")):
            return "有色"
        return "能化"
    if sym.startswith("INE."):
        return "能化"
    if sym.startswith("DCE."):
        code = sym[4:]
        if code.startswith(("i", "j", "jm", "l", "v", "pp", "eg", "eb", "pg")):
            return "黑色/能化"
        return "农产品"
    if sym.startswith("CZCE."):
        return "农产品"
    if sym.startswith("GFEX."):
        return "黑色"
    return "其他"


def classify_regime(year):
    """简单的市场环境分类。"""
    if year in [2022]:
        return "熊市"
    if year in [2023]:
        return "震荡"
    return "牛市"


def compute_panel(sym):
    """计算单合约的四象限因子，对齐到 1h。"""
    f1h = CSV_DIR / f"{sym}.tqsdk.1h.csv"
    f15 = CSV_DIR / f"{sym}.tqsdk.15m.csv"
    if not f1h.exists() or not f15.exists():
        return None
    df_1h = pd.read_csv(f1h, parse_dates=["datetime"]).sort_values("datetime").reset_index(drop=True)
    df_15 = pd.read_csv(f15, parse_dates=["datetime"]).sort_values("datetime").reset_index(drop=True)
    if len(df_1h) < 200 or len(df_15) < 400:
        return None

    df_1h["H"] = wilder_atr(df_1h, 14)
    df_1h["H_long"] = wilder_atr(df_1h, 50)
    df_15["L"] = wilder_atr(df_15, 14)
    df_15["L_clock"] = wilder_atr(df_15, 56)
    df_15["L_long"] = wilder_atr(df_15, 200)

    base = df_1h[["datetime", "open", "high", "low", "close", "H", "H_long"]].dropna().sort_values("datetime")
    l_sub = df_15[["datetime", "L", "L_clock", "L_long"]].dropna().sort_values("datetime")
    base = pd.merge_asof(base, l_sub, on="datetime", direction="backward")
    base = base.dropna()

    base["R_bar"] = base["H"] / base["L_clock"]
    base["S_H"] = base["H"] / base["H_long"]
    base["S_L"] = base["L_clock"] / base["L_long"]
    base["H_norm"] = base["H"] / base["close"]

    sh = base["S_H"] > 1
    sl = base["S_L"] > 1
    base["state_S"] = "co_compress"
    base.loc[sh & sl, "state_S"] = "co_expand"
    base.loc[sh & ~sl, "state_S"] = "H_only"
    base.loc[~sh & sl, "state_S"] = "L_only"

    # 前向波动率
    base["fwd_ret_5"] = base["close"].shift(-5) / base["close"] - 1
    base["fwd_ret_20"] = base["close"].shift(-20) / base["close"] - 1
    base["fwd_abs_ret_5"] = base["fwd_ret_5"].abs()
    base["fwd_abs_ret_20"] = base["fwd_ret_20"].abs()
    # 已实现波动率（20 根收益率标准差）
    base["ret_1h"] = base["close"].pct_change()
    base["rv_20"] = base["ret_1h"].rolling(20).std()

    base["symbol"] = sym
    base["sector"] = classify_sector(sym)
    base["date"] = base["datetime"].dt.date
    base["year"] = base["datetime"].dt.year
    base["month"] = base["datetime"].dt.month
    base["hour"] = base["datetime"].dt.hour
    base["regime"] = base["year"].apply(classify_regime)
    base["buy_hold"] = base["close"].iloc[-1] / base["close"].iloc[0] - 1

    return base


def main():
    print("加载所有合约...", flush=True)
    panels = []
    for f in sorted(CSV_DIR.glob("*.1h.csv")):
        sym = f.name.replace(".tqsdk.1h.csv", "")
        p = compute_panel(sym)
        if p is not None:
            panels.append(p)
    panel = pd.concat(panels, ignore_index=True)
    print(f"面板: {len(panel)} 行, {panel['symbol'].nunique()} 合约", flush=True)
    print(f"时间: {panel['datetime'].min()} ~ {panel['datetime'].max()}", flush=True)
    print(f"年份: {sorted(panel['year'].unique())}", flush=True)

    # ============================================================
    # 1. 整体四象限画像
    # ============================================================
    print("\n=== 1. 四象限基础画像（全周期）===", flush=True)
    rows = []
    for state in STATE_ORDER:
        sub = panel[panel["state_S"] == state]
        row = {
            "state": state, "label": STATE_LABELS[state],
            "n": len(sub), "pct": len(sub)/len(panel),
            "R_bar_mean": sub["R_bar"].mean(), "R_bar_median": sub["R_bar"].median(),
            "S_H_mean": sub["S_H"].mean(), "S_L_mean": sub["S_L"].mean(),
            "H_norm_pct": sub["H_norm"].mean() * 100,
            "rv20_pct": sub["rv_20"].mean() * 100,
            "fwd_abs5_pct": sub["fwd_abs_ret_5"].mean() * 100,
            "fwd_abs20_pct": sub["fwd_abs_ret_20"].mean() * 100,
        }
        rows.append(row)
    profile = pd.DataFrame(rows)
    profile.to_csv(OUT_DIR / "full_profile_by_state.csv", index=False)
    print(profile.round(4).to_string(index=False), flush=True)

    # ============================================================
    # 2. 牛/熊/震荡对比
    # ============================================================
    print("\n=== 2. 市场环境 × 四象限 ===", flush=True)
    regime_state = panel.groupby(["regime", "state_S"]).size().unstack(fill_value=0)
    regime_pct = regime_state.div(regime_state.sum(axis=1), axis=0)
    regime_pct = regime_pct[STATE_ORDER]
    regime_pct.to_csv(OUT_DIR / "full_regime_state_pct.csv")
    print(regime_pct.round(3).to_string(), flush=True)

    # 各象限在不同 regime 下的波动率
    print("\n--- 各象限 H_norm (%) by regime ---", flush=True)
    regime_vol = panel.groupby(["regime", "state_S"])["H_norm"].mean().unstack() * 100
    regime_vol = regime_vol[STATE_ORDER]
    regime_vol.to_csv(OUT_DIR / "full_regime_vol.csv")
    print(regime_vol.round(3).to_string(), flush=True)

    # 前向波动率
    print("\n--- 各象限 fwd_|r|_20 (%) by regime ---", flush=True)
    regime_fwd = panel.groupby(["regime", "state_S"])["fwd_abs_ret_20"].mean().unstack() * 100
    regime_fwd = regime_fwd[STATE_ORDER]
    regime_fwd.to_csv(OUT_DIR / "full_regime_fwd_vol.csv")
    print(regime_fwd.round(3).to_string(), flush=True)

    # ============================================================
    # 3. 按板块
    # ============================================================
    print("\n=== 3. 板块 × 象限 ===", flush=True)
    sector_state = panel.groupby(["sector", "state_S"]).size().unstack(fill_value=0)
    sector_pct = sector_state.div(sector_state.sum(axis=1), axis=0)[STATE_ORDER]
    sector_pct.to_csv(OUT_DIR / "full_sector_state_pct.csv")
    print(sector_pct.round(3).to_string(), flush=True)

    # ============================================================
    # 4. 按交易时段
    # ============================================================
    def session(h):
        if 9 <= h < 11 or 13 <= h < 15:
            return "日盘"
        if 21 <= h <= 23 or 0 <= h < 3:
            return "夜盘"
        return "其他"
    panel["session"] = panel["hour"].apply(session)
    sess_state = panel.groupby(["session", "state_S"]).size().unstack(fill_value=0)
    sess_pct = sess_state.div(sess_state.sum(axis=1), axis=0)[STATE_ORDER]
    sess_pct.to_csv(OUT_DIR / "full_session_state_pct.csv")
    print("\n=== 4. 交易时段 × 象限 ===", flush=True)
    print(sess_pct.round(3).to_string(), flush=True)

    # ============================================================
    # 5. 状态持续时间
    # ============================================================
    print("\n=== 5. 状态持续时间 ===", flush=True)
    panel_sorted = panel.sort_values(["symbol", "datetime"]).reset_index(drop=True)
    sym_change = panel_sorted["symbol"] != panel_sorted["symbol"].shift(1)
    state_change = panel_sorted["state_S"] != panel_sorted["state_S"].shift(1)
    new_seg = sym_change | state_change
    panel_sorted["seg_id"] = new_seg.cumsum()
    durations = panel_sorted.groupby(["symbol", "seg_id", "state_S"]).size().reset_index(name="duration")
    dur_rows = []
    for state in STATE_ORDER:
        d = durations[durations["state_S"] == state]["duration"]
        dur_rows.append({
            "state": state, "n_segments": len(d),
            "mean": d.mean(), "median": d.median(),
            "p25": d.quantile(0.25), "p75": d.quantile(0.75),
            "p90": d.quantile(0.90), "max": d.max(),
        })
    dur_df = pd.DataFrame(dur_rows)
    dur_df.to_csv(OUT_DIR / "full_duration.csv", index=False)
    print(dur_df.round(2).to_string(index=False), flush=True)

    # ============================================================
    # 6. 状态转换矩阵
    # ============================================================
    print("\n=== 6. 状态转换矩阵 ===", flush=True)
    panel_sorted["next_state"] = panel_sorted.groupby("symbol")["state_S"].shift(-1)
    trans = panel_sorted.dropna(subset=["next_state"])
    trans = trans[trans["symbol"] == trans["symbol"].shift(-1)]  # 排除跨 symbol
    tm = pd.crosstab(trans["state_S"], trans["next_state"], normalize="index")
    tm = tm.reindex(index=STATE_ORDER, columns=STATE_ORDER, fill_value=0)
    tm.to_csv(OUT_DIR / "full_transition.csv")
    print(tm.round(3).to_string(), flush=True)

    # 5 步转换
    panel_sorted["next_state_5"] = panel_sorted.groupby("symbol")["state_S"].shift(-5)
    trans5 = panel_sorted.dropna(subset=["next_state_5"])
    tm5 = pd.crosstab(trans5["state_S"], trans5["next_state_5"], normalize="index")
    tm5 = tm5.reindex(index=STATE_ORDER, columns=STATE_ORDER, fill_value=0)
    tm5.to_csv(OUT_DIR / "full_transition_5.csv")

    # ============================================================
    # 7. R_bar 自相关（全周期）
    # ============================================================
    print("\n=== 7. R_bar 自相关 ===", flush=True)
    acf_rows = []
    for sym, sub in panel_sorted.groupby("symbol"):
        r = sub["R_bar"].dropna().values
        if len(r) < 100:
            continue
        def acf(lag):
            if len(r) <= lag + 5:
                return np.nan
            return float(np.corrcoef(r[:-lag], r[lag:])[0, 1])
        a1 = acf(1)
        a5 = acf(5)
        a20 = acf(20)
        half = -np.log(2)/np.log(abs(a1)) if 0 < a1 < 1 else np.nan
        acf_rows.append({"symbol": sym, "acf1": a1, "acf5": a5, "acf20": a20,
                         "half_life": half, "sector": sub["sector"].iloc[0]})
    acf_df = pd.DataFrame(acf_rows)
    acf_df.to_csv(OUT_DIR / "full_rbar_acf.csv", index=False)
    print(f"  ACF(1) 中位: {acf_df['acf1'].median():.3f}")
    print(f"  ACF(5) 中位: {acf_df['acf5'].median():.3f}")
    print(f"  ACF(20) 中位: {acf_df['acf20'].median():.3f}")
    print(f"  半衰期（根）中位: {acf_df['half_life'].median():.1f}", flush=True)

    # ============================================================
    # 8. R_bar 对前向波动率的预测力（全周期 vs 分 regime）
    # ============================================================
    print("\n=== 8. R_bar 与前向波动率相关性 ===", flush=True)
    corr_rows = []
    for regime_name, sub in panel.groupby("regime"):
        for metric in ["R_bar", "S_H", "S_L", "H_norm", "rv_20"]:
            for h in [5, 20]:
                col = f"fwd_abs_ret_{h}"
                mask = ~(sub[metric].isna() | sub[col].isna())
                c = float(np.corrcoef(sub.loc[mask, metric], sub.loc[mask, col])[0, 1])
                corr_rows.append({"regime": regime_name, "metric": metric,
                                   "horizon": h, "corr": c})
    # 整体
    for metric in ["R_bar", "S_H", "S_L", "H_norm", "rv_20"]:
        for h in [5, 20]:
            col = f"fwd_abs_ret_{h}"
            mask = ~(panel[metric].isna() | panel[col].isna())
            c = float(np.corrcoef(panel.loc[mask, metric], panel.loc[mask, col])[0, 1])
            corr_rows.append({"regime": "ALL", "metric": metric, "horizon": h, "corr": c})
    corr_df = pd.DataFrame(corr_rows)
    corr_df.to_csv(OUT_DIR / "full_predictive_corr.csv", index=False)
    print(corr_df.pivot_table(index="metric", columns=["regime", "horizon"], values="corr").round(3).to_string(), flush=True)

    # ============================================================
    # 图表
    # ============================================================
    print("\n生成图表...", flush=True)

    # Fig 1: 四象限画像
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    x = np.arange(len(STATE_ORDER))
    axes[0,0].bar(x, profile["pct"]*100, color=[STATE_COLORS[s] for s in STATE_ORDER])
    axes[0,0].set_xticks(x); axes[0,0].set_xticklabels([STATE_LABELS[s] for s in STATE_ORDER], fontsize=9)
    axes[0,0].set_title("样本占比"); axes[0,0].grid(axis="y", alpha=0.3)
    axes[0,0].set_ylabel("%")

    w = 0.25
    axes[0,1].bar(x-w, profile["R_bar_mean"], w, label="R_bar", color="#4C72B0")
    axes[0,1].bar(x, profile["S_H_mean"], w, label="S_H", color="#DD8452")
    axes[0,1].bar(x+w, profile["S_L_mean"], w, label="S_L", color="#55A868")
    axes[0,1].axhline(1.0, color="gray", ls="--", lw=0.8)
    axes[0,1].set_xticks(x); axes[0,1].set_xticklabels([STATE_LABELS[s] for s in STATE_ORDER], fontsize=9)
    axes[0,1].set_title("因子均值"); axes[0,1].legend(fontsize=8); axes[0,1].grid(axis="y", alpha=0.3)

    axes[1,0].bar(x-w, profile["H_norm_pct"], w, label="H_norm(%)", color="#DD8452")
    axes[1,0].bar(x, profile["rv20_pct"], w, label="rv_20(%)", color="#8172B2")
    axes[1,0].bar(x+w, profile["fwd_abs20_pct"], w, label="fwd_|r|20(%)", color="#C44E52")
    axes[1,0].set_xticks(x); axes[1,0].set_xticklabels([STATE_LABELS[s] for s in STATE_ORDER], fontsize=9)
    axes[1,0].set_title("波动率水平"); axes[1,0].legend(fontsize=8); axes[1,0].grid(axis="y", alpha=0.3)

    # 牛熊对比占比
    for i, regime in enumerate(["熊市", "震荡", "牛市"]):
        if regime in regime_pct.index:
            axes[1,1].plot(x, regime_pct.loc[regime].values*100, marker="o", label=regime)
    axes[1,1].set_xticks(x); axes[1,1].set_xticklabels([STATE_LABELS[s] for s in STATE_ORDER], fontsize=9)
    axes[1,1].set_title("各市场环境下的象限占比"); axes[1,1].legend(fontsize=9); axes[1,1].grid(alpha=0.3)
    axes[1,1].set_ylabel("%")

    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig1_quadrant_profile.png", dpi=150, bbox_inches="tight")
    plt.close()

    # Fig 2: R_bar 分布
    fig, ax = plt.subplots(figsize=(12, 6))
    for state in STATE_ORDER:
        sub = panel[panel["state_S"] == state]
        ax.hist(sub["R_bar"].dropna(), bins=80, alpha=0.5, density=True,
                label=STATE_LABELS[state], color=STATE_COLORS[state])
    ax.axvline(2.0, color="black", ls="--", lw=1, label="sqrt(4)=2.0")
    ax.axvline(panel["R_bar"].median(), color="gray", ls=":", lw=1,
               label=f"中位 {panel['R_bar'].median():.2f}")
    ax.set_xlabel("R_bar"); ax.set_ylabel("密度")
    ax.set_title("R_bar 分布（全周期 2022-2026）"); ax.legend(fontsize=9); ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig2_rbar_dist.png", dpi=150, bbox_inches="tight")
    plt.close()

    # Fig 3: 转换热力图
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    for ax, mat, title in [(axes[0], tm, "1 步转换"), (axes[1], tm5, "5 步转换")]:
        im = ax.imshow(mat.values, cmap="YlOrRd", aspect="auto", vmin=0, vmax=1)
        ax.set_xticks(range(4)); ax.set_yticks(range(4))
        ax.set_xticklabels([STATE_LABELS[s] for s in STATE_ORDER], rotation=30, ha="right", fontsize=9)
        ax.set_yticklabels([STATE_LABELS[s] for s in STATE_ORDER], fontsize=9)
        ax.set_xlabel("下一状态"); ax.set_ylabel("当前状态"); ax.set_title(title)
        for i in range(4):
            for j in range(4):
                v = mat.iloc[i, j]
                ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                        color="white" if v > 0.5 else "black", fontsize=9)
        plt.colorbar(im, ax=ax, fraction=0.046)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig3_transition.png", dpi=150, bbox_inches="tight")
    plt.close()

    # Fig 4: 板块 × 象限
    fig, ax = plt.subplots(figsize=(12, 6))
    sectors = sector_pct.index.tolist()
    bottom = np.zeros(len(sectors))
    for state in STATE_ORDER:
        vals = sector_pct[state].values * 100 if state in sector_pct.columns else np.zeros(len(sectors))
        ax.bar(sectors, vals, bottom=bottom, label=STATE_LABELS[state], color=STATE_COLORS[state])
        bottom += vals
    ax.set_ylabel("%"); ax.set_title("板块 × 四象限"); ax.legend(fontsize=9); ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig4_sector.png", dpi=150, bbox_inches="tight")
    plt.close()

    # Fig 5: 各 regime 下的波动率
    fig, ax = plt.subplots(figsize=(10, 6))
    regimes = ["熊市", "震荡", "牛市"]
    w = 0.15
    for i, regime in enumerate(regimes):
        if regime in regime_vol.index:
            vals = [regime_vol.loc[regime, s] if s in regime_vol.columns else 0 for s in STATE_ORDER]
            ax.bar(x + (i-1)*w, vals, w, label=regime)
    ax.set_xticks(x); ax.set_xticklabels([STATE_LABELS[s] for s in STATE_ORDER], fontsize=9)
    ax.set_ylabel("H_norm (%)"); ax.set_title("各市场环境下的波动率水平")
    ax.legend(fontsize=9); ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig5_regime_vol.png", dpi=150, bbox_inches="tight")
    plt.close()

    # Fig 6: R_bar 自相关衰减
    fig, ax = plt.subplots(figsize=(10, 6))
    for sym, sub in panel_sorted.groupby("symbol"):
        r = sub["R_bar"].dropna().values
        if len(r) < 200:
            continue
        acfs = []
        for lag in [1,2,3,5,10,20,40,60]:
            if len(r) > lag+5:
                acfs.append(float(np.corrcoef(r[:-lag], r[lag:])[0,1]))
            else:
                acfs.append(np.nan)
        ax.plot([1,2,3,5,10,20,40,60], acfs, alpha=0.15, color="#4C72B0", lw=0.8)
    lags = [1,2,3,5,10,20,40,60]
    med = []
    for lag in lags:
        vals = []
        for sym, sub in panel_sorted.groupby("symbol"):
            r = sub["R_bar"].dropna().values
            if len(r) > lag+5:
                vals.append(float(np.corrcoef(r[:-lag], r[lag:])[0,1]))
        med.append(np.nanmedian(vals))
    ax.plot(lags, med, color="red", lw=2.5, marker="o", label="中位 ACF", zorder=5)
    ax.axhline(0, color="gray", ls="--", lw=0.8)
    ax.set_xlabel("滞后（根 1h）"); ax.set_ylabel("ACF")
    ax.set_xscale("log"); ax.set_title("R_bar 自相关衰减（全周期）")
    ax.legend(); ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig6_rbar_acf.png", dpi=150, bbox_inches="tight")
    plt.close()

    # Summary
    summary = {
        "n_rows": int(len(panel)),
        "n_symbols": int(panel["symbol"].nunique()),
        "date_range": [str(panel["datetime"].min()), str(panel["datetime"].max())],
        "regimes": {r: int((panel["regime"]==r).sum()) for r in ["熊市","震荡","牛市"]},
        "state_pct": {s: float((panel["state_S"]==s).mean()) for s in STATE_ORDER},
        "rbar_median": float(panel["R_bar"].median()),
        "rbar_acf1_median": float(acf_df["acf1"].median()),
        "rbar_half_life_median": float(acf_df["half_life"].median()),
        "transition_1step": tm.round(3).to_dict(),
    }
    with open(OUT_DIR / "full_profile_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n输出已保存到 {OUT_DIR}", flush=True)


if __name__ == "__main__":
    main()
