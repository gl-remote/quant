import type { BacktestRecord } from "@/types";
import QlPanel from "@/components/QlPanel";

interface Props {
  backtests: BacktestRecord[] | null;
  selectedSymbol: string;
}

function formatPct(v: number, digits = 2): string {
  return `${v.toFixed(digits)}%`;
}

export default function BacktestDetail({
  backtests,
  selectedSymbol,
}: Props) {
  if (!backtests || backtests.length === 0) {
    return (
      <QlPanel qlId="RUN-BT-EMPTY" name="回测记录详情" style={{ marginBottom: 24 }}>
        <div className="text-[13px] text-slate-400 py-4 text-center">暂无回测记录</div>
      </QlPanel>
    );
  }

  const bt = backtests.find((b) => b.symbol === selectedSymbol);
  if (!bt) {
    return (
      <QlPanel qlId="RUN-BT-EMPTY" name={`回测记录详情  ·  ${selectedSymbol}`} style={{ marginBottom: 24 }}>
        <div className="text-[13px] text-slate-400 py-4 text-center">未找到 "{selectedSymbol}" 的回测记录</div>
      </QlPanel>
    );
  }

  const metrics: [string, string][] = [
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
    <QlPanel
      qlId="RUN-BT-CONTAINER"
      name={`回测记录详情  ·  ${selectedSymbol}`}
      style={{ marginBottom: 24 }}
    >
      <div data-ql-id="RUN-BT-METRICS" className="grid grid-cols-[repeat(auto-fill,minmax(180px,1fr))] gap-2">
        {metrics.map(([label, value]) => (
          <div key={label} className="flex justify-between px-2.5 py-1.5 bg-slate-50 rounded border border-slate-100">
            <span className="text-xs text-slate-400">{label}</span>
            <span className="text-[13px] font-semibold text-slate-600">{value}</span>
          </div>
        ))}
      </div>

      {bt.params && bt.params.length > 0 && (
        <div data-ql-id="RUN-BT-PARAMS" className="mt-4">
          <div className="text-sm font-semibold text-slate-600 mb-2">策略参数</div>
          <div className="grid grid-cols-[repeat(auto-fill,minmax(180px,1fr))] gap-2">
            {bt.params.map((p) => (
              <div key={p.name} className="flex justify-between px-2.5 py-1.5 bg-slate-50 rounded border border-slate-100">
                <span className="text-xs text-slate-400">{p.name}</span>
                <span className="text-[13px] font-semibold text-slate-600">{p.value}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </QlPanel>
  );
}