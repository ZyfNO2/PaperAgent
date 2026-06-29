// Session 52: 静态配置基线 — 单一来源
// 后续 S53+ 把运行时常量 (theme / feature flag) 移到 context
export const APP_CONFIG = {
  appName: "PaperAgent",
  mode: "react-scaffold",
  currentSession: 52,
  backendBaseUrl: "/api", // dev: Vite proxy → http://127.0.0.1:18181
  legacyWebUrl: "http://127.0.0.1:18182",
  migrationPhase: "S52: 脚手架与迁移基线",
} as const;
