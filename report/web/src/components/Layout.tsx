import { Link, useLocation } from "react-router-dom";

interface LayoutProps {
  children: React.ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const location = useLocation();
  const isHome = location.hash === "#/" || location.hash === "";

  return (
    <div className="font-sans m-0 p-0 text-slate-800 bg-slate-100 min-h-screen flex flex-col">
      <header data-ql-id="LAY-HDR-CONTAINER" className="sticky top-0 z-[100] bg-gradient-to-br from-[#1e3a5f] to-[#2d5a87] px-6 py-4 shadow-lg shadow-[#1e3a5f]/30">
        <div className="flex justify-between items-center max-w-[1400px] mx-auto">
          <div data-ql-id="LAY-HDR-LOGO" className="flex items-center gap-2.5">
            <div className="text-2xl">📊</div>
            <span className="text-lg font-bold text-white tracking-wide">Quant Report</span>
          </div>
          <div className="flex items-center">
            <span data-ql-id="LAY-HDR-VERSION" className="text-xs text-white/70 bg-white/10 px-2.5 py-1 rounded-xl">
              v0.2.0
            </span>
          </div>
        </div>
      </header>

      {!isHome && (
        <div className="px-6 py-3 bg-white border-b border-slate-200">
          <nav data-ql-id="LAY-HDR-BREADCRUMB" className="flex items-center gap-2 max-w-[1400px] mx-auto">
            <Link to="/" className="flex items-center gap-1.5 text-[13px] font-medium text-blue-600 no-underline">
              <span className="text-sm">🏠</span>
              <span>回测导航</span>
            </Link>
            <span className="text-sm text-slate-400">→</span>
            <span className="text-[13px] font-semibold text-slate-600">
              {location.hash.match(/run\/(\d+)/)
                ? `回测 #${location.hash.match(/run\/(\d+)/)![1]}`
                : "回测详情"}
            </span>
          </nav>
        </div>
      )}

      <main data-ql-id="LAY-MAIN-AREA" className="flex-1 py-8 px-7 max-w-[1400px] mx-auto w-full box-border">
        {children}
      </main>

      <footer data-ql-id="LAY-FTR-CONTAINER" className="py-4 px-6 bg-white border-t border-slate-200 mt-auto">
        <span className="block text-xs text-slate-400 text-center">策略工具箱 · 回测报告</span>
      </footer>
    </div>
  );
}