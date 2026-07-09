# PaperAgent Re3.9.4 — 3篇测试结果与标答汇总

> 本文档汇总 R39-CONS、R39-PILE、R39-GAS 三个 case 的最终结果。

- **数据来源**: tmp_re13_eval
- **case 总数**: 3

## 总览

| Case ID | 题目 | 论文数 | Repo | Dataset | Baseline | 可行性 | 评审 |
|---|---|---|---|---|---|---|---|
| R39-CONS | ? | 3 | 4 | 0 | 3 | feasible(82) | MINOR_REVISION |
| R39-PILE | ? | 9 | 0 | 0 | 2 | risky(55) | MINOR_REVISION |
| R39-GAS | ? | 36 | 0 | 0 | 19 | risky(65) | MINOR_REVISION |


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
- total: 12
- kept: 12
- dropped: 0
- low_relevance: 0

### Verified Papers (3 篇)
- **Deep Convolutional Neural Network with Differential Feature Maps for Construction Safety Risks Assessment of Bridge Engineering** — crossref
  - URL: https://doi.org/10.1109/icdsns62112.2024.10691175
- **Early warning control model and simulation study of engineering safety risk based on a convolutional neural network** — crossref
  - URL: https://doi.org/10.1007/s00521-022-08170-9
- **Construction of Safety Early Warning Model for Construction of Engineering Based on Convolution Neural Network** — crossref
  - URL: https://doi.org/10.1155/2022/8937084
  - Abstract: <jats:p>In recent years, China’s engineering construction management level has been greatly improved, but compared with other industries, the construc...

### Weak Papers (16 篇)
- **Urban safety network for long-term structural health monitoring of buildings using convolutional neural network** — crossref (relevance: none)
- **Early Warning Classification of Geotechnical Engineering Construction Safety using Clique Graph Convolutional Network with Fast Sigmoid Activation** — crossref (relevance: none)
- **Smart safety early warning model of landslide geological hazard based on BP neural network** — crossref (relevance: none)
- **Research on construction engineering safety early warning based on BP neural network** — crossref (relevance: none)
- **Application of Soft Computing to Address Uncertainty in Construction Project Management: A Systematic Literature Review** — semantic_scholar (relevance: none)
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
- total: 55
- kept: 51
- dropped: 0
- low_relevance: 4

### Verified Papers (9 篇)
- **Assessment Study on Impact of Pile Driving Vibration on Surrounding Houses** — crossref
  - URL: https://doi.org/10.4028/www.scientific.net/amr.457-458.325
  - Abstract: <jats:p>It’s common to see the dispute caused by pile driving construction vibration effect, which has become a concern of social problems. The paper ...
- **Pile-driving Induced Vibration and its Transmission to Buildings** — crossref
  - URL: https://doi.org/10.1177/026309239201100302
  - Abstract: <jats:p>The paper reports a case study of pile-driving induced vibration and its transmission to buildings which was carried out in the construction s...
- **Interaction of the pile and surrounding soil during vibration driving** — crossref
  - URL: https://doi.org/10.1088/1757-899x/456/1/012093
- **Developing an Explainable Artificial Intelligent (XAI) Model for Predicting Pile Driving Vibrations in Bangkok's Subsoil** — arxiv
  - URL: http://arxiv.org/abs/2409.05918v1
  - Abstract: This study presents an explainable artificial intelligent (XAI) model for predicting pile driving vibrations in Bangkok's soft clay subsoil. A deep ne...
- **Mesoscopic Investigation and Shaft Friction Resistance Modeling of Saturated Sand Under High-Frequency Vibratory Pile Driving** — crossref
  - URL: https://doi.org/10.2139/ssrn.5079506
- **A case study on safe sheet pile driving with vibration monitoring** — crossref
  - URL: https://doi.org/10.1201/9781003762478-20
- **Use of Surface Wave Testing to Develop Pile Driving Vibration Criteria in a Coastal Environment** — crossref
  - URL: https://doi.org/10.1061/9780784484043.012
- **Vibration and dynamic settlement from pile driving** — crossref
  - URL: https://doi.org/10.1680/bop.44548.0016
- **Numerical evaluation of pile vibration and noise emission during offshore pile driving** — crossref
  - URL: https://doi.org/10.1016/j.apacoust.2015.05.008

### Weak Papers (11 篇)
- **Measuring the right thing: justifying metrics in AI impact assessments** — arxiv (relevance: none)
- **When and How AI Should Assist Brainstorming for AI Impact Assessment** — arxiv (relevance: none)
- **QuakeBERT: Accurate Classification of Social Media Texts for Rapid Earthquake Impact Assessment** — arxiv (relevance: none)
- **Vibratory pile driving - Vibration in pile driving** — crossref (relevance: none)
- **pile driving by vibration** — crossref (relevance: none)
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
- total: 24
- kept: 24
- dropped: 0
- low_relevance: 0

### Verified Papers (36 篇)
- **Coal and gas outburst risk prediction based on the F-SPA model** — openalex
- **Coal and Gas Outburst Risk Prediction and Management Based on WOA-ELM** — openalex
- **Risk Prediction of Coal and Gas Outburst in Deep Coal Mines Based on the SAPSO-ELM Algorithm** — openalex
- **A new method for coal and gas outburst prediction and prevention based on the fragmentation of ejected coal** — openalex
- **Regional Prediction of Coal and Gas Outburst Under Uncertain Conditions Based on the Spatial Distribution of Risk Index** — openalex
- **Risk Prediction of Coal and Gas Outburst Based on Abnormal Gas Concentration in Blasting Driving Face** — openalex
- **Prediction method for risks of coal and gas outbursts based on spatial chaos theory using gas desorption index of drill cuttings** — openalex
- **Machine Learning Prediction and Interpretability Analysis of Coal and Gas Outburst** — crossref
  - URL: https://doi.org/10.20944/preprints202512.2442.v1
  - Abstract: <jats:p>Coal and gas outbursts constitute a major hazard for mining safety, which is critical for the sustainable development of China’s energy indust...
- **Study on Compound Genetic and Back Propagation Algorithm for Prediction of Coal and Gas Outburst Risk** — crossref
  - URL: https://doi.org/10.1007/978-0-387-44641-7_25
- **Research and Application of Regional Outburst Risk Prediction Based on Gas Content Method** — crossref
  - URL: https://doi.org/10.1088/1755-1315/208/1/012122
- **Study on the Prediction of Coal and Gas Outburst Risk Based on Temporal and Spatial Evolution Law of Microseismic** — crossref
  - URL: https://doi.org/10.2139/ssrn.5258521
- **REAL COAL AND GAS OUTBURST RISK AND OUTBURST CONDITION JUDGMENT OF GASSY COAL** — crossref
  - URL: https://doi.org/10.1142/9789814749503_0028
- **Mine Coal and Gas Outburst Prediction Area** — crossref
  - URL: https://doi.org/10.4028/www.scientific.net/amm.157-158.484
  - Abstract: <jats:p>In this paper, based on geological power division method of qidong well find out fault block coal mine, determined the change law of the groun...
- **Coal and Gas Outburst Prediction Method Integrating Acoustic Emission -Electromagnetic Radiation -Gas Concentration -Fiber Optic Strain Multi-Parameter Fusion Based on AutoGluon** — crossref
  - URL: https://doi.org/10.2139/ssrn.5766202
- **Influence of temperature on gas desorption characterization in the whole process from coals and its application analysis on outburst risk prediction** — openalex
- ... 等共 36 篇

### Weak Papers (19 篇)
- **Management of outburst in underground coal mines** — openalex (relevance: none)
- **Risk prediction and factors risk analysis based on IFOA-GRNN and apriori algorithms: Application of artificial intelligence in accident prevention** — openalex (relevance: none)
- **A novel edge computing architecture for intelligent coal mining system** — semantic_scholar (relevance: none)
- **Integrating Elman recurrent neural network with particle swarm optimization algorithms for an improved hybrid training of multidisciplinary datasets** — semantic_scholar (relevance: none)
- **Early Warning of Gas Concentration in Coal Mines Production Based on Probability Density Machine** — semantic_scholar (relevance: none)
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