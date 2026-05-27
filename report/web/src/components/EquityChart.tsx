import Plot from "@/components/PlotlyWrapper";
import type { EquityData } from "@/types";

interface Props {
  data: EquityData;
}

export default function EquityChart({ data }: Props) {
  if (!data || data.equity.length === 0) {
    return (
      <div style={styles.empty}>
        <p>暂无资金曲线数据</p>
      </div>
    );
  }

  const equityTrace = {
    x: data.dates,
    y: data.equity,
    type: "scatter" as const,
    mode: "lines",
    name: "资金曲线",
    line: {
      color: "#2563eb",
      width: 2,
    },
    yaxis: "y1",
  };

  const drawdownTrace = {
    x: data.dates,
    y: data.drawdown.map((d) => d * 100),
    type: "scatter" as const,
    mode: "lines",
    name: "回撤",
    line: {
      color: "#dc2626",
      width: 2,
    },
    fill: "tozeroy",
    fillcolor: "rgba(220, 38, 38, 0.1)",
    yaxis: "y2",
  };

  const startEquity = data.equity[0] || 100000;
  const endEquity = data.equity[data.equity.length - 1] || 100000;
  const totalReturn = ((endEquity - startEquity) / startEquity * 100).toFixed(2);
  const maxDrawdown = (Math.min(...data.drawdown) * 100).toFixed(2);

  return (
    <div style={styles.wrapper}>
      <div style={styles.header}>
        <div style={styles.titleSection}>
          <h3 style={styles.title}>
            <span style={styles.titleIcon}>💰</span>
            资金曲线
          </h3>
          <span style={styles.symbol}>{data.symbol}</span>
        </div>
        <div style={styles.statsRow}>
          <div style={styles.statCard}>
            <span style={styles.statLabel}>累计收益</span>
            <span style={{ ...styles.statValue, color: parseFloat(totalReturn) >= 0 ? "#059669" : "#dc2626" }}>
              {totalReturn}%
            </span>
          </div>
          <div style={styles.statCard}>
            <span style={styles.statLabel}>最大回撤</span>
            <span style={{ ...styles.statValue, color: "#dc2626" }}>{maxDrawdown}%</span>
          </div>
          <div style={styles.statCard}>
            <span style={styles.statLabel}>最终权益</span>
            <span style={styles.statValue}>{endEquity.toLocaleString()}</span>
          </div>
        </div>
      </div>
      <Plot
        data={[equityTrace, drawdownTrace] as any}
        layout={{
          height: 350,
          margin: { l: 60, r: 60, t: 20, b: 40 },
          hovermode: "x unified",
          showlegend: true,
          legend: {
            orientation: "h",
            x: 0.05,
            y: 1.15,
          },
          dragmode: "pan",
          paper_bgcolor: "#fff",
          plot_bgcolor: "#fff",
          xaxis: {
            showgrid: true,
            gridcolor: "#f0f0f0",
            rangeslider: { visible: false },
            tickformat: "%Y-%m-%d",
          },
          yaxis: {
            showgrid: true,
            gridcolor: "#f0f0f0",
            title: { text: "权益 (元)" },
            tickformat: ",.0f",
          },
          yaxis2: {
            title: { text: "回撤 (%)" },
            overlaying: "y",
            side: "right",
            showgrid: false,
            range: [-100, 0],
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
    background: "#ffffff",
    borderRadius: "12px",
    padding: "20px",
    marginBottom: "20px",
    boxShadow: "0 4px 20px rgba(0, 0, 0, 0.08)",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "12px",
    paddingBottom: "12px",
    borderBottom: "1px solid #f0f0f0",
  },
  titleSection: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
  },
  title: {
    fontSize: "16px",
    fontWeight: 600,
    margin: 0,
    color: "#1a1a1a",
    display: "flex",
    alignItems: "center",
    gap: "8px",
  },
  titleIcon: {
    fontSize: "18px",
  },
  symbol: {
    fontSize: "13px",
    padding: "4px 10px",
    background: "#f0f9ff",
    color: "#0369a1",
    borderRadius: "6px",
    fontWeight: 500,
  },
  statsRow: {
    display: "flex",
    gap: "16px",
  },
  statCard: {
    display: "flex",
    flexDirection: "column",
    alignItems: "right",
    padding: "8px 14px",
    background: "#f9fafb",
    borderRadius: "8px",
    minWidth: "90px",
  },
  statLabel: {
    fontSize: "11px",
    color: "#9ca3af",
    marginBottom: "4px",
  },
  statValue: {
    fontSize: "14px",
    fontWeight: 600,
    color: "#374151",
  },
  empty: {
    background: "#ffffff",
    borderRadius: "12px",
    padding: "48px",
    textAlign: "center",
    color: "#999",
    boxShadow: "0 4px 20px rgba(0, 0, 0, 0.08)",
  },
};