export interface RunInfo {
  id: number;
  strategy: string;
  engine: string;
  symbols: number;
  status: string;
  created_at: string;
}

export interface NavItem {
  id: number;
  strategy: string;
  engine: string;
  symbols: number;
  status: string;
  created: string;
}

export interface SummaryItem {
  symbol: string;
  total_return: number;
  total_trades: number;
  win_rate: number;
  max_drawdown: number;
  sharpe: number;
  end_balance: number;
  ret_cls?: string;
  sr_cls?: string;
}

export interface KlinePoint {
  datetime: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface KlineData {
  symbol: string;
  interval: string;
  csv_source: string;
  daily: KlinePoint[];
  raw: KlinePoint[];
  raw_count: number;
  raw_downsampled: boolean;
  raw_sample_max: number;
}

export interface DailyPoint {
  date: string;
  equity: number;
  daily_return: number;
  drawdown: number;
}

export interface EquityData {
  symbol: string;
  dates: string[];
  equity: number[];
  drawdown: number[];
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
  win_rate: number;
  total_trades: number;
  data_src: string;
  kline_interval: string;
  strategy_version: string;
  git_hash: string;
  params: { name: string; value: number }[];
  daily: DailyPoint[];
}

export interface BestParam {
  name: string;
  value: number;
}

export interface ParamScatter {
  x_label: string;
  y_label: string;
  x_vals: number[];
  y_vals: number[];
  scores: number[];
}

export interface PlotlySpec {
  data: object[];
  layout: object;
}

export interface OptunaData {
  study_name: string;
  trial_count: number;
  trial_nums: number[];
  trial_values: number[];
  best_params: BestParam[];
  param_scatter: ParamScatter | null;
  charts: {
    optimization_history: PlotlySpec | null;
    param_importances: PlotlySpec | null;
    parallel_coordinate: PlotlySpec | null;
    contour: PlotlySpec | null;
  };
}