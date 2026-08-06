"""
OI（持仓量）× 成交量放量研究

核心问题：
1. 放量时 OI 是增还是减？增加 = 新资金进场（趋势可能延续），减少 = 仓位了结（可能反转）
2. 在高 s_pre + 高 MADEV + 放量条件下，OI 变化能否区分"好放量"和"坏放量"
3. OI 变化对未来收益的独立预测力（控制 MADEV、Z 后）

四个 OI 维度：
- dOI_1    ：当前 bar OI 变化（close_oi - open_oi），即这根 K 线内的持仓变化
- dOI_N    ：过去 N 根 bar 的累计 OI 变化率（normalize by OI level）
- dOI_z    ：dOI 的同时段 z-score（和成交量 z 同样口径）
- OI_trend ：过去 N 根 OI 的线性斜率 / OI 水平

输出到 stdout 和 outputs/oi_results.json
"""
from __future__ import annotations

import json
import math
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))

from workspace.common.symbol_utils import extract_contract_prefix  # noqa: E402
from workspace.data.output_paths import market_csv_dir  # noqa: E402

N_Z = 20          # 成交量/OI z-score 回看
H = 100           # 未来收益 bar 数
N_OI = 20         # OI 趋势窗口
N_BOOT = 500


def load(p: Path) -> pd.DataFrame:
    d = pd.read_csv(p)
    d["datetime"] = pd.to_datetime(d["datetime"])
    d = d.sort_values("datetime").reset_index(drop=True)
    d["lr"] = np.log(d.close).diff()
    v, h = d.volume, d.datetime.dt.hour

    # 同时段成交量 z
    mu = v.groupby(h).shift(1).groupby(h).transform(
        lambda s: s.rolling(N_Z, min_periods=N_Z).mean()
    )
    sd = v.groupby(h).shift(1).groupby(h).transform(
        lambda s: s.rolling(N_Z, min_periods=N_Z).std(ddof=1)
    )
    d["z"] = (v - mu) / sd

    # OI：用 close_oi 作为 bar 结束时持仓
    oi = d["close_oi"].astype(float).copy()
    d["oi"] = oi

    # bar 内 OI 变化
    d["doi_1"] = d["close_oi"].astype(float) - d["open_oi"].astype(float)

    # OI 比率变化（过去 N 根）
    d["oi_ret"] = oi.pct_change()

    # 同时段 doi_1 z-score
    doi = d["doi_1"].astype(float)
    mu_doi = doi.groupby(h).shift(1).groupby(h).transform(
        lambda s: s.rolling(N_Z, min_periods=N_Z).mean()
    )
    sd_doi = doi.groupby(h).shift(1).groupby(h).transform(
        lambda s: s.rolling(N_Z, min_periods=N_Z).std(ddof=1)
    )
    d["doi_z"] = (doi - mu_doi) / sd_doi

    # 过去 N_OI 根累计 OI 变化率
    d["oi_cum_change"] = (oi - oi.shift(N_OI)) / oi.shift(N_OI)

    # OI 趋势：过去 N_OI 根线性斜率 / 平均 OI
    def _slope(y: np.ndarray) -> float:
        if len(y) < N_OI or not np.all(np.isfinite(y)):
            return np.nan
        x = np.arange(N_OI)
        return float(np.polyfit(x, y, 1)[0] / max(abs(np.mean(y)), 1e-9))

    d["oi_slope"] = oi.rolling(N_OI).apply(_slope, raw=True)

    return d


def build_events() -> pd.DataFrame:
    recs = []
    csv_dir = market_csv_dir()
    for p in sorted(csv_dir.glob("*.1h.csv")):
        try:
            head = pd.read_csv(p, nrows=1, usecols=["datetime", "close_oi"])
        except Exception:
            continue
        # 需要有 OI 数据
        if "close_oi" not in head.columns:
            continue
        try:
            full = pd.read_csv(p, usecols=["datetime", "close_oi"])
            if (full["close_oi"].fillna(0) == 0).all():
                continue
        except Exception:
            continue

        if len(pd.read_csv(p, usecols=["datetime"])) < 420:
            continue
        sym = p.name.split(".tqsdk.1h.csv")[0]
        pfx = extract_contract_prefix(sym) or ""
        d = load(p)
        c = d.close
        r = d.lr.to_numpy()
        z = d.z.to_numpy()
        doi_z = d.doi_z.to_numpy()
        oi_cum = d.oi_cum_change.to_numpy()
        oi_slope = d.oi_slope.to_numpy()
        ts = d.datetime

        ma120 = c.rolling(120).mean().to_numpy()
        madev = (c.to_numpy() - ma120) / ma120

        n = len(d)
        for t in range(N_Z + H + 1, n - H):
            zv = z[t]
            if not math.isfinite(zv):
                continue
            pre = r[t - 100 : t]
            if not np.all(np.isfinite(pre)):
                continue
            s_sd = pre.std(ddof=1)
            if s_sd <= 0:
                continue
            s_pre = pre.mean() / s_sd
            if not math.isfinite(madev[t]):
                continue
            if not math.isfinite(doi_z[t]):
                continue
            recs.append(
                dict(
                    sym=sym,
                    pfx=pfx,
                    t=t,
                    ts=ts.iloc[t],
                    z=float(zv),
                    doi_z=float(doi_z[t]),
                    oi_cum=float(oi_cum[t]),
                    oi_slope=float(oi_slope[t]),
                    s_pre=float(s_pre),
                    madev=float(madev[t]),
                    pre_cum=float(pre.sum()),
                    r100=float(r[t + 1 : t + 1 + H].sum()),
                )
            )
    return pd.DataFrame(recs)


def sp_ic(x: pd.Series, y: pd.Series) -> float:
    if len(x) < 20 or x.std() < 1e-10 or y.std() < 1e-10:
        return float("nan")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return float(spearmanr(x, y).correlation)


def boot(vals: np.ndarray, seed: int = 42) -> tuple[float, float, float]:
    rng = np.random.default_rng(seed)
    a = np.asarray(vals, float)
    a = a[np.isfinite(a)]
    if len(a) < 10:
        return float("nan"), float("nan"), float("nan")
    idx = rng.integers(0, len(a), size=(N_BOOT, len(a)))
    b = a[idx].mean(axis=1)
    return float(a.mean()), float(np.quantile(b, 0.025)), float(np.quantile(b, 0.975))


def fmt(v: float, pct: bool = True) -> str:
    if not math.isfinite(v):
        return "  nan"
    return f"{v*100:+.2f}%" if pct else f"{v:+.3f}"


def main() -> None:
    out_dir = Path(__file__).resolve().parent.parent / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    df = build_events()
    print(f"total events: {len(df)}")
    print(f"date range: {df.ts.min()} ~ {df.ts.max()}")
    print(f"symbols: {df.sym.nunique()}")

    df["vg"] = pd.cut(
        df.z,
        bins=[-np.inf, -0.5, 0.5, 1.5, np.inf],
        labels=["缩量", "正常", "放量", "极端"],
    )

    results: dict = {"n_events": int(len(df)), "sections": {}}

    # =====================================================
    # 1. 放量时 OI 是增还是减？
    # =====================================================
    print("\n" + "=" * 80)
    print("检验 1：各成交量组的 OI 变化")
    print("=" * 80)
    print(f"{'vg':>6} {'n':>8} {'doi_z mean':>12} {'oi_cum mean':>14} {'oi_slope mean':>16}")
    sec1 = {}
    for vg in ["缩量", "正常", "放量", "极端"]:
        sub = df[df.vg == vg]
        line = (
            f"{vg:>6} {len(sub):>8} "
            f"{sub.doi_z.mean():>+12.3f} "
            f"{sub.oi_cum.mean()*100:>+13.2f}% "
            f"{sub.oi_slope.mean():>+16.5f}"
        )
        print(line)
        sec1[vg] = dict(
            n=int(len(sub)),
            doi_z=float(sub.doi_z.mean()),
            oi_cum=float(sub.oi_cum.mean()),
            oi_slope=float(sub.oi_slope.mean()),
        )
    results["sections"]["1_oi_by_volume"] = sec1

    # =====================================================
    # 2. 在高 s_pre + 高 MADEV + 放量条件下，OI 能否区分好坏
    # =====================================================
    print("\n" + "=" * 80)
    print("检验 2：高 s_pre + 放量下，OI 方向对未来收益的影响")
    print("=" * 80)
    high_s = df[df.s_pre >= 0.10].copy()
    print(f"高 s_pre 样本: {len(high_s)}")

    # 在高 s_pre + 放量/极端组内按 doi_z 分三组
    spike = high_s[high_s.vg.isin(["放量", "极端"])].copy()
    print(f"高 s_pre + 放量/极端: {len(spike)}")

    if len(spike) > 30:
        spike["oi_g"] = pd.qcut(
            spike.doi_z, 3, labels=["OI减仓", "OI中性", "OI增仓"]
        )
        # 按 MADEV 三分位
        spike["mq"] = pd.qcut(spike.madev, 3, labels=["低", "中", "高"])

        print("\n  2a. 高 s_pre + 放量/极端，按 OI 分组的 mean r100")
        print(f"  {'OI组':>10} {'n':>6} {'mean':>10} {'CI lo':>10} {'CI hi':>10} {'% pos':>8}")
        sec2a = {}
        for og in ["OI减仓", "OI中性", "OI增仓"]:
            sub = spike[spike.oi_g == og]
            if len(sub) > 5:
                m, lo, hi = boot(sub.r100.values)
                pct_pos = float((sub.r100 > 0).mean())
                print(
                    f"  {og:>10} {len(sub):>6} {fmt(m):>10} {fmt(lo):>10} "
                    f"{fmt(hi):>10} {pct_pos*100:>7.1f}%"
                )
                sec2a[og] = dict(
                    n=int(len(sub)), mean=m, ci_lo=lo, ci_hi=hi, pct_pos=pct_pos
                )
        results["sections"]["2a_high_s_spike_by_oi"] = sec2a

        print("\n  2b. 高 s_pre + 放量/极端，OI 组 × MADEV 分位 (mean r100)")
        print(f"  {'':>10} {'低MADEV':>12} {'中MADEV':>12} {'高MADEV':>12}")
        sec2b = {}
        for og in ["OI减仓", "OI中性", "OI增仓"]:
            line = f"  {og:>10}"
            row = {}
            for mq in ["低", "中", "高"]:
                sub = spike[(spike.oi_g == og) & (spike.mq == mq)]
                if len(sub) >= 5:
                    m = sub.r100.mean()
                    line += f" {m*100:>+10.2f}%"
                    row[mq] = dict(n=int(len(sub)), mean=float(m))
                else:
                    line += f" {'(n='+str(len(sub))+')':>10}"
                    row[mq] = dict(n=int(len(sub)), mean=None)
            print(line)
            sec2b[og] = row
        results["sections"]["2b_oi_x_madev"] = sec2b

        # OI 极端组合：高 MADEV + 放量 + OI 增 vs 减
        print("\n  2c. 高 s_pre + 高 MADEV（前 1/3）+ 放量/极端 的极端 OI 组合")
        high_madev = spike[spike.mq == "高"]
        print(f"  样本: {len(high_madev)}")
        sec2c = {}
        for og in ["OI减仓", "OI中性", "OI增仓"]:
            sub = high_madev[high_madev.oi_g == og]
            if len(sub) >= 3:
                m, lo, hi = boot(sub.r100.values)
                pct_pos = float((sub.r100 > 0).mean())
                print(
                    f"    {og}: n={len(sub)}, mean={fmt(m)}, "
                    f"CI=[{fmt(lo)},{fmt(hi)}], %pos={pct_pos*100:.1f}%"
                )
                sec2c[og] = dict(
                    n=int(len(sub)), mean=m, ci_lo=lo, ci_hi=hi, pct_pos=pct_pos
                )
        results["sections"]["2c_high_madev_extreme_oi"] = sec2c

    # =====================================================
    # 3. 多元 IC：控制 MADEV、Z 后 OI 还有没有预测力
    # =====================================================
    print("\n" + "=" * 80)
    print("检验 3：IC 相关（Spearman）")
    print("=" * 80)
    sec3 = {}
    for label, sub in [("全样本", df), ("高 s_pre", high_s), ("高s+放量", spike if len(spike) > 30 else high_s)]:
        print(f"\n  {label} (n={len(sub)})")
        print(f"  {'变量':>12} {'IC(r100)':>12}")
        row = {}
        for var, name in [
            ("z", "成交量 z"),
            ("madev", "MADEV"),
            ("doi_z", "OI z"),
            ("oi_cum", "OI 累计变化"),
            ("oi_slope", "OI 斜率"),
        ]:
            ic = sp_ic(sub[var], sub.r100)
            print(f"  {name:>12} {ic:>+12.4f}")
            row[name] = ic
        sec3[label] = row
    results["sections"]["3_ic"] = sec3

    # =====================================================
    # 4. R² 消融：MADEV / Z / OI 各自贡献
    # =====================================================
    print("\n" + "=" * 80)
    print("检验 4：高 s_pre 样本 R² 消融（线性回归，numpy lstsq）")
    print("=" * 80)
    cols = ["z", "madev", "doi_z"]
    clean = high_s[cols + ["r100"]].replace([np.inf, -np.inf], np.nan).dropna()
    print(f"  有效样本: {len(clean)}")

    def ols_r2(xvars: list[str], data: pd.DataFrame = clean) -> tuple[float, np.ndarray]:
        X = np.column_stack([np.ones(len(data))] + [data[v].values for v in xvars])
        y = data.r100.values
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        yhat = X @ beta
        ss_res = float(np.sum((y - yhat) ** 2))
        ss_tot = float(np.sum((y - y.mean()) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
        return r2, beta[1:]  # type: ignore[return-value]

    sec4 = {}
    for label, xvars in [
        ("Z only", ["z"]),
        ("MADEV only", ["madev"]),
        ("OI only", ["doi_z"]),
        ("Z+MADEV", ["z", "madev"]),
        ("Z+OI", ["z", "doi_z"]),
        ("MADEV+OI", ["madev", "doi_z"]),
        ("Z+MADEV+OI", ["z", "madev", "doi_z"]),
    ]:
        r2, beta = ols_r2(xvars)
        print(f"  {label:>16}: R²={r2:.4f}")
        sec4[label] = float(r2)
    results["sections"]["4_r2_ablation"] = sec4

    # 带交互项：Z*OI
    print("\n  带交互项：")
    clean2 = clean.copy()
    clean2["z_x_oi"] = clean2["z"] * clean2["doi_z"]
    r2_int, beta_int = ols_r2(
        ["z", "madev", "doi_z", "z_x_oi"], data=clean2
    )
    print(f"  {'Z+MADEV+OI+Z×OI':>20}: R²={r2_int:.4f}, β_Z×OI={beta_int[-1]:+.6f}")
    sec4["Z+MADEV+OI+Z×OI"] = float(r2_int)
    sec4["beta_z_x_oi"] = float(beta_int[-1])

    # =====================================================
    # 5. 低 s_pre 镜像：放量+减仓=空头回补？放量+增仓=新空进场？
    # =====================================================
    print("\n" + "=" * 80)
    print("检验 5：低 s_pre 镜像（下跌趋势放量 + OI 方向）")
    print("=" * 80)
    low_s = df[df.s_pre <= -0.10].copy()
    low_spike = low_s[low_s.vg.isin(["放量", "极端"])].copy()
    print(f"低 s_pre 样本: {len(low_s)}, 低 s_pre + 放量/极端: {len(low_spike)}")

    sec5 = {}
    if len(low_spike) > 30:
        low_spike["oi_g"] = pd.qcut(
            low_spike.doi_z, 3, labels=["OI减仓", "OI中性", "OI增仓"]
        )
        low_spike["mq"] = pd.qcut(low_spike.madev, 3, labels=["低", "中", "高"])

        print(f"\n  5a. 低 s_pre + 放量/极端，按 OI 分组的 mean r100")
        print(f"  {'OI组':>10} {'n':>6} {'mean':>10} {'CI lo':>10} {'CI hi':>10} {'% pos':>8}")
        sec5a = {}
        for og in ["OI减仓", "OI中性", "OI增仓"]:
            sub = low_spike[low_spike.oi_g == og]
            if len(sub) > 5:
                m, lo, hi = boot(sub.r100.values)
                pct_pos = float((sub.r100 > 0).mean())
                print(
                    f"  {og:>10} {len(sub):>6} {fmt(m):>10} {fmt(lo):>10} "
                    f"{fmt(hi):>10} {pct_pos*100:>7.1f}%"
                )
                sec5a[og] = dict(
                    n=int(len(sub)), mean=m, ci_lo=lo, ci_hi=hi, pct_pos=pct_pos
                )
        sec5["5a_low_s_spike_by_oi"] = sec5a

        print("\n  5b. 低 s_pre + 低 MADEV（远低于均线）+ 放量/极端，按 OI 分组")
        low_madev = low_spike[low_spike.mq == "低"]
        print(f"  样本: {len(low_madev)}")
        sec5b = {}
        for og in ["OI减仓", "OI中性", "OI增仓"]:
            sub = low_madev[low_madev.oi_g == og]
            if len(sub) >= 3:
                m, lo, hi = boot(sub.r100.values)
                pct_pos = float((sub.r100 > 0).mean())
                print(
                    f"    {og}: n={len(sub)}, mean={fmt(m)}, "
                    f"CI=[{fmt(lo)},{fmt(hi)}], %pos={pct_pos*100:.1f}%"
                )
                sec5b[og] = dict(
                    n=int(len(sub)), mean=m, ci_lo=lo, ci_hi=hi, pct_pos=pct_pos
                )
        sec5["5b_low_madev_extreme_oi"] = sec5b
    results["sections"]["5_low_s_mirror"] = sec5

    # 保存
    out_file = out_dir / "oi_results.json"
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n结果已保存: {out_file}")


if __name__ == "__main__":
    main()
