import { useState, useMemo } from "react";
import type { OptunaData } from "@/types";
import EChartsChart from "@/components/charts/EChartsChart";
import QlPanel from "@/components/layout/QlPanel";
import { qlIdNameMap } from "@/data/qlIdMapping";

interface OptunaChartsProps {
  data: OptunaData | null;
}

/** 从原始试验数据构建 ECharts option */
function buildContourOption(
  trials: { params: Record<string, number>; value: number | null }[],
  xParam: string,
  yParam: string,
): Record<string, any> | null {
  const values: number[] = [];
  const points: [number, number, number][] = [];
  for (const t of trials) {
    const xv = t.params[xParam];
    const v = t.value;
    if (xv === undefined || v === null) continue;
    if (xParam === yParam) {
      // X=Y 时：展⽰参数值与目标值的关系，X=参数值, Y=目标值, color=目标值
      points.push([xv, v, v]);
    } else {
      const yv = t.params[yParam];
      if (yv === undefined) continue;
      points.push([xv, yv, v]);
    }
    values.push(v);
  }
  if (points.length === 0) return null;

  const minV = Math.min(...values);
  const maxV = Math.max(...values);
  return {
    tooltip: {
      formatter: (params: any) => {
        try {
          const item = Array.isArray(params) ? params[0] : params;
          const val = item?.value ?? item?.data ?? item;
          const objVal = Array.isArray(val) ? val[2] : val;
          const label = xParam === yParam ? `${xParam} vs 目标值` : `${xParam} vs ${yParam}`;
          return `${label}<br/>目标值=${Number(objVal).toFixed(6)}`;
        } catch {
          return "";
        }
      },
    },
    visualMap: {
      min: minV, max: maxV,
      inRange: {
        color: ["#313695", "#4575b4", "#74add1", "#abd9e9","#fee090", "#fdae61", "#f46d43", "#d73027", "#a50026"],
      },
      calculable: true, orient: "vertical", right: 10, top: 20, bottom: 40,
    },
    xAxis: { type: "value", name: xParam, nameLocation: "center", nameGap: 25 },
    yAxis: { type: "value", name: xParam === yParam ? "目标值" : yParam, nameLocation: "center", nameGap: 35 },
    grid: { left: 70, right: 60, top: 20, bottom: 40 },
    series: [{
      type: "scatter", data: points, symbolSize: 8,
    }],
  };
}

export default function OptunaCharts({ data }: OptunaChartsProps) {
  const [xParam, setXParam] = useState("");
  const [yParam, setYParam] = useState("");

const paramNames = data?.contours?.param_names ?? [];
  console.log("[OptunaCharts] contours:", data?.contours, "xParam:", xParam, "yParam:", yParam);
  if (!xParam && paramNames.length > 0) setXParam(paramNames[0]);
  if (!yParam && paramNames.length > 1) setYParam(paramNames[1]);

  const contourOption = useMemo(
    () => {
      if (!data?.contours || !xParam || !yParam) return null;
      const opt = buildContourOption(data.contours.trials, xParam, yParam);
      console.log("[OptunaCharts] contourOption:", opt ? "built" : "null", "name:", opt ? Object.keys(opt) : "null");
      return opt;
    },
    [data?.contours, xParam, yParam],
  );

  if (!data) {
    return (
      <QlPanel qlId="RUN-OPT-EMPTY" name={qlIdNameMap["RUN-OPT-EMPTY"]}>
        <div className="text-slate-400 text-center p-6">
          暂无参数优化数据
        </div>
      </QlPanel>
    );
  }

  const { study_name, best_params, best_value, optimization_history, param_importances, parallel_coordinate, contours } = data;
  

  return (
    <div data-ql-id="RUN-OPT-CONTAINER">
      <div
        data-ql-id="RUN-OPT-HEADER"
        className="mb-5 py-3.5 px-5 rounded-lg text-white"
        style={{ background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)" }}
      >
        <div data-ql-id="RUN-OPT-STUDYNAME" className="text-base font-semibold">
          {study_name}
        </div>
        {best_value != null && (
          <div data-ql-id="RUN-OPT-BESTVALUE" className="text-sm mt-1 opacity-90">
            最优目标值: {Number(best_value).toFixed(4)}
          </div>
        )}
      </div>

      {best_params.length > 0 && (
        <QlPanel
          qlId="RUN-OPT-BESTPARAMS"
          name={qlIdNameMap["RUN-OPT-BESTPARAMS"]}
          compact
          className="mb-5"
        >
          <div
            data-ql-id="RUN-OPT-PARAMLIST"
            className="grid gap-1.5"
            style={{ gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))" }}
          >
            {best_params.map((p) => (
              <div
                key={p.name}
                data-ql-id={`RUN-OPT-PARAM-${p.name.toUpperCase()}`}
                className="flex justify-between py-1.5 px-3 bg-slate-50 rounded border border-slate-200 text-[13px]"
              >
                <span className="text-slate-400">{p.name}</span>
                <span className="font-semibold text-slate-700">
                  {typeof p.value === "number" ? p.value.toFixed(4) : String(p.value)}
                </span>
              </div>
            ))}
          </div>
        </QlPanel>
      )}

      <div data-ql-id="RUN-OPT-CHARTS" className="flex flex-col gap-5">
        {optimization_history && (
          <QlPanel
            qlId="RUN-OPT-HISTORY"
            name={qlIdNameMap["RUN-OPT-HISTORY"]}
            compact
          >
            <EChartsChart qlId="RUN-OPT-HISTORY-CHART" option={optimization_history} className="w-full h-[350px]" />
          </QlPanel>
        )}
        {param_importances ? (
          <QlPanel
            qlId="RUN-OPT-IMPORTANCE"
            name={qlIdNameMap["RUN-OPT-IMPORTANCE"]}
            compact
          >
            <EChartsChart qlId="RUN-OPT-IMPORTANCE-CHART" option={param_importances} className="w-full h-[350px]" />
          </QlPanel>
        ) : (
          <QlPanel
            qlId="RUN-OPT-IMPORTANCE"
            name={qlIdNameMap["RUN-OPT-IMPORTANCE"]}
            compact
          >
            <div className="text-slate-400 text-center py-10">
              参数重要性无法计算（trial 数量不足或目标值无显著差异）
            </div>
          </QlPanel>
        )}
        {parallel_coordinate && (
          <QlPanel
            qlId="RUN-OPT-PARALLEL"
            name={qlIdNameMap["RUN-OPT-PARALLEL"]}
            compact
          >
            <EChartsChart qlId="RUN-OPT-PARALLEL-CHART" option={parallel_coordinate} className="w-full h-[400px]" />
          </QlPanel>
        )}
        {contours && paramNames.length > 0 && (
          <QlPanel
            qlId="RUN-OPT-CONTOUR"
            name={qlIdNameMap["RUN-OPT-CONTOUR"]}
            compact
          >
            <div className="py-2 flex items-center gap-2">
              <label className="text-[13px] text-slate-400">X 轴</label>
              <select
                value={xParam}
                onChange={(e) => setXParam(e.target.value)}
                className="px-2 py-1 text-[13px] bg-slate-800 text-slate-200 border border-slate-600 rounded"
              >
                {paramNames.map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
              <label className="text-[13px] text-slate-400">Y 轴</label>
              <select
                value={yParam}
                onChange={(e) => setYParam(e.target.value)}
                className="px-2 py-1 text-[13px] bg-slate-800 text-slate-200 border border-slate-600 rounded"
              >
                {paramNames.map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </div>
            <EChartsChart qlId="RUN-OPT-CONTOUR-CHART" option={contourOption} className="w-full h-[400px]" />
          </QlPanel>
        )}
      </div>
    </div>
  );
}