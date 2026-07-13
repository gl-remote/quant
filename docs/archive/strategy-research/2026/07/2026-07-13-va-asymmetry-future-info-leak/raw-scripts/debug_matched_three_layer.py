#!/usr/bin/env python3
"""
文件级元信息：
- 创建背景：v2 matched 是跨合约错配垃圾，需要从 R/E 原始 parquet 自己构造
  "同合约同日期 → 信号是否一致"的三级样本集合（strict/loose/day-both）；
  然后在三级样本上做三层对比：因子输入 / 分类信号 / 交易执行。
- 样本分级：
  Level1 strict: 同合约同日 tier+direction 完全一致（最理想，先找有没有）
  Level2 loose : 同合约同日 direction 一致但 tier 可能不同（看执行差异够用）
  Level3 day-both: 同合约同日 R 和 E 都有信号（不管 tier/dir 是什么，看输入因子差）
- 输出：三级样本各自的三层对比宽表 + 一致率汇总 + 各样本分级的三层打印。

===============================================================================
【共同分类器 → 猜疑范围已收敛】   (两侧 100% 共用 workspace/strategies/classifiers/poc_va.py)
===============================================================================

✅ 可排除（纯函数/数据结构完全一致，不需再查）：
  1. 归一化 roll_t_pit() 实现 —— MAD=1.4826, ν=12 稳健 z → 学生 t CDF
  2. 六阵营 classify_tier() 阈值 —— 共用同一份 TIERS 元组 (L_seg3 s∈(0.09,0.30] …)
  3. r_s 互补取法 —— 统一 r_s = 1.0 - t-PIT(A3_skew 原值)，没有"signed_skew"取负号差异
  4. 窗口配置 ClassifierConfig —— 研究侧默认 10 / 工程侧 VAAsymmetryCompositeParams 默认 10
       skew_rank_win = atr_rank_win = trend_win = atr_entry_win = trend_entry_win = 10
  5. trend 原始值 —— 统一 log(C_d / C_{d-9}) 10 日累计对数收益（非 bps）
  6. trans 制度切换 —— 统一 compute_transition_series(r_a 系列)：三分桶 → crossover → age<3
  7. _spec 后缀"修正"—— 研究侧 A3_skew_spec / daily_atr_spec / trend_ret_M_spec
       就是 volume_weighted_skew / daily_atr_sma(HLC,10) / trend_log_return(close,10)
       纯原始值，没有神秘调整。ATR 名义价 / bps 化不影响 t-PIT 结果（秩化归一化）。

❓ 仅存的 4 个真实差异猜疑点（按影响权重降序）：
  A. ★★★★★ §2.1 入场触发 open_grace_min=5min
     E 侧：session open 后 ≥ 5 分钟才允许开仓；base_tf=5m → 实际落在每时段第二根 bar open
           即 09:00 段 → 09:10；21:00 段 → 21:10；13:30 段 → 13:50。
           L1 样本 E 入场时间 09:10 / 13:50 完全吻合 → 中位数入场时点差 17400 s (4.8 h)，
           入场价相对差 14.9 bps (median)。
     R 侧：entry_time 常在 09:00 / 21:00 / 10:00（第一根 bar open）—— 是否完全没有
           open_grace 限制？需在研究侧 simulate 函数里核实。
  B. ★★★★  §3.1 sizing 比例常数
     L1 3 样本 E/R qty = 2.56x / 2.02x / 1.28x。RiskPerTrade=0.02 / K_SL 两边都对齐，
     需逐项比：① daily_atr_bps 的来源是否同是 SMA10 日线？② CONTRACT_SPECS 里
     合约 multiplier / tick_size 两侧取值是否相同？③ R 侧 cap=4.0（单笔名义暴露封顶）
     在 E 侧有没有等价约束？
  C. ★★★   Skew 的 session 边界定义
     E 侧：按自然日 today 聚合 session 内 5m bar 计算 volume_weighted_skew（含夜盘）。
     R 侧 build_events / build_daily_features 是否把"21:00-次日 15:00"整个交易日
     归为同一天？如果 CZCE/DCE 夜盘品种跨自然日 bar 归属偏移一天 → A3_skew 数值会差很多。
  D. ★★    Sizing 的 equity 基期
     R 侧是否按单合约独立资金（每笔用 EQUITY_INIT 固定 100w + cap），
     E 侧回测共享组合资金池净值（随盈亏浮动）—— 即使 capital=100w 也会有几% 差。

===============================================================================
"""

from __future__ import annotations

import sys
from collections import deque
from math import log
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "workspace"))
sys.path.insert(0, str(REPO / "docs/workbench/va-asymmetry-composite/scripts"))

from strategies.classifiers.poc_va import (  # noqa: E402
    ClassifierConfig,
    compute_transition_series,
    evaluate_dataset,
    roll_t_pit,
    classify_tier,
    tier_direction,
)
import reproduce_research_side as RSIDE  # noqa: E402

CMP_DIR = REPO / "docs/workbench/va-asymmetry-composite/outputs/compare-r-e"
OUTPUT = CMP_DIR / "same_contract_day_three_layer_diff.parquet"
CSV_DIR = RSIDE.CSV_DIR


# =====================================================================
# 公共工具
# =====================================================================
def fmt_num(v, nd=4, w=10):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return f"{'N/A':>{w}}"
    if isinstance(v, (int, float, np.integer, np.floating)):
        return f"{float(v):>{w}.{nd}f}"
    return f"{str(v):>{w}}"


def rel_diff(rv, ev) -> str:
    if not isinstance(rv, (int, float, np.integer, np.floating)):
        return f"{'—':>14}"
    if not isinstance(ev, (int, float, np.integer, np.floating)):
        return f"{'—':>14}"
    if np.isnan(rv) or np.isnan(ev) or abs(rv) <= 1e-14:
        return f"{'—':>14}"
    d = (float(ev) - float(rv)) / abs(float(rv)) * 100
    return f"{d:>+13.2f}%"


def block(title: str, w=120):
    print()
    print("=" * w)
    print(f"  {title}")
    print("=" * w)


# =====================================================================
# 工程侧分类镜像（与策略 _on_new_day 逐行对齐）
#   窗口 10/10/10 / buf_ready 10/10/19，完全按 VAAsymmetryCompositeParams 默认
# =====================================================================
class EngMirror:
    def __init__(self, cfg=None):
        self.cfg = cfg or ClassifierConfig(
            skew_rank_win=10, atr_rank_win=10, trend_win=10,
            atr_entry_win=10, trend_entry_win=10,
        )
        self.skews = deque(maxlen=40)
        self.atrs = deque(maxlen=40)
        self.closes = deque(maxlen=40)

    def feed(self, skew_y, atr_bps_y, close_y):
        if not np.isnan(skew_y):
            self.skews.append(float(skew_y))
        if not np.isnan(atr_bps_y):
            self.atrs.append(float(atr_bps_y))
        if not np.isnan(close_y):
            self.closes.append(float(close_y))

    def classify(self) -> dict:
        out = dict(
            em_r_s=np.nan, em_r_a=np.nan, em_r_t=np.nan, em_trans=None,
            em_tier=None, em_direction="", em_daily_atr_bps=np.nan,
            em_buf_skew=len(self.skews), em_buf_atr=len(self.atrs),
            em_buf_close=len(self.closes), em_buf_ready=False,
        )
        cfg = self.cfg
        min_len = cfg.skew_rank_win  # 10
        trend_min_len = (cfg.trend_entry_win - 1) + cfg.trend_win  # 9 + 10 = 19
        if len(self.skews) >= min_len and len(self.atrs) >= min_len and len(self.closes) >= trend_min_len:
            out["em_buf_ready"] = True
            trend_offset = cfg.trend_entry_win - 1
            t_vals = []
            n_close = len(self.closes)
            for i in range(trend_offset, n_close):
                a, b = self.closes[i - trend_offset], self.closes[i]
                t_vals.append(log(b / a) if a > 0 and b > 0 else np.nan)
            s_sk = pd.Series(list(self.skews), dtype=float)
            s_at = pd.Series(list(self.atrs), dtype=float)
            s_tr = pd.Series(t_vals, dtype=float)
            r_s_raw = roll_t_pit(s_sk, cfg.skew_rank_win)
            r_s = 1.0 - float(r_s_raw.iloc[-1])
            ra_ser = roll_t_pit(s_at, cfg.atr_rank_win)
            r_a = float(ra_ser.iloc[-1])
            rt_ser = roll_t_pit(s_tr, cfg.trend_win)
            r_t = float(rt_ser.iloc[-1])
            trans_df = compute_transition_series(ra_ser)
            trans = str(trans_df["trans"].iloc[-1])
            tier = direction = None
            if not np.isnan(r_s) and not np.isnan(r_a) and not np.isnan(r_t):
                tier = classify_tier(float(r_s), float(r_a), float(r_t), trans)
                if tier:
                    direction = tier_direction(tier)
            out.update(em_r_s=r_s, em_r_a=r_a, em_r_t=r_t, em_trans=trans,
                       em_tier=tier, em_direction=direction or "",
                       em_daily_atr_bps=(float(self.atrs[-1]) if self.atrs else np.nan))
        return out


# =====================================================================
# 研究侧合约级 mirror（load once per contract）
# =====================================================================
class ResearchMirror:
    def __init__(self, symbol: str):
        self.symbol = symbol
        tick = RSIDE.get_tick(symbol)
        ev = RSIDE.build_events(symbol, tick)
        daily = RSIDE.build_daily_features(symbol)
        self.daily: pd.DataFrame = daily
        self.bars5m: pd.DataFrame | None = None
        if ev.empty or daily.empty:
            self.df = pd.DataFrame()
            return
        df = ev.merge(daily, left_on="event_date", right_on="date", how="left")
        df["event_time"] = pd.to_datetime(df["event_time"])
        df["event_date"] = pd.to_datetime(df["event_date"])
        df = df.sort_values(["contract", "event_time"]).reset_index(drop=True)
        df["signed_skew"] = -df["A3_skew"]
        df["signed_skew_rank_roll"] = RSIDE.rolling_pct_rank(df["signed_skew"], 100)
        for feat_col, roll_col in (("daily_atr_10_bps", "atr_rank_roll"),
                                   ("trend_ret_10d", "trend_rank_roll")):
            dg = df.drop_duplicates("event_date").sort_values("event_date").copy()
            dg[roll_col] = RSIDE.rolling_pct_rank(dg[feat_col], RSIDE.ROLLING_DAYS)
            df = df.merge(dg[["contract", "event_date", roll_col]], on=["contract", "event_date"], how="left")
        dates = sorted(df["event_date"].unique())
        if len(dates) < RSIDE.WARMUP_DAYS:
            self.df = pd.DataFrame()
            return
        wend = dates[RSIDE.WARMUP_DAYS - 1]
        df = df[df["event_date"] > wend].reset_index(drop=True)
        df = df.dropna(subset=["signed_skew_rank_roll", "atr_rank_roll", "trend_rank_roll"])
        cfg = ClassifierConfig()
        result = evaluate_dataset(
            df, cfg, a3_skew_col="A3_skew_spec", atr_col="daily_atr_spec",
            trend_col="trend_ret_M_spec",
        )
        ev_out = result.dropna(subset=["tier"]).copy()
        ev_out = ev_out.sort_values(["contract", "event_time"]).reset_index(drop=True)
        prev = ev_out.groupby("contract")["event_time"].shift(1)
        keep = prev.isna() | ((ev_out["event_time"] - prev) > pd.Timedelta(hours=RSIDE.DEDUP_H))
        ev_out = ev_out[keep].reset_index(drop=True)
        ev_out["entry_atr_bps"] = ev_out["daily_atr_spec"] / ev_out["close_t"] * 10000.0
        self.df = ev_out
        # 5m bars cache (load on demand)
        self._bars5m_loaded = False

    def ensure_5m(self):
        if self._bars5m_loaded:
            return
        p = CSV_DIR / f"{self.symbol}.tqsdk.5m.csv"
        if p.exists():
            bars = pd.read_csv(p, usecols=["datetime", "open", "high", "low", "close", "volume"])
            bars["datetime"] = pd.to_datetime(bars["datetime"])
            bars["date"] = pd.to_datetime(bars["datetime"].dt.date)
            self.bars5m = bars.sort_values("datetime").reset_index(drop=True)
        self._bars5m_loaded = True


def build_sample_set(r_trades: pd.DataFrame, e_pairs: pd.DataFrame) -> pd.DataFrame:
    """同合约同日三级样本集合。返回带 level 标签的索引行。"""
    R = r_trades.copy()
    E = e_pairs.copy()
    R["_day"] = pd.to_datetime(R["_entry_date"]).dt.date
    E["_day"] = pd.to_datetime(E["_entry_date"]).dt.date
    R["_dir"] = R["direction"].map(lambda x: "L" if float(x) == 1.0 else ("S" if float(x) == -1.0 else "?"))
    E["_dir"] = E["direction"].map(lambda x: "L" if float(x) == 1.0 else ("S" if float(x) == -1.0 else "?"))
    merged = R.merge(E, on=["contract", "_day"], how="inner", suffixes=("_R", "_E"))
    def level(row):
        strict = (row["tier_R"] == row["tier_E"]) and (row["_dir_R"] == row["_dir_E"])
        loose = row["_dir_R"] == row["_dir_E"]
        if strict:
            return "L1-strict"
        if loose:
            return "L2-loose"
        return "L3-dayboth"
    merged["level"] = merged.apply(level, axis=1)
    merged = merged.sort_values(["level", "contract", "_day"]).reset_index(drop=True)
    print(f"\n[同合约同日样本集合构造] 共 {len(merged)} 对：")
    for lv, n in merged["level"].value_counts().sort_index().items():
        print(f"    {lv:<10} {int(n):>6} 对")
    if len(merged) == 0:
        print("    FATAL: 一对都没有。检查 parquet 是否 contract 命名一致。")
    return merged


def print_sample_layer1_factor(rec: dict):
    print("  【层 1 · 因子输入】")
    rows = [
        ("A3_skew_spec",         rec.get("r_A3_skew_spec"),    None,                       5),
        ("daily_atr_10_bps",     rec.get("r_daily_atr_10_bps"),rec.get("em_daily_atr_bps"),3),
        ("trend_ret_10d_bps",    rec.get("r_trend_ret_10d"),   None,                       3),
        ("signed_skew",          rec.get("r_signed_skew"),    None,                       6),
        ("skew_rank (100d vs 20d t-PIT)", rec.get("r_skew_rank_100d"), rec.get("em_r_s"), 5),
        ("atr_rank  (20d vs t-PIT)",     rec.get("r_atr_rank_20d"),   rec.get("em_r_a"),   5),
        ("trend_rank(20d vs t-PIT)",     rec.get("r_trend_rank_20d"), rec.get("em_r_t"),   5),
        ("atr_trans (t-PIT)",    None, rec.get("em_trans"), 0),
        ("buf_ready (>=20+29)",  None, rec.get("em_buf_ready"), 0),
    ]
    print(f"  {'因子':<35}{'R 实际':>16}{'E 镜像':>16}{'Δ(相对)':>14}")
    print("  " + "-" * 84)
    for name, rv, ev, nd in rows:
        if name == "atr_trans (t-PIT)":
            print(f"  {name:<35}{fmt_num(rv, nd, 16)}{str(ev) if ev is not None else 'N/A':>16}{'—':>14}")
            continue
        if name == "buf_ready (>=20+29)":
            rs = "✅" if rv is None or rv else "N/A"
            es = "✅" if bool(ev) else "❌"
            print(f"  {name:<35}{rs:>16}{es:>16}{'—':>14}")
            continue
        print(f"  {name:<35}{fmt_num(rv, nd, 16)}{fmt_num(ev, nd, 16)}{rel_diff(rv, ev)}")


def print_sample_layer2_signal(rec: dict):
    print("\n  【层 2 · 分类信号】")
    r_tier = rec.get("r_tier", None)
    e_tier_act = rec.get("e_tier_actual", None)
    e_tier_em = rec.get("em_tier", None)
    r_dir = rec.get("r_dir", None)
    e_dir_act = rec.get("e_dir_actual", None)
    e_dir_em = rec.get("em_direction", None)
    r_dirm = "L" if rec.get("r_direction_mirror") in ("long", "L") else ("S" if rec.get("r_direction_mirror") in ("short", "S") else "?")
    e_dirm = "L" if e_dir_em == "long" else ("S" if e_dir_em == "short" else "?")
    print(f"  {'':<15}{'R 实际落盘':>16}{'E 实际落盘':>16}{'E 镜像(纯函数)':>16}")
    print(f"  {'tier':<15}{str(r_tier):>16}{str(e_tier_act):>16}{str(e_tier_em):>16}")
    print(f"  {'direction':<15}{str(r_dir):>16}{str(e_dir_act):>16}{str(e_dirm):>16}")
    print(f"  {'一致度':<15}"
          f"  R.tier==E.tier: {'✅' if str(r_tier)==str(e_tier_act) else '⚠️'}   "
          f"R.dir==E.dir: {'✅' if str(r_dir)==str(e_dir_act) else '⚠️'}   "
          f"E.tier(act)==E.mirror: {'✅' if str(e_tier_act)==str(e_tier_em) else '⚠️'}")


def print_sample_layer3_exec(rec: dict):
    print("\n  【层 3 · 交易执行】")
    print(f"  entry_time  R : {rec.get('r_entry_bar')}")
    print(f"  entry_time  E : {rec.get('e_entry_bar')}   Δ {rec.get('entry_dt_diff_sec')} s")
    rep = rec.get("r_entry_price")
    eep = rec.get("e_entry_price")
    rd = f"{rep:.4f}" if rep is not None and not np.isnan(rep) else "N/A"
    ed = f"{eep:.4f}" if eep is not None and not np.isnan(eep) else "N/A"
    reld = rec.get("entry_price_reldiff")
    reld_s = f"{reld*10000:.2f} bps" if isinstance(reld, float) and not np.isnan(reld) else "—"
    print(f"  entry_price R : {rd}   E : {ed}   rel Δ {reld_s}")
    rx = rec.get("r_exit_price"); ex = rec.get("e_exit_price")
    rxd = f"{rx:.4f}" if rx is not None and not np.isnan(rx) else "N/A"
    exd = f"{ex:.4f}" if ex is not None and not np.isnan(ex) else "N/A"
    print(f"  exit_price  R : {rxd}   E : {exd}")
    rr = rec.get("r_exit_reason"); er = rec.get("e_exit_reason")
    print(f"  exit_reason R : {rr}   E : {er}   一致 {'✅' if str(rr)==str(er) else '⚠️'}")
    rq = rec.get("r_qty_actual"); eq = rec.get("e_qty")
    rqs = f"{rq:,.2f}" if isinstance(rq, float) and not np.isnan(rq) else "N/A"
    eqs = f"{eq:,.2f}" if isinstance(eq, float) and not np.isnan(eq) else "N/A"
    print(f"  qty_actual  R : {rqs}   E : {eqs}")
    rgp = rec.get("r_pnl_gross_bps"); egp = rec.get("e_gross_pnl_ccy")
    rgps = f"{rgp:,.2f} bps" if isinstance(rgp, float) and not np.isnan(rgp) else "N/A"
    egps = f"{egp:+,.2f} ¥" if isinstance(egp, float) and not np.isnan(egp) else "N/A"
    print(f"  gross_pnl   R : {rgps}   E : {egps}")
    if rec.get("e_commission_ccy") is not None or rec.get("e_slippage_ccy") is not None:
        com = rec.get("e_commission_ccy"); slp = rec.get("e_slippage_ccy")
        coms = f"{com:,.2f}" if isinstance(com, float) and not np.isnan(com) else "N/A"
        slps = f"{slp:,.2f}" if isinstance(slp, float) and not np.isnan(slp) else "N/A"
        print(f"  E cost : 佣金 {coms} ¥ · 滑点 {slps} ¥")
    rpnl = rec.get("r_pnl_net_ccy"); epnl = rec.get("e_pnl_net_ccy")
    rps = f"{rpnl:+,.2f}" if isinstance(rpnl, float) and not np.isnan(rpnl) else "N/A"
    eps = f"{epnl:+,.2f}" if isinstance(epnl, float) and not np.isnan(epnl) else "N/A"
    diff = ""
    if isinstance(rpnl, float) and isinstance(epnl, float) and not np.isnan(rpnl) and not np.isnan(epnl):
        diff = f"   Δ {float(epnl)-float(rpnl):+,.2f} ¥"
    print(f"  net_pnl(¥)  R : {rps}   E : {eps}{diff}")


def main():
    # --- 读 R / E 两侧原始 parquet ---
    r_trades_path = CMP_DIR / "research_trades.parquet"
    e_pairs_path = CMP_DIR / "engine_paired_trades.parquet"
    if not r_trades_path.exists() or not e_pairs_path.exists():
        print("FATAL: 先跑 v1 对比生成 research_trades/engine_paired_trades parquet")
        return
    r_trades = pd.read_parquet(r_trades_path)
    e_pairs = pd.read_parquet(e_pairs_path)
    # --- 构造三级样本 ---
    samples = build_sample_set(r_trades, e_pairs)
    if samples.empty:
        # 最后兜底：R 侧 contract 是 "CZCE.MA601"，E 侧可能是 vt_symbol 格式 "MA601.CZCE"？尝试交换
        print("\n⚠️ 直接 contract 对齐失败，尝试 vt_symbol ↔ symbol 对调")
        def swap(s):
            if "." in s:
                a, b = s.split(".", 1)
                return f"{b}.{a}"
            return s
        r_trades2 = r_trades.copy(); r_trades2["contract"] = r_trades2["contract"].map(swap)
        samples = build_sample_set(r_trades2, e_pairs)
        if samples.empty:
            e_pairs2 = e_pairs.copy(); e_pairs2["contract"] = e_pairs2["contract"].map(swap)
            samples = build_sample_set(r_trades, e_pairs2)
    if samples.empty:
        return

    # --- 全局 cache ---
    r_mirrors: dict[str, ResearchMirror] = {}
    e_mirrors: dict[str, EngMirror] = {}
    records: list[dict] = []
    N = len(samples)

    # 打印限制：三级样本各展示前 3 个（太多刷屏）
    shown = {"L1-strict": 0, "L2-loose": 0, "L3-dayboth": 0}
    show_limits = {"L1-strict": 999, "L2-loose": 3, "L3-dayboth": 2}

    for idx, (_, srow) in enumerate(samples.iterrows(), 1):
        contract = srow["contract"]
        day = srow["_day"]
        level = srow["level"]
        r_tier, e_tier_actual = srow["tier_R"], srow["tier_E"]
        r_dir, e_dir_actual = srow["_dir_R"], srow["_dir_E"]
        show_this = shown[level] < show_limits[level]
        shown[level] += 1

        if show_this:
            block(f"[{level}] 样本 {idx}/{N} · {contract} · {day} · "
                  f"R(tier={r_tier}, dir={r_dir}) vs E(tier={e_tier_actual}, dir={e_dir_actual})")

        # --- R 侧因子：从研究 mirror 取 ---
        rm = r_mirrors.setdefault(contract, ResearchMirror(contract))
        r_factors = {}
        r_tier_from_mirror = r_dir_from_mirror = None
        r_entry_row = None
        if not rm.df.empty:
            sub = rm.df[
                (rm.df["contract"] == contract) &
                (pd.to_datetime(rm.df["event_date"]).dt.date == day)
            ]
            if not sub.empty:
                # 同日多小时事件：优先 tier/dir 匹配落盘的那一个
                cand = sub[(sub["tier"] == r_tier)]
                if cand.empty:
                    cand = sub.head(1)
                rr = cand.iloc[0]
                r_entry_row = rr
                r_factors.update(
                    r_A3_skew_spec=float(rr.get("A3_skew_spec", np.nan)),
                    r_daily_atr_bps_spec=float(rr.get("daily_atr_spec", np.nan)),
                    r_daily_atr_10_bps=float(rr.get("daily_atr_10_bps", np.nan)),
                    r_trend_ret_10d=float(rr.get("trend_ret_10d", np.nan)),
                    r_signed_skew=float(rr.get("signed_skew", np.nan)),
                    r_skew_rank_100d=float(rr.get("signed_skew_rank_roll", np.nan)),
                    r_atr_rank_20d=float(rr.get("atr_rank_roll", np.nan)),
                    r_trend_rank_20d=float(rr.get("trend_rank_roll", np.nan)),
                    r_entry_atr_bps=float(rr.get("entry_atr_bps", np.nan)),
                    r_event_time=pd.Timestamp(rr["event_time"]),
                    r_close_t=float(rr.get("close_t", np.nan)),
                )
                r_tier_from_mirror = rr.get("tier")
                r_dir_from_mirror = rr.get("direction")

        # --- E 侧镜像因子：先 feed 历史 ---
        em = e_mirrors.get(contract)
        if em is None or True:  # 每个样本独立播到 event_date 前一天（不跨样本积累，防偏）
            em_new = EngMirror()
            rm.ensure_5m()
            if rm.daily is not None and not rm.daily.empty and rm.bars5m is not None:
                daily = rm.daily.copy()
                daily["date_date"] = pd.to_datetime(daily["date"]).dt.date
                bars = rm.bars5m.copy()
                bars["date_date"] = bars["date"].dt.date
                for _, drow in daily.sort_values("date").iterrows():
                    d_date = drow["date_date"]
                    if d_date >= day:
                        break
                    sk_y = float(drow.get("A3_skew_spec", np.nan))
                    at_y = float(drow.get("daily_atr_10_bps", np.nan))
                    dbars = bars[bars["date_date"] == d_date]
                    cl_y = float(dbars["close"].iloc[-1]) if not dbars.empty else np.nan
                    em_new.feed(sk_y, at_y, cl_y)
            em = em_new
            e_mirrors[contract] = em  # 样本级 mirror（每个样本独立）
        em_out = em.classify()

        # --- seg 边界辅助 ---
        segs = {}
        if not rm.df.empty and r_entry_row is not None:
            hist = rm.df[rm.df["contract"] == contract].drop_duplicates("event_date").sort_values("event_date")
            for col, key in (("signed_skew_rank_roll", "sk"), ("atr_rank_roll", "at"), ("trend_rank_roll", "tr")):
                s = hist[col].dropna()
                cur = float(r_factors.get(f"r_{key}_rank_20d", np.nan)) if key != "sk" else float(r_factors.get("r_skew_rank_100d", np.nan))
                segs[f"seg_{key}_cur"] = cur
                segs[f"seg_{key}_seg12"] = float(s.quantile(1/3)) if len(s)>=5 else np.nan
                segs[f"seg_{key}_seg34"] = float(s.quantile(2/3)) if len(s)>=5 else np.nan
                segs[f"seg_{key}_min"] = float(s.min()) if len(s) else np.nan
                segs[f"seg_{key}_max"] = float(s.max()) if len(s) else np.nan

        # --- E 侧执行信息直接从 srow 拿 ---
        # 先算 entry_price_reldiff / dt_diff（srow 里只有 R/E 的 entry 列，没有直接算）
        rep = srow["entry_price_R"]; eep = srow["entry_price_E"]
        reld = abs(eep - rep) / abs(rep) if isinstance(rep, float) and isinstance(eep, float) and abs(rep) > 1e-12 else np.nan
        dtdiff = None
        try:
            dtdiff = abs((pd.Timestamp(srow.get("entry_bar_E")) -
                          pd.Timestamp(srow.get("entry_bar_R"))).total_seconds())
        except Exception:
            pass
        exec_rec = dict(
            r_entry_bar=srow.get("entry_bar_R"),
            e_entry_bar=srow.get("entry_bar_E"),
            entry_dt_diff_sec=dtdiff,
            r_entry_price=rep,
            e_entry_price=eep,
            entry_price_reldiff=reld,
            r_exit_reason=srow.get("exit_reason_R"),
            e_exit_reason=srow.get("exit_reason_E"),
            r_exit_price=srow.get("exit_price_R"),
            e_exit_price=srow.get("exit_price_E"),
            r_qty_raw=srow.get("qty_raw"),
            r_qty_actual=srow.get("qty_actual_R"),
            e_qty=srow.get("qty_actual_E"),
            r_pnl_net_ccy=srow.get("pnl_net_ccy"),
            e_pnl_net_ccy=srow.get("net_pnl_ccy"),
            r_pnl_gross_bps=srow.get("pnl_gross_bps"),
            e_gross_pnl_ccy=srow.get("gross_pnl_ccy"),
            e_commission_ccy=srow.get("commission_ccy"),
            e_slippage_ccy=srow.get("slippage_ccy"),
        )

        rec = dict(
            idx=idx, level=level, contract=contract, event_date=day,
            r_tier=r_tier, e_tier_actual=e_tier_actual,
            r_dir=r_dir, e_dir_actual=e_dir_actual,
            r_direction_mirror=r_dir_from_mirror, r_tier_from_mirror=r_tier_from_mirror,
            **r_factors, **em_out, **segs, **exec_rec,
        )
        records.append(rec)
        if not show_this:
            continue

        print_sample_layer1_factor(rec)
        print_sample_layer2_signal(rec)
        print_sample_layer3_exec(rec)

    out_df = pd.DataFrame(records)
    out_df.to_parquet(OUTPUT, index=False)

    # --- 汇总 ---
    block("三层对比 · 一致率汇总")
    if not out_df.empty:
        def sr(col_a, col_b):
            a = out_df[col_a].astype(str).fillna("")
            b = out_df[col_b].astype(str).fillna("")
            ok = int((a == b).sum()); n = int(len(a))
            return f"{ok}/{n} = {ok/n*100:>5.1f}%"

        for lv, g in out_df.groupby("level"):
            print(f"\n  Level {lv} (N={len(g)}):")
            ok = int(((g["r_tier"].astype(str) == g["e_tier_actual"].astype(str)) &
                      (g["r_dir"].astype(str) == g["e_dir_actual"].astype(str))).sum())
            print(f"    tier+dir 完全一致 R vs E          : {ok}/{len(g)} = {ok/max(len(g),1)*100:.1f}%")
            ok = int((g["r_dir"].astype(str) == g["e_dir_actual"].astype(str)).sum())
            print(f"    direction 一致 R vs E              : {ok}/{len(g)} = {ok/max(len(g),1)*100:.1f}%")
            ok = int((g["r_exit_reason"].astype(str) == g["e_exit_reason"].astype(str)).sum())
            print(f"    exit_reason 一致                   : {ok}/{len(g)} = {ok/max(len(g),1)*100:.1f}%")
            has_em = g["em_tier"].notna() & (g["em_tier"] != "None")
            if has_em.any():
                gg = g[has_em]
                print(f"    [E act vs E 镜像] tier 一致       : {int((gg['e_tier_actual'].astype(str)==gg['em_tier'].astype(str)).sum())}/{len(gg)}")
                ok = int((gg["e_dir_actual"].astype(str).map(lambda s: s.upper()) ==
                          gg["em_direction"].astype(str).map(lambda s: "L" if s=="long" else ("S" if s=="short" else "?"))).sum())
                print(f"    [E act vs E 镜像] direction 一致  : {ok}/{len(gg)}")
            prd = g["entry_price_reldiff"].dropna().astype(float) * 10000
            etd = g["entry_dt_diff_sec"].dropna().astype(float)
            pnl = g[["r_pnl_net_ccy", "e_pnl_net_ccy"]].dropna()
            print(f"    入场价相对差 median(bps) : {prd.median():>6.2f}  mean {prd.mean():>6.2f}")
            print(f"    入场时间差 median(s)    : {etd.median():>6.0f}  mean {etd.mean():>6.0f}")
            if len(pnl):
                diff = pnl["e_pnl_net_ccy"].astype(float) - pnl["r_pnl_net_ccy"].astype(float)
                print(f"    单笔净盈亏差 median(¥)  : {diff.median():>+10,.2f}  mean {diff.mean():>+10,.2f}  "
                      f"R Σ {pnl['r_pnl_net_ccy'].sum():>12,.2f}  E Σ {pnl['e_pnl_net_ccy'].sum():>12,.2f}")
    print(f"\n✓ 三层对比宽表落盘: {OUTPUT}  (共 {len(records)} 行)")


if __name__ == "__main__":
    main()
