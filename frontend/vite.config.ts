import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const api = process.env.API_UPSTREAM ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // The only chunk above 500 kB is the lazily loaded Plotly basic bundle (~1.1 MB, 380 kB gzipped).
  build: { chunkSizeWarningLimit: 1200 },
  server: {
    port: 5173,
    proxy: {
      "/api": api,
      "/healthz": api,
      "/readyz": api,
      "/ws": { target: api.replace(/^http/, "ws"), ws: true },
    },
  },
  test: { environment: "jsdom" },
});
