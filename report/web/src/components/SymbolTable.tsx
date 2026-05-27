import type { SummaryItem } from "@/types";

interface Props {
  data: SummaryItem[] | null;
  onSelect: (symbol: string) => void;
  selectedSymbol: string;
}

function formatPct(v: number, digits = 2): string {
  return `${(v).toFixed(digits)}%`;
}

export default function SymbolTable({ data, onSelect, selectedSymbol }: Props) {
  if (!data || data.length === 0) {
    return <p style={{ color: "#999" }}>无回测记录</p>;
  }

  return (
    <div style={styles.wrapper}>
      <h2 style={styles.title}>品种汇总</h2>
      <div style={styles.tableWrap}>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>品种</th>
              <th style={styles.th}>收益率</th>
              <th style={styles.th}>交易次数</th>
              <th style={styles.th}>胜率</th>
              <th style={styles.th}>最大回撤</th>
              <th style={styles.th}>夏普</th>
              <th style={styles.th}>最终权益</th>
            </tr>
          </thead>
          <tbody>
            {data.map((item) => {
              const isSelected = item.symbol === selectedSymbol;
              return (
                <tr
                  key={item.symbol}
                  onClick={() => onSelect(item.symbol)}
                  style={{
                    ...styles.row,
                    ...(isSelected ? styles.selectedRow : {}),
                  }}
                >
                  <td style={styles.td}>{item.symbol}</td>
                  <td
                    style={{
                      ...styles.td,
                      color: item.total_return >= 0 ? "#059669" : "#dc2626",
                    }}
                  >
                    {formatPct(item.total_return * 100)}
                  </td>
                  <td style={styles.td}>{item.total_trades}</td>
                  <td style={styles.td}>{formatPct(item.win_rate, 1)}</td>
                  <td style={{ ...styles.td, color: "#dc2626" }}>
                    {formatPct(item.max_drawdown)}
                  </td>
                  <td
                    style={{
                      ...styles.td,
                      color: item.sharpe >= 0 ? "#059669" : "#dc2626",
                    }}
                  >
                    {item.sharpe.toFixed(2)}
                  </td>
                  <td style={styles.td}>
                    {item.end_balance.toLocaleString()}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
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
  tableWrap: {
    overflowX: "auto",
    maxHeight: "400px",
    overflowY: "auto",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse" as const,
    fontSize: "13px",
  },
  th: {
    textAlign: "left" as const,
    padding: "8px 12px",
    background: "#f9fafb",
    borderBottom: "2px solid #e5e7eb",
    color: "#666",
    position: "sticky" as const,
    top: 0,
  },
  td: {
    padding: "6px 12px",
    borderBottom: "1px solid #f3f4f6",
  },
  row: {
    cursor: "pointer",
  },
  selectedRow: {
    background: "#eff6ff",
  },
};