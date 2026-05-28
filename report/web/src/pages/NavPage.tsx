import { Link } from "react-router-dom";
import { useFetchJson } from "@/hooks/useFetchJson";
import type { NavItem } from "@/types";

export default function NavPage() {
  const { data: runs, loading, error } = useFetchJson<NavItem[]>("nav.json");

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <div className="w-10 h-10 border-4 border-slate-200 border-t-blue-600 rounded-full animate-spin" />
        <p className="mt-4 text-sm text-slate-400">加载中...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center py-20 bg-white rounded-xl shadow-md border border-slate-200">
        <div className="text-5xl mb-4">❌</div>
        <p className="text-sm text-red-600">加载失败: {error}</p>
      </div>
    );
  }

  if (!runs || runs.length === 0) {
    return (
      <div className="flex flex-col items-center py-20 bg-white rounded-xl shadow-md border border-slate-200">
        <div className="text-6xl mb-4">📊</div>
        <h2 className="text-xl font-semibold text-slate-900 mb-2">暂无回测记录</h2>
        <p className="text-sm text-slate-400">运行回测后，结果将在这里显示</p>
      </div>
    );
  }

  return (
    <div data-ql-id="NAV-PG-CONTAINER" className="max-w-[1200px] mx-auto">
      <div
        data-ql-id="NAV-PG-HERO"
        className="flex justify-between items-center bg-gradient-to-br from-[#1e3a5f] to-[#2d5a87] rounded-xl py-10 px-10 mb-8 shadow-lg shadow-[#1e3a5f]/20"
      >
        <div className="text-white">
          <h1 className="text-2xl font-bold mb-2">回测报告导航</h1>
          <p className="text-sm text-white/80">共 {runs.length} 条回测记录</p>
        </div>
        <div data-ql-id="NAV-PG-STATS" className="flex items-center gap-6">
          <div className="flex flex-col items-center">
            <span className="text-[28px] font-bold text-white">{runs.length}</span>
            <span className="text-xs text-white/70 mt-1">总回测</span>
          </div>
          <div className="w-px h-10 bg-white/20" />
          <div className="flex flex-col items-center">
            <span className="text-[28px] font-bold text-white">
              {runs.filter((r) => r.status === "completed").length}
            </span>
            <span className="text-xs text-white/70 mt-1">已完成</span>
          </div>
          <div className="w-px h-10 bg-white/20" />
          <div className="flex flex-col items-center">
            <span className="text-[28px] font-bold text-white">
              {runs.reduce((sum, r) => sum + r.symbols, 0)}
            </span>
            <span className="text-xs text-white/70 mt-1">品种数</span>
          </div>
        </div>
      </div>

      <div data-ql-id="NAV-PG-CARDLIST" className="grid grid-cols-[repeat(auto-fill,minmax(320px,1fr))] gap-7">
        {runs.map((run) => (
          <Link
            key={run.id}
            to={`/run/${run.id}`}
            className="no-underline text-inherit"
          >
            <div data-ql-id={`NAV-CARD-${run.id}`} className="bg-white rounded-xl py-7 px-6 shadow-md border border-slate-100 transition-transform hover:scale-[1.02] hover:shadow-lg">
              <div className="flex justify-between items-center mb-4 pb-3 border-b border-slate-100">
                <div className="flex gap-2 items-center">
                  <span className="text-sm font-bold text-slate-900">#{run.id}</span>
                  <span
                    className="text-[11px] font-medium px-2 py-0.5 rounded-xl"
                    style={{
                      backgroundColor: run.status === "completed" ? "#dcfce7" : "#fef3c7",
                      color: run.status === "completed" ? "#166534" : "#854d0e",
                    }}
                  >
                    {run.status === "completed" ? "完成" : "运行中"}
                  </span>
                </div>
                <div className="text-xs text-slate-400">{run.created}</div>
              </div>

              <div className="mb-4">
                <div className="text-lg font-semibold text-slate-900 mb-2">{run.strategy}</div>
                <div className="flex gap-4">
                  <span className="flex items-center gap-1 text-[13px] text-slate-500">
                    <span className="text-sm">⚙️</span>
                    {run.engine}
                  </span>
                  <span className="flex items-center gap-1 text-[13px] text-slate-500">
                    <span className="text-sm">📈</span>
                    {run.symbols} 个品种
                  </span>
                </div>
              </div>

              <div className="flex justify-between items-center pt-3 border-t border-slate-100 text-blue-600">
                <span className="text-[13px] font-medium">查看详情</span>
                <span className="text-base">→</span>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}