/**
 * @file BacktestDetail.tsx
 * @description 回测详情组件
 * 展示选中品种的详细回测指标和策略参数
 * 包括收益率、胜率、最大回撤、夏普比率、交易次数等关键指标
 */

import type { BacktestRecord } from "@/types";

/**
 * BacktestDetail组件属性接口
 * @interface Props
 * @property {BacktestRecord[] | null} backtests - 回测记录数组
 * @property {string} selectedSymbol - 选中的品种代码
 */
interface Props {
  backtests: BacktestRecord[] | null;
  selectedSymbol: string;
}

/**
 * 格式化百分比
 * @param {number} v - 数值
 * @param {number} [digits=2] - 小数位数
 * @returns {string} 格式化后的百分比字符串
 */
function formatPct(v: number, digits = 2): string {
  return `${(v).toFixed(digits)}%`;
}

/**
 * BacktestDetail组件
 * 回测详情展示组件
 * 
 * @component
 * @param {Props} props - 组件属性
 * @returns {JSX.Element} 渲染后的回测详情组件
 */
export default function BacktestDetail({
  backtests,
  selectedSymbol,
}: Props) {
  // 无回测数据时返回空
  if (!backtests || backtests.length === 0) {
    return <div data-ql-id="RUN-BT-EMPTY" />;
  }

  // 查找选中品种的回测记录
  const bt = backtests.find((b) => b.symbol === selectedSymbol);
  if (!bt) {
    return <div data-ql-id="RUN-BT-EMPTY" />;
  }

  // 构建指标数组
  const metrics = [
    ["收益率", formatPct(bt.total_return * 100)],
    ["胜率", formatPct(bt.win_rate, 1)],
    ["最大回撤", formatPct(bt.max_drawdown)],
    ["夏普比率", bt.sharpe_ratio?.toFixed(2) || "-"],
    ["交易次数", String(bt.total_trades)],
    ["初始资金", bt.initial_capital?.toLocaleString() || "-"],
    ["最终权益", bt.end_balance?.toLocaleString() || "-"],
    ["回测区间", `${bt.start_date} ~ ${bt.end_date}`],
    ["K线周期", bt.kline_interval || "-"],
    ["策略版本", bt.strategy_version || "-"],
  ];

  return (
    <div data-ql-id="RUN-BT-CONTAINER" style={styles.wrapper}>
      <h2 data-ql-id="RUN-BT-HEADER" style={styles.title}>{selectedSymbol} 回测详情</h2>
      <div data-ql-id="RUN-BT-METRICS" style={styles.grid}>
        {metrics.map(([label, value]) => (
          <div key={label} style={styles.item}>
            <span style={styles.label}>{label}</span>
            <span style={styles.value}>{value}</span>
          </div>
        ))}
      </div>

      {/* 显示策略参数（如果有） */}
      {bt.params && bt.params.length > 0 && (
        <div data-ql-id="RUN-BT-PARAMS">
          <h3 style={styles.subtitle}>策略参数</h3>
          <div style={styles.grid}>
            {bt.params.map((p) => (
              <div key={p.name} style={styles.item}>
                <span style={styles.label}>{p.name}</span>
                <span style={styles.value}>{p.value}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * 样式对象
 * 定义了BacktestDetail组件中所有元素的样式
 */
const styles: Record<string, React.CSSProperties> = {
  wrapper: {
    background: "#fff",
    borderRadius: "8px",
    padding: "16px",
    marginBottom: "16px",
    boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
  },
  title: {
    fontSize: "16px",
    fontWeight: 600,
    margin: "0 0 12px 0",
    color: "#555",
  },
  subtitle: {
    fontSize: "14px",
    fontWeight: 600,
    margin: "16px 0 8px 0",
    color: "#555",
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
    gap: "8px",
  },
  item: {
    display: "flex",
    justifyContent: "space-between",
    padding: "6px 10px",
    background: "#f9fafb",
    borderRadius: "4px",
  },
  label: {
    fontSize: "12px",
    color: "#888",
  },
  value: {
    fontSize: "13px",
    fontWeight: 600,
    color: "#333",
  },
};
