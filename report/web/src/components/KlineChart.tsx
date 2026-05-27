/**
 * @file KlineChart.tsx
 * @description K线图组件
 * 使用lightweight-charts库绘制K线图，支持日线和分钟线切换，支持SMA均线显示/隐藏
 * 包含蜡烛图、成交量柱状图和SMA移动平均线
 */

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

/**
 * 视图模式类型
 */
type ViewMode = "daily" | "raw";

/**
 * KlineChart组件属性接口
 * @interface Props
 * @property {KlineData | null} data - K线数据
 * @property {boolean} [loading] - 加载状态
 */
interface Props {
  data: KlineData | null;
  loading?: boolean;
}

/**
 * 将K线数据转换为蜡烛图数据格式
 * @param {KlinePoint[]} data - K线数据数组
 * @returns {CandlestickData<Time>[]} 转换后的蜡烛图数据
 */
function convertToCandleData(data: KlinePoint[]): CandlestickData<Time>[] {
  return data.map((d) => ({
    time: d.datetime as Time,
    open: d.open,
    high: d.high,
    low: d.low,
    close: d.close,
  }));
}

/**
 * 计算SMA简单移动平均线
 * @param {KlinePoint[]} data - K线数据数组
 * @param {number} period - 周期
 * @returns {number[]} SMA值数组
 */
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

/**
 * KlineChart组件
 * K线图展示组件
 * 
 * @component
 * @param {Props} props - 组件属性
 * @returns {JSX.Element} 渲染后的K线图组件
 */
export default function KlineChart({ data, loading }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const candlestickSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const smaShortSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const smaLongSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const [mode, setMode] = useState<ViewMode>("daily");
  const [indicators, setIndicators] = useState<{ sma: boolean }>({ sma: true });

  // 根据模式选择K线数据
  const klineData = data ? (mode === "daily" ? data.daily : data.raw) : null;

  /**
   * 初始化图表
   */
  useEffect(() => {
    if (!containerRef.current) return;

    // 创建图表实例
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

    // 添加蜡烛图序列
    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#26A69A",
      downColor: "#EF5350",
      borderUpColor: "#26A69A",
      borderDownColor: "#EF5350",
      wickUpColor: "#26A69A",
      wickDownColor: "#EF5350",
    });

    // 添加成交量序列
    const volumeSeries = chart.addSeries(HistogramSeries, {
      color: "#26A69A",
      priceFormat: {
        type: "volume",
      },
      priceScaleId: "",
    });

    // 添加短期SMA均线
    const smaShortSeries = chart.addSeries(LineSeries, {
      color: "#FF6B6B",
      lineWidth: 2,
    });

    // 添加长期SMA均线
    const smaLongSeries = chart.addSeries(LineSeries, {
      color: "#4ECDC4",
      lineWidth: 2,
    });

    // 配置成交量价格标尺
    volumeSeries.priceScale().applyOptions({
      scaleMargins: {
        top: 0.85,
        bottom: 0,
      },
    });

    // 保存序列引用
    candlestickSeriesRef.current = candlestickSeries;
    volumeSeriesRef.current = volumeSeries;
    smaShortSeriesRef.current = smaShortSeries;
    smaLongSeriesRef.current = smaLongSeries;

    // 处理窗口大小变化
    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({
          width: containerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener("resize", handleResize);

    // 清理函数
    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, []);

  /**
   * 更新图表数据
   */
  useEffect(() => {
    if (!candlestickSeriesRef.current || !volumeSeriesRef.current || !klineData)
      return;

    // 更新蜡烛图数据
    const candleData = convertToCandleData(klineData);
    candlestickSeriesRef.current.setData(candleData);

    // 更新成交量数据
    const volumeData: HistogramData<Time>[] = klineData.map((d, i) => ({
      time: d.datetime as Time,
      value: d.volume,
      color: d.close >= d.open ? "rgba(38,166,154,0.5)" : "rgba(239,83,80,0.5)",
    }));
    volumeSeriesRef.current.setData(volumeData);

    // 更新SMA均线数据
    if (indicators.sma && smaShortSeriesRef.current && smaLongSeriesRef.current) {
      const smaShort = calculateSMA(klineData, 5);
      const smaLong = calculateSMA(klineData, 60);

      const smaShortData = klineData.map((d, i) => ({
        time: d.datetime as Time,
        value: smaShort[i],
      }));

      const smaLongData = klineData.map((d, i) => ({
        time: d.datetime as Time,
        value: smaLong[i],
      }));

      smaShortSeriesRef.current.setData(smaShortData);
      smaLongSeriesRef.current.setData(smaLongData);
    }
  }, [klineData, indicators]);

  /**
   * 更新SMA均线显示状态
   */
  useEffect(() => {
    if (smaShortSeriesRef.current && smaLongSeriesRef.current) {
      smaShortSeriesRef.current.applyOptions({ visible: indicators.sma });
      smaLongSeriesRef.current.applyOptions({ visible: indicators.sma });
    }
  }, [indicators.sma]);

  // 加载状态
  if (loading) {
    return (
      <>
        <style>{`@keyframes ql-spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}`}</style>
        <div style={styles.loading} data-ql-id="RUN-KLINE-LOADING">
          <div style={styles.spinner} />
          <p style={{ marginTop: 12, color: "#999", fontSize: 14 }}>K 线数据加载中...</p>
        </div>
      </>
    );
  }

  // 无数据状态
  if (!data) {
    return (
      <div style={styles.empty} data-ql-id="RUN-KLINE-EMPTY">
        <p>暂无 K 线数据</p>
      </div>
    );
  }

  // 无当前模式数据状态
  if (!klineData || klineData.length === 0) {
    return (
      <div style={styles.empty} data-ql-id="RUN-KLINE-EMPTY">
        <p>当前周期暂无 K 线数据，请切换周期</p>
      </div>
    );
  }

  return (
    <div style={styles.wrapper} data-ql-id="RUN-KLINE-CONTAINER">
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
      <div ref={containerRef} style={styles.chartContainer} data-ql-id="RUN-KLINE-CHART" />
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
    </div>
  );
}

/**
 * 样式对象
 * 定义了KlineChart组件中所有元素的样式
 */
const styles: Record<string, React.CSSProperties> = {
  wrapper: {
    background: "#ffffff",
    borderRadius: "12px",
    padding: "20px",
    marginBottom: "20px",
    boxShadow: "0 4px 20px rgba(0, 0, 0, 0.08)",
  },
  toolbar: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "16px",
    paddingBottom: "12px",
    borderBottom: "1px solid #f0f0f0",
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
    fontFamily: "Monaco, 'Courier New', monospace",
  },
  samplingBadge: {
    fontSize: "11px",
    padding: "2px 8px",
    background: "#fff3cd",
    color: "#856404",
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
    background: "#f5f6fa",
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
    color: "#666",
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
    border: "1px solid #e5e7eb",
    background: "#ffffff",
    fontSize: "12px",
    cursor: "pointer",
    color: "#666",
    borderRadius: "6px",
    transition: "all 0.2s",
  },
  indicatorActive: {
    background: "#f0fdf4",
    borderColor: "#22c55e",
    color: "#166534",
  },
  chartContainer: {
    width: "100%",
    height: "500px",
    position: "relative",
  },
  legend: {
    display: "flex",
    justifyContent: "center",
    gap: "24px",
    marginTop: "12px",
    paddingTop: "12px",
    borderTop: "1px solid #f0f0f0",
  },
  legendItem: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    fontSize: "12px",
    color: "#666",
  },
  legendDot: {
    width: "8px",
    height: "8px",
    borderRadius: "50%",
  },
  empty: {
    background: "#ffffff",
    borderRadius: "12px",
    padding: "60px",
    textAlign: "center",
    color: "#999",
    boxShadow: "0 4px 20px rgba(0, 0, 0, 0.08)",
  },
  loading: {
    background: "#ffffff",
    borderRadius: "12px",
    padding: "80px",
    textAlign: "center",
    color: "#999",
    boxShadow: "0 4px 20px rgba(0, 0, 0, 0.08)",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
  },
  spinner: {
    width: 36,
    height: 36,
    border: "3px solid #f0f0f0",
    borderTop: "3px solid #2563eb",
    borderRadius: "50%",
    animation: "ql-spin 0.8s linear infinite",
  },
};
