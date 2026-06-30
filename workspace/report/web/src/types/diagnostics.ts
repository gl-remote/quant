export interface ClearingDiagnostics {
  backtest_id: number;
  symbol?: string;
  trade_count: number;
  total_net_pnl?: number;
  cost_adjusted_win_rate?: number;
  cost_adjusted_payoff_ratio?: number;
  breakeven_win_rate?: number;
  win_rate_margin?: number;
  avg_win?: number;
  avg_loss?: number;
  max_single_loss?: number;
  max_consecutive_losses?: number;
  exit_reason_distribution?: Record<string, number>;
  raw_account_r_multiples?: number[];
  raw_price_r_multiples?: number[];
  mae_values?: number[];
  mfe_values?: number[];
}
