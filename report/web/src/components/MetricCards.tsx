/**
 * @file MetricCards.tsx
 * @description 回测指标卡片组件
 * 展示回测的关键指标，包括策略名称、引擎、品种数量、平均收益率、总交易次数、平均夏普比率等
 * 收益率和夏普比率会根据正负值显示不同的颜色
 */

import type { BacktestRecord, RunInfo } from "@/types";

/**
 * MetricCards组件属性接口
 * @interface Props
 * @property {RunInfo | null} run - 回测基本信息
 * @property {BacktestRecord[] | null} backtests - 回测记录数据
 */
interface Props {
  run: RunInfo | null;
  backtests: BacktestRecord[] | null;
}

/**
 * MetricCards组件
 * 回测指标卡片展示组件
 * 
 * @component
 * @param {Props} props - 组件属性
 * @returns {JSX.Element | null} 渲染后的指标卡片组件，无数据时返回null
 */
export default function MetricCards({ run, backtests }: Props) {
  // 如果没有回测数据，返回null
  if (!backtests || backtests.length === 0) {
    return null;
  }

  // 计算各项指标
  const totalReturn = backtests.reduce(
    (sum, b) => sum + (b.total_return || 0),
    0
  );
  const avgReturn = totalReturn / backtests.length;
  const totalTrades = backtests.reduce(
    (sum, b) => sum + (b.total_trades || 0),
    0
  );
  const avgSharpe =
    backtests.reduce((sum, b) => sum + (b.sharpe_ratio || 0), 0) /
    backtests.length;

  // 构建指标卡片数组
  const cards = [
    { label: "总品种数", value: String(backtests.length) },
    {
      label: "平均收益率",
      value: `${(avgReturn * 100).toFixed(2)}%`,
      color: avgReturn >= 0 ? "#059669" : "#dc2626",
    },
    { label: "总交易次数", value: String(totalTrades) },
    {
      label: "平均夏普",
      value: avgSharpe.toFixed(2),
      color: avgSharpe >= 0 ? "#059669" : "#dc2626",
    },
  ];

  // 如果有run信息，添加策略和引擎信息
  if (run) {
    cards.unshift({ label: "策略", value: run.strategy });
    cards.unshift({ label: "引擎", value: run.engine });
  }

  // 映射QL ID
  const qlIdMap: Record<string, string> = {
    "总品种数": "RUN-MET-ITEM-SYMBOLS",
    "平均收益率": "RUN-MET-ITEM-RETURN",
    "总交易次数": "RUN-MET-ITEM-TRADES",
    "平均夏普": "RUN-MET-ITEM-SHARPE",
  };

  return (
    <div style={styles.grid} data-ql-id="RUN-MET-CONTAINER">
      {cards.map((c) => (
        <div key={c.label} style={styles.card} data-ql-id={qlIdMap[c.label]}>
          <div style={styles.cardLabel}>{c.label}</div>
          <div style={{ ...styles.cardValue, color: c.color || "#333" }}>
            {c.value}
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * 样式对象
 * 定义了MetricCards组件中所有元素的样式
 */
const styles: Record<string, React.CSSProperties> = {
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
    gap: "12px",
    marginBottom: "20px",
  },
  card: {
    background: "#fff",
    borderRadius: "8px",
    padding: "14px",
    textAlign: "center",
    boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
  },
  cardLabel: {
    fontSize: "11px",
    color: "#888",
    marginBottom: "4px",
    textTransform: "uppercase",
    letterSpacing: "0.5px",
  },
  cardValue: {
    fontSize: "20px",
    fontWeight: 700,
  },
};
