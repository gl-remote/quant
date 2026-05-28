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

  // 当选中的 symbol 变化时，从 backtests 中获取对应的 interval
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
      <div data-ql-id="RUN-PG-LOADING" style={styles.loadingContainer}>
        <div style={styles.loadingSpinner}></div>
        <p style={styles.loadingText}>加载中...</p>
      </div>
    );
  }

  const hasOptuna = optuna && optuna.study_name;

  return (
    <div data-ql-id="RUN-PG-CONTAINER">
      <style>{animationStyles}</style>

      <div data-ql-id="RUN-PG-HEADER" style={styles.header}>
        <div style={styles.headerLeft}>
          <div style={styles.runBadge}>
            <span style={styles.runId}>Run #{runId}</span>
            <span style={styles.statusPill}>已完成</span>
          </div>
          <h1 style={styles.title}>{run?.strategy || "策略回测"}</h1>
          <div style={styles.metaRow}>
            <span style={styles.metaItem}>
              <span style={styles.metaIcon}>⚙️</span>
              {run?.engine}
            </span>
            <span style={styles.metaDivider}>|</span>
            <span style={styles.metaItem}>
              <span style={styles.metaIcon}>📈</span>
              {run?.symbols} 个品种
            </span>
            <span style={styles.metaDivider}>|</span>
            <span style={styles.metaItem}>
              <span style={styles.metaIcon}>📅</span>
              {run?.created_at}
            </span>
          </div>
        </div>

        <div role="tablist" aria-label="内容切换" style={styles.tabGroup}>
          <button
            role="tab"
            id="tab-backtest"
            aria-selected={activeTab === "backtest"}
            aria-controls="panel-backtest"
            tabIndex={activeTab === "backtest" ? 0 : -1}
            data-ql-id="RUN-PG-TAB-BACKTEST"
            onClick={() => switchTab("backtest")}
            onKeyDown={(e) => handleTabKeyDown(e, "backtest")}
            style={{
              ...styles.tabBtn,
              ...(activeTab === "backtest" ? styles.tabBtnActive : {}),
            }}
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
            style={{
              ...styles.tabBtn,
              ...(activeTab === "params" ? styles.tabBtnActive : {}),
              ...(!hasOptuna ? styles.tabBtnDisabled : {}),
            }}
            title={hasOptuna ? "查看参数优化结果" : "该 run 无优化数据"}
          >
            参数优化
          </button>
        </div>
      </div>

      <div style={styles.tabContent}>
        <div
          key={`backtest-${animKey}`}
          id="panel-backtest"
          role="tabpanel"
          aria-labelledby="tab-backtest"
          style={activeTab === "backtest" ? styles.panelVisible : styles.panelHidden}
        >
          <div style={activeTab === "backtest" ? { animation: "tabFadeIn 0.25s ease-out" } : undefined}>
            <MetricCards run={run} backtests={backtests} />
            <div style={styles.contentGrid}>
              <div style={styles.leftPanel}>
                <KlineChart data={kline} loading={klineLoading} />
                {equity && selectedSymbol && equity[selectedSymbol] && (
                  <EquityChart data={equity[selectedSymbol]} />
                )}
              </div>
              <div style={styles.rightPanel}>
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
          style={activeTab === "params" ? styles.panelVisible : styles.panelHidden}
        >
          <div style={activeTab === "params" ? { animation: "tabFadeIn 0.25s ease-out" } : undefined}>
            {hasOptuna ? (
              <OptunaCharts data={optuna!} />
            ) : (
              <div style={styles.emptyPanel}>
                <p style={styles.emptyPanelText}>该 run 无优化数据</p>
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

const styles: Record<string, React.CSSProperties> = {
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: "28px",
    padding: "24px",
    background: "#ffffff",
    borderRadius: "12px",
    border: "1px solid #e2e8f0",
    flexWrap: "wrap" as const,
    gap: "16px",
  },
  headerLeft: {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
  },
  runBadge: {
    display: "flex",
    gap: "10px",
    alignItems: "center",
  },
  runId: {
    fontSize: "14px",
    fontWeight: 700,
    color: "#1a1a1a",
    fontFamily: "SF Mono, Monaco, Consolas, monospace",
  },
  statusPill: {
    fontSize: "11px",
    padding: "3px 10px",
    background: "#dcfce7",
    color: "#166534",
    borderRadius: "10px",
    fontWeight: 500,
  },
  title: {
    fontSize: "24px",
    fontWeight: 700,
    margin: 0,
    color: "#1a1a1a",
  },
  metaRow: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
    flexWrap: "wrap" as const,
  },
  metaItem: {
    display: "flex",
    alignItems: "center",
    gap: "4px",
    fontSize: "13px",
    color: "#64748b",
  },
  metaIcon: {
    fontSize: "14px",
  },
  metaDivider: {
    color: "#cbd5e1",
  },
  tabGroup: {
    display: "flex",
    background: "#f1f5f9",
    borderRadius: "8px",
    padding: "2px",
    flexShrink: 0,
  },
  tabBtn: {
    padding: "8px 18px",
    border: "none",
    background: "transparent",
    fontSize: "13px",
    fontWeight: 500,
    color: "#64748b",
    borderRadius: "6px",
    cursor: "pointer",
    outline: "none",
    transition: "all 0.2s ease",
    whiteSpace: "nowrap" as const,
  },
  tabBtnActive: {
    background: "#2563eb",
    color: "#ffffff",
    boxShadow: "0 2px 8px rgba(37, 99, 235, 0.3)",
  },
  tabBtnDisabled: {
    opacity: 0.45,
    cursor: "not-allowed",
  },
  tabContent: {
    position: "relative" as const,
  },
  panelVisible: {
    display: "block",
  },
  panelHidden: {
    display: "none",
  },
  emptyPanel: {
    background: "#ffffff",
    borderRadius: "12px",
    border: "1px solid #e2e8f0",
    padding: "60px 0",
    textAlign: "center" as const,
  },
  emptyPanelText: {
    color: "#94a3b8",
    fontSize: "14px",
    margin: 0,
  },
  contentGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 420px",
    gap: "28px",
  },
  leftPanel: {
    display: "flex",
    flexDirection: "column",
  },
  rightPanel: {
    display: "flex",
    flexDirection: "column",
    gap: "28px",
    height: "calc(100vh - 84px)",
    overflowY: "auto" as const,
    paddingRight: 4,
    // 量化终端风格细滚动条
    scrollbarWidth: "thin" as const,
    scrollbarColor: "#cbd5e1 transparent",
  },
  loadingContainer: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    padding: "80px",
    background: "#ffffff",
    borderRadius: "12px",
    border: "1px solid #e2e8f0",
  },
  loadingSpinner: {
    width: "40px",
    height: "40px",
    border: "4px solid #f1f5f9",
    borderTopColor: "#2563eb",
    borderRadius: "50%",
    animation: "spin 1s linear infinite",
  },
  loadingText: {
    marginTop: "16px",
    color: "#94a3b8",
    fontSize: "14px",
  },
};