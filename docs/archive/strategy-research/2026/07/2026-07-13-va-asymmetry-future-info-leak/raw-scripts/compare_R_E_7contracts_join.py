"""构建 R/E 同口径信号列表并 join 对比。

信号口径：每 (合约, 入场自然日) 最多一条（同日去重，取首笔）
  - direction: long / short
  - tier: 阵营名（如果有）
  - entry_price / entry_time / pnl_net_ccy（如果有）

研究侧: 从 trades.parquet 取 7 合约子集
工程侧: 从 backtest_trades 开仓记录（offset=OPEN）配对成 (合约, 入场日)
"""
from __future__ import annotations
import sys, os, sqlite3
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "workspace"))
import pandas as pd
import numpy as np

R_DIR = "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-composite/outputs/reproduce-research-side"
TARGET = ["SHFE.rb2501","SHFE.hc2501","DCE.m2501","DCE.y2501","DCE.i2501","INE.sc2503","CZCE.MA501","CZCE.TA501"]

# ─────────────────────────────────────────────
# 1. 研究侧：trades.parquet → (contract, _entry_date, direction, tier, pnl, entry_time)
# ─────────────────────────────────────────────
r_trades = pd.read_parquet(os.path.join(R_DIR, "trades.parquet"))
r_t = r_trades[r_trades["contract"].isin(TARGET)].copy()
# direction int → str  (R侧: 1=long, -1=short，根据 tier 前缀校验)
def r_dir_map(row):
    t = row["tier"]
    expect = "long" if (isinstance(t, str) and t.startswith("L_")) else "short" if (isinstance(t, str) and t.startswith("S_")) else ""
    mapped = {-1: "short", 1: "long", "long": "long", "short": "short"}.get(row["direction"], "")
    return mapped or expect
r_t["dir"] = r_t.apply(r_dir_map, axis=1)
r_t["entry_date"] = pd.to_datetime(r_t["_entry_date"]).dt.date
# 按 (contract, entry_date) 去重留首笔（按 entry_bar 排序）
r_t = r_t.sort_values(["contract","entry_bar"]).reset_index(drop=True)
r_signal = r_t.groupby(["contract","entry_date"], as_index=False).first()
r_signal = r_signal.rename(columns={
    "tier": "R_tier", "dir": "R_dir", "pnl_net_ccy": "R_pnl_net",
    "entry_bar": "R_entry_time", "entry_price": "R_entry_price",
})
r_signal = r_signal[["contract","entry_date","R_dir","R_tier","R_entry_time","R_entry_price","R_pnl_net"]]
print(f"研究侧：7合约 原始 trades={len(r_t)}行 → 按日去重后 信号数={len(r_signal)}")

# ─────────────────────────────────────────────
# 2. 工程侧：backtest_trades（开仓 OPEN）+ 平仓 CLOSE 配对 → 单笔交易 pnl
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
print(f"工程侧：run_id=18 backtest_trades 原始行数={len(e_raw)}")
print(f"  offset 分布: {e_raw['offset'].value_counts().to_dict()}")
print(f"  direction 分布: {e_raw['direction'].value_counts().to_dict()}")

# 简化：vnpy 的 backtest_trades 里每一条 trade 记录通常是「单向成交」—— open 是开仓成交，close 是平仓成交。
# 把同一个合约同一 direction 的 open/close 按顺序一一配对（FIFO）。
def pair_trades(g: pd.DataFrame) -> pd.DataFrame:
    """按 FIFO 配对 open/close → 单笔交易记录（entry_date, dir, tier, pnl_net ...)."""
    opens = g[g["offset"].str.lower().isin(("open","0","open_long","open_short","buy","sell")) if g["offset"].dtype==object else g["offset"].isin((0,))].copy()
    closes = g[g["offset"].str.lower().isin(("close","1","close_long","close_short","sell","buy")) if g["offset"].dtype==object else g["offset"].isin((1,))].copy()
    # 更直接：vnpy的 offset 值看样例。我们直接根据数量 FIFO 配对：open 逐笔累积，close 逐笔消耗。
    rows = []
    open_stack = []  # list[dict]
    for _, t in g.sort_values("datetime").iterrows():
        off = str(t["offset"]).lower()
        # vnpy 惯例: offset = 'OPEN' / 'CLOSE' 或数字 0/1
        is_open = (off in ("open","0","开仓")) or ("open" in off) or (isinstance(t["offset"],(int,float)) and int(t["offset"]) == 0)
        is_close = (off in ("close","1","平仓")) or ("close" in off) or (isinstance(t["offset"],(int,float)) and int(t["offset"]) == 1)
        if is_open:
            open_stack.append(t)
        elif is_close and open_stack:
            o = open_stack.pop(0)
            # 方向：R 侧用 long/short，E 侧 direction 字段也有 long/short，直接用开仓的 direction
            dir_val = str(o["direction"]).lower()
            if dir_val in ("0","1"):
                dir_val = "long" if dir_val=="1" else "short"
            pnl_net = float(t["pnl"]) if "pnl" in t and pd.notna(t["pnl"]) else (float(t["close_price"])-float(o["open_price"]))*float(o["quantity"])
            fee = float(o.get("commission",0) or 0) + float(t.get("commission",0) or 0)
            net_after = pnl_net - fee
            rows.append({
                "contract": str(g.name) if isinstance(g.name, str) else str(o["symbol"] if "symbol" in o else o["contract"]),
                "entry_time": pd.to_datetime(o["datetime"]),
                "exit_time": pd.to_datetime(t["datetime"]),
                "entry_date": pd.to_datetime(o["datetime"]).date(),
                "E_dir": dir_val,
                "E_tier": None,
                "E_entry_price": float(o["open_price"]),
                "E_exit_price": float(t["close_price"]),
                "E_qty": float(o["quantity"]),
                "E_pnl_net": net_after,
                "E_gross": pnl_net,
                "E_fee": fee,
                "E_exit_reason": str(t.get("reason","")),
            })
    return pd.DataFrame(rows)

# 直接更简单的方法：用 reason / open-close 推断。如果上面识别错了 offset，我们换一种口径：
# 从工程侧 total_trades = 39 笔来看，数据库里 open+close 记录数应该是 78 条（每笔有开有平）。
# 检查：
e_raw2 = e_raw.copy()
if "contract" not in e_raw2.columns and "symbol" in e_raw2.columns:
    e_raw2["contract"] = e_raw2["symbol"]
# 简单方式：按 (contract, direction) 配对，每 2 行=1 笔交易（开+平 FIFO）
e_pair_rows = []
for c, g_c in e_raw2.sort_values("datetime").groupby("contract"):
    # 按顺序每两行配对（假设奇数行=开仓，偶数行=平仓）
    recs = list(g_c.itertuples())
    for i in range(0, len(recs), 2):
        if i+1 >= len(recs):
            break
        o = recs[i]; cl = recs[i+1]
        dir_val = str(getattr(o, "direction", "")).lower()
        if dir_val in ("0","1"):
            dir_val = "long" if dir_val == "1" else "short"
        try:
            entry_t = pd.to_datetime(getattr(o, "datetime"))
            exit_t = pd.to_datetime(getattr(cl, "datetime"))
            e_pair_rows.append({
                "contract": c,
                "entry_date": entry_t.date(),
                "E_entry_time": entry_t,
                "E_exit_time": exit_t,
                "E_dir": dir_val,
                "E_tier": None,
                "E_entry_price": float(getattr(o, "open_price", getattr(o, "price", 0))),
                "E_exit_price": float(getattr(cl, "close_price", getattr(cl, "price", 0))),
                "E_qty": float(getattr(o, "quantity", 0)),
                "E_gross_pnl": float(getattr(cl, "pnl", 0)),
                "E_fee": float(getattr(o, "commission", 0) or 0) + float(getattr(cl, "commission", 0) or 0),
                "E_pnl_net": float(getattr(cl, "pnl", 0)) - (float(getattr(o, "commission", 0) or 0) + float(getattr(cl, "commission", 0) or 0)),
                "E_exit_reason": str(getattr(cl, "reason", "")),
            })
        except Exception as ex:
            print(f"  配对失败 {c}[{i}:{i+2}]: {ex}")

e_signal = pd.DataFrame(e_pair_rows)
# 去重（同合约同入场日取第一笔）
if len(e_signal):
    e_signal = e_signal.sort_values(["contract","E_entry_time"]).groupby(["contract","entry_date"], as_index=False).first()
print(f"工程侧：配对后 单笔交易数={len(e_signal)} (预期=39)")
if len(e_signal):
    with pd.option_context("display.width", 240, "display.float_format","{:.2f}".format, "display.max_columns", 20):
        print(e_signal.to_string(index=False))
    print(f"\n工程侧方向分布:\n{e_signal['E_dir'].value_counts().to_string()}")
    print(f"\n工程侧每合约笔数:\n{e_signal.groupby('contract').size().sort_values(ascending=False).to_string()}")

# ─────────────────────────────────────────────
# 3. 按 (contract, entry_date, dir) 做 inner + outer 分四类
# ─────────────────────────────────────────────
print(f"\n{'='*80}\n3. 信号 join 对比\n{'='*80}")
if len(r_signal) == 0 or len(e_signal) == 0:
    print(f"  对比无法进行: R信号={len(r_signal)}  E信号={len(e_signal)}")
else:
    # 先只按 (contract, entry_date) merge，再看方向是否一致
    m = pd.merge(r_signal, e_signal, on=["contract","entry_date"], how="outer", indicator=True)
    def classify(r):
        if r["_merge"] == "left_only":
            return "R-only"
        if r["_merge"] == "right_only":
            return "E-only"
        # both: 看方向
        if r["R_dir"] == r["E_dir"]:
            return "共有+方向一致"
        return "共有+方向相反"
    m["class"] = m.apply(classify, axis=1)
    print(f"总 join 行数: {len(m)}")
    print(f"类别分布:\n{m['class'].value_counts().to_string()}")
    print(f"\n类别聚合（按合约）:")
    ct = m.groupby(["contract","class"]).size().unstack(fill_value=0)
    with pd.option_context("display.float_format","{:,.0f}".format, "display.width", 200):
        print(ct.to_string())

    # PnL 汇总
    print(f"\nPnL 汇总（每类合计）:")
    pnl_sum = m.groupby("class").agg({
        "R_pnl_net": lambda s: pd.to_numeric(s, errors="coerce").sum(),
        "E_pnl_net": lambda s: pd.to_numeric(s, errors="coerce").sum(),
    })
    with pd.option_context("display.float_format","{:,.2f}".format):
        print(pnl_sum.to_string())

    # 详细明细
    out_dir = "/Users/gaolei/Documents/src/quant/project_data/ai_tmp/R_E_signal_compare_7contracts"
    os.makedirs(out_dir, exist_ok=True)
    detail_path = f"{out_dir}/signal_join_detail.csv"
    cols = [c for c in ["contract","entry_date","class","R_dir","E_dir","R_tier","E_tier",
                        "R_entry_time","E_entry_time","R_entry_price","E_entry_price",
                        "R_pnl_net","E_pnl_net","E_exit_reason"] if c in m.columns]
    m[cols].sort_values(["contract","entry_date"]).to_csv(detail_path, index=False)
    print(f"\n明细已保存: {detail_path}")
    with pd.option_context("display.width", 280, "display.float_format","{:,.2f}".format, "display.max_rows", 200, "display.max_columns", 20):
        print("\n完整明细:\n")
        print(m[cols].sort_values(["contract","entry_date"]).to_string(index=False))
