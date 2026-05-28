import { useState, useEffect, useCallback } from "react";
import { useParams } from "react-router-dom";
import { useFetchJson } from "@/hooks/useFetchJson";
import type {
  RunInfo,
  SummaryItem,
  BacktestRecord,
  KlineData,
  EquityData,
  OptunaData,
} from "@/types";
import MetricCards from "@/components/MetricCards";
import SymbolTable from "@/components/SymbolTable";
import KlineChart from "@/components/KlineChart";
import EquityChart from "@/components/EquityChart";
import BacktestDetail from "@/components/BacktestDetail";
import OptunaCharts from "@/components/OptunaCharts";

type TabId = "backtest" | "params";

export default function RunPage() {
  const { id } = useParams<{ id: string }>();
  const runId = Number(id);
  const [activeTab, setActiveTab] = useState<TabId>("backtest");
  const [animKey, setAnimKey] = useState(0);

  const { data: run, loading: runLoading } = useFetchJson<RunInfo>(
    "run.json",
    runId
  );
  const { data: summary, loading: summaryLoading } =
    useFetchJson<SummaryItem[]>("summary.json", runId);
  const { data: backtests, loading: btLoading } =
    useFetchJson<BacktestRecord[]>("backtests.json", runId);
  const { data: equity } = useFetchJson<Record<string, EquityData>>(
    "equity.json",
    runId
  );
  const { data: optuna } = useFetchJson<OptunaData | null>(
    "optuna.json",
    runId
  );

  const [selectedSymbol, setSelectedSymbol] = useState<string>("");
  const [selectedInterval, setSelectedInterval] = useState<string>("");

  useEffect(() => {
    if (summary && summary.length > 0 && !selectedSymbol) {
      setSelectedSymbol(summary[0].symbol);
    }
  }, [summary, selectedSymbol]);

  useEffect(() => {
    if (selectedSymbol && backtests) {
      const bt = backtests.find((b) => b.symbol === selectedSymbol);
      if (bt) {
        setSelectedInterval(bt.kline_interval || "1m");
      }
    }
  }, [selectedSymbol, backtests]);

  const { data: kline, loading: klineLoading } = useFetchJson<KlineData>(
    selectedSymbol && selectedInterval ? `kline_${selectedSymbol}.${selectedInterval}.json` : "",
    selectedSymbol ? runId : undefined
  );

  const switchTab = useCallback((tab: TabId) => {
    if (tab !== activeTab) {
      setActiveTab(tab);
      setAnimKey((k) => k + 1);
    }
  }, [activeTab]);

  const handleTabKeyDown = useCallback(
    (e: React.KeyboardEvent, tab: TabId) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        switchTab(tab);
      }
    },
    [switchTab]
  );

  const loading = runLoading || summaryLoading || btLoading;
  if (loading) {
    return (
      <div data-ql-id="RUN-PG-LOADING" className="flex flex-col items-center justify-center py-20 bg-white rounded-xl border border-slate-200">
        <div className="w-10 h-10 border-4 border-slate-100 border-t-blue-600 rounded-full animate-spin" />
        <p className="mt-4 text-sm text-slate-400">加载中...</p>
      </div>
    );
  }

  const hasOptuna = optuna && optuna.study_name;

  const tabBtn = "px-[18px] py-2 text-[13px] font-medium rounded-md border-none bg-transparent cursor-pointer outline-none transition-all whitespace-nowrap";
  const tabActive = "bg-blue-600 text-white shadow-md shadow-blue-600/30";
  const tabInactive = "text-slate-500";

  return (
    <div data-ql-id="RUN-PG-CONTAINER">
      <style>{animationStyles}</style>

      <div data-ql-id="RUN-PG-HEADER" className="flex justify-between items-start mb-7 p-6 bg-white rounded-xl border border-slate-200 flex-wrap gap-4">
        <div className="flex flex-col gap-2">
          <div className="flex gap-2.5 items-center">
            <span className="text-sm font-bold text-slate-900 font-mono">Run #{runId}</span>
            <span className="text-[11px] font-medium px-2.5 py-0.5 bg-green-100 text-green-700 rounded-xl">已完成</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900 m-0">{run?.strategy || "策略回测"}</h1>
          <div className="flex items-center gap-3 text-[13px] text-slate-500 flex-wrap">
            <span className="flex items-center gap-1">
              <span className="text-sm">⚙️</span>
              {run?.engine}
            </span>
            <span className="text-slate-300">|</span>
            <span className="flex items-center gap-1">
              <span className="text-sm">📈</span>
              {run?.symbols} 个品种
            </span>
            <span className="text-slate-300">|</span>
            <span className="flex items-center gap-1">
              <span className="text-sm">📅</span>
              {run?.created_at}
            </span>
          </div>
        </div>

        <div role="tablist" aria-label="内容切换" className="flex bg-slate-100 rounded-lg p-0.5 shrink-0">
          <button
            role="tab"
            id="tab-backtest"
            aria-selected={activeTab === "backtest"}
            aria-controls="panel-backtest"
            tabIndex={activeTab === "backtest" ? 0 : -1}
            data-ql-id="RUN-PG-TAB-BACKTEST"
            onClick={() => switchTab("backtest")}
            onKeyDown={(e) => handleTabKeyDown(e, "backtest")}
            className={`${tabBtn} ${activeTab === "backtest" ? tabActive : tabInactive}`}
          >
            回测结果
          </button>
          <button
            role="tab"
            id="tab-params"
            aria-selected={activeTab === "params"}
            aria-controls="panel-params"
            tabIndex={activeTab === "params" ? 0 : -1}
            data-ql-id="RUN-PG-TAB-PARAMS"
            onClick={() => switchTab("params")}
            onKeyDown={(e) => handleTabKeyDown(e, "params")}
            disabled={!hasOptuna}
            className={`${tabBtn} ${activeTab === "params" ? tabActive : tabInactive} ${!hasOptuna ? "opacity-45 cursor-not-allowed" : ""}`}
            title={hasOptuna ? "查看参数优化结果" : "该 run 无优化数据"}
          >
            参数优化
          </button>
        </div>
      </div>

      <div className="relative">
        <div
          key={`backtest-${animKey}`}
          id="panel-backtest"
          role="tabpanel"
          aria-labelledby="tab-backtest"
          className={activeTab === "backtest" ? "block" : "hidden"}
        >
          <div style={activeTab === "backtest" ? { animation: "tabFadeIn 0.25s ease-out" } : undefined}>
            <MetricCards run={run} backtests={backtests} />
            <div className="grid grid-cols-[1fr_420px] gap-7">
              <div className="flex flex-col">
                <KlineChart data={kline} loading={klineLoading} />
                {equity && selectedSymbol && equity[selectedSymbol] && (
                  <EquityChart data={equity[selectedSymbol]} />
                )}
              </div>
              <div
                className="flex flex-col gap-7 min-h-0 overflow-y-auto pr-1"
                style={{
                  height: "calc(100vh - 84px)",
                  scrollbarWidth: "thin",
                  scrollbarColor: "#cbd5e1 transparent",
                } as React.CSSProperties}
              >
                <SymbolTable
                  data={summary}
                  onSelect={setSelectedSymbol}
                  selectedSymbol={selectedSymbol}
                />
                <BacktestDetail
                  backtests={backtests}
                  selectedSymbol={selectedSymbol}
                />
              </div>
            </div>
          </div>
        </div>

        <div
          key={`params-${animKey}`}
          id="panel-params"
          role="tabpanel"
          aria-labelledby="tab-params"
          className={activeTab === "params" ? "block" : "hidden"}
        >
          <div style={activeTab === "params" ? { animation: "tabFadeIn 0.25s ease-out" } : undefined}>
            {hasOptuna ? (
              <OptunaCharts data={optuna!} />
            ) : (
              <div className="bg-white rounded-xl border border-slate-200 py-16 text-center">
                <p className="text-sm text-slate-400 m-0">该 run 无优化数据</p>
              </div>
            )}
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