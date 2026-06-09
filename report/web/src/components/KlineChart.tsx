import { useEffect, useRef, useState } from "react";
import {
  createChart,
  IChartApi,
  ISeriesApi,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  CandlestickData,
  HistogramData,
  Time,
  TickMarkType,
  createSeriesMarkers,
} from "lightweight-charts";
import type { KlineData, KlinePoint, TradeRecord } from "@/types";
import QlPanel from "@/components/QlPanel";
import { qlIdNameMap } from "@/data/qlIdMapping";
import { SMA, MACD, Stochastic } from "lightweight-charts-indicators";
import type { Bar } from "oakscriptjs";

type ViewMode = "daily" | "1m" | "5m" | "15m" | "1h";

interface Props {
  data: KlineData | null;
  trades?: TradeRecord[] | null;
  loading?: boolean;
}

function toChartTime(dt: string | number): Time {
  if (typeof dt === "number") {
    return dt as Time;
  }
  if (!isNaN(Number(dt))) {
    return Number(dt) as Time;
  }
  if (dt.includes(" ")) {
    return (new Date(dt.replace(" ", "T") + "Z").getTime() / 1000) as Time;
  }
  if (dt.includes("T")) {
    return (new Date(dt + "Z").getTime() / 1000) as Time;
  }
  return dt as Time;
}

function convertToCandleData(data: KlinePoint[]): CandlestickData<Time>[] {
  return data.map((d) => ({
    time: toChartTime(d.datetime),
    open: d.open,
    high: d.high,
    low: d.low,
    close: d.close,
  }));
}



function convertTradeToMarkers(
  trades: TradeRecord[],
  klineData: KlinePoint[],
  currentMode: ViewMode,
): any[] {
  if (!trades || trades.length === 0 || !klineData || klineData.length === 0) {
    return [];
  }

  // 日线不展示买卖点
  if (currentMode === "daily") return [];

  // 将 klineData 按 datetime 排序，用于二分查找归属K线
  const sortedKlines = [...klineData].sort((a, b) => Number(a.datetime) - Number(b.datetime));
  const klineTimes = sortedKlines.map(k => Number(k.datetime));

  // 将交易时间归一化到所属K线的时间戳
  function mapTradeToKlineTime(tradeTimestamp: number): number | null {
    let lo = 0, hi = klineTimes.length - 1;
    let result = -1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (klineTimes[mid] <= tradeTimestamp) {
        result = mid;
        lo = mid + 1;
      } else {
        hi = mid - 1;
      }
    }
    if (result === -1) return null;
    return klineTimes[result];
  }

  // 1m 使用原来的详细标注（多开/空开/空平/多平）
  if (currentMode === "1m") {
    const markers: any[] = [];
    for (const trade of trades) {
      let tradeTimestamp: number;
      if (typeof trade.datetime === "number") {
        tradeTimestamp = trade.datetime;
      } else if (trade.datetime.includes(" ")) {
        tradeTimestamp = new Date(trade.datetime.replace(" ", "T")).getTime() / 1000;
      } else if (trade.datetime.includes("T")) {
        tradeTimestamp = new Date(trade.datetime).getTime() / 1000;
      } else {
        tradeTimestamp = Number(trade.datetime);
      }

      const klineTime = mapTradeToKlineTime(tradeTimestamp);
      if (klineTime === null) continue;

      let position: "aboveBar" | "belowBar";
      let color: string;
      let shape: "arrowUp" | "arrowDown";
      let text: string;

      if (trade.offset === "open") {
        if (trade.direction === "long") {
          position = "belowBar"; color = "#26A69A"; shape = "arrowUp"; text = "多开";
        } else {
          position = "aboveBar"; color = "#EF5350"; shape = "arrowDown"; text = "空开";
        }
      } else {
        if (trade.direction === "long") {
          position = "belowBar"; color = "#26A69A"; shape = "arrowUp"; text = "空平";
        } else {
          position = "aboveBar"; color = "#EF5350"; shape = "arrowDown"; text = "多平";
        }
      }

      markers.push({ time: klineTime as Time, position, color, shape, text });
    }
    return markers;
  }

  // 5m/15m/1h 使用聚合标记
  const tradeByKline: Map<number, { buy: number; sell: number }> = new Map();

  for (const trade of trades) {
    let tradeTimestamp: number;
    if (typeof trade.datetime === "number") {
      tradeTimestamp = trade.datetime;
    } else if (trade.datetime.includes(" ")) {
      tradeTimestamp = new Date(trade.datetime.replace(" ", "T")).getTime() / 1000;
    } else if (trade.datetime.includes("T")) {
      tradeTimestamp = new Date(trade.datetime).getTime() / 1000;
    } else {
      tradeTimestamp = Number(trade.datetime);
    }

    const klineTime = mapTradeToKlineTime(tradeTimestamp);
    if (klineTime === null) continue;

    if (!tradeByKline.has(klineTime)) {
      tradeByKline.set(klineTime, { buy: 0, sell: 0 });
    }
    const entry = tradeByKline.get(klineTime)!;

    if (trade.direction === "long") {
      entry.buy += 1;
    } else {
      entry.sell += 1;
    }
  }

  const markers: any[] = [];

  for (const [klineTime, counts] of tradeByKline.entries()) {
    const { buy, sell } = counts;

    if (buy > 0 && sell > 0) {
      markers.push({
        time: klineTime as Time,
        position: "belowBar",
        color: "#FF9800",
        shape: "arrowUp",
        text: "T",
      });
    } else if (buy > 0) {
      markers.push({
        time: klineTime as Time,
        position: "belowBar",
        color: "#26A69A",
        shape: "arrowUp",
        text: "多",
      });
    } else if (sell > 0) {
      markers.push({
        time: klineTime as Time,
        position: "aboveBar",
        color: "#EF5350",
        shape: "arrowDown",
        text: "空",
      });
    }
  }

  return markers;
}

export default function KlineChart({ data, trades, loading }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candlestickSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const smaShortSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const smaLongSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const markersRef = useRef<any>(null);
  
  // MACD refs
  const macdLineRef = useRef<ISeriesApi<"Line"> | null>(null);
  const macdSignalRef = useRef<ISeriesApi<"Line"> | null>(null);
  const macdHistogramRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  
  // KDJ refs
  const kdjKRef = useRef<ISeriesApi<"Line"> | null>(null);
  const kdjDRef = useRef<ISeriesApi<"Line"> | null>(null);
  const kdjJRef = useRef<ISeriesApi<"Line"> | null>(null);
  
  // PriceLine refs
  const macdZeroPriceLineRef = useRef<any>(null);
  const kdjFiftyPriceLineRef = useRef<any>(null);
  
  const [mode, setMode] = useState<ViewMode>("daily");
  const [indicators, setIndicators] = useState<{ 
    sma: boolean; 
    trades: boolean; 
    macd: boolean; 
    kdj: boolean 
  }>({
    sma: true,
    trades: true,
    macd: true,
    kdj: true,
  });

  const klineData = data
    ? mode === "daily"
      ? data.daily
      : mode === "1m"
        ? data.raw
        : data.multi_timeframe?.[mode] ?? data.raw
    : null;

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    
    const hideLogo = () => {
      const logoElements = container.querySelectorAll('a[href*="tradingview.com"], a[href*="lightweight-charts.com"]');
      logoElements.forEach(el => {
        (el as HTMLElement).style.display = 'none';
      });
      
      const allElements = container.querySelectorAll('*');
      allElements.forEach(el => {
        const htmlEl = el as HTMLElement;
        if (htmlEl.style.position === 'absolute' && 
            (htmlEl.style.bottom === '0px' || htmlEl.style.bottom === '0')) {
          htmlEl.style.display = 'none';
        }
      });
    };
    
    hideLogo();
    
    const observer = new MutationObserver(hideLogo);
    observer.observe(container, { childList: true, subtree: true });
    
    return () => observer.disconnect();
  }, [klineData]);

  useEffect(() => {
    if (!klineData) return;
    const container = containerRef.current;
    if (!container) {
      return;
    }
    if (chartRef.current) {
      return;
    }

    const chart = createChart(container, {
      layout: {
        background: { color: "#ffffff" },
        textColor: "#333",
        panes: {
          separatorColor: "#e0e0e0",
        },
      },
      grid: {
        vertLines: { color: "#f0f0f0" },
        horzLines: { color: "#f0f0f0" },
      },
      width: container.clientWidth,
      height: 600,
      crosshair: {
        mode: 1, // CrosshairMode.Magnet
        vertLine: {
          width: 1,
          color: "rgba(180, 180, 180, 0.5)",
          style: 3,
          visible: true,
        },
        horzLine: {
          width: 1,
          color: "rgba(180, 180, 180, 0.5)",
          style: 3,
          visible: true,
        },
      },
      rightPriceScale: {
        borderColor: "#e0e0e0",
      },
      timeScale: {
        borderColor: "#e0e0e0",
        timeVisible: true,
        secondsVisible: false,
        tickMarkFormatter: (time: Time, tickMarkType: TickMarkType, _locale: string) => {
          if (typeof time !== "number") return null;
          const d = new Date(time * 1000);
          const pad = (n: number) => String(n).padStart(2, "0");
          switch (tickMarkType) {
            case TickMarkType.Year:
              return String(d.getFullYear());
            case TickMarkType.Month:
              return `${d.getFullYear()}/${pad(d.getMonth() + 1)}`;
            case TickMarkType.DayOfMonth:
              return `${pad(d.getMonth() + 1)}/${pad(d.getDate())}`;
            case TickMarkType.Time:
              return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
            case TickMarkType.TimeWithSeconds:
              return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
          }
          return null;
        },
      },
      localization: {
        locale: "zh-CN",
        timeFormatter: (time: Time) => {
          if (typeof time !== "number") return String(time);
          const d = new Date(time * 1000);
          const pad = (n: number) => String(n).padStart(2, "0");
          return `${d.getFullYear()}/${pad(d.getMonth() + 1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
        },
      },
    });

    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#26A69A",
      downColor: "#EF5350",
      borderUpColor: "#26A69A",
      borderDownColor: "#EF5350",
      wickUpColor: "#26A69A",
      wickDownColor: "#EF5350",
    }, 0);

    const volumeSeries = chart.addSeries(HistogramSeries, {
      color: "#26A69A",
      priceFormat: {
        type: "volume",
      },
      priceScaleId: "",
    }, 0);

    const smaShortSeries = chart.addSeries(LineSeries, {
      color: "#FF6B6B",
      lineWidth: 2,
    }, 0);

    const smaLongSeries = chart.addSeries(LineSeries, {
      color: "#4ECDC4",
      lineWidth: 2,
    }, 0);

    // MACD series - pane 1
    const macdLine = chart.addSeries(LineSeries, {
      color: "#FF6B6B",
      lineWidth: 1,
    }, 1);
    
    // MACD DIFF 线创建 0 轴
    macdZeroPriceLineRef.current = macdLine.createPriceLine({
      price: 0,
      color: "#999",
      lineStyle: 2,
      axisLabelVisible: true,
    });
    
    const macdSignal = chart.addSeries(LineSeries, {
      color: "#4ECDC4",
      lineWidth: 1,
    }, 1);
    
    const macdHistogram = chart.addSeries(HistogramSeries, {
      priceFormat: {
        type: "price",
      },
    }, 1);

    // KDJ series - pane 2
    const kdjK = chart.addSeries(LineSeries, {
      color: "#FF6B6B",
      lineWidth: 1,
    }, 2);
    
    // KDJ K 线序列实例上创建 50 线
    kdjFiftyPriceLineRef.current = kdjK.createPriceLine({
      price: 50,
      color: "#999",
      lineStyle: 2,
      axisLabelVisible: true,
    });
    
    const kdjD = chart.addSeries(LineSeries, {
      color: "#4ECDC4",
      lineWidth: 1,
    }, 2);
    
    const kdjJ = chart.addSeries(LineSeries, {
      color: "#FFA500",
      lineWidth: 1,
    }, 2);

    const markers = createSeriesMarkers(candlestickSeries);

    volumeSeries.priceScale().applyOptions({
      scaleMargins: {
        top: 0.85,
        bottom: 0,
      },
    });

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

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({
          width: containerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      chartRef.current = null;
      markersRef.current = null;
    };
  }, [klineData]);

  useEffect(() => {
    if (!klineData) return;
    const candleSeries = candlestickSeriesRef.current;
    const volSeries = volumeSeriesRef.current;
    const markers = markersRef.current;
    if (!candleSeries || !volSeries) return;

    const candleData = convertToCandleData(klineData);
    candleSeries.setData(candleData);

    const volumeData: HistogramData<Time>[] = klineData.map((d) => ({
      time: toChartTime(d.datetime),
      value: d.volume,
      color: d.close >= d.open ? "rgba(38,166,154,0.5)" : "rgba(239,83,80,0.5)",
    }));
    volSeries.setData(volumeData);

    // Convert to Bar[] for lightweight-charts-indicators
    const bars: Bar[] = klineData.map((d) => ({
      time: toChartTime(d.datetime) as number,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
      volume: d.volume,
    }));

    if (indicators.sma && smaShortSeriesRef.current && smaLongSeriesRef.current) {
      const smaShortResult = SMA.calculate(bars, { len: 5, src: "close" });
      const smaLongResult = SMA.calculate(bars, { len: 60, src: "close" });

      smaShortSeriesRef.current.setData(smaShortResult.plots.plot0);
      smaLongSeriesRef.current.setData(smaLongResult.plots.plot0);
    }

    // MACD
    if (
      indicators.macd && 
      macdLineRef.current && 
      macdSignalRef.current && 
      macdHistogramRef.current
    ) {
      const macdResult = MACD.calculate(bars, { 
        fastLength: 12, 
        slowLength: 26, 
        signalLength: 9 
      });
      
      // 自定义 MACD histogram 的颜色
      const histogramData = macdResult.plots.plot2.map((item) => ({
        ...item,
        color: (item.value ?? 0) >= 0 
          ? "rgba(38,166,154,0.7)" 
          : "rgba(239,83,80,0.7)",
      }));
      
      macdLineRef.current.setData(macdResult.plots.plot0);
      macdSignalRef.current.setData(macdResult.plots.plot1);
      macdHistogramRef.current.setData(histogramData);
    }

    // KDJ (Stochastic)
    if (
      indicators.kdj && 
      kdjKRef.current && 
      kdjDRef.current && 
      kdjJRef.current
    ) {
      const stochasticResult = Stochastic.calculate(bars, { 
        period: 9, 
        smooth: 3 
      } as any);
      
      // Stochastic 默认给出 K 和 D，J = 3K - 2D
      const kData = stochasticResult.plots.plot0;
      const dData = stochasticResult.plots.plot1;
      const jData = kData.map((item, idx) => {
        const kVal = kData[idx]?.value;
        const dVal = dData[idx]?.value;
        const jVal = (kVal != null && dVal != null) ? 3 * Number(kVal) - 2 * Number(dVal) : undefined;
        return {
          ...item,
          value: jVal,
        };
      });
      
      kdjKRef.current.setData(kData);
      kdjDRef.current.setData(dData);
      kdjJRef.current.setData(jData);
    }

    if (markers) {
      console.log("[KlineChart-DEBUG] trades 传入:", trades ? `${trades.length}条` : "null");
      console.log("[KlineChart-DEBUG] indicators.trades:", indicators.trades);
      console.log("[KlineChart-DEBUG] mode:", mode, "(raw=分钟线, daily=日线)");
      if (trades && trades.length > 0) {
        console.log("[KlineChart-DEBUG] trades 前3条样本:", trades.slice(0, 3).map(t => ({ datetime: t.datetime, direction: t.direction, offset: t.offset })));
      // 验证：交易时间解析后的数值 vs K线时间戳是否一致
      if (trades.length > 0) {
        const sample = trades[0];
        let ts: number;
        if (typeof sample.datetime === "number") {
          ts = sample.datetime;
        } else if (sample.datetime.includes(" ")) {
          ts = new Date(sample.datetime.replace(" ", "T")).getTime() / 1000;
        } else {
          ts = new Date(sample.datetime).getTime() / 1000;
        }
        const tsDate = new Date(ts * 1000);
        console.log("[KlineChart-DEBUG] ⚠️ 时区验证 - trades[0]:", sample.datetime);
        console.log("[KlineChart-DEBUG] ⚠️ 时区验证 - 解析后时间戳:", ts, "→ UTC:", tsDate.toISOString(), "→ 本地时间:", tsDate.toLocaleString());
        console.log("[KlineChart-DEBUG] ⚠️ 时区验证 - K线首根时间戳:", klineData[0]?.datetime, "→ 对应时间:", new Date(Number(klineData[0].datetime) * 1000).toISOString());
        console.log("[KlineChart-DEBUG] ⚠️ 时区验证 - 差值(秒):", ts - Number(klineData[0].datetime));
      }
      }
      if (klineData && klineData.length > 0) {
        console.log("[KlineChart-DEBUG] klineData(raw) 前3条 datetime:", klineData.slice(0, 3).map(k => k.datetime));
        console.log("[KlineChart-DEBUG] klineData(raw) 后3条 datetime:", klineData.slice(-3).map(k => k.datetime));
      }
      if (indicators.trades && trades) {
        const markerData = convertTradeToMarkers(trades, klineData, mode);
        console.log("[KlineChart-DEBUG] convertTradeToMarkers 结果:", markerData.length, "个", markerData.length > 0 ? "样本:" + JSON.stringify(markerData.slice(0, 2)) : "");
        markers.setMarkers(markerData);
      } else {
        console.log("[KlineChart-DEBUG] 跳过标记设置: indicators.trades=", indicators.trades, "trades=", !!trades);
        markers.setMarkers([]);
      }
    } else {
      console.log("[KlineChart-DEBUG] markers ref 未初始化");
    }
  }, [klineData, indicators, trades, mode]);

  useEffect(() => {
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
  }, [indicators]);

  if (loading) {
    return (
      <QlPanel qlId="RUN-KLINE-LOADING" name={qlIdNameMap["RUN-KLINE-LOADING"]} style={{ marginBottom: 28 }}>
        <style>{`@keyframes ql-spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}`}</style>
        <div className="flex flex-col items-center py-16">
          <div className="w-9 h-9 border-[3px] border-slate-100 border-t-blue-600 rounded-full animate-[ql-spin_0.8s_linear_infinite]" />
          <p className="mt-3 text-sm text-slate-400">K 线数据加载中...</p>
        </div>
      </QlPanel>
    );
  }

  if (!data) {
    return (
      <QlPanel qlId="RUN-KLINE-EMPTY" name={qlIdNameMap["RUN-KLINE-EMPTY"]} style={{ marginBottom: 28 }}>
        <p className="text-center text-slate-400 py-10">暂无 K 线数据</p>
      </QlPanel>
    );
  }

  if (!klineData || klineData.length === 0) {
    return (
      <QlPanel qlId="RUN-KLINE-EMPTY" name={qlIdNameMap["RUN-KLINE-EMPTY"]} style={{ marginBottom: 28 }}>
        <p className="text-center text-slate-400 py-10">当前周期暂无 K 线数据，请切换周期</p>
      </QlPanel>
    );
  }

  const btnBase = "px-4 py-1.5 text-[13px] font-medium border-none bg-transparent cursor-pointer rounded-md transition-all";
  const toggleBtn = `${btnBase} text-slate-500`;
  const toggleActive = `${btnBase} bg-blue-800 text-slate-900 shadow-md shadow-blue-800/30`;

  const toolbar = (
    <div className="flex justify-between items-center mb-4 pb-3 border-b border-slate-100" data-ql-id="RUN-KLINE-TOOLBAR">
      <div className="flex items-center gap-2">
        <span className="text-lg font-bold text-slate-900 font-mono">{data.symbol}</span>
        {mode === "1m" && data.raw_downsampled && (
          <span className="text-[11px] px-2 py-0.5 bg-amber-50 text-amber-800 rounded">抽样显示</span>
        )}
      </div>
      <div className="flex items-center">
        <div className="flex bg-slate-100 rounded-lg p-0.5">
          {(["daily", "1h", "15m", "5m", "1m"] as ViewMode[]).map((vm) => (
            <button
              key={vm}
              onClick={() => setMode(vm)}
              data-ql-id={`RUN-KLINE-BTN-${vm.toUpperCase()}`}
              className={mode === vm ? toggleActive : toggleBtn}
            >
              {vm === "daily" ? "日线" : vm === "1m" ? "1分钟" : vm}
            </button>
          ))}
        </div>
      </div>
      <div className="flex gap-2">
        <button
          onClick={() => setIndicators((prev) => ({ ...prev, sma: !prev.sma }))}
          data-ql-id="RUN-KLINE-BTN-SMA"
          className={`px-3.5 py-1.5 text-xs cursor-pointer rounded-md transition-all border ${
            indicators.sma
              ? "bg-green-50 border-green-300 text-green-700"
              : "bg-white border-slate-200 text-slate-500"
          }`}
        >
          SMA 均线
        </button>
        <button
          onClick={() => setIndicators((prev) => ({ ...prev, macd: !prev.macd }))}
          data-ql-id="RUN-KLINE-BTN-MACD"
          className={`px-3.5 py-1.5 text-xs cursor-pointer rounded-md transition-all border ${
            indicators.macd
              ? "bg-purple-50 border-purple-300 text-purple-700"
              : "bg-white border-slate-200 text-slate-500"
          }`}
        >
          MACD
        </button>
        <button
          onClick={() => setIndicators((prev) => ({ ...prev, kdj: !prev.kdj }))}
          data-ql-id="RUN-KLINE-BTN-KDJ"
          className={`px-3.5 py-1.5 text-xs cursor-pointer rounded-md transition-all border ${
            indicators.kdj
              ? "bg-orange-50 border-orange-300 text-orange-700"
              : "bg-white border-slate-200 text-slate-500"
          }`}
        >
          KDJ
        </button>
        <button
          onClick={() => setIndicators((prev) => ({ ...prev, trades: !prev.trades }))}
          data-ql-id="RUN-KLINE-BTN-TRADES"
          className={`px-3.5 py-1.5 text-xs cursor-pointer rounded-md transition-all border ${
            indicators.trades
              ? "bg-blue-50 border-blue-300 text-blue-700"
              : "bg-white border-slate-200 text-slate-500"
          }`}
        >
          交易标记
        </button>
      </div>
    </div>
  );

  return (
    <QlPanel
      qlId="RUN-KLINE-CONTAINER"
      name={qlIdNameMap["RUN-KLINE-CONTAINER"]}
      style={{ marginBottom: 28 }}
    >
      {toolbar}
      <div
        ref={containerRef}
        className="w-full h-[600px]"
        data-ql-id="RUN-KLINE-CHART"
      />
      <div className="flex justify-center gap-6 mt-3 pt-3 border-t border-slate-100">
        <div className="flex items-center gap-1.5 text-xs text-slate-500">
          <span className="w-2 h-2 rounded-full bg-[#FF6B6B]" />
          <span>SMA(5)</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-slate-500">
          <span className="w-2 h-2 rounded-full bg-[#4ECDC4]" />
          <span>SMA(60)</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-slate-500">
          <span className="w-2 h-2 rounded-full bg-[#26A69A]" />
          <span>阳线</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-slate-500">
          <span className="w-2 h-2 rounded-full bg-[#EF5350]" />
          <span>阴线</span>
        </div>
        {mode === "1m" ? (
          <>
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
              <span className="text-[#26A69A]">▲</span>
              <span>多开/空平</span>
            </div>
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
              <span className="text-[#EF5350]">▼</span>
              <span>空开/多平</span>
            </div>
          </>
        ) : mode !== "daily" ? (
          <>
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
              <span className="text-[#26A69A]">▲</span>
              <span>买入</span>
            </div>
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
              <span className="text-[#EF5350]">▼</span>
              <span>卖出</span>
            </div>
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
              <span className="text-[#FF9800]">▲</span>
              <span>双向(T)</span>
            </div>
          </>
        ) : null}
      </div>
    </QlPanel>
  );
}
