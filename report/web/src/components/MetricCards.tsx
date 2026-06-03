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

  // 只保留每个品种最优的那条回测记录（和 SymbolTable 保持一致）
  const bestBySymbol: Record<string, typeof backtests[0]> = {};
  for (const bt of backtests) {
    const sym = bt.symbol;
    if (!bestBySymbol[sym] || (bt.total_return || 0) > (bestBySymbol[sym].total_return || 0)) {
      bestBySymbol[sym] = bt;
    }
  }
  const bestRecords = Object.values(bestBySymbol);
  const uniqueSymbols = bestRecords.length;

  const totalReturn = bestRecords.reduce(
    (sum, b) => sum + (b.total_return || 0),
    0
  );
  const avgReturn = totalReturn / uniqueSymbols;
  const totalTrades = bestRecords.reduce(
    (sum, b) => sum + (b.total_trades || 0),
    0
  );
  const avgSharpe =
    bestRecords.reduce((sum, b) => sum + (b.sharpe_ratio || 0), 0) /
    uniqueSymbols;

  const cards = [
    { label: "总品种数", value: String(uniqueSymbols) },
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
      <div className="grid grid-cols-[repeat(auto-fit,minmax(140px,1fr))] gap-4">
        {cards.map((c) => (
          <div key={c.label} className="bg-slate-50 rounded-lg p-3.5 text-center" data-ql-id={qlIdMap[c.label]}>
            <div className="text-[11px] text-slate-400 uppercase tracking-wider mb-1">{c.label}</div>
            <div className="text-xl font-bold" style={{ color: c.color || "#333" }}>
              {c.value}
            </div>
          </div>
        ))}
      </div>
    </QlPanel>
  );
}