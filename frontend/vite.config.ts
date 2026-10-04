import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const api = process.env.API_UPSTREAM ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
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
