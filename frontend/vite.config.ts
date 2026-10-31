import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const api = env.VITE_API_TARGET || "http://127.0.0.1:8000";
  return {
    plugins: [react()],
    server: {
      port: Number(env.VITE_PORT || 5173),
      strictPort: false,
      proxy: {
        "/api": { target: api, changeOrigin: true },
        "/ws": { target: api.replace(/^http/, "ws"), ws: true, changeOrigin: true },
      },
    },
    preview: {
      port: 4173,
      proxy: {
        "/api": { target: api, changeOrigin: true },
        "/ws": { target: api.replace(/^http/, "ws"), ws: true, changeOrigin: true },
      },
    },
    test: { environment: "node" },
  };
});
