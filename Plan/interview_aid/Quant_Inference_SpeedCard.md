# 量化与推理加速 ·面试速记卡（口语向，够用就讲）

> 日期：2026-06-23
> 性质：口语速记卡（非项目设计）。对应小红书一面反思点 #3——「面试官对量化/推理理解不深，问的是概念；应用模块才深入。先把推理加速/训练粗粗起来，面试自信地讲就够」。
> 用法：面试前念熟关键词 +30版 + 60版。不必是专家，照着讲就能过概念关。
> 诚实边界：PaperAgent 自身是 API 侧消费（调 Minimax 等），不做本地量化。被问「你项目怎么量化」时，诚实说 +如果要在 CPU 跑我们会用的方案（见 §5）。

---

## 1. 必背关键词（照背就够）

### 量化方法
- **INT8 / INT4**：权重位宽。越低位省显存越快、但越掉点。
- **AWQ**（Activation-aware Weight Quantization）：看激活值哪些通道重要、重点保精度；常用于 GPU 推理。
- **GPTQ**：基于二阶 Hessian 信息的后训练量化，逐层校准；GPU 推理（适配）。
- **GGUF Q4_K_M**：llama.cpp/CPU，分块混合精度；移动/边缘首选。
- **BF16/FP8**：训练用 BF16（数值稳定）；H100 推理用 FP8。

### 推理加速（系统层，面试官爱问）
- **KV-Cache**：缓存 Transformer 的 K/V，避免重算历史 token；长序列省的是平方级开销。
- **PagedAttention**（vLLM）：KV-Cache 分页管理，像 OS 页表，解碎片 →高吞吐。
- **Continuous Batching**：动态拼 batch，请求别等齐 →GPU 占用满。
- **Prefix Cache / Prompt Caching**：system prompt 共享部分只算一次，复用 KV。
- **Speculative Decoding**：小模型猜 token +大模型并行校验，命中则白多 token。
- **Chunked Prefill**：把长 prompt 片 prefill，prefill 不阻塞 decode。

### 推理框架
- **vLLM**：PagedAttention + continuous batching，吞吐王。
- **SGLang**：结构化输出 + RadixAttention（前缀树复用 KV），复杂工具调用/JSON 快。
- **llama.cpp**：CPU/边缘 GGUF 量化。
- **TensorRT-LLM**：NVIDIA 推理专用。

### 压缩技术族谱（被问「还有哪些」）
- 量化：低位宽，模型小但结构不变
- 蒸馏：训小模型模仿大模型（logits / 黑盒）
- 剪枝：结构化剪枝（通道）> 非结构化（稀疏）
- 二值化：极端 1-bit，研究向

## 2. 30版（念完就过）

> 推理加速我从两条线讲：一是模型层量化，常用 Q4_K_M 混合精度——Attention 保 5-bit、FFN 4-bit、输出层 6-bit，在精度和资源间取平衡；GPU 侧会用 AWQ 或 GPTQ。二是系统层，vLLM 的 PagedAttention + continuous batching 把吞吐拉满，KV-Cache 配 prefix cache 降长序列成本，命中。我会按场景选：CPU / 边缘用 llama.cpp GGUF，GPU 高并发用 vLLM，结构化输出多用 SGLang。

## 3. 60版（被追问展开）

> 量化本质是用低位表示权重和激活，省显存、降显存带宽瓶颈。好处是推理快、成本低、能跑在更小卡上；缺点是精度损失，特别是激活值离群通道，AWQ 就是看激活感知地保它们。
> 推理加速我把模型层和系统层分开：模型层除了量化还有蒸馏 / 剪枝，蒸馏训小模型模仿大模型、剪枝去冗余通道；系统层核心是让 GPU 别闲着——KV-Cache 避免重复计算历史 token，PagedAttention 分页管 KV 解碎片，continuous batching 动态拼请求，prefix cache 复用公共 prompt。
> 如果要上 spec decoding 低延迟、或 chunked prefill 长 prompt 塞 decode，就进一步提升并发。我按延迟 vs 吞吐优先选：边缘低延迟 GGUF，服务端高吞吐 vLLM，重结构化 SGLang。


## 4. 常见追问与陷阱（被问到怎么接）

| 面试官问 | 答方向 | 避坑 |
|---|---|---|
| 「量化和 KV-Cache 什么关系？」 | 技术不同可结合：量化降权重/激活位宽省显存，KV-Cache 避免重算历史。量化也可作用在 KV-Cache 上（KV quant），双省。 | 别说没关系完事——补一句「可结合，KV-Cache 量化是进阶点」。 |
| 「降低精度有什么影响？」 | 分层说：离群激活通道误差放大 →精度降；分层说：输出分布漂移 →长尾 / 罕见 token 产量降。可校准+混合精度缓。 | 别只「精度变低」，给一层「怎么产生」的机制。 |
| 「Q4_K_M 是什么？」 | llama.cpp 块混合精度：重要层高 bit、次要层低 bit，全局 4-bit 平均。 | 别报错成「全部 4-bit」。 |
| 「Q4 和 Q8 多大差别？」 | 约一半显存，质量 Q4 约 Q8 95% 上下、明显优于 Q2。 | 给数值感：显存 -50%、质量 -low 个位数%。 |
| 「为什么大模型不直接 FP8/INT4 全用？」 | 训练稳用 BF16，FP8 H100；尾部 token 多保精度。 | 别说「FP8 全面更好」。 |

## 5. PaperAgent 项目怎么（诚实口径）

当前：PaperAgent 调外部 LLM API（Minimax 等），不做本地量化/推理。这条要*诚实先说*，不冒充。

如果被追「那本地部署的话你会怎么」，给关键词方案（design-only，不落实现）：

> PaperAgent 如果在 CPU 跑（场景：边界设备），我会选 Q4_K_M 混合精度——Attention 保 5-bit、FFN 4-bit、输出层 6-bit，保关键层精度。用 llama.cpp GGUF 本地推理，系统层用 prefix cache 复用同一题目流的公共 prompt（system + RAG context），降低重复 prefill 成本。如果上 GPU 服务，换 vLLM + AWQ。这整套对应企业级「推理服务降本」讲法。

收尾诚一句：「PaperAgent MVP 先把 Agent 工作流做清楚，量化/推理服务是部署扩展位，不是当前核心卖点。」——守住 Technical_Highlights 三档口径。

## 6. 简历可包装句（量化向，求职包装）

- 「采用 Q4_K_M 混合精度方案（Attention 5-bit / FFN 4-bit / 输出 6-bit）实现 CPU 端实时推理，显存降约 50% 质量损失可控」
- 「基于 vLLM PagedAttention + continuous batching 部署服务，配合 prefix caching 复用 RAG 公共上下文。」
- 注：PaperAgent 项目本身写简历时这一条要标「推理服务侧方案」，不冒充主线。

## 7. 语气提醒

面试官对量化理解通常不深、问概念为主 →粗 + 关键词 + 一层机制足够，别被拽进「GPTQ Hessian 公式」细节泥潭；如果对方深问，诚实说「这块我不是专家，但我清楚量化的应用层取舍和适用场景」——区分比硬装高。