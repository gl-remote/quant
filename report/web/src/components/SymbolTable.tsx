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

const columns: { key: SortKey; label: string; format: (v: any) => string }[] = [
  { key: "symbol", label: "品种", format: (v) => String(v) },
  { key: "total_return", label: "收益率", format: (v) => formatPct(v * 100) },
  { key: "win_rate", label: "胜率", format: (v) => formatPct(v, 1) },
  { key: "win_loss_ratio", label: "盈亏比", format: (v) => v.toFixed(2) },
  { key: "total_trades", label: "交易次数", format: formatNumber },
  { key: "max_drawdown", label: "最大回撤", format: (v) => formatPct(v) },
  { key: "sharpe", label: "夏普比率", format: (v) => v.toFixed(2) },
  { key: "annual_return", label: "年化收益率", format: (v) => formatPct(v * 100) },
  { key: "end_balance", label: "最终权益", format: formatNumber },
  { key: "id", label: "回测ID", format: (v) => String(v) },
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
        <div className="text-center py-10 text-slate-400">
          <div className="text-5xl mb-3">📭</div>
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
      <div className="flex justify-between items-center mb-4 pb-3 border-b border-slate-100" data-ql-id="RUN-TBL-HEADER">
        <div>
          <h2 className="text-base font-semibold text-slate-800 m-0">📈 品种汇总</h2>
        </div>
        <div className="flex gap-6">
          <div className="flex flex-col items-end">
            <span className="text-[11px] text-slate-400 mb-0.5">平均收益</span>
            <span className="text-sm font-semibold" style={{ color: totalStats.avgReturn >= 0 ? "#059669" : "#dc2626" }}>
              {formatPct(totalStats.avgReturn * 100)}
            </span>
          </div>
          <div className="flex flex-col items-end">
            <span className="text-[11px] text-slate-400 mb-0.5">平均夏普</span>
            <span className="text-sm font-semibold" style={{ color: totalStats.avgSharpe >= 0 ? "#059669" : "#dc2626" }}>
              {totalStats.avgSharpe.toFixed(2)}
            </span>
          </div>
          <div className="flex flex-col items-end">
            <span className="text-[11px] text-slate-400 mb-0.5">总交易次数</span>
            <span className="text-sm font-semibold text-slate-600">{formatNumber(totalStats.totalTrades)}</span>
          </div>
        </div>
      </div>

      <div className="overflow-x-auto max-h-[50vh] overflow-y-auto" style={{ scrollbarWidth: "thin", scrollbarColor: "#cbd5e1 transparent" } as React.CSSProperties}>
        <table className="w-full border-collapse text-[13px]" data-ql-id="RUN-TBL-TABLE">
          <thead>
            <tr>
              {columns.map((col) => (
                <th
                  key={String(col.key)}
                  className="text-left px-3.5 py-2.5 bg-slate-50 border-b-2 border-slate-200 text-slate-500 sticky top-0 cursor-pointer whitespace-nowrap"
                  onClick={() => handleSort(col.key)}
                >
                  <div className="flex items-center gap-1.5">
                    <span>{col.label}</span>
                    {sortKey === col.key && (
                      <span className="text-[10px] text-slate-400">
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
                  className={`cursor-pointer transition-colors ${isSelected ? "bg-blue-50" : "hover:bg-slate-50"}`}
                >
                  <td className="px-3.5 py-2.5 border-b border-slate-50 font-semibold text-slate-600 whitespace-nowrap">{item.symbol}</td>
                  <td
                    className="px-3.5 py-2.5 border-b border-slate-50 font-semibold whitespace-nowrap"
                    style={{ color: item.total_return >= 0 ? "#059669" : "#dc2626" }}
                  >
                    {formatPct(item.total_return * 100)}
                  </td>
                  <td className="px-3.5 py-2.5 border-b border-slate-50 text-slate-600 whitespace-nowrap">{formatPct(item.win_rate, 1)}</td>
                  <td
                    className="px-3.5 py-2.5 border-b border-slate-50 whitespace-nowrap"
                    style={{ color: item.win_loss_ratio >= 1 ? "#059669" : "#dc2626" }}
                  >
                    {item.win_loss_ratio.toFixed(2)}
                  </td>
                  <td className="px-3.5 py-2.5 border-b border-slate-50 text-slate-600 whitespace-nowrap">{formatNumber(item.total_trades)}</td>
                  <td className="px-3.5 py-2.5 border-b border-slate-50 text-red-600 whitespace-nowrap">
                    {formatPct(item.max_drawdown)}
                  </td>
                  <td
                    className="px-3.5 py-2.5 border-b border-slate-50 whitespace-nowrap"
                    style={{ color: item.sharpe >= 0 ? "#059669" : "#dc2626" }}
                  >
                    {item.sharpe.toFixed(2)}
                  </td>
                  <td
                    className="px-3.5 py-2.5 border-b border-slate-50 whitespace-nowrap"
                    style={{ color: item.annual_return >= 0 ? "#059669" : "#dc2626" }}
                  >
                    {formatPct(item.annual_return * 100)}
                  </td>
                  <td className="px-3.5 py-2.5 border-b border-slate-50 text-slate-600 whitespace-nowrap">{formatNumber(item.end_balance)}</td>
                  <td className="px-3.5 py-2.5 border-b border-slate-50 text-slate-400 text-xs whitespace-nowrap">{item.id}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </QlPanel>
  );
}