#!/bin/bash

run_lint() {
    echo "── [lint] ruff check $* ──"
    ruff check "$@"
}

run_format() {
    echo "── [format] ruff format --check $* ──"
    ruff format --check "$@"
}

run_type() {
    echo "── [type] mypy $* ──"
    uv run python -m mypy --config-file pyproject.toml "$@"
}

run_unit() {
    if [ "$#" -eq 0 ]; then
        echo -e "${YELLOW}── [unit] 该域无测试目录，跳过 ──${NC}"
        return 0
    fi
    echo "── [unit] pytest $* ──"
    # 覆盖 pyproject 的 addopts（含 --cov=. 全量覆盖率），按域验证时不需要全量 coverage
    #
    # contracts 域的测试（workspace/packages/python-contracts/tests/）有独立的
    # conftest.py，与主项目 workspace/tests/conftest.py 冲突（都解析为 tests.conftest），
    # 需要从项目根之外分开跑。主项目全量时分别调两次 run_unit 来处理。
    if [ "$*" = "workspace/packages/python-contracts/tests/" ]; then
        (cd workspace/packages/python-contracts && uv run python -m pytest tests/ -m "not slow and not local_data" -q --tb=short -o "addopts=" -p no:cacheprovider)
        return $?
    fi
    uv run python -m pytest "$@" -m "not slow and not local_data" -o addopts="" -p no:cacheprovider -q --tb=short
}

run_marked_tests() {
    local marker="$1"
    shift
    if [ "$#" -eq 0 ]; then
        echo -e "${YELLOW}── [$marker] 该域无测试目录，跳过 ──${NC}"
        return 0
    fi
    echo "── [$marker] pytest $* ──"
    local status
    set +e
    if [ "$*" = "workspace/packages/python-contracts/tests/" ]; then
        (cd workspace/packages/python-contracts && uv run python -m pytest tests/ -m "$marker" -q --tb=short -o "addopts=" -p no:cacheprovider)
        status=$?
    else
        uv run python -m pytest "$@" -m "$marker" -o addopts="" -p no:cacheprovider -q --tb=short
        status=$?
    fi
    set -e
    if [ "$status" -eq 5 ]; then
        echo -e "${YELLOW}── [$marker] 未匹配到测试，跳过 ──${NC}"
        return 0
    fi
    return "$status"
}

run_integration() {
    run_marked_tests "integration and not slow and not local_data" "$@"
}

run_slow() {
    run_marked_tests "slow" "$@"
}

run_local_data() {
    run_marked_tests "local_data" "$@"
}

run_coverage() {
    local src="$1"
    shift
    if [ "$#" -eq 0 ]; then
        echo -e "${YELLOW}── [coverage] 该域无测试目录，跳过 ──${NC}"
        return 0
    fi
    echo "── [coverage] pytest $* --cov=$src ──"
    if [ "$*" = "workspace/packages/python-contracts/tests/" ]; then
        (
            cd workspace/packages/python-contracts
            uv run python -m pytest tests/ \
                -m "not slow and not local_data" \
                --cov=src \
                --cov-report=term-missing:skip-covered \
                -q --tb=short -o "addopts=" -p no:cacheprovider
        )
        return $?
    fi
    uv run python -m pytest "$@" \
        -m "not slow and not local_data" \
        --cov="$src" \
        --cov-report=term-missing:skip-covered \
        -q --tb=short -o addopts="" -p no:cacheprovider
}
