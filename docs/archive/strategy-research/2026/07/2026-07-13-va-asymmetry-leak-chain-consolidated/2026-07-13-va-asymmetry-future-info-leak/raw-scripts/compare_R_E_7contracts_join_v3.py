"""v3: E信号=offset=open事件；完整交易PnL用FIFO配对算出来"""
from __future__ import annotations
import sys, os, sqlite3
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "workspace"))
import pandas as pd
import numpy as np

R_DIR = "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-composite/outputs/reproduce-research-side"
TARGET = ["SHFE.rb2501","SHFE.hc2501","DCE.m2501","DCE.y2501","DCE.i2501","INE.sc2503","CZCE.MA501","CZCE.TA501"]

# ── 1. 研究侧：完整交易 = 一次开仓信号 ──
r_trades = pd.read_parquet(os.path.join(R_DIR, "trades.parquet"))
r_t = r_trades[r_trades["contract"].isin(TARGET)].copy()
def r_dir_map(row):
    d = row["direction"]
    if isinstance(d, (int, float)) and int(d) in (-1, 1):
        return "short" if int(d) == -1 else "long"
    t = str(row.get("tier", ""))
    if t.startswith("L_"): return "long"
    if t.startswith("S_"): return "short"
    return str(d).lower()
r_t["R_dir"] = r_t.apply(r_dir_map, axis=1)
r_t["entry_date"] = pd.to_datetime(r_t["_entry_date"]).dt.date
r_t = r_t.sort_values(["contract","entry_bar"]).reset_index(drop=True)
r_signal = r_t.groupby(["contract","entry_date"], as_index=False).first()
r_signal = r_signal.rename(columns={
    "tier":"R_tier","pnl_net_ccy":"R_pnl_net","entry_bar":"R_entry_time",
    "entry_price":"R_entry_price","exit_reason":"R_exit_reason",
})
r_signal = r_signal[["contract","entry_date","R_dir","R_tier","R_entry_time","R_entry_price","R_pnl_net","R_exit_reason"]]
print(f"研究侧（R）: 按(合约,日)去重后 开仓信号数 = {len(r_signal)}")
print(f"  R_dir 分布:\n{r_signal['R_dir'].value_counts().to_string()}")
print(f"  R_tier 分布:\n{r_signal['R_tier'].value_counts().to_string()}")
print(f"  合约 × tier:")
ct = pd.crosstab(r_signal["contract"], r_signal["R_tier"])
with pd.option_context("display.width", 200):
    print(ct.to_string())

# ── 2. 工程侧：open行=开仓信号；close行用FIFO与对应open配对算出每笔完整交易的pnl ──
DB = "/Users/gaolei/Documents/src/quant/project_data/database/backtest/quant.db"
conn = sqlite3.connect(DB)
e_raw = pd.read_sql("""
    SELECT b.symbol AS contract, t.*
    FROM backtest_trades t JOIN backtests b ON t.backtest_id = b.id
    WHERE b.run_id = 24
    ORDER BY b.symbol, t.datetime ASC
""", conn)
conn.close()

def e_tier_from_reason(r):
    s = str(r)
    if s.startswith("entry_"):
        return s[len("entry_"):]
    return None

opens_raw = e_raw[e_raw["offset"].astype(str).str.lower() == "open"].copy()
closes_raw = e_raw[e_raw["offset"].astype(str).str.lower() == "close"].copy()

print(f"\n工程侧（E）: open={len(opens_raw)}次  close={len(closes_raw)}次")

# 每个合约内部 FIFO 配对: 用open逐笔累积队列，close逐笔出队配对
pair_rows = []
for c in sorted(set(opens_raw["contract"].tolist() + closes_raw.get("contract", pd.Series(dtype=object)).tolist())):
    ops = opens_raw[opens_raw["contract"] == c].sort_values("datetime").reset_index(drop=True)
    cls = closes_raw[closes_raw["contract"] == c].sort_values("datetime").reset_index(drop=True)
    q = []
    for _, o in ops.iterrows():
        q.append(o)
    for _, cl in cls.iterrows():
        if not q:
            break
        o = q.pop(0)
        tier = e_tier_from_reason(o.get("reason",""))
        direction = str(o["direction"]).lower()
        if direction in ("1","0","-1"):
            direction = "long" if direction == "1" else "short"
        open_p = float(o["open_price"] if pd.notna(o.get("open_price")) else o.get("price", 0))
        close_p = float(cl["close_price"] if pd.notna(cl.get("close_price")) else cl.get("price", 0))
        qty = float(o["quantity"])
        size = 1  # contract multiplier unknown — use raw pnl
        gross = float(cl["pnl"]) if pd.notna(cl.get("pnl")) else (close_p - open_p) * qty * 1
        fee_o = float(o.get("commission") or 0)
        fee_c = float(cl.get("commission") or 0)
        pair_rows.append({
            "contract": c,
            "E_entry_time": pd.to_datetime(o["datetime"]),
            "E_exit_time": pd.to_datetime(cl["datetime"]),
            "entry_date": pd.to_datetime(o["datetime"]).date(),
            "E_dir": direction,
            "E_tier": tier,
            "E_entry_price": open_p,
            "E_exit_price": close_p,
            "E_qty": qty,
            "E_gross": gross,
            "E_fee": fee_o + fee_c,
            "E_pnl_net": gross - fee_o - fee_c,
            "E_exit_reason": str(cl.get("reason", "")),
            "E_decision": str(o.get("reason", "")),
        })
    # 剩下没配对的 open：未平仓（没有 close），记为开仓信号，pnl=NaN
    for o in q:
        tier = e_tier_from_reason(o.get("reason",""))
        direction = str(o["direction"]).lower()
        if direction in ("1","0","-1"):
            direction = "long" if direction == "1" else "short"
        pair_rows.append({
            "contract": c,
            "E_entry_time": pd.to_datetime(o["datetime"]),
            "E_exit_time": pd.NaT,
            "entry_date": pd.to_datetime(o["datetime"]).date(),
            "E_dir": direction,
            "E_tier": tier,
            "E_entry_price": float(o["open_price"] if pd.notna(o.get("open_price")) else o.get("price", 0)),
            "E_exit_price": np.nan,
            "E_qty": float(o["quantity"]),
            "E_gross": np.nan,
            "E_fee": np.nan,
            "E_pnl_net": np.nan,
            "E_exit_reason": "(未平仓)",
            "E_decision": str(o.get("reason", "")),
        })

e_pairs = pd.DataFrame(pair_rows).sort_values(["contract","E_entry_time"]).reset_index(drop=True)
# 去重同合约同入场日
e_signal = e_pairs.groupby(["contract","entry_date"], as_index=False).first()
print(f"工程侧（E）: FIFO配对后 完整交易数={len(e_pairs)}（含未平仓）；按(合约,日)去重后开仓信号数={len(e_signal)}")
print(f"  E_dir 分布:\n{e_signal['E_dir'].value_counts(dropna=False).to_string()}")
print(f"  E_tier 分布:\n{e_signal['E_tier'].value_counts(dropna=False).to_string()}")
print(f"  E_decision (open的reason) 分布:\n{e_signal['E_decision'].value_counts(dropna=False).to_string()}")
print(f"  合约 × tier:")
ct_e = pd.crosstab(e_signal["contract"].fillna("(NA)"), e_signal["E_tier"].fillna("(NA)"))
with pd.option_context("display.width", 200):
    print(ct_e.to_string())

with pd.option_context("display.width", 280, "display.float_format", "{:,.2f}".format, "display.max_columns", 20):
    print(f"\nE 侧明细:\n{e_signal.to_string(index=False)}")

# ── 3. Join 对比 ──
print(f"\n{'='*100}\n3. Join 对比 (合约+入场日)\n{'='*100}")
m = pd.merge(r_signal, e_signal, on=["contract","entry_date"], how="outer", indicator=True)
def classify(r):
    if r["_merge"] == "left_only":  return "R-only（研究侧独有）"
    if r["_merge"] == "right_only": return "E-only（工程侧独有）"
    rd, ed = str(r.get("R_dir","")).strip(), str(r.get("E_dir","")).strip()
    rt, et = str(r.get("R_tier","")).strip(), str(r.get("E_tier","")).strip()
    if rd == ed:
        if rt == et: return "共有+方向一致+tier一致"
        return "共有+方向一致+tier不同"
    return "共有+方向相反"
m["class"] = m.apply(classify, axis=1)

total_R = (m["_merge"] != "right_only").sum()
total_E = (m["_merge"] != "left_only").sum()
cls_cnt = m["class"].value_counts()
print(f"R 侧总信号 = {total_R}   E 侧总信号 = {total_E}")
print(f"类别分布（笔数）:\n{cls_cnt.to_string()}")
match_n = ((m["class"] == "共有+方向一致+tier一致") | (m["class"] == "共有+方向一致+tier不同")).sum()
exact_n = (m["class"] == "共有+方向一致+tier一致").sum()
print(f"\n覆盖率:")
print(f"  方向+日期 = {match_n}/{total_R} = {match_n/max(1,total_R)*100:.2f}%")
print(f"  方向+日期+tier完全一致 = {exact_n}/{total_R} = {exact_n/max(1,total_R)*100:.2f}%")
print(f"  日期级（不管方向/tier）= {(m['_merge']=='both').sum()}/{total_R} = {(m['_merge']=='both').sum()/max(1,total_R)*100:.2f}%")

print(f"\n合约 × 类别:")
with pd.option_context("display.width", 260):
    print(pd.crosstab(m["contract"].fillna("(NA)"), m["class"]).to_string())

print(f"\nPnL 合计（¥）:")
pnl_agg = m.groupby("class").agg(
    笔数=("class","count"),
    R_pnl=("R_pnl_net", lambda s: pd.to_numeric(s, errors="coerce").sum()),
    E_pnl=("E_pnl_net", lambda s: pd.to_numeric(s, errors="coerce").sum()),
)
with pd.option_context("display.float_format", "{:,.2f}".format):
    print(pnl_agg.to_string())

# 深度问题 1：R-only 的 tier 分布（E 侧没命中的研究侧独有信号）
print(f"\n{'='*100}\n4. 深度问题定位\n{'='*100}")
ron = m[m["class"].str.startswith("R-only")]
print(f"R-only {len(ron)}笔 × R_tier × R_dir:")
with pd.option_context("display.width", 220):
    print(pd.crosstab(ron["R_tier"].fillna("NA"), ron["R_dir"].fillna("NA")).to_string())
    print(f"\nR-only 合约 × tier:")
    print(pd.crosstab(ron["contract"].fillna("NA"), ron["R_tier"].fillna("NA")).to_string())

# 深度问题 2：共有但 tier 不同 / 方向相反 的样本
wrong = m[m["class"].str.contains("tier不同|方向相反", na=False)]
if len(wrong):
    print(f"\n共有+方向/阵营不一致 ({len(wrong)}笔):")
    cols = [c for c in ["contract","entry_date","class","R_dir","E_dir","R_tier","E_tier",
                        "R_entry_time","E_entry_time","R_pnl_net","E_pnl_net"] if c in m.columns]
    with pd.option_context("display.width", 300, "display.float_format", "{:,.2f}".format):
        print(wrong[cols].sort_values(["contract","entry_date"]).to_string(index=False))

# 深度问题 3：E-only 的 tier
eon = m[m["class"].str.startswith("E-only")]
if len(eon):
    print(f"\nE-only {len(eon)}笔 × E_tier × E_dir:")
    with pd.option_context("display.width", 220):
        print(pd.crosstab(eon["E_tier"].fillna("NA"), eon["E_dir"].fillna("NA")).to_string())

# 保存
out_dir = "/Users/gaolei/Documents/src/quant/project_data/ai_tmp/R_E_signal_compare_7contracts"
os.makedirs(out_dir, exist_ok=True)
cols_save = [c for c in ["contract","entry_date","class","R_dir","E_dir","R_tier","E_tier","E_decision",
                         "R_entry_time","E_entry_time","R_pnl_net","E_pnl_net","R_exit_reason","E_exit_reason"] if c in m.columns]
m[cols_save].sort_values(["contract","entry_date"]).to_csv(f"{out_dir}/signal_join_detail_v3.csv", index=False)
m[cols_save].sort_values(["contract","entry_date"]).to_parquet(f"{out_dir}/signal_join_detail_v3.parquet")
print(f"\n明细保存: {out_dir}/signal_join_detail_v3.{{csv,parquet}}")

with pd.option_context("display.width", 320, "display.float_format", "{:,.2f}".format, "display.max_rows", 200, "display.max_columns", 20):
    print(f"\n完整明细:\n" + "="*100)
    print(m[cols_save].sort_values(["contract","entry_date"]).to_string(index=False))
