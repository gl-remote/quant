import type { EChartsOption } from "echarts";

export type ParamValue = number | string | boolean | null;

export interface ContourTrial {
  params: Record<string, number>;
  value: number | null;
}

export interface ContourMeta {
  param_names: string[];
  trials: ContourTrial[];
}

export interface BestParam {
  name: string;
  value: ParamValue;
}

export interface DenormalizedScatter {
  x_label: string;
  y_label: string;
  x_vals: number[];
  y_vals: number[];
  scores: number[];
}

export interface OptunaData {
  study_name: string;
  best_params: BestParam[];
  best_value: number | null;
  optimization_history: EChartsOption | null;
  param_importances: EChartsOption | null;
  parallel_coordinate: EChartsOption | null;
  contours: ContourMeta | null;
}

export type { EChartsOption };
