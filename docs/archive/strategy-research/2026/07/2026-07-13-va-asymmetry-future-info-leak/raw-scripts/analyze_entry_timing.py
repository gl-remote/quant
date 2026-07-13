#!/usr/bin/env python3
"""分析73个三级样本的R/E入场时段分布、跨段差异、覆盖率与收益影响估算。"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[4]
CMP_DIR = REPO / "docs/workbench/va-asymmetry-composite/outputs/compare-r-e"
PARQUET = CMP_DIR / "same_contract_day_three_layer_diff.parquet"
V2MATCH = CMP_DIR / "matched_pair_detail_v2.parquet"

SEG_NAMES = {
    "S1": "S1(09:00)",
    "S2": "S2(10:30)",
    "S3": "S3(13:30)",
    "N1": "N1(21:00)",
    "N2": "N2(23:00+)",
    "OTH": "OTH",
}
SEG_KEYS = ["S1", "S2", "S3", "N1", "N2", "OTH"]


def session_of(ts):
    if ts is None or pd.isna(ts):
        return "NA"
    hm = ts.hour * 100 + ts.minute
    if 900 <= hm < 1030: return "S1"
    if 1030 <= hm < 1130: return "S2"
    if 1330 <= hm < 1500: return "S3"
    if 2100 <= hm < 2300: return "N1"
    if hm >= 2300 or hm < 300: return "N2"
    return "OTH"


def grace_of(ts):
    if ts is None or pd.isna(ts):
        return -999
    s = session_of(ts)
    starts = {"S1": (9, 0), "S2": (10, 30), "S3": (13, 30), "N1": (21, 0), "N2": (23, 0)}
    if s not in starts:
        return -999
    sh, sm = starts[s]
    base = ts.replace(hour=sh, minute=sm, second=0, microsecond=0)
    if s == "N2" and ts.hour < 12:
        base = base - pd.Timedelta(days=1)
    diff_min = int((ts - base).total_seconds() // 60
    if diff_min < 0 or diff_min > 300:
        return -999
    return diff_min // 5


def main():
    if not PARQUET.exists():
        print(f"FATAL: {PARQUET} 不存在")
        return 1
    df73 = pd.read_parquet(PARQUET)
    df73["r_ts"] = pd.to_datetime(df73["r_entry_bar"])
    df73["e_ts"] = pd.to_datetime(df73["e_entry_bar"])
    df73["r_seg"] = df73["r_ts"].apply(session_of)
    df73["e_seg"] = df73["e_ts"].apply(session_of)
    df73["r_gr"] = df73["r_ts"].apply(grace_of)
    df73["e_gr"] = df73["e_ts"].apply(grace_of)
    df73["same_seg"] = df73["r_seg"] == df73["e_seg"]

    # v2 读取
    v2 = None
    if V2MATCH.exists():
        v2 = pd.read_parquet(V2MATCH)
        print(f"v2 稳健匹配 {len(v2)} 行：{dict(v2['match_type'].value_counts().to_dict())}")
    print()

    # ================================================================
    # Part A: 段分布
    # ================================================================
    print("=" * 90)
    print("Part A · 73样本：R/E 入场时段分布 + 段内第几根5m bar")
    print("=" * 90)
    for lv in ["L1-strict", "L2-loose", "L3-dayboth"]:
        g = df73[df73["level"] == lv]
        if len(g) == 0:
            continue
        print(f"\nLevel {lv} (N={len(g)}):")
        rvc = g["r_seg"].value_counts()
        evc = g["e_seg"].value_counts()
        print(f"  {'段':<14}{'R 计':>6}{'R%':>7}  {'E 计':>6}{'E%':>7}")
        for s in SEG_KEYS:
            rc = int(rvc.get(s, 0))
            ec = int(evc.get(s, 0))
            print(f"  {SEG_NAMES[s]:<14}{rc:>6}{rc/len(g)*100:>6.1f}%  {ec:>6}{ec/len(g)*100:>6.1f}%")
        rgr_vc = g["r_gr"].value_counts().sort_index()
        egr_vc = g["e_gr"].value_counts().sort_index()
        print(f"  R段内bar分布 (bar#0=段首open): {dict(rgr_vc[rgr_vc.index>=0].to_dict())}  median={g[g['r_gr'>=0]['r_gr'].median():.0f}")
        print(f"  E段内bar分布:                     {dict(egr_vc[egr_vc.index>=0].to_dict())}  median={g[g['e_gr'>=0]['e_gr'].median():.0f}")

    # ================================================================
    # Part B: 跨段
    # ================================================================
    print("\n" + "=" * 90)
    print("Part B · R/E 跨段不匹配模式 + 同段/跨段净盈亏对比")
    print("=" * 90)
    for lv in ["L1-strict", "L2-loose", "L3-dayboth"]:
        g = df73[df73["level"] == lv]
        if len(g) == 0:
            continue
        same = int(g["same_seg"].sum())
        print(f"\nLevel {lv} (N={len(g)}): 同段={same}  跨段={len(g)-same}")
        if len(g) - same > 0:
            vc = (g["r_seg"] + "→" + g["e_seg"])[~g["same_seg"]].value_counts()
            for pat, n in vc.items():
                print(f"  {pat} ×{n}")
        if "r_pnl_net_ccy" in g.columns and "e_pnl_net_ccy" in g.columns:
            print(f"  单笔净盈亏 median(¥):")
            for tag, sub in [("同段", g[g["same_seg"]]), ("跨段", g[~g["same_seg"]])]:
                if len(sub) == 0: continue
                rp = sub["r_pnl_net_ccy"].dropna()
                ep = sub["e_pnl_net_ccy"].dropna()
                print(f"    {tag} N={len(sub):>3}: R median={rp.median():>+10,.0f}  E median={ep.median():>+10,.0f}  E−R median={(ep - rp.reindex(ep.index).median() if len(ep) else np.nan):>+10,.0f}" if len(rp) and len(ep) else "")

    # ================================================================
    # Part C: 预期 vs 实际
    # ================================================================
    print("\n" + "=" * 90)
    print("Part C · 预期模式(同段 R#0→E#1) vs 偏差模式 计数 + E−R盈亏影响")
    print("  预期内：同段 + R在bar0/1 + E在bar#1（即5min grace")
    print("  偏差A：跨段 + R bar0 + E bar1（段错位）")
    print("=" * 90)

    def pat(rg, eg, rs, es):
        if rs == es and rg in (0, 1) and eg == 1:
            return "预期内(同段 R#0/1→E#1)"
        if rs == es and rg == 0 and eg >= 2:
            return f"同段但E过晚(bar#{eg})"
        if rs == es:
            return f"同段双方都偏(R#{rg}→E#{eg})"
        if rs != es and rg == 0 and eg == 1:
            return f"偏差A·跨段错位(R{rs}#0→E{es}#1)"
        return f"其他(R{rs}#{rg}→E{es}#{eg})"

    df73["pat"] = df73.apply(lambda r: pat(r["r_gr"], r["e_gr"], r["r_seg"], r["e_seg"]), axis=1)
    for lv in ["L1-strict", "L2-loose", "L3-dayboth"]:
        g = df73[df73["level"] == lv]
        if len(g) == 0: continue
        print(f"\nLevel {lv} (N={len(g)}):")
        vc = g["pat"].value_counts()
        for p, n in vc.items():
            sub = g[g["pat"] == p]
            med = ""
            if "r_pnl_net_ccy" in sub.columns and "e_pnl_net_ccy" in sub.columns:
                d = (sub["e_pnl_net_ccy"] - sub["r_pnl_net_ccy"]).dropna()
                if len(d):
                    med = f"  E−R median={d.median():>+10,.0f}¥  ΣR={sub['r_pnl_net_ccy'].dropna().sum():>+12,.0f}¥  ΣE={sub['e_pnl_net_ccy'].dropna().sum():>+12,.0f}¥"
            print(f"  {p:<42} ×{n:>3}{med}")

    # ================================================================
    # Part D: 覆盖率影响（R-only 914 的段分布
    # ================================================================
    print("\n" + "=" * 90)
    print("Part D · 覆盖率影响估算：从 R-only 914 合约日")
    print("  估算：E 如果E在任一段grace后都可触发 → 能补多少笔、补多少盈亏")
    print("=" * 90)
    if v2 is None:
        print("  v2 未找到，跳过")
    else:
        ro = v2[v2["match_type"] == "research_only"].copy()
        print(f"\nresearch_only N={len(ro)}")
        # 找列
        rcands = [c for c in ro.columns if "entry" in c.lower() and ("bar" in c.lower() or "time" in c.lower()) and "_R" in c]
        tc = rcands[0] if rcands else None
        pnl_col = "pnl_net_ccy" if "pnl_net_ccy" in ro.columns else None
        if tc:
            ro_ts = pd.to_datetime(ro[tc])
            ro_seg = ro_ts.apply(session_of)
            ro_gr = ro_ts.apply(grace_of)
            print(f"  R-only 段分布：")
            vc = ro_seg.value_counts()
            tot_seg = 0
            tot_seg_pnl_map = {}
            for s in SEG_KEYS:
                c = int(vc.get(s, 0))
                tot_seg += c
                mask = ro_seg == s
                if pnl_col and mask.any():
                    pn = ro[mask][pnl_col].dropna()
                    tot_seg_pnl_map[s] = (c, pn.sum() if len(pn) else 0.0, pn.mean() if len(pn) else 0.0
                else:
                    tot_seg_pnl_map[s] = (c, 0.0, 0.0)
                print(f"    {SEG_NAMES[s]:<14}{c:>5}  {c/len(ro)*100:>5.1f}%  → E补做=覆盖率+{c/926*100:>5.1f}pp")
            # bar0 非S1段
            ro["seg"] = ro_seg
            ro["gr"] = ro_gr
            nons1_bar0 = ro[(ro["seg"].isin(["S2","S3","N1","N2"])) & (ro["gr"] == 0)]
            # 非S1段 且 bar0触发（即R在S2/S3/N1 段首触发
            print(f"\n★ R-only中非S1段+段首bar0（即R在S2/S3/N1段首整点 = {len(nons1_bar0)} 笔")
            if len(nons1_bar0) > 0:
                vc2 = nons1_bar0["seg"].value_counts().sort_index()
                for s, n in vc2.items():
                    print(f"    {SEG_NAMES.get(s,s):<14} ×{n:>5}")
                if pnl_col:
                    pn = nons1_bar0[pnl_col].dropna()
                    if len(pn):
                        print(f"  这些R信号 R净盈亏 Σ = {pn.sum():>+15,.0f}¥  avg = {pn.mean():>+10,.0f}¥/笔")
                        print(f"  → 如果E补做：预期净盈亏增加值 ≈ {pn.sum():>+15,.0f}¥")

            # S1 段补做
            s1_bar0 = ro[(ro["seg"] == "S1") & (ro["gr"] == 0)]
            print(f"\n★ R-only中S1段+段首bar0 = {len(s1_bar0)} 笔（这些E侧应该也能在S1 bar#1触发 → 未触发 = 不是段首时段问题，而是输入因子差导致")
            if len(s1_bar0) and pnl_col:
                pn = s1_bar0[pnl_col].dropna()
                if len(pn):
                    print(f"  S1段首信号 ΣR净盈亏 = {pn.sum():>+15,.0f}¥")

    # ================================================================
    # Part E: L1+L2 逐笔详情
    # ================================================================
    print("\n" + "=" * 90)
    print("Part E · L1+L2 逐笔详情")
    print("=" * 90)
    cols = []
    for c in ["level", "contract", "event_date",
              "r_seg", "r_gr", "r_ts", "r_tier", "r_dir", "r_pnl_net_ccy",
              "e_seg", "e_gr", "e_ts", "e_tier_actual", "e_dir_actual", "e_pnl_net_ccy"]:
        if c in df73.columns:
            cols.append(c)
    t = df73[df73["level"].isin(["L1-strict", "L2-loose"])][cols]
    pd.set_option("display.max_columns", 30)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_colwidth", 22)
    print(t.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
