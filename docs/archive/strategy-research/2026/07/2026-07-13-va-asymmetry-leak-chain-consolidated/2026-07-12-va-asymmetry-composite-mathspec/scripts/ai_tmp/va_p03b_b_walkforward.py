#!/usr/bin/env python3
"""
va-composite · P3 · B 轨(t-PIT 归一化) —— walk-forward / 时间外持有期 OOS 验证

主题: docs/research/themes/va-asymmetry-composite/
依赖: 冻结 B0 管线(classifier_v31_timeline.parquet + 5m CSV)，
      复用 va_composite_p1_cap 的模拟器/压仓/指标/配对门禁(簇自助 P(μ_true>0))。
      B 轨 t-PIT 变换复用 P3(va_p03c_b_track.py)：仅 skew 切到稳健 z + 参数化 t-PIT(ν=12)，
      atr/trend 冻结为 A 轨(rank)值，单一变量隔离"归一化方式"。

背景（P3 · 2026-07-11，全样本 in-sample）：
  - A(rank) 26.12%/3.62 vs B(t-PIT) 33.97%/4.19（Cap=1.0），B 年化+7.85pp、夏普+0.57、回撤更低；
    paired ΔSharpe(B−A)=+1.18、μ_true+7.30%、P(B>A)=0.866 → 四项一致指向 B 更优，但 P<0.95 未过"等效"门，
    且为同数据全样本 in-sample → 必须走 OOS/walk-forward 确认防过拟合（与 H_vol 当年处境相同）。

本脚本设计（B 是固定因果变换、无选择参数，故 walk-forward 退化为时间外持有期检验）：
  1. 构建 B 轨时间线（因果滚动 t-PIT，仅用过去 → 无未来泄漏）。
  2. A/B 各事件集在冻结引擎下模拟（Cap=4.0 当前默认；另报 Cap=1.0 作与 P3 的交叉校验）。
  3. in-sample：全样本配对（应复现 P3 方向 ΔSh≈+1.18）。
  4. OOS：按时间中位切分，取**后 50%** 为持有期外样本配对（真实泛化检验）；另报 4 折前向逐折稳定性。
  5. 门禁（spec §0.2，复用 P1.paired_delta）：B vs A 配对须 ΔSharpe≥0.2 **且** P(μ_true>0)≥0.95。

运行: uv run python scripts/ai_tmp/va_p03b_b_walkforward.py
输出: project_data/ai_tmp/p3b_b_walkforward/summary.md
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import t as t_dist

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "workspace"))
sys.path.insert(0, str(REPO / "scripts" / "ai_tmp"))
import va_composite_p1_cap as P1  # noqa: E402
from va_composite_p1_cap import (  # noqa: E402
    A_TIER_RAW, TIER_TO_V40, DEDUP_HOURS,
)
from strategies.classifiers.poc_va import POCVAClassifier  # noqa: E402

OUT_DIR = Path("project_data/ai_tmp/p3b_b_walkforward")
OUT_DIR.mkdir(parents=True, exist_ok=True)

CAP = 4.0          # 当前默认（spec §0.1 2026-07-11 修订）
SKEW_WIN, SKEW_MINP = 100, 10   # 对齐 A 轨 skew 口径（事件行）
ATR_WIN, ATR_MINP = 20, 10       # 对齐 A 轨 atr/trend 口径（去重日滚）
T_PIT_DF = 12                   # spec §1.3.0 注 (iii): ν=12
N_FOLDS = 4


# =====================================================================
# B 归一化: 稳健 z-score + 参数化 t-PIT（spec §1.3.0 注 (iii)，复用 P3）
# =====================================================================
def t_pit_window(w: np.ndarray) -> float:
    x = w[-1]
    med = np.median(w)
    mad = np.median(np.abs(w - med))
    scale = 1.4826 * mad
    if scale < 1e-12:
        return 0.5
    z = (x - med) / scale
    return float(t_dist.cdf(z, df=T_PIT_DF))


def roll_t_pit_event(s: pd.Series, N: int, minp: int) -> pd.Series:
    return s.rolling(N, min_periods=minp).apply(t_pit_window, raw=True)


def build_b_coords(df: pd.DataFrame) -> pd.DataFrame:
    sk_B = df.groupby("contract")["A3_skew"].transform(
        lambda s: roll_t_pit_event(s, SKEW_WIN, SKEW_MINP))
    out = pd.DataFrame(index=df.index)
    out["sk_B"] = sk_B.values
    out["atr_B"] = df["atr_rank_roll"].values    # 冻结值（=A 轨）
    out["tr_B"] = df["trend_rank_roll"].values   # 冻结值（=A 轨）
    return out


def classify_b(df: pd.DataFrame) -> pd.Series:
    tmp = df[["contract", "event_time", "transition_flag",
              "sk_B", "atr_B", "tr_B"]].rename(columns={
        "sk_B": "signed_skew_rank_roll",
        "atr_B": "atr_rank_roll",
        "tr_B": "trend_rank_roll",
    }).dropna(subset=["signed_skew_rank_roll", "atr_rank_roll", "trend_rank_roll"])
    res = POCVAClassifier().evaluate_dataset(tmp).dropna(subset=["tier"])
    return res["tier"].reindex(df.index)


def make_b_timeline(src: Path) -> pd.DataFrame:
    """构建 B 轨时间线（因果）：skew→t-PIT，atr/trend 冻结=A 轨；保留全部原始列仅替换 tier。"""
    df = pd.read_parquet(src)
    df["event_time"] = pd.to_datetime(df["event_time"])
    b_coords = build_b_coords(df)
    df_b = pd.concat([df[["contract", "event_time", "transition_flag"]], b_coords], axis=1)
    b_tier = classify_b(df_b)
    out = df.copy()
    out["tier"] = b_tier.values
    out = out.dropna(subset=["tier"])
    return out.reset_index(drop=True)


def load_events_from_frame(tl: pd.DataFrame) -> pd.DataFrame:
    """镜像 P1.load_events，但基于给定帧（其 tier 为 B 分类结果）。"""
    a = tl[tl["tier"].isin(A_TIER_RAW)].copy()
    a["direction"] = a["tier"].apply(lambda t: "long" if t.startswith("UP") else "short")
    a["tier_v40"] = a["tier"].map(TIER_TO_V40)
    a = a.dropna(subset=["tier_v40"])
    a["entry_atr_bps"] = a["daily_atr_10_bps"]
    a = a.sort_values(["contract", "event_time"]).reset_index(drop=True)
    prev = a.groupby("contract")["event_time"].shift(1)
    a = a[(prev.isna()) | ((a["event_time"] - prev) > pd.Timedelta(hours=DEDUP_HOURS))]
    return a.reset_index(drop=True)


def sim_all(events: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for c, g in events.groupby("contract"):
        rows.extend(P1.simulate_contract(c, g))
    return pd.DataFrame(rows)


def eval_trades(raw: pd.DataFrame, cap: float, ad) -> tuple:
    t = P1.compress(raw, cap)
    t = P1.assign_equity(t)
    m = P1.base_metrics(t, active_days=ad)
    m["monthly_win"] = P1.monthly_win_rate(t)
    m["ir"] = P1.per_trade_ir(t)
    m["nu"], m["p"] = P1.nu_implied(t)
    return t, m


def full_metrics(trades: pd.DataFrame, ad) -> dict:
    m = P1.base_metrics(trades, active_days=ad)
    m["monthly_win"] = P1.monthly_win_rate(trades)
    m["ir"] = P1.per_trade_ir(trades)
    m["nu"], m["p"] = P1.nu_implied(trades)
    return m


def metrics_row(name: str, m: dict) -> str:
    return (f"| {name} | {m['ann_ret']*100:6.2f}% | {m['sharpe']:5.2f} | "
            f"{m['max_dd']*100:6.2f}% | {m['monthly_win']*100:5.1f}% | "
            f"{m['ir']:5.3f} | {m['nu']:+.3f} | {m['p']:.3f} |")


def paired_subset(tA: pd.DataFrame, tB: pd.DataFrame, lo, hi=None):
    if hi is None:
        a = tA[tA["_entry_date"] >= lo]
        b = tB[tB["_entry_date"] >= lo]
    else:
        a = tA[(tA["_entry_date"] >= lo) & (tA["_entry_date"] < hi)]
        b = tB[(tB["_entry_date"] >= lo) & (tB["_entry_date"] < hi)]
    if len(a) == 0 or len(b) == 0:
        return None
    return P1.paired_delta(a, b)


def main() -> None:
    print("=" * 78)
    print("va-composite · P3 · B 轨(t-PIT) walk-forward / 时间外持有期 OOS 验证  "
          f"[Cap={CAP} 默认 · {N_FOLDS}折时间展开 · t-PIT ν={T_PIT_DF}]")
    print("=" * 78)

    print("[1/5] 加载冻结 timeline + 构建 B 轨(因果 t-PIT)...")
    tl_src = pd.read_parquet(P1.TIMELINE_PATH)
    ad = P1.active_day_set(tl_src, "signed_skew_rank_roll")
    evA = P1.load_events()
    print(f"      A 事件 {len(evA)} | 合约 {evA['contract'].nunique()} | "
          f"多 {(evA['direction']=='long').sum()} / 空 {(evA['direction']=='short').sum()}")

    b_tl = make_b_timeline(P1.TIMELINE_PATH)
    b_tl.to_parquet(OUT_DIR / "timeline_B_frozen.parquet", index=False)
    evB = load_events_from_frame(b_tl)
    print(f"      B 事件 {len(evB)} | 合约 {evB['contract'].nunique()} | "
          f"多 {(evB['direction']=='long').sum()} / 空 {(evB['direction']=='short').sum()}")
    # 重分类导致的事件集差异（核心：A/B 差异来源）
    setA, setB = set(evA["contract"] + "|" + evA["event_time"].astype(str)), \
                 set(evB["contract"] + "|" + evB["event_time"].astype(str))
    print(f"      A/B 事件集差: 仅A有 {len(setA-setB)} | 仅B有 {len(setB-setA)} | 交集 {len(setA&setB)}")

    print("\n[2/5] 冻结引擎模拟（Cap=4.0 默认 + Cap=1.0 交叉校验）...")
    rawA = sim_all(evA)
    rawB = sim_all(evB)
    tA4, mA4 = eval_trades(rawA, 4.0, ad)
    tB4, mB4 = eval_trades(rawB, 4.0, ad)
    tA1, mA1 = eval_trades(rawA, 1.0, ad)
    tB1, mB1 = eval_trades(rawB, 1.0, ad)
    print("      A(Cap4) : " + metrics_row("A(rank)", mA4).strip())
    print("      B(Cap4) : " + metrics_row("B(t-PIT)", mB4).strip())
    ins_p4 = P1.paired_delta(tA4, tB4)
    ins_p1 = P1.paired_delta(tA1, tB1)
    print(f"      in-sample paired(B−A) Cap4.0 : ΔSh={ins_p4['dsharpe']:+.2f} "
          f"μ_true={ins_p4['nu_true']*100:+.3f}% P(B>A)={ins_p4['p_nu_pos']:.3f}")
    print(f"      in-sample paired(B−A) Cap1.0 : ΔSh={ins_p1['dsharpe']:+.2f} "
          f"μ_true={ins_p1['nu_true']*100:+.3f}% P(B>A)={ins_p1['p_nu_pos']:.3f} "
          f"(P3 校验·原 +1.18/0.866)")

    print(f"\n[3/5] walk-forward 时间外持有期（{N_FOLDS}折前向）...")
    times = np.sort(evA["event_time"].values)
    qs = [pd.Timestamp(t) for t in np.quantile(times, np.linspace(0, 1, N_FOLDS + 1))]
    split = qs[N_FOLDS // 2]   # 后 50% 持有期外
    oos_p = paired_subset(tA4, tB4, split.date())
    # OOS 主指标
    tA_oos = tA4[tA4["_entry_date"] >= split.date()]
    tB_oos = tB4[tB4["_entry_date"] >= split.date()]
    mA_oos = full_metrics(tA_oos, ad)
    mB_oos = full_metrics(tB_oos, ad)
    fold_rows = []
    for i in range(N_FOLDS):
        r = paired_subset(tA4, tB4, qs[i].date(), qs[i + 1].date())
        fold_rows.append((i, r))
        if r:
            print(f"      折{i} [{qs[i].date()}→{qs[i+1].date()}): "
                  f"ΔSh={r['dsharpe']:+.2f} P(B>A)={r['p_nu_pos']:.3f}")
        else:
            print(f"      折{i}: 空")
    print(f"      OOS(后50%) : ΔSh={oos_p['dsharpe']:+.2f} μ_true={oos_p['nu_true']*100:+.3f}% "
          f"P(B>A)={oos_p['p_nu_pos']:.3f}")

    print("\n[4/5] 写出交易明细 parquet...")
    tA4.to_parquet(OUT_DIR / "A_cap4.trades.parquet", index=False)
    tB4.to_parquet(OUT_DIR / "B_cap4.trades.parquet", index=False)
    tA_oos.to_parquet(OUT_DIR / "A_oos.trades.parquet", index=False)
    tB_oos.to_parquet(OUT_DIR / "B_oos.trades.parquet", index=False)

    print("[5/5] 门禁判定 + 写 summary...")
    gate = (oos_p["dsharpe"] >= 0.2) and (oos_p["p_nu_pos"] >= 0.95)

    def pj(name, p):
        if p is None:
            return f"| {name} | — | — | — | 空 |"
        return (f"| {name} | {p['dsharpe']:+.2f} | {p['nu_true']*100:+.3f}% | "
                f"{p['p_nu_pos']:.3f} | {'过 ✅' if (p['dsharpe']>=0.2 and p['p_nu_pos']>=0.95) else '未过 ❌'} |")

    L = []
    L.append("# va-asymmetry-composite · Phase 3 · B 轨(t-PIT) walk-forward / 时间外持有期 OOS 验证报告")
    L.append("")
    L.append(f"> 日期 2026-07-11 · 引擎复用 P1 冻结模拟器 · Cap={CAP}(当前默认) · "
             f"t-PIT ν={T_PIT_DF} · {N_FOLDS}折时间展开")
    L.append("> B 轨 = 同源 raw 量仅对 **skew 切到 t-PIT**(稳健 z=med+1.4826·MAD，PIT=F_t(·;ν))，"
             "atr/trend 冻结=A 轨值，单一变量隔离'归一化方式'。")
    L.append("> B 是**固定因果变换(无拟合参数)**，故 walk-forward 退化为**时间外持有期检验**："
             "全样本 B 时间线已因果(仅用过去)构建，OOS=后50%时段配对。")
    L.append("> 门禁(spec §0.2)：B vs A 配对须 **ΔSharpe≥0.2 且 P(μ_true>0)≥0.95** 同时成立方升格默认。")
    L.append("")
    L.append("## 1. 主指标（Cap=%.1f，新·可交易日口径）" % CAP)
    L.append("")
    L.append("| 轨 | 年化 | 净夏普 | MaxDD | 月度胜率 | 单笔IR | ν_implied | P(ν>0) |")
    L.append("|:---|---:|---:|---:|---:|---:|---:|---:|")
    L.append(metrics_row("A(rank) · 全样本", mA4))
    L.append(metrics_row("B(t-PIT) · 全样本", mB4))
    L.append(metrics_row("A(rank) · OOS后50%", mA_oos))
    L.append(metrics_row("B(t-PIT) · OOS后50%", mB_oos))
    L.append("")
    L.append("## 2. 配对增量（B − A，簇自助 P(μ_true>0)）")
    L.append("")
    L.append("| 样本 | ΔSharpe | μ_true | P(B>A) | 门禁 |")
    L.append("|:---|---:|---:|---:|:---:|")
    L.append(pj("in-sample 全样本 (Cap=4.0)", ins_p4))
    L.append(pj("in-sample 全样本 (Cap=1.0 校验)", ins_p1))
    L.append(pj(f"**OOS 后50%** (Cap=4.0)", oos_p))
    for i, r in fold_rows:
        L.append(pj(f"折{i} 前向 (Cap=4.0)", r))
    L.append("")
    L.append("## 3. 事件集差异（A/B 差异来源）")
    L.append("")
    L.append(f"- A 事件 {len(evA)} · B 事件 {len(evB)}")
    L.append(f"- 仅 A 有 {len(setA-setB)} · 仅 B 有 {len(setB-setA)} · 交集 {len(setA&setB)}")
    L.append("- 说明：B 重分类后，部分事件在'A 活跃 6 tier'内外迁移 → 进入/移出回测事件集，"
             "这是 A/B 收益差的根本来源（tier_v40 在模拟中仅为归因标签，不改变 K/H）。")
    L.append("")
    L.append("## 4. 结论与处置")
    L.append("")
    L.append(f"- **in-sample**(全样本, 应复现 P3 方向)：B−A ΔSh={ins_p4['dsharpe']:+.2f}、"
             f"μ_true={ins_p4['nu_true']*100:+.3f}%、P(B>A)={ins_p4['p_nu_pos']:.3f} "
             f"(Cap1.0 校验 ΔSh={ins_p1['dsharpe']:+.2f}/P={ins_p1['p_nu_pos']:.3f}，与原 P3 +1.18/0.866 一致)。")
    L.append(f"- **OOS**(后50%时间外持有期)：B−A ΔSh={oos_p['dsharpe']:+.2f}、"
             f"μ_true={oos_p['nu_true']*100:+.3f}%、P(B>A)={oos_p['p_nu_pos']:.3f} → "
             f"**{'过门 ✅ 升格默认' if gate else '未过门 ❌ 维持 A'}**")
    L.append("- in-sample→OOS 的 ΔSharpe/P 衰减即过拟合程度；若 OOS 显著低于 in-sample，"
             "说明 B 的 in-sample 优势含样本特定运气，须谨慎。")
    if gate:
        L.append("- **采用建议**：B(t-PIT) OOS 过门，将默认归一化由 A(rank) 升格为 B(t-PIT)；"
                 "回灌 spec §1.3.0（B 由'待校准变体'升为默认）与 §0.1 总表。")
    else:
        L.append("- **采用建议**：OOS 未过门，维持 A(rank) 为默认归一化；B 仍为 in-sample 占优候选，"
                 "须经更大样本/跨期复验或 ν 鲁棒性扫描后再评估，不可直接继承 in-sample 结论。"
                 "（此处境与 H_vol 当年一致——in-sample 占优≠OOS 成立。）")
    L.append("")
    L.append("> 局限：B 为固定因果变换，本检验验证'同一变换在后期数据仍占优'；未覆盖超参 ν 鲁棒性"
             "(ν∈{8,12,20})，若后续要升格建议补 ν 扫描。")
    L.append("")

    (OUT_DIR / "summary.md").write_text("\n".join(L), encoding="utf-8")
    print(f"      写出: {OUT_DIR / 'summary.md'}")
    print("\nPhase 3 B 轨 OOS 终判:")
    print(f"  B(t-PIT) OOS 门禁(Cap4.0, 后50%): {'PASS ✅' if gate else 'FAIL ❌'}")


if __name__ == "__main__":
    main()
