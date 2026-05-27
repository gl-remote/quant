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
} from "lightweight-charts";
import type { KlineData, KlinePoint } from "@/types";
import QlPanel from "@/components/QlPanel";
import { qlIdNameMap } from "@/data/qlIdMapping";

type ViewMode = "daily" | "raw";

interface Props {
  data: KlineData | null;
  loading?: boolean;
}

function toChartTime(dt: string): Time {
  if (dt.includes(" ")) {
    return (new Date(dt.replace(" ", "T") + "+08:00").getTime() / 1000) as Time;
  }
  if (dt.includes("T")) {
    return (new Date(dt + "+08:00").getTime() / 1000) as Time;
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

export default function KlineChart({ data, loading }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const candlestickSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const smaShortSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const smaLongSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const [mode, setMode] = useState<ViewMode>("daily");
  const [indicators, setIndicators] = useState<{ sma: boolean }>({ sma: true });

  const klineData = data ? (mode === "daily" ? data.daily : data.raw) : null;

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: "#ffffff" },
        textColor: "#333",
      },
      grid: {
        vertLines: { color: "#f0f0f0" },
        horzLines: { color: "#f0f0f0" },
      },
      width: containerRef.current.clientWidth,
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
    };
  }, []);

  useEffect(() => {
    if (!candlestickSeriesRef.current || !volumeSeriesRef.current || !klineData)
      return;

    const candleData = convertToCandleData(klineData);
    candlestickSeriesRef.current.setData(candleData);

    const volumeData: HistogramData<Time>[] = klineData.map((d, i) => ({
      time: toChartTime(d.datetime),
      value: d.volume,
      color: d.close >= d.open ? "rgba(38,166,154,0.5)" : "rgba(239,83,80,0.5)",
    }));
    volumeSeriesRef.current.setData(volumeData);

    if (indicators.sma && smaShortSeriesRef.current && smaLongSeriesRef.current) {
      const smaShort = calculateSMA(klineData, 5);
      const smaLong = calculateSMA(klineData, 60);

      const smaShortData = klineData.map((d, i) => ({
        time: toChartTime(d.datetime),
        value: smaShort[i],
      }));

      const smaLongData = klineData.map((d, i) => ({
        time: toChartTime(d.datetime),
        value: smaLong[i],
      }));

      smaShortSeriesRef.current.setData(smaShortData);
      smaLongSeriesRef.current.setData(smaLongData);
    }
  }, [klineData, indicators]);

  useEffect(() => {
    if (smaShortSeriesRef.current && smaLongSeriesRef.current) {
      smaShortSeriesRef.current.applyOptions({ visible: indicators.sma });
      smaLongSeriesRef.current.applyOptions({ visible: indicators.sma });
    }
  }, [indicators.sma]);

  if (loading) {
    return (
      <QlPanel qlId="RUN-KLINE-LOADING" name={qlIdNameMap["RUN-KLINE-LOADING"]} style={{ marginBottom: 28 }}>
        <style>{`@keyframes ql-spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}`}</style>
        <div style={styles.loadingInner}>
          <div style={styles.spinner} />
          <p style={{ marginTop: 12, color: "#94a3b8", fontSize: 14 }}>K 线数据加载中...</p>
        </div>
      </QlPanel>
    );
  }

  if (!data) {
    return (
      <QlPanel qlId="RUN-KLINE-EMPTY" name={qlIdNameMap["RUN-KLINE-EMPTY"]} style={{ marginBottom: 28 }}>
        <p style={styles.emptyText}>暂无 K 线数据</p>
      </QlPanel>
    );
  }

  if (!klineData || klineData.length === 0) {
    return (
      <QlPanel qlId="RUN-KLINE-EMPTY" name={qlIdNameMap["RUN-KLINE-EMPTY"]} style={{ marginBottom: 28 }}>
        <p style={styles.emptyText}>当前周期暂无 K 线数据，请切换周期</p>
      </QlPanel>
    );
  }

  const toolbar = (
    <div style={styles.toolbar} data-ql-id="RUN-KLINE-TOOLBAR">
      <div style={styles.leftGroup}>
        <span style={styles.symbol}>{data.symbol}</span>
        {mode === "raw" && data.raw_downsampled && (
          <span style={styles.samplingBadge}>抽样显示</span>
        )}
      </div>
      <div style={styles.centerGroup}>
        <div style={styles.toggleGroup}>
          <button
            onClick={() => setMode("daily")}
            data-ql-id="RUN-KLINE-BTN-DAILY"
            style={{
              ...styles.toggleBtn,
              ...(mode === "daily" ? styles.toggleActive : {}),
            }}
          >
            日线
          </button>
          <button
            onClick={() => setMode("raw")}
            data-ql-id="RUN-KLINE-BTN-MINUTE"
            style={{
              ...styles.toggleBtn,
              ...(mode === "raw" ? styles.toggleActive : {}),
            }}
          >
            分钟线
          </button>
        </div>
      </div>
      <div style={styles.rightGroup}>
        <button
          onClick={() => setIndicators((prev) => ({ ...prev, sma: !prev.sma }))}
          data-ql-id="RUN-KLINE-BTN-SMA"
          style={{
            ...styles.indicatorBtn,
            ...(indicators.sma ? styles.indicatorActive : {}),
          }}
        >
          SMA 均线
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
        style={styles.chartContainer}
        data-ql-id="RUN-KLINE-CHART"
      />
      <div style={styles.legend}>
        <div style={styles.legendItem}>
          <span style={{ ...styles.legendDot, backgroundColor: "#FF6B6B" }} />
          <span>SMA(5)</span>
        </div>
        <div style={styles.legendItem}>
          <span style={{ ...styles.legendDot, backgroundColor: "#4ECDC4" }} />
          <span>SMA(60)</span>
        </div>
        <div style={styles.legendItem}>
          <span style={{ ...styles.legendDot, backgroundColor: "#26A69A" }} />
          <span>阳线</span>
        </div>
        <div style={styles.legendItem}>
          <span style={{ ...styles.legendDot, backgroundColor: "#EF5350" }} />
          <span>阴线</span>
        </div>
      </div>
    </QlPanel>
  );
}

const styles: Record<string, React.CSSProperties> = {
  toolbar: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "16px",
    paddingBottom: "12px",
    borderBottom: "1px solid #f1f5f9",
  },
  leftGroup: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
  },
  symbol: {
    fontSize: "18px",
    fontWeight: 700,
    color: "#1a1a1a",
    fontFamily: "SF Mono, Monaco, Consolas, monospace",
  },
  samplingBadge: {
    fontSize: "11px",
    padding: "2px 8px",
    background: "#fef3c7",
    color: "#92400e",
    borderRadius: "4px",
  },
  centerGroup: {
    display: "flex",
    alignItems: "center",
  },
  rightGroup: {
    display: "flex",
    gap: "8px",
  },
  toggleGroup: {
    display: "flex",
    background: "#f1f5f9",
    borderRadius: "8px",
    padding: "2px",
  },
  toggleBtn: {
    padding: "6px 16px",
    border: "none",
    background: "transparent",
    fontSize: "13px",
    fontWeight: 500,
    cursor: "pointer",
    color: "#64748b",
    borderRadius: "6px",
    transition: "all 0.2s",
  },
  toggleActive: {
    background: "#2563eb",
    color: "#ffffff",
    boxShadow: "0 2px 8px rgba(37, 99, 235, 0.3)",
  },
  indicatorBtn: {
    padding: "6px 14px",
    border: "1px solid #e2e8f0",
    background: "#ffffff",
    fontSize: "12px",
    cursor: "pointer",
    color: "#64748b",
    borderRadius: "6px",
    transition: "all 0.2s",
  },
  indicatorActive: {
    background: "#f0fdf4",
    borderColor: "#86efac",
    color: "#166534",
  },
  chartContainer: {
    width: "100%",
    height: "500px",
  },
  legend: {
    display: "flex",
    justifyContent: "center",
    gap: "24px",
    marginTop: "12px",
    paddingTop: "12px",
    borderTop: "1px solid #f1f5f9",
  },
  legendItem: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    fontSize: "12px",
    color: "#64748b",
  },
  legendDot: {
    width: "8px",
    height: "8px",
    borderRadius: "50%",
  },
  loadingInner: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    padding: "60px 0",
  },
  spinner: {
    width: 36,
    height: 36,
    border: "3px solid #f1f5f9",
    borderTop: "3px solid #2563eb",
    borderRadius: "50%",
    animation: "ql-spin 0.8s linear infinite",
  },
  emptyText: {
    textAlign: "center",
    color: "#94a3b8",
    padding: "40px 0",
  },
};