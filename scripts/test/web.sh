#!/bin/bash

# ── 前端（report-web）工具链：stage 语义对齐 Python 侧 ──
web_lint()   { echo "── [lint] eslint ──";  (cd "$WEB_DIR" && npm run --silent lint); }
web_type()   { echo "── [type] tsc --noEmit ──"; (cd "$WEB_DIR" && npx --no-install tsc --noEmit); }
web_unit()   { echo "── [unit] vitest run ──"; (cd "$WEB_DIR" && npx --no-install vitest run); }
web_format() { echo -e "${YELLOW}── [format] 前端无独立 prettier 脚本，eslint 已含风格，跳过 ──${NC}"; }

run_web_stage() {
    case "$1" in
        lint)   web_lint ;;
        format) web_format ;;
        type)   web_type ;;
        unit)   web_unit ;;
        all)    web_lint; web_type; web_unit ;;
        *) echo -e "${RED}未知 stage: $1${NC}"; exit 1 ;;
    esac
}
