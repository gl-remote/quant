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
  LineData,
  Time,
  TickMarkType,
} from "lightweight-charts";
import type { KlineData, KlinePoint, TradeRecord } from "@/types";
import QlPanel from "@/components/QlPanel";
import { qlIdNameMap } from "@/data/qlIdMapping";

type ViewMode = "daily" | "raw";

interface Props {
  data: KlineData | null;
  trades?: TradeRecord[] | null;
  loading?: boolean;
}

function toChartTime(dt: string | number): Time {
  if (typeof dt === "number") {
    return dt as Time;
  }
  // 处理字符串格式的时间戳
  if (!isNaN(Number(dt))) {
    return Number(dt) as Time;
  }
  // 兼容旧格式（已废弃，保留用于迁移）
  if (dt.includes(" ")) {
    return (new Date(dt.replace(" ", "T") + "Z").getTime() / 1000) as Time;
  }
  if (dt.includes("T")) {
    return (new Date(dt + "Z").getTime() / 1000) as Time;
  }
  // 纯日期格式返回字符串
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

function calculateSMA(data: KlinePoint[], period: number): number[] {
  const result: number[] = [];
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      result.push(NaN);
      continue;
    }
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) {
      sum += data[j].close;
    }
    result.push(sum / period);
  }
  return result;
}

function convertTradeToMarkers(
  trades: TradeRecord[],
  klineData: KlinePoint[]
): LineData<Time>[] {
  if (!trades || trades.length === 0 || !klineData || klineData.length === 0) {
    return [];
  }

  // 找到K线数据的价格范围，用于计算标记位置
  const prices = klineData.flatMap((k) => [k.high, k.low]);
  const minPrice = Math.min(...prices);
  const maxPrice = Math.max(...prices);
  const priceRange = maxPrice - minPrice;
  const padding = priceRange * 0.05; // 5%的边距

  const markers: LineData<Time>[] = [];

  for (const trade of trades) {
    // 转换交易时间为时间戳
    let tradeTime: Time;
    if (typeof trade.datetime === "number") {
      tradeTime = trade.datetime as Time;
    } else if (trade.datetime.includes(" ")) {
      tradeTime = (new Date(trade.datetime.replace(" ", "T") + "Z").getTime() / 1000) as Time;
    } else if (trade.datetime.includes("T")) {
      tradeTime = (new Date(trade.datetime + "Z").getTime() / 1000) as Time;
    } else {
      tradeTime = trade.datetime as Time;
    }

    // 确定标记位置和形状
    let price: number;
    let shape: "arrowUp" | "arrowDown";
    let color: string;
    let text: string;

    if (trade.offset === "open") {
      price = trade.open_price;
      if (trade.direction === "long") {
        shape = "arrowUp";
        color = "#26A69A"; // 绿色，做多开仓
        text = "开多";
      } else {
        shape = "arrowDown";
        color = "#EF5350"; // 红色，做空开仓
        text = "开空";
      }
      // 开仓标记在价格下方一点
      price = price - padding;
    } else {
      price = trade.close_price;
      if (trade.direction === "long") {
        shape = "arrowDown";
        color = "#26A69A"; // 绿色，做多平仓
        text = "平多";
      } else {
        shape = "arrowUp";
        color = "#EF5350"; // 红色，做空平仓
        text = "平空";
      }
      // 平仓标记在价格上方一点
      price = price + padding;
    }

    markers.push({
      time: tradeTime,
      value: price,
      // @ts-ignore - lightweight-charts 支持自定义标记，但类型定义可能不完整
      marker: {
        shape,
        color,
        size: 1,
        text,
      },
    });
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
  const tradeMarkersSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const [mode, setMode] = useState<ViewMode>("daily");
  const [indicators, setIndicators] = useState<{ sma: boolean; trades: boolean }>({
    sma: true,
    trades: true,
  });

  const klineData = data ? (mode === "daily" ? data.daily : data.raw) : null;
  console.log("[KlineChart] 渲染 - data:", data ? "有数据" : "null", "loading:", loading, "klineData:", klineData ? `${klineData.length}条` : "null");

  // 初始化图表 - 依赖 klineData，当有数据且容器挂载后才初始化
  useEffect(() => {
    console.log("[KlineChart] 图表初始化 useEffect, klineData:", !!klineData, "container:", !!containerRef.current, "chart:", !!chartRef.current);
    
    if (!klineData) return;
    const container = containerRef.current;
    if (!container) {
      console.log("[KlineChart] 无容器，跳过");
      return;
    }
    if (chartRef.current) {
      console.log("[KlineChart] 图表已存在，跳过");
      return;
    }

    console.log("[KlineChart] 创建图表");
    const chart = createChart(container, {
      layout: {
        background: { color: "#ffffff" },
        textColor: "#333",
      },
      grid: {
        vertLines: { color: "#f0f0f0" },
        horzLines: { color: "#f0f0f0" },
      },
      width: container.clientWidth,
      height: 500,
      crosshair: {
        mode: 1,
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
      // @ts-ignore - logo 是 lightweight-charts 的有效配置，但类型定义可能没有更新
      logo: {
        visible: false, // 隐藏 TradingView 品牌链接
      },
    });

    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#26A69A",
      downColor: "#EF5350",
      borderUpColor: "#26A69A",
      borderDownColor: "#EF5350",
      wickUpColor: "#26A69A",
      wickDownColor: "#EF5350",
    });

    const volumeSeries = chart.addSeries(HistogramSeries, {
      color: "#26A69A",
      priceFormat: {
        type: "volume",
      },
      priceScaleId: "",
    });

    const smaShortSeries = chart.addSeries(LineSeries, {
      color: "#FF6B6B",
      lineWidth: 2,
    });

    const smaLongSeries = chart.addSeries(LineSeries, {
      color: "#4ECDC4",
      lineWidth: 2,
    });

    const tradeMarkersSeries = chart.addSeries(LineSeries, {
      color: "transparent",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });

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
    tradeMarkersSeriesRef.current = tradeMarkersSeries;
    chartRef.current = chart;
    console.log("[KlineChart] 图表创建成功");

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
    };
  }, [klineData]);

  // 设置 K 线数据
  useEffect(() => {
    if (!klineData) return;
    const candleSeries = candlestickSeriesRef.current;
    const volSeries = volumeSeriesRef.current;
    const tradeMarkersSeries = tradeMarkersSeriesRef.current;
    if (!candleSeries || !volSeries) return;

    console.log("[KlineChart] 设置 K 线数据:", klineData.length, "条");
    const candleData = convertToCandleData(klineData);
    candleSeries.setData(candleData);

    const volumeData: HistogramData<Time>[] = klineData.map((d) => ({
      time: toChartTime(d.datetime),
      value: d.volume,
      color: d.close >= d.open ? "rgba(38,166,154,0.5)" : "rgba(239,83,80,0.5)",
    }));
    volSeries.setData(volumeData);

    if (indicators.sma && smaShortSeriesRef.current && smaLongSeriesRef.current) {
      const smaShort = calculateSMA(klineData, 5);
      const smaLong = calculateSMA(klineData, 60);

      const smaShortData = klineData.map((d, idx) => ({
        time: toChartTime(d.datetime),
        value: smaShort[idx],
      }));

      const smaLongData = klineData.map((d, idx) => ({
        time: toChartTime(d.datetime),
        value: smaLong[idx],
      }));

      smaShortSeriesRef.current.setData(smaShortData);
      smaLongSeriesRef.current.setData(smaLongData);
    }

    // 设置交易标记
    if (tradeMarkersSeries && indicators.trades && trades) {
      const markers = convertTradeToMarkers(trades, klineData);
      tradeMarkersSeries.setData(markers);
      tradeMarkersSeries.applyOptions({ visible: true });
    } else if (tradeMarkersSeries) {
      tradeMarkersSeries.setData([]);
      tradeMarkersSeries.applyOptions({ visible: false });
    }
  }, [klineData, indicators, trades]);

  // 控制 SMA 和交易标记可见性
  useEffect(() => {
    if (smaShortSeriesRef.current && smaLongSeriesRef.current) {
      smaShortSeriesRef.current.applyOptions({ visible: indicators.sma });
      smaLongSeriesRef.current.applyOptions({ visible: indicators.sma });
    }
    if (tradeMarkersSeriesRef.current) {
      tradeMarkersSeriesRef.current.applyOptions({ visible: indicators.trades });
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
        {mode === "raw" && data.raw_downsampled && (
          <span className="text-[11px] px-2 py-0.5 bg-amber-50 text-amber-800 rounded">抽样显示</span>
        )}
      </div>
      <div className="flex items-center">
        <div className="flex bg-slate-100 rounded-lg p-0.5">
          <button
            onClick={() => setMode("daily")}
            data-ql-id="RUN-KLINE-BTN-DAILY"
            className={mode === "daily" ? toggleActive : toggleBtn}
          >
            日线
          </button>
          <button
            onClick={() => setMode("raw")}
            data-ql-id="RUN-KLINE-BTN-MINUTE"
            className={mode === "raw" ? toggleActive : toggleBtn}
          >
            分钟线
          </button>
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
        className="w-full h-[500px]"
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
        <div className="flex items-center gap-1.5 text-xs text-slate-500">
          <span className="text-[#26A69A]">▲</span>
          <span>开多</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-slate-500">
          <span className="text-[#EF5350]">▼</span>
          <span>开空</span>
        </div>
      </div>
    </QlPanel>
  );
}