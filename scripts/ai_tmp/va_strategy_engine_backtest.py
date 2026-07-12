"""VA 非对称复合策略 · 用真实 vnpy 回测引擎跑 B 层策略，并与研究引擎(event_time 进场)对照。

目的: 验证 va_asymmetry_composite_strategy.py（每日首根 entry_tf 进场）相对
研究引擎（盘中 event_time 进场）的差距是否显著。

做法:
  (A) 我的 Strategy 子类 → VnpyBacktestEngine.run（逐合约，batch_mode 不落库）
      → 逐日 net_pnl 序列 → 等权汇总成组合日收益 → 年化/夏普/MaxDD
  (B) 研究引擎 P1.simulate_contract（event_time 进场，复刻冻结管线）对同样合约
      → 同样汇总口径 → 组合日收益 → 年化/夏普/MaxDD

两者共享同一 A 层(白名单 144tier→v40)、同一 sizing、同一 SL/时间退出规则，
唯一系统差异 = 进场时点(首根 bar vs event_time) + vnpy 撮合(次根开盘成交)。

用法: 仓库根目录执行  uv run python scripts/ai_tmp/va_strategy_engine_backtest.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

import loguru

loguru.logger.remove()
loguru.logger.add(sys.stderr, level="WARNING")

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "workspace"))
sys.path.insert(0, str(REPO / "scripts/ai_tmp"))  # 引入冻结研究引擎 P1

import va_composite_p1_cap as P1  # noqa: E402  va_composite_p1_cap
from backtest.vnpy_backtest_engine import VnpyBacktestEngine  # noqa: E402
from config import ConfigManager  # noqa: E402
from config.app_config import BacktestConfig  # noqa: E402
from data import DataManager  # noqa: E402

# 初始化数据环境（桥的 DataFeed.create 需要）
_cm = ConfigManager(env="backtest")
DataManager(_cm)
from strategies import (  # noqa: E402
    VAAsymmetryCompositeParams,
    VAAsymmetryCompositeStrategy,
)
from strategies.va_asymmetry_composite_strategy import A_TIER_RAW  # noqa: E402

TL_PATH = "project_data/logs/poc_va_asymmetry_stage4/classifier_v31_timeline.parquet"
CSV_DIR = Path("project_data/market_data/csv")
EQUITY = 1_000_000.0


def _portfolio_metrics(daily_pnl_by_contract: dict, label: str) -> dict:
    """等权汇总各合约逐日 net_pnl → 组合日收益 → 指标。"""
    if not daily_pnl_by_contract:
        print(f"[{label}] 无数据")
        return {}
    mat = pd.DataFrame(daily_pnl_by_contract).fillna(0.0)
    port_daily = mat.sum(axis=1).sort_index()
    ret = port_daily / EQUITY
    ann = float(ret.mean() * 252)
    sd = float(ret.std())
    sharpe = float(ret.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0
    equity = EQUITY + port_daily.cumsum()
    dd = (equity - equity.cummax()) / equity.cummax()
    maxdd = float(dd.min())
    n_trades = int((mat != 0).any(axis=1).sum())
    print(f"[{label}] 年化={ann*100:6.2f}%  夏普={sharpe:5.2f}  MaxDD={maxdd*100:6.2f}%  "
          f"活跃日={len(port_daily)}  合约数={mat.shape[1]}")
    return {"ann": ann, "sharpe": sharpe, "maxdd": maxdd, "n_days": len(port_daily)}


def main() -> None:
    # ── 0. 白名单合约（与研究引擎同一 A 层）──
    tl = pd.read_parquet(TL_PATH, columns=["contract", "tier"])
    wl = tl[tl["tier"].isin(A_TIER_RAW)]
    contracts = sorted(wl["contract"].unique())
    print(f"白名单合约(timeline 内): {len(contracts)}")

    # ── 1. 装载 5m bar（与研究引擎同源）──
    pairs = []
    csv_map: dict[str, pd.DataFrame] = {}
    for c in contracts:
        fp = CSV_DIR / f"{c}.tqsdk.5m.csv"
        if not fp.exists():
            continue
        df = pd.read_csv(fp)
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.sort_values("datetime").reset_index(drop=True)
        pairs.append((c, df, "va_asymmetry_composite", {}))
        csv_map[c] = df
    print(f"有 5m 数据可回测的合约: {len(pairs)}")

    # ── 2. (A) 我的 Strategy 经真实 vnpy 引擎 ──
    cfg = BacktestConfig(
        initial_capital=EQUITY,
        commission_rate=0.0002,  # 注: vnpy 引擎内部 rate 硬编码 0.0，仅 tick 滑点生效
        slippage=0.0,
        price_tick=1.0,
        contract_size=10,
        interval="5m",
    )
    A_daily: dict[str, pd.Series] = {}
    ok = fail = 0
    for c, df, name, params in pairs[:3]:
        try:
            eng = VnpyBacktestEngine(cfg)
            res = eng.run([(c, df, name, params)], batch_mode=True)
            r = res[0]
            if not r.success:
                print(f"  [A] FAIL {c}: {r.error_message}")
                fail += 1
                continue
            dr = pd.DataFrame(r.daily_results)
            if dr.empty or "net_pnl" not in dr.columns:
                A_daily[c] = pd.Series(dtype=float)
                ok += 1
                continue
            datecol = [col for col in dr.columns if col not in (
                "net_pnl", "commission", "slippage", "turnover", "trade_count")][0]
            s = dr.set_index(datecol)["net_pnl"]
            s.index = pd.to_datetime(s.index).date
            A_daily[c] = s
            ok += 1
        except Exception as e:  # noqa: BLE001
            print(f"  [A] ERR {c}: {repr(e)}")
            fail += 1
    print(f"[A] 成功 {ok} / 失败 {fail}")
    mA = _portfolio_metrics(A_daily, "A: 我的策略(首根bar进场, vnpy撮合)")

    # ── 3. (B) 研究引擎 P1.simulate_contract（event_time 进场）──
    events = P1.load_events()  # contract,event_time,direction,tier_v40,entry_atr_bps,close_t
    B_daily: dict[str, pd.Series] = {}
    for c, g in events.groupby("contract"):
        if c not in csv_map:
            continue
        P1.bars = csv_map[c]
        try:
            rows = P1.simulate_contract(c, g)
        except Exception as e:  # noqa: BLE001
            print(f"  [B] ERR {c}: {repr(e)}")
            continue
        if not rows:
            continue
        tdf = pd.DataFrame(rows)
        if "_exit_date" not in tdf.columns or tdf.empty:
            continue
        s = tdf.groupby("_exit_date")["pnl_net_ccy"].sum()
        s.index = pd.to_datetime(s.index).date
        B_daily[c] = s
    mB = _portfolio_metrics(B_daily, "B: 研究引擎(event_time进场, close_t撮合)")

    # ── 4. 对照差距 ──
    if mA and mB:
        print("\n" + "=" * 60)
        print("对照（同 A 层 / 同 sizing / 同 SL+时间退出，仅进场时点不同）")
        print("=" * 60)
        print(f"  年化:   A={mA['ann']*100:6.2f}%   B={mB['ann']*100:6.2f}%   "
              f"Δ={ (mA['ann']-mB['ann'])*100:+.2f}pp")
        print(f"  夏普:   A={mA['sharpe']:5.2f}        B={mB['sharpe']:5.2f}        "
              f"Δ={mA['sharpe']-mB['sharpe']:+.2f}")
        print(f"  MaxDD:  A={mA['maxdd']*100:6.2f}%   B={mB['maxdd']*100:6.2f}%   "
              f"Δ={ (mA['maxdd']-mB['maxdd'])*100:+.2f}pp")
        print("\n说明: A 的 vnpy 成本仅含 tick 滑点(佣金硬编码0)，B 含 realistic bps 成本，")


if __name__ == "__main__":
    main()
