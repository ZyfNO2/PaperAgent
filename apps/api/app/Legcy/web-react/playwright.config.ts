import { defineConfig, devices } from "@playwright/test";

// Session 52: web-react e2e 配置
// - 默认 baseURL = 新前端 dev server (18183)
// - 用 chromium, 不依赖 webServer 启动, 由外层脚本先 `npm run dev`
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:18183",
    trace: "off",
    headless: true,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
