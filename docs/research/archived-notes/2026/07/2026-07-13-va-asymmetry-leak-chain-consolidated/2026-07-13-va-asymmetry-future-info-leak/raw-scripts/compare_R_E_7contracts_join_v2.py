"""修正版：backtest_trades 每行=1笔完整交易，不用 open/close 配对！"""
from __future__ import annotations
import sys, os, sqlite3
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "workspace"))
import pandas as pd
import numpy as np

R_DIR = "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-composite/outputs/reproduce-research-side"
TARGET = ["SHFE.rb2501","SHFE.hc2501","DCE.m2501","DCE.y2501","DCE.i2501","INE.sc2503","CZCE.MA501","CZCE.TA501"]

# ─────────────────────────────────────────────
# 1. 研究侧：trades.parquet → (contract, entry_date, R_dir, R_tier, R_pnl)
# ─────────────────────────────────────────────
r_trades = pd.read_parquet(os.path.join(R_DIR, "trades.parquet"))
r_t = r_trades[r_trades["contract"].isin(TARGET)].copy()

def r_dir_map(row):
    d = row["direction"]
    if isinstance(d, (int, float)) and int(d) in (-1, 1):
        return "short" if int(d) == -1 else "long"
    s = str(d).lower()
    if s in ("short", "long"):
        return s
    t = str(row.get("tier", ""))
    if t.startswith("L_"):
        return "long"
    if t.startswith("S_"):
        return "short"
    return ""

r_t["R_dir"] = r_t.apply(r_dir_map, axis=1)
r_t["entry_date"] = pd.to_datetime(r_t["_entry_date"]).dt.date
r_t = r_t.sort_values(["contract", "entry_bar"]).reset_index(drop=True)
r_signal = r_t.groupby(["contract", "entry_date"], as_index=False).first()
r_signal = r_signal.rename(columns={
    "tier": "R_tier", "pnl_net_ccy": "R_pnl_net",
    "entry_bar": "R_entry_time", "entry_price": "R_entry_price",
    "exit_reason": "R_exit_reason",
})
r_signal = r_signal[["contract","entry_date","R_dir","R_tier","R_entry_time","R_entry_price","R_pnl_net","R_exit_reason"]]

print(f"研究侧：7合约 原始 trades={len(r_t)} → 按(合约,日)去重后信号数={len(r_signal)}")
print(f"  R_dir 分布:\n{r_signal['R_dir'].value_counts().to_string()}")
print(f"  R_tier 分布:\n{r_signal['R_tier'].value_counts().to_string()}")
print(f"  每合约笔数:\n{r_signal.groupby('contract').size().sort_values(ascending=False).to_string()}")

# ─────────────────────────────────────────────
# 2. 工程侧：backtest_trades 每行 = 1 笔完整交易（同时含 open_price + close_price + pnl）
# ─────────────────────────────────────────────
DB = "/Users/gaolei/Documents/src/quant/project_data/database/backtest/quant.db"
conn = sqlite3.connect(DB)
e_raw = pd.read_sql("""
    SELECT b.symbol AS contract, t.*
    FROM backtest_trades t JOIN backtests b ON t.backtest_id = b.id
    WHERE b.run_id = 18
    ORDER BY b.symbol, t.datetime ASC
""", conn)
conn.close()
print(f"\n工程侧：run_id=18 backtest_trades 行数={len(e_raw)} (预期=39笔)")
print(f"  direction 分布:\n{e_raw['direction'].value_counts().to_string()}")
print(f"  offset 分布:\n{e_raw['offset'].value_counts().to_string()}")
print(f"  reason 分布:\n{e_raw['reason'].value_counts().to_string()}")

# 标准化 E 侧字段
e_t = e_raw.copy()
e_t["E_dir"] = e_t["direction"].astype(str).str.lower().replace({"1": "long", "0": "short", "-1": "short"})
e_t["entry_date"] = pd.to_datetime(e_t["datetime"]).dt.date
e_t["E_entry_time"] = pd.to_datetime(e_t["datetime"])
e_t["E_entry_price"] = pd.to_numeric(e_t["open_price"], errors="coerce")
e_t["E_exit_price"] = pd.to_numeric(e_t["close_price"], errors="coerce")
e_t["E_qty"] = pd.to_numeric(e_t["quantity"], errors="coerce")
e_t["E_gross"] = pd.to_numeric(e_t["pnl"], errors="coerce").fillna(0.0)
e_t["E_fee"] = pd.to_numeric(e_t["commission"], errors="coerce").fillna(0.0)
e_t["E_pnl_net"] = e_t["E_gross"] - e_t["E_fee"]
e_t["E_exit_reason"] = e_t["reason"].astype(str)
e_t["E_tier"] = None  # 数据库没存 tier

# 按 (合约, entry_date) 去重，取最早 entry_time 的一笔
e_t = e_t.sort_values(["contract", "E_entry_time"]).reset_index(drop=True)
e_signal = e_t.groupby(["contract", "entry_date"], as_index=False).first()
e_signal = e_signal[["contract","entry_date","E_dir","E_tier","E_entry_time","E_entry_price","E_exit_price","E_qty","E_pnl_net","E_gross","E_fee","E_exit_reason"]]

print(f"\n工程侧：按(合约,日)去重后 信号数={len(e_signal)} (数据库 total_trades合计=39)")
print(f"  E_dir 分布:\n{e_signal['E_dir'].value_counts().to_string()}")
print(f"  E_exit_reason 分布:\n{e_signal['E_exit_reason'].value_counts().to_string()}")
print(f"  每合约笔数:\n{e_signal.groupby('contract').size().sort_values(ascending=False).to_string()}")
with pd.option_context("display.width", 260, "display.float_format", "{:,.2f}".format, "display.max_columns", 20):
    print(e_signal.to_string(index=False))

# ─────────────────────────────────────────────
# 3. Join 对比分四类
# ─────────────────────────────────────────────
print(f"\n{'='*90}\n3. (合约+入场日) Join 信号对比\n{'='*90}")
m = pd.merge(r_signal, e_signal, on=["contract","entry_date"], how="outer", indicator=True)
def classify(r):
    if r["_merge"] == "left_only":
        return "R-only（研究侧独有）"
    if r["_merge"] == "right_only":
        return "E-only（工程侧独有）"
    rd = str(r.get("R_dir","")).strip()
    ed = str(r.get("E_dir","")).strip()
    if rd == ed:
        return "共有+方向一致"
    return "共有+方向相反"
m["class"] = m.apply(classify, axis=1)

print(f"总对比样本: {len(m)}  (R侧{r_signal.shape[0]}笔 + E侧{e_signal.shape[0]}笔)")
cls_cnt = m["class"].value_counts()
print(f"\n类别分布（笔数）:\n{cls_cnt.to_string()}")
for cls, n in cls_cnt.items():
    pct = n / len(m) * 100 if len(m) else 0
    # 覆盖率指标：R侧有多少笔在E侧找到同方向信号
    pass

# 覆盖率定义：(共有+方向一致) / R侧总笔数  × 100%
total_R = (m["_merge"] != "right_only").sum()
cov_n = (m["class"] == "共有+方向一致").sum()
print(f"\n信号覆盖率定义（按研究侧基准）:")
print(f"  方向性覆盖率 = 共有+方向一致 / R侧总 = {cov_n}/{total_R} = {cov_n/max(1,total_R)*100:.2f}%")
print(f"  日期级覆盖率 = 共有(方向一致+相反) / R侧总 = {(m['_merge']=='both').sum()}/{total_R} = {(m['_merge']=='both').sum()/max(1,total_R)*100:.2f}%")

# 按合约 × 类别的交叉表
print(f"\n合约 × 类别 交叉表:")
ct = pd.crosstab(m["contract"], m["class"])
with pd.option_context("display.float_format", "{:,.0f}".format, "display.width", 220):
    print(ct.to_string())

# PnL 汇总
print(f"\nPnL 汇总（¥，按 class 合计）:")
pnl_sum = m.groupby("class").agg(
    笔数=("class", "count"),
    R_pnl合计=("R_pnl_net", lambda s: pd.to_numeric(s, errors="coerce").sum()),
    E_pnl合计=("E_pnl_net", lambda s: pd.to_numeric(s, errors="coerce").sum()),
)
with pd.option_context("display.float_format", "{:,.2f}".format):
    print(pnl_sum.to_string())

# 每合约 PnL 对比
print(f"\n合约 × 侧  PnL 合计对比（¥）:")
pnl_c = m.groupby("contract").agg(
    R_pnl合计=("R_pnl_net", lambda s: pd.to_numeric(s, errors="coerce").sum()),
    E_pnl合计=("E_pnl_net", lambda s: pd.to_numeric(s, errors="coerce").sum()),
    R笔数=("R_dir", lambda s: s.notna().sum()),
    E笔数=("E_dir", lambda s: s.notna().sum()),
)
with pd.option_context("display.float_format", "{:,.2f}".format):
    print(pnl_c.to_string())

# ─────────────────────────────────────────────
# 4. 关键问题定位：共有但方向相反 + 最常见 R-only top 10
# ─────────────────────────────────────────────
print(f"\n{'='*90}\n4. 深度问题定位\n{'='*90}")
opp = m[m["class"] == "共有+方向相反"]
if len(opp):
    print(f"共有+方向相反 ({len(opp)}笔):")
    with pd.option_context("display.width", 280, "display.float_format","{:,.2f}".format):
        cols = [c for c in ["contract","entry_date","R_dir","E_dir","R_tier","R_entry_time","E_entry_time",
                            "R_entry_price","E_entry_price","R_pnl_net","E_pnl_net","R_exit_reason","E_exit_reason"] if c in m.columns]
        print(opp[cols].to_string(index=False))
else:
    print("无「共有+方向相反」样本。")

# R-only 按合约看 tier 分布（看是不是 short 阵营全军覆没）
print(f"\nR-only（共{(m['class']=='R-only（研究侧独有）').sum()}笔）按 R_tier × R_dir 分布：")
ron = m[m["class"] == "R-only（研究侧独有）"]
if len(ron):
    print(pd.crosstab(ron["R_tier"], ron["R_dir"]).to_string())
    print(f"\nR-only 按合约 × R_dir 分布：")
    print(pd.crosstab(ron["contract"], ron["R_dir"]).to_string())

# E-only 按合约 × E_dir 分布
eon = m[m["class"] == "E-only（工程侧独有）"]
if len(eon):
    print(f"\nE-only（共{len(eon)}笔）按合约 × E_dir 分布：")
    print(pd.crosstab(eon["contract"], eon["E_dir"]).to_string())

# 保存
out_dir = "/Users/gaolei/Documents/src/quant/project_data/ai_tmp/R_E_signal_compare_7contracts"
os.makedirs(out_dir, exist_ok=True)
cols_save = [c for c in ["contract","entry_date","class","R_dir","E_dir","R_tier","E_tier",
                         "R_entry_time","E_entry_time","R_entry_price","E_entry_price",
                         "R_pnl_net","E_pnl_net","R_exit_reason","E_exit_reason"] if c in m.columns]
m[cols_save].sort_values(["contract","entry_date"]).to_csv(f"{out_dir}/signal_join_detail_v2.csv", index=False)
m[cols_save].sort_values(["contract","entry_date"]).to_parquet(f"{out_dir}/signal_join_detail_v2.parquet")
print(f"\n明细已保存: {out_dir}/signal_join_detail_v2.{{csv,parquet}}")

with pd.option_context("display.width", 300, "display.float_format","{:,.2f}".format, "display.max_rows", 200, "display.max_columns", 20):
    print("\n" + "=" * 90 + "\n完整明细:\n" + "=" * 90)
    print(m[cols_save].sort_values(["contract","entry_date"]).to_string(index=False))
