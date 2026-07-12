"""
研究 D2 = A3_skew 统计量自身的分布（逐事件/逐合约的 skew 值序列）。
目标：用数据检验假设 "A3_skew ~ t 分布 / 类 t，值>0，右重尾"。

数据：project_data/logs/poc_va_asymmetry_stage4/dataset_full.parquet
  - contract, event_time, A3_skew, signed_skew_rank_roll, ...
A3_skew：每事件的日内量加权偏度（D1 的概括量），本脚本研究的是它跨事件的时间序列（D2）。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

PARQUET = "project_data/logs/poc_va_asymmetry_stage4/dataset_full.parquet"


def section(title: str) -> None:
    print("\n" + "=" * 100)
    print(title)
    print("=" * 100)


def main() -> None:
    df = pd.read_parquet(PARQUET)
    x = df["A3_skew"].dropna().to_numpy(dtype=float)
    n_total = len(df)
    n_valid = len(x)
    print(f"总行数={n_total}, A3_skew 非缺失={n_valid} "
          f"({n_valid/n_total:.2%}), 缺失={n_total-n_valid}")

    # ---------- (0) 支撑 / 符号：检验 "值>0" 假设 ----------
    section("§0 支撑区间 & 符号分布（检验 '值>0' 假设）")
    print(f"min={x.min():+.4f}  max={x.max():+.4f}")
    print(f"mean={x.mean():+.4f}  median={np.median(x):+.4f}  std={x.std():.4f}")
    frac_pos = float(np.mean(x > 0))
    frac_neg = float(np.mean(x < 0))
    frac_zero = float(np.mean(x == 0))
    print(f"P(skew>0)={frac_pos:.2%}   P(skew<0)={frac_neg:.2%}   P(skew==0)={frac_zero:.2%}")
    print("→ 若显著跨 0，则 '值>0' 假设不成立，log/正支撑变换失效。")
    # 关键分位
    qs = [0.001, 0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99, 0.999]
    qv = np.quantile(x, qs)
    print("分位: " + "  ".join(f"q{q:.1%}={v:+.3f}" for q, v in zip(qs, qv)))

    # ---------- (1) 池化 D2 的形状：偏度/峰度/正态检验/t 拟合 ----------
    section("§1 池化 D2 形状 & 正态 vs Student-t 拟合")
    m, s = float(x.mean()), float(x.std(ddof=1))
    sk = float(stats.skew(x))            # D2 自身的偏度
    kt = float(stats.kurtosis(x))        # 超额峰度（正态=0）
    jb_stat, jb_p = stats.jarque_bera(x)
    print(f"mean={m:+.4f}  std={s:.4f}  skew(D2自身)={sk:+.3f}  excess_kurt={kt:+.3f}")
    print(f"Jarque-Bera: stat={jb_stat:.2f}  p={jb_p:.3e}  → "
          f"{'显著非正态' if jb_p<0.05 else '未拒绝正态'}")
    # 拟合
    t_df, t_loc, t_scale = stats.t.fit(x)
    norm_ll = float(np.sum(stats.norm.logpdf(x, m, s)))
    t_ll = float(np.sum(stats.t.logpdf(x, t_df, loc=t_loc, scale=t_scale)))
    print(f"Normal(loc={m:.4f}, scale={s:.4f})  logL={norm_ll:.1f}")
    print(f"  t(df={t_df:.2f}, loc={t_loc:.4f}, scale={t_scale:.4f})  logL={t_ll:.1f}")
    print(f"→ t 较 Normal 对数似然差 = {t_ll-norm_ll:+.1f} "
          f"({'t 拟合更好' if t_ll>norm_ll else '正态更好'})")
    print(f"→ {t_df:.1f} < 30 说明存在重尾；越接近 ∞ 越像正态")
    print(f"  注: skew(D2自身)={sk:+.3f}，若 ≈0 则 D2 近似对称（即便重尾）")

    # QQ 表：经验分位 vs 正态理论 vs t 理论
    print("\nQQ 对照表（empirical vs 拟合理论分位）:")
    print(f"{'q':>7s} {'empirical':>11s} {'normal':>11s} {'t(df)':>11s} {'|emp-nrm|':>11s} {'|emp-t|':>11s}")
    t_theory = stats.t.ppf(qs, t_df, loc=t_loc, scale=t_scale)
    n_theory = stats.norm.ppf(qs, m, s)
    for q, e, nt, tt in zip(qs, qv, n_theory, t_theory):
        print(f"{q:>7.1%} {e:>+11.4f} {nt:>+11.4f} {tt:>+11.4f} {abs(e-nt):>11.4f} {abs(e-tt):>11.4f}")

    # ---------- (2) 逐合约：是否跨合约一致（关系到跨品种可移植） ----------
    section("§2 逐合约 D2（跨合约一致性 → 跨品种可移植性）")
    print(f"{'contract':16s} {'n':>5s} {'P>0':>6s} {'mean':>8s} {'std':>7s} "
          f"{'skew':>7s} {'kurt':>7s} {'JBp':>9s} {'t_df':>7s}")
    rows = []
    for c in sorted(df["contract"].unique()):
        xc = df[df["contract"] == c]["A3_skew"].dropna().to_numpy(dtype=float)
        if len(xc) < 30:
            continue
        mc, sc = float(xc.mean()), float(xc.std(ddof=1))
        skc = float(stats.skew(xc)); ktc = float(stats.kurtosis(xc))
        jbc, jbp = stats.jarque_bera(xc)
        tdfc, _, tsc = stats.t.fit(xc)
        fracp = float(np.mean(xc > 0))
        print(f"{c:16s} {len(xc):>5d} {fracp:>6.2%} {mc:>+8.3f} {sc:>7.3f} "
              f"{skc:>+7.3f} {ktc:>+7.3f} {jbp:>9.3f} {tdfc:>7.2f}")
        rows.append((c, len(xc), fracp, mc, sc, skc, ktc, jbp, tdfc))
    arr = np.array([r[3:7] for r in rows])
    print("-" * 100)
    print(f"逐合约 mean 范围 [{arr[:,0].min():+.3f},{arr[:,0].max():+.3f}]  "
          f"std 范围 [{arr[:,1].min():.3f},{arr[:,1].max():.3f}]")
    print(f"逐合约 skew 范围 [{arr[:,2].min():+.3f},{arr[:,2].max():+.3f}]  "
          f"kurt 范围 [{arr[:,3].min():+.3f},{arr[:,3].max():+.3f}]")
    print("→ 若各合约 D2 形状/尺度差异大，则 A/D(绝对阈值) 不具跨品种可移植，A/C(排名) 才稳健。")

    # ---------- (3) rolling-window 稳定性（归一化的核心问题） ----------
    section("§3 滚动窗口内 D2 的稳定性（归一化方式选型的关键）")
    print("按合约构造逐事件时间序，以 10 事件为滑动窗，统计窗内:")
    print("  - skew 是否跨 0（窗内同现正负）")
    print("  - 窗内 skew 跨度 (max-min)，相对尺度")
    cross0 = []
    spans = []
    for c in sorted(df["contract"].unique()):
        xc = df[df["contract"] == c].sort_values("event_time")["A3_skew"].dropna().to_numpy(dtype=float)
        if len(xc) < 30:
            continue
        for i in range(0, len(xc) - 9, 1):
            w = xc[i:i+10]
            if w.min() < 0 < w.max():
                cross0.append(1)
            else:
                cross0.append(0)
            spans.append(w.max() - w.min())
    cross0 = np.array(cross0); spans = np.array(spans)
    print(f"10-事件窗总数={len(cross0)}，其中窗内跨 0 的比例={cross0.mean():.2%}")
    print(f"窗内 skew 跨度: median={np.median(spans):.4f}  p90={np.quantile(spans,0.9):.4f}  max={spans.max():.4f}")
    print("→ 若大量窗内跨 0：单窗内 D2 同时含正负，'skew>0 整体右偏'不成立，"\
          "且固定 z/绝对阈值在窗内无意义 → 排名(A/C) 是唯一稳健归一化。")
    print("→ 若窗内跨度普遍很大且不稳定：B(z-score) 的 μ/σ 每窗剧变，固定 z 边界不可移植。")

    # ---------- (4) 结论速判 ----------
    section("§4 速判：假设成立与否")
    print(f"A. '值>0' 假设: P(skew>0)={frac_pos:.2%} → "
          f"{'成立(绝大多数>0)' if frac_pos>0.8 else '不成立(显著跨0)'}")
    print(f"B. 重尾: pooled excess_kurt={kt:+.2f}, t_df={t_df:.1f} → "
          f"{'明显重尾' if (kt>1 or t_df<30) else '接近正态'}")
    print(f"C. 对称: skew(D2自身)={sk:+.3f} → "
          f"{'近似对称' if abs(sk)<0.5 else '自身偏斜'}")
    print(f"D. 跨合约一致: 见 §2 范围 → "
          f"{'一致→阈值可移植' if arr[:,1].max()/arr[:,1].min()<2 else '尺度差异大→仅排名稳健'}")
    print(f"E. 窗内跨0: {cross0.mean():.2%} → "
          f"{'大量跨0→否定整体正偏 & 强化排名归一化' if cross0.mean()>0.3 else '多数不跨0'}")


if __name__ == "__main__":
    main()
