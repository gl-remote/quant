import { useState } from "react";
import type { SummaryItem } from "@/types";

interface Props {
  data: SummaryItem[] | null;
  onSelect: (symbol: string) => void;
  selectedSymbol: string;
}

type SortKey = keyof SummaryItem;
type SortOrder = "asc" | "desc";

function formatPct(v: number, digits = 2): string {
  return `${v.toFixed(digits)}%`;
}

function formatNumber(v: number): string {
  return v.toLocaleString("zh-CN");
}

const columns: { key: SortKey; label: string; format: (v: number) => string }[] = [
  { key: "symbol", label: "品种", format: (v) => String(v) },
  { key: "total_return", label: "收益率", format: (v) => formatPct(v * 100) },
  { key: "total_trades", label: "交易次数", format: formatNumber },
  { key: "win_rate", label: "胜率", format: (v) => formatPct(v, 1) },
  { key: "max_drawdown", label: "最大回撤", format: (v) => formatPct(v) },
  { key: "sharpe", label: "夏普比率", format: (v) => v.toFixed(2) },
  { key: "end_balance", label: "最终权益", format: formatNumber },
];

export default function SymbolTable({ data, onSelect, selectedSymbol }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("total_return");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");

  if (!data || data.length === 0) {
    return (
      <div style={styles.empty}>
        <div style={styles.emptyIcon}>📭</div>
        <p>暂无回测记录</p>
      </div>
    );
  }

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortOrder("desc");
    }
  };

  const sortedData = [...data].sort((a, b) => {
    const aVal = a[sortKey] as number;
    const bVal = b[sortKey] as number;
    if (sortOrder === "asc") {
      return aVal - bVal;
    }
    return bVal - aVal;
  });

  const totalStats = {
    avgReturn: data.reduce((sum, item) => sum + item.total_return, 0) / data.length,
    avgSharpe: data.reduce((sum, item) => sum + item.sharpe, 0) / data.length,
    totalTrades: data.reduce((sum, item) => sum + item.total_trades, 0),
  };

  return (
    <div style={styles.wrapper}>
      <div style={styles.header}>
        <h2 style={styles.title}>
          <span style={styles.titleIcon}>📈</span>
          品种汇总
        </h2>
        <div style={styles.summaryStats}>
          <div style={styles.summaryItem}>
            <span style={styles.summaryLabel}>平均收益</span>
            <span style={{ ...styles.summaryValue, color: totalStats.avgReturn >= 0 ? "#059669" : "#dc2626" }}>
              {formatPct(totalStats.avgReturn * 100)}
            </span>
          </div>
          <div style={styles.summaryItem}>
            <span style={styles.summaryLabel}>平均夏普</span>
            <span style={{ ...styles.summaryValue, color: totalStats.avgSharpe >= 0 ? "#059669" : "#dc2626" }}>
              {totalStats.avgSharpe.toFixed(2)}
            </span>
          </div>
          <div style={styles.summaryItem}>
            <span style={styles.summaryLabel}>总交易次数</span>
            <span style={styles.summaryValue}>{formatNumber(totalStats.totalTrades)}</span>
          </div>
        </div>
      </div>

      <div style={styles.tableWrap}>
        <table style={styles.table}>
          <thead>
            <tr>
              {columns.map((col) => (
                <th
                  key={String(col.key)}
                  style={styles.th}
                  onClick={() => handleSort(col.key)}
                >
                  <div style={styles.thContent}>
                    <span>{col.label}</span>
                    {sortKey === col.key && (
                      <span style={styles.sortIcon}>
                        {sortOrder === "asc" ? "↑" : "↓"}
                      </span>
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedData.map((item) => {
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
                  <td style={{ ...styles.td, fontWeight: 600 }}>{item.symbol}</td>
                  <td
                    style={{
                      ...styles.td,
                      color: item.total_return >= 0 ? "#059669" : "#dc2626",
                      fontWeight: 600,
                    }}
                  >
                    {formatPct(item.total_return * 100)}
                  </td>
                  <td style={styles.td}>{formatNumber(item.total_trades)}</td>
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
                  <td style={styles.td}>{formatNumber(item.end_balance)}</td>
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
    background: "#ffffff",
    borderRadius: "12px",
    padding: "20px",
    marginBottom: "20px",
    boxShadow: "0 4px 20px rgba(0, 0, 0, 0.08)",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "16px",
    paddingBottom: "12px",
    borderBottom: "1px solid #f0f0f0",
  },
  title: {
    fontSize: "16px",
    fontWeight: 600,
    margin: 0,
    color: "#1a1a1a",
    display: "flex",
    alignItems: "center",
    gap: "8px",
  },
  titleIcon: {
    fontSize: "18px",
  },
  summaryStats: {
    display: "flex",
    gap: "24px",
  },
  summaryItem: {
    display: "flex",
    flexDirection: "column",
    alignItems: "right",
  },
  summaryLabel: {
    fontSize: "11px",
    color: "#9ca3af",
    marginBottom: "2px",
  },
  summaryValue: {
    fontSize: "14px",
    fontWeight: 600,
    color: "#374151",
  },
  tableWrap: {
    overflowX: "auto",
    maxHeight: "450px",
    overflowY: "auto",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse" as const,
    fontSize: "13px",
  },
  th: {
    textAlign: "left" as const,
    padding: "10px 14px",
    background: "#f9fafb",
    borderBottom: "2px solid #e5e7eb",
    color: "#6b7280",
    position: "sticky" as const,
    top: 0,
    cursor: "pointer",
    whiteSpace: "nowrap" as const,
  },
  thContent: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
  },
  sortIcon: {
    fontSize: "10px",
    color: "#9ca3af",
  },
  td: {
    padding: "10px 14px",
    borderBottom: "1px solid #f3f4f6",
    color: "#374151",
    whiteSpace: "nowrap" as const,
  },
  row: {
    cursor: "pointer",
    transition: "background-color 0.15s",
  },
  selectedRow: {
    background: "#eff6ff",
  },
  empty: {
    background: "#fafafa",
    borderRadius: "8px",
    padding: "48px",
    textAlign: "center",
    color: "#9ca3af",
  },
  emptyIcon: {
    fontSize: "48px",
    marginBottom: "12px",
  },
};