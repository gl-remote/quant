import Plot from "@/components/PlotlyWrapper";
import type { PlotlySpec } from "@/types";

interface Props {
  title: string;
  spec: PlotlySpec | null;
}

export default function GenericChart({ title, spec }: Props) {
  if (!spec) {
    return (
      <div style={styles.empty}>
        <p>{title} — 无数据</p>
      </div>
    );
  }

  return (
    <div style={styles.wrapper}>
      <Plot
        data={spec.data as Plotly.Data[]}
        layout={{
          ...spec.layout,
          height: 400,
          margin: { l: 60, r: 40, t: 50, b: 40 },
          paper_bgcolor: "#fff",
          plot_bgcolor: "#fff",
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
  empty: {
    background: "#fff",
    borderRadius: "8px",
    padding: "40px",
    textAlign: "center",
    color: "#999",
    marginBottom: "16px",
  },
};