"""容差对齐：验证 only_rs / only_fw 的 12 个差异是否为夜盘导致的日历日错位。

做法：对每侧单边键，在另一侧找 (symbol, direction, tier) 相同且 |日差|<=2 的候选，
若都能找到，则证明是日期错位而非信号真差异。
"""
from __future__ import annotations

import sqlite3

import pandas as pd

DB = "project_data/database/backtest/quant.db"
RES = "project_data/ai_tmp/p1_cap/cap1.0.trades.parquet"
ID_LO, ID_HI = 460, 574


def main() -> None:
    con = sqlite3.connect(DB)
    fw = pd.read_sql_query(
        f"select symbol, datetime, direction, reason from backtest_trades "
        f"where backtest_id between {ID_LO} and {ID_HI} and offset='open'",
        con,
    )
    con.close()
    fw["dt"] = pd.to_datetime(fw["datetime"])
    fw["entry_date"] = fw["dt"].dt.normalize()
    fw["direction"] = fw["direction"].map({"long": 1, "short": -1})
    fw["tier"] = fw["reason"].str.replace(r"^entry_", "", regex=True)
    fw = fw.rename(columns={"symbol": "symbol"})[["symbol", "entry_date", "direction", "tier"]]

    rs = pd.read_parquet(RES)
    rs["entry_date"] = pd.to_datetime(rs["entry_bar"]).dt.normalize()
    rs["direction"] = rs["direction"].astype(int)
    rs["tier"] = rs["tier"].astype(str)
    rs = rs[["contract", "entry_date", "direction", "tier"]].rename(columns={"contract": "symbol"})

    # 严格键
    fw_k = set(map(tuple, fw[["symbol", "entry_date", "direction"]].values))
    rs_k = set(map(tuple, rs[["symbol", "entry_date", "direction"]].values))
    only_rs = rs_k - fw_k
    only_fw = fw_k - rs_k

    def find_tolerant(target, other_df, tol_days=2):
        sym, d, direc = target
        cand = other_df[(other_df["symbol"] == sym) & (other_df["direction"] == direc)]
        for _, r in cand.iterrows():
            if abs((r["entry_date"] - d).days) <= tol_days:
                return (r["symbol"], r["entry_date"].date(), int(r["direction"]), r["tier"])
        return None

    print(f"严格单边: 仅研究 {len(only_rs)}  仅框架 {len(only_fw)}")
    matched_rs = sum(1 for k in only_rs if find_tolerant(k, fw) is not None)
    matched_fw = sum(1 for k in only_fw if find_tolerant(k, rs) is not None)
    print(f"±{2}天容差可解释: 仅研究 {matched_rs}/{len(only_rs)}  仅框架 {matched_fw}/{len(only_fw)}")

    print("\n[无法容差解释的仅研究]:")
    for k in only_rs:
        if find_tolerant(k, fw) is None:
            t = rs[(rs['symbol']==k[0])&(rs['entry_date']==k[1])&(rs['direction']==k[2])]['tier'].iloc[0]
            print("   ", k, "tier=", t)
    print("\n[无法容差解释的仅框架]:")
    for k in only_fw:
        if find_tolerant(k, rs) is None:
            t = fw[(fw['symbol']==k[0])&(fw['entry_date']==k[1])&(fw['direction']==k[2])]['tier'].iloc[0]
            print("   ", k, "tier=", t)


if __name__ == "__main__":
    main()
