/**
 * 数据预加载机制 - 核心设计说明
 * 
 * 【重要特性】所有数据打包到 HTML
 * 
 * 设计目的：
 * 1. 支持 file:// 协议访问（避免 CORS 问题）
 * 2. 实现离线浏览能力
 * 3. 提升页面加载性能（一次加载，无需多次网络请求）
 * 
 * 工作原理：
 * 1. 构建阶段（builder.py）：将所有 JSON 数据文件读取并序列化为 JSON 字符串
 * 2. 注入阶段：将 JSON 数据嵌入到 index.html 的 <script> 标签中
 *    格式：window.__DATA__ = { "data/xxx.json": {...}, "r1/data/xxx.json": {...} }
 * 3. 运行阶段：前端通过 fetchJson() 从 window.__DATA__ 读取数据
 * 
 * 数据键格式：
 * - 公共数据: data/{filename}.json
 * - 回测数据: r{runId}/data/{filename}.json
 * 
 * 注意事项（修改此文件时必须保持）：
 * 1. 必须优先从 window.__DATA__ 读取数据
 * 2. 不允许使用 fetch() 等网络请求获取数据
 * 3. 数据缺失时应抛出明确错误，提示数据未预加载
 * 4. 保持与 builder.py 中 _build_preload_script() 的数据键格式一致
 * 
 * 修改记录：
 * - 创建：实现数据预加载机制，支持 file:// 协议离线访问
 */
declare global {
  interface Window {
    __DATA__: Record<string, unknown>;
  }
}

const __DATA__: Record<string, unknown> = window.__DATA__ || {};

function dataKey(relPath: string, runId?: number): string {
  const base = runId !== undefined ? `r${runId}/data` : "data";
  return `${base}/${relPath}`;
}

/**
 * 从预加载的 window.__DATA__ 中获取 JSON 数据
 * 
 * @param relPath - 数据文件相对路径（不含 data/ 前缀）
 * @param runId - 回测 ID（可选，用于回测相关数据）
 * @returns Promise 包装的数据对象
 * @throws Error 数据未预加载时抛出错误
 */
export async function fetchJson<T>(
  relPath: string,
  runId?: number
): Promise<T> {
  const key = dataKey(relPath, runId);

  if (key in __DATA__) {
    return __DATA__[key] as T;
  }

  throw new Error(`数据未预加载: ${key}`);
}

/**
 * 清空数据缓存（用于测试或特殊场景）
 */
export function clearCache(): void {
  Object.keys(__DATA__).forEach((k) => delete __DATA__[k]);
}