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

export type RunLogs = string;
