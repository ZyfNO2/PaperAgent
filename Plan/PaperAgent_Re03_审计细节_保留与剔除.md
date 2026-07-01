# Re03 Case A/B 审计细节（保留 / 剔除 / 原因）

> 用户要求：审计表必须中文。paper title 留英文（标识符），reason / 角色 / 类型 / 层级 全部中文一句话。
> 对应数据来源：`tmp_s66v_traces/re03_caseA_llm_online.json` + `re03_caseB_llm_online.json`

---

## Case A — 题目：基于三维成像的损伤检测智能方法

### A.1 各检索器入池统计（raw 22 → 入池 23）

| 检索器 | 原始 n | 流向 |
|---|---:|---|
| arxiv | 4 | 4 条全部入 pool，但 ER 后被 seed_relevance + 证据审查判定为 noise（标题涉及结构光 / RSNA / 纹理） |
| crossref | 16 | 13 条入 pool（MVCrackViT 等实质命中）+ 3 条 ER 后落到 candidate/rejected |
| github | 2 | 2 条入库作为代码候选（PointNet 类道路损伤） |
| openalex | 0 | 限流 / 无网络 |

### A.2 ER + 合成 4 桶分桶（pool n=23）

| 层级 | 数量 | 标题 + cid（中文 reason） |
|---|---:|---|
| 核心 | 1 | MVCrackViT 多视图点云裂纹检测（c-8e220e87）— 多视图+裂纹+点云三轴全中 |
| 候选 | 11 | 8 篇 MVS 背景参考（c-322b30e8 教程 / c-6f876b1e 大规模 / c-d1996e8e 光度立体 / c-a8b075ae LCD / c-d7f4a150 注意力 / c-46a0eb5d MVS2 / c-b5bad248 半监督 / c-81fa3ec0 网格细化）+ 2 代码库（c-66c13761 PointNet / c-1c8126ca 路面分割）+ 1 2D 纹理数据集（c-502e9839） |
| 需人工 | 2 | 3D 延性损伤相场论文（c-747d2323）— 力学非视觉，需人复核；AID（c-a1a73fed）— 标题裸名无元数据，需人识别 |
| 已剔除 | 9 | 拓扑控制与结构光（c-35b480e8）/ RSNA 腹部 CT（c-3d589791）/ RSNA 腰椎 MRI（c-55e48609）/ 面部麻痹识别（c-9940f86f）/ 汉字识别网格（c-7937ff50）/ 疝气手术评述（c-25ff717a）/ 主动网格特征跟踪（c-285ddaed）/ 直线段模式识别（c-f2ae2863）/ CAPTCHA 总结表（c-cc8619e1） |

### A.3 种子扩展决策（seeds 5 / 通过 0 / 拒绝 5 / 引用新增 0）

| 状态 | 标题 | reason |
|---|---|---|
| 种子拒绝 | Topological Control of Chirality and Spin with Structured Light（c-35b480e8） | 方法是物理结构光，任务是自旋轨道 — 与「损伤检测 / 点云分割」零重合 |
| 种子拒绝 | RSNA RATIC CT Dataset（c-3d589791） | 临床 CT 三维医学影像，缺「损伤 / 点云」 |
| 种子拒绝 | RSNA LumbarDISC MRI（c-55e48609） | 腰椎 MRI 退变分类，仅与「三维成像」共享一词 |
| 种子拒绝 | A New Benchmark Dataset for Texture Image Analysis（c-502e9839） | 2D 纹理基准，缺「三维 / 点云」 — 保留为数据集候选，但不做种子扩展 |
| 种子拒绝 | MVCrackViT（c-8e220e87） | 已在核心池里，种子扩展防自环跳过。**净结果：0 种子通过，全 5 被 seed_relevance 闸门挡掉** |

### A.4 最终合成 paper_groups（保留 4 个基线候选：c-8e220e87 / c-1c8126ca / c-66c13761 / c-502e9839）

| 分桶 | 数量 | cid 列表 |
|---|---:|---|
| 基线 | 2 | MVCrackViT（点云裂纹，2024）+ Point-cloud-seg 代码库 |
| 平行 | 2 | PointNet 路面损伤代码 + 2D 纹理缺陷数据集 |
| 引用 | 7 | 7 篇 MVS / 网格背景参考文献 |
| 长尾 | 3 | 网格细化 + 3D 损伤相场（需人工）+ AID（需人工） |

**最终被剔除 9 条**（理由同 §A.2 第 4 行）：拓扑 / RSNA CT / RSNA MRI / 面部麻痹 / 汉字识别 / 疝气手术 / 主动网格 / 模式识别 / CAPTCHA 表 — 全部为「刷关键词」型噪声，只命中宽词「三维」或「网格」却缺「损伤 / 点云」。

---

## Case B — 题目：基于 Unet 的钢材裂缝分割

### B.1 各检索器入池统计（raw 28 → 入池 28）

| 检索器 | 原始 n | 流向 |
|---|---:|---|
| arxiv | 8 | 5 入池（图像分割综述 / 多模态注意力 / NEU 纹理基准 / 路面缺陷综述 / ECFN 等子集）+ 3 ER 后剔除 |
| crossref | 8 | 8 全部入池（ECFN / 钢液分布 / SkipFusion / 缺陷+分割融合 / 双层腐蚀 / 钢丝绳 / 地面 UAV / 钢材缺陷） |
| github | 12 | 12 全部入池作为代码候选（12 个独立裂纹分割代码库） |
| openalex | 0 | 限流 / 无网络 |

### B.2 ER + 合成 4 桶分桶（pool n=28）

| 层级 | 数量 | 标题 + cid（中文 reason） |
|---|---:|---|
| 核心 | 3 | ECFN 钢材表面分割（c-d426dce8，2025）+ 缺陷检测+分割融合（c-70de81ae，2022）+ 钢材缺陷语义分割法（c-51cefa16，2020） — 全部 U-Net + 钢材裂缝三轴命中 |
| 候选 | 19 | 4 篇综述/平行参考（图像分割基础模型综述 / 路面缺陷综述 / ECFN 等）+ 5 篇钢材表面并行参考（钢液 / SkipFusion / 双层腐蚀 / 钢丝绳损伤 / 多模态注意力）+ 12 个 U-Net 裂纹代码库 + 1 NEU 纹理数据集 |
| 需人工 | 1 | CrackSegmentationDeepLearning（c-b67265e9）— U-Net+裂纹命中但缺「钢材」，从路面迁移到钢材需人复核 |
| 已剔除 | 5 | 9 平方度 Bootes 天文学调查（c-c9ef4648）/ LLM 编码德国开放问卷（c-59933ada）/ 3D 肾脏肿瘤分割（c-90e9cc00）/ 甲醇多波束天文学（c-42c94238）/ UAV 地面点云分割（c-f65c2f4c） — 全部只命中「语义分割」宽词却缺「钢材 / 裂纹」 |

### B.3 种子扩展决策（seeds 5 / 通过 2 / 拒绝 3 / 引用新增 0）

| 状态 | 标题 | reason |
|---|---|---|
| 种子入选 | Image Segmentation in Foundation Model Era: A Survey（c-1680caba） | 方法+任务双中（语义分割+U-Net 字样）— 留为引用。**净结果：openalex_citation 适配器仍返回 0 引用** |
| 种子入选 | Multi-Modal Attention Networks for Enhanced Segmentation（c-7d867196） | 分割+工业+缺陷三轴命中 — 留为平行。**openalex 仍 0** |
| 种子拒绝 | A rich bounty of AGN in the 9 square degree Bootes survey（c-c9ef4648） | 纯天文学，「钢材 / 裂纹」零重合 |
| 种子拒绝 | AIn't Nothing But a Survey? LLM Coding German Open-Ended（c-59933ada） | 社会学方法论，零重合 |
| 种子拒绝 | A New Benchmark Dataset for Texture Image Analysis（c-c94b06ac） | 2D 表面纹理，缺「U-Net / 钢材」 — 保留为数据集候选，未走种子扩展 |

**Case B 总结：2 种子入选但 0 引用新增**，因为 openalex_citation 适配器网络层返回 0（限流）。种子入选本身已对 ER 起到反馈作用。

### B.4 最终合成 paper_groups（保留 4 个基线候选：c-51cefa16 / c-70de81ae / c-d426dce8 / c-b67265e9）

| 分桶 | 数量 | cid 列表 |
|---|---:|---|
| 基线 | 2 | 钢材缺陷语义分割法（2020）+ 缺陷检测+分割融合（2022）— 双基线全部钢材表面 |
| 平行 | 6 | ECFN（2025）+ 钢液分布 + SkipFusion + 双层腐蚀 + 钢丝绳损伤 + 多模态注意力 |
| 引用 | 3 | 图像分割基础模型综述 + 路面缺陷综述 + NEU 纹理基准 |
| 长尾 | 12 | 12 个 U-Net 裂纹代码库（CrackSegmentationDeepLearning / RyM-CIC / Concrete-Crack / DenseUnet / DeepLabV3+UNET / Mohamadhoseinraad / smcck222 / BBahtiri / khanhha / konskyrt / Yuki-11 CSSR / anishreddy3） — 实现即用 |

**最终被剔除 5 条**（同 §B.2 第 4 行）：AGN/Bootes 天文 / LLM-编码 社科 / 3D 肾脏医学 / 甲醇多波束天文 / 地面 UAV — 全部只命中「语义分割」却缺「钢材 / 裂纹」。

---

## 跨 case 对照（一屏审计）

| 维度 | Case A | Case B |
|---|---|---|
| 原始总数 | 22（4 论文 + 16 出版 + 0 OA + 2 代码） | 28（8 论文 + 0 OA + 8 出版 + 12 代码） |
| 入池 | 23（去重后多出 1 数据集 AID） | 28（无去重） |
| 检索器层剔除 | 0（openalex 0 命中为限流） | 0（openalex 0 命中为限流） |
| ER 剔除 | 9（拓扑 / RSNA CT / RSNA MRI / 面部 / 汉字 / 疝气 / 主动网格 / 模式识别 / CAPTCHA） | 5（AGN / LLM 编码 / 3D 肾脏 / 甲醇 / UAV） |
| ER 核心 | 1（MVCrackViT） | 3（ECFN / 缺陷融合 / 钢材缺陷） |
| 种子扩展新增引用 | 0（5 全拒） | 0（2 入但 openalex 返 0） |
| Low-bar 结论 | `needs_revision`（can_continue=False） | `pass`（can_continue=True） |
| 失败 / 通过根因 | 核心集薄（1 篇）+ 9 噪声未在检索器层过滤（待 Re04 收紧 query_matrix） | 核心集厚（3 篇 2020-2025）+ 12 U-Net 代码库即用 + 3 篇 2025-2026 平行参考 |
