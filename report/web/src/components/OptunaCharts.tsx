import type { OptunaData } from "@/types";
import EChartsChart from "@/components/EChartsChart";
import QlPanel from "@/components/QlPanel";
import { qlIdNameMap } from "@/data/qlIdMapping";

interface OptunaChartsProps {
  data: OptunaData | null;
}

export default function OptunaCharts({ data }: OptunaChartsProps) {
  if (!data) {
    return (
      <QlPanel qlId="RUN-OPT-EMPTY" name={qlIdNameMap["RUN-OPT-EMPTY"]}>
        <div style={{ color: "#94a3b8", textAlign: "center", padding: 24 }}>
          暂无参数优化数据
        </div>
      </QlPanel>
    );
  }

  const { study_name, best_params, best_value, optimization_history, param_importances, parallel_coordinate, contour } = data;

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
        {param_importances && (
          <QlPanel
            qlId="RUN-OPT-IMPORTANCE"
            name={qlIdNameMap["RUN-OPT-IMPORTANCE"]}
            compact
          >
            <EChartsChart qlId="RUN-OPT-IMPORTANCE-CHART" option={param_importances} style={{ height: 350 }} />
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
        {contour && (
          <QlPanel
            qlId="RUN-OPT-CONTOUR"
            name={qlIdNameMap["RUN-OPT-CONTOUR"]}
            compact
          >
            <EChartsChart qlId="RUN-OPT-CONTOUR-CHART" option={contour} style={{ height: 400 }} />
          </QlPanel>
        )}
      </div>
    </div>
  );
}