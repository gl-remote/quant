/**
 * 数据获取 Hook
 * 
 * 【功能说明】
 * - 封装了从预加载的 window.__DATA__ 中获取数据的逻辑
 * - 提供加载状态、数据和错误状态的统一管理
 * - 支持组件卸载时取消请求（避免内存泄漏）
 * 
 * 【数据流】
 * 1. 组件渲染 → 触发 useEffect → 设置 loading=true
 * 2. 调用 fetchJson() → 从 window.__DATA__ 读取数据
 * 3. 成功 → 更新 state.data
 * 4. 失败 → 更新 state.error
 * 5. 组件卸载 → 标记 cancelled=true，忽略后续更新
 * 
 * 【使用示例】
 * ```tsx
 * const { data, loading, error } = useFetchJson<RunInfo>("run.json", 1);
 * ```
 */

import { useState, useEffect } from "react";
import { fetchJson } from "@/data/loader";

/**
 * 数据获取状态接口
 * 
 * @template T 数据类型
 */
interface FetchState<T> {
  data: T | null;       // 数据（加载成功时）
  loading: boolean;     // 是否正在加载
  error: string | null; // 错误信息（加载失败时）
}

/**
 * 数据获取 Hook
 * 
 * @template T 数据类型
 * @param relPath 数据文件相对路径（不含 data/ 前缀）
 * @param runId 回测 ID（可选，用于回测相关数据）
 * @returns FetchState<T> 包含数据、加载状态和错误信息
 */
export function useFetchJson<T>(
  relPath: string,
  runId?: number
): FetchState<T> {
  // 初始化状态：loading=true，data=null，error=null
  const [state, setState] = useState<FetchState<T>>({
    data: null,
    loading: true,
    error: null,
  });

  useEffect(() => {
    // 标记是否已取消（用于组件卸载时避免状态更新）
    let cancelled = false;

    // 如果路径为空，直接返回空数据
    if (!relPath) {
      setState({ data: null, loading: false, error: null });
      return () => { cancelled = true; };
    }

    // 开始加载：重置错误，设置 loading=true
    setState((prev) => ({ ...prev, loading: true, error: null }));

    // 获取数据
    fetchJson<T>(relPath, runId)
      .then((data) => {
        // 只有未取消时才更新状态
        if (!cancelled) {
          setState({ data, loading: false, error: null });
        }
      })
      .catch((err: Error) => {
        // 只有未取消时才更新状态
        if (!cancelled) {
          setState({ data: null, loading: false, error: err.message });
        }
      });

    // 清理函数：组件卸载时标记为已取消
    return () => {
      cancelled = true;
    };
  }, [relPath, runId]); // 依赖项：路径或回测ID变化时重新获取

  return state;
}