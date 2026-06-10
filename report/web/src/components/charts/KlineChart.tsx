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

  // 空状态/加载状态通过 overlay 显示，确保容器 div 始终在 DOM 中
  // 这样 useKlineChart 的 init effect 才能初始化图表实例
  const hasNoData = !data;
  const hasNoKline = data && (!klineData || klineData.length === 0);

  return (
    <QlPanel
      qlId="RUN-KLINE-CONTAINER"
      name={qlIdNameMap["RUN-KLINE-CONTAINER"]}
      className="mb-7"
    >
      <KlineToolbar
        symbol={data?.symbol ?? ""}
        mode={mode}
        onModeChange={setMode}
        indicators={indicators}
        onIndicatorsChange={setIndicators}
        rawDownsampled={mode === "1m" && data ? data.raw_downsampled : false}
      />

      <div className="relative w-full h-[600px]">
        <div ref={containerRef} className="absolute inset-0" />

        {loading && (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-white/90">
            <div className="w-9 h-9 border-[3px] border-surface-alt border-t-primary rounded-full animate-spin" />
            <p className="mt-3 text-sm text-text-disabled">K 线数据加载中...</p>
          </div>
        )}

        {!loading && hasNoData && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-white/90">
            <p className="text-text-disabled">暂无 K 线数据</p>
          </div>
        )}

        {!loading && hasNoKline && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-white/90">
            <p className="text-text-disabled">当前周期暂无 K 线数据，请切换周期</p>
          </div>
        )}
      </div>

      <KlineLegend mode={mode} />
    </QlPanel>
  );
}
