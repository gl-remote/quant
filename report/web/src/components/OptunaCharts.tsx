import type { OptunaData } from "@/types";
import GenericChart from "@/components/GenericChart";

interface Props {
  data: OptunaData;
}

export default function OptunaCharts({ data }: Props) {
  if (!data || !data.charts) {
    return <p style={{ textAlign: "center", color: "#999" }}>无优化结果</p>;
  }

  const { charts, best_params, study_name } = data;

  return (
    <div>
      <h2 style={styles.title}>{study_name} 优化结果</h2>

      {best_params && best_params.length > 0 && (
        <div style={styles.params}>
          <h3 style={styles.subtitle}>最优参数</h3>
          <div style={styles.paramGrid}>
            {best_params.map((p) => (
              <div key={p.name} style={styles.paramItem}>
                <span style={styles.paramName}>{p.name}</span>
                <span style={styles.paramValue}>{p.value}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <GenericChart
        title="优化历史"
        spec={charts.optimization_history}
      />
      <GenericChart
        title="参数重要性"
        spec={charts.param_importances}
      />
      <GenericChart
        title="平行坐标"
        spec={charts.parallel_coordinate}
      />
      <GenericChart
        title="等高线"
        spec={charts.contour}
      />
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  title: {
    fontSize: "20px",
    fontWeight: 700,
    marginBottom: "16px",
    color: "#333",
  },
  subtitle: {
    fontSize: "14px",
    fontWeight: 600,
    margin: "0 0 8px 0",
    color: "#555",
  },
  params: {
    background: "#fff",
    borderRadius: "8px",
    padding: "16px",
    marginBottom: "16px",
    boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
  },
  paramGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))",
    gap: "8px",
  },
  paramItem: {
    display: "flex",
    justifyContent: "space-between",
    padding: "6px 10px",
    background: "#f0fdf4",
    borderRadius: "4px",
    border: "1px solid #bbf7d0",
  },
  paramName: {
    fontSize: "12px",
    color: "#666",
    fontWeight: 600,
  },
  paramValue: {
    fontSize: "12px",
    color: "#059669",
    fontWeight: 600,
  },
};