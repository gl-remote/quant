"""测试用回测记录构造。"""

from common.constants import STATUS_SUCCESS
from common.types import BacktestResult

VNPTY_STATS = {
    "total_trades": 80,
    "win_trades": 45,
    "loss_trades": 35,
    "end_balance": 118000.0,
    "annual_return": 0.18,
    "max_consecutive_win": 6,
    "max_consecutive_loss": 3,
    "average_win": 120.0,
    "average_loss": -55.0,
    "win_loss_ratio": 2.18,
    "sharpe_ratio": 1.35,
    "max_drawdown": 0.12,
    "max_ddpercent_duration": 15,
    "daily_std": 0.018,
    "return_drawdown_ratio": 1.5,
    "max_ddpercent": 12.5,
    "total_net_pnl": 18000.0,
    "daily_net_pnl": 49.32,
    "total_commission": 1200.5,
    "daily_commission": 3.29,
    "total_slippage": 800.0,
    "daily_slippage": 2.19,
    "total_turnover": 4000000.0,
    "daily_turnover": 10958.9,
    "profit_days": 195,
    "loss_days": 170,
    "daily_trade_count": 0.22,
    "daily_return_pct": 0.049,
    "ewm_sharpe": 1.42,
    "rgr_ratio": 1.65,
}


def make_trade(
    dt: str,
    sym: str = "DCE.m2509",
    direction: str = "long",
    offset: str = "open",
    price: float = 3500.0,
    quantity: int = 1,
    pnl: float = 0.0,
    commission: float = 10.5,
) -> dict:
    return {
        "datetime": dt,
        "symbol": sym,
        "direction": direction,
        "offset": offset,
        "open_price": price,
        "close_price": price,
        "quantity": quantity,
        "pnl": pnl,
        "commission": commission,
    }


def make_daily(dt: str, equity: float = 100000.0, daily_return: float = 0.0, drawdown: float = 0.0) -> dict:
    return {
        "datetime": dt,
        "equity": equity,
        "daily_return": daily_return,
        "drawdown": drawdown,
    }


def insert_full_backtest(store, **overrides) -> int:
    s = VNPTY_STATS
    result = BacktestResult(
        symbol=overrides.get("symbol", "DCE.m2509"),
        strategy=overrides.get("strategy", "ma"),
        status=STATUS_SUCCESS,
        start_date="2024-01-01",
        end_date="2024-12-31",
        total_days=365,
        initial_capital=100000.0,
        commission_rate=0.0003,
        slippage=1.0,
        price_tick=1.0,
        contract_size=10,
        kline_interval="1m",
        end_balance=s["end_balance"],
        total_return=s["end_balance"] - 100000.0,
        annual_return=s["annual_return"],
        total_trades=s["total_trades"],
        win_trades=s["win_trades"],
        loss_trades=s["loss_trades"],
        max_consecutive_win=s["max_consecutive_win"],
        max_consecutive_loss=s["max_consecutive_loss"],
        avg_win=s["average_win"],
        avg_loss=s["average_loss"],
        win_loss_ratio=s["win_loss_ratio"],
        sharpe_ratio=s["sharpe_ratio"],
        max_drawdown=s["max_drawdown"],
        max_ddpercent=s["max_ddpercent"],
        max_drawdown_duration=s["max_ddpercent_duration"],
        daily_std=s["daily_std"],
        return_drawdown_ratio=s["return_drawdown_ratio"],
        total_net_pnl=s["total_net_pnl"],
        daily_net_pnl=s["daily_net_pnl"],
        total_commission=s["total_commission"],
        daily_commission=s["daily_commission"],
        total_slippage=s["total_slippage"],
        daily_slippage=s["daily_slippage"],
        total_turnover=s["total_turnover"],
        daily_turnover=s["daily_turnover"],
        profit_days=s["profit_days"],
        loss_days=s["loss_days"],
        daily_trade_count=s["daily_trade_count"],
        daily_return_pct=s["daily_return_pct"],
        ewm_sharpe=s["ewm_sharpe"],
        rgr_ratio=s["rgr_ratio"],
        win_rate=s["win_trades"] / (s["win_trades"] + s["loss_trades"]),
        strategy_params={"sma_short": 5, "sma_long": 20},
        strategy_version="1.0",
        git_hash="abc1234",
    )
    bt_id = store.insert_backtest_detailed(result)
    trades = [
        make_trade("2024-01-15 10:00:00", direction="long", offset="open", pnl=200.0),
        make_trade("2024-01-20 14:30:00", direction="short", offset="close", pnl=-100.0),
        make_trade("2024-02-01 09:15:00", direction="long", offset="open", pnl=350.0),
    ]
    store.insert_backtest_trades(bt_id, trades)
    daily = [
        make_daily("2024-01-15", 100200.0, 200.0, 0.0),
        make_daily("2024-01-20", 100100.0, -100.0, 0.001),
        make_daily("2024-02-01", 100450.0, 350.0, 0.0),
    ]
    store.insert_backtest_daily(bt_id, daily)
    return bt_id
