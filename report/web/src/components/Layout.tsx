import { Link, useLocation } from "react-router-dom";

interface LayoutProps {
  children: React.ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const location = useLocation();
  const isHome = location.hash === "#/" || location.hash === "";

  return (
    <div style={styles.body}>
      <header style={styles.header} data-ql-id="LAY-HDR-CONTAINER">
        <div style={styles.headerContent}>
          <div style={styles.logo} data-ql-id="LAY-HDR-LOGO">
            <div style={styles.logoIcon}>📊</div>
            <span style={styles.logoText}>Quant Report</span>
          </div>
          <div style={styles.headerRight}>
            <span style={styles.version} data-ql-id="LAY-HDR-VERSION">v0.2.0</span>
          </div>
        </div>
      </header>
      
      {!isHome && (
        <div style={styles.breadcrumb}>
          <nav style={styles.breadcrumbNav} data-ql-id="LAY-HDR-BREADCRUMB">
            <Link to="/" style={styles.breadcrumbLink}>
              <span style={styles.breadcrumbIcon}>🏠</span>
              <span>回测导航</span>
            </Link>
            <span style={styles.breadcrumbSeparator}>→</span>
            <span style={styles.breadcrumbCurrent}>
              {location.hash.match(/run\/(\d+)/) ? `回测 #${location.hash.match(/run\/(\d+)/)![1]}` : "优化详情"}
            </span>
          </nav>
        </div>
      )}
      
      <main style={styles.main} data-ql-id="LAY-MAIN-AREA">{children}</main>
      
      <footer style={styles.footer} data-ql-id="LAY-FTR-CONTAINER">
        <span style={styles.footerText}>天勤量化交易系统 · 策略回测报告</span>
      </footer>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  body: {
    fontFamily:
      '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans SC", sans-serif',
    margin: 0,
    padding: 0,
    color: "#1a1a1a",
    background: "#f0f2f5",
    minHeight: "100vh",
    display: "flex",
    flexDirection: "column",
  },
  header: {
    background: "linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%)",
    padding: "16px 24px",
    boxShadow: "0 4px 20px rgba(30, 58, 95, 0.3)",
    position: "sticky",
    top: 0,
    zIndex: 100,
  },
  headerContent: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    maxWidth: "1400px",
    margin: "0 auto",
  },
  logo: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
  },
  logoIcon: {
    fontSize: "24px",
  },
  logoText: {
    fontSize: "18px",
    fontWeight: 700,
    color: "#ffffff",
    letterSpacing: "0.5px",
  },
  headerRight: {
    display: "flex",
    alignItems: "center",
  },
  version: {
    fontSize: "12px",
    color: "rgba(255, 255, 255, 0.7)",
    background: "rgba(255, 255, 255, 0.1)",
    padding: "4px 10px",
    borderRadius: "12px",
  },
  breadcrumb: {
    padding: "12px 24px",
    background: "#ffffff",
    borderBottom: "1px solid #e5e7eb",
  },
  breadcrumbNav: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    maxWidth: "1400px",
    margin: "0 auto",
  },
  breadcrumbLink: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    color: "#2563eb",
    textDecoration: "none",
    fontSize: "13px",
    fontWeight: 500,
    transition: "color 0.2s",
  },
  breadcrumbIcon: {
    fontSize: "14px",
  },
  breadcrumbSeparator: {
    color: "#9ca3af",
    fontSize: "14px",
  },
  breadcrumbCurrent: {
    color: "#374151",
    fontSize: "13px",
    fontWeight: 600,
  },
  main: {
    flex: 1,
    padding: "24px",
    maxWidth: "1400px",
    margin: "0 auto",
    width: "100%",
    boxSizing: "border-box",
  },
  footer: {
    padding: "16px 24px",
    background: "#ffffff",
    borderTop: "1px solid #e5e7eb",
    marginTop: "auto",
  },
  footerText: {
    fontSize: "12px",
    color: "#6b7280",
    textAlign: "center",
    display: "block",
  },
};