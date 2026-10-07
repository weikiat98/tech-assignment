import createPlotlyComponent from "react-plotly.js/factory";
// @ts-expect-error - the dist bundle ships without type declarations
import Plotly from "plotly.js-basic-dist-min";
import type { Chart } from "../lib/types";

const Plot = createPlotlyComponent(Plotly);

export default function PlotlyChart({ chart }: { chart: Chart }) {
  return (
    <Plot
      data={chart.spec.data}
      layout={{ ...chart.spec.layout, autosize: true, height: 340, paper_bgcolor: "white", plot_bgcolor: "white" }}
      config={{ displaylogo: false, responsive: true }}
      style={{ width: "100%" }}
      useResizeHandler
    />
  );
}
