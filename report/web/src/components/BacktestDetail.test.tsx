import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import BacktestDetail from '../components/BacktestDetail';
import type { BacktestRecord } from '../types';

describe('BacktestDetail', () => {
  // vnpy 输出格式：total_return 是百分比(如 10.5)，max_drawdown 是金额(元)
  // win_rate 经过 store 层 *100 后是百分比(如 60.0)
  const mockBacktests: BacktestRecord[] = [
    {
      id: 1,
      symbol: 'DCE.m2509',
      strategy: 'ma',
      status: 'success',
      total_return: 10.5,          // vnpy 百分比
      total_trades: 50,
      win_rate: 60.0,              // store 层已 *100
      max_drawdown: 5200,          // vnpy 绝对金额(元)
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
      // 新增字段 (2026-06-06)
      total_net_pnl: 10500,
      total_commission: 350,
      total_slippage: 150,
      profit_days: 180,
      loss_days: 170,
    },
  ];

  it('should render backtest details', () => {
    render(<BacktestDetail backtests={mockBacktests} selectedSymbol="DCE.m2509" />);

    // total_return 是 vnpy 百分比，直接显示
    expect(screen.getByText('10.50%')).toBeInTheDocument();
    expect(screen.getByText('50')).toBeInTheDocument();
    // win_rate 已被 store *100，formatPct 显示百分比
    expect(screen.getByText('60.0%')).toBeInTheDocument();
    // 新增字段展示
    expect(screen.getByText(/10,500/)).toBeInTheDocument();       // 净盈亏
    expect(screen.getByText(/350/)).toBeInTheDocument();           // 手续费
    expect(screen.getByText(/5,200元/)).toBeInTheDocument();      // 最大回撤(金额)
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