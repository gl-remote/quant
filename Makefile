# ============================================================================
# quant 项目命令入口
# ----------------------------------------------------------------------------
# 真正的逻辑都在 scripts/tools/*.sh 里（参数有意写死）。
# 这里只做「好记的入口 + 固定组合 + 顺序保证」。
#
# 用法示例:
#   make                 # 显示帮助
#   make backtest-ma     # 只跑 MA 全链路回测
#   make backtest-atr    # 只跑 ATR 全链路回测
#   make backtest-ma PATTERN='SHFE\.rb.*'   # 临时换合约筛选正则
#   make debug-parallel  # 并行 DEBUG 回测（trials=3，不 clean）
#   make debug-single    # 单线程 DEBUG 回测
#   make debug-single ARGS="--profile"          # 透传脚本参数
#   make debug-single SYMBOL=DCE.c2601 STRATEGY=ma   # 透传环境变量
#   make report          # 重建可视化回测报告（默认 --build）
#   make report ARGS="--id 42"           # 透传 report 子命令参数
#   make clean           # 清理回测/Optuna 数据
#   make fetch           # 拉取多周期 K 线
#   make signal          # 实时信号链路测试
# ============================================================================

# 允许从命令行透传环境变量给底层脚本（如 SYMBOL=xxx make debug-single）
export SYMBOL STRATEGY PATTERN TRIALS EARLY_STOP_PATIENCE MODE WORKERS CAPITAL

# 透传给底层脚本的额外参数（如 make debug-single ARGS="--profile"）
ARGS ?=

# VA 策略默认的合约筛选：全量 5m CSV（与研究侧基线对齐）
# 可用 make PATTERN='DCE\.m.*' backtest-va 临时覆盖
PATTERN ?= \.tqsdk\.5m\.
# 全链路回测试验数（debug-parallel 覆写为 3）
TRIALS ?= 30

.DEFAULT_GOAL := help
.PHONY: help backtest-ma backtest-atr backtest-va backtest-va-search debug-parallel debug-single report clean clean-backtests clean-reports clean-cache clean-logs clean-research clean-runtime fetch signal

help: ## 显示可用命令
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

clean: ## 清空所有回测衍生物：DB 业务表 + reports/cache/logs/profiles/coverage/research（保留 CSV / metadata）
	bash scripts/tools/clean_data.sh all

clean-backtests: ## 只清 DB 中回测 / Optuna 数据（保留 CSV / metadata）
	bash scripts/tools/clean_data.sh backtests

clean-reports: ## 只清 project_data/reports
	bash scripts/tools/clean_data.sh reports

clean-cache: ## 只清 project_data/cache
	bash scripts/tools/clean_data.sh cache

clean-logs: ## 只清 project_data/logs
	bash scripts/tools/clean_data.sh logs

clean-research: ## 只清 project_data/research（脚本产出的 JSON 摘要）
	bash scripts/tools/clean_data.sh research

clean-runtime: ## 清 reports/cache/profiles/coverage，保留 market_data/database
	bash scripts/tools/clean_data.sh runtime

backtest-ma: ## MA 策略全链路回测（含贝叶斯搜索）
	bash scripts/tools/backtest-ma.sh $(ARGS)

backtest-atr: ## ATR 策略全链路回测（含贝叶斯搜索）
	bash scripts/tools/backtest-atr.sh $(ARGS)

backtest-va: ## VA策略(默认全量5m合约+默认参数并行单次回测,可 MODE=search 切贝叶斯)
	bash scripts/tools/backtest-va.sh $(ARGS)

backtest-va-search: ## VA策略全量贝叶斯参数搜索（等价 make backtest-va MODE=search）
	MODE=search bash scripts/tools/backtest-va.sh $(ARGS)

debug-parallel: ## 并行 DEBUG 回测（trials=3，不清理）
	TRIALS=3 bash scripts/tools/backtest-ma.sh $(ARGS)

debug-single: ## 单线程 DEBUG 回测（关搜索 + 落地指标 + 重建报告）
	bash scripts/tools/backtest-debug.sh $(ARGS)

report: ## 重建可视化回测报告（默认 --build，可用 ARGS 覆盖）
	./run.sh report $(or $(ARGS),--build)

fetch: ## 拉取多品种多周期 K 线数据
	bash scripts/tools/fetch_data.sh $(ARGS)

signal: ## 实时信号链路测试（不下单，安全）
	bash scripts/tools/test-signal.sh $(ARGS)
