#!/bin/bash

run_uncovered_notice() {
    uncovered=()
    for f in "$@"; do
        covered=0
        for p in "${COVERED_PREFIXES[@]}"; do
            case "$f" in "$p"*) covered=1; break ;; esac
        done
        [ "$covered" -eq 0 ] && uncovered+=("$f")
    done
    if [ "${#uncovered[@]}" -gt 0 ]; then
        echo -e "${YELLOW}⚠ 以下改动文件不在任何 pre-commit 域 hook 覆盖范围内（未被验证）：${NC}"
        for f in "${uncovered[@]}"; do echo "    $f"; done
        echo -e "${YELLOW}  （AI：请判断是否需要提醒用户为这些文件补充测试覆盖或纳入某业务域。）${NC}"
    fi
}
