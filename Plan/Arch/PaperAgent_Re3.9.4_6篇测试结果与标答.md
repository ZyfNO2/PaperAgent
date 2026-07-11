# PaperAgent Re3.9.4 — 6篇测试结果与标答汇总

> 本文档汇总 R39-CONS、R39-PILE、R39-GAS、R39-CORR、R39-NDT、R39-LOAD 六个 case 的最终结果。

- **数据来源**: tmp_re13_eval
- **case 总数**: 6

## 总览

| Case ID | 题目 | 论文数 | Repo | Dataset | Baseline | 可行性 | 评审 |
|---|---|---|---|---|---|---|---|
| R39-CORR | 钢筋混凝土中钢筋腐蚀原理的研究 | 42 | 0 | 0 | 32 | risky(65) | MINOR_REVISION |
| R39-NDT | 混凝土非破损检测技术开发与应用研究 | 21 | 0 | 0 | 19 | risky(65) | MINOR_REVISION |
| R39-LOAD | 基于大数据分析的电力负荷预测模型研究 | 6 | 0 | 0 | 2 | risky(55) | MINOR_REVISION |
| R39-CONS | ? | 3 | 4 | 0 | 3 | feasible(82) | MINOR_REVISION |
| R39-PILE | ? | 9 | 0 | 0 | 2 | risky(55) | MINOR_REVISION |
| R39-GAS | ? | 36 | 0 | 0 | 19 | risky(65) | MINOR_REVISION |


## R39-CORR — 钢筋混凝土中钢筋腐蚀原理的研究

- **可行性裁决**: `risky` (分数: 65)
- **可行性理由**: Baseline论文32篇（如Electrochemical Aspects of Galvanized Reinforcement Corrosion）提供理论基础，但无数据集和代码仓库，需自建实验数据；硬件依赖（电化学测试设备）存在获取风险，但可通过模拟或文献数据降级。
- **复核裁决**: `MINOR_REVISION`
- **领域**: ['civil_infra']
- **方法关键词**: ['electrochemical corrosion', 'corrosion mechanism']
- **对象关键词**: ['steel reinforcement', 'reinforced concrete']
- **任务关键词**: ['corrosion analysis', 'mechanism study']
- **关键词全英文**: ✅

### Search Steps (8 步)
- step 0: openalex ""electrochemical corrosion" "steel reinforcement"" -> FAILED
- step 1: arxiv ""electrochemical corrosion" "steel reinforcement" corrosion " -> 12 results
- step 2: github "electrochemical corrosion steel reinforcement" -> FAILED
- step 3: semantic_scholar "electrochemical corrosion steel reinforcement" -> FAILED
- step 4: crossref "electrochemical corrosion steel reinforcement" -> 12 results
- step 5: crossref ""corrosion mechanism" "steel reinforcement"" -> 12 results
- step 6: core "electrochemical corrosion steel reinforcement" -> FAILED
- step 7: crossref ""corrosion mechanism" "reinforced concrete"" -> FAILED

### Filter Results
- total: 33, kept: 33, dropped: 0, low_relevance: 0

### Verified Papers (42 篇)
- **Electrochemical Aspects of Galvanized Reinforcement Corrosion** — crossref
  - **中文译名**: 镀锌钢筋腐蚀的电化学特性
  - URL: https://doi.org/10.1016/b978-008044511-3/50020-7
- **Electrochemical Injection of Corrosion Inhibitors and Chloride Extraction for Protection of Steel Reinforcement** — crossref
  - **中文译名**: 钢筋保护用电化学注入缓蚀剂与氯离子提取技术
  - URL: https://doi.org/10.5006/c2019-13451
  - Abstract: <jats:title>Abstract</jats:title>
               <jats:p>Electrochemical chloride extraction from a reinforced concrete structure may be accompanied w...
- **Electrochemical Potential Monitoring of Corrosion and Coating Protection of Mild Steel Reinforcement in Concrete** — crossref
  - **中文译名**: 混凝土中低碳钢钢筋腐蚀与涂层保护的电位监测
  - URL: https://doi.org/10.5006/1.3577871
  - Abstract: <jats:p>The corrosion and protection behavior of a mild steel reinforcement in concrete, partially immersed in different test media, was investigated ...
- **Study of the Corrosion of Concrete Reinforcement by Electrochemical Impedance Measurement** — crossref
  - **中文译名**: 基于电化学阻抗谱的混凝土钢筋腐蚀研究
  - URL: https://doi.org/10.1520/stp25019s
  - Abstract: <jats:p>Electrochemical impedance measurement is a convenient method to analyze the corrosion phenomena of steel in concrete. A data analysis method i...
- **Phase sensitive detection of extent of corrosion in steel reinforcing bars using eddy currents** — arxiv
  - **中文译名**: 基于涡流的钢筋腐蚀程度相位敏感检测
  - URL: http://arxiv.org/abs/2001.03756v1
  - Abstract: Corrosion of steel bars in reinforced cement concrete (RCC) structures leads to premature deterioration and increase in life cycle maintenance costs. ...
- **Introduction of Inhibitors, Mechanism and Application for Protection of Steel Reinforcement Corrosion in Concrete** — crossref
  - **中文译名**: 混凝土中钢筋腐蚀抑制剂的机理与应用综述
  - URL: https://doi.org/10.5772/intechopen.92374
- **Atomic Level Study on the Steel Reinforcement Corrosion Mechanism by Experimental Investigations and Theoretical Calculations** — crossref
  - **中文译名**: 钢筋腐蚀机理的原子级实验与理论研究
  - URL: https://doi.org/10.2139/ssrn.5279829
- **Corrosion of Steel Reinforcement in Concrete** — crossref
  - **中文译名**: 混凝土中钢筋腐蚀
  - URL: https://doi.org/10.1201/b16793-7
- **Corrosion of Steel Reinforcement** — crossref
  - **中文译名**: 钢筋腐蚀
  - URL: https://doi.org/10.1007/978-981-99-5933-4_5
- **Effect of Inhibitors and Admixed Chloride on Electrochemical Corrosion Behavior of Mild Steel Reinforcement in Concrete in Seawater** — crossref
  - **中文译名**: 海水环境下缓蚀剂与掺入氯离子对混凝土中低碳钢钢筋电化学腐蚀行为的影响
  - URL: https://doi.org/10.5006/1.3315997
  - Abstract: <jats:p>Electrochemical potential monitoring experiments have been performed on the mild steel rebars embedded in concrete admixed with different inhi...
- **Electrochemical Noise Measurement to Assess Corrosion of Steel Reinforcement in Concrete** — crossref
  - **中文译名**: 基于电化学噪声测量的混凝土钢筋腐蚀评估
  - URL: https://doi.org/10.3390/ma14185392
  - Abstract: <jats:p>The electrochemical noise method (ENM) has previously been employed to monitor the corrosion of steel reinforcement in concrete. The developme...
- **Electrochemical Corrosion Behavior of Carbon Steel Reinforcement in Concrete Containing Limestone and Mesoporous Silica Nanoparticles under Acidic Environment** — crossref
  - **中文译名**: 酸性环境下含石灰石与介孔二氧化硅纳米颗粒混凝土中碳钢钢筋的电化学腐蚀行为
  - URL: https://doi.org/10.20964/2020.12.16
- **Electrochemical Characteristics and Corrosion Mechanisms of High-Strength Corrosion-Resistant Steel Reinforcement under Simulated Service Conditions** — crossref
  - **中文译名**: 模拟服役条件下高强耐腐蚀钢筋的电化学特性与腐蚀机理
  - URL: https://doi.org/10.3390/met14080876
  - Abstract: <jats:p>Long-term steel reinforcement corrosion greatly impacts reinforced concrete structures, particularly in marine and coastal settings. Concrete ...
- **Corrosion mechanisms of steel reinforcement in concrete** — crossref
  - **中文译名**: 混凝土中钢筋腐蚀机理
  - URL: https://doi.org/10.23860/diss-4135
- **Electrochemical Corrosion Behaviour of Carbon Steel Reinforcement in Metakaolin-Limestone Modified Concrete Exposed to Simulated Soil Solution** — crossref
  - **中文译名**: 模拟土壤溶液环境下偏高岭土-石灰石改性混凝土中碳钢钢筋的电化学腐蚀行为
  - URL: https://doi.org/10.20964/2021.05.23
- ... 等共 42 篇

### Weak Papers (23 篇)
- **Galvanized steel reinforcement** — crossref (relevance: none)
  - **中文译名**: 镀锌钢筋
- **Evaluation of corrosion resistance of different steel reinforcement types** — crossref (relevance: none)
  - **中文译名**: 不同类型钢筋耐腐蚀性能评估
- **Corrosion‐Resistant Reinforcement** — crossref (relevance: none)
  - **中文译名**: 耐腐蚀钢筋
- **Inhibitor Effect of Anthocleista djalonensis Extract on the Corrosion of Concrete Steel Reinforcement** — crossref (relevance: none)
  - **中文译名**: Anthocleista djalonensis提取物对混凝土钢筋腐蚀的抑制效果
- **Epoxy Coatings for Corrosion Protection of Reinforcement Steel** — crossref (relevance: none)
  - **中文译名**: 钢筋防腐环氧涂层
- ... 等共 23 篇

### Repos (0 个)
（无）

### Datasets (0 个)
（无）

### Baselines (32 个)
- Electrochemical Aspects of Galvanized Reinforcement Corrosion
- Electrochemical Injection of Corrosion Inhibitors and Chloride Extraction for Protection of Steel Reinforcement
- Electrochemical Potential Monitoring of Corrosion and Coating Protection of Mild Steel Reinforcement in Concrete
- Study of the Corrosion of Concrete Reinforcement by Electrochemical Impedance Measurement
- Phase sensitive detection of extent of corrosion in steel reinforcing bars using eddy currents
- Introduction of Inhibitors, Mechanism and Application for Protection of Steel Reinforcement Corrosion in Concrete
- Atomic Level Study on the Steel Reinforcement Corrosion Mechanism by Experimental Investigations and Theoretical Calculations
- Corrosion of Steel Reinforcement in Concrete
- Corrosion of Steel Reinforcement
- Effect of Inhibitors and Admixed Chloride on Electrochemical Corrosion Behavior of Mild Steel Reinforcement in Concrete in Seawater

### Innovation Points (3 个)
- 将电化学注入缓蚀剂与氯离子提取技术与ZnO缓蚀剂结合，用于钢筋混凝土腐蚀防护
- 将涡流检测技术与碳纤维/光纤布拉格光栅主动热探针结合，实现钢筋腐蚀的早期无损检测
- 将电化学阻抗谱测量方法与Vernonia amygdalina提取物缓蚀剂结合，评估天然缓蚀剂对钢筋腐蚀的抑制效果

### Stitching Plan (缝合方案)
- **Baseline**: 电化学注入缓蚀剂与氯离子提取模型
- **Module B**: ZnO缓蚀剂性能评估方法（来自Update Results of ZnO Behavior as a Corrosion Inhibitor for Rebars）
- **Module C**: 电化学阻抗谱监测方法（来自Study of the Corrosion of Concrete Reinforcement by Electrochemical Impedance Measurement）

## R39-NDT — 混凝土非破损检测技术开发与应用研究

- **可行性裁决**: `risky` (分数: 65)
- **可行性理由**: 5篇baseline论文均涉及超声检测混凝土，但无数据集和代码仓库，需自建实验平台和采集数据，硬件依赖（超声设备、混凝土试件）存在获取风险，且无公开数据集支撑，证据链不完整。
- **复核裁决**: `MINOR_REVISION`
- **领域**: ['civil_infra']
- **方法关键词**: ['ultrasonic testing', 'rebar detection', 'ground penetrating radar']
- **对象关键词**: ['concrete', 'reinforced concrete', 'concrete structure']
- **任务关键词**: ['detection', 'evaluation', 'quality assessment']
- **关键词全英文**: ✅

### Search Steps (8 步)
- step 0: openalex ""ultrasonic testing" concrete" -> 12 results
- step 1: openalex ""rebar detection" concrete" -> 12 results
- step 2: arxiv ""ultrasonic testing" concrete detection" -> 12 results
- step 3: openalex ""ground penetrating radar" concrete detection" -> 12 results
- step 4: github "ultrasonic testing concrete detection" -> FAILED
- step 5: semantic_scholar ""ultrasonic testing" concrete detection" -> FAILED
- step 6: openalex ""ground penetrating radar" concrete evaluation" -> FAILED
- step 7: crossref "ultrasonic testing concrete detection" -> FAILED

### Filter Results
- total: 48, kept: 47, dropped: 0, low_relevance: 1

### Verified Papers (21 篇)
- **Characterization and hardening of concrete with ultrasonic testing** — openalex
  - **中文译名**: 基于超声测试的混凝土特性表征与硬化研究
- **Ultrasonic testing of non-metallic materials: concrete and marble** — openalex
  - **中文译名**: 非金属材料的超声检测：混凝土与大理石
- **Detection of the corrosion damage in reinforced concrete members by ultrasonic testing** — openalex
  - **中文译名**: 基于超声检测的钢筋混凝土构件腐蚀损伤识别
- **Ultrasonic testing of reactive powder concrete** — openalex
  - **中文译名**: 活性粉末混凝土的超声检测
- **Ultrasonic Testing of Damage in Concrete under Uniaxial Compression** — openalex
  - **中文译名**: 单轴压缩下混凝土损伤的超声检测
- **Measurement of reinforcement corrosion in concrete adopting ultrasonic tests and artificial neural network** — openalex
  - **中文译名**: 基于超声测试与人工神经网络的混凝土钢筋腐蚀测量
- **Ultrasonic tests in the evaluation of the stress level in concrete prisms based on the acoustoelasticity** — openalex
  - **中文译名**: 基于声弹性效应的混凝土棱柱体应力水平超声评估
- **The ultrasonic testing of concrete** — openalex
  - **中文译名**: 混凝土超声检测
- **Nonlinear ultrasonic test of concrete cubes with induced crack** — openalex
  - **中文译名**: 含预制裂缝混凝土立方体的非线性超声检测
- **Ultrasonic testing on evaluation of concrete residual compressive strength: A review** — openalex
  - **中文译名**: 基于超声检测的混凝土剩余抗压强度评估：综述
- **Review of GPR Rebar Detection** — openalex
  - **中文译名**: 探地雷达钢筋检测综述
- **A computer vision based rebar detection chain for automatic processing of concrete bridge deck GPR data** — openalex
  - **中文译名**: 基于计算机视觉的混凝土桥面板探地雷达数据自动钢筋检测流程
- **A Machine Learning Based Approach for Automatic Rebar Detection and Quantification of Deterioration in Concrete Bridge Deck Ground Penetrating Radar B-scan Images** — openalex
  - **中文译名**: 基于机器学习的混凝土桥面板探地雷达B扫图像自动钢筋检测与劣化量化方法
- **Automated GPR Rebar Analysis for Robotic Bridge Deck Evaluation** — openalex
  - **中文译名**: 面向机器人桥面板评估的自动探地雷达钢筋分析
- **Rebar Detection in Concrete Based on GPR B-scan** — openalex
  - **中文译名**: 基于探地雷达B扫的混凝土钢筋检测
- ... 等共 21 篇

### Weak Papers (15 篇)
- **Data-driven Detection and Evaluation of Damages in Concrete Structures: Using Deep Learning and Computer Vision** — arxiv (relevance: none)
  - **中文译名**: 数据驱动的混凝土结构损伤检测与评估：基于深度学习与计算机视觉
- **Deep Learning-Based Automated Image Segmentation for Concrete Petrographic Analysis** — arxiv (relevance: none)
  - **中文译名**: 基于深度学习的混凝土岩相分析自动图像分割
- **Compton back scatter imaging for mild steel rebar detection and depth characterization embedded in concrete** — openalex (relevance: none)
  - **中文译名**: 基于康普顿背散射成像的混凝土内低碳钢钢筋检测与深度表征
- **MUSIC algorithms for rebar detection** — openalex (relevance: none)
  - **中文译名**: 钢筋检测的MUSIC算法
- **Capacitance-Based Technique for Detection of Reinforcement Bars in Concrete Structures** — openalex (relevance: none)
  - **中文译名**: 基于电容技术的混凝土结构钢筋检测方法
- ... 等共 15 篇

### Repos (0 个)
（无）

### Datasets (0 个)
（无）

### Baselines (19 个)
- Characterization and hardening of concrete with ultrasonic testing
- Ultrasonic testing of non-metallic materials: concrete and marble
- Detection of the corrosion damage in reinforced concrete members by ultrasonic testing
- Ultrasonic testing of reactive powder concrete
- Ultrasonic Testing of Damage in Concrete under Uniaxial Compression
- Measurement of reinforcement corrosion in concrete adopting ultrasonic tests and artificial neural network
- Ultrasonic tests in the evaluation of the stress level in concrete prisms based on the acoustoelasticity
- The ultrasonic testing of concrete
- Nonlinear ultrasonic test of concrete cubes with induced crack
- A computer vision based rebar detection chain for automatic processing of concrete bridge deck GPR data

### Innovation Points (5 个)
- 将超声脉冲速度法与声发射技术结合，实现混凝土损伤的实时监测与定位
- 将超声衰减谱分析与机器学习分类器结合，自动识别混凝土内部缺陷类型
- 将超声相控阵成像与腐蚀电位测量结合，实现钢筋锈蚀区域的三维可视化
- 将超声表面波法与红外热成像结合，检测混凝土表层脱空与分层缺陷
- 将超声纵波与横波联合测量与反应粉末混凝土的微观结构表征结合，评估其力学性能

### Stitching Plan (缝合方案)
- **Baseline**: 超声脉冲速度损伤检测模型
- **Module B**: 声发射事件定位模块（来自Ultrasonic Testing of Damage in Concrete under Uniaxial Compression）
- **Module C**: 超声衰减谱特征提取模块（来自Characterization and hardening of concrete with ultrasonic testing）

## R39-LOAD — 基于大数据分析的电力负荷预测模型研究

- **可行性裁决**: `risky` (分数: 55)
- **可行性理由**: 仅2篇baseline论文（有repo），无数据集无代码仓库。电力负荷预测需自建高质量时序数据，数据获取与清洗周期长，存在数据可用性风险。
- **复核裁决**: `MINOR_REVISION`
- **领域**: ['energy_power']
- **方法关键词**: ['big data analysis', 'load forecasting']
- **对象关键词**: ['power load', 'electricity consumption']
- **任务关键词**: ['prediction', 'forecasting']
- **关键词全英文**: ✅

### Search Steps (8 步)
- step 0: openalex ""big data analysis" "power load" forecasting" -> FAILED
- step 1: arxiv ""big data analysis" "power load" prediction" -> 12 results
- step 2: github "big data analysis power load forecasting" -> FAILED
- step 3: arxiv "big data analysis power load prediction" -> 12 results
- step 4: semantic_scholar "big data analysis power load forecasting" -> FAILED
- step 5: arxiv "big data analysis power load prediction" -> 12 results
- step 6: crossref "big data analysis power load forecasting" -> 12 results
- step 7: crossref "big data analysis power load prediction" -> FAILED

### Filter Results
- total: 36, kept: 33, dropped: 0, low_relevance: 3

### Verified Papers (6 篇)
- **Fluctuation analysis of high frequency electric power load in the Czech Republic** — arxiv
  - **中文译名**: 捷克共和国高频电力负荷波动分析
  - URL: http://arxiv.org/abs/1602.05498v1
  - Abstract: We analyze the electric power load in the Czech Republic (CR) which exhibits a seasonality as well as other oscillations typical for European countrie...
- **Big Data Analytics for Dynamic Energy Management in Smart Grids** — arxiv
  - **中文译名**: 面向智能电网动态能源管理的大数据分析
  - URL: http://arxiv.org/abs/1504.02424v3
  - Abstract: The smart electricity grid enables a two-way flow of power and data between suppliers and consumers in order to facilitate the power flow optimization...
- **Uncovering Dominant Features in Short-term Power Load Forecasting Based on Multi-source Feature** — arxiv
  - **中文译名**: 基于多源特征的短期电力负荷预测主导特征挖掘
  - URL: http://arxiv.org/abs/2103.12534v1
  - Abstract: Due to the limitation of data availability, traditional power load forecasting methods focus more on studying the load variation pattern and the influ...
- **Big Data in Power Load Forecast** — crossref
  - **中文译名**: 电力负荷预测中的大数据
  - URL: https://doi.org/10.1201/9781003147213-3-3
- **Automatic Machine Learning Participation in Power Load Forecasting Under the Background of Big Data** — crossref
  - **中文译名**: 大数据背景下自动机器学习在电力负荷预测中的应用
  - URL: https://doi.org/10.1109/icepet61938.2024.10626878
- **A Review of Conventional,Modernand Big Data AnalyticsTechniques forShort Term Load Forecasting inSmart Grid** — crossref
  - **中文译名**: 智能电网短期负荷预测中传统、现代与大数据分析技术综述
  - URL: https://doi.org/10.48047/jocaaa.2019.26.05.1

### Weak Papers (13 篇)
- **A Random Sample Partition Data Model for Big Data Analysis** — arxiv (relevance: none)
  - **中文译名**: 面向大数据分析随机样本划分的数据模型
- **From human mobility to renewable energies: Big data analysis to approach worldwide multiscale phenomena** — arxiv (relevance: none)
  - **中文译名**: 从人类流动性到可再生能源：大数据分析方法探索全球多尺度现象
- **A Semantic Approach for Big Data Exploration in Industry 4.0** — arxiv (relevance: none)
  - **中文译名**: 面向工业4.0大数据探索的语义方法
- **Big Data: Understanding Big Data** — arxiv (relevance: none)
  - **中文译名**: 大数据：理解大数据
- **Big Data Analytics for QoS Prediction Through Probabilistic Model Checking** — arxiv (relevance: none)
  - **中文译名**: 基于概率模型检验的大数据QoS预测分析
- ... 等共 13 篇

### Repos (0 个)
（无）

### Datasets (0 个)
（无）

### Baselines (2 个)
- Big Data in Power Load Forecast
- Automatic Machine Learning Participation in Power Load Forecasting Under the Background of Big Data

### Innovation Points (3 个)
- 在基于大数据的电力负荷预测基线模型中，引入高频负荷波动分析模块，通过1/f噪声检测和确定性/随机性分离，增强模型对负荷波动特征的捕捉能力。
- 在基线模型中集成多源特征主导性发现模块，通过特征重要性排序和筛选，提升短期负荷预测的准确性。
- 在基线模型中引入动态能源管理的大数据分析模块，通过实时数据流处理和优化算法，提升模型对智能电网动态变化的适应性。

### Stitching Plan (缝合方案)
- **Baseline**: 基于大数据的电力负荷预测模型（复现自Big Data in Power Load Forecast和Automatic Machine Learning Participation in Power Load Forecasting Under the Background of Big Data）
- **Module B**: 高频负荷波动分析模块（来自Fluctuation analysis of high frequency electric power load in the Czech Republic）
- **Module C**: 多源特征主导性发现模块（来自Uncovering Dominant Features in Short-term Power Load Forecasting Based on Multi-source Feature）

## R39-CONS — ?

- **可行性裁决**: `feasible` (分数: 82)
- **可行性理由**: 有3篇baseline论文且均有repo，方法可复现；但无公开数据集，需自建施工安全图像数据集，存在数据采集和标注工作量风险。
- **复核裁决**: `MINOR_REVISION`
- **领域**: ['civil_infra']
- **方法关键词**: ['convolutional neural network']
- **对象关键词**: ['construction engineering', 'construction safety']
- **任务关键词**: ['early warning', 'prediction']
- **关键词全英文**: ✅

### Search Steps (6 步)
- step 0: openalex ""convolutional neural network" "construction engineering" sa" -> FAILED
- step 1: arxiv ""convolutional neural network" construction safety early war" -> FAILED
- step 2: semantic_scholar ""convolutional neural network" "construction safety" early w" -> FAILED
- step 3: crossref ""convolutional neural network" "construction safety" early w" -> 12 results
- step 4: github "convolutional neural network construction safety" -> 4 results
- step 5: STOP — 已有 12 篇论文 + 4 个 repo，足够开始分析

### Filter Results
- total: 12, kept: 12, dropped: 0, low_relevance: 0

### Verified Papers (3 篇)
- **Deep Convolutional Neural Network with Differential Feature Maps for Construction Safety Risks Assessment of Bridge Engineering** — crossref
  - **中文译名**: 基于差分特征图的深度卷积神经网络用于桥梁工程施工安全风险评估
  - URL: https://doi.org/10.1109/icdsns62112.2024.10691175
- **Early warning control model and simulation study of engineering safety risk based on a convolutional neural network** — crossref
  - **中文译名**: 基于卷积神经网络的工程安全风险预警控制模型与仿真研究
  - URL: https://doi.org/10.1007/s00521-022-08170-9
- **Construction of Safety Early Warning Model for Construction of Engineering Based on Convolution Neural Network** — crossref
  - **中文译名**: 基于卷积神经网络的工程施工安全预警模型构建
  - URL: https://doi.org/10.1155/2022/8937084
  - Abstract: <jats:p>In recent years, China’s engineering construction management level has been greatly improved, but compared with other industries, the construc...

### Weak Papers (16 篇)
- **Urban safety network for long-term structural health monitoring of buildings using convolutional neural network** — crossref (relevance: none)
  - **中文译名**: 基于卷积神经网络的建筑长期结构健康监测城市安全网络
- **Early Warning Classification of Geotechnical Engineering Construction Safety using Clique Graph Convolutional Network with Fast Sigmoid Activation** — crossref (relevance: none)
  - **中文译名**: 基于快速Sigmoid激活的团图卷积网络的岩土工程施工安全预警分类
- **Smart safety early warning model of landslide geological hazard based on BP neural network** — crossref (relevance: none)
  - **中文译名**: 基于BP神经网络的地质灾害滑坡智能安全预警模型
- **Research on construction engineering safety early warning based on BP neural network** — crossref (relevance: none)
  - **中文译名**: 基于BP神经网络的工程施工安全预警研究
- **Application of Soft Computing to Address Uncertainty in Construction Project Management: A Systematic Literature Review** — semantic_scholar (relevance: none)
  - **中文译名**: 软计算在建筑项目管理不确定性中的应用：系统文献综述
- ... 等共 16 篇

### Repos (4 个)
- **?**
  - URL: https://github.com/jaco-lau/Site-Safety-Assistant
- **?**
  - URL: https://github.com/riu-rd/Worksite-Safety-Monitoring
- **?**
  - URL: https://github.com/CherokeeBoose/Helmet-Detection-using-Convolutional-Neural-Networks-CNNs-
- **?**
  - URL: https://github.com/d1ya07/AI-Safety-Monitor-for-Labs-or-Construction-Sites

### Datasets (0 个)
（无）

### Baselines (3 个)
- Deep Convolutional Neural Network with Differential Feature Maps for Construction Safety Risks Assessment of Bridge Engineering
- Early warning control model and simulation study of engineering safety risk based on a convolutional neural network
- Construction of Safety Early Warning Model for Construction of Engineering Based on Convolution Neural Network

### Innovation Points (3 个)
- 结合差分特征图与卷积神经网络，增强对桥梁工程安全风险的识别能力
- 将工程安全风险预警控制模型与卷积神经网络结合，实现动态预警
- 融合差分特征图与预警控制模型，构建增强型施工安全预警系统

### Stitching Plan (缝合方案)
- **Baseline**: Deep Convolutional Neural Network with Differential Feature Maps for Construction Safety Risks Assessment of Bridge Engineering
- **Module B**: 预警控制模型（来自Early warning control model and simulation study of engineering safety risk based on a convolutional neural network）
- **Module C**: 差分特征图模块（来自Deep Convolutional Neural Network with Differential Feature Maps for Construction Safety Risks Assessment of Bridge Engineering）

## R39-PILE — ?

- **可行性裁决**: `risky` (分数: 55)
- **可行性理由**: Baseline仅2篇且无数据集和代码仓库，需自建现场监测数据或数值模拟，存在数据获取和硬件依赖风险（如振动传感器、场地许可）。
- **复核裁决**: `MINOR_REVISION`
- **领域**: ['civil_infra']
- **方法关键词**: ['high-frequency vibration', 'pile driving']
- **对象关键词**: ['surrounding environment', 'soil', 'structure']
- **任务关键词**: ['impact assessment', 'monitoring']
- **关键词全英文**: ✅

### Search Steps (8 步)
- step 0: openalex ""high-frequency vibration" "pile driving" "surrounding envir" -> FAILED
- step 1: arxiv ""high-frequency vibration" "pile driving" "surrounding envir" -> 12 results
- step 2: github "high-frequency vibration pile driving" -> FAILED
- step 3: arxiv ""high-frequency vibration" "surrounding environment" "impact" -> 12 results
- step 4: semantic_scholar ""high-frequency vibration" "pile driving" "surrounding envir" -> FAILED
- step 5: arxiv "high-frequency vibration surrounding environment impact asse" -> 12 results
- step 6: crossref ""high-frequency vibration" "pile driving" "surrounding envir" -> 12 results
- step 7: crossref ""high-frequency vibration" "surrounding environment"" -> 12 results

### Filter Results
- total: 55, kept: 51, dropped: 0, low_relevance: 4

### Verified Papers (9 篇)
- **Assessment Study on Impact of Pile Driving Vibration on Surrounding Houses** — crossref
  - **中文译名**: 打桩振动对周边房屋影响的评估研究
  - URL: https://doi.org/10.4028/www.scientific.net/amr.457-458.325
  - Abstract: <jats:p>It’s common to see the dispute caused by pile driving construction vibration effect, which has become a concern of social problems. The paper ...
- **Pile-driving Induced Vibration and its Transmission to Buildings** — crossref
  - **中文译名**: 打桩引起的振动及其向建筑物的传播
  - URL: https://doi.org/10.1177/026309239201100302
  - Abstract: <jats:p>The paper reports a case study of pile-driving induced vibration and its transmission to buildings which was carried out in the construction s...
- **Interaction of the pile and surrounding soil during vibration driving** — crossref
  - **中文译名**: 振动沉桩过程中桩周土相互作用
  - URL: https://doi.org/10.1088/1757-899x/456/1/012093
- **Developing an Explainable Artificial Intelligent (XAI) Model for Predicting Pile Driving Vibrations in Bangkok's Subsoil** — arxiv
  - **中文译名**: 面向曼谷软黏土地层打桩振动预测的可解释人工智能模型构建
  - URL: http://arxiv.org/abs/2409.05918v1
  - Abstract: This study presents an explainable artificial intelligent (XAI) model for predicting pile driving vibrations in Bangkok's soft clay subsoil. A deep ne...
- **Mesoscopic Investigation and Shaft Friction Resistance Modeling of Saturated Sand Under High-Frequency Vibratory Pile Driving** — crossref
  - **中文译名**: 高频振动沉桩下饱和砂细观研究与桩侧摩阻力建模
  - URL: https://doi.org/10.2139/ssrn.5079506
- **A case study on safe sheet pile driving with vibration monitoring** — crossref
  - **中文译名**: 基于振动监测的安全钢板桩沉桩案例研究
  - URL: https://doi.org/10.1201/9781003762478-20
- **Use of Surface Wave Testing to Develop Pile Driving Vibration Criteria in a Coastal Environment** — crossref
  - **中文译名**: 基于表面波测试的沿海环境打桩振动标准制定
  - URL: https://doi.org/10.1061/9780784484043.012
- **Vibration and dynamic settlement from pile driving** — crossref
  - **中文译名**: 打桩引起的振动与动态沉降
  - URL: https://doi.org/10.1680/bop.44548.0016
- **Numerical evaluation of pile vibration and noise emission during offshore pile driving** — crossref
  - **中文译名**: 海上打桩过程中桩振动与噪声排放的数值评估
  - URL: https://doi.org/10.1016/j.apacoust.2015.05.008

### Weak Papers (11 篇)
- **Measuring the right thing: justifying metrics in AI impact assessments** — arxiv (relevance: none)
  - **中文译名**: 测量正确指标：人工智能影响评估中的指标论证
- **When and How AI Should Assist Brainstorming for AI Impact Assessment** — arxiv (relevance: none)
  - **中文译名**: 人工智能何时及如何辅助人工智能影响评估的头脑风暴
- **QuakeBERT: Accurate Classification of Social Media Texts for Rapid Earthquake Impact Assessment** — arxiv (relevance: none)
  - **中文译名**: QuakeBERT：社交媒体文本快速地震影响评估的精确分类
- **Vibratory pile driving - Vibration in pile driving** — crossref (relevance: none)
  - **中文译名**: 振动沉桩——沉桩中的振动
- **pile driving by vibration** — crossref (relevance: none)
  - **中文译名**: 通过振动进行沉桩
- ... 等共 11 篇

### Repos (0 个)
（无）

### Datasets (0 个)
（无）

### Baselines (2 个)
- Interaction of the pile and surrounding soil during vibration driving
- Mesoscopic Investigation and Shaft Friction Resistance Modeling of Saturated Sand Under High-Frequency Vibratory Pile Driving

### Innovation Points (3 个)
- 结合高频振动沉桩的土体相互作用模型与振动对周边建筑影响的评估方法，建立考虑建筑响应的环境影响预测模型
- 将高频振动沉桩的细观砂土摩擦模型与可解释人工智能预测模型结合，实现振动预测的可解释性
- 整合高频振动沉桩的振动传播规律与表面波测试方法，建立基于现场测试的振动控制标准

### Stitching Plan (缝合方案)
- **Baseline**: 高频振动沉桩桩-土相互作用模型
- **Module B**: 建筑振动响应评估方法（来自Assessment Study on Impact of Pile Driving Vibration on Surrounding Houses）
- **Module C**: 表面波测试方法（来自Use of Surface Wave Testing to Develop Pile Driving Vibration Criteria in a Coastal Environment）

## R39-GAS — ?

- **可行性裁决**: `risky` (分数: 65)
- **可行性理由**: Baseline≥3篇，有2篇带repo，但无公开数据集且无代码仓库，需自建数据（如矿井实测瓦斯参数），存在数据获取和现场实验风险。
- **复核裁决**: `MINOR_REVISION`
- **领域**: ['unknown']
- **方法关键词**: ['Gas Outburst Risk Prediction']
- **对象关键词**: []
- **任务关键词**: []
- **关键词全英文**: ✅

### Search Steps (8 步)
- step 0: arxiv ""Gas Outburst Risk Prediction"" -> FAILED
- step 1: openalex "Gas Outburst Risk Prediction" -> 12 results
- step 2: github "Gas Outburst Risk Prediction" -> FAILED
- step 3: semantic_scholar "Gas Outburst Risk Prediction" -> FAILED
- step 4: crossref "Gas Outburst Risk Prediction" -> 12 results
- step 5: openalex "coal and gas outburst risk prediction" -> FAILED
- step 6: crossref "coal gas outburst risk prediction" -> FAILED
- step 7: STOP — 已有24篇论文，但所有可用工具均已失败且不可重试，无法继续搜索。

### Filter Results
- total: 24, kept: 24, dropped: 0, low_relevance: 0

### Verified Papers (36 篇)
- **Coal and gas outburst risk prediction based on the F-SPA model** — openalex
  - **中文译名**: 基于F-SPA模型的煤与瓦斯突出危险性预测
- **Coal and Gas Outburst Risk Prediction and Management Based on WOA-ELM** — openalex
  - **中文译名**: 基于WOA-ELM的煤与瓦斯突出危险性预测与管理
- **Risk Prediction of Coal and Gas Outburst in Deep Coal Mines Based on the SAPSO-ELM Algorithm** — openalex
  - **中文译名**: 基于SAPSO-ELM算法的深部煤矿煤与瓦斯突出危险性预测
- **A new method for coal and gas outburst prediction and prevention based on the fragmentation of ejected coal** — openalex
  - **中文译名**: 基于抛出煤破碎度的煤与瓦斯突出预测预防新方法
- **Regional Prediction of Coal and Gas Outburst Under Uncertain Conditions Based on the Spatial Distribution of Risk Index** — openalex
  - **中文译名**: 基于风险指数空间分布的不确定条件下煤与瓦斯突出区域预测
- **Risk Prediction of Coal and Gas Outburst Based on Abnormal Gas Concentration in Blasting Driving Face** — openalex
  - **中文译名**: 基于爆破工作面异常瓦斯浓度的煤与瓦斯突出危险性预测
- **Prediction method for risks of coal and gas outbursts based on spatial chaos theory using gas desorption index of drill cuttings** — openalex
  - **中文译名**: 基于钻屑瓦斯解吸指标空间混沌理论的煤与瓦斯突出危险性预测方法
- **Machine Learning Prediction and Interpretability Analysis of Coal and Gas Outburst** — crossref
  - **中文译名**: 煤与瓦斯突出的机器学习预测与可解释性分析
  - URL: https://doi.org/10.20944/preprints202512.2442.v1
  - Abstract: <jats:p>Coal and gas outbursts constitute a major hazard for mining safety, which is critical for the sustainable development of China’s energy indust...
- **Study on Compound Genetic and Back Propagation Algorithm for Prediction of Coal and Gas Outburst Risk** — crossref
  - **中文译名**: 基于复合遗传与反向传播算法的煤与瓦斯突出危险性预测研究
  - URL: https://doi.org/10.1007/978-0-387-44641-7_25
- **Research and Application of Regional Outburst Risk Prediction Based on Gas Content Method** — crossref
  - **中文译名**: 基于瓦斯含量法的区域突出危险性预测研究与应用
  - URL: https://doi.org/10.1088/1755-1315/208/1/012122
- **Study on the Prediction of Coal and Gas Outburst Risk Based on Temporal and Spatial Evolution Law of Microseismic** — crossref
  - **中文译名**: 基于微震时空演化规律的煤与瓦斯突出危险性预测研究
  - URL: https://doi.org/10.2139/ssrn.5258521
- **REAL COAL AND GAS OUTBURST RISK AND OUTBURST CONDITION JUDGMENT OF GASSY COAL** — crossref
  - **中文译名**: 高瓦斯煤的真实煤与瓦斯突出风险及突出条件判断
  - URL: https://doi.org/10.1142/9789814749503_0028
- **Mine Coal and Gas Outburst Prediction Area** — crossref
  - **中文译名**: 矿井煤与瓦斯突出预测区域
  - URL: https://doi.org/10.4028/www.scientific.net/amm.157-158.484
  - Abstract: <jats:p>In this paper, based on geological power division method of qidong well find out fault block coal mine, determined the change law of the groun...
- **Coal and Gas Outburst Prediction Method Integrating Acoustic Emission -Electromagnetic Radiation -Gas Concentration -Fiber Optic Strain Multi-Parameter Fusion Based on AutoGluon** — crossref
  - **中文译名**: 基于AutoGluon的声发射-电磁辐射-瓦斯浓度-光纤应变多参数融合的煤与瓦斯突出预测方法
  - URL: https://doi.org/10.2139/ssrn.5766202
- **Influence of temperature on gas desorption characterization in the whole process from coals and its application analysis on outburst risk prediction** — openalex
  - **中文译名**: 温度对煤全过程瓦斯解吸特征的影响及其在突出危险性预测中的应用分析
- ... 等共 36 篇

### Weak Papers (19 篇)
- **Management of outburst in underground coal mines** — openalex (relevance: none)
  - **中文译名**: 地下煤矿突出灾害管理
- **Risk prediction and factors risk analysis based on IFOA-GRNN and apriori algorithms: Application of artificial intelligence in accident prevention** — openalex (relevance: none)
  - **中文译名**: 基于IFOA-GRNN与Apriori算法的风险预测及因素风险分析：人工智能在事故预防中的应用
- **A novel edge computing architecture for intelligent coal mining system** — semantic_scholar (relevance: none)
  - **中文译名**: 面向智能煤矿系统的新型边缘计算架构
- **Integrating Elman recurrent neural network with particle swarm optimization algorithms for an improved hybrid training of multidisciplinary datasets** — semantic_scholar (relevance: none)
  - **中文译名**: 集成Elman递归神经网络与粒子群优化算法的多学科数据集混合训练改进方法
- **Early Warning of Gas Concentration in Coal Mines Production Based on Probability Density Machine** — semantic_scholar (relevance: none)
  - **中文译名**: 基于概率密度机的煤矿生产瓦斯浓度早期预警
- ... 等共 19 篇

### Repos (0 个)
（无）

### Datasets (0 个)
（无）

### Baselines (19 个)
- Coal and gas outburst risk prediction based on the F-SPA model
- Coal and Gas Outburst Risk Prediction and Management Based on WOA-ELM
- Risk Prediction of Coal and Gas Outburst in Deep Coal Mines Based on the SAPSO-ELM Algorithm
- Machine Learning Prediction and Interpretability Analysis of Coal and Gas Outburst
- Study on Compound Genetic and Back Propagation Algorithm for Prediction of Coal and Gas Outburst Risk
- Coal and gas outburst prediction model based on extension theory and its application
- A novel combined intelligent algorithm prediction model for the risk of the coal and gas outburst
- Prediction of Coal and Gas Outburst Risk in West No. 2 Mining Area of Weijiadi Coal Mine
- Prediction of coal and gas outburst risk by fuzzy rock engineering system
- Prediction Method of Coal and Gas Outburst Intensity Based on Digital Twin and Deep Learning

### Innovation Points (3 个)
- 将Parallel论文中的空间混沌理论（基于钻屑瓦斯解吸指标）与Baseline中的WOA-ELM模型结合，构建空间混沌特征增强的WOA-ELM预测模型。
- 将Parallel论文中的抛煤破碎度指标作为新特征，融入Baseline中的F-SPA模型，提升模型对突出强度的预测能力。
- 将Parallel论文中的爆破工作面异常瓦斯浓度特征与Baseline中的SAPSO-ELM算法结合，构建针对掘进面的动态预警模型。

### Stitching Plan (缝合方案)
- **Baseline**: WOA-ELM
- **Module B**: 空间混沌特征提取模块（来自Parallel论文：Prediction method for risks of coal and gas outbursts based on spatial chaos theory using gas desorption index of drill cuttings）
- **Module C**: 无