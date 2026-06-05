import { useState, useMemo } from "react";
import type { OptunaData } from "@/types";
import EChartsChart from "@/components/EChartsChart";
import QlPanel from "@/components/QlPanel";
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

  const selectStyle: React.CSSProperties = {
    padding: "4px 8px", fontSize: 13,
    background: "#1e293b", color: "#e2e8f0",
    border: "1px solid #334155", borderRadius: 4,
  };

  if (!data) {
    return (
      <QlPanel qlId="RUN-OPT-EMPTY" name={qlIdNameMap["RUN-OPT-EMPTY"]}>
        <div style={{ color: "#94a3b8", textAlign: "center", padding: 24 }}>
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
        style={{
          marginBottom: 20,
          padding: "14px 20px",
          background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
          borderRadius: 10,
          color: "#fff",
        }}
      >
        <div data-ql-id="RUN-OPT-STUDYNAME" style={{ fontSize: 16, fontWeight: 600 }}>
          {study_name}
        </div>
        {best_value != null && (
          <div data-ql-id="RUN-OPT-BESTVALUE" style={{ fontSize: 14, marginTop: 4, opacity: 0.9 }}>
            最优目标值: {Number(best_value).toFixed(4)}
          </div>
        )}
      </div>

      {best_params.length > 0 && (
        <QlPanel
          qlId="RUN-OPT-BESTPARAMS"
          name={qlIdNameMap["RUN-OPT-BESTPARAMS"]}
          compact
          style={{ marginBottom: 20 }}
        >
          <div
            data-ql-id="RUN-OPT-PARAMLIST"
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
              gap: 6,
            }}
          >
            {best_params.map((p) => (
              <div
                key={p.name}
                data-ql-id={`RUN-OPT-PARAM-${p.name.toUpperCase()}`}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  padding: "6px 12px",
                  background: "#f8fafc",
                  borderRadius: 4,
                  border: "1px solid #e2e8f0",
                  fontSize: 13,
                }}
              >
                <span style={{ color: "#94a3b8" }}>{p.name}</span>
                <span style={{ fontWeight: 600, color: "#334155" }}>
                  {typeof p.value === "number" ? p.value.toFixed(4) : String(p.value)}
                </span>
              </div>
            ))}
          </div>
        </QlPanel>
      )}

      <div data-ql-id="RUN-OPT-CHARTS" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        {optimization_history && (
          <QlPanel
            qlId="RUN-OPT-HISTORY"
            name={qlIdNameMap["RUN-OPT-HISTORY"]}
            compact
          >
            <EChartsChart qlId="RUN-OPT-HISTORY-CHART" option={optimization_history} style={{ height: 350 }} />
          </QlPanel>
        )}
        {param_importances ? (
          <QlPanel
            qlId="RUN-OPT-IMPORTANCE"
            name={qlIdNameMap["RUN-OPT-IMPORTANCE"]}
            compact
          >
            <EChartsChart qlId="RUN-OPT-IMPORTANCE-CHART" option={param_importances} style={{ height: 350 }} />
          </QlPanel>
        ) : (
          <QlPanel
            qlId="RUN-OPT-IMPORTANCE"
            name={qlIdNameMap["RUN-OPT-IMPORTANCE"]}
            compact
          >
            <div style={{ color: "#94a3b8", textAlign: "center", padding: 40 }}>
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
            <EChartsChart qlId="RUN-OPT-PARALLEL-CHART" option={parallel_coordinate} style={{ height: 400 }} />
          </QlPanel>
        )}
        {contours && paramNames.length > 0 && (
          <QlPanel
            qlId="RUN-OPT-CONTOUR"
            name={qlIdNameMap["RUN-OPT-CONTOUR"]}
            compact
          >
            <div style={{ padding: "8px 0", display: "flex", alignItems: "center", gap: 8 }}>
              <label style={{ fontSize: 13, color: "#94a3b8" }}>X 轴</label>
              <select value={xParam} onChange={e => setXParam(e.target.value)} style={selectStyle}>
                {paramNames.map(n => <option key={n} value={n}>{n}</option>)}
              </select>
              <label style={{ fontSize: 13, color: "#94a3b8" }}>Y 轴</label>
              <select value={yParam} onChange={e => setYParam(e.target.value)} style={selectStyle}>
                {paramNames.map(n => <option key={n} value={n}>{n}</option>)}
              </select>
            </div>
            <EChartsChart qlId="RUN-OPT-CONTOUR-CHART" option={contourOption} style={{ height: 400 }} />
          </QlPanel>
        )}
      </div>
    </div>
  );
}