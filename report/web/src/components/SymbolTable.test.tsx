import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import SymbolTable from '../components/SymbolTable';
import type { SummaryItem } from '../types';

describe('SymbolTable', () => {
  // vnpy 输出格式：total_return/annual_return 是百分比，max_drawdown 是金额(元)
  const mockSummaryItems: SummaryItem[] = [
    {
      symbol: 'DCE.m2509',
      total_return: 10.5,       // vnpy 百分比
      total_trades: 50,
      win_rate: 60.0,
      win_loss_ratio: 1.5,
      annual_return: 8.0,       // vnpy 百分比
      max_drawdown: 5200,       // vnpy 绝对金额(元)
      sharpe: 1.8,
      end_balance: 110500,
      id: 1,
      // 新增字段 (2026-06-06)
      total_net_pnl: 10500,
      total_commission: 350,
      profit_days: 180,
    },
    {
      symbol: 'SHFE.au2506',
      total_return: 15.2,       // vnpy 百分比
      total_trades: 30,
      win_rate: 70.0,
      win_loss_ratio: 2.1,
      annual_return: 12.0,      // vnpy 百分比
      max_drawdown: 4000,       // vnpy 绝对金额(元)
      sharpe: 2.2,
      end_balance: 115200,
      id: 2,
      // 新增字段 (2026-06-06)
      total_net_pnl: 15200,
      total_commission: 420,
      profit_days: 190,
    },
  ];

  it('should render table with data', () => {
    render(<SymbolTable data={mockSummaryItems} selectedSymbol="" onSelect={() => {}} />);
    
    expect(screen.getByText('DCE.m2509')).toBeInTheDocument();
    expect(screen.getByText('SHFE.au2506')).toBeInTheDocument();
  });

  it('should call onSelect when row is clicked', () => {
    const handleSelect = vi.fn();
    render(<SymbolTable data={mockSummaryItems} selectedSymbol="" onSelect={handleSelect} />);
    
    const row = screen.getByText('DCE.m2509').closest('tr');
    fireEvent.click(row!);
    
    expect(handleSelect).toHaveBeenCalledWith('DCE.m2509');
  });

  it('should highlight selected row', () => {
    render(<SymbolTable data={mockSummaryItems} selectedSymbol="DCE.m2509" onSelect={() => {}} />);
    
    const row = screen.getByText('DCE.m2509').closest('tr');
    expect(row).toHaveStyle({ background: '#eff6ff' });
  });

  it('should display correct metrics', () => {
    render(<SymbolTable data={mockSummaryItems} selectedSymbol="" onSelect={() => {}} />);
    
    expect(screen.getByText('10.50%')).toBeInTheDocument();
    expect(screen.getByText('15.20%')).toBeInTheDocument();
    expect(screen.getByText('60.0%')).toBeInTheDocument();
    expect(screen.getByText('70.0%')).toBeInTheDocument();
  });

  it('should handle empty data', () => {
    render(<SymbolTable data={[]} selectedSymbol="" onSelect={() => {}} />);
    
    expect(screen.getByText('暂无回测记录')).toBeInTheDocument();
  });
});