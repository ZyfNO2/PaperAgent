import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Session 52: 脚手架基线 — 端口 18183, /api 代理到 18181
// 旧 apps/web (18182) 与新 apps/web-react (18183) 并行存在, 直到 Session 56 决定切换
export default defineConfig({
  plugins: [react()],
  server: {
    port: 18183,
    strictPort: true,
    host: "127.0.0.1",
    proxy: {
      "/api": {
        target: "http://127.0.0.1:18181",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
