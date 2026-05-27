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

  const { data: kline } = useFetchJson<KlineData>(
    `kline_${selectedSymbol}.json`,
    runId
  );

  const loading = runLoading || summaryLoading || btLoading;
  if (loading) {
    return (
      <p style={{ textAlign: "center", padding: 60, color: "#888" }}>
        加载中...
      </p>
    );
  }

  const hasOptuna = optuna && optuna.study_name;

  return (
    <div>
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>
            r{runId} — {run?.strategy || "加载中"}
          </h1>
          <span style={styles.sub}>
            {run?.engine} | {run?.symbols} 品种 | {run?.created_at}
          </span>
        </div>
        {hasOptuna && (
          <Link
            to={showOptuna ? `/run/${runId}` : `/run/${runId}/optuna`}
            style={styles.optunaLink}
          >
            {showOptuna ? "回测结果" : "参数优化"}
          </Link>
        )}
      </div>

      {showOptuna && optuna ? (
        <OptunaCharts data={optuna} />
      ) : (
        <>
          <MetricCards run={run} backtests={backtests} />
          <SymbolTable
            data={summary}
            onSelect={setSelectedSymbol}
            selectedSymbol={selectedSymbol}
          />
          {kline && <KlineChart data={kline} />}
          {equity && selectedSymbol && equity[selectedSymbol] && (
            <EquityChart data={equity[selectedSymbol]} />
          )}
          <BacktestDetail
            backtests={backtests}
            selectedSymbol={selectedSymbol}
          />
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
    marginBottom: "20px",
  },
  title: {
    fontSize: "22px",
    fontWeight: 700,
    margin: 0,
    color: "#222",
  },
  sub: {
    fontSize: "12px",
    color: "#999",
  },
  optunaLink: {
    padding: "6px 16px",
    background: "#2563eb",
    color: "#fff",
    borderRadius: "6px",
    textDecoration: "none",
    fontSize: "13px",
    fontWeight: 600,
  },
};