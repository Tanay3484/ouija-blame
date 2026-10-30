import { defineConfig } from "vite";

// In dev, /api goes to the Python backend on :8000. In production the backend serves this build.
export default defineConfig({
  base: "./",
  server: { proxy: { "/api": "http://localhost:8000" } },
  build: { target: "es2022", sourcemap: false },
  test: { environment: "node", include: ["src/**/*.test.ts"] },
});
