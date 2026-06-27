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
  use_fixed_seed?: boolean;
  random_seed?: number | null;
}

export type RunLogs = string;
