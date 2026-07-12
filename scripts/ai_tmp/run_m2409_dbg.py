"""单合约 m2409 调试回测：直接调用 BacktestRunWorkflow，绕开 CLI 拦截。
需配合环境变量 VA_DEBUG 指向日志文件（在策略内已读取）。
"""
import os
import sys

sys.path.insert(0, os.getcwd())

from config import ConfigManager
from data import DataManager
from cli.workflows.backtests_run import BacktestRunWorkflow, VnpySearchRequest

os.environ.setdefault("VA_DEBUG", "/tmp/va_dbg_m2409.log")

cm = ConfigManager(env="backtest")
dm = DataManager(cm)
wf = BacktestRunWorkflow(cm=cm, dm=dm)

req = VnpySearchRequest(
    strategy="va_asymmetry_composite",
    capital=None,
    contract_size=None,
    symbol="DCE.m2409",
    pattern=None,
    start="2024-06-04",
    end="2024-06-07",
    optimizer=None,
    trials=None,
    parallel=False,
    workers=None,
    no_search=True,
    no_report=True,
)
wf.run_vnpy_search(req)
print("DONE")
