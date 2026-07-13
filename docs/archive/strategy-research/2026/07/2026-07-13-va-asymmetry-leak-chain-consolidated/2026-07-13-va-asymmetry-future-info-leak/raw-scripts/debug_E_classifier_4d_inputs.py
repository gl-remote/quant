"""对比R/E两侧相同(合约,入场日)的分类器4维输入 r_s/r_a/r_t/trans
目标：定位为什么 E 侧只有 L_seg3_lowmid_up 一种 tier + 无 short 信号
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "workspace"))
import pandas as pd
import numpy as np
import sqlite3
from math import log
from strategies.classifiers.poc_va import (
    ClassifierConfig, TRANS_STABLE, classify_tier,
    compute_transition_series, roll_t_pit, tier_direction,
    volume_weighted_skew,
)

R_DIR = "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-composite/outputs/reproduce-research-side"
TARGET = ["SHFE.rb2501","SHFE.hc2501","DCE.m2501","DCE.y2501","DCE.i2501","INE.sc2503","CZCE.MA501","CZCE.TA501"]

# ═══════════════════════════════════════════════════════════════
# 1. 先拿到 R 侧所有 (contract, entry_date) 的 tier 列表
# ═══════════════════════════════════════════════════════════════
r_trades = pd.read_parquet(os.path.join(R_DIR, "trades.parquet"))
r_t = r_trades[r_trades["contract"].isin(TARGET)].copy()
r_t["entry_date"] = pd.to_datetime(r_t["_entry_date"]).dt.date
def r_dir_map(row):
    t = str(row.get("tier", ""))
    if t.startswith("L_"): return "long"
    if t.startswith("S_"): return "short"
    return str(row["direction"]).lower()
r_t["R_dir"] = r_t.apply(r_dir_map, axis=1)
r_signal = r_t.groupby(["contract","entry_date"], as_index=False).first()
r_signal = r_signal.rename(columns={"tier":"R_tier"})[["contract","entry_date","R_tier","R_dir","entry_bar","_entry_date"]]
print(f"R侧信号: {len(r_signal)}")
print(f"  R_tier 分布:\n{r_signal['R_tier'].value_counts().to_string()}\n")

# ═══════════════════════════════════════════════════════════════
# 2. 重建 E 侧每日 skew/atr/close 缓冲区并在特定日期计算 4 维输入
# ═══════════════════════════════════════════════════════════════
from strategies.core import State, Fill, Signal
from strategies.va_asymmetry_composite_strategy import VAAsymmetryCompositeStrategy, VAAsymmetryCompositeParams
from strategies.runtime.requirements import BarContext, Bar

DB = "/Users/gaolei/Documents/src/quant/project_data/database/backtest/quant.db"
conn = sqlite3.connect(DB)
# 拿 run_id=18 的 backtest id 列表
bt_ids = pd.read_sql("SELECT id, symbol FROM backtests WHERE run_id=18", conn)
print(f"run_id=18 backtests: {len(bt_ids)} 个合约\n")

# 读 parquet datafeed：datafeed 缓存
DATA_ROOT = "/Users/gaolei/Documents/src/quant/project_data/cache/datafeed"

def load_5m_csv(contract: str) -> pd.DataFrame:
    """加载单合约 5m parquet（datafeed cache）"""
    fp = os.path.join(DATA_ROOT, contract, "5m.parquet")
    if not os.path.exists(fp):
        return pd.DataFrame()
    df = pd.read_parquet(fp)
    # datetime 是 INDEX → 转成列
    if "datetime" not in df.columns and df.index.name in ("datetime", "ts", "date", None):
        df = df.reset_index()
        if df.index.name is not None:
            # 有些 parquet 的 index 有名字但 reset_index 后自动转列
            pass
    # 重命名列（datafeed parquet 标准列：datetime/open/high/low/close/volume）
    col_map = {}
    for c in df.columns:
        cl = str(c).lower()
        if cl in ("datetime", "ts", "date", "time", "index") and "datetime" not in col_map:
            col_map[c] = "datetime"
        elif cl == "open": col_map[c] = "open"
        elif cl == "high": col_map[c] = "high"
        elif cl == "low": col_map[c] = "low"
        elif cl == "close": col_map[c] = "close"
        elif cl == "volume": col_map[c] = "volume"
    df = df.rename(columns=col_map)
    if "datetime" not in df.columns:
        return pd.DataFrame()
    if not np.issubdtype(df["datetime"].dtype, np.datetime64):
        df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    return df[["datetime","open","high","low","close","volume"]]

def aggregate_daily(df_5m: pd.DataFrame) -> pd.DataFrame:
    """聚合 5m → 1d，计算 SMA(10) ATR 及 daily_atr_bps"""
    if df_5m.empty:
        return pd.DataFrame()
    d = df_5m.copy()
    d["date"] = d["datetime"].dt.date
    d1 = d.groupby("date", as_index=False).agg(
        open=("open","first"), high=("high","max"), low=("low","min"),
        close=("close","last"), volume=("volume","sum"),
        first_time=("datetime","first"), last_time=("datetime","last"),
    )
    d1 = d1.sort_values("date").reset_index(drop=True)
    # TR & ATR(10 SMA)
    prev_close = d1["close"].shift(1)
    tr = pd.concat([
        d1["high"] - d1["low"],
        (d1["high"] - prev_close).abs(),
        (d1["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    d1["tr"] = tr
    d1["atr10"] = tr.rolling(10, min_periods=1).mean()
    d1["daily_atr_bps"] = d1["atr10"] / d1["close"].shift(1) * 10000
    return d1

def build_session_bars(df_5m: pd.DataFrame, d: object) -> list[dict]:
    """取 date=d 的自然日所有 5m bar（用于 A3_skew 计算）"""
    mask = df_5m["datetime"].dt.date == d
    sub = df_5m[mask].sort_values("datetime").reset_index(drop=True)
    bars = []
    for _, r in sub.iterrows():
        bars.append({
            "open": float(r["open"]), "high": float(r["high"]),
            "low": float(r["low"]), "close": float(r["close"]),
            "volume": float(r["volume"]),
        })
    return bars

def compute_e_tier_for_date(contract: str, signal_date: object,
                            df_5m: pd.DataFrame, df_d: pd.DataFrame,
                            debug_print: bool = False):
    """在 signal_date 开盘前，用 E 侧逻辑重算 tier（模拟工程侧 on_bar → hourly 模式）
    返回 (r_s, r_a, r_t, trans, tier_name, direction)
    """
    N = 6  # daily_repeat_count 默认值
    config = ClassifierConfig(skew_rank_win=10, atr_rank_win=10, trend_win=10,
                             atr_entry_win=10, trend_entry_win=10)
    # 找 signal_date 在 df_d 中的位置
    d_dates = list(df_d["date"])
    if signal_date not in d_dates:
        return None
    idx = d_dates.index(signal_date)
    # 需要 idx 之前（含昨日）的数据 → 取 0..idx-1（昨日是 idx-1）
    if idx == 0:
        return None  # 没有昨日
    hist_d = df_d.iloc[:idx].copy().reset_index(drop=True)

    # 逐个历史日：结算 session skew → 重复 append N 次到 3 个缓冲区
    skews, atrs, closes = [], [], []
    HALF_EPS = 1e-10
    mid = 0.5 * float(N - 1)
    for i, row in hist_d.iterrows():
        d_i = row["date"]
        # 1) session skew = 当日所有 5m bar 的 volume_weighted_skew(closes, volumes)
        s_bars = build_session_bars(df_5m, d_i)
        sk = float("nan")
        yc = float("nan")
        if s_bars:
            sc = np.array([b["close"] for b in s_bars], dtype=float)
            sv = np.array([b["volume"] for b in s_bars], dtype=float)
            sk = volume_weighted_skew(sc, sv)
            yc = float(sc[-1])
        # 2) daily_atr_bps = hist_d.at[i, "daily_atr_bps"]
        atr_bps = float(hist_d.at[i, "daily_atr_bps"]) if pd.notna(hist_d.at[i, "daily_atr_bps"]) else float("nan")
        # 3) 重复 append N 次（含 1e-10 微扰）
        if not np.isnan(sk):
            for j in range(N):
                delta = (float(j) - mid) * HALF_EPS * max(1.0, abs(sk))
                skews.append(sk + delta)
        if not np.isnan(atr_bps):
            for j in range(N):
                delta = (float(j) - mid) * HALF_EPS * max(1.0, abs(atr_bps))
                atrs.append(atr_bps + delta)
        if not np.isnan(yc):
            for j in range(N):
                delta = (float(j) - mid) * HALF_EPS * max(1.0, yc)
                closes.append(yc + delta)
    if debug_print:
        print(f"  build buf: skews_len={len(skews)}, atrs_len={len(atrs)}, closes_len={len(closes)}")

    min_len = config.skew_rank_win
    trend_offset = config.trend_entry_win - 1
    trend_min_len = trend_offset + config.trend_win
    if len(skews) < min_len or len(atrs) < min_len or len(closes) < trend_min_len:
        return {"_warmup": True, "_sk_len": len(skews), "_cl_len": len(closes)}

    # 计算 s_trend = log(close[i] / close[i - trend_offset])
    t_vals = []
    n_close = len(closes)
    for i in range(trend_offset, n_close):
        c0 = float(closes[i - trend_offset])
        c1 = float(closes[i])
        if c0 > 0 and c1 > 0:
            t_vals.append(float(log(c1 / c0)))
        else:
            t_vals.append(float("nan"))
    s_trend = pd.Series(t_vals, dtype=float)

    # 4 维输入（E 侧：r_s = 1 - roll_t_pit(skew)，保持 skew 已互补语义）
    r_s_raw = roll_t_pit(pd.Series(skews, dtype=float), config.skew_rank_win)
    r_s = 1.0 - (float(r_s_raw.iloc[-1]) if len(r_s_raw) else float("nan"))
    r_a_series = roll_t_pit(pd.Series(atrs, dtype=float), config.atr_rank_win)
    r_a = float(r_a_series.iloc[-1]) if len(r_a_series) else float("nan")
    r_t_series = roll_t_pit(s_trend, config.trend_win)
    r_t = float(r_t_series.iloc[-1]) if len(r_t_series) else float("nan")

    trans = TRANS_STABLE
    if len(r_a_series) > 0 and r_a_series.notna().any():
        trans_df = compute_transition_series(r_a_series)
        trans = str(trans_df["trans"].iloc[-1])

    tier = None
    direction = ""
    if np.isfinite(r_s) and np.isfinite(r_a) and np.isfinite(r_t):
        tier = classify_tier(float(r_s), float(r_a), float(r_t), trans)
        if tier:
            direction = tier_direction(tier)
    return {
        "r_s": r_s, "r_a": r_a, "r_t": r_t, "trans": trans,
        "tier": tier, "direction": direction,
        "_sk_len": len(skews), "_cl_len": len(closes),
    }

# ═══════════════════════════════════════════════════════════════
# 3. 对 R 侧每个 (contract, entry_date) 计算 E 侧分类器 4 维输入
# ═══════════════════════════════════════════════════════════════
debug_rows = []
contracts_done = {}
for _, rs in r_signal.iterrows():
    c = rs["contract"]
    ed = rs["entry_date"]
    if c not in contracts_done:
        df_5 = load_5m_csv(c)
        df_d = aggregate_daily(df_5)
        contracts_done[c] = (df_5, df_d)
        print(f"[{c}] 5m bars={len(df_5)}, days={len(df_d)}")
    df_5, df_d = contracts_done[c]
    result = compute_e_tier_for_date(c, ed, df_5, df_d) or {}
    row = {
        "contract": c, "entry_date": ed,
        "R_tier": rs["R_tier"], "R_dir": rs["R_dir"],
        "R_entry_bar": rs["entry_bar"],
    }
    row.update(result)
    debug_rows.append(row)

dbg = pd.DataFrame(debug_rows)
print(f"\n{'='*100}\nE 侧独立计算结果 × R 侧信号分类\n{'='*100}")

# tier 对比
def compare_tier(r):
    rt = str(r.get("R_tier",""))
    et = str(r.get("tier","")) if pd.notna(r.get("tier")) else "(NA)"
    if rt == et: return "一致"
    if et == "(NA)" or et == "None": return "E-未命中"
    rd = "long" if rt.startswith("L_") else ("short" if rt.startswith("S_") else "")
    ed_ = "long" if et.startswith("L_") else ("short" if et.startswith("S_") else "")
    if rd == ed_: return "方向一致-tier不同"
    return "方向不同/其他"

dbg["cmp"] = dbg.apply(compare_tier, axis=1)
print(f"\ncmp 分布:\n{dbg['cmp'].value_counts().to_string()}")
print(f"\nE_tier 分布（R 侧有信号的日期）:\n{dbg['tier'].fillna('(NA)').value_counts().to_string()}")
print(f"\nE_direction 分布:\n{dbg['direction'].fillna('(NA)').value_counts().to_string()}")

# 细分 short 信号
print(f"\n{'='*60}\nR 侧 short 信号 × E 侧计算结果\n{'='*60}")
short_mask = dbg["R_dir"] == "short"
cols_show = ["contract","entry_date","R_tier","tier","direction","r_s","r_a","r_t","trans","cmp"]
with pd.option_context("display.width", 260, "display.float_format", "{:.4f}".format):
    if short_mask.any():
        print(dbg.loc[short_mask, cols_show].sort_values(["contract","entry_date"]).to_string(index=False))
    print(f"\nR 侧 long 信号 × E 侧计算结果（取前20条）:")
    long_mask = dbg["R_dir"] == "long"
    print(dbg.loc[long_mask, cols_show].head(20).sort_values(["contract","entry_date"]).to_string(index=False))

# 阈值对比：S 阵营需要的条件
print(f"\n{'='*60}\n阈值校验：short信号（S_*）需要的 4 维边界\n{'='*60}")
print("  S_seg12: s∈[0.81,1.00], a∈(0.67,1.00], t∈[0,0.20], trans ∈ {stable, trans_expand}")
print("  S_seg34: s∈[0.60,0.81), a∈(0.67,1.00], t∈[0,0.20], trans ∈ {stable, trans_expand}")
print("  S_seg2 : s∈(0.81,0.91], a∈(0.33,0.67], t∈[0,0.20], trans ∈ {trans_expand, trans_contract}")

# short 信号的 E 侧 r_a/r_t 统计
if short_mask.any():
    sdf = dbg[short_mask].copy()
    print(f"\nshort 信号的 E 侧 r_a 分布 (S阵营需 a>0.67):")
    print(f"  min={sdf['r_a'].min():.4f}, max={sdf['r_a'].max():.4f}, median={sdf['r_a'].median():.4f}")
    print(f"  r_a>0.67 的比例 = {(sdf['r_a']>0.67).mean()*100:.1f}% ({(sdf['r_a']>0.67).sum()}/{len(sdf)})")
    print(f"\nshort 信号的 E 侧 r_t 分布 (S阵营需 t<0.20):")
    print(f"  min={sdf['r_t'].min():.4f}, max={sdf['r_t'].max():.4f}, median={sdf['r_t'].median():.4f}")
    print(f"  r_t<0.20 的比例 = {(sdf['r_t']<0.20).mean()*100:.1f}% ({(sdf['r_t']<0.20).sum()}/{len(sdf)})")
    print(f"\nshort 信号的 E 侧 r_s 分布 (S阵营需 s>0.60):")
    print(f"  min={sdf['r_s'].min():.4f}, max={sdf['r_s'].max():.4f}, median={sdf['r_s'].median():.4f}")
    print(f"  r_s>0.60 的比例 = {(sdf['r_s']>0.60).mean()*100:.1f}% ({(sdf['r_s']>0.60).sum()}/{len(sdf)})")

# L 阵营分布
print(f"\n{'='*60}\nR 侧 long 信号 × E 侧 tier 未命中的原因统计\n{'='*60}")
long_na = dbg[long_mask & (dbg["tier"].isna() | (dbg["tier"] == "(NA)"))]
print(f"long信号中 E-未命中 = {len(long_na)}/{long_mask.sum()}")
if len(long_na) > 0:
    with pd.option_context("display.float_format", "{:.4f}".format):
        print(f"  r_s 范围: {long_na['r_s'].min():.3f} ~ {long_na['r_s'].max():.3f} (L_需要s∈[0,0.30])")
        print(f"  r_a 范围: {long_na['r_a'].min():.3f} ~ {long_na['r_a'].max():.3f} (L_seg3需要a≤0.67; L_seg12需要a>0.67)")
        print(f"  r_t 范围: {long_na['r_t'].min():.3f} ~ {long_na['r_t'].max():.3f} (L_seg3/12需要t≥0.75; L_seg2需要0.20<t<0.75)")

# 保存
out_dir = "/Users/gaolei/Documents/src/quant/project_data/ai_tmp/R_E_signal_compare_7contracts"
os.makedirs(out_dir, exist_ok=True)
dbg.to_parquet(f"{out_dir}/E_classifier_4d_input_debug.parquet")
dbg.to_csv(f"{out_dir}/E_classifier_4d_input_debug.csv", index=False)
print(f"\n保存: {out_dir}/E_classifier_4d_input_debug.*")
conn.close()
