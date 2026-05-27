import { useState } from "react";
import Plot from "@/components/PlotlyWrapper";
import type { KlineData, KlinePoint } from "@/types";

type ViewMode = "daily" | "raw";

function toCandlestick(data: KlinePoint[], name: string) {
  return {
    x: data.map((d) => d.datetime),
    open: data.map((d) => d.open),
    high: data.map((d) => d.high),
    low: data.map((d) => d.low),
    close: data.map((d) => d.close),
    type: "candlestick" as const,
    name,
    increasing: { line: { color: "#26A69A" } },
    decreasing: { line: { color: "#EF5350" } },
  };
}

function toVolume(data: KlinePoint[]) {
  const colors = data.map((d) =>
    d.close >= d.open ? "rgba(38,166,154,0.4)" : "rgba(239,83,80,0.4)"
  );
  return {
    x: data.map((d) => d.datetime),
    y: data.map((d) => d.volume),
    type: "bar" as const,
    name: "成交量",
    marker: { color: colors },
    yaxis: "y2",
  };
}

interface Props {
  data: KlineData;
}

export default function KlineChart({ data }: Props) {
  const [mode, setMode] = useState<ViewMode>("daily");
  const klineData = mode === "daily" ? data.daily : data.raw;

  if (!klineData || klineData.length === 0) {
    return (
      <div style={styles.empty}>
        <p>暂无 K 线数据</p>
      </div>
    );
  }

  const traces = [toCandlestick(klineData, "K线"), toVolume(klineData)];

  return (
    <div style={styles.wrapper}>
      <div style={styles.toolbar}>
        <span style={styles.symbol}>{data.symbol}</span>
        <div style={styles.toggleGroup}>
          <button
            onClick={() => setMode("daily")}
            style={{
              ...styles.toggleBtn,
              ...(mode === "daily" ? styles.toggleActive : {}),
            }}
          >
            日线
          </button>
          <button
            onClick={() => setMode("raw")}
            style={{
              ...styles.toggleBtn,
              ...(mode === "raw" ? styles.toggleActive : {}),
            }}
          >
            分钟线
            {data.raw_downsampled && mode === "raw" && (
              <span style={styles.badge}>抽样</span>
            )}
          </button>
        </div>
      </div>
      <Plot
        data={traces as any}
        layout={{
          height: 500,
          margin: { l: 60, r: 60, t: 10, b: 40 },
          hovermode: "x unified",
          showlegend: false,
          dragmode: "pan",
          paper_bgcolor: "#fff",
          plot_bgcolor: "#fff",
          xaxis: {
            showgrid: true,
            gridcolor: "#f0f0f0",
            rangeslider: { visible: false },
          },
          yaxis: {
            showgrid: true,
            gridcolor: "#f0f0f0",
            title: { text: "价格" },
          },
          yaxis2: {
            title: { text: "成交量" },
            overlaying: "y",
            side: "right",
            showgrid: false,
            tickformat: ",s",
          },
        }}
        config={{
          responsive: true,
          displaylogo: false,
          scrollZoom: true,
        }}
        useResizeHandler
        style={{ width: "100%" }}
      />
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrapper: {
    background: "#fff",
    borderRadius: "8px",
    padding: "16px",
    marginBottom: "16px",
    boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
  },
  toolbar: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "8px",
  },
  symbol: {
    fontSize: "16px",
    fontWeight: 600,
    color: "#333",
  },
  toggleGroup: {
    display: "flex",
    gap: 0,
  },
  toggleBtn: {
    padding: "4px 12px",
    border: "1px solid #d1d5db",
    background: "#fff",
    fontSize: "12px",
    cursor: "pointer",
    color: "#666",
  },
  toggleActive: {
    background: "#2563eb",
    color: "#fff",
    borderColor: "#2563eb",
  },
  badge: {
    fontSize: "10px",
    marginLeft: "4px",
    opacity: 0.7,
  },
  empty: {
    background: "#fff",
    borderRadius: "8px",
    padding: "40px",
    textAlign: "center",
    color: "#999",
  },
};