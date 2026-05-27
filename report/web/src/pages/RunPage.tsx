import { useState, useEffect } from "react";
import { useParams, Link, useLocation } from "react-router-dom";
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

export default function RunPage() {
  const { id } = useParams<{ id: string }>();
  const location = useLocation();
  const runId = Number(id);
  const showOptuna = location.pathname.includes("/optuna");

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

  useEffect(() => {
    if (summary && summary.length > 0 && !selectedSymbol) {
      setSelectedSymbol(summary[0].symbol);
    }
  }, [summary, selectedSymbol]);

  const { data: kline, loading: klineLoading } = useFetchJson<KlineData>(
    `kline_${selectedSymbol}.json`,
    runId
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
        {hasOptuna && (
          <div data-ql-id="RUN-PG-TABS" style={styles.headerRight}>
            <Link
              data-ql-id="RUN-PG-TAB-BACKTEST"
              to={showOptuna ? `/run/${runId}` : `/run/${runId}/optuna`}
              style={{
                ...styles.tabLink,
                ...(showOptuna ? styles.tabActive : {}),
              }}
            >
              回测结果
            </Link>
            <Link
              data-ql-id="RUN-PG-TAB-OPTUNA"
              to={showOptuna ? `/run/${runId}/optuna` : `/run/${runId}`}
              style={{
                ...styles.tabLink,
                ...(!showOptuna ? styles.tabActive : {}),
              }}
            >
              参数优化
            </Link>
          </div>
        )}
      </div>

      {showOptuna && optuna ? (
        <OptunaCharts data={optuna} />
      ) : (
        <>
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
        </>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: "24px",
    padding: "20px",
    background: "#ffffff",
    borderRadius: "12px",
    boxShadow: "0 4px 20px rgba(0, 0, 0, 0.08)",
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
    fontFamily: "Monaco, 'Courier New', monospace",
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
  },
  metaItem: {
    display: "flex",
    alignItems: "center",
    gap: "4px",
    fontSize: "13px",
    color: "#6b7280",
  },
  metaIcon: {
    fontSize: "14px",
  },
  metaDivider: {
    color: "#d1d5db",
  },
  headerRight: {
    display: "flex",
    background: "#f5f6fa",
    borderRadius: "8px",
    padding: "2px",
  },
  tabLink: {
    padding: "8px 18px",
    textDecoration: "none",
    fontSize: "13px",
    fontWeight: 500,
    color: "#6b7280",
    borderRadius: "6px",
    transition: "all 0.2s",
  },
  tabActive: {
    background: "#2563eb",
    color: "#ffffff",
    boxShadow: "0 2px 8px rgba(37, 99, 235, 0.3)",
  },
  contentGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 400px",
    gap: "20px",
  },
  leftPanel: {
    display: "flex",
    flexDirection: "column",
    gap: "20px",
  },
  rightPanel: {
    display: "flex",
    flexDirection: "column",
    gap: "20px",
    position: "sticky",
    top: "120px",
    maxHeight: "calc(100vh - 120px)",
    overflowY: "auto",
  },
  loadingContainer: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    padding: "80px",
    background: "#ffffff",
    borderRadius: "12px",
    boxShadow: "0 4px 20px rgba(0, 0, 0, 0.08)",
  },
  loadingSpinner: {
    width: "40px",
    height: "40px",
    border: "4px solid #f0f0f0",
    borderTopColor: "#2563eb",
    borderRadius: "50%",
    animation: "spin 1s linear infinite",
  },
  loadingText: {
    marginTop: "16px",
    color: "#9ca3af",
    fontSize: "14px",
  },
};