import createPlotlyComponent from "react-plotly.js/factory";
import type { PlotParams } from "react-plotly.js";

const Plot = createPlotlyComponent((window as any).Plotly) as React.ComponentType<
  PlotParams
>;

export default Plot;