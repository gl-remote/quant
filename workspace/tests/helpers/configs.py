"""测试用配置字典构造。"""


def make_trading_config_dict() -> dict:
    return {
        "stop_loss_ratio": 0.03,
        "take_profit_ratio": 0.05,
        "position_ratio": 0.3,
        "sma_short": 10,
        "sma_long": 40,
        "kline_period": 5,
        "atr_period": 14,
        "atr_stop_loss_multiplier": 2.0,
        "atr_take_profit_multiplier": 3.0,
    }


def make_base_config_dict() -> dict:
    return {
        "strategies": [
            {
                "name": "ma",
                "sma_short": 10,
                "sma_long": 40,
                "stop_loss_ratio": 0.03,
                "take_profit_ratio": 0.05,
                "position_ratio": 0.3,
                "kline_period": 5,
                "atr_period": 14,
                "atr_stop_loss_multiplier": 2.0,
                "atr_take_profit_multiplier": 3.0,
            },
        ],
        "data": {
            "environment": "unit_test",
            "base_dir": "project_data",
            "database_path": "project_data/database/unit_test/quant.db",
            "export_dir": "project_data/market_data/csv",
            "filename_template": "{symbol}.{provider}.{interval}.csv",
            "allow_aggressive_schema_migration": True,
        },
        "backtest": {
            "initial_capital": 100000.0,
            "commission_rate": 0.0003,
            "slippage": 1.0,
            "price_tick": 1.0,
            "contract_size": 10,
            "interval": "1m",
        },
        "system": {
            "logging": {
                "level": "INFO",
            },
        },
    }
