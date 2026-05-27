import { Link, useLocation } from "react-router-dom";

interface LayoutProps {
  children: React.ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const location = useLocation();
  const isHome = location.hash === "#/" || location.hash === "";

  return (
    <div style={styles.body}>
      {!isHome && (
        <div style={styles.breadcrumb}>
          <Link to="/" style={styles.link}>
            &larr; 返回导航
          </Link>
        </div>
      )}
      <main>{children}</main>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  body: {
    fontFamily:
      '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans SC", sans-serif',
    margin: 0,
    padding: "20px",
    color: "#333",
    background: "#f5f6fa",
    minHeight: "100vh",
  },
  breadcrumb: {
    marginBottom: "16px",
  },
  link: {
    color: "#2563eb",
    textDecoration: "none",
    fontSize: "14px",
  },
};