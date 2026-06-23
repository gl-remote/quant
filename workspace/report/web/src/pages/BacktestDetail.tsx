import type { BacktestRecord } from "@/types";
import QlPanel from "@/components/layout/QlPanel";

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
      <QlPanel qlId="RUN-BT-EMPTY" name="回测记录详情" className="mb-6">
        <div className="text-[13px] text-slate-400 py-4 text-center">暂无回测记录</div>
      </QlPanel>
    );
  }

  const bt = backtests.find((b) => b.symbol === selectedSymbol);
  if (!bt) {
    return (
      <QlPanel qlId="RUN-BT-EMPTY" name={`回测记录详情  ·  ${selectedSymbol}`} className="mb-6">
        <div className="text-[13px] text-slate-400 py-4 text-center">未找到 "{selectedSymbol}" 的回测记录</div>
      </QlPanel>
    );
  }

  const metrics: [string, string][] = [
    // 资金概况：total_return 是 vnpy 输出的百分比（已乘100），直接显示
    ["收益率", `${bt.total_return?.toFixed(2) || "-"}%`],
    ["净盈亏", bt.total_net_pnl?.toLocaleString("zh-CN") || "-"],
    ["总手续费", bt.total_commission?.toLocaleString("zh-CN") || "-"],
    ["总滑点", bt.total_slippage?.toLocaleString("zh-CN") || "-"],
    // win_rate 基于 pnl>0 的平仓交易计算（排除开仓 pnl=0）
    ["胜率(平仓)", formatPct(bt.win_rate, 1)],
    // max_drawdown 是 vnpy 输出的绝对金额(元)，max_ddpercent 是百分比
    ["最大回撤", `${bt.max_drawdown?.toLocaleString("zh-CN")}元 (${bt.max_ddpercent?.toFixed(2) || "-"}%)`],
    ["夏普比率", bt.sharpe_ratio?.toFixed(2) || "-"],
    ["EWM夏普", bt.ewm_sharpe?.toFixed(2) || "-"],
    // total_trades 是总成交笔数（含开仓+平仓），非盈亏笔数
    ["成交次数", String(bt.total_trades)],
    ["盈利天数", String(bt.profit_days ?? "-")],
    ["亏损天数", String(bt.loss_days ?? "-")],
    ["初始资金", bt.initial_capital?.toLocaleString("zh-CN") || "-"],
    ["最终权益", bt.end_balance?.toLocaleString("zh-CN") || "-"],
    ["回测区间", `${bt.start_date} ~ ${bt.end_date}`],
    ["K线周期", bt.kline_interval || "-"],
    ["策略版本", bt.strategy_version || "-"],
  ];

  return (
    <QlPanel
      qlId="RUN-BT-CONTAINER"
      name={`回测记录详情  ·  ${selectedSymbol}`}
      className="mb-6"
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