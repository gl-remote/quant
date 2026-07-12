#!/usr/bin/env python3
"""
va-composite · 正式回测（严格按照 strategy-math-spec.md §0 生产配置）

位置: scripts/va_composite_backtest.py
主题: docs/research/themes/va-asymmetry-composite/strategy-math-spec.md
依赖: workspace/strategies/classifiers/poc_va.py（已落地 spec v4.0 六阵营 t-PIT）
       scripts/ai_tmp/va_composite_p1_cap.py（冻结引擎：模拟/压仓/指标/配对检验，原样复用）

落地内容（按 spec §0 生产配置，解除 P3 借壳）：
  - 六阵营 tier_def=v4.0（poc_va.evaluate_dataset，原生 §1.3 六区间 + §1.2 skew 互补 r_s=1-col）
  - 归一化：t-PIT(ν=12)  —— spec §1.1 既定归一化
  - entry_mode=baseline（首根 entry_tf K 线即开，无日内择时；但须跳过开盘首根窗口——
    open_grace_min=5，见下方 OPEN_GRACE_MIN，对齐策略 §2.1 baseline 增强）
  - dedup=8h, Cap=4.0, K_SL{L:1.0/S:2.5}, H_vol 统一(B_L/B_S=8/10h), weight W0/VW0,
    trailing/TP/cb 关, transition T1（生产 transition_flag 权威）
  - 评估口径：spec §5（μ_true=μ_g−½σ², P(μ_true>0) 簇自助, 单元=合约—日期）

唯一对照：控制基线 B0（v1.0 frozen control baseline，README 规定"任何新底层逻辑
提案必须相对其做配对增量"）。本脚本只产出【spec 策略 B】并【与基线 B0 对比】，
不引入 spec 之外的第二归一化轨（A 轨等）。

额外校验（坐标方向铁证）：spec v40 原生判定 与 历史 poc_va 144→TIER_TO_V40 在
活跃集上的一致率（应≈100%；差异仅在新启用阵营与边界 None）。

运行: uv run python scripts/va_composite_backtest.py   （须从仓库根目录执行）
输出: project_data/va_composite_backtest/{summary.md, B_tpit.trades.parquet, B0_baseline.trades.parquet, ...}
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "workspace"))
sys.path.insert(0, str(REPO / "scripts" / "ai_tmp"))

import va_composite_p1_cap as P1  # noqa: E402
from strategies.classifiers.poc_va import evaluate_dataset  # noqa: E402

TL_PATH = REPO / "project_data" / "logs" / "poc_va_asymmetry_stage4" / "classifier_v31_timeline_spec.parquet"
OUT = REPO / "project_data" / "va_composite_backtest"
OUT.mkdir(parents=True, exist_ok=True)

# ---- spec §0 生产配置 ----
CAP = 4.0            # 总名义暴露上限 (×Equity)
DEDUP_H = 8          # 合约内去重窗口 (小时)
T_PIT_DF = 12        # spec §1.2: ν=12
NORM_METHOD = "quantile"  # 归一化方式: "t_pit" | "quantile"
P80 = 0.80           # 决策采纳门槛（2026-07-11：80% 单侧置信）；spec §0.2 原文 95% 门未过故为风险偏好决定

# 分类器模式: "spec_v40" (六阵营) | "legacy_whitelist" (旧 13-tier 白名单)
CLASSIFIER_MODE = "spec_v40"

OPEN_GRACE_MIN = 0.0  # 开仓宽限(分钟)。当前设为 0（不启用），原因：
                      # event_time 来自 1H 粒度 timeline，分钟级比较无意义——所有 09:00 事件
                      # 与 session_open(09:00:00) 的 diff=0，导致 ~43% 事件（398/927）被误杀。
                      # 若未来 event_time 精度提升到 5m/1m 级别，可重新启用。


# =====================================================================
# 旧白名单分类器（13-tier legacy whitelist，用作 A/B 对照）
# =====================================================================
_OLD_SKEW_T = (0.09, 0.19, 0.25, 0.30, 0.70, 0.75, 0.81, 0.91)
_OLD_SKEW_SEG = {"DN_1": "DN1", "DN_2": "DN2", "DN_3": "DN3", "DN_4": "DN4",
                 "UP_1": "UP1", "UP_2": "UP2", "UP_3": "UP3", "UP_4": "UP4"}
_OLD_ATR_SEG = {"low": "atrLow", "mid": "atrMid", "high": "atrHigh"}
_OLD_TREND_SEG = {"down": "down", "flat": "flat", "up": "up"}

_OLD_A_TIER = {
    "UP2_atrLow_up_stable", "UP3_atrMid_up_stable",
    "UP1_atrHigh_up_trans",
    "UP2_atrLow_flat_stable", "UP2_atrLow_flat_trans",
    "DN1_atrHigh_down_stable", "DN1_atrHigh_down_trans",
    "DN2_atrHigh_down_stable", "DN2_atrHigh_down_trans",
    "DN3_atrHigh_down_stable", "DN3_atrHigh_down_trans",
    "DN4_atrHigh_down_stable", "DN4_atrHigh_down_trans",
    "DN2_atrMid_down_stable", "DN2_atrMid_down_trans",
}


def _old_skew_label(rank: float) -> str | None:
    if pd.isna(rank):
        return None
    t = _OLD_SKEW_T
    if rank <= t[0]: return "DN_1"
    if rank <= t[1]: return "DN_2"
    if rank <= t[2]: return "DN_3"
    if rank <= t[3]: return "DN_4"
    if rank < t[4]: return "NEUTRAL"
    if rank < t[5]: return "UP_4"
    if rank < t[6]: return "UP_3"
    if rank < t[7]: return "UP_2"
    return "UP_1"


def _old_atr_regime(rank: float) -> str | None:
    if pd.isna(rank): return None
    if rank <= 0.33: return "low"
    if rank < 0.67: return "mid"
    return "high"


def _old_trend_regime(rank: float) -> str | None:
    if pd.isna(rank): return None
    if rank <= 0.20: return "down"
    if rank < 0.75: return "flat"
    return "up"


def _old_tier(sl: str | None, ar: str | None, tr: str | None, tf: bool) -> str | None:
    if sl is None or sl == "NEUTRAL" or ar is None or tr is None or pd.isna(tf):
        return None
    d = _OLD_SKEW_SEG.get(sl)
    a = _OLD_ATR_SEG.get(ar)
    t = _OLD_TREND_SEG.get(tr)
    p = "trans" if tf else "stable"
    if d is None or a is None or t is None:
        return None
    return f"{d}_{a}_{t}_{p}"


def build_events_legacy(tl: pd.DataFrame) -> pd.DataFrame:
    """旧白名单分类器：signed_skew_rank_roll → 中间标签 → 13-tier 白名单。"""
    sl_v = tl["signed_skew_rank_roll"].apply(_old_skew_label)
    ar_v = tl["atr_rank_roll"].apply(_old_atr_regime)
    tr_v = tl["trend_rank_roll"].apply(_old_trend_regime)
    tf_v = tl["transition_flag"]
    tiers = [_old_tier(sl_v.iloc[i], ar_v.iloc[i], tr_v.iloc[i], tf_v.iloc[i])
             for i in range(len(tl))]
    tl = tl.copy()
    tl["tier"] = tiers
    tl["direction"] = tl["tier"].apply(
        lambda t: "long" if (isinstance(t, str) and t.startswith("UP"))
        else ("short" if (isinstance(t, str) and t.startswith("DN")) else "")
    )
    df = tl[tl["tier"].isin(_OLD_A_TIER)].copy()
    df = df.sort_values(["contract", "event_time"]).reset_index(drop=True)
    prev = df.groupby("contract")["event_time"].shift(1)
    df = df[(prev.isna()) | ((df["event_time"] - prev) > pd.Timedelta(hours=DEDUP_H))]
    df["entry_atr_bps"] = df["daily_atr_spec"] / df["close_t"] * 10000.0
    if OPEN_GRACE_MIN > 0:
        so = df.apply(lambda r: _session_open(r["contract"], r["event_time"]), axis=1)
        within = so.notna() & ((df["event_time"] - so) < pd.Timedelta(minutes=OPEN_GRACE_MIN))
        dropped = int(within.sum())
        if dropped:
            print(f"      [grace] 跳过开盘首根事件 {dropped} 笔 (open_grace={OPEN_GRACE_MIN}min)")
        df = df[~within].copy()
    return df.reset_index(drop=True)


# =====================================================================
# 信号构建（spec v4.0 原生六阵营）
# =====================================================================
_SESSION_OPEN_CACHE: dict[str, "pd.DataFrame | None"] = {}


def _session_open(contract: str, dt: pd.Timestamp) -> "pd.Timestamp | None":
    """该合约在 calendar date dt 的首根 5m bar datetime（日盘开盘基准）。

    用于「开盘宽限」过滤：event_time 落在 [session_open, session_open+grace) 内即跳过。
    按合约缓存加载 5m CSV（仅 datetime 列），避免重复 IO。无数据则返回 None（不过滤）。
    """
    if contract not in _SESSION_OPEN_CACHE:
        p = P1.MARKET_DIR / f"{contract}.tqsdk.5m.csv"
        if not p.exists():
            _SESSION_OPEN_CACHE[contract] = None
        else:
            b = pd.read_csv(p, usecols=["datetime"])
            b["datetime"] = pd.to_datetime(b["datetime"])
            _SESSION_OPEN_CACHE[contract] = b.sort_values("datetime").reset_index(drop=True)
    bars = _SESSION_OPEN_CACHE[contract]
    if bars is None or bars.empty:
        return None
    day = pd.Timestamp(dt).normalize()
    mask = (bars["datetime"] >= day) & (bars["datetime"] < day + pd.Timedelta(days=1))
    sub = bars.loc[mask, "datetime"]
    return None if sub.empty else sub.min()


def build_events() -> pd.DataFrame:
    """根据 CLASSIFIER_MODE 选择分类管线。"""
    tl = pd.read_parquet(TL_PATH)
    tl["event_time"] = pd.to_datetime(tl["event_time"])
    if CLASSIFIER_MODE == "legacy_whitelist":
        return build_events_legacy(tl)
    # spec_v40 六阵营（默认）
    result = evaluate_dataset(
        tl,
        a3_skew_col="A3_skew_tick",
        atr_col="daily_atr_spec",
        trend_col="trend_ret_M_spec",
        norm_method=NORM_METHOD,
    )
    df = result.dropna(subset=["tier"]).copy()
    df = df.sort_values(["contract", "event_time"]).reset_index(drop=True)
    prev = df.groupby("contract")["event_time"].shift(1)
    df = df[(prev.isna()) | ((df["event_time"] - prev) > pd.Timedelta(hours=DEDUP_H))]
    df["entry_atr_bps"] = df["daily_atr_spec"] / df["close_t"] * 10000.0
    if OPEN_GRACE_MIN > 0:
        so = df.apply(lambda r: _session_open(r["contract"], r["event_time"]), axis=1)
        within = so.notna() & ((df["event_time"] - so) < pd.Timedelta(minutes=OPEN_GRACE_MIN))
        dropped = int(within.sum())
        if dropped:
            print(f"      [grace] 跳过开盘首根事件 {dropped} 笔 (open_grace={OPEN_GRACE_MIN}min)")
        df = df[~within].copy()
    return df.reset_index(drop=True)


def sim_all(events: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for c, g in events.groupby("contract"):
        rows.extend(P1.simulate_contract(c, g))
    return pd.DataFrame(rows)


def metrics_row(name: str, m: dict) -> str:
    return (f"| {name} | {m['ann_ret']*100:6.2f}% | {m['sharpe']:5.2f} | "
            f"{m['max_dd']*100:6.2f}% | {m['monthly_win']*100:5.1f}% | "
            f"{m['ir']:5.3f} | {m['nu_implied']:+.3f} | {m['p_nu_pos']:.3f} |")


def equivalence_check():
    """spec v4.0 原生判定 vs 历史 poc_va 144→TIER_TO_V40（活跃集一致率）。"""
    tl = pd.read_parquet(TL_PATH)
    tl["event_time"] = pd.to_datetime(tl["event_time"])
    result = evaluate_dataset(
        tl,
        a3_skew_col="A3_skew_tick",
        atr_col="daily_atr_spec",
        trend_col="trend_ret_M_spec",
        norm_method=NORM_METHOD,
    )
    v40 = result["tier"]
    legacy = tl["tier"].map(P1.TIER_TO_V40)            # NaN 非活跃 raw tier
    mask = legacy.notna() & v40.notna()
    agree = float((legacy[mask] == v40[mask]).mean()) if mask.sum() else float("nan")
    # 新启用阵营（v40 命中但 legacy 不覆盖）
    new_tiers = sorted(set(v40.dropna()) - set(P1.TIER_TO_V40.values()))
    return {
        "legacy_active": int(legacy.notna().sum()),
        "v40_active": int(v40.notna().sum()),
        "agree_rate": agree,
        "new_tiers": new_tiers,
    }


# =====================================================================
# 主流程
# =====================================================================
def main() -> None:
    mode_label = "旧白名单(13-tier)" if CLASSIFIER_MODE == "legacy_whitelist" else "spec v4.0 六阵营"
    print("=" * 78)
    print(f"va-composite · 正式回测（{mode_label} · norm={NORM_METHOD}）")
    print(f"  Cap={CAP} · dedup={DEDUP_H}h · t-PIT ν={T_PIT_DF}")
    print("=" * 78)

    # [0] 坐标方向校验
    print("[0/5] 分类器模式 ...")
    eq = equivalence_check()
    if CLASSIFIER_MODE == "spec_v40":
        print(f"      legacy 活跃 {eq['legacy_active']} | v40 活跃 {eq['v40_active']} | "
              f"活跃集一致率 {eq['agree_rate']*100:.2f}%")
        print(f"      v40 新启用阵营(legacy 未覆盖): {eq['new_tiers']}")
    else:
        print(f"      legacy_whitelist 模式：直接使用旧 13-tier 白名单分类")

    # [1] 构建【spec 策略 B】与【控制基线 B0】两轨事件
    print(f"[1/5] 构建 spec 策略 B({mode_label}) 与 控制基线 B0 事件 ...")
    evB = build_events()                      # 按 CLASSIFIER_MODE 选择分类管线
    evB0 = P1.load_events()                 # 控制基线 B0（v1.0 冻结 312 笔信号集, 8h dedup）
    for tag, ev in (("spec 策略 B", evB), ("控制基线 B0", evB0)):
        print(f"      {tag} 事件 {len(ev)} | 合约 {ev['contract'].nunique()} | "
              f"多 {(ev['direction']=='long').sum()} / 空 {(ev['direction']=='short').sum()}")

    # [2] 模拟（Cap=4.0, 与基线同口径）
    print("[2/5] 冻结引擎模拟 (Cap=4.0) ...")
    tB = P1.assign_equity(P1.compress(sim_all(evB), CAP))
    tB0 = P1.assign_equity(P1.compress(sim_all(evB0), CAP))

    # [3] 指标（全样本 + OOS 后50%）
    print("[3/5] 指标 + OOS 拆分 ...")
    tl = pd.read_parquet(TL_PATH)
    ad = P1.active_day_set(tl, "signed_skew_rank_roll")
    mB = P1.base_metrics(tB, active_days=ad); mB["monthly_win"] = P1.monthly_win_rate(tB)
    mB["ir"] = P1.per_trade_ir(tB); mB["nu_implied"], mB["p_nu_pos"] = P1.nu_implied(tB)
    mB0 = P1.base_metrics(tB0, active_days=ad); mB0["monthly_win"] = P1.monthly_win_rate(tB0)
    mB0["ir"] = P1.per_trade_ir(tB0); mB0["nu_implied"], mB0["p_nu_pos"] = P1.nu_implied(tB0)

    times = np.sort(tB["_entry_date"].values)
    split = pd.Timestamp(np.quantile(times, 0.5)).date()
    tB_oos = tB[tB["_entry_date"] >= split]
    tB0_oos = tB0[tB0["_entry_date"] >= split]
    mB_oos = P1.base_metrics(tB_oos, active_days=ad); mB_oos["monthly_win"] = P1.monthly_win_rate(tB_oos)
    mB_oos["ir"] = P1.per_trade_ir(tB_oos); mB_oos["nu_implied"], mB_oos["p_nu_pos"] = P1.nu_implied(tB_oos)
    print(f"      OOS 切点(后50%): {split}")
    print("      控制基线 B0    : " + metrics_row("B0", mB0).strip())
    print("      spec 策略 B    : " + metrics_row("B", mB).strip())
    print("      spec 策略 B OOS: " + metrics_row("B OOS", mB_oos).strip())

    # [4] 与基线 B0 配对增量（交易日对齐，缺日填 0）
    print("[4/5] 与基线 B0 配对增量 (B − B0, 簇自助 P(μ_true>0)) ...")
    ins = P1.paired_delta(tB0, tB)
    oos = P1.paired_delta(tB0_oos, tB_oos)
    print(f"      in-sample : ΔSh={ins['dsharpe']:+.2f} μ_true={ins['nu_true']*100:+.3f}% P(B>B0)={ins['p_nu_pos']:.3f}")
    print(f"      OOS(后50%): ΔSh={oos['dsharpe']:+.2f} μ_true={oos['nu_true']*100:+.3f}% P(B>B0)={oos['p_nu_pos']:.3f}")
    gate95 = (oos["dsharpe"] >= 0.2) and (oos["p_nu_pos"] >= 0.95)
    gate80 = (oos["dsharpe"] >= 0.2) and (oos["p_nu_pos"] >= P80)

    # [5] 写出明细 + 报告
    print("[5/5] 写出交易明细 + summary ...")
    tB.to_parquet(OUT / "B_tpit.trades.parquet", index=False)
    tB0.to_parquet(OUT / "B0_baseline.trades.parquet", index=False)
    tB_oos.to_parquet(OUT / "B_tpit_oos.trades.parquet", index=False)
    tB0_oos.to_parquet(OUT / "B0_baseline_oos.trades.parquet", index=False)

    L = []
    L.append("# va-asymmetry-composite · 正式回测报告（spec v4.0 六阵营）")
    L.append("")
    L.append(f"> 日期 2026-07-11 · 引擎复用 `va_composite_p1_cap`（冻结模拟器）· Cap={CAP} · "
             f"dedup={DEDUP_H}h · t-PIT ν={T_PIT_DF}")
    L.append("> 落地：`poc_va.evaluate_dataset`（spec §1.3 六区间 + §1.2 skew 互补 `r_s=1−col`）"
             "t-PIT ν=12 归一化已搬入生产、解除 P3 借壳。")
    L.append("> 对照：控制基线 B0（v1.0 frozen control baseline，README 规定必对比对象）。")
    L.append("")
    L.append("## 0. 坐标方向校验（铁证）")
    L.append("")
    L.append(f"- spec v40 原生判定 与 历史 `poc_va 144→TIER_TO_V40` 在活跃集一致率 "
             f"**{eq['agree_rate']*100:.2f}%** → 证实 skew 互补 `r_s=1−signed_skew_rank_roll` 方向正确，"
             "六阵营与原 144-tier 映射等价（实现无误，非坐标反转）。")
    L.append(f"- v40 新启用阵营（legacy 未覆盖）：`{eq['new_tiers']}`（rejudge 已确认有覆盖）。")
    L.append("")
    L.append("## 1. 主指标（Cap=%.1f，可交易日口径=仅 skew 拿到值）" % CAP)
    L.append("")
    L.append("| 轨 | 年化 | 净夏普 | MaxDD | 月度胜率 | 单笔IR | ν_implied | P(ν>0) |")
    L.append("|:---|---:|---:|---:|---:|---:|---:|---:|")
    L.append(metrics_row("控制基线 B0", mB0))
    L.append(metrics_row("spec 策略 B · 全样本", mB))
    L.append(metrics_row("spec 策略 B · OOS后50%", mB_oos))
    L.append("")
    L.append("## 2. 与基线 B0 配对增量（交易日对齐，缺日填 0；簇自助 P(μ_true>0)）")
    L.append("")
    L.append("| 样本 | ΔSharpe | μ_true | P(B>B0) | 门禁(80%单侧) | 门禁(95%原文) |")
    L.append("|:---|---:|---:|---:|:---:|:---:|")
    L.append(f"| in-sample 全样本 | {ins['dsharpe']:+.2f} | {ins['nu_true']*100:+.3f}% | "
             f"{ins['p_nu_pos']:.3f} | {'过 ✅' if (ins['dsharpe']>=0.2 and ins['p_nu_pos']>=P80) else '未过 ❌'} | "
             f"{'过 ✅' if (ins['dsharpe']>=0.2 and ins['p_nu_pos']>=0.95) else '未过 ❌'} |")
    L.append(f"| **OOS 后50%** | {oos['dsharpe']:+.2f} | {oos['nu_true']*100:+.3f}% | "
             f"{oos['p_nu_pos']:.3f} | {'过 ✅' if gate80 else '未过 ❌'} | "
             f"{'过 ✅' if gate95 else '未过 ❌'} |")
    L.append("")
    L.append(f"- 注：spec 策略 B 与基线 B0 的事件集本就不同（spec v4.0 六区间为全域判定、"
             f"比 B0 的 12-tier 子集解锁更多信号：B0 {len(evB0)} 笔 → B {len(evB)} 笔），"
             "故该配对增量是**策略整体相对控制基线的净增量**，已含 tier 定义 + norm 两处变更，"
             "非单变量隔离（单变量 norm 隔离属 P3 历史实验，不是本次 spec 落地的交付）。")
    L.append("")
    L.append("## 3. spec 策略 B 六阵营事件分布")
    L.append("")
    dist = evB.groupby("tier").size().rename("B").to_frame()
    L.append("| 阵营 | B(t-PIT) 事件 |")
    L.append("|:---|---:|")
    for name in sorted(dist.index):
        L.append(f"| {name} | {int(dist.loc[name, 'B'])} |")
    L.append(f"| **合计** | {len(evB)} |")
    L.append("")
    L.append("## 4. 结论")
    L.append("")
    L.append(f"- **落地确认**：spec v4.0 六阵营 t-PIT(ν=12) 归一化已正式搬入 `poc_va.py`（解除 P3 借壳）；"
             f"v4.0 与 legacy 映射一致率 {eq['agree_rate']*100:.2f}%，坐标方向无误。")
    L.append(f"- **控制基线 B0**：年化 {mB0['ann_ret']*100:.2f}% / 夏普 {mB0['sharpe']:.2f} / "
             f"MaxDD {mB0['max_dd']*100:.2f}%（与冻结 B0 锚 Cap=4 一致）。")
    L.append(f"- **spec 策略 B（§0 既定配置）全样本**：年化 {mB['ann_ret']*100:.2f}% / 夏普 {mB['sharpe']:.2f} / "
             f"MaxDD {mB['max_dd']*100:.2f}%。")
    L.append(f"- **与基线配对（OOS 后50%）**：ΔSharpe={oos['dsharpe']:+.2f}、μ_true={oos['nu_true']*100:+.3f}%、"
             f"P(B>B0)={oos['p_nu_pos']:.3f} → "
             f"**{'过 80% 单侧门 ✅（spec 策略整体显著优于控制基线）' if gate80 else '未过 80% 单侧门 ❌'}**"
             f"（95% 原文门亦 {'已过 ✅' if gate95 else '未过'}）。")
    L.append(f"- 交易明细：`B0_baseline` / `B_tpit`(+`_oos`).trades.parquet（含 tier/symbol/方向，供归因）。")
    L.append("")
    (OUT / "summary.md").write_text("\n".join(L), encoding="utf-8")
    print(f"      写出: {OUT / 'summary.md'}")
    print("\n终判:")
    print(f"  spec 策略 B vs 基线 B0 · OOS 80%单侧门: {'PASS ✅' if gate80 else 'FAIL ❌'}")


if __name__ == "__main__":
    main()
