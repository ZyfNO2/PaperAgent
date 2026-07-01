# Session 52: React + Vite 前端 e2e

依赖外部已起:
- 后端 uvicorn: `http://127.0.0.1:18181`
- Vite dev server: `http://127.0.0.1:18183`

## 跑测试

```bash
cd apps/web-react
npx playwright install chromium  # 首次安装浏览器
npx playwright test
```

测试用例见 `test_session52_react_scaffold.py`：

| ID | 用例 | 验收点 |
|---|---|---|
| s52_01 | 首页可打开 | title 含 PaperAgent |
| s52_02 | 迁移阶段可见 | phase-card 展示 S52-S56 |
| s52_03 | 旧前端入口 | legacy-card 链接到 18182 |
| s52_04 | health 三态 | loading/ok/error 至少一个 |
| s52_05 | 侧栏出现 | sidenav 含脚手架与旧前端入口 |
