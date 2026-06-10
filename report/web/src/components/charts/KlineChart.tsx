import { useEffect, useState } from "react";
import type { KlineData, TradeRecord } from "@/types";
import QlPanel from "@/components/layout/QlPanel";
import KlineToolbar from "@/components/charts/KlineToolbar";
import KlineLegend from "@/components/charts/KlineLegend";
import { useKlineChart } from "@/hooks/useKlineChart";
import { ViewMode, IndicatorState } from "@/config/chartConfig";
import { convertToCandleData, convertToVolumeData, convertToBars } from "@/utils/indicators";
import { convertTradeToMarkers } from "@/utils/tradeMarkers";
import { qlIdNameMap } from "@/data/qlIdMapping";

interface KlineChartProps {
  data: KlineData | null;
  trades?: TradeRecord[] | null;
  loading?: boolean;
}

export default function KlineChart({ data, trades, loading }: KlineChartProps) {
  const [mode, setMode] = useState<ViewMode>("daily");
  const [indicators, setIndicators] = useState<IndicatorState>({
    sma: true,
    trades: true,
    macd: true,
    kdj: true,
  });

  const { containerRef, setKlineData, setIndicatorsVisibility } = useKlineChart();

  const klineData = data
    ? mode === "daily"
      ? data.daily
      : mode === "1m"
        ? data.raw
        : data.multi_timeframe?.[mode] ?? data.raw
    : null;

  useEffect(() => {
    if (!klineData || klineData.length === 0) return;

    const candles = convertToCandleData(klineData);
    const volumes = convertToVolumeData(klineData);
    const bars = convertToBars(klineData);

    const markerData = indicators.trades && trades
      ? convertTradeToMarkers(trades, klineData, mode)
      : [];

    setKlineData(candles, volumes, bars, markerData, indicators);
  }, [klineData, indicators, trades, mode, setKlineData]);

  useEffect(() => {
    setIndicatorsVisibility(indicators);
  }, [indicators, setIndicatorsVisibility]);

  if (loading) {
    return (
      <QlPanel qlId="RUN-KLINE-LOADING" name={qlIdNameMap["RUN-KLINE-LOADING"]} className="mb-7">
        <div className="flex flex-col items-center py-16">
          <div className="w-9 h-9 border-[3px] border-surface-alt border-t-primary rounded-full animate-spin" />
          <p className="mt-3 text-sm text-text-disabled">K 线数据加载中...</p>
        </div>
      </QlPanel>
    );
  }

  if (!data) {
    return (
      <QlPanel qlId="RUN-KLINE-EMPTY" name={qlIdNameMap["RUN-KLINE-EMPTY"]} className="mb-7">
        <p className="text-center text-text-disabled py-10">暂无 K 线数据</p>
      </QlPanel>
    );
  }

  if (!klineData || klineData.length === 0) {
    return (
      <QlPanel qlId="RUN-KLINE-EMPTY" name={qlIdNameMap["RUN-KLINE-EMPTY"]} className="mb-7">
        <p className="text-center text-text-disabled py-10">当前周期暂无 K 线数据，请切换周期</p>
      </QlPanel>
    );
  }

  return (
    <QlPanel
      qlId="RUN-KLINE-CONTAINER"
      name={qlIdNameMap["RUN-KLINE-CONTAINER"]}
      className="mb-7"
    >
      <KlineToolbar
        symbol={data.symbol}
        mode={mode}
        onModeChange={setMode}
        indicators={indicators}
        onIndicatorsChange={setIndicators}
        rawDownsampled={mode === "1m" ? data.raw_downsampled : false}
      />

      <div ref={containerRef} className="w-full h-[600px]" />

      <KlineLegend mode={mode} />
    </QlPanel>
  );
}