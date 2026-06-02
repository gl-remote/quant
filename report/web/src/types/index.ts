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
 */
export interface SummaryItem {
  symbol: string;              // 品种代码
  total_return: number;        // 总收益率
  total_trades: number;       // 总交易次数
  win_rate: number;          // 胜率
  max_drawdown: number;      // 最大回撤
  sharpe: number;             // 夏普比率
  end_balance: number;        // 最终资金
  ret_cls?: string;         // 收益率样式类（可选）
  sr_cls?: string;          // 夏普比率样式类（可选）
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
 * 日线数据点（用于资金曲线
 */
export interface DailyPoint {
  date: string;            // 日期
  equity: number;            // 资金
  daily_return: number;      // 日收益率
  drawdown: number;      // 回撤
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
  total_return: number;      // 总收益率
  sharpe_ratio: number;       // 夏普比率
  max_drawdown: number;      // 最大回撤
  win_rate: number;         // 胜率
  total_trades: number;       // 总交易次数
  data_src: string;         // K线数据源
  kline_interval: string;      // K线周期
  strategy_version: string;   // 策略版本
  git_hash: string;        // Git提交哈希
  params: { name: string; value: number }[]; // 策略参数
  daily: DailyPoint[];       // 日线数据
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
  contour: EChartsOption | null;       // 等高线图配置
}

export type { EChartsOption };

/**
 * 运行日志 — 单字符串（整个 run.log 内容）
 */
export type RunLogs = string;