import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Local dev talks to the API container by proxy, so the browser only ever
    // sees same-origin requests and no CORS config is needed in development.
    proxy: {
      "/api": { target: process.env.API_URL || "http://localhost:8000", changeOrigin: true },
      "/health": { target: process.env.API_URL || "http://localhost:8000", changeOrigin: true },
    },
  },
});
