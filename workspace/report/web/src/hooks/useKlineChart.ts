import { useEffect, useRef } from "react";
import {
  createChart,
  IChartApi,
  ISeriesApi,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  createSeriesMarkers,
} from "lightweight-charts";
import {
  SMA as SMAImpl,
  MACD as MACDImpl,
  Stochastic as StochasticImpl,
} from "lightweight-charts-indicators";
import { buildChartOptions, CHART_COLORS, INDICATOR_PARAMS, IndicatorState } from "@/config/chartConfig";

/**
 * useKlineChart —— 封装 K 线图表的创建、初始化、更新和清理。
 *
 * 对外暴露一个 API 对象：
 *   - containerRef: 绑定到 DOM 容器
 *   - setKlineData(candles, volumes, bars, trades, markers): 更新所有数据
 *   - setIndicatorsVisibility(indicators): 切换指标显示/隐藏
 *
 * 图表实例创建后复用，不会因为数据更新而重建。
 */

export interface KlineChartApi {
  containerRef: React.RefObject<HTMLDivElement>;
  setKlineData: (
    candles: { time: any; open: number; high: number; low: number; close: number }[],
    volumes: { time: any; value: number; color?: string }[],
    bars: any[],
    trades: any[],
    indicators: IndicatorState,
  ) => void;
  setIndicatorsVisibility: (indicators: IndicatorState) => void;
}

export function useKlineChart(): KlineChartApi {
  const containerRef = useRef<HTMLDivElement>(null);

  // chartRef 是主图表引用，其他 series refs 通过闭包引用
  const chartRef = useRef<IChartApi | null>(null);
  const candlestickSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const smaShortSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const smaLongSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const macdLineRef = useRef<ISeriesApi<"Line"> | null>(null);
  const macdSignalRef = useRef<ISeriesApi<"Line"> | null>(null);
  const macdHistogramRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const kdjKRef = useRef<ISeriesApi<"Line"> | null>(null);
  const kdjDRef = useRef<ISeriesApi<"Line"> | null>(null);
  const kdjJRef = useRef<ISeriesApi<"Line"> | null>(null);
  const markersRef = useRef<any>(null);

  // 预制数据时序问题：window.__DATA__ 同步预加载时 setKlineData 可能
  // 在 chart 初始化之前被调用，存入此 ref 等 init 完成后自动应用。
  const pendingArgsRef = useRef<Parameters<KlineChartApi["setKlineData"]> | null>(null);

  // 确保图表初始化一次
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    if (chartRef.current) return;

    // 如果容器在初始化时处于隐藏状态（display:none），clientWidth 可能为 0
    // 先尝试获取实际宽度，兜底使用默认值
    const initWidth = container.clientWidth > 0 ? container.clientWidth : 800;
    const chart = createChart(container, buildChartOptions(initWidth));

    // ── Pane 0: 主图（蜡烛 + 成交量 + SMA） ──────────────────────
    const candlestickSeries = chart.addSeries(
      CandlestickSeries,
      {
        upColor: CHART_COLORS.upCandle,
        downColor: CHART_COLORS.downCandle,
        borderUpColor: CHART_COLORS.upCandle,
        borderDownColor: CHART_COLORS.downCandle,
        wickUpColor: CHART_COLORS.upCandle,
        wickDownColor: CHART_COLORS.downCandle,
      },
      0,
    );

    const volumeSeries = chart.addSeries(
      HistogramSeries,
      {
        color: CHART_COLORS.upCandle,
        priceFormat: { type: "volume" },
        priceScaleId: "",
      },
      0,
    );
    volumeSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 },
    });

    const smaShortSeries = chart.addSeries(
      LineSeries,
      { color: CHART_COLORS.smaShort, lineWidth: 2 },
      0,
    );
    const smaLongSeries = chart.addSeries(
      LineSeries,
      { color: CHART_COLORS.smaLong, lineWidth: 2 },
      0,
    );

    // ── Pane 1: MACD ─────────────────────────────────────────────
    const macdLine = chart.addSeries(
      LineSeries,
      { color: CHART_COLORS.smaShort, lineWidth: 1 },
      1,
    );
    macdLine.createPriceLine({ price: 0, color: "#999", lineStyle: 2, axisLabelVisible: true });

    const macdSignal = chart.addSeries(
      LineSeries,
      { color: CHART_COLORS.smaLong, lineWidth: 1 },
      1,
    );

    const macdHistogram = chart.addSeries(
      HistogramSeries,
      { priceFormat: { type: "price" } },
      1,
    );

    // ── Pane 2: KDJ ─────────────────────────────────────────────
    const kdjK = chart.addSeries(
      LineSeries,
      { color: CHART_COLORS.smaShort, lineWidth: 1 },
      2,
    );
    kdjK.createPriceLine({ price: 50, color: "#999", lineStyle: 2, axisLabelVisible: true });

    const kdjD = chart.addSeries(
      LineSeries,
      { color: CHART_COLORS.smaLong, lineWidth: 1 },
      2,
    );

    const kdjJ = chart.addSeries(
      LineSeries,
      { color: CHART_COLORS.tradeBoth, lineWidth: 1 },
      2,
    );

    const markers = createSeriesMarkers(candlestickSeries);

    // 保存所有引用
    candlestickSeriesRef.current = candlestickSeries;
    volumeSeriesRef.current = volumeSeries;
    smaShortSeriesRef.current = smaShortSeries;
    smaLongSeriesRef.current = smaLongSeries;
    macdLineRef.current = macdLine;
    macdSignalRef.current = macdSignal;
    macdHistogramRef.current = macdHistogram;
    kdjKRef.current = kdjK;
    kdjDRef.current = kdjD;
    kdjJRef.current = kdjJ;
    markersRef.current = markers;
    chartRef.current = chart;

    // 预加载数据可能先于 chart 初始化到达，此处应用缓存的待处理数据
    if (pendingArgsRef.current) {
      _applyKlineData(...pendingArgsRef.current);
      pendingArgsRef.current = null;
    }

    // 用 ResizeObserver 替代 window.resize，更精确地监听容器尺寸变化
    // 尤其重要：当容器从 display:none 变为可见时，ResizeObserver 会触发
    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0) {
          chart.applyOptions({ width, height: 600 });
        }
      }
    });
    resizeObserver.observe(container);

    // 兜底：window resize 时也触发 resize（确保跨 tab 切换后尺寸正确）
    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
      markersRef.current = null;
    };
  }, []);

  // ─── 内部：实际应用数据到图表 ────────────────────────────────────

  const _applyKlineData = (
    candles: Parameters<KlineChartApi["setKlineData"]>[0],
    volumes: Parameters<KlineChartApi["setKlineData"]>[1],
    bars: Parameters<KlineChartApi["setKlineData"]>[2],
    trades: Parameters<KlineChartApi["setKlineData"]>[3],
    indicators: Parameters<KlineChartApi["setKlineData"]>[4],
  ) => {
    candlestickSeriesRef.current!.setData(candles);
    volumeSeriesRef.current!.setData(volumes);

    if (indicators.sma && smaShortSeriesRef.current && smaLongSeriesRef.current) {
      const shortResult = SMAImpl.calculate(bars, {
        len: INDICATOR_PARAMS.smaShort,
        src: "close",
      });
      const longResult = SMAImpl.calculate(bars, {
        len: INDICATOR_PARAMS.smaLong,
        src: "close",
      });
      smaShortSeriesRef.current.setData(shortResult.plots.plot0);
      smaLongSeriesRef.current.setData(longResult.plots.plot0);
    }

    if (
      indicators.macd &&
      macdLineRef.current &&
      macdSignalRef.current &&
      macdHistogramRef.current
    ) {
      const macdResult = MACDImpl.calculate(bars, {
        fastLength: INDICATOR_PARAMS.macdFast,
        slowLength: INDICATOR_PARAMS.macdSlow,
        signalLength: INDICATOR_PARAMS.macdSignal,
      });

      const histogram = macdResult.plots.plot2.map((item: any) => ({
        ...item,
        color: (item.value ?? 0) >= 0 ? "rgba(38,166,154,0.7)" : "rgba(239,83,80,0.7)",
      }));

      macdLineRef.current.setData(macdResult.plots.plot0);
      macdSignalRef.current.setData(macdResult.plots.plot1);
      macdHistogramRef.current.setData(histogram);
    }

    if (indicators.kdj && kdjKRef.current && kdjDRef.current && kdjJRef.current) {
      const kdjResult = StochasticImpl.calculate(bars, {
        period: INDICATOR_PARAMS.kdjPeriod,
        smooth: INDICATOR_PARAMS.kdjSmooth,
      } as any);

      const kData = kdjResult.plots.plot0;
      const dData = kdjResult.plots.plot1;
      const jData = kData.map((item: any, idx: number) => {
        const kVal = kData[idx]?.value;
        const dVal = dData[idx]?.value;
        const jVal =
          kVal != null && dVal != null ? 3 * Number(kVal) - 2 * Number(dVal) : undefined;
        return { ...item, value: jVal };
      });

      kdjKRef.current.setData(kData);
      kdjDRef.current.setData(dData);
      kdjJRef.current.setData(jData);
    }

    if (markersRef.current) {
      markersRef.current.setMarkers(trades);
    }
  };

  // ─── 对外 API ─────────────────────────────────────────────────

  const setKlineData: KlineChartApi["setKlineData"] = (
    candles,
    volumes,
    bars,
    trades,
    indicators,
  ) => {
    if (!candlestickSeriesRef.current || !volumeSeriesRef.current) {
      // 图表尚未初始化（预加载数据先到达），暂存等 init 完成后自动应用
      pendingArgsRef.current = [candles, volumes, bars, trades, indicators];
      return;
    }

    _applyKlineData(candles, volumes, bars, trades, indicators);
  };

  const setIndicatorsVisibility: KlineChartApi["setIndicatorsVisibility"] = (indicators) => {
    if (smaShortSeriesRef.current && smaLongSeriesRef.current) {
      smaShortSeriesRef.current.applyOptions({ visible: indicators.sma });
      smaLongSeriesRef.current.applyOptions({ visible: indicators.sma });
    }
    if (macdLineRef.current && macdSignalRef.current && macdHistogramRef.current) {
      macdLineRef.current.applyOptions({ visible: indicators.macd });
      macdSignalRef.current.applyOptions({ visible: indicators.macd });
      macdHistogramRef.current.applyOptions({ visible: indicators.macd });
    }
    if (kdjKRef.current && kdjDRef.current && kdjJRef.current) {
      kdjKRef.current.applyOptions({ visible: indicators.kdj });
      kdjDRef.current.applyOptions({ visible: indicators.kdj });
      kdjJRef.current.applyOptions({ visible: indicators.kdj });
    }
  };

  return { containerRef, setKlineData, setIndicatorsVisibility };
}
