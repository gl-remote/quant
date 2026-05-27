import type { BacktestRecord, RunInfo } from "@/types";
import QlPanel from "@/components/QlPanel";

interface Props {
  run: RunInfo | null;
  backtests: BacktestRecord[] | null;
}

export default function MetricCards({ run, backtests }: Props) {
  if (!backtests || backtests.length === 0) {
    return null;
  }

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

  if (run) {
    cards.unshift({ label: "策略", value: run.strategy });
    cards.unshift({ label: "引擎", value: run.engine });
  }

  const qlIdMap: Record<string, string> = {
    "总品种数": "RUN-MET-ITEM-SYMBOLS",
    "平均收益率": "RUN-MET-ITEM-RETURN",
    "总交易次数": "RUN-MET-ITEM-TRADES",
    "平均夏普": "RUN-MET-ITEM-SHARPE",
  };

  return (
    <QlPanel
      qlId="RUN-MET-CONTAINER"
      name="指标总览"
      style={{ marginBottom: 28 }}
    >
      <div style={styles.grid}>
        {cards.map((c) => (
          <div key={c.label} style={styles.card} data-ql-id={qlIdMap[c.label]}>
            <div style={styles.cardLabel}>{c.label}</div>
            <div style={{ ...styles.cardValue, color: c.color || "#333" }}>
              {c.value}
            </div>
          </div>
        ))}
      </div>
    </QlPanel>
  );
}

const styles: Record<string, React.CSSProperties> = {
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
    gap: "16px",
  },
  card: {
    background: "#f8fafc",
    borderRadius: "8px",
    padding: "14px",
    textAlign: "center",
  },
  cardLabel: {
    fontSize: "11px",
    color: "#94a3b8",
    marginBottom: "4px",
    textTransform: "uppercase",
    letterSpacing: "0.5px",
  },
  cardValue: {
    fontSize: "20px",
    fontWeight: 700,
  },
};