import type { BacktestRecord } from "@/types";

interface Props {
  backtests: BacktestRecord[] | null;
  selectedSymbol: string;
}

function formatPct(v: number, digits = 2): string {
  return `${(v).toFixed(digits)}%`;
}

export default function BacktestDetail({
  backtests,
  selectedSymbol,
}: Props) {
  if (!backtests || backtests.length === 0) return null;

  const bt = backtests.find((b) => b.symbol === selectedSymbol);
  if (!bt) return null;

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
    <div style={styles.wrapper}>
      <h2 style={styles.title}>{selectedSymbol} 回测详情</h2>
      <div style={styles.grid}>
        {metrics.map(([label, value]) => (
          <div key={label} style={styles.item}>
            <span style={styles.label}>{label}</span>
            <span style={styles.value}>{value}</span>
          </div>
        ))}
      </div>

      {bt.params && bt.params.length > 0 && (
        <>
          <h3 style={styles.subtitle}>策略参数</h3>
          <div style={styles.grid}>
            {bt.params.map((p) => (
              <div key={p.name} style={styles.item}>
                <span style={styles.label}>{p.name}</span>
                <span style={styles.value}>{p.value}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

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