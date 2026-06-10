import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { useFetchJson } from "@/hooks/useFetchJson";
import type {
  RunInfo,
  SummaryItem,
  BacktestRecord,
  KlineData,
  EquityData,
  OptunaData,
  RunLogs,
  TradesData,
} from "@/types";

export interface RunData {
  runId: number;
  run: RunInfo | null;
  summary: SummaryItem[] | null;
  backtests: BacktestRecord[] | null;
  equity: Record<string, EquityData> | null;
  optuna: OptunaData | null;
  runLogs: RunLogs | null;
  tradesData: TradesData | null;
  kline: KlineData | null;
  loading: boolean;
  hasOptuna: boolean;
  selectedSymbol: string;
  setSelectedSymbol: (s: string) => void;
  selectedInterval: string;
}

export function useRunData(): RunData {
  const { id } = useParams<{ id: string }>();
  const runId = Number(id);

  const [selectedSymbol, setSelectedSymbol] = useState<string>("");
  const [selectedInterval, setSelectedInterval] = useState<string>("");

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
  const { data: runLogs } = useFetchJson<RunLogs>("logs.json", runId);
  const { data: tradesData } = useFetchJson<TradesData>(
    "trades.json",
    runId
  );

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

  const loading = runLoading || summaryLoading || btLoading;
  const hasOptuna = Boolean(optuna && optuna.study_name);

  return {
    runId,
    run,
    summary,
    backtests,
    equity,
    optuna,
    runLogs,
    tradesData,
    kline,
    loading,
    hasOptuna,
    selectedSymbol,
    setSelectedSymbol,
    selectedInterval,
  };
}
