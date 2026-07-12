"""验证 poc_va.py 优化后性能"""
import sys, os
_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _root)
import pandas as pd, time

tl = pd.read_parquet(os.path.join(_root, 'project_data/ai_tmp/p0_calib/timeline_calA_min.parquet'))
print(f'{len(tl)} 行, {tl.contract.nunique()} 合约')

from workspace.strategies.classifiers.poc_va import evaluate_dataset
t0 = time.time()
r = evaluate_dataset(tl, atr_col='daily_atr_10_bps', trend_col='trend_ret_10d')
print(f'耗时 {time.time()-t0:.2f}s')
print(r['tier'].value_counts(dropna=False))
print(r['direction'].value_counts(dropna=False))
