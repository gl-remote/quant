import { Link } from "react-router-dom";
import { useFetchJson } from "@/hooks/useFetchJson";
import type { NavItem } from "@/types";

function statusLabel(status: string): string {
  switch (status) {
    case "success":
      return "成功";
    case "running":
      return "运行中";
    case "failed":
      return "失败";
    default:
      return status;
  }
}

export default function NavPage() {
  const { data, loading, error } = useFetchJson<NavItem[]>("nav.json");

  return (
    <div>
      <h1 style={styles.title}>量化回测监控</h1>

      {loading && <p style={styles.status}>加载中...</p>}
      {error && <p style={{ ...styles.status, color: "#dc2626" }}>加载失败: {error}</p>}
      {data && data.length === 0 && <p style={styles.status}>暂无回测记录</p>}

      {data && data.length > 0 && (
        <div style={styles.grid}>
          {data.map((run) => (
            <Link
              key={run.id}
              to={`/run/${run.id}`}
              style={{ textDecoration: "none" }}
            >
              <div style={styles.card}>
                <div style={styles.cardHeader}>
                  <span style={styles.cardId}>r{run.id}</span>
                  <span
                    style={{
                      ...styles.cardStatus,
                      color:
                        run.status === "success"
                          ? "#059669"
                          : run.status === "running"
                          ? "#d97706"
                          : "#dc2626",
                    }}
                  >
                    {statusLabel(run.status)}
                  </span>
                </div>
                <div style={styles.cardBody}>
                  <div style={styles.cardLabel}>策略引擎</div>
                  <div style={styles.cardValue}>
                    {run.strategy} / {run.engine}
                  </div>
                </div>
                <div style={styles.cardMeta}>
                  <span>{run.symbols} 个品种</span>
                  <span>{run.created}</span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  title: {
    fontSize: "24px",
    fontWeight: 700,
    marginBottom: "24px",
    color: "#222",
  },
  status: {
    color: "#888",
    textAlign: "center",
    padding: "40px 0",
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
    gap: "16px",
  },
  card: {
    background: "#fff",
    borderRadius: "8px",
    padding: "16px",
    boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
    cursor: "pointer",
    transition: "box-shadow 0.15s",
  },
  cardHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "12px",
  },
  cardId: {
    fontSize: "14px",
    fontWeight: 700,
    color: "#2563eb",
  },
  cardStatus: {
    fontSize: "11px",
    fontWeight: 600,
  },
  cardBody: {
    marginBottom: "8px",
  },
  cardLabel: {
    fontSize: "11px",
    color: "#999",
    marginBottom: "2px",
  },
  cardValue: {
    fontSize: "14px",
    fontWeight: 600,
    color: "#333",
  },
  cardMeta: {
    display: "flex",
    justifyContent: "space-between",
    fontSize: "11px",
    color: "#aaa",
  },
};