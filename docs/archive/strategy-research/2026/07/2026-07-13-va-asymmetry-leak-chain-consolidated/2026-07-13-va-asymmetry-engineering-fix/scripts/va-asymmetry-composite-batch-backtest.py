"""批量回测 + 跨品种合并：跑 2601/2512 主力合约，合并算组合指标。"""
import sys, json, sqlite3, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workspace"))

import pandas as pd
import numpy as np

DB = Path(__file__).resolve().parents[2] / "project_data/database/backtest/quant.db"
SYMBOLS = [
    "DCE.m2601", "DCE.p2601", "DCE.c2601", "DCE.cs2601", "DCE.i2601", "DCE.y2601",
    "INE.sc2512",
    "SHFE.ag2601", "SHFE.al2601", "SHFE.au2512", "SHFE.cu2601", "SHFE.hc2601", "SHFE.rb2601",
]

def run_backtest(sym: str) -> int | None:
    """调用 CLI 回测，返回 backtest_id。"""
    import subprocess
    cmd = [
        "uv", "run", "python", "main.py", "backtest",
        "--env", "backtest", "--engine", "vnpy", "--mode", "single",
        "--strategy", "va_asymmetry_composite", "--symbol", sym,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=Path(__file__).resolve().parents[2])
    for line in result.stdout.split("\n"):
        if "backtest_id=" in line and "清算完成" in line:
            try:
                return int(line.split("backtest_id=")[1].split()[0])
            except (ValueError, IndexError):
                pass
    for line in result.stdout.split("\n"):
        if "backtest_id=" in line:
            try:
                return int(line.split("backtest_id=")[1].split()[0])
            except (ValueError, IndexError):
                pass
    # fallback: query latest
    return None


def get_combined_metrics(backtest_ids: list[int]):
    """从数据库读取清算数据，按时间合并所有品种，计算组合日收益率曲线和指标。"""
    conn = sqlite3.connect(str(DB))
    ids_str = ",".join(str(i) for i in backtest_ids)

    # 1. 读取所有清算
    clearings = pd.read_sql(f"""
        SELECT backtest_id, symbol, open_time, close_time, net_pnl, holding_seconds,
               volume, open_price, contract_multiplier, direction, open_reason
        FROM trade_clearings WHERE backtest_id IN ({ids_str})
        ORDER BY close_time
    """, conn)

    # 2. 读取回测汇总
    backtests = pd.read_sql(f"""
        SELECT id, symbol, start_date, end_date, initial_capital, total_trades, total_net_pnl
        FROM backtests WHERE id IN ({ids_str})
    """, conn)
    conn.close()

    if clearings.empty:
        print("  无交易数据")
        return

    clearings["open_time"] = pd.to_datetime(clearings["open_time"])
    clearings["close_time"] = pd.to_datetime(clearings["close_time"])

    # 3. 计算每个品种的逐日净值（持仓期间按比例分配盈亏）
    # 简化：用清算净盈亏构造每日权益曲线
    # 取全局时间范围
    all_dates = pd.date_range(
        clearings["close_time"].min().normalize(),
        clearings["close_time"].max().normalize(),
        freq="D"
    )
    # 初始总资金 = 品种数 × 单品种初始资金
    single_cap = float(backtests["initial_capital"].iloc[0])
    n_symbols = len(backtest_ids)
    total_init_cap = single_cap * n_symbols

    # 逐日净值：初始=总资金，每天叠加所有品种当天的 net_pnl
    daily_pnl = pd.Series(0.0, index=all_dates)
    for _, row in clearings.iterrows():
        close_date = row["close_time"].normalize()
        if close_date in daily_pnl.index:
            daily_pnl[close_date] += row["net_pnl"]
        else:
            # 找最近的日期
            nearest = daily_pnl.index[daily_pnl.index <= close_date]
            if len(nearest) > 0:
                daily_pnl[nearest[-1]] += row["net_pnl"]

    equity = total_init_cap + daily_pnl.cumsum()
    daily_ret = daily_pnl / total_init_cap

    # 4. 计算指标
    total_net = daily_pnl.sum()
    total_ret = total_net / total_init_cap
    n_days = len(all_dates)
    ann_ret = (1 + total_ret) ** (365 / max(n_days, 1)) - 1

    # 日夏普
    daily_std = daily_ret.std()
    daily_mean = daily_ret.mean()
    ann_sharpe = (daily_mean / daily_std * np.sqrt(365)) if daily_std > 1e-12 else 0

    # 最大回撤
    peak = equity.cummax()
    dd = (equity - peak) / peak
    max_dd = dd.min()

    # 胜率
    nl = len(clearings)
    nw = (clearings["net_pnl"] > 0).sum()
    win_rate = nw / nl if nl > 0 else 0

    # 持仓统计
    total_hold_hours = clearings["holding_seconds"].sum() / 3600
    # 资金使用率：总名义市值 / 总初始资金（按同时持仓最大计算开销略，用平均）
    clearings["notional"] = clearings["volume"] * clearings["open_price"] * clearings["contract_multiplier"]
    avg_notional = clearings["notional"].mean()
    max_notional = clearings.groupby(clearings["open_time"].dt.normalize())["notional"].sum().max()
    cap_util = max_notional / total_init_cap if total_init_cap > 0 else 0

    # 5. 输出
    print(f"\n{'='*70}")
    print(f"组合汇总 ({n_symbols} 品种合并, {n_days} 天)")
    print(f"{'='*70}")
    print(f"  总初始资金: {total_init_cap:,.0f}")
    print(f"  总交易笔数: {nl}")
    print(f"  盈利笔数: {nw}  胜率: {win_rate:.0%}")
    print(f"  总净盈亏: {total_net:,.0f}")
    print(f"  总收益率: {total_ret*100:.2f}%")
    print(f"  年化收益率: {ann_ret*100:.2f}%")
    print(f"  日收益均值: {daily_mean*100:.4f}%")
    print(f"  日收益标准差: {daily_std*100:.4f}%")
    print(f"  夏普比率: {ann_sharpe:.2f}")
    print(f"  最大回撤: {max_dd*100:.2f}%")
    print(f"  总持仓时间: {total_hold_hours:.0f}小时 ({total_hold_hours/(n_days*24)*100:.1f}% 时间)")
    print(f"  最大同时持仓市值: {max_notional:,.0f} ({cap_util*100:.0f}% 资金占用)")

    # 6. 每日明细
    active_days = daily_ret[daily_ret != 0]
    print(f"  有交易天数: {len(active_days)}/{n_days} ({len(active_days)/n_days*100:.1f}%)")

    # 7. 各品种贡献
    print(f"\n{'─'*70}")
    print(f"{'品种':<18} {'笔数':>4} {'净盈亏':>10} {'胜率':>6} {'占总额':>8}")
    print(f"{'─'*70}")
    for sym in sorted(clearings["symbol"].unique()):
        sub = clearings[clearings["symbol"] == sym]
        pnl = sub["net_pnl"].sum()
        wr = (sub["net_pnl"] > 0).mean()
        pct = pnl / total_net * 100 if abs(total_net) > 1 else 0
        print(f"  {sym:<16} {len(sub):>4} {pnl:>10,.0f} {wr:>5.0%} {pct:>7.1f}%")

    # 8. 按阵营汇总
    print(f"\n{'─'*70}")
    print(f"{'Tier':<30} {'笔数':>4} {'净盈亏':>10} {'胜率':>6}")
    print(f"{'─'*70}")
    for tier in sorted(clearings["open_reason"].unique()):
        sub = clearings[clearings["open_reason"] == tier]
        pnl = sub["net_pnl"].sum()
        wr = (sub["net_pnl"] > 0).mean()
        print(f"  {tier:<28} {len(sub):>4} {pnl:>10,.0f} {wr:>5.0%}")

    return dict(total_ret=total_ret, ann_ret=ann_ret, sharpe=ann_sharpe, max_dd=max_dd,
                win_rate=win_rate, total_net=total_net, nl=nl, n_days=n_days)


def main():
    t0 = time.time()
    backtest_ids = []
    results = {}

    print(f"批量回测 {len(SYMBOLS)} 个品种...")
    for i, sym in enumerate(SYMBOLS):
        print(f"  [{i+1}/{len(SYMBOLS)}] {sym} ...", end=" ", flush=True)
        try:
            bid = run_backtest(sym)
            if bid:
                backtest_ids.append(bid)
                print(f"OK (id={bid})")
            else:
                print("无交易或失败")
        except Exception as e:
            print(f"错误: {e}")

    elapsed = time.time() - t0
    print(f"\n回测完成: {len(backtest_ids)}/{len(SYMBOLS)} 成功, 耗时 {elapsed:.0f}s")

    if backtest_ids:
        get_combined_metrics(backtest_ids)
    else:
        print("无有效回测结果")


if __name__ == "__main__":
    main()
