import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import MetricCards from '../components/MetricCards';
import type { BacktestRecord, RunInfo } from '../types';

describe('MetricCards', () => {
  const mockRun: RunInfo = {
    id: 1,
    strategy: 'ma',
    engine: 'backtest',
    symbols: 3,
    status: 'success',
    created_at: '2024-01-01',
  };

  const mockBacktests: BacktestRecord[] = [
    {
      id: 1,
      symbol: 'DCE.m2509',
      strategy: 'ma',
      status: 'success',
      total_return: 0.105, // 10.5%
      total_trades: 50,
      win_rate: 60.0,
      max_drawdown: 5.2,
      sharpe_ratio: 1.8,
      end_balance: 110500,
      start_date: '2024-01-01',
      end_date: '2024-01-31',
      initial_capital: 100000,
      data_src: '',
      kline_interval: '',
      strategy_version: '',
      git_hash: '',
      params: [],
      daily: [],
    },
    {
      id: 2,
      symbol: 'DCE.m2509',
      strategy: 'ma',
      status: 'success',
      total_return: 0.083, // 8.3%
      total_trades: 45,
      win_rate: 55.0,
      max_drawdown: 6.1,
      sharpe_ratio: 1.5,
      end_balance: 108300,
      start_date: '2024-01-01',
      end_date: '2024-01-31',
      initial_capital: 100000,
      data_src: '',
      kline_interval: '',
      strategy_version: '',
      git_hash: '',
      params: [],
      daily: [],
    },
    {
      id: 3,
      symbol: 'SHFE.au2506',
      strategy: 'ma',
      status: 'success',
      total_return: 0.152, // 15.2%
      total_trades: 30,
      win_rate: 70.0,
      max_drawdown: 4.0,
      sharpe_ratio: 2.2,
      end_balance: 115200,
      start_date: '2024-01-01',
      end_date: '2024-01-31',
      initial_capital: 100000,
      data_src: '',
      kline_interval: '',
      strategy_version: '',
      git_hash: '',
      params: [],
      daily: [],
    },
  ];

  it('should render without errors', () => {
    render(<MetricCards run={mockRun} backtests={mockBacktests} />);
    expect(screen.getByText('总品种数')).toBeInTheDocument();
  });

  it('should display correct total symbols count (unique)', () => {
    render(<MetricCards run={mockRun} backtests={mockBacktests} />);
    expect(screen.getByText('2')).toBeInTheDocument();
  });

  it('should display total trades', () => {
    render(<MetricCards run={mockRun} backtests={mockBacktests} />);
    expect(screen.getByText('125')).toBeInTheDocument();
  });

  it('should display average return', () => {
    render(<MetricCards run={mockRun} backtests={mockBacktests} />);
    expect(screen.getByText('11.33%')).toBeInTheDocument();
  });

  it('should display average sharpe', () => {
    render(<MetricCards run={mockRun} backtests={mockBacktests} />);
    expect(screen.getByText('1.83')).toBeInTheDocument();
  });

  it('should handle empty backtests array', () => {
    render(<MetricCards run={null} backtests={[]} />);
    // Should render nothing or empty div
    expect(true).toBe(true); // Just verify no error is thrown
  });
});