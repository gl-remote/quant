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

  const completedCount = runs.filter((r) => r.status === "success").length;
  const totalSymbols = runs.reduce((sum, r) => sum + r.symbols, 0);

  return (
    <div className="max-w-[1200px] mx-auto">
      {/* Hero */}
      <div className="flex justify-between items-center bg-gradient-to-br from-[#1e3a5f] to-[#2d5a87] rounded-xl py-10 px-10 mb-8 shadow-lg shadow-[#1e3a5f]/20">
        <div className="text-white">
          <h1 className="text-2xl font-bold mb-2">回测报告导航</h1>
          <p className="text-sm text-white/80">共 {runs.length} 条回测记录</p>
        </div>
        <div className="flex items-center gap-6">
          <Stat value={runs.length} label="总回测" />
          <Divider />
          <Stat value={completedCount} label="已完成" />
          <Divider />
          <Stat value={totalSymbols} label="品种数" />
        </div>
      </div>

      {/* Cards */}
      <div className="grid grid-cols-[repeat(auto-fill,minmax(320px,1fr))] gap-7">
        {runs.map((run) => (
          <NavCard key={run.id} run={run} />
        ))}
      </div>
    </div>
  );
}

const STATUS_CLASS: Record<string, string> = {
  success: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
  running: "bg-amber-100 text-amber-700",
  skipped: "bg-slate-100 text-slate-600",
};

function NavCard({ run }: { run: NavItem }) {
  const badgeClass = STATUS_CLASS[run.status] ?? "bg-slate-100 text-slate-600";

  return (
    <Link
      to={`/run/${run.id}`}
      className="no-underline text-inherit block"
    >
      <div className="bg-white rounded-xl py-6 px-6 shadow-md border border-slate-100 transition-transform hover:scale-[1.02] hover:shadow-lg">
        <div className="flex justify-between items-center">
          <div className="flex gap-2 items-center">
            <span className="text-sm font-bold text-slate-900">#{run.id}</span>
            <span className={`text-[11px] font-medium px-2 py-0.5 rounded-xl ${badgeClass}`}>
              {run.status}
            </span>
          </div>
          <div className="text-xs text-slate-400">{run.created}</div>
        </div>

        <h3 className="text-lg font-semibold text-slate-900 mt-4 mb-2">
          {run.strategy}
        </h3>
        <div className="flex gap-4 text-[13px] text-slate-500">
          <span>⚙️ {run.engine}</span>
          <span>📈 {run.symbols} 个品种</span>
        </div>
      </div>
    </Link>
  );
}

function Stat({ value, label }: { value: number; label: string }) {
  return (
    <div className="flex flex-col items-center">
      <span className="text-[28px] font-bold text-white">{value}</span>
      <span className="text-xs text-white/70 mt-1">{label}</span>
    </div>
  );
}

function Divider() {
  return <div className="w-px h-10 bg-white/20" />;
}
