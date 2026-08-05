"""
只看成交量 z 和 volume skew 的极端组合，不加 MADEV 条件。
检验：
1. z 极端 + skew 极端的二维分组
2. 全样本（不限制高 s）和高 s 样本分别看
3. skew 极端（正负 1σ 外）本身有没有预测力
4. z×skew 交互
"""
import sys, math
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))

out = Path("/Users/gaolei/Documents/src/quant/project_data/research/volume-spike-regime-shift")
df = pd.read_csv(out/"volume_skew_events.csv", parse_dates=["ts"])
print(f"Total events: {len(df)}")

# Define extreme thresholds
df["z_extreme_high"] = df.z >= 2.5
df["z_extreme_low"] = df.z <= -0.5
df["skew_std"] = (df.vp_skew - df.vp_skew.mean())/df.vp_skew.std()
df["skew_extreme_pos"] = df.skew_std >= 1.0   # >+1σ 正偏（成交集中低位）
df["skew_extreme_neg"] = df.skew_std <= -1.0  # <-1σ 负偏（成交集中高位）
df["balance_std"] = (df.balance - df.balance.mean())/df.balance.std()

def report(sub, name):
    if len(sub)<20:
        print(f"  {name}: n={len(sub)} (too few)")
        return
    m=sub.r100.mean()
    pn=(sub.r100>0).mean()*100
    ic=sp_ic(sub)
    print(f"  {name:<35} n={len(sub):<5} mean={m*100:>+7.3f}%  %pos={pn:>4.0f}%  IC={ic:+.3f}")

def sp_ic(sub):
    if len(sub)<20 or sub.r100.std()==0: return float('nan')
    ic,_=spearmanr(sub.vp_skew, sub.r100)
    return ic

print("\n"+"="*80)
print("全样本（不限制 s_pre）")
print("="*80)

print("\n--- 按 z 分组 ---")
for name,mask in [
    ("z<=-0.5 缩量", df.z<=-0.5),
    ("|z|<0.5 正常", abs(df.z)<0.5),
    ("1.5<=z<2.5 放量", (df.z>=1.5)&(df.z<2.5)),
    ("z>=2.5 极端放量", df.z>=2.5),
]:
    report(df[mask], name)

print("\n--- 按 skew 分组 ---")
for name,mask in [
    ("skew <= -1σ (负偏)", df.skew_extreme_neg),
    ("-1σ < skew < +1σ", (~df.skew_extreme_pos)&(~df.skew_extreme_neg)),
    ("skew >= +1σ (正偏)", df.skew_extreme_pos),
]:
    report(df[mask], name)

print("\n--- z × skew 双排序（mean r100）---")
df["zq"]=pd.cut(df.z,bins=[-99,-0.5,0.5,1.5,2.5,99],
               labels=["缩量","正常","放量","极端放量","z>=2.5"])
df["sq"]=pd.cut(df.skew_std,bins=[-99,-1,-0.5,0.5,1,99],
               labels=["<-1σ","-1~-0.5σ","-0.5~0.5σ","0.5~1σ",">1σ"])
pivot=df.groupby(["zq","sq"],observed=True).r100.agg(["mean","count"])
print((pivot*100).round(3).to_string())

print("\n--- z × skew 双排序（只看极端组合）---")
combos = [
    ("缩量 + 正偏(>+1σ)", (df.z<-0.5)&df.skew_extreme_pos),
    ("缩量 + 负偏(<-1σ)", (df.z<-0.5)&df.skew_extreme_neg),
    ("放量 + 正偏(>+1σ)", (df.z>=1.5)&df.skew_extreme_pos),
    ("放量 + 负偏(<-1σ)", (df.z>=1.5)&df.skew_extreme_neg),
    ("极端放量 + 正偏", (df.z>=2.5)&df.skew_extreme_pos),
    ("极端放量 + 负偏", (df.z>=2.5)&df.skew_extreme_neg),
]
for name,mask in combos:
    report(df[mask], name)

# High s only
print("\n"+"="*80)
print("高 s 样本（s_pre>=0.10）")
print("="*80)
hi=df[df.s_pre>=0.10]
print(f"n={len(hi)}")
print("\n--- z × skew 双排序 ---")
pivot2=hi.groupby(["zq","sq"],observed=True).r100.agg(["mean","count"])
print((pivot2*100).round(3).to_string())

print("\n--- 极端组合 ---")
for name,mask in combos:
    report(hi[mask], name)

# Balance instead of skew
print("\n"+"="*80)
print("用 Balance 代替 Skew（全样本）")
print("="*80)
df["bal_extreme_high"]=df.balance_std>=1
df["bal_extreme_low"]=df.balance_std<=-1
combos2=[
    ("缩量 + Balance高(上方成交多)", (df.z<-0.5)&df.bal_extreme_high),
    ("缩量 + Balance低(下方成交多)", (df.z<-0.5)&df.bal_extreme_low),
    ("放量 + Balance高", (df.z>=1.5)&df.bal_extreme_high),
    ("放量 + Balance低", (df.z>=1.5)&df.bal_extreme_low),
    ("极端放量 + Balance高", (df.z>=2.5)&df.bal_extreme_high),
    ("极端放量 + Balance低", (df.z>=2.5)&df.bal_extreme_low),
]
for name,mask in combos2:
    report(df[mask], name)

print("\n高 s:")
for name,mask in combos2:
    report(hi[mask], name)

# DevClose (close relative to VWAP)
print("\n"+"="*80)
print("用 DevClose（收盘相对 VWAP 偏离）")
print("="*80)
df["dc_std"]=(df.dev_close-df.dev_close.mean())/df.dev_close.std()
for z_name,z_mask in [("缩量",df.z<-0.5),("放量",df.z>=1.5),("极端放量",df.z>=2.5)]:
    for dc_name,dc_mask in [("收在VWAP上方(>+1σ)",df.dc_std>=1),("收在VWAP下方(<-1σ)",df.dc_std<=-1)]:
        report(df[z_mask&dc_mask], f"{z_name} + {dc_name}")

print("\n高 s:")
for z_name,z_mask in [("缩量",hi.z<-0.5),("放量",hi.z>=1.5),("极端放量",hi.z>=2.5)]:
    for dc_name,dc_mask in [("收在VWAP上方",hi.dc_std>=1),("收在VWAP下方",hi.dc_std<=-1)]:
        report(hi[z_mask&dc_mask], f"{z_name} + {dc_name}")
