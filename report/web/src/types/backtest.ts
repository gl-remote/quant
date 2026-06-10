export interface SummaryItem {
  symbol: string;
  total_return: number;
  total_trades: number;
  win_rate: number;
  win_loss_ratio: number;
  annual_return: number;
  max_drawdown: number;
  max_ddpercent?: number;
  sharpe: number;
  end_balance: number;
  id: number;
  ret_cls?: string;
  sr_cls?: string;
  total_net_pnl?: number;
  total_commission?: number;
  total_slippage?: number;
  profit_days?: number;
  loss_days?: number;
  ewm_sharpe?: number;
  rgr_ratio?: number;
}

export interface DailyPoint {
  date: string;
  equity: number;
  daily_return: number;
  drawdown: number;
  turnover?: number;
  commission?: number;
  slippage?: number;
  trade_count?: number;
}

export interface BacktestRecord {
  id: number;
  symbol: string;
  strategy: string;
  status: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
  end_balance: number;
  total_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
  max_ddpercent?: number;
  win_rate: number;
  total_trades: number;
  data_src: string;
  kline_interval: string;
  strategy_version: string;
  git_hash: string;
  params: { name: string; value: number }[];
  daily: DailyPoint[];
  total_net_pnl?: number;
  daily_net_pnl?: number;
  total_commission?: number;
  daily_commission?: number;
  total_slippage?: number;
  daily_slippage?: number;
  total_turnover?: number;
  daily_turnover?: number;
  profit_days?: number;
  loss_days?: number;
  daily_trade_count?: number;
  daily_return_pct?: number;
  ewm_sharpe?: number;
  rgr_ratio?: number;
}

export interface TradeRecord {
  datetime: string;
  symbol: string;
  direction: string;
  offset: string;
  open_price: number;
  close_price: number;
  quantity: number;
  pnl: number;
  commission: number;
}

export type TradesData = Record<string, TradeRecord[]>;
