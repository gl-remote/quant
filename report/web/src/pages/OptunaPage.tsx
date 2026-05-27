/**
 * @file OptunaPage.tsx
 * @description Optuna参数优化详情页面组件
 * 展示参数优化的结果，包括优化历史、参数重要性、平行坐标图等
 * 提供返回回测结果的导航链接
 */

import { useParams, Link } from "react-router-dom";
import { useFetchJson } from "@/hooks/useFetchJson";
import OptunaCharts from "@/components/OptunaCharts";
import type { OptunaData } from "@/types";

/**
 * OptunaPage组件
 * Optuna参数优化详情页面，展示优化结果的各种图表
 * 
 * @component
 * @returns {JSX.Element} 渲染后的Optuna详情页面组件
 */
export default function OptunaPage() {
  const { id } = useParams<{ id: string }>();
  const runId = Number(id);

  // 获取Optuna优化数据
  const { data: optuna, loading, error } = useFetchJson<OptunaData | null>(
    "optuna.json",
    runId
  );

  // 加载状态
  if (loading) {
    return (
      <p data-ql-id="OPT-PG-LOADING" style={{ textAlign: "center", padding: 60, color: "#888" }}>
        加载中...
      </p>
    );
  }

  // 错误或无数据状态
  if (error || !optuna || !optuna.study_name) {
    return (
      <div data-ql-id="OPT-PG-ERROR">
        <p style={{ textAlign: "center", color: "#999", padding: 40 }}>
          该 run 无优化数据
        </p>
        <div style={{ textAlign: "center" }}>
          <Link data-ql-id="OPT-PG-BACKLINK" to={`/run/${runId}`} style={styles.backLink}>
            &larr; 返回回测结果
          </Link>
        </div>
      </div>
    );
  }

  // 正常显示Optuna优化结果
  return (
    <div data-ql-id="OPT-PG-CONTAINER">
      <div style={styles.header}>
        <h1 style={styles.title}>参数优化</h1>
        <Link data-ql-id="OPT-PG-BACKLINK" to={`/run/${runId}`} style={styles.backLink}>
          &larr; 返回回测结果
        </Link>
      </div>
      <OptunaCharts data={optuna} />
    </div>
  );
}

/**
 * 样式对象
 * 定义了OptunaPage组件中所有元素的样式
 */
const styles: Record<string, React.CSSProperties> = {
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "16px",
  },
  title: {
    fontSize: "20px",
    fontWeight: 700,
    margin: 0,
    color: "#222",
  },
  backLink: {
    color: "#2563eb",
    textDecoration: "none",
    fontSize: "13px",
    fontWeight: 600,
  },
};
