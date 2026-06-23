export interface KlinePoint {
  datetime: number;
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
  multi_timeframe?: Record<string, KlinePoint[]>;
}
