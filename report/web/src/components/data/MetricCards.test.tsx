import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import MetricCards from './MetricCards';
import type { BacktestRecord, RunInfo } from '../../types';

describe('MetricCards', () => {
  const mockRun: RunInfo = {
    id: 1,
    strategy: 'ma',
    engine: 'backtest',
    symbols: 3,
    status: 'success',
    created_at: '2024-01-01',
  };

  // vnpy 输出格式：total_return 是百分比(如 10.5)，max_drawdown 是金额(元)
  const mockBacktests: BacktestRecord[] = [
    {
      id: 1,
      symbol: 'DCE.m2509',
      strategy: 'ma',
      status: 'success',
      total_return: 10.5,          // vnpy 百分比
      total_trades: 50,
      win_rate: 60.0,
      max_drawdown: 5200,          // vnpy 绝对金额
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
      total_net_pnl: 10500,
      total_commission: 350,
    },
    {
      id: 2,
      symbol: 'DCE.m2509',
      strategy: 'ma',
      status: 'success',
      total_return: 8.3,           // vnpy 百分比
      total_trades: 45,
      win_rate: 55.0,
      max_drawdown: 6100,          // vnpy 绝对金额
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
      total_net_pnl: 8300,
      total_commission: 280,
    },
    {
      id: 3,
      symbol: 'SHFE.au2506',
      strategy: 'ma',
      status: 'success',
      total_return: 15.2,          // vnpy 百分比
      total_trades: 30,
      win_rate: 70.0,
      max_drawdown: 4000,          // vnpy 绝对金额
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
      total_net_pnl: 15200,
      total_commission: 420,
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

  it('should display total trades from best record per symbol', () => {
    render(<MetricCards run={mockRun} backtests={mockBacktests} />);
    expect(screen.getByText('80')).toBeInTheDocument();
  });

  it('should display average return from best record per symbol', () => {
    render(<MetricCards run={mockRun} backtests={mockBacktests} />);
    expect(screen.getByText('12.85%')).toBeInTheDocument();
  });

  it('should display average sharpe from best record per symbol', () => {
    render(<MetricCards run={mockRun} backtests={mockBacktests} />);
    expect(screen.getByText('2.00')).toBeInTheDocument();
  });

  // 新增字段测试 (2026-06-06)
  it('should display total net pnl and commission from best record per symbol', () => {
    render(<MetricCards run={mockRun} backtests={mockBacktests} />);
    expect(screen.getByText(/25,700/)).toBeInTheDocument();
    expect(screen.getByText(/770/)).toBeInTheDocument();
  });
});