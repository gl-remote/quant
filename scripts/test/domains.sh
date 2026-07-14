#!/bin/bash

# 全量 mypy 范围（不传 domain 时使用，与历史 pre-commit 保持一致）
MYPY_TARGETS=(workspace/common/ workspace/data/ workspace/backtest/ workspace/clearing/ workspace/strategies/)

# 业务域 coverage 阈值。按域设置，不使用全仓库总阈值。
# 阈值先按当前基线下沿设置，确保今天不会因既有覆盖率阻塞；后续再逐步提高。
resolve_coverage_min() {
    case "$1" in
        common) echo "60" ;;
        config) echo "90" ;;
        data) echo "50" ;;
        backtest) echo "50" ;;
        clearing) echo "85" ;;
        strategies) echo "74" ;;
        report) echo "25" ;;
        cli) echo "30" ;;
        contracts) echo "60" ;;
        *) echo "" ;;
    esac
}

# 业务域 → 源码路径（lint/format/type 的目标）
resolve_src() {
    case "$1" in
        common|config|data|backtest|clearing|strategies|cli) echo "workspace/$1/" ;;
        report) echo "workspace/report/" ;;
        contracts) echo "workspace/packages/python-contracts/src/" ;;
        *) echo "" ;;
    esac
}

# 业务域 → 测试路径（unit 的目标）
resolve_test() {
    case "$1" in
        common|config|data|backtest|clearing|strategies|report|cli) echo "workspace/tests/$1/" ;;
        contracts) echo "workspace/packages/python-contracts/tests/" ;;
        *) echo "" ;;
    esac
}

# 已被某个 pre-commit 测试 hook 覆盖的路径前缀（与 .pre-commit-config.yaml 的 files 对应）。
# 落在这些前缀外的改动 = 不会触发任何测试 hook 的盲区。
# 维护规则：在 .pre-commit-config.yaml 新增/调整测试 hook 时，同步更新此清单。
COVERED_PREFIXES=(
    "workspace/common/" "workspace/config/" "workspace/data/" "workspace/backtest/"
    "workspace/clearing/" "workspace/strategies/" "workspace/cli/" "workspace/report/"
    "workspace/tests/"                                # 测试自身改动由对应域 hook（含 tests/<domain>/）覆盖
    "workspace/packages/python-contracts/"    # contracts 域
)
