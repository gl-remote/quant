"""信号级对照：框架 CLI 进场 vs 研究引擎进场。

重点不是逐笔盈亏（两边 sizing/资本口径不同，绝对盈亏不可比），
而是"是否对同一 (合约, 进场日, 方向, tier) 发出进场信号"——这才是框架
A 层查表 + tier 门控 + 时机逻辑是否正确的核心验证。

框架端：backtest_trades 中 offset='open' 的行为进场，reason 含 tier 标签。
研究端：cap1.0.trades.parquet 的 entry_bar/direction/tier。
"""
from __future__ import annotations

import re
import sqlite3

import pandas as pd

DB = "project_data/database/backtest/quant.db"
RES = "project_data/ai_tmp/p1_cap/cap1.0.trades.parquet"
ID_LO, ID_HI = 460, 574


def parse_tier(reason: str) -> str:
    # reason 形如 entry_S_seg12_high_dn / entry_L_seg3_lowmid_up
    m = re.match(r"entry_(.+)", str(reason))
    return m.group(1) if m else ""


def load_framework_entries() -> pd.DataFrame:
    con = sqlite3.connect(DB)
    q = f"""
        select symbol, datetime, direction, reason
        from backtest_trades
        where backtest_id between {ID_LO} and {ID_HI}
          and offset = 'open'
        order by symbol, datetime
    """
    rows = con.execute(q).fetchall()
    con.close()
    df = pd.DataFrame(rows, columns=["symbol", "dt", "direction", "reason"])
    df["dt"] = pd.to_datetime(df["dt"])
    df["entry_date"] = df["dt"].dt.normalize()
    df["direction"] = df["direction"].map({"long": 1, "short": -1})
    df["tier"] = df["reason"].map(parse_tier)
    return df[["symbol", "entry_date", "direction", "tier"]]


def main() -> None:
    fw = load_framework_entries()
    print(f"[框架] 进场信号数: {len(fw)}  合约数: {fw['symbol'].nunique()}")

    rs = pd.read_parquet(RES)
    rs = rs.copy()
    rs["entry_date"] = pd.to_datetime(rs["entry_bar"]).dt.normalize()
    rs["direction"] = rs["direction"].astype(int)
    rs["tier"] = rs["tier"].astype(str)
    rs_entries = rs[["contract", "entry_date", "direction", "tier"]].rename(
        columns={"contract": "symbol"}
    )
    print(f"[研究] 进场信号数: {len(rs_entries)}  合约数: {rs_entries['symbol'].nunique()}")

    fw_k = fw.set_index(["symbol", "entry_date", "direction"])
    rs_k = rs_entries.set_index(["symbol", "entry_date", "direction"])

    common = fw_k.index.intersection(rs_k.index)
    only_fw = fw_k.index.difference(rs_k.index)
    only_rs = rs_k.index.difference(fw_k.index)

    print(f"\n[信号对齐] 共键: {len(common)}")
    print(f"  仅框架(框架有/研究无): {len(only_fw)}")
    print(f"  仅研究(研究有/框架无): {len(only_rs)}")

    # tier 一致性（共键内，用 merge 避免重复索引长度不一致）
    if len(common):
        fa = fw_k.loc[common].reset_index()
        ra = rs_k.loc[common].reset_index()
        merged = fa.merge(
            ra, on=["symbol", "entry_date", "direction"], suffixes=("_fw", "_rs")
        )
        mism = (merged["tier_fw"] != merged["tier_rs"]).sum()
        print(f"  共键内可配对 {len(merged)} 行，tier 不一致数: {mism}")

    print("\n[仅研究样本] (框架漏发信号):")
    for k in list(only_rs)[:12]:
        print("   ", k, "tier=", rs_k.loc[k, "tier"])
    print("\n[仅框架样本] (框架多发信号):")
    for k in list(only_fw)[:12]:
        print("   ", k, "tier=", fw_k.loc[k, "tier"])

    # 按合约统计覆盖率
    cov = []
    for sym in sorted(set(fw["symbol"]) | set(rs_entries["symbol"])):
        f_n = (fw["symbol"] == sym).sum()
        r_n = (rs_entries["symbol"] == sym).sum()
        cov.append((sym, r_n, f_n))
    cov_df = pd.DataFrame(cov, columns=["symbol", "research", "framework"])
    miss = cov_df[(cov_df["research"] > 0) & (cov_df["framework"] == 0)]
    print(f"\n[合约覆盖] 研究有信号但框架0信号的合约数: {len(miss)}")
    if len(miss):
        print(miss.head(15).to_string(index=False))


if __name__ == "__main__":
    main()
