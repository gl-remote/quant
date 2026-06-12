import { useState } from "react";
import { useRunData } from "./useRunData";
import RunHeader, { type TabId } from "./RunHeader";
import MetricCards from "@/components/data/MetricCards";
import SymbolTable from "@/components/data/SymbolTable";
import KlineChart from "@/components/charts/KlineChart";
import EquityChart from "@/components/charts/EquityChart";
import BacktestDetail from "@/pages/BacktestDetail";
import OptunaCharts from "@/components/charts/OptunaCharts";
import LogViewer from "@/components/data/RunLogs";

export default function RunPage() {
  const data = useRunData();
  const [activeTab, setActiveTab] = useState<TabId>("backtest");

  if (data.loading) {
    return (
      <div
        data-ql-id="RUN-PG-LOADING"
        className="flex flex-col items-center justify-center py-20 bg-white rounded-xl border border-slate-200"
      >
        <div className="w-10 h-10 border-4 border-slate-100 border-t-blue-600 rounded-full animate-spin" />
        <p className="mt-4 text-sm text-slate-400">加载中...</p>
      </div>
    );
  }

  return (
    <div data-ql-id="RUN-PG-CONTAINER">
      <style>{animationStyles}</style>

      <RunHeader
        runId={data.runId}
        run={data.run}
        hasOptuna={data.hasOptuna}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />

      <div className="relative">
        {/* 回测结果 */}
        <div
          id="panel-backtest"
          role="tabpanel"
          aria-labelledby="tab-backtest"
          className={activeTab === "backtest" ? "block" : "hidden"}
        >
          <div
            style={
              activeTab === "backtest"
                ? { animation: "tabFadeIn 0.25s ease-out" }
                : undefined
            }
          >
            <MetricCards run={data.run} backtests={data.backtests} />
            <div className="grid grid-cols-[1fr_420px] gap-7">
              <div className="flex flex-col">
                <KlineChart
                  data={data.kline}
                  trades={
                    data.selectedSymbol
                      ? data.tradesData?.[data.selectedSymbol]
                      : null
                  }
                  loading={data.klineLoading}
                />
                {data.equity &&
                  data.selectedSymbol &&
                  data.equity[data.selectedSymbol] && (
                    <EquityChart data={data.equity[data.selectedSymbol]} />
                  )}
              </div>
              <div className="flex flex-col gap-7">
                <SymbolTable
                  data={data.summary}
                  onSelect={data.setSelectedSymbol}
                  selectedSymbol={data.selectedSymbol}
                />
                <BacktestDetail
                  backtests={data.backtests}
                  selectedSymbol={data.selectedSymbol}
                />
              </div>
            </div>
          </div>
        </div>

        {/* 参数优化 */}
        <div
          id="panel-params"
          role="tabpanel"
          aria-labelledby="tab-params"
          className={activeTab === "params" ? "block" : "hidden"}
        >
          <div
            style={
              activeTab === "params"
                ? { animation: "tabFadeIn 0.25s ease-out" }
                : undefined
            }
          >
            {data.hasOptuna && data.optuna ? (
              <OptunaCharts data={data.optuna} />
            ) : (
              <div className="bg-white rounded-xl border border-slate-200 py-16 text-center">
                <p className="text-sm text-slate-400 m-0">该 run 无优化数据</p>
              </div>
            )}
          </div>
        </div>

        {/* 运行日志 */}
        <div
          id="panel-logs"
          role="tabpanel"
          aria-labelledby="tab-logs"
          className={activeTab === "logs" ? "block" : "hidden"}
        >
          <div
            style={
              activeTab === "logs"
                ? { animation: "tabFadeIn 0.25s ease-out" }
                : undefined
            }
          >
            <LogViewer logs={data.runLogs ?? null} />
          </div>
        </div>
      </div>
    </div>
  );
}

const animationStyles = `
@keyframes tabFadeIn {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
}
`;
