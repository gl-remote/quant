import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import BacktestDetail from '../components/BacktestDetail';
import type { BacktestRecord } from '../types';

describe('BacktestDetail', () => {
  const mockBacktests: BacktestRecord[] = [
    {
      id: 1,
      symbol: 'DCE.m2509',
      strategy: 'ma',
      status: 'success',
      total_return: 0.105,
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
  ];

  it('should render backtest details', () => {
    render(<BacktestDetail backtests={mockBacktests} selectedSymbol="DCE.m2509" />);
    
    expect(screen.getByText('10.50%')).toBeInTheDocument();
    expect(screen.getByText('50')).toBeInTheDocument();
    expect(screen.getByText('60.0%')).toBeInTheDocument();
  });

  it('should handle null data', () => {
    render(<BacktestDetail backtests={null} selectedSymbol="" />);
    
    expect(screen.getByText('暂无回测记录')).toBeInTheDocument();
  });

  it('should handle non-existent symbol', () => {
    render(<BacktestDetail backtests={mockBacktests} selectedSymbol="NOT_EXISTS" />);
    
    expect(screen.getByText('未找到 "NOT_EXISTS" 的回测记录')).toBeInTheDocument();
  });
});