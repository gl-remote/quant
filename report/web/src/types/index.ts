/**
 * TypeScript 类型定义
 * 
 * 【说明】
 * - 定义了所有前端使用的数据类型
 * - 与 Python 后端生成的数据结构保持一致
 * - 包含回测、K线、资金曲线、Optuna等数据类型
 * 
 * 【数据流】
 * Python 后端生成 JSON → TypeScript 类型 → React 组件使用
 */

import type { EChartsOption } from "echarts";

/**
 * ContourTrial — 一次 Optuna 试验的参数和值
 */
export interface ContourTrial {
  params: Record<string, number>;
  value: number | null;
}

/**
 * ContourMeta — 等高线图的原始数据，参数名 + 试验列表
 */
export interface ContourMeta {
  param_names: string[];
  trials: ContourTrial[];
}

/**
 * 回测运行信息
 * 
 * 对应 Python 后端 runs 表结构
 */
export interface RunInfo {
  id: number;                  // 运行 ID
  strategy: string;                // 策略名称
  engine: string;              // 回测引擎
  symbols: number;             // 品种数量
  status: string;              // 状态（如 success/fail）
  created_at: string;         // 创建时间
}

/**
 * 导航项（用于首页导航页面）
 */
export interface NavItem {
  id: number;                  // 运行 ID
  strategy: string;                // 策略名称
  engine: string;              // 回测引擎
  symbols: number;             // 品种数量
  status: string;              // 状态
  created: string;         // 创建时间（显示用）
}

/**
 * 品种汇总项
 *
 * 包含每个品种的最优回测指标
 * 2026-06-06 新增 vnpy 统计字段（盈亏汇总 / 交易日统计 / 进阶指标）
 */
export interface SummaryItem {
  symbol: string;              // 品种代码
  total_return: number;        // 总收益率
  total_trades: number;       // 总交易次数
  win_rate: number;          // 胜率
  win_loss_ratio: number;    // 盈亏比
  annual_return: number;     // 年化收益率
  max_drawdown: number;      // 最大回撤
  max_ddpercent?: number;    // 最大回撤百分比 [vnpy] (2026-06-06新增)
  sharpe: number;             // 夏普比率
  end_balance: number;        // 最终资金
  id: number;                 // 回测ID
  ret_cls?: string;         // 收益率样式类（可选）
  sr_cls?: string;          // 夏普比率样式类（可选）
  // 盈亏汇总 [vnpy] (2026-06-06新增)
  total_net_pnl?: number;     // 总净盈亏金额
  total_commission?: number;  // 总手续费
  total_slippage?: number;    // 总滑点成本
  // 交易日统计 [vnpy]
  profit_days?: number;       // 盈利交易日数
  loss_days?: number;         // 亏损交易日数
  // 进阶指标 [vnpy]
  ewm_sharpe?: number;        // EWM夏普比率
  rgr_ratio?: number;         // RGR比率
}

/**
 * K线数据点
 * 
 * OHLCV 格式：开盘价、最高价、最低价、收盘价、成交量
 */
export interface KlinePoint {
  datetime: number;    // Unix 时间戳（秒）
  open: number;       // 开盘价
  high: number;        // 最高价
  low: number;         // 最低价
  close: number;       // 收盘价
  volume: number;      // 成交量
}

/**
 * K线完整数据
 * 
 * 包含日线和原始数据（可能降采样）
 */
export interface KlineData {
  symbol: string;              // 品种代码
  interval: string;            // K线周期
  csv_source: string;          // CSV文件源路径
  daily: KlinePoint[];         // 日线数据
  raw: KlinePoint[];         // 原始数据（分钟线等）
  raw_count: number;          // 原始数据点数
  raw_downsampled: boolean;   // 是否已降采样
  raw_sample_max: number;     // 降采样阈值
}

/**
 * 日线数据点（用于资金曲线）
 * 2026-06-06 新增 vnpy 日度字段
 */
export interface DailyPoint {
  date: string;            // 日期
  equity: number;            // 资金
  daily_return: number;      // 日收益(金额)
  drawdown: number;      // 回撤
  // 2026-06-06 新增 vnpy 日度字段
  turnover?: number;       // 当日成交金额 [vnpy]
  commission?: number;     // 当日手续费 [vnpy]
  slippage?: number;       // 当日滑点成本 [vnpy]
  trade_count?: number;    // 当日成交笔数 [vnpy]
}

/**
 * 资金曲线数据
 */
export interface EquityData {
  symbol: string;              // 品种代码
  dates: string[];           // 日期数组
  equity: number[];           // 资金数组
  drawdown: number[];       // 回撤数组
}

/**
 * 回测记录
 * 2026-06-06 新增 vnpy 统计字段（盈亏汇总 / 交易日统计 / 进阶指标）
 */
export interface BacktestRecord {
  id: number;                  // 回测 ID
  symbol: string;              // 品种代码
  strategy: string;            // 策略名称
  status: string;             // 状态
  start_date: string;         // 开始日期
  end_date: string;          // 结束日期
  initial_capital: number;     // 初始资金
  end_balance: number;       // 最终资金
  total_return: number;      // 总收益率 [vnpy]
  sharpe_ratio: number;       // 夏普比率 [vnpy]
  max_drawdown: number;      // 最大回撤(金额) [vnpy]
  max_ddpercent?: number;     // 最大回撤百分比 [vnpy] (2026-06-06新增)
  win_rate: number;         // 胜率 (基于逐笔 net_pnl 计算)
  total_trades: number;       // 总交易次数
  data_src: string;         // K线数据源
  kline_interval: string;      // K线周期
  strategy_version: string;   // 策略版本
  git_hash: string;        // Git提交哈希
  params: { name: string; value: number }[]; // 策略参数
  daily: DailyPoint[];       // 日线数据
  // 盈亏汇总 [vnpy] (2026-06-06新增)
  total_net_pnl?: number;         // 总净盈亏金额
  daily_net_pnl?: number;         // 日均净盈亏
  total_commission?: number;      // 总手续费
  daily_commission?: number;      // 日均手续费
  total_slippage?: number;        // 总滑点成本
  daily_slippage?: number;        // 日均滑点
  total_turnover?: number;        // 总成交金额
  daily_turnover?: number;        // 日均成交额
  // 交易日统计 [vnpy] (2026-06-06新增)
  profit_days?: number;            // 盈利交易日数
  loss_days?: number;              // 亏损交易日数
  daily_trade_count?: number;      // 日均成交笔数
  daily_return_pct?: number;       // 日均收益率%
  // 进阶指标 [vnpy] (2026-06-06新增)
  ewm_sharpe?: number;             // EWM夏普比率
  rgr_ratio?: number;              // RGR比率
}

/**
 * Optuna 最优参数
 */
export interface BestParam {
  name: string;           // 参数名
  value: number;           // 参数值
}

/**
 * 参数散点图数据
 */
export interface DenormalizedScatter {
  x_label: string;       // X轴标签
  y_label: string;       // Y轴标签
  x_vals: number[];     // X轴值数组
  y_vals: number[];     // Y轴值数组
  scores: number[];      // 评分数组
}

/**
 * Optuna 完整数据
 * 
 * 包含优化历史、参数重要性、平行坐标图等
 */
export interface OptunaData {
  study_name: string;              // 优化研究名称
  best_params: BestParam[];      // 最优参数
  best_value: number | null;     // 最优值
  optimization_history: EChartsOption | null; // 优化历史图表配置
  param_importances: EChartsOption | null; // 参数重要性图表配置
  parallel_coordinate: EChartsOption | null; // 平行坐标图配置
  contours: ContourMeta | null; // 等高线原始数据
}

export type { EChartsOption };

/**
 * 运行日志 — 单字符串（整个 run.log 内容）
 */
export type RunLogs = string;

/**
 * 单笔交易记录
 */
export interface TradeRecord {
  datetime: string;  // 交易时间
  symbol: string;    // 品种代码
  direction: string; // 方向: long/short
  offset: string;    // 开平: open/close
  open_price: number; // 开仓价
  close_price: number; // 平仓价
  quantity: number; // 数量
  pnl: number;      // 盈亏
  commission: number; // 手续费
}

/**
 * 所有交易数据（按品种分组）
 */
export type TradesData = Record<string, TradeRecord[]>;