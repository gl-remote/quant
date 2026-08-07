"""
ATR 跨周期比值研究 · 状态转换路径分析
======================================

研究两条路径的差异：
  路径 H：co_compress → H_only → co_expand（高周期先扩张）
  路径 L：co_compress → L_only → co_expand（低周期先扩张）

对比维度：
1. 发生频率（各占多少比例）
2. 转换时间（每步间隔多久、总时长）
3. 中间态的持续时间
4. 进入共振后的波动率变化
5. 后续波动率/方向收益
6. 在不同市场环境（牛/熊/震荡）和板块中的分布
7. 失败路径（压缩→H/L_only 后回到压缩，没到共振）
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
OUT_DIR = SCRIPT_DIR / "outputs" / "transition_paths"
FIG_DIR = OUT_DIR / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)

BOOT_N = 1000
BOOT_SEED = 42

STATE_ORDER = ["co_compress", "H_only", "L_only", "co_expand"]
STATE_LABELS = {"co_compress": "压缩", "H_only": "H独扩", "L_only": "L独扩", "co_expand": "共振"}
STATE_COLORS = {"co_compress": "#4C72B0", "H_only": "#DD8452", "L_only": "#55A868", "co_expand": "#C44E52"}


def cluster_ci(values):
    rng = np.random.default_rng(BOOT_SEED)
    v = np.array([x for x in values if not np.isnan(x)])
    if len(v) < 10:
        return np.nan, np.nan
    n = len(v)
    stats = np.empty(BOOT_N)
    for i in range(BOOT_N):
        stats[i] = rng.choice(v, size=n, replace=True).mean()
    return float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5))


# 复用 profile_quadrants_full 的因子计算
import importlib.util
spec = importlib.util.spec_from_file_location(
    "profile_quadrants_full", SCRIPT_DIR / "scripts" / "profile_quadrants_full.py"
)
pq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pq)


def build_panel():
    panels = []
    for f in sorted((ROOT / "project_data/market_data/csv").glob("*.1h.csv")):
        sym = f.name.replace(".tqsdk.1h.csv", "")
        p = pq.compute_panel(sym)
        if p is not None:
            panels.append(p)
    return pd.concat(panels, ignore_index=True)


def find_transitions(panel_sorted):
    """识别所有状态转换点，返回 (symbol, datetime, from_state, to_state, duration_in_state)。"""
    transitions = []
    for sym, sub in panel_sorted.groupby("symbol", sort=False):
        sub = sub.sort_values("datetime").reset_index(drop=True)
        states = sub["state_S"].values
        times = sub["datetime"].values
        h_norms = sub["H_norm"].values
        rbars = sub["R_bar"].values
        for i in range(1, len(states)):
            if states[i] != states[i-1]:
                # 找前一段开始位置
                j = i - 1
                while j > 0 and states[j] == states[i-1]:
                    j -= 1
                seg_start = j + 1 if states[j] != states[i-1] else j
                duration = i - seg_start
                transitions.append({
                    "symbol": sym,
                    "from_state": states[i-1],
                    "to_state": states[i],
                    "datetime": times[i],
                    "duration_in_from": duration,
                    "pre_H_norm": h_norms[i-1],
                    "post_H_norm": h_norms[i] if i < len(h_norms) else np.nan,
                    "pre_R_bar": rbars[i-1],
                    "post_R_bar": rbars[i] if i < len(rbars) else np.nan,
                    "sector": sub["sector"].iloc[0],
                    "year": pd.Timestamp(times[i]).year,
                    "regime": sub["regime"].iloc[0] if "regime" in sub.columns else None,
                    "bar_idx": i,
                })
    return pd.DataFrame(transitions)


def trace_paths_from_compress(panel_sorted, max_forward=60):
    """对每段 co_compress，追踪接下来 max_forward 根的状态路径。

    返回每段压缩的完整后续路径及关键事件：
    - first_exit_state：离开压缩后第一个状态
    - first_exit_after：多少根后离开
    - reached_co_expand：是否在 max_forward 内到达 co_expand
    - bars_to_expand：多少根后到达共振
    - path_type：H_path / L_path / direct / other / no_expand
    """
    paths = []
    for sym, sub in panel_sorted.groupby("symbol", sort=False):
        sub = sub.sort_values("datetime").reset_index(drop=True)
        states = sub["state_S"].values
        times = sub["datetime"].values
        h_norms = sub["H_norm"].values
        closes = sub["close"].values
        rbars = sub["R_bar"].values
        sector = sub["sector"].iloc[0]
        regime = sub["regime"].iloc[0] if "regime" in sub.columns else None

        # 找所有 co_compress 段起点
        i = 0
        while i < len(states):
            if states[i] != "co_compress":
                i += 1
                continue
            # 段开始
            seg_start = i
            while i < len(states) and states[i] == "co_compress":
                i += 1
            seg_end = i  # 第一个非压缩位置
            if seg_end >= len(states) - max_forward:
                break

            first_exit = states[seg_end]
            exit_after = seg_end - seg_start

            # 在 max_forward 内追踪
            reached = False
            bars_to_expand = None
            path_via = None
            for k in range(max_forward):
                idx = seg_end + k
                if idx >= len(states):
                    break
                if states[idx] == "co_expand":
                    reached = True
                    bars_to_expand = k
                    # 判断经过谁
                    if first_exit == "H_only":
                        path_via = "H_path"
                    elif first_exit == "L_only":
                        path_via = "L_path"
                    elif first_exit == "co_expand":
                        path_via = "direct"
                    else:
                        path_via = "other"
                    break

            if not reached:
                path_via = "no_expand"

            # 波动率路径
            pre_vol = np.nanmean(h_norms[max(0, seg_end-5):seg_end]) if seg_end >= 5 else np.nan
            exit_vol = h_norms[seg_end] if seg_end < len(h_norms) else np.nan
            expand_vol = h_norms[seg_end + bars_to_expand] if reached and seg_end + bars_to_expand < len(h_norms) else np.nan
            post5_vol = np.nanmean(h_norms[seg_end:seg_end+5]) if seg_end + 5 <= len(h_norms) else np.nan
            post20_vol = np.nanmean(h_norms[seg_end:seg_end+20]) if seg_end + 20 <= len(h_norms) else np.nan

            # 方向收益
            if seg_end + 20 < len(closes):
                ret_20 = closes[seg_end+20] / closes[seg_end] - 1
            else:
                ret_20 = np.nan
            if seg_end + 60 < len(closes):
                ret_60 = closes[seg_end+60] / closes[seg_end] - 1
            else:
                ret_60 = np.nan

            paths.append({
                "symbol": sym,
                "sector": sector,
                "regime": regime,
                "start_time": times[seg_start],
                "exit_time": times[seg_end],
                "first_exit": first_exit,
                "compress_duration": exit_after,
                "reached_expand": reached,
                "bars_to_expand": bars_to_expand,
                "path_type": path_via,
                "pre_vol": pre_vol,
                "exit_vol": exit_vol,
                "expand_vol": expand_vol,
                "post5_vol": post5_vol,
                "post20_vol": post20_vol,
                "vol_change_pct": (post20_vol / pre_vol - 1) if pre_vol and not np.isnan(pre_vol) else np.nan,
                "ret_20": ret_20,
                "ret_60": ret_60,
                "pre_R_bar": np.nanmean(rbars[max(0,seg_end-5):seg_end]) if seg_end >= 5 else np.nan,
            })
    return pd.DataFrame(paths)


def main():
    print("构建面板...", flush=True)
    panel = build_panel()
    panel = panel.sort_values(["symbol", "datetime"]).reset_index(drop=True)
    print(f"面板: {len(panel)} 行, {panel['symbol'].nunique()} 合约", flush=True)

    # ============================================================
    # 1. 转换频率
    # ============================================================
    print("\n=== 1. 状态转换频率 ===", flush=True)
    trans = find_transitions(panel)
    ct = pd.crosstab(trans["from_state"], trans["to_state"], normalize="index")
    ct = ct.reindex(index=STATE_ORDER, columns=STATE_ORDER, fill_value=0)
    ct.to_csv(OUT_DIR / "transition_matrix_expanded.csv")
    print(ct.round(3).to_string(), flush=True)

    # 平均在原状态的持续时间
    dur = trans.groupby("from_state")["duration_in_from"].agg(["count", "mean", "median"])
    dur.to_csv(OUT_DIR / "duration_before_exit.csv")
    print("\n离开前持续时间:")
    print(dur.round(2).to_string(), flush=True)

    # ============================================================
    # 2. 追踪路径
    # ============================================================
    print("\n=== 2. 压缩后路径追踪（60 根内）===", flush=True)
    paths = trace_paths_from_compress(panel, max_forward=60)
    paths.to_csv(OUT_DIR / "compress_paths.csv", index=False)
    print(f"总压缩段: {len(paths)}", flush=True)
    path_counts = paths["path_type"].value_counts(normalize=True)
    print("\n路径分布:")
    print(path_counts.round(4).to_string(), flush=True)

    # 到达共振的路径细分
    expanded = paths[paths["reached_expand"]]
    print(f"\n60 根内到达共振: {len(expanded)} ({len(expanded)/len(paths):.1%})")
    via_counts = expanded["path_type"].value_counts(normalize=True)
    print("\n到达共振的路径细分:")
    print(via_counts.round(4).to_string(), flush=True)

    # ============================================================
    # 3. H_path vs L_path 对比
    # ============================================================
    print("\n=== 3. H_path vs L_path vs direct 对比 ===", flush=True)
    compare_rows = []
    for ptype in ["H_path", "L_path", "direct"]:
        sub = expanded[expanded["path_type"] == ptype]
        if len(sub) < 5:
            continue
        row = {
            "path": ptype,
            "n": len(sub),
            "compress_dur_mean": sub["compress_duration"].mean(),
            "bars_to_expand_mean": sub["bars_to_expand"].mean(),
            "bars_to_expand_median": sub["bars_to_expand"].median(),
            "pre_vol_pct": sub["pre_vol"].mean() * 100,
            "exit_vol_pct": sub["exit_vol"].mean() * 100,
            "expand_vol_pct": sub["expand_vol"].mean() * 100,
            "post20_vol_pct": sub["post20_vol"].mean() * 100,
            "vol_change_pct": sub["vol_change_pct"].mean() * 100,
            "ret_20_pct": sub["ret_20"].mean() * 100,
            "ret_60_pct": sub["ret_60"].mean() * 100,
            "win_rate_60": float((sub["ret_60"] > 0).mean()),
        }
        compare_rows.append(row)
    compare_df = pd.DataFrame(compare_rows)
    compare_df.to_csv(OUT_DIR / "path_comparison.csv", index=False)
    print(compare_df.round(4).to_string(index=False), flush=True)

    # 加上 no_expand 对比
    no_exp = paths[~paths["reached_expand"]]
    if len(no_exp) > 5:
        print(f"\nno_expand: n={len(no_exp)}, post20_vol={no_exp['post20_vol'].mean()*100:.3f}%, "
              f"ret_60={no_exp['ret_60'].mean()*100:.3f}%, win60={(no_exp['ret_60']>0).mean():.1%}",
              flush=True)

    # ============================================================
    # 4. 分市场环境
    # ============================================================
    print("\n=== 4. 路径分布 by 市场环境 ===", flush=True)
    regime_path = paths.groupby(["regime", "path_type"]).size().unstack(fill_value=0)
    regime_pct = regime_path.div(regime_path.sum(axis=1), axis=0)
    regime_pct.to_csv(OUT_DIR / "path_by_regime.csv")
    print(regime_pct.round(3).to_string(), flush=True)

    # 各环境下 H_path vs L_path 的后续表现
    print("\n--- 各环境 ret_60 (%) ---", flush=True)
    regime_perf = paths[paths.reached_expand].groupby(["regime", "path_type"])["ret_60"].agg(
        ["count", "mean", "median"]
    ).reset_index()
    regime_perf["mean_pct"] = regime_perf["mean"] * 100
    print(regime_perf[["regime", "path_type", "count", "mean_pct"]].round(3).to_string(index=False), flush=True)

    # ============================================================
    # 5. 分板块
    # ============================================================
    print("\n=== 5. 路径分布 by 板块 ===", flush=True)
    sector_path = paths.groupby(["sector", "path_type"]).size().unstack(fill_value=0)
    sector_pct = sector_path.div(sector_path.sum(axis=1), axis=0)
    sector_pct.to_csv(OUT_DIR / "path_by_sector.csv")
    print(sector_pct.round(3).to_string(), flush=True)

    # ============================================================
    # 6. 波动率路径对比（事件时间）
    # ============================================================
    print("\n=== 6. 波动率路径（事件时间）===", flush=True)
    # 对 H_path / L_path，对齐 from compress 退出点，计算前后 20 根的 H_norm 均值
    event_vol = {}
    for ptype in ["H_path", "L_path", "direct"]:
        sub = expanded[expanded["path_type"] == ptype]
        vols_aligned = []
        for _, row in sub.iterrows():
            sym_df = panel[panel["symbol"] == row["symbol"]].sort_values("datetime").reset_index(drop=True)
            # 找 exit_time 在 sym_df 中的位置
            exit_idx_arr = sym_df.index[sym_df["datetime"] == row["exit_time"]].values
            if len(exit_idx_arr) == 0:
                continue
            exit_idx = exit_idx_arr[0]
            window = slice(max(0, exit_idx-10), min(len(sym_df), exit_idx+30))
            v = sym_df["H_norm"].iloc[window].values
            # 对齐到 exit_idx
            start = exit_idx - 10 if exit_idx >= 10 else 0
            aligned = np.full(40, np.nan)
            offset = start - (exit_idx - 10)
            aligned[offset:offset+len(v)] = v
            vols_aligned.append(aligned)
        if vols_aligned:
            event_vol[ptype] = np.nanmean(vols_aligned, axis=0) * 100

    event_vol_df = pd.DataFrame(event_vol)
    event_vol_df.index = range(-10, 30)
    event_vol_df.to_csv(OUT_DIR / "event_vol_path.csv")
    print(event_vol_df.iloc[::5].round(3).to_string(), flush=True)

    # ============================================================
    # 7. 失败路径：H/L_only 后回压缩
    # ============================================================
    print("\n=== 7. 失败路径（独扩后回压缩）===", flush=True)
    # first_exit 是 H_only 或 L_only，但没到共振
    fail = paths[paths["path_type"] == "no_expand"]
    fail_by_exit = fail.groupby("first_exit").agg(
        n=("symbol", "count"),
        compress_dur=("compress_duration", "mean"),
        post5_vol=("post5_vol", "mean"),
        post20_vol=("post20_vol", "mean"),
        ret_60=("ret_60", "mean"),
        win_rate_60=("ret_60", lambda x: (x > 0).mean()),
    ).reset_index()
    fail_by_exit["post20_vol_pct"] = fail_by_exit["post20_vol"] * 100
    fail_by_exit["ret_60_pct"] = fail_by_exit["ret_60"] * 100
    fail_by_exit.to_csv(OUT_DIR / "failed_paths.csv", index=False)
    print(fail_by_exit[["first_exit", "n", "compress_dur", "post20_vol_pct", "ret_60_pct", "win_rate_60"]].round(4).to_string(index=False), flush=True)

    # ============================================================
    # 图表
    # ============================================================
    print("\n生成图表...", flush=True)

    # Fig 1: H/L/direct 波动率事件路径
    if event_vol:
        fig, ax = plt.subplots(figsize=(11, 6))
        for ptype, color in [("H_path", "#DD8452"), ("L_path", "#55A868"), ("direct", "#C44E52")]:
            if ptype in event_vol:
                ax.plot(event_vol_df.index, event_vol[ptype], marker="o", markersize=3,
                        label=ptype, color=color, linewidth=1.8)
        ax.axvline(0, color="black", linestyle="--", linewidth=0.8, alpha=0.7, label="离开压缩")
        ax.set_xlabel("相对退出压缩的时间（根 1h）")
        ax.set_ylabel("H_norm (%)")
        ax.set_title("压缩退出前后的波动率路径")
        ax.legend()
        ax.grid(alpha=0.3)
        plt.tight_layout()
        plt.savefig(FIG_DIR / "fig1_event_vol.png", dpi=150, bbox_inches="tight")
        plt.close()

    # Fig 2: 路径占比（整体 + by regime）
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    path_order = ["H_path", "L_path", "direct", "no_expand"]
    path_colors = {"H_path": "#DD8452", "L_path": "#55A868", "direct": "#C44E52", "no_expand": "#888888"}
    pct = path_counts.reindex(path_order).fillna(0)
    axes[0].bar(range(len(pct)), pct.values * 100, color=[path_colors[p] for p in path_order])
    axes[0].set_xticks(range(len(pct)))
    axes[0].set_xticklabels(path_order, rotation=15)
    axes[0].set_ylabel("%")
    axes[0].set_title("整体路径分布")
    axes[0].grid(axis="y", alpha=0.3)
    for i, v in enumerate(pct.values * 100):
        axes[0].text(i, v + 1, f"{v:.1f}%", ha="center", fontsize=9)

    for regime in regime_pct.index:
        if regime in regime_pct.index:
            vals = [regime_pct.loc[regime].get(p, 0)*100 for p in path_order if p in regime_pct.columns]
            x = np.arange(len(vals))
            axes[1].plot(x, vals, marker="o", label=str(regime))
    axes[1].set_xticks(range(len([p for p in path_order if p in regime_pct.columns])))
    axes[1].set_xticklabels([p for p in path_order if p in regime_pct.columns], rotation=15)
    axes[1].set_ylabel("%")
    axes[1].set_title("路径分布 by 市场环境")
    axes[1].legend()
    axes[1].grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig2_path_distribution.png", dpi=150, bbox_inches="tight")
    plt.close()

    # Fig 3: 到达共振的时间分布
    fig, ax = plt.subplots(figsize=(10, 6))
    for ptype, color in [("H_path", "#DD8452"), ("L_path", "#55A868"), ("direct", "#C44E52")]:
        sub = expanded[expanded.path_type == ptype]
        if len(sub) > 10:
            ax.hist(sub["bars_to_expand"], bins=30, alpha=0.5, density=True, label=ptype, color=color)
    ax.set_xlabel("离开压缩后到达共振的根数")
    ax.set_ylabel("密度")
    ax.set_title("到达共振的时间分布")
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig3_time_to_expand.png", dpi=150, bbox_inches="tight")
    plt.close()

    # Fig 4: 板块热力图
    fig, ax = plt.subplots(figsize=(10, 6))
    im = ax.imshow(sector_pct.values, cmap="YlOrRd", aspect="auto", vmin=0, vmax=0.7)
    ax.set_xticks(range(len(sector_pct.columns)))
    ax.set_xticklabels(sector_pct.columns, rotation=30, ha="right")
    ax.set_yticks(range(len(sector_pct.index)))
    ax.set_yticklabels(sector_pct.index)
    for i in range(len(sector_pct.index)):
        for j in range(len(sector_pct.columns)):
            v = sector_pct.iloc[i, j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                    color="white" if v > 0.4 else "black", fontsize=9)
    plt.colorbar(im, ax=ax, fraction=0.046)
    ax.set_title("板块 × 路径分布")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig4_sector_heatmap.png", dpi=150, bbox_inches="tight")
    plt.close()

    # Summary
    summary = {
        "n_compress_segments": int(len(paths)),
        "n_reached_expand": int(len(expanded)),
        "expand_rate": float(len(expanded) / len(paths)),
        "path_distribution": path_counts.to_dict(),
        "via_distribution": via_counts.to_dict() if len(expanded) > 0 else {},
        "comparison": compare_df.to_dict("records"),
        "regime_distribution": regime_pct.to_dict(),
        "failed_paths": fail_by_exit[["first_exit", "n", "ret_60_pct"]].to_dict("records"),
    }
    with open(OUT_DIR / "paths_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n输出已保存到 {OUT_DIR}", flush=True)


if __name__ == "__main__":
    main()
