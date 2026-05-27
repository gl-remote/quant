import { useParams, Link } from "react-router-dom";
import { useFetchJson } from "@/hooks/useFetchJson";
import OptunaCharts from "@/components/OptunaCharts";
import type { OptunaData } from "@/types";

export default function OptunaPage() {
  const { id } = useParams<{ id: string }>();
  const runId = Number(id);

  const { data: optuna, loading, error } = useFetchJson<OptunaData | null>(
    "optuna.json",
    runId
  );

  if (loading) {
    return (
      <p style={{ textAlign: "center", padding: 60, color: "#888" }}>
        加载中...
      </p>
    );
  }

  if (error || !optuna || !optuna.study_name) {
    return (
      <div>
        <p style={{ textAlign: "center", color: "#999", padding: 40 }}>
          该 run 无优化数据
        </p>
        <div style={{ textAlign: "center" }}>
          <Link to={`/run/${runId}`} style={styles.backLink}>
            &larr; 返回回测结果
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div style={styles.header}>
        <h1 style={styles.title}>参数优化</h1>
        <Link to={`/run/${runId}`} style={styles.backLink}>
          &larr; 返回回测结果
        </Link>
      </div>
      <OptunaCharts data={optuna} />
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "16px",
  },
  title: {
    fontSize: "20px",
    fontWeight: 700,
    margin: 0,
    color: "#222",
  },
  backLink: {
    color: "#2563eb",
    textDecoration: "none",
    fontSize: "13px",
    fontWeight: 600,
  },
};