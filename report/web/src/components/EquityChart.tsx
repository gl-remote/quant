import Plot from "@/components/PlotlyWrapper";
import type { EquityData } from "@/types";

interface Props {
  data: EquityData;
}

export default function EquityChart({ data }: Props) {
  if (!data || !data.dates || data.dates.length === 0) {
    return <p style={{ color: "#999", textAlign: "center" }}>无资金曲线数据</p>;
  }

  const equityTrace = {
    x: data.dates,
    y: data.equity,
    type: "scatter" as const,
    mode: "lines" as const,
    name: "权益",
    line: { color: "#2563eb", width: 2 },
    fill: "tozeroy" as const,
    fillcolor: "rgba(37,99,235,0.1)",
  };

  const drawdownTrace = {
    x: data.dates,
    y: data.drawdown,
    type: "scatter" as const,
    mode: "lines" as const,
    name: "回撤",
    yaxis: "y2",
    line: { color: "#ef4444", width: 1.5 },
    fill: "tozeroy" as const,
    fillcolor: "rgba(239,68,68,0.1)",
  };

  return (
    <div style={styles.wrapper}>
      <h2 style={styles.title}>{data.symbol} 资金曲线</h2>
      <Plot
        data={[equityTrace, drawdownTrace] as any}
        layout={{
          height: 400,
          margin: { l: 60, r: 60, t: 10, b: 40 },
          hovermode: "x unified",
          legend: { x: 0.01, y: 0.99, bgcolor: "rgba(255,255,255,0.6)" },
          paper_bgcolor: "#fff",
          plot_bgcolor: "#fff",
          xaxis: { showgrid: true, gridcolor: "#f0f0f0" },
          yaxis: { showgrid: true, gridcolor: "#f0f0f0", title: { text: "权益" } },
          yaxis2: {
            title: { text: "回撤 %" },
            overlaying: "y",
            side: "right",
            showgrid: false,
            tickformat: ".1%",
          },
        }}
        config={{ responsive: true, displaylogo: false }}
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
  title: {
    fontSize: "16px",
    fontWeight: 600,
    margin: "0 0 12px 0",
    color: "#555",
  },
};