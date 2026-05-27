import type { OptunaData } from "@/types";
import EChartsChart from "@/components/EChartsChart";

interface OptunaChartsProps {
  data: OptunaData | null;
}

export default function OptunaCharts({ data }: OptunaChartsProps) {
  if (!data) {
    return (
      <div
        data-ql-id="RUN-OPT-EMPTY"
        style={{
          padding: 24,
          color: "#999",
          textAlign: "center",
          background: "#fafafa",
          borderRadius: 8,
          border: "1px solid #e8e8e8",
        }}
      >
        暂无参数优化数据
      </div>
    );
  }

  const { study_name, best_params, best_value, optimization_history, param_importances, parallel_coordinate, contour } = data;

  return (
    <div data-ql-id="RUN-OPT-CONTAINER">
      <div
        data-ql-id="RUN-OPT-HEADER"
        style={{
          marginBottom: 16,
          padding: "12px 16px",
          background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
          borderRadius: 8,
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
        <div data-ql-id="RUN-OPT-BESTPARAMS" style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: "#555" }}>
            最优参数
          </div>
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
                  background: "#f8f9fa",
                  borderRadius: 4,
                  border: "1px solid #e8e8e8",
                  fontSize: 13,
                }}
              >
                <span style={{ color: "#888" }}>{p.name}</span>
                <span style={{ fontWeight: 600, color: "#333" }}>
                  {typeof p.value === "number" ? p.value.toFixed(4) : String(p.value)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div data-ql-id="RUN-OPT-CHARTS" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {optimization_history && (
          <div data-ql-id="RUN-OPT-HISTORY" style={chartSectionStyle}>
            <div style={chartTitleStyle}>优化历史</div>
            <EChartsChart qlId="RUN-OPT-HISTORY-CHART" option={optimization_history} style={{ height: 350 }} />
          </div>
        )}
        {param_importances && (
          <div data-ql-id="RUN-OPT-IMPORTANCE" style={chartSectionStyle}>
            <div style={chartTitleStyle}>参数重要性</div>
            <EChartsChart qlId="RUN-OPT-IMPORTANCE-CHART" option={param_importances} style={{ height: 350 }} />
          </div>
        )}
        {parallel_coordinate && (
          <div data-ql-id="RUN-OPT-PARALLEL" style={chartSectionStyle}>
            <div style={chartTitleStyle}>平行坐标</div>
            <EChartsChart qlId="RUN-OPT-PARALLEL-CHART" option={parallel_coordinate} style={{ height: 400 }} />
          </div>
        )}
        {contour && (
          <div data-ql-id="RUN-OPT-CONTOUR" style={chartSectionStyle}>
            <div style={chartTitleStyle}>等高线</div>
            <EChartsChart qlId="RUN-OPT-CONTOUR-CHART" option={contour} style={{ height: 400 }} />
          </div>
        )}
      </div>
    </div>
  );
}

const chartSectionStyle: React.CSSProperties = {
  background: "#fff",
  borderRadius: 8,
  border: "1px solid #e8e8e8",
  padding: 12,
};

const chartTitleStyle: React.CSSProperties = {
  fontSize: 14,
  fontWeight: 600,
  color: "#555",
  marginBottom: 8,
};