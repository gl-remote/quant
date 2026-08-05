"""
生成核心结论可视化：
1. 主图：高MADEV组下，缩量 vs 放量的收益分布对比（密度+kde），
   直观展示均值漂移（-2.54%）远大于方差放大（+0.71%）
2. 辅图：回归路径——MADEV 随时间收敛，放量 vs 缩量
3. 辅图：尾部概率柱状图
输出到 docs/research/themes/volume-spike-regime-shift/figures/
"""
from __future__ import annotations
import sys, math
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch
from scipy.stats import gaussian_kde, norm

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))
from workspace.common.symbol_utils import extract_contract_prefix
from workspace.data.output_paths import market_csv_dir

N = 20; H = 100

# Use English labels to avoid CJK font issues
plt.rcParams["font.family"] = ["DejaVu Sans", "Arial", "Helvetica"]
plt.rcParams["axes.unicode_minus"] = False


def load(p):
    d = pd.read_csv(p)
    d["datetime"] = pd.to_datetime(d["datetime"])
    d = d.sort_values("datetime").reset_index(drop=True)
    d["lr"] = np.log(d.close).diff()
    v, h = d.volume, d.datetime.dt.hour
    mu = v.groupby(h).shift(1).groupby(h).transform(lambda s: s.rolling(N,min_periods=N).mean())
    sd = v.groupby(h).shift(1).groupby(h).transform(lambda s: s.rolling(N,min_periods=N).std(ddof=1))
    d["z"] = (v-mu)/sd
    return d


def build():
    recs = []
    for p in sorted(market_csv_dir().glob("*.1h.csv")):
        try:
            head = pd.read_csv(p, usecols=["datetime"])
        except: continue
        if len(head) < 420: continue
        sym = p.name.split(".tqsdk.1h.csv")[0]
        pfx = extract_contract_prefix(sym) or ""
        d = load(p)
        c = d.close; r = d.lr.to_numpy(); z = d.z.to_numpy()
        ma120 = c.rolling(120).mean().to_numpy()
        ma200 = c.rolling(200).mean().to_numpy()
        c_arr = c.to_numpy()
        n = len(d)
        for t in range(N+H+1, n-H):
            zv = z[t]
            if not math.isfinite(zv): continue
            pre = r[t-100:t]
            if not np.all(np.isfinite(pre)): continue
            s_sd = pre.std(ddof=1)
            if s_sd <= 0: continue
            s_pre = pre.mean()/s_sd
            if s_pre < 0.10: continue
            if not (math.isfinite(ma120[t]) and ma120[t] > 0): continue
            madev = float((c_arr[t]-ma120[t])/ma120[t])
            fut = r[t+1:t+1+H]
            # path of MADEV at intermediate horizons
            path = {}
            for h in [0,20,40,60,80,100]:
                idx = t+h
                if idx < n and math.isfinite(ma120[idx]) and ma120[idx] > 0:
                    path[f"dev{h}"] = float((c_arr[idx]-ma120[idx])/ma120[idx])
                else:
                    path[f"dev{h}"] = np.nan
            recs.append(dict(sym=sym, pfx=pfx, z=float(zv), s_pre=float(s_pre),
                madev=madev, r100=float(fut.sum()), **path))
    return pd.DataFrame(recs)


def main():
    out_dir = REPO_ROOT / "docs/research/themes/volume-spike-regime-shift/figures"
    out_dir.mkdir(parents=True, exist_ok=True)

    df = build()
    print(f"events: {len(df)}")
    hi = df[df.s_pre >= 0.10].copy()
    # Median split (consistent with r2_uncertainty_test.py)
    med = hi.madev.median()
    hi_hi = hi[hi.madev >= med]  # high MADEV (top 50%)
    print(f"MADEV median={med:.4f}")
    # volume groups
    vlow = hi_hi[hi_hi.z < -0.5]
    normal = hi_hi[abs(hi_hi.z) < 0.5]
    spike = hi_hi[hi_hi.z >= 1.5]
    extreme = hi_hi[hi_hi.z >= 2.5]

    print(f"high MADEV groups: vlow={len(vlow)} normal={len(normal)} spike={len(spike)} extreme={len(extreme)}")

    # ========== FIGURE 1: Distribution comparison ==========
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5), gridspec_kw={"width_ratios":[2, 1]})

    # Left: KDE distributions
    ax = axes[0]
    colors = {"Low volume (z<-0.5)": "#2196F3",
              "High volume (z>=1.5)": "#E53935",
              "Normal (|z|<0.5)": "#9E9E9E"}
    datasets = [("Low volume (z<-0.5)", vlow.r100),
                ("Normal (|z|<0.5)", normal.r100),
                ("High volume (z>=1.5)", spike.r100)]
    xgrid = np.linspace(-0.10, 0.08, 500)
    for label, data in datasets:
        data = data.dropna().values
        if len(data) < 10: continue
        kde = gaussian_kde(data, bw_method=0.35)
        ax.plot(xgrid*100, kde(xgrid), color=colors[label], lw=2.2, label=label)
        ax.fill_between(xgrid*100, kde(xgrid), alpha=0.12, color=colors[label])
        m = data.mean()
        ax.axvline(m*100, color=colors[label], ls="--", lw=1.2, alpha=0.7)

    means = [d[1].mean() for d in datasets if len(d[1])>10]
    ax.annotate("", xy=(means[2]*100, 5), xytext=(means[0]*100, 5),
                arrowprops=dict(arrowstyle="<->", color="black", lw=1.5))
    ax.text((means[0]+means[2])/2*100, 6.5, f"Mean shift\n{(means[2]-means[0])*100:+.2f}%",
            ha="center", va="bottom", fontsize=10, fontweight="bold", color="#333")

    ax.set_xlabel("Forward 100-bar return (%)", fontsize=11)
    ax.set_ylabel("Density", fontsize=11)
    ax.set_title("Return Distribution: Above-Median MADEV + Volume Conditioning\n(Mean shift dominates variance change)",
                 fontsize=12, fontweight="bold")
    ax.legend(loc="upper left", fontsize=9, framealpha=0.9)
    ax.set_xlim(-8, 6)
    ax.axvline(0, color="black", lw=0.5, ls="-")

    # Add stats text box
    stats_text = (f"Low vol:  mean={vlow.r100.mean()*100:+.2f}%  std={vlow.r100.std()*100:.2f}%\n"
                  f"Normal:   mean={normal.r100.mean()*100:+.2f}%  std={normal.r100.std()*100:.2f}%\n"
                  f"High vol: mean={spike.r100.mean()*100:+.2f}%  std={spike.r100.std()*100:.2f}%\n\n"
                  f"Mean shift = {(spike.r100.mean()-vlow.r100.mean())*100:+.2f}%\n"
                  f"Std change = {(spike.r100.std()-vlow.r100.std())*100:+.2f}%\n"
                  f"Ratio = {abs((spike.r100.mean()-vlow.r100.mean())/(spike.r100.std()-vlow.r100.std())):.1f}x")
    ax.text(0.98, 0.97, stats_text, transform=ax.transAxes, fontsize=8.5,
            va="top", ha="right", family="monospace",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="#F5F5F5", edgecolor="#CCC"))

    # Right: bar chart of mean vs std change
    ax2 = axes[1]
    categories = ["Mean shift\n(1st moment)", "Std change\n(2nd moment)"]
    values = [(spike.r100.mean()-vlow.r100.mean())*100,
              (spike.r100.std()-vlow.r100.std())*100]
    bars = ax2.bar(categories, values, color=["#E53935", "#FF9800"], width=0.5, edgecolor="black", lw=0.5)
    for bar, val in zip(bars, values):
        ax2.text(bar.get_x()+bar.get_width()/2, bar.get_height()-0.15 if val<0 else bar.get_height()+0.05,
                 f"{val:+.2f}%", ha="center", va="top" if val<0 else "bottom",
                 fontsize=11, fontweight="bold")
    ax2.axhline(0, color="black", lw=0.8)
    ax2.set_ylabel("Change (high vol - low vol), %", fontsize=10)
    ax2.set_title("First moment dominates", fontsize=11, fontweight="bold")
    ax2.set_ylim(-3.2, 0.5)

    plt.tight_layout()
    fig.savefig(out_dir/"mean_shift_vs_variance.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {out_dir}/mean_shift_vs_variance.png")

    # ========== FIGURE 2: Regression path ==========
    fig2, ax = plt.subplots(figsize=(9, 5.5))
    horizons = [0, 20, 40, 60, 80, 100]
    days = [h*5/60/5 for h in horizons]  # approx trading days (100 5m bars = 20 days for 1h... 100 1h bars = 20 trading days)
    # Actually for 1h bars with ~5h/day, 100 bars = 20 days
    days = [h/5 for h in horizons]  # 5 bars per trading day (1h)

    for label, data, color, marker in [
        ("Low volume (z<-0.5)", vlow, "#2196F3", "o"),
        ("Normal (|z|<0.5)", normal, "#9E9E9E", "s"),
        ("High volume (z>=2.5)", extreme, "#E53935", "^"),
        ("High volume (z>=1.5)", spike, "#FF7043", "v"),
    ]:
        means = []
        sems = []
        for h in horizons:
            vals = data[f"dev{h}"].dropna().values
            if len(vals) > 5:
                means.append(vals.mean()*100)
                sems.append(vals.std()/math.sqrt(len(vals))*100)
            else:
                means.append(np.nan); sems.append(np.nan)
        means = np.array(means); sems = np.array(sems)
        ax.plot(days, means, color=color, marker=marker, lw=2, markersize=7, label=label)
        ax.fill_between(days, means-sems, means+sems, color=color, alpha=0.12)

    ax.axhline(0, color="black", lw=1, ls="-", label="MA120")
    ax.axvspan(8, 12, alpha=0.08, color="red")
    ax.text(10, 7.5, "Crossing\n8-12 days", ha="center", fontsize=9, color="#C62828")

    ax.set_xlabel("Bars after volume event (trading days)", fontsize=11)
    ax.set_ylabel("Deviation from MA120 (%)", fontsize=11)
    ax.set_title("Mean-Reversion Path (above-median MADEV)\nPrice converges to MA120 and overshoots",
                 fontsize=12, fontweight="bold")
    ax.legend(loc="upper right", fontsize=9)
    ax.set_xlim(-0.5, 21)
    ax.grid(True, alpha=0.2)

    plt.tight_layout()
    fig2.savefig(out_dir/"reversion_path.png", dpi=150, bbox_inches="tight")
    plt.close(fig2)
    print(f"  saved {out_dir}/reversion_path.png")

    # ========== FIGURE 3: Tail probabilities ==========
    fig3, ax = plt.subplots(figsize=(9, 5))
    groups = [("Low vol\n(z<-0.5)", vlow),
              ("Normal\n(|z|<0.5)", normal),
              ("High vol\n(1.5<=z<2.5)", spike),
              ("Extreme\n(z>=2.5)", extreme)]
    x = np.arange(len(groups))
    w = 0.28
    up_probs = [(g.r100 > 0.03).mean()*100 for _,g in groups]
    down_probs = [(g.r100 < -0.03).mean()*100 for _,g in groups]
    abs_probs = [(g.r100.abs() > 0.03).mean()*100 for _,g in groups]

    ax.bar(x-w, up_probs, w, label="P(r > +3%)", color="#4CAF50", edgecolor="black", lw=0.5)
    ax.bar(x, down_probs, w, label="P(r < -3%)", color="#E53935", edgecolor="black", lw=0.5)
    ax.bar(x+w, abs_probs, w, label="P(|r| > 3%)", color="#757575", alpha=0.7, edgecolor="black", lw=0.5)

    for i,(u,d,a) in enumerate(zip(up_probs, down_probs, abs_probs)):
        ax.text(i-w, u+0.5, f"{u:.0f}%", ha="center", fontsize=9)
        ax.text(i, d+0.5, f"{d:.0f}%", ha="center", fontsize=9)
        ax.text(i+w, a+0.5, f"{a:.0f}%", ha="center", fontsize=9)

    ax.set_xticks(x)
    ax.set_xticklabels([g[0] for g in groups])
    ax.set_ylabel("Probability (%)", fontsize=11)
    ax.set_title("Tail Probabilities (above-median MADEV)\nAsymmetric downside thickening, not symmetric variance increase",
                 fontsize=12, fontweight="bold")
    ax.legend(fontsize=10)
    ax.set_ylim(0, 38)
    ax.grid(True, alpha=0.2, axis="y")

    plt.tight_layout()
    fig3.savefig(out_dir/"tail_probabilities.png", dpi=150, bbox_inches="tight")
    plt.close(fig3)
    print(f"  saved {out_dir}/tail_probabilities.png")

    print("\nAll figures generated.")


if __name__ == "__main__":
    main()
