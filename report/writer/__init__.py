"""报告数据写入模块

负责将各类数据导出为 JSON 文件，包括：
- 运行信息
- 品种汇总
- 回测记录
- 资金曲线
- K线数据
- 交易记录
- Optuna 优化数据
- 导航数据
"""

from .json_writer import (
    export_run_json,
    export_summary_json,
    export_backtests_json,
    export_equity_json,
    export_kline_json,
    export_trades_json,
    export_optuna_json,
    write_nav_json,
)

__all__ = [
    "export_run_json",
    "export_summary_json",
    "export_backtests_json",
    "export_equity_json",
    "export_kline_json",
    "export_trades_json",
    "export_optuna_json",
    "write_nav_json",
]