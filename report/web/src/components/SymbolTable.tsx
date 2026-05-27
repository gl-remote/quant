import { useState } from "react";
import type { SummaryItem } from "@/types";
import QlPanel from "@/components/QlPanel";
import { qlIdNameMap } from "@/data/qlIdMapping";

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
      <QlPanel
        qlId="RUN-TBL-EMPTY"
        name={qlIdNameMap["RUN-TBL-EMPTY"]}
        style={{ marginBottom: 28 }}
      >
        <div style={{ textAlign: "center", padding: "40px 0", color: "#94a3b8" }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>📭</div>
          <p>暂无回测记录</p>
        </div>
      </QlPanel>
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
    <QlPanel
      qlId="RUN-TBL-CONTAINER"
      name={qlIdNameMap["RUN-TBL-CONTAINER"]}
      style={{ marginBottom: 28 }}
    >
      <div style={styles.headRow} data-ql-id="RUN-TBL-HEADER">
        <div>
          <h2 style={styles.headTitle}>📈 品种汇总</h2>
        </div>
        <div style={styles.statsRow}>
          <div style={styles.statItem}>
            <span style={styles.statLabel}>平均收益</span>
            <span style={{ ...styles.statVal, color: totalStats.avgReturn >= 0 ? "#059669" : "#dc2626" }}>
              {formatPct(totalStats.avgReturn * 100)}
            </span>
          </div>
          <div style={styles.statItem}>
            <span style={styles.statLabel}>平均夏普</span>
            <span style={{ ...styles.statVal, color: totalStats.avgSharpe >= 0 ? "#059669" : "#dc2626" }}>
              {totalStats.avgSharpe.toFixed(2)}
            </span>
          </div>
          <div style={styles.statItem}>
            <span style={styles.statLabel}>总交易次数</span>
            <span style={styles.statVal}>{formatNumber(totalStats.totalTrades)}</span>
          </div>
        </div>
      </div>

      <div style={styles.tableWrap}>
        <table style={styles.table} data-ql-id="RUN-TBL-TABLE">
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
                  data-ql-id={`RUN-TBL-ROW-${item.symbol}`}
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
    </QlPanel>
  );
}

const styles: Record<string, React.CSSProperties> = {
  headRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "16px",
    paddingBottom: "12px",
    borderBottom: "1px solid #f1f5f9",
  },
  headTitle: {
    fontSize: "16px",
    fontWeight: 600,
    margin: 0,
    color: "#1e293b",
  },
  statsRow: {
    display: "flex",
    gap: "24px",
  },
  statItem: {
    display: "flex",
    flexDirection: "column",
    alignItems: "flex-end",
  },
  statLabel: {
    fontSize: "11px",
    color: "#94a3b8",
    marginBottom: "2px",
  },
  statVal: {
    fontSize: "14px",
    fontWeight: 600,
    color: "#475569",
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
    padding: "10px 14px",
    background: "#f8fafc",
    borderBottom: "2px solid #e2e8f0",
    color: "#64748b",
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
    color: "#94a3b8",
  },
  td: {
    padding: "10px 14px",
    borderBottom: "1px solid #f8fafc",
    color: "#475569",
    whiteSpace: "nowrap" as const,
  },
  row: {
    cursor: "pointer",
    transition: "background-color 0.15s",
  },
  selectedRow: {
    background: "#eff6ff",
  },
};