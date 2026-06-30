import { useCallback } from "react";
import type { RunInfo } from "@/types";

export type TabId = "backtest" | "structure" | "params" | "logs";

interface Props {
  runId: number;
  run: RunInfo | null;
  hasOptuna: boolean;
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
}

const tabBtn = "px-[18px] py-2 text-[13px] font-medium rounded-md border-none bg-transparent cursor-pointer outline-none transition-all whitespace-nowrap";
const tabActive = "bg-blue-800 text-slate-900 shadow-md shadow-blue-800/30";
const tabInactive = "text-slate-500";

export default function RunHeader({
  runId,
  run,
  hasOptuna,
  activeTab,
  onTabChange,
}: Props) {
  const handleTabKeyDown = useCallback(
    (e: React.KeyboardEvent, tab: TabId) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        onTabChange(tab);
      }
    },
    [onTabChange]
  );

  return (
    <div
      data-ql-id="RUN-PG-HEADER"
      className="flex justify-between items-start mb-7 p-6 bg-white rounded-xl border border-slate-200 flex-wrap gap-4"
    >
      <div className="flex flex-col gap-2">
        <div className="flex gap-2.5 items-center">
          <span className="text-sm font-bold text-slate-900 font-mono">
            Run #{runId}
          </span>
          <span className="text-[11px] font-medium px-2.5 py-0.5 bg-green-100 text-green-700 rounded-xl">
            已完成
          </span>
        </div>
        <h1 className="text-2xl font-bold text-slate-900 m-0">
          {run?.strategy || "策略回测"}
        </h1>
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

      <div
        role="tablist"
        aria-label="内容切换"
        className="flex bg-slate-100 rounded-lg p-0.5 shrink-0"
      >
        <button
          role="tab"
          id="tab-backtest"
          aria-selected={activeTab === "backtest"}
          aria-controls="panel-backtest"
          tabIndex={activeTab === "backtest" ? 0 : -1}
          data-ql-id="RUN-PG-TAB-BACKTEST"
          onClick={() => onTabChange("backtest")}
          onKeyDown={(e) => handleTabKeyDown(e, "backtest")}
          className={`${tabBtn} ${activeTab === "backtest" ? tabActive : tabInactive}`}
        >
          回测结果
        </button>
        <button
          role="tab"
          id="tab-structure"
          aria-selected={activeTab === "structure"}
          aria-controls="panel-structure"
          tabIndex={activeTab === "structure" ? 0 : -1}
          data-ql-id="RUN-PG-TAB-STRUCTURE"
          onClick={() => onTabChange("structure")}
          onKeyDown={(e) => handleTabKeyDown(e, "structure")}
          className={`${tabBtn} ${activeTab === "structure" ? tabActive : tabInactive}`}
        >
          结构诊断
        </button>
        <button
          role="tab"
          id="tab-params"
          aria-selected={activeTab === "params"}
          aria-controls="panel-params"
          tabIndex={activeTab === "params" ? 0 : -1}
          data-ql-id="RUN-PG-TAB-PARAMS"
          onClick={() => onTabChange("params")}
          onKeyDown={(e) => handleTabKeyDown(e, "params")}
          disabled={!hasOptuna}
          className={`${tabBtn} ${activeTab === "params" ? tabActive : tabInactive} ${!hasOptuna ? "opacity-45 cursor-not-allowed" : ""}`}
          title={hasOptuna ? "查看参数优化结果" : "该 run 无优化数据"}
        >
          参数优化
        </button>
        <button
          role="tab"
          id="tab-logs"
          aria-selected={activeTab === "logs"}
          aria-controls="panel-logs"
          tabIndex={activeTab === "logs" ? 0 : -1}
          data-ql-id="RUN-PG-TAB-LOGS"
          onClick={() => onTabChange("logs")}
          onKeyDown={(e) => handleTabKeyDown(e, "logs")}
          className={`${tabBtn} ${activeTab === "logs" ? tabActive : tabInactive}`}
        >
          运行日志
        </button>
      </div>
    </div>
  );
}
