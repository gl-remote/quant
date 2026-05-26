#!/usr/bin/env python3
"""
天勤量化交易系统 - 入口转发器

本文件仅作为命令行入口，实际实现已重构到 cli/ 子包中。

命令参考:
    python main.py export     # 数据导出
    python main.py test       # 策略测试
    python main.py backtest   # 统一回测 (TqSdk / vn.py)
    python main.py live       # 实盘交易
    python main.py report     # 生成报告

详细帮助: python main.py --help
"""

from cli.main import main

if __name__ == "__main__":
    main()
