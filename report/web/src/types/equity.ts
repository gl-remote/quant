export interface EquityData {
  symbol: string;
  dates: string[];
  equity: number[];
  drawdown: number[];
  max_ddpercent?: number;
  initial_capital?: number;
}
