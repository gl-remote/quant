#!/bin/bash
# 天勤量化交易系统环境启动脚本
# 使用方法: ./activate_env.sh

# 切换到脚本所在目录
cd "$(dirname "$0")"

# Conda环境路径
CONDA_PATH="/usr/local/Caskroom/miniconda/base/bin"
ENV_NAME="quant_trading"

# 检查conda是否存在
if [ ! -f "$CONDA_PATH/activate" ]; then
    echo "错误: 未找到Conda安装"
    echo "请先安装Miniconda或Anaconda"
    exit 1
fi

# 激活conda环境
source "$CONDA_PATH/activate" "$ENV_NAME"

if [ $? -eq 0 ]; then
    echo "✓ Conda环境 '$ENV_NAME' 已激活"
    echo "  Python路径: $(which python)"
    echo "  Python版本: $(python --version)"
    echo ""
    echo "运行策略测试:"
    echo "  python main.py --mode test"
    echo ""
    echo "运行实盘交易:"
    echo "  python main.py --mode live --symbol DCE.m2109"
    echo ""
    echo "运行回测:"
    echo "  python main.py --mode backtest --symbol DCE.m2109 --start 2024-01-01 --end 2024-12-31"
    echo ""
    echo "要退出环境，请输入: conda deactivate"
else
    echo "错误: Conda环境激活失败"
    exit 1
fi
