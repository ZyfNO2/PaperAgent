import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Session 53: 组件单元测试 — jsdom + RTL
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
