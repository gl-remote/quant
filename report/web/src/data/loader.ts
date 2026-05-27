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

export function clearCache(): void {
  Object.keys(__DATA__).forEach((k) => delete __DATA__[k]);
}