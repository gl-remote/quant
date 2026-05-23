#!/bin/bash
# 天勤量化交易系统环境启动脚本
# 使用方法: ./activate_env.sh

CONDA_BASE="${CONDA_PREFIX:-/usr/local/Caskroom/miniconda/base}"
ENV_NAME="quant_trading"

# 检查conda是否存在
if [ ! -f "$CONDA_BASE/bin/activate" ]; then
    echo "错误: 未找到Conda安装"
    echo "请先安装Miniconda或Anaconda，或设置 CONDA_PREFIX 环境变量"
    exit 1
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