# ============================================================================
# quant 项目命令入口
# ----------------------------------------------------------------------------
# 真正的逻辑都在 scripts/tools/*.sh 里（参数有意写死）。
# 这里只做「好记的入口 + 固定组合 + 顺序保证」。
#
# 用法示例:
#   make                 # 显示帮助
#   make backtest        # 先 clean 再跑 MA 全链路回测
#   make backtest-ma     # 只跑 MA 全链路回测
#   make backtest-ma PATTERN='SHFE\.rb.*'   # 临时换合约筛选正则
#   make backtest-quick  # 轻量回测（trials=3，不 clean），适合快速验证
#   make debug           # 单次 DEBUG 回测
#   make debug ARGS="--profile"          # 透传脚本参数
#   make debug SYMBOL=DCE.c2601 STRATEGY=ma   # 透传环境变量
#   make report          # 重建可视化回测报告（默认 --build）
#   make report ARGS="--id 42"           # 透传 report 子命令参数
#   make clean           # 清理回测/Optuna 数据
#   make fetch           # 拉取多周期 K 线
#   make signal          # 实时信号链路测试
# ============================================================================

# 允许从命令行透传环境变量给底层脚本（如 SYMBOL=xxx make debug）
export SYMBOL STRATEGY PATTERN TRIALS EARLY_STOP_PATIENCE

# 透传给底层脚本的额外参数（如 make debug ARGS="--profile"）
ARGS ?=

# MA 全链路回测的合约筛选正则（平时主要调这个，其余参数钉死在脚本里）
PATTERN ?= DCE\.m.*
# 全链路回测试验数（backtest-quick 覆写为 3）
TRIALS ?= 30

.DEFAULT_GOAL := help
.PHONY: help backtest backtest-ma backtest-quick debug report clean fetch signal

help: ## 显示可用命令
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

clean: ## 清理回测 / Optuna 数据（保留 CSV / metadata）
	bash scripts/tools/clean_data.sh

backtest-ma: ## MA 策略全链路回测（含贝叶斯搜索）
	bash scripts/tools/backtest-ma.sh $(ARGS)

backtest: clean backtest-ma ## 先清理再跑 MA 全链路回测

backtest-quick: ## 轻量回测（trials=3，不清理），适合快速验证参数
	TRIALS=3 bash scripts/tools/backtest-ma.sh $(ARGS)

debug: ## 单次 DEBUG 回测（关搜索 + 落地指标 + 重建报告）
	bash scripts/tools/backtest-debug.sh $(ARGS)

report: ## 重建可视化回测报告（默认 --build，可用 ARGS 覆盖）
	./run.sh report $(or $(ARGS),--build)

fetch: ## 拉取多品种多周期 K 线数据
	bash scripts/tools/fetch_data.sh $(ARGS)

signal: ## 实时信号链路测试（不下单，安全）
	bash scripts/tools/test-signal.sh $(ARGS)
