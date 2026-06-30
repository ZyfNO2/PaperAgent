# PaperAgent SOP 执行 Rules：真实接线与点击验收

日期：2026-06-30

用途：后续所有 Session SOP 默认继承本 Rules。执行者不得只做静态 UI、mock 数据或本地状态假闭环。除非 SOP 明确写明 `design-only`，否则所有用户可点击能力必须接入真实后端、真实状态或真实持久化。

## 0. 默认工程风格：Ponytail ladder

Ponytail 已作为全局 skill 安装：

```text
C:\Users\ZYF\.codex\skills\ponytail
C:\Users\ZYF\.agents\skills\ponytail
```

后续所有 PaperAgent Session 默认采用 Ponytail full。执行者在做任何代码或方案前，必须按以下 ladder 逐级判断，停在第一个可工作的层级：

1. 这个功能是否真的需要存在？不需要就跳过，并在报告中说明。
2. 代码库里是否已有模块/工具/类型可复用？有就复用，不重新造。
3. 标准库能否解决？能就用标准库。
4. 平台原生能力能否解决？能就用原生能力。
5. 已安装依赖能否解决？能就复用，不新增依赖。
6. 一行或一个小函数能否解决？能就不要建复杂抽象。
7. 只有以上都不成立，才写最小可工作的新增代码。

Ponytail 在 PaperAgent 中的额外约束：

- Bug fix 必须修根因，不修单一路径症状。
- 新模块必须先说明“为什么已有模块不能复用”。
- 不允许创建只有一个实现的 interface/factory/strategy。
- 不允许为了“以后可能会用”写空扩展层。
- 如果做了刻意简化，必须用 `ponytail:` 注释写清 ceiling 与升级触发条件。
- 非平凡逻辑必须有最小可运行测试或 self-check。
- 真实用户流程优先于工程炫技；普通界面不展示调试复杂度。

## 1. 禁止偷懒规则

### R1：禁止前端假交互

如果页面上有按钮、输入框、提交、查询、分析、入库、索引、问答等动作，必须产生可验证的真实后果。

不允许：

- 点击按钮只改文案。
- 输入后只写入 React `useState`，刷新即丢，且 SOP 要求后端闭环。
- 显示“已应用”“已入库”“已索引”，但后端没有记录。
- 使用固定 demo 文案冒充真实分析。

允许：

- 明确标记 `本地草稿`。
- 明确标记 `待后端接线`。
- 开发者模式中展示 mock，但普通用户模式不能把 mock 当真。

### R2：禁止绕开已有后端能力另造假模块

如果仓库已有后端服务，执行者必须优先复用。

例如本地 RAG 必须优先检查并复用：

```text
apps/api/app/services/paper_library/embedding.py
apps/api/app/services/paper_library/indexer.py
apps/api/app/services/paper_library/retriever.py
apps/api/app/services/paper_library/paper_qa.py
apps/api/app/services/paper_library/storage.py
apps/api/app/api/v1/paper_library.py
```

不允许：

- 在前端新建一个假 RAG 数组冒充文献库。
- 绕开 `paper_library` 已有 storage/indexer/retriever。
- 复制一套不兼容的 embedding/index 数据结构。

### R3：必须有模块职责边界

每个新增模块必须写清楚“做什么”和“不做什么”。

示例：

```text
创建 ManualPaperIngest 模块，用于把用户手动提交的文献文本/链接转换为 PaperRecord + PaperChunk。
该模块不应该调用外部搜索，不应该做 RAG 问答，不应该写前端状态。
```

### R4：普通用户界面不能暴露开发/测试内容

普通用户界面只保留当前产品主线。

面试、测试、协议、baseline、raw trace、Playwright、旧前端入口、health、Session 标签，默认都放到开发者窗口。

### R5：失败必须诚实展示

API 失败、LLM 不可用、索引为空、无检索命中，都必须明确展示。

不允许：

- 吞掉错误。
- 用成功样式展示失败结果。
- 用假答案代替无命中。
- **用关键词模板硬编码替代 LLM 路径**（除非 LLM 失败时显式 fail-fast 抛错，不做物理分词 fallback）。S62 self-audit：方向生成必须是 LLM-first (arXiv 参考论文 + LLM)，硬编码模板会把 3D 题错推 YOLO/U-Net, 把 NLP 题完全漏掉。

### R6：链接 / 路径规范

后续 SOP / 验收报告 / 用户汇报必须遵守：

- 文件 / 文件夹引用一律用 markdown 链接语法，路径相对 workspace 根：
  `[label](apps/api/app/services/graduation/direction_planner.py)`
- `Ctrl+点击` 在 VSCode 可直接跳转；不要再用"绝对路径"形式单独贴一行。
- 链接名要能区分模块（避免 `Foo` 这种裸名）。
- 给所有重要文件加链接，不能"打包"说"详见相关模块"。

### R7：Self-audit 强约束

后续每个 SOP 必须包含 self-audit 步骤，不能只按"测试通过"收尾：

- 推荐结果是否合理？（例如 3D 题推荐 3D baseline, NLP 题推荐 BERT/Transformer）
- 是否复用已有模块？（避免重造；新模块必须先说明为什么已有模块不能用）
- 失败是否 fail-fast？（heuristic fallback 仅在 LLM 不可达且抛错后才考虑；不要静默兜底）
- 截图分析是否真实目视？（不能只写"截图通过"，必须列出截图证据 + 截图中看到的具体内容）

不满足 self-audit 的 Session 默认不得通过验收。

## 2. SOP 编写最低结构

后续 SOP 必须包含：

1. 当前基线。
2. 用户目标。
3. 本轮做什么。
4. 本轮不做什么。
5. 新增模块清单。
6. 每个模块职责。
7. 每个模块禁止事项。
8. API / 前端 / 测试接线点。
9. 全流程真实点击测试。
10. 截图验收要求。
11. 最终通过条件。

## 3. 测试与验收硬门槛

### 3.1 自动测试

必须至少包含：

- 后端单元测试或 API 测试。
- 前端 Playwright 测试。
- 如涉及类型变更，必须跑 TypeScript 构建或类型检查。

### 3.2 真实点击测试

执行者必须用真实浏览器走完整用户路径，而不是只跑单测。

报告必须写清：

- 打开哪个 URL。
- 输入了什么。
- 点击了哪些按钮。
- 后端返回了什么。
- 页面显示了什么。
- 截图路径。

### 3.3 截图分析

每轮涉及 UI 的 Session 必须产出截图，并在报告中分析截图是否可用。

截图不是装饰，必须回答：

- 用户能不能一眼找到下一步？
- 是否存在没接线的按钮？
- 错误是否可理解？
- 普通用户是否看到过多开发信息？

## 4. 验收报告最低要求

报告必须包含：

```text
1. 完成内容
2. 新增/修改模块
3. 每个模块真实接线说明
4. 不做什么与边界
5. 自动测试结果
6. 真实浏览器点击链路
7. 截图清单与截图分析
8. 已知问题
9. 是否建议通过验收
```

如果缺少真实点击测试或截图分析，默认不得通过验收。
