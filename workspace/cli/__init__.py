"""
CLI 模块包

提供命令行界面功能，包含策略测试、回测、实盘交易等命令。

模块结构:
    - cli/main.py          # 主入口和参数解析
    - cli/commands/        # 命令实现子包
        - export.py        # 数据导出命令
        - test.py          # 策略测试命令
        - backtest.py      # 统一回测命令 (TqSdk / vn.py)
        - live.py          # 实盘交易命令
        - report.py        # 报告生成命令
"""
