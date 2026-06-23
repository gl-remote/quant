import { SMA, MACD, Stochastic } from "lightweight-charts-indicators";
import type { Bar } from "oakscriptjs";
import { CandlestickData, HistogramData, Time } from "lightweight-charts";
import type { KlinePoint } from "@/types";
import { toChartTime } from "@/utils/chartTime";

/**
 * 将 KlinePoint 数组转换为 lightweight-charts 需要的 CandlestickData 格式。
 */
export function convertToCandleData(
  data: KlinePoint[],
): CandlestickData<Time>[] {
  return data.map((d) => ({
    time: toChartTime(d.datetime),
    open: d.open,
    high: d.high,
    low: d.low,
    close: d.close,
  }));
}

/**
 * 将 KlinePoint 数组转换为成交量数据。
 */
export function convertToVolumeData(
  data: KlinePoint[],
): HistogramData<Time>[] {
  return data.map((d) => ({
    time: toChartTime(d.datetime),
    value: d.volume,
    color: d.close >= d.open ? "rgba(38,166,154,0.5)" : "rgba(239,83,80,0.5)",
  }));
}

/**
 * 将 KlinePoint 数组转换为指标库需要的 Bar 格式。
 */
export function convertToBars(data: KlinePoint[]): Bar[] {
  return data.map((d) => ({
    time: toChartTime(d.datetime) as number,
    open: d.open,
    high: d.high,
    low: d.low,
    close: d.close,
    volume: d.volume,
  }));
}

/**
 * 计算 SMA（简单移动平均）指标。
 * @returns SMA 线数据，可直接用于 LineSeries.setData()
 */
export function calculateSMA(
  bars: Bar[],
  period: number,
): { time: Time; value: number }[] {
  const result = SMA.calculate(bars, { len: period, src: "close" });
  return result.plots.plot0;
}

/**
 * 计算 MACD 指标。
 * @returns { line: DIFF 线, signal: DEA 线, histogram: MACD 柱（带颜色）}
 */
export function calculateMACD(bars: Bar[]): {
  line: { time: Time; value: number | null }[];
  signal: { time: Time; value: number | null }[];
  histogram: { time: Time; value: number | null; color: string }[];
} {
  const result = MACD.calculate(bars, {
    fastLength: 12,
    slowLength: 26,
    signalLength: 9,
  });

  const histogram = result.plots.plot2.map((item) => ({
    ...item,
    color: (item.value ?? 0) >= 0 ? "rgba(38,166,154,0.7)" : "rgba(239,83,80,0.7)",
  }));

  return {
    line: result.plots.plot0,
    signal: result.plots.plot1,
    histogram,
  };
}

/**
 * 计算 KDJ 指标。
 * - K 线: Stochastic 的 %K
 * - D 线: Stochastic 的 %D
 * - J 线: 3*K - 2*D
 */
export function calculateKDJ(bars: Bar[]): {
  k: { time: Time; value: number | null }[];
  d: { time: Time; value: number | null }[];
  j: { time: Time; value: number | undefined }[];
} {
  const result = Stochastic.calculate(bars, { period: 9, smooth: 3 } as any);

  const kData = result.plots.plot0;
  const dData = result.plots.plot1;

  const jData = kData.map((item, idx) => {
    const kVal = kData[idx]?.value;
    const dVal = dData[idx]?.value;
    const jVal =
      kVal != null && dVal != null ? 3 * Number(kVal) - 2 * Number(dVal) : undefined;
    return { ...item, value: jVal };
  });

  return { k: kData, d: dData, j: jData };
}
