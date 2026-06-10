import { useState } from "react";
import type { SummaryItem } from "@/types";
import QlPanel from "@/components/layout/QlPanel";
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

const columns: { key: SortKey; label: string; format: (v: any) => string; textClass?: (v: any) => string }[] = [
  { key: "symbol", label: "品种", format: (v) => String(v) },
  { key: "total_return", label: "收益率", format: (v) => `${v.toFixed(2)}%`, textClass: (v) => v >= 0 ? "text-green-600" : "text-red-600" },
  { key: "win_rate", label: "胜率", format: (v) => formatPct(v, 1) },
  { key: "win_loss_ratio", label: "盈亏比", format: (v) => v.toFixed(2), textClass: (v) => v >= 1 ? "text-green-600" : "text-red-600" },
  { key: "total_trades", label: "成交次数", format: formatNumber },
  { key: "max_drawdown", label: "最大回撤(元)", format: (v) => formatNumber(v || 0), textClass: () => "text-red-600" },
  { key: "sharpe", label: "夏普比率", format: (v) => v.toFixed(2), textClass: (v) => v >= 0 ? "text-green-600" : "text-red-600" },
  { key: "annual_return", label: "年化收益", format: (v) => `${v.toFixed(2)}%`, textClass: (v) => v >= 0 ? "text-green-600" : "text-red-600" },
  { key: "end_balance", label: "最终权益", format: formatNumber },
  { key: "total_net_pnl" as SortKey, label: "净盈亏", format: (v) => formatNumber(v || 0), textClass: (v) => (v || 0) >= 0 ? "text-green-600" : "text-red-600" },
  { key: "total_commission" as SortKey, label: "手续费", format: (v) => formatNumber(v || 0) },
  { key: "profit_days" as SortKey, label: "盈利天数", format: (v) => String(v ?? "-") },
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
        className="mb-7"
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

  const avgReturnClass = totalStats.avgReturn >= 0 ? "text-green-600" : "text-red-600";
  const avgSharpeClass = totalStats.avgSharpe >= 0 ? "text-green-600" : "text-red-600";

  return (
    <QlPanel
      qlId="RUN-TBL-CONTAINER"
      name={qlIdNameMap["RUN-TBL-CONTAINER"]}
      className="mb-7"
    >
      <div className="flex justify-between items-center mb-4 pb-3 border-b border-slate-100" data-ql-id="RUN-TBL-HEADER">
        <div>
          <h2 className="text-base font-semibold text-slate-800 m-0">📈 品种汇总</h2>
        </div>
        <div className="flex gap-6">
          <div className="flex flex-col items-end">
            <span className="text-[11px] text-slate-400 mb-0.5">平均收益</span>
            <span className={`text-sm font-semibold ${avgReturnClass}`}>
              {`${totalStats.avgReturn.toFixed(2)}%`}
            </span>
          </div>
          <div className="flex flex-col items-end">
            <span className="text-[11px] text-slate-400 mb-0.5">平均夏普</span>
            <span className={`text-sm font-semibold ${avgSharpeClass}`}>
              {totalStats.avgSharpe.toFixed(2)}
            </span>
          </div>
          <div className="flex flex-col items-end">
            <span className="text-[11px] text-slate-400 mb-0.5">总交易次数</span>
            <span className="text-sm font-semibold text-slate-600">{formatNumber(totalStats.totalTrades)}</span>
          </div>
        </div>
      </div>

      <div className="overflow-x-auto max-h-[50vh] overflow-y-auto">
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
                  {columns.map((col) => {
                    const raw = item[col.key];
                    const textClass = col.textClass ? col.textClass(raw) : "text-slate-600";
                    const isFirst = col.key === "symbol";
                    return (
                      <td
                        key={String(col.key)}
                        className={`px-3.5 py-2.5 border-b border-slate-50 whitespace-nowrap ${isFirst ? "font-semibold text-slate-600" : textClass}`}
                      >
                        {col.format(raw)}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </QlPanel>
  );
}
