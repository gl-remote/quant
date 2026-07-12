import sys; sys.path.insert(0,"workspace"); sys.path.insert(0,"scripts/ai_tmp")
import pandas as pd, numpy as np
import va_composite_p1_cap as P1
from backtest.vnpy_backtest_engine import VnpyBacktestEngine
from config import ConfigManager
from config.app_config import BacktestConfig
from data import DataManager
_cm=ConfigManager(env="backtest"); DataManager(_cm)
from strategies import VAAsymmetryCompositeStrategy
from strategies.va_asymmetry_composite_strategy import A_TIER_RAW

TL="project_data/logs/poc_va_asymmetry_stage4/classifier_v31_timeline.parquet"
tl=pd.read_parquet(TL, columns=["contract","tier"])
contracts=sorted(tl[tl["tier"].isin(A_TIER_RAW)]["contract"].unique())
csv_map={}
for c in contracts:
    try:
        df=pd.read_csv(f"project_data/market_data/csv/{c}.tqsdk.5m.csv")
        df["datetime"]=pd.to_datetime(df["datetime"]); df=df.sort_values("datetime").reset_index(drop=True)
        csv_map[c]=df
    except Exception: pass

cfg=BacktestConfig(initial_capital=1_000_000.0,commission_rate=0.0002,slippage=0.0,price_tick=1.0,contract_size=10,interval="5m")

fw_total={}; b_total={}
events=P1.load_events()
ev_by_c={c: g for c, g in events.groupby("contract")}
for c in csv_map:
    df=csv_map[c]
    eng=VnpyBacktestEngine(cfg)
    res=eng.run([(c,df,"va_asymmetry_composite",{})],batch_mode=True)
    r=res[0]
    if r.success and r.daily_results:
        dr=pd.DataFrame(r.daily_results)
        col=[x for x in dr.columns if x not in ("net_pnl","commission","slippage","turnover","trade_count")][0]
        fw_total[c]=float(dr.set_index(col)["net_pnl"].sum())
    else:
        fw_total[c]=0.0
    if c in ev_by_c:
        P1.bars=df
        rows=P1.simulate_contract(c, ev_by_c[c])
        b_total[c]=float(pd.DataFrame(rows)["pnl_net_ccy"].sum()) if rows else 0.0
    else:
        b_total[c]=0.0

fw=pd.Series(fw_total); b=pd.Series(b_total)
print(f"FRAMEWORK total net pnl = {fw.sum():,.0f}  (over {len(fw)} contracts)")
print(f"RESEARCH  total net pnl = {b.sum():,.0f}")
print(f"RATIO fw/research = {fw.sum()/b.sum():.3f}")
print()
comp=pd.DataFrame({"fw":fw,"b":b}).fillna(0.0)
comp["ratio"]=comp["fw"]/comp["b"].replace(0,np.nan)
comp=comp.sort_values("b",ascending=False)
print("Top 15 contracts by research pnl (ratio=fw/research):")
print(comp.head(15).to_string())
print()
print(f"Median per-contract ratio (where b>0): {comp[comp['b']>0]['ratio'].median():.3f}")
print(f"# contracts fw<0.7*b: {(comp['fw']<0.7*comp['b']).sum()} / {len(comp)}")
