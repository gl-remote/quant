import sys; sys.path.insert(0,"workspace"); sys.path.insert(0,"scripts/ai_tmp")
import pandas as pd, numpy as np
import va_composite_p1_cap as P1
from strategies.va_asymmetry_composite_strategy import A_TIER_RAW

print("P1.RISK_PER_TRADE =", getattr(P1,"RISK_PER_TRADE", "MISSING"))
print("P1.EQUITY_INIT    =", getattr(P1,"EQUITY_INIT", "MISSING"))
ev=P1.load_events()
print("load_events rows:", len(ev), " contracts:", ev['contract'].nunique())

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

tot=0.0; n=0; nf=0.0
b_daily={}
for c,g in ev.groupby("contract"):
    if c not in csv_map: continue
    P1.bars=csv_map[c]
    rows=P1.simulate_contract(c,g)
    if not rows: continue
    tdf=pd.DataFrame(rows)
    tot+=tdf["pnl_net_ccy"].sum(); n+=len(tdf); nf+=tdf["_notional_frac"].sum()
    s=tdf.groupby("_exit_date")["pnl_net_ccy"].sum(); s.index=pd.to_datetime(s.index).date
    b_daily[c]=s

print(f"B-side total pnl_net_ccy = {tot:,.0f}")
print(f"B-side n trades = {n}, avg pnl/trade = {tot/n:,.0f}")
print(f"B-side avg notional_frac/trade = {nf/n:.4f}")
mat=pd.DataFrame(b_daily).fillna(0.0); port=mat.sum(axis=1).sort_index()
ret=port/1_000_000.0
ann=ret.mean()*252; sd=ret.std()
print(f"B-side REcomputed ann% = {ann*100:.2f}  sharpe = {ann/sd*np.sqrt(252):.2f}  active_days = {(mat!=0).any(axis=1).sum()}")
print(f"B-side span days = {(port.index.max()-port.index.min()).days}")
