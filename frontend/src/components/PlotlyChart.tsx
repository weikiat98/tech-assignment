import createPlotlyComponent from "react-plotly.js/factory";
// @ts-expect-error - the dist bundle ships without type declarations
import Plotly from "plotly.js-basic-dist-min";
import type { Layout } from "plotly.js";
import type { Chart } from "../lib/types";

const Plot = createPlotlyComponent(Plotly);

// The app's dark theme (index.css tokens). The backend's colorway and trace colours are left as they are.
const INK = "#e6ecea";
const MUTED = "#9aa9af";
const GRID = "#2a3a42";
const AXIS = "#3b4e57";

/** Dark layout over the backend's figure: transparent ground, theme fonts, grid and axis colours. */
export function darkLayout(layout: Partial<Layout>): Partial<Layout> {
  const axis = (a: Partial<Layout>["xaxis"]) => ({
    ...a,
    color: MUTED,
    gridcolor: GRID,
    linecolor: AXIS,
    zerolinecolor: AXIS,
    tickfont: { ...a?.tickfont, color: MUTED },
  });
  const title = typeof layout.title === "string" ? { text: layout.title } : layout.title;
  return {
    ...layout,
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { ...layout.font, family: "IBM Plex Sans, system-ui, sans-serif", color: INK },
    title: title ? { ...title, font: { ...title.font, color: INK } } : title,
    xaxis: axis(layout.xaxis),
    yaxis: axis(layout.yaxis),
    legend: { ...layout.legend, font: { ...layout.legend?.font, color: MUTED }, bgcolor: "rgba(0,0,0,0)" },
    hoverlabel: { bgcolor: "#1c2930", bordercolor: AXIS, font: { color: INK } },
  };
}

export default function PlotlyChart({ chart, height = 340 }: { chart: Chart; height?: number }) {
  return (
    <Plot
      data={chart.spec.data}
      layout={{ ...darkLayout(chart.spec.layout), autosize: true, height }}
      config={{ displaylogo: false, responsive: true }}
      style={{ width: "100%" }}
      useResizeHandler
    />
  );
}
