#!/bin/bash
# 策略工具箱环境启动脚本
# 使用方法: source activate_env.sh  (注意：必须用 source，不能用 ./ 执行)

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "错误：请用 source 执行本脚本，而非直接运行"
    echo "  source activate_env.sh"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
ENV_NAME="quant_trading"

# 如果已在目标环境中，跳过激活
if [[ "${CONDA_DEFAULT_ENV:-}" == "$ENV_NAME" ]]; then
    return 0 2>/dev/null || exit 0
fi

CONDA_BASE="${CONDA_PREFIX:-/usr/local/Caskroom/miniconda/base}"
# CONDA_PREFIX 指向 envs/xxx 时回溯到 base
if [[ "$CONDA_BASE" == */envs/* ]]; then
    CONDA_BASE="$(dirname "$(dirname "$CONDA_BASE")")"
fi

# 检查conda是否存在
if [ ! -f "$CONDA_BASE/bin/activate" ]; then
    echo "错误: 未找到Conda安装"
    echo "请先安装Miniconda或Anaconda，或设置 CONDA_PREFIX 环境变量"
    exit 1
fi

# 加载本地密钥（不提交 Git）
if [ -f "$SCRIPT_DIR/.env" ]; then
    source "$SCRIPT_DIR/.env"
fi

# 激活conda环境
source "$CONDA_BASE/bin/activate" "$ENV_NAME"

if [ $? -eq 0 ]; then
    echo "Conda环境 '$ENV_NAME' 已激活"
    echo "  Python路径: $(which python)"
    echo "  Python版本: $(python --version)"
    echo ""
    echo "运行策略测试:"
    echo "  python main.py test"
    echo ""
    echo "导出历史数据:"
    echo "  python main.py export --symbol DCE.m2509 --start 2025-01-01 --end 2026-01-01"
    echo ""
    echo "运行回测:"
    echo "  python main.py backtest --symbol DCE.m2509"
    echo ""
    echo "实盘交易:"
    echo "  python main.py live --symbol DCE.m2509 --gui"
    echo ""
    echo "要退出环境，请输入: conda deactivate"
else
    echo "错误: Conda环境激活失败"
    exit 1
fi