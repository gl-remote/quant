import { Link, useLocation } from "react-router-dom";
import { Breadcrumb } from "antd";

interface LayoutProps {
  children: React.ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const location = useLocation();

  const match = location.hash.match(/run\/(\d+)/);
  const isHome = location.hash === "#/" || location.hash === "";

  const breadcrumbItems = isHome
    ? [{ title: "🏠 回测导航" }]
    : [
        { title: <Link to="/">🏠 回测导航</Link> },
        { title: match ? `回测 #${match[1]}` : "回测详情" },
      ];

  return (
    <div className="font-sans m-0 p-0 text-text bg-page min-h-screen flex flex-col">
      <header data-ql-id="LAY-HDR-CONTAINER" className="sticky top-0 z-[100] bg-gradient-to-br from-hero-start to-hero-end px-6 py-4 shadow-lg">
        <div className="flex justify-between items-center max-w-[1400px] mx-auto">
          <div data-ql-id="LAY-HDR-LOGO" className="flex items-center gap-2.5">
            <div className="text-2xl">📊</div>
            <span className="text-lg font-bold text-text-inverse tracking-wide">Quant Report</span>
          </div>
          <div className="flex items-center">
            <span data-ql-id="LAY-HDR-VERSION" className="text-xs text-text-inverse-dim bg-text-inverse/10 px-2.5 py-1 rounded-xl">
              v0.2.0
            </span>
          </div>
        </div>
      </header>

      {!isHome && (
        <div className="px-6 py-3 bg-surface border-b border-border">
          <nav data-ql-id="LAY-HDR-BREADCRUMB" className="max-w-[1400px] mx-auto">
            <Breadcrumb items={breadcrumbItems} />
          </nav>
        </div>
      )}

      <main data-ql-id="LAY-MAIN-AREA" className="flex-1 py-8 px-7 max-w-[1400px] mx-auto w-full box-border">
        {children}
      </main>

      <footer data-ql-id="LAY-FTR-CONTAINER" className="py-4 px-6 bg-surface border-t border-border mt-auto">
        <span className="block text-xs text-text-disabled text-center">策略工具箱 · 回测报告</span>
      </footer>
    </div>
  );
}