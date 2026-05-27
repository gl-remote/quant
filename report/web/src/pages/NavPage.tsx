import { Link } from "react-router-dom";
import { fetchJson } from "@/data/loader";
import type { NavItem } from "@/types";
import { useState, useEffect } from "react";

export default function NavPage() {
  const [runs, setRuns] = useState<NavItem[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJson<NavItem[]>("nav.json")
      .then((data) => {
        setRuns(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div style={styles.loadingContainer}>
        <div style={styles.loadingSpinner}></div>
        <p style={styles.loadingText}>加载中...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={styles.errorContainer}>
        <div style={styles.errorIcon}>❌</div>
        <p style={styles.errorText}>加载失败: {error}</p>
      </div>
    );
  }

  if (!runs || runs.length === 0) {
    return (
      <div style={styles.emptyContainer}>
        <div style={styles.emptyIcon}>📊</div>
        <h2 style={styles.emptyTitle}>暂无回测记录</h2>
        <p style={styles.emptyText}>运行回测后，结果将在这里显示</p>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <div style={styles.headerSection}>
        <div style={styles.headerTitle}>
          <h1 style={styles.title}>回测报告导航</h1>
          <p style={styles.subtitle}>共 {runs.length} 条回测记录</p>
        </div>
        <div style={styles.headerStats}>
          <div style={styles.statItem}>
            <span style={styles.statNumber}>{runs.length}</span>
            <span style={styles.statLabel}>总回测</span>
          </div>
          <div style={styles.statDivider}></div>
          <div style={styles.statItem}>
            <span style={styles.statNumber}>{runs.filter((r) => r.status === "completed").length}</span>
            <span style={styles.statLabel}>已完成</span>
          </div>
          <div style={styles.statDivider}></div>
          <div style={styles.statItem}>
            <span style={styles.statNumber}>
              {runs.reduce((sum, r) => sum + r.symbols, 0)}
            </span>
            <span style={styles.statLabel}>品种数</span>
          </div>
        </div>
      </div>

      <div style={styles.cardGrid}>
        {runs.map((run) => (
          <Link
            key={run.id}
            to={`/run/${run.id}`}
            style={styles.cardLink}
          >
            <div style={styles.card}>
              <div style={styles.cardHeader}>
                <div style={styles.runBadge}>
                  <span style={styles.runId}>#{run.id}</span>
                  <span
                    style={{
                      ...styles.statusBadge,
                      backgroundColor:
                        run.status === "completed" ? "#dcfce7" : "#fef3c7",
                      color:
                        run.status === "completed" ? "#166534" : "#854d0e",
                    }}
                  >
                    {run.status === "completed" ? "完成" : "运行中"}
                  </span>
                </div>
                <div style={styles.cardDate}>{run.created}</div>
              </div>

              <div style={styles.cardBody}>
                <div style={styles.cardTitle}>{run.strategy}</div>
                <div style={styles.cardMeta}>
                  <span style={styles.metaItem}>
                    <span style={styles.metaIcon}>⚙️</span>
                    {run.engine}
                  </span>
                  <span style={styles.metaItem}>
                    <span style={styles.metaIcon}>📈</span>
                    {run.symbols} 个品种
                  </span>
                </div>
              </div>

              <div style={styles.cardFooter}>
                <span style={styles.viewText}>查看详情</span>
                <span style={styles.viewArrow}>→</span>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    maxWidth: "1200px",
    margin: "0 auto",
  },
  headerSection: {
    background: "linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%)",
    borderRadius: "12px",
    padding: "32px",
    marginBottom: "24px",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    boxShadow: "0 8px 32px rgba(30, 58, 95, 0.2)",
  },
  headerTitle: {
    color: "#ffffff",
  },
  title: {
    fontSize: "24px",
    fontWeight: 700,
    margin: 0,
    marginBottom: "8px",
  },
  subtitle: {
    fontSize: "14px",
    color: "rgba(255, 255, 255, 0.8)",
    margin: 0,
  },
  headerStats: {
    display: "flex",
    alignItems: "center",
    gap: "24px",
  },
  statItem: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
  },
  statNumber: {
    fontSize: "28px",
    fontWeight: 700,
    color: "#ffffff",
  },
  statLabel: {
    fontSize: "12px",
    color: "rgba(255, 255, 255, 0.7)",
    marginTop: "4px",
  },
  statDivider: {
    width: "1px",
    height: "40px",
    background: "rgba(255, 255, 255, 0.2)",
  },
  cardGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
    gap: "20px",
  },
  cardLink: {
    textDecoration: "none",
    color: "inherit",
  },
  card: {
    background: "#ffffff",
    borderRadius: "12px",
    padding: "20px",
    boxShadow: "0 4px 20px rgba(0, 0, 0, 0.08)",
    transition: "transform 0.2s, box-shadow 0.2s",
    border: "1px solid #f0f0f0",
  },
  cardHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "16px",
    paddingBottom: "12px",
    borderBottom: "1px solid #f0f0f0",
  },
  runBadge: {
    display: "flex",
    gap: "8px",
    alignItems: "center",
  },
  runId: {
    fontSize: "14px",
    fontWeight: 700,
    color: "#1a1a1a",
  },
  statusBadge: {
    fontSize: "11px",
    padding: "3px 8px",
    borderRadius: "10px",
    fontWeight: 500,
  },
  cardDate: {
    fontSize: "12px",
    color: "#9ca3af",
  },
  cardBody: {
    marginBottom: "16px",
  },
  cardTitle: {
    fontSize: "18px",
    fontWeight: 600,
    color: "#1a1a1a",
    marginBottom: "8px",
  },
  cardMeta: {
    display: "flex",
    gap: "16px",
  },
  metaItem: {
    display: "flex",
    alignItems: "center",
    gap: "4px",
    fontSize: "13px",
    color: "#6b7280",
  },
  metaIcon: {
    fontSize: "14px",
  },
  cardFooter: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    paddingTop: "12px",
    borderTop: "1px solid #f0f0f0",
    color: "#2563eb",
  },
  viewText: {
    fontSize: "13px",
    fontWeight: 500,
  },
  viewArrow: {
    fontSize: "16px",
  },
  loadingContainer: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    padding: "80px",
  },
  loadingSpinner: {
    width: "40px",
    height: "40px",
    border: "4px solid #f0f0f0",
    borderTopColor: "#2563eb",
    borderRadius: "50%",
    animation: "spin 1s linear infinite",
  },
  loadingText: {
    marginTop: "16px",
    color: "#9ca3af",
    fontSize: "14px",
  },
  errorContainer: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    padding: "80px",
    background: "#ffffff",
    borderRadius: "12px",
    boxShadow: "0 4px 20px rgba(0, 0, 0, 0.08)",
  },
  errorIcon: {
    fontSize: "48px",
    marginBottom: "16px",
  },
  errorText: {
    color: "#dc2626",
    fontSize: "14px",
  },
  emptyContainer: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    padding: "80px",
    background: "#ffffff",
    borderRadius: "12px",
    boxShadow: "0 4px 20px rgba(0, 0, 0, 0.08)",
  },
  emptyIcon: {
    fontSize: "64px",
    marginBottom: "16px",
  },
  emptyTitle: {
    fontSize: "20px",
    fontWeight: 600,
    color: "#1a1a1a",
    margin: 0,
    marginBottom: "8px",
  },
  emptyText: {
    color: "#9ca3af",
    fontSize: "14px",
    margin: 0,
  },
};