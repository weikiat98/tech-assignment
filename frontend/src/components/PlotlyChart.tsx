import createPlotlyComponent from "react-plotly.js/factory";
// @ts-expect-error - the dist bundle ships without type declarations
import Plotly from "plotly.js-basic-dist-min";
import type { Chart } from "../lib/types";

const Plot = createPlotlyComponent(Plotly);

export default function PlotlyChart({ chart, height = 340 }: { chart: Chart; height?: number }) {
  return (
    <Plot
      data={chart.spec.data}
      layout={{ ...chart.spec.layout, autosize: true, height, paper_bgcolor: "white", plot_bgcolor: "white" }}
      config={{ displaylogo: false, responsive: true }}
      style={{ width: "100%" }}
      useResizeHandler
    />
  );
}
