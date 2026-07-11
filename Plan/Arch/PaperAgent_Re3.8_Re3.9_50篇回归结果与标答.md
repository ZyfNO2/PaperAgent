# PaperAgent Re3.8+Re3.9 — 50篇回归结果与标答汇总

> 本文档汇总 Re3.8/Re3.9 回归测试中各 case 的最终结果（论文/Repo/Dataset/Baselines/创新点/缝合方案/研究叙事）以及对应的标答（Ground Truth）。

- **数据来源**: tmp\_re34\_eval, tmp\_re35\_eval, tmp\_re36\_eval, tmp\_re38\_eval
- **标答来源**: Re3.0 Batch20 标答 + 100篇测试集一级标注
- **case 总数**: 见下表

## 总览

| Case ID  | 题目                        | 论文数 | Repo | Dataset | Baseline | 可行性          | 评审              |
| -------- | ------------------------- | --- | ---- | ------- | -------- | ------------ | --------------- |
| R34-002  | 基于深度学习的磁瓦在线检测技术研究         | 10  | 13   | 0       | 9        | feasible(75) | MINOR\_REVISION |
| R34-033  | 基于YOLOV5的肺结节检测算法研究        | 9   | 1    | 1       | 8        | feasible(85) | ACCEPT          |
| R34-038  | 基于深度学习的无人机图像目标检测算法研究      | 31  | 4    | 5       | 27       | feasible(82) | ACCEPT          |
| R34-046  | 基于视觉的机械臂目标检测和避障路径规划研究与应用  | 11  | 0    | 0       | 11       | feasible(75) | ACCEPT          |
| R34-066  | 面向自动驾驶中多模态融合感知算法的攻击和防御    | 3   | 0    | 0       | 3        | risky(45)    | MINOR\_REVISION |
| R34-092  | 海上风机叶片缺陷检测及分类             | 5   | 12   | 0       | 5        | feasible(75) | ACCEPT          |
| R34-S01  | 基于多视差一致性的伪深度图误差过滤方法       | 5   | 0    | 0       | 5        | feasible(75) | MINOR\_REVISION |
| R34-S02  | 无人机ZED立体匹配网络训练与评测研究       | 14  | 3    | 2       | 4        | feasible(85) | ACCEPT          |
| R34-S03  | 深度先验引导的无监督立体匹配与视差置信度估计    | 16  | 11   | 1       | 16       | feasible(75) | ACCEPT          |
| R34-S03R | 深度先验引导的无监督立体匹配与视差置信度估计    | 18  | 11   | 1       | 12       | feasible(75) | ACCEPT          |
| R34-S04  | 基于三维点云重建的混凝土结构裂缝定位与追踪     | 15  | 0    | 0       | 6        | feasible(75) | ACCEPT          |
| R35-033  | 基于YOLOV5的肺结节检测算法研究        | 9   | 1    | 1       | 7        | feasible(78) | ACCEPT          |
| R35-046  | 基于视觉的机械臂目标检测和避障路径规划研究与应用  | 15  | 0    | 0       | 2        | feasible(75) | MINOR\_REVISION |
| R36-003  | 基于点云多平面检测的三维重建关键技术研究      | 5   | 0    | 0       | 2        | risky(45)    | MINOR\_REVISION |
| R36-007  | 基于视觉的无人机识别与跟踪技术研究         | 18  | 2    | 0       | 17       | feasible(75) | MINOR\_REVISION |
| R36-015  | 基于患者虚拟定位的三维人体重建关键技术研究     | 14  | 0    | 0       | 12       | risky(45)    | MINOR\_REVISION |
| R36-021  | 基于深度学习的自动驾驶感知算法研究         | 55  | 12   | 6       | 6        | feasible(78) | ACCEPT          |
| R36-052  | 基于深度强化学习的无人驾驶感知与决策研究      | 4   | 12   | 0       | 3        | feasible(85) | ACCEPT          |
| R36-060  | 基于深度学习的车道线检测方法研究          | 3   | 12   | 0       | 2        | feasible(75) | ACCEPT          |
| R36-074  | 基于深度学习的混凝土桥梁裂缝检测研究        | 43  | 5    | 3       | 40       | feasible(82) | ACCEPT          |
| R36-079  | 基于结构光的隧道裂缝检测技术研究与实现       | 10  | 0    | 0       | 2        | risky(55)    | MINOR\_REVISION |
| R36-084  | 基于U-Net卷积网络的地质岩层裂缝检测方法    | 9   | 0    | 0       | 8        | feasible(75) | ACCEPT          |
| R36-091  | 基于云计算的输电线路缺陷检测平台          | 5   | 0    | 0       | 1        | risky(45)    | MINOR\_REVISION |
| R36-094  | 基于SCADA数据的风机叶片结冰诊断研究      | 37  | 0    | 0       | 35       | risky(45)    | MINOR\_REVISION |
| R36-100  | 基于深度学习的配电设备视觉识别技术研究       | 7   | 0    | 2       | 3        | risky(45)    | MINOR\_REVISION |
| R38-004  | 基于深度学习的医学图像分割算法研究         | 8   | 12   | 0       | 3        | risky(65)    | MINOR\_REVISION |
| R38-005  | 基于深度学习的钢材表面缺陷检测算法研究       | 38  | 12   | 2       | 35       | feasible(88) | ACCEPT          |
| R38-006  | 基于深度学习的三维物体重建技术研究         | 6   | 12   | 0       | 1        | risky(55)    | MINOR\_REVISION |
| R38-008  | 基于机器视觉的PCB缺陷检测系统研究        | 45  | 3    | 1       | 14       | feasible(88) | ACCEPT          |
| R38-009  | 点云的三维重建与纹理映射              | 31  | 0    | 1       | 6        | risky(55)    | MINOR\_REVISION |
| R38-011  | 基于深度学习的锂电池表面缺陷检测方法研究      | 16  | 1    | 1       | 10       | feasible(88) | ACCEPT          |
| R38-013  | 基于机器视觉的板类堆叠零件分拣系统研究       | 4   | 0    | 0       | 1        | risky(55)    | MINOR\_REVISION |
| R38-014  | 基于生成对抗网络的织物缺陷检测算法研究       | 26  | 0    | 0       | 22       | risky(65)    | MINOR\_REVISION |
| R38-018  | 基于深度学习的三维点云补全方法研究         | 17  | 9    | 2       | 12       | feasible(88) | ACCEPT          |
| R38-023  | 基于深度学习的焊缝缺陷检测技术研究         | 42  | 12   | 1       | 31       | feasible(85) | ACCEPT          |
| R38-026  | 基于深度卷积神经网络的巡检图像电力部件识别方法研究 | 3   | 0    | 0       | 1        | risky(55)    | MINOR\_REVISION |
| R38-027  | 基于深度学习的农作物病虫害检测研究         | 48  | 12   | 5       | 42       | feasible(88) | ACCEPT          |
| R38-029  | 基于多种数据库的改进YOLO算法研究        | 10  | 0    | 0       | 7        | risky(65)    | MINOR\_REVISION |
| R38-034  | 基于深度学习的目标检测算法研究           | 4   | 12   | 0       | 1        | risky(55)    | MINOR\_REVISION |
| R38-037  | 基于无人机遥感的森林火灾检测算法研究        | 41  | 1    | 1       | 20       | feasible(88) | ACCEPT          |
| R38-040  | 基于改进YOLO网络与极限学习机的绝缘子故障检测  | 14  | 0    | 0       | 13       | risky(65)    | MINOR\_REVISION |
| R38-043  | 基于无人机平台的动态目标检测系统开发        | 35  | 1    | 1       | 14       | feasible(85) | ACCEPT          |
| R38-047  | 基于深度学习的交通标志识别算法研究         | 43  | 12   | 1       | 29       | feasible(88) | ACCEPT          |
| R38-049  | 基于特征点的目标位姿估计与机械臂抓取控制      | 25  | 0    | 1       | 10       | risky(55)    | MINOR\_REVISION |
| R38-050  | 基于深度学习的行人检测与跟踪算法研究        | 26  | 12   | 3       | 23       | feasible(82) | ACCEPT          |
| R38-057  | 基于深度相机的机械臂动态避障规划研究        | 23  | 0    | 0       | 8        | risky(65)    | MINOR\_REVISION |
| R38-067  | 基于深度学习的车辆检测及应用研究          | 18  | 12   | 2       | 12       | feasible(85) | ACCEPT          |
| R38-075  | 基于深度学习的混凝土路面裂缝检测研究        | 38  | 0    | 2       | 36       | feasible(88) | ACCEPT          |
| R38-076  | 基于深度学习的道路裂缝检测研究           | 45  | 12   | 3       | 45       | feasible(88) | ACCEPT          |
| R38-083  | 基于多分辨率网络的桥梁裂缝分割算法研究       | 5   | 0    | 0       | 5        | risky(50)    | ACCEPT          |
| R38-095  | 基于深度学习的输电杆塔关键点检测方法研究      | 11  | 0    | 1       | 1        | feasible(78) | MINOR\_REVISION |
| R38-096  | 基于石墨烯薄膜电热效应的风机叶片防冰除冰系统研究  | 17  | 0    | 0       | 11       | risky(65)    | MINOR\_REVISION |
| R38-098  | 基于深度学习的接触网绝缘子识别及其污秽检测技术研究 | 19  | 0    | 0       | 19       | risky(65)    | MINOR\_REVISION |

**总计**: 53 cases

## R34-002 — 基于深度学习的磁瓦在线检测技术研究

- **可行性裁决**: `feasible` (分数: 75)
- **可行性理由**: 有9篇baseline论文（含1篇有repo的UniNet）和13个代码仓库，但无公开数据集，需自建数据集。
- **复核裁决**: `MINOR_REVISION`
- **领域**: vision\_2d
- **方法关键词**: \['deep learning']
- **对象关键词**: \['magnetic tile']

### Verified Papers (10 篇)

- **Performance Evaluation of Deep Learning Architectures for Tile Defect Detection** — crossref
  - URL: <https://doi.org/10.64470/elene.2025.16>
  - Abstract: \<jats:p xml:lang="tr">In this study, an artificial intelligence-based quality control system was developed for the automatic detection and classificat...
- **Segmentation Method of Magnetic Tile Surface Defects Based on Deep Learning** — openalex
- **FFCNN: A Deep Neural Network for Surface Defect Detection of Magnetic Tile** — openalex
- **A hierarchical feature-logit-based knowledge distillation scheme for internal defect detection of magnetic tiles** — openalex
- **A semi-supervised learning method for surface defect classification of magnetic tiles** — openalex
- **UniNet: a real-time edge subdivision network for enhancing industrial products surface defect detection performance** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/cb37597783d0cfc79bfafa766ac7d1495d7c74ce>
- **Surface defect saliency of magnetic tile** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/a62b0b8ff07bdbcf4fd1c8449acac1f24d8434c4>
- **A Lightweight Transfer Learning Model with Pruned and Distilled YOLOv5s to Identify Arc Magnet Surface Defects** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/d8a3a938740f235201d7b76fa27740a04576460e>
  - Abstract: Surface defects in arc magnets constitute the main culprit for performance degradation and safety hazards in permanent magnet motors. Machine-vision m...
- **Small Defect Detection Based on Local Structure Similarity for Magnetic Tile Surface** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/f64e4ee2ba7c30eddc37d8785f9870aa9e91482e>
  - Abstract: Surface defect detection is critical in manufacturing magnetic tiles to improve production yield. However, existing detection methods are difficult to...
- **Entropy-Driven Adaptive Neighborhood Selection and Fitting for Sub-Millimeter Defect Detection and Quantitative Evaluation in Magnetic Tiles** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/8c1ffda09559db7515b296ccd0b2a39430aff4a5>
  - Abstract: Surface defects in magnetic tiles pose significant challenges to the performance and reliability of permanent magnet motors. Traditional defect detect...

### Weak Papers (50 篇)

- **A multitask deep learning model for real-time deployment in embedded systems** — arxiv
- **DILIE: Deep Internal Learning for Image Enhancement** — arxiv
- **Deep Learning Based Automatic Defect Detection System for Tile Walls** — crossref
- **Impact of Deep Learning Libraries on Online Adaptive Lightweight Time Series Anomaly Detection** — crossref
- **Visual-Based Defect Detection and Classification Approaches for Industrial Applications—A SURVEY** — openalex
- ... 等共 50 篇

### Repos (13 个)

- **?**
  - URL: <https://github.com/Oumllack/Petroleum-Drilling-Computer-Vision>
- **?**
  - URL: <https://github.com/MitraDP/Detection-of-Surface-Defects-in-Magnetic-Tile-Images>
- **?**
  - URL: <https://github.com/Clarkxielf/Multimodal-Fusion-Convolutional-Neural-Network-for-Internal-Defect-Detection-of-Magnetic-Tile>
- **?**
  - URL: <https://github.com/albertchristianto/defect_detection>
- **?**
  - URL: <https://github.com/Clarkxielf/A-hierarchical-feature-logit-based-knowledge-distillation-scheme-for-internal-defect-detection>
- **?**
  - URL: <https://github.com/beyzaatosun/Defect-Detection>
- **?**
  - URL: <https://github.com/share2code99/magnetic_tile_defect_detection_yolo11_seg>
- **?**
  - URL: <https://github.com/chenqili2020/Damage_detection>
- **?**
  - URL: <https://github.com/Faiza-Waheed/Magnetic-Tile-Surface-Defects>
- **?**
  - URL: <https://github.com/FrozenP1anet/Magnetic-Tile-Defect-Detection-using-FPGA>

### Datasets (0 个)

（无）

### Baselines (9 个)

- Segmentation Method of Magnetic Tile Surface Defects Based on Deep Learning
- FFCNN: A Deep Neural Network for Surface Defect Detection of Magnetic Tile
- A hierarchical feature-logit-based knowledge distillation scheme for internal defect detection of magnetic tiles
- A semi-supervised learning method for surface defect classification of magnetic tiles
- UniNet: a real-time edge subdivision network for enhancing industrial products surface defect detection performance
- Surface defect saliency of magnetic tile
- A Lightweight Transfer Learning Model with Pruned and Distilled YOLOv5s to Identify Arc Magnet Surface Defects
- Small Defect Detection Based on Local Structure Similarity for Magnetic Tile Surface
- Entropy-Driven Adaptive Neighborhood Selection and Fitting for Sub-Millimeter Defect Detection and Quantitative Evaluation in Magnetic Tiles

### Innovation Points (3 个)

- 将UniNet的边缘细分模块与FFCNN的深层特征提取网络结合，提升磁瓦表面缺陷检测的精度和边缘定位能力
- 将层次化特征-逻辑知识蒸馏方法应用于磁瓦内部缺陷检测，结合半监督学习策略提升小样本场景下的检测性能
- 将Performance Evaluation论文中的多架构评估策略与FFCNN的缺陷检测网络结合，构建自适应架构选择机制

### Stitching Plan (缝合方案)

- **Baseline**: FFCNN
- **Module B**: UniNet的边缘细分模块
- **Module C**: Performance Evaluation论文的多架构评估模块

### 标答 (Ground Truth)

- **领域**: 工业缺陷/钢铁
- **可行性**: `feasible`
- **标准 Baselines**: YOLOv5, ResNet
- **标准 Datasets**: NEU-DET, GC10-DET
- **标准 Repos**: ultralytics/yolov5

## R34-033 — 基于YOLOV5的肺结节检测算法研究

- **可行性裁决**: `feasible` (分数: 85)
- **可行性理由**: 有5篇baseline论文，其中3篇有代码仓库，1个匹配数据集，1个代码仓库，证据充足，可保毕业。
- **复核裁决**: `ACCEPT`
- **领域**: medical\_ai
- **方法关键词**: \['YOLOV5']
- **对象关键词**: \['lung nodule']

### Verified Papers (9 篇)

- **Lung Nodule Detection in Medical Images Based on Improved YOLOv5s** — openalex
- **An improved YOLOv5 network for lung nodule detection** — crossref
  - URL: <https://doi.org/10.1109/eiecs53707.2021.9588065>
- **Based on the Improved YOLOv5 Lung Nodule Detection Method** — crossref
  - URL: <https://doi.org/10.12677/sea.2023.122026>
- **Lung Nodule Detection Algorithm Based on Improved YOLOv5 Network Modeling** — crossref
  - URL: <https://doi.org/10.1109/iceict61637.2024.10671019>
- **A Model for Lung Nodule Detection using a Hybrid Approach by Combining YOLOv5 and ResNet101 Pretrained Artificial Intelligence Models** — crossref
  - URL: <https://doi.org/10.5829/ije.2026.39.09c.15>
- **Nodules Detection in Lungs CT Images Using Improved YOLOV5 and Classification of Types of Nodules by CNN-SVM** — openalex
- **Identification of lung nodules CT scan using YOLOv5 based on convolution neural network** — arxiv
  - URL: <http://arxiv.org/abs/2301.02166v1>
  - Abstract: Purpose: The lung nodules localization in CT scan images is the most difficult task due to the complexity of the arbitrariness of shape, size, and tex...
- **LNA-Net: Enhancing detection and classification of benign and malignant pulmonary nodules in CT scans** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/f502997a7cc7c95aba6c9eac6c72ea9065b9b04b>
- **YOLOv5-Z:A Target Detection Algorithm Suitable for New Theories of Medical Image Recognition** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/403e18a68803baac6e40718f95adcc5840a8e443>
  - Abstract: The enhanced YOLO algorithm YOLOv5-Z is designed for precise target detection. This paper primarily focuses on optimizing the YOLOv5 target detection ...

### Weak Papers (41 篇)

- **Domain Adaptive Lung Nodule Detection in X-ray Image** — arxiv
- **X-ray Dissectography Improves Lung Nodule Detection** — arxiv
- **S4ND: Single-Shot Single-Scale Lung Nodule Detection** — arxiv
- **AttentNet: Fully Convolutional 3D Attention for Lung Nodule Detection** — arxiv
- **Crowdsourcing Lung Nodules Detection and Annotation** — arxiv
- ... 等共 41 篇

### Repos (1 个)

- **?**
  - URL: <https://github.com/anujmundu/lung-nodule-detection>

### Datasets (1 个)

- **COCO** (source: paper\_title\_heuristic)

### Baselines (8 个)

- Lung Nodule Detection in Medical Images Based on Improved YOLOv5s
- An improved YOLOv5 network for lung nodule detection
- Based on the Improved YOLOv5 Lung Nodule Detection Method
- Lung Nodule Detection Algorithm Based on Improved YOLOv5 Network Modeling
- Nodules Detection in Lungs CT Images Using Improved YOLOV5 and Classification of Types of Nodules by CNN-SVM
- Identification of lung nodules CT scan using YOLOv5 based on convolution neural network
- LNA-Net: Enhancing detection and classification of benign and malignant pulmonary nodules in CT scans
- YOLOv5-Z:A Target Detection Algorithm Suitable for New Theories of Medical Image Recognition

### Innovation Points (3 个)

- 在YOLOv5s骨干网络中引入注意力机制（如CBAM）以增强肺结节特征提取能力，同时使用CIoU损失函数优化边界框回归精度。
- 结合YOLOv5与ResNet101预训练模型进行混合特征提取，利用ResNet101的深层语义信息提升小结节检测能力。
- 在YOLOv5检测头后添加CNN-SVM分类器，对检测到的结节进行良恶性分类，提升分类准确率。

### Stitching Plan (缝合方案)

- **Baseline**: YOLOv5s
- **Module B**: CBAM注意力模块（来自Lung Nodule Detection in Medical Images Based on Improved YOLOv5s）
- **Module C**: ResNet101特征融合分支（来自A Model for Lung Nodule Detection using a Hybrid Approach by Combining YOLOv5 and ResNet101 Pretrained Artificial Intelligence Models）

### 标答 (Ground Truth)

- **领域**: 医学/肺结节
- **可行性**: `risky`
- **标准 Baselines**: U-Net, YOLOv5
- **标准 Datasets**: LUNA16, LIDC-IDRI
- **标准 Repos**: ultralytics/yolov5

## R34-038 — 基于深度学习的无人机图像目标检测算法研究

- **可行性裁决**: `feasible` (分数: 82)
- **可行性理由**: 27篇baseline论文中，R-FCN、OHEM、Fast animal detection有代码仓库，且数据集5个，代码仓库4个，支撑充分。
- **复核裁决**: `ACCEPT`
- **领域**: vision\_2d
- **方法关键词**: \['deep learning']
- **对象关键词**: \['UAV image']

### Verified Papers (31 篇)

- **Detecting mammals in UAV images: Best practices to address a substantially imbalanced dataset with deep learning** — openalex
- **Deep learning-based object detection in low-altitude UAV datasets: A survey** — openalex
- **UAV-YOLOv8: A Small-Object-Detection Model Based on Improved YOLOv8 for UAV Aerial Photography Scenarios** — openalex
- **R-FCN: Object Detection via Region-based Fully Convolutional Networks** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/b724c3f7ff395235b62537203ddeb710f0eb27bb>
  - Abstract: We present region-based, fully convolutional networks for accurate and efficient object detection. In contrast to previous region-based detectors such...
- **Training Region-Based Object Detectors with Online Hard Example Mining** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/63333669bcf694aba2e1928f6060ab1d6a5161fe>
  - Abstract: The field of object detection has made significant advances riding on the wave of region-based ConvNets, but their training procedure still includes m...
- **Fast animal detection in UAV images using convolutional neural networks** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/4aad0edbb0aab2cde98fbd63687e88393fb2c876>
- **Evaluating machine learning models for multi‐species wildlife detection and identification on remote sensed nadir imagery in South African savanna** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/a7171d92775cdcc368373f77c78cece779753a2c>
  - Abstract: This research paper investigates the efficacy of leading machine learning (ML) models for detecting and identifying ungulate species in African savann...
- **Lightweight Object Detection Algorithm for UAV Aerial Imagery** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/a5ea68286916f98898c23852101bbe55a72589ce>
  - Abstract: Addressing the challenges of low detection precision and excessive parameter volume presented by the high resolution, significant scale variations, an...
- **A Light-Weight Network for Small Insulator and Defect Detection Using UAV Imaging Based on Improved YOLOv5** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/6f5030e7632204b3c5e8bf9b1b149619c787c6dc>
  - Abstract: Insulator defect detection is of great significance to compromise the stability of the power transmission line. The state-of-the-art object detection ...
- **UAV-based Wildlife Detection using Deep Learning and Resource-Constrained Edge Devices** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/8b4689f663718e61e9d841edb58aeeae4860fffe>
  - Abstract: Monitoring and conserving wildlife involves various hurdles to overcome, which include needing to observe the wildlife from a safe distance while rema...
- ... 等共 31 篇

### Weak Papers (42 篇)

- **Remote Sensing Object Detection in the Deep Learning Era—A Review** — openalex
- **Oriented object detection in optical remote sensing images using deep learning: a survey** — arxiv
- **DILIE: Deep Internal Learning for Image Enhancement** — arxiv
- **DCIL: Deep Contextual Internal Learning for Image Restoration and Image Retargeting** — arxiv
- **RIS-assisted UAV Communications for IoT with Wireless Power Transfer Using Deep Reinforcement Learning** — arxiv
- ... 等共 42 篇

### Repos (4 个)

- **?**
  - URL: <https://github.com/SomiaImdad/Plant-Disease-Diagnostics-using-UAV-and-Android-APP>
- **?**
  - URL: <https://github.com/LeadingIndiaAI/Computer-Vision-for-Wildlife-Conservation>
- **?**
  - URL: <https://github.com/sharat910/Deep-Salient-Object-Detection-in-UAV-Imagery>
- **?**
  - URL: <https://github.com/AmirthaB/Plant-Counting-and-Localization-Using-YOLOv11s>

### Datasets (5 个)

- **Pascal VOC** (source: paper\_title\_heuristic)
- **COCO** (source: paper\_title\_heuristic)
- **VisDrone** (source: paper\_title\_heuristic)
- **CIFAR** (source: paper\_title\_heuristic)
- **DOTA** (source: paper\_title\_heuristic)

### Baselines (27 个)

- Detecting mammals in UAV images: Best practices to address a substantially imbalanced dataset with deep learning
- UAV-YOLOv8: A Small-Object-Detection Model Based on Improved YOLOv8 for UAV Aerial Photography Scenarios
- R-FCN: Object Detection via Region-based Fully Convolutional Networks
- Training Region-Based Object Detectors with Online Hard Example Mining
- Fast animal detection in UAV images using convolutional neural networks
- Lightweight Object Detection Algorithm for UAV Aerial Imagery
- UAV-based Wildlife Detection using Deep Learning and Resource-Constrained Edge Devices
- AEWD: A weakly observable object detection benchmark for UAV-based endangered wildlife monitoring
- Small-Object Detection for UAV-Based Images Using a Distance Metric Method
- Target Detection Method of UAV Aerial Imagery Based on Improved YOLOv5

### Innovation Points (3 个)

- 针对无人机图像中目标小、背景复杂的问题，结合Swin Transformer的自注意力机制与YOLOv8的C2f模块，构建Swin-C2f混合特征提取模块，提升小目标检测精度。
- 针对无人机图像中目标类别不平衡问题，引入在线难例挖掘（OHEM）策略到YOLOv8的训练流程，自动选择高损失样本进行反向传播，提升稀有类别检测性能。
- 针对无人机图像中目标尺度差异大、小目标密集的问题，在YOLOv8中集成R-FCN的位置敏感RoI池化层，增强对密集小目标的定位能力。

### Stitching Plan (缝合方案)

- **Baseline**: UAV-YOLOv8
- **Module B**: Swin Transformer Block（来自Swin-Transformer-Based YOLOv5）
- **Module C**: OHEM难例挖掘（来自Training Region-Based Object Detectors with Online Hard Example Mining）

### 标答 (Ground Truth)

- **领域**: 遥感/无人机
- **可行性**: `feasible`
- **标准 Baselines**: YOLOv5, ResNet
- **标准 Datasets**: DOTA, VisDrone, UAVDT
- **标准 Repos**: ultralytics/yolov5

## R34-046 — 基于视觉的机械臂目标检测和避障路径规划研究与应用

- **可行性裁决**: `feasible` (分数: 75)
- **可行性理由**: 5篇baseline论文中有4篇提供代码仓库，覆盖视觉检测与避障路径规划核心模块，但无公开数据集和parallel论文，需自行采集数据。
- **复核裁决**: `ACCEPT`
- **领域**: unknown
- **方法关键词**: \['避障路径规划研究']
- **对象关键词**: \[]

### Verified Papers (11 篇)

- **Vision-based obstacle avoidance robotic arm path planning based on a multi-level PPO framework** — crossref
  - URL: <https://doi.org/10.1016/j.rineng.2025.107021>
- **Fast Robot Arm Inverse Kinematics and Path Planning Under Complex Static and Dynamic Obstacle Constraints** — arxiv
  - URL: <http://arxiv.org/abs/1906.10678v5>
  - Abstract: Described here is a simple, reliable, and quite general method for rapid computation of robot arm inverse kinematic solutions and motion path plans in...
- **Obstacle Avoidance Path Planning for the Dual-Arm Robot Based on an Improved RRT Algorithm** — openalex
- **An obstacle avoidance path planning method for robot grasping based on point cloud environment modelling** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/0cd2947a37c9f78921ad4cf4bc8133e00166caa6>
- **An improved RRT-based path planning approach with dynamic cone angle guidance for robotic manipulator obstacle avoidance** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/b28e06691eb8edef41efb1596f756337f11101d4>
- **Motion Planning and Control of Redundant Manipulators for Dynamical Obstacle Avoidance** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/404117eea1d11c49db2237d088b375e5a4b03fd4>
  - Abstract: This paper presents a framework for the motion planning and control of redundant manipulators with the added task of collision avoidance. The algorith...
- **A Method on Dynamic Path Planning for Robotic Manipulator Autonomous Obstacle Avoidance Based on an Improved RRT Algorithm** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/addea3e6793c2e636b93ab08819ab0527d444eb1>
  - Abstract: In a future intelligent factory, a robotic manipulator must work efficiently and safely in a Human–Robot collaborative and dynamic unstructured enviro...
- **Research on Six-Degree-of-Freedom Refueling Robotic Arm Positioning and Docking Based on RGB-D Visual Guidance** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/561d4d3b5b62e3b7218aef9dd93c19cf92b7a6a0>
  - Abstract: The main contribution of this paper is the proposal of a six-degree-of-freedom (6-DoF) refueling robotic arm positioning and docking technology guided...
- **MMD-RRT: a path planning strategy for robotic arm with improved RRT algorithm in unstructured environments** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/b5185f2225811b0d64587969c900d834935cc071>
  - Abstract: Robotic arm path planning in complex, unstructured environments often suffers from challenges such as excessive sampling randomness, low search effici...
- **Spatial path planning for hydraulic turbine flow channels using an improved RRT algorithm** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/40244e86e87afb3adbbde61d44bfb137a5639ccc>
  - Abstract: The purpose of this study is to propose a path planning method based on an improved Rapidly-exploring Random Tree (RRT) algorithm to address the path ...
- ... 等共 11 篇

### Weak Papers (60 篇)

- **Local Path Planning with Dynamic Obstacle Avoidance in Unstructured Environments** — arxiv
- **Approximate Computing for Robotic path planning -- Experimentation, Case Study and Practical Implications** — arxiv
- **Robust UAV Path Planning with Obstacle Avoidance for Emergency Rescue** — arxiv
- **A Comprehensive Review of Coverage Path Planning in Robotics Using Classical and Heuristic Algorithms** — openalex
- **Robotic arm obstacle avoidance path planning based on improved PPO algorithm** — crossref
- ... 等共 60 篇

### Repos (0 个)

（无）

### Datasets (0 个)

（无）

### Baselines (11 个)

- Vision-based obstacle avoidance robotic arm path planning based on a multi-level PPO framework
- Fast Robot Arm Inverse Kinematics and Path Planning Under Complex Static and Dynamic Obstacle Constraints
- Obstacle Avoidance Path Planning for the Dual-Arm Robot Based on an Improved RRT Algorithm
- An obstacle avoidance path planning method for robot grasping based on point cloud environment modelling
- An improved RRT-based path planning approach with dynamic cone angle guidance for robotic manipulator obstacle avoidance
- Motion Planning and Control of Redundant Manipulators for Dynamical Obstacle Avoidance
- A Method on Dynamic Path Planning for Robotic Manipulator Autonomous Obstacle Avoidance Based on an Improved RRT Algorithm
- Research on Six-Degree-of-Freedom Refueling Robotic Arm Positioning and Docking Based on RGB-D Visual Guidance
- MMD-RRT: a path planning strategy for robotic arm with improved RRT algorithm in unstructured environments
- Spatial path planning for hydraulic turbine flow channels using an improved RRT algorithm

### Innovation Points (3 个)

- 结合多级PPO框架与改进RRT算法，实现机械臂在复杂静态和动态障碍物环境下的高效目标检测与避障路径规划
- 融合MSC快速逆运动学算法与点云环境建模，提升机械臂在复杂障碍物场景下的路径规划实时性和准确性
- 将改进RRT算法与双机械臂协同避障策略结合，实现双机械臂在共享工作空间中的无碰撞路径规划

### Stitching Plan (缝合方案)

- **Baseline**: 多级PPO框架
- **Module B**: 改进RRT算法（动态锥角引导）
- **Module C**: 点云环境建模

### 标答 (Ground Truth)

- **领域**: 机器人/机械臂
- **可行性**: `not_recommended`
- **标准 Baselines**: ResNet
- **标准 Datasets**: Cornell Grasping, Jacquard
- **标准 Repos**: （无）

## R34-066 — 面向自动驾驶中多模态融合感知算法的攻击和防御

- **可行性裁决**: `risky` (分数: 45)
- **可行性理由**: 有3篇baseline论文，但仅1篇有repo，且无数据集和parallel论文，实验复现和验证风险高。
- **复核裁决**: `MINOR_REVISION`
- **领域**: robotics\_control
- **方法关键词**: \['multi-modal fusion', 'adversarial attack', 'adversarial defense']
- **对象关键词**: \['perception algorithm']

### Verified Papers (3 篇)

- **Generating Adversarial Point Clouds on Multi-modal Fusion Based 3D Object Detection Model** — None
- **Adversarial Attacks on Camera-LiDAR Models for 3D Car Detection** — openalex
- **Adversarial Attack on Radar-based Environment Perception Systems** — arxiv
  - URL: <http://arxiv.org/abs/2211.01112v2>
  - Abstract: Due to their robustness to degraded capturing conditions, radars are widely used for environment perception, which is a critical task in applications ...

### Weak Papers (17 篇)

- **Temporal Adversarial Attacks on Time Series and Reinforcement Learning Systems: A Systematic Survey, Taxonomy, and Benchmarking Roadmap** — openalex
- **RobustE2E: Exploring the Robustness of End-to-End Autonomous Driving** — openalex
- **Multi-Task Learning With Self-Defined Tasks for Adversarial Robustness of Deep Networks** — openalex
- **A Multi-objective Memetic Algorithm for Auto Adversarial Attack Optimization Design** — arxiv
- **Uncertainty-Encoded Multi-Modal Fusion for Robust Object Detection in Autonomous Driving** — arxiv
- ... 等共 17 篇

### Repos (0 个)

（无）

### Datasets (0 个)

（无）

### Baselines (3 个)

- Generating Adversarial Point Clouds on Multi-modal Fusion Based 3D Object Detection Model
- Adversarial Attacks on Camera-LiDAR Models for 3D Car Detection
- Adversarial Attack on Radar-based Environment Perception Systems

### Innovation Points (2 个)

- 结合多模态融合点云对抗攻击与雷达感知对抗攻击，设计针对相机-激光雷达-雷达融合感知系统的统一对抗攻击方法
- 将相机-激光雷达融合对抗攻击扩展到包含雷达的融合系统，设计跨模态协同攻击策略

### Stitching Plan (缝合方案)

- **Baseline**: 多模态融合3D目标检测模型（如AVOD、F-PointNet等）
- **Module B**: 雷达对抗攻击方法（来自Adversarial Attack on Radar-based Environment Perception Systems）
- **Module C**: 相机-激光雷达融合对抗攻击方法（来自Adversarial Attacks on Camera-LiDAR Models for 3D Car Detection）

### 标答 (Ground Truth)

- **领域**: 自动驾驶/多模态
- **可行性**: `risky`
- **标准 Baselines**: ResNet
- **标准 Datasets**: KITTI, nuScenes
- **标准 Repos**: （无）

## R34-092 — 海上风机叶片缺陷检测及分类

- **可行性裁决**: `feasible` (分数: 75)
- **可行性理由**: 5篇baseline均有代码仓库，覆盖冰检测、表面损伤、异常检测等，但无专用数据集，需自行采集或仿真。
- **复核裁决**: `ACCEPT`
- **领域**: energy\_power
- **方法关键词**: \['defect detection', 'classification']
- **对象关键词**: \['wind turbine blade']

### Verified Papers (5 篇)

- **WaveletAE: A Wavelet-enhanced Autoencoder for Wind Turbine Blade Icing Detection** — arxiv
  - URL: <http://arxiv.org/abs/1902.05625v2>
  - Abstract: Wind power, as an alternative to burning fossil fuels, is abundant and inexhaustible. To fully utilize wind power, wind farms are usually located in a...
- **Prototype-based Heterogeneous Federated Learning for Blade Icing Detection in Wind Turbines with Class Imbalanced Data** — arxiv
  - URL: <http://arxiv.org/abs/2503.08325v1>
  - Abstract: Wind farms, typically in high-latitude regions, face a high risk of blade icing. Traditional centralized training methods raise serious privacy concer...
- **A Novel Approach for Defect Detection of Wind Turbine Blade Using Virtual Reality and Deep Learning** — arxiv
  - URL: <http://arxiv.org/abs/2401.00237v1>
  - Abstract: Wind turbines are subjected to continuous rotational stresses and unusual external forces such as storms, lightning, strikes by flying objects, etc., ...
- **Wind Turbine Blade Surface Damage Detection based on Aerial Imagery and VGG16-RCNN Framework** — arxiv
  - URL: <http://arxiv.org/abs/2108.08636v2>
  - Abstract: In this manuscript, an image analytics based deep learning framework for wind turbine blade surface damage detection is proposed. Turbine blade(s) whi...
- **Semi-Supervised Surface Anomaly Detection of Composite Wind Turbine Blades From Drone Imagery** — arxiv
  - URL: <http://arxiv.org/abs/2112.00556v1>
  - Abstract: Within commercial wind energy generation, the monitoring and predictive maintenance of wind turbine blades in-situ is a crucial task, for which remote...

### Weak Papers (2 篇)

- **Fault Detection in New Wind Turbines with Limited Data by Generative Transfer Learning** — arxiv
- **Distributed Intelligent System Architecture for UAV-Assisted Monitoring of Wind Energy Infrastructure** — arxiv

### Repos (12 个)

- **?**
  - URL: <https://github.com/memari-majid/Wind-Turbine-Blade-Defect-Detection-with-YOLO-Models>
- **?**
  - URL: <https://github.com/yuuStella/Wind-Turbine-Blade-Defect-Detection-with-a-Semi-supervised-Deep-Learning-Framework>
- **?**
  - URL: <https://github.com/share2code99/wind_turbine_blade_defect_detection>
- **?**
  - URL: <https://github.com/share2code99/wind_turbine_blade_defect_detection_yolo11>
- **?**
  - URL: <https://github.com/QQ767172261/Deep-Learning-How-the-YOLOV8-Model-Trains-Wind-Turbine-Blade-Defect-Detection-Datasets-Establish-Dee>
- **?**
  - URL: <https://github.com/mxy021120-ops/fans-defect-Dataset>
- **?**
  - URL: <https://github.com/mpmpj1/Intelligent-Recognition-System-for-UAV-based-Wind-Turbine-Blade-Inspection>
- **?**
  - URL: <https://github.com/QQ767172261/Deep-Learning-YOLOV11-Model-How-to-Train-Class-9-9900-UAV-Wind-Turbine-Blade-Defect-Detection-Datase>
- **?**
  - URL: <https://github.com/fqiu-yu/BladeYOLO>
- **?**
  - URL: <https://github.com/Megatroncode/wind-turbine-blade-fault-detection>

### Datasets (0 个)

（无）

### Baselines (5 个)

- WaveletAE: A Wavelet-enhanced Autoencoder for Wind Turbine Blade Icing Detection
- Prototype-based Heterogeneous Federated Learning for Blade Icing Detection in Wind Turbines with Class Imbalanced Data
- A Novel Approach for Defect Detection of Wind Turbine Blade Using Virtual Reality and Deep Learning
- Wind Turbine Blade Surface Damage Detection based on Aerial Imagery and VGG16-RCNN Framework
- Semi-Supervised Surface Anomaly Detection of Composite Wind Turbine Blades From Drone Imagery

### Innovation Points (3 个)

- 结合WaveletAE的时频特征提取与VGG16-RCNN的定位能力，实现叶片缺陷的精确检测与分类
- 将原型联邦学习中的类不平衡处理机制与半监督异常检测结合，提升叶片缺陷检测的泛化能力
- 利用虚拟现实数据增强与WaveletAE的时频特征，提升叶片缺陷检测在复杂背景下的鲁棒性

### Stitching Plan (缝合方案)

- **Baseline**: WaveletAE
- **Module B**: VGG16-RCNN目标检测框架
- **Module C**: 虚拟现实数据增强模块

### 标答 (Ground Truth)

- **领域**: 能源装备/风机
- **可行性**: `not_recommended`
- **标准 Baselines**: ResNet
- **标准 Datasets**: （无）
- **标准 Repos**: （无）

## R34-S01 — 基于多视差一致性的伪深度图误差过滤方法

- **可行性裁决**: `feasible` (分数: 75)
- **可行性理由**: 5篇baseline均有repo，覆盖多视一致性、边缘自适应滤波等核心方法，但无数据集和parallel论文，需自行构建或借用公开数据。
- **复核裁决**: `MINOR_REVISION`
- **领域**: unknown
- **方法关键词**: \['伪深度图误差过滤方法']
- **对象关键词**: \[]

### Verified Papers (5 篇)

- **Multi-View Depth Map Estimation With Cross-View Consistency** — crossref
  - URL: <https://doi.org/10.5244/c.28.76>
- **Edge and motion-adaptive median filtering for multi-view depth map enhancement** — crossref
  - URL: <https://doi.org/10.1109/pcs.2009.5167415>
- **Depth map inter-view consistency refinement for multiview video** — crossref
  - URL: <https://doi.org/10.1109/pcs.2012.6213305>
- **Discontinuity-adaptive Depth Map Filtering for 3D View Generation** — crossref
  - URL: <https://doi.org/10.4108/icst.immerscom2009.6284>
- **Inter-View Depth Consistency Testing in Depth Difference Subspace** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/5c1a3cbe54474d6ea55d47523ed68f47411e8fca>
  - Abstract: Multiview depth imagery will play a critical role in free-viewpoint television. This technology requires high quality virtual view synthesis to enable...

### Weak Papers (36 篇)

- **Self-supervised Multi-view Stereo via Effective Co-Segmentation and Data-Augmentation** — openalex
- **MV-Map: Offboard HD Map Generation with Multi-view Consistency** — crossref
- **Multi-view stereo using cross-view depth map completion and row-column depth refinement** — crossref
- **Joint view filtering for multiview depth map sequences** — crossref
- **AI-Driven Enhancement of Depth Map Consistency** — crossref
- ... 等共 36 篇

### Repos (0 个)

（无）

### Datasets (0 个)

（无）

### Baselines (5 个)

- Multi-View Depth Map Estimation With Cross-View Consistency
- Edge and motion-adaptive median filtering for multi-view depth map enhancement
- Depth map inter-view consistency refinement for multiview video
- Discontinuity-adaptive Depth Map Filtering for 3D View Generation
- Inter-View Depth Consistency Testing in Depth Difference Subspace

### Innovation Points (3 个)

- 结合多视一致性校验与边缘自适应中值滤波，构建两阶段伪深度图误差过滤方法：第一阶段利用跨视一致性检测并标记不一致像素，第二阶段对标记像素执行边缘自适应中值滤波以保留边缘细节。
- 融合视间一致性测试与深度差异子空间分析，先通过深度差异子空间检测异常深度值，再结合视间一致性测试进行二次验证，提高伪深度点检测准确率。
- 结合不连续性自适应深度图滤波与视间一致性细化，先利用不连续性自适应滤波平滑深度图内部区域，再通过视间一致性细化修正边界处的不一致伪影。

### Stitching Plan (缝合方案)

- **Baseline**: 多视一致性深度图估计模型
- **Module B**: 边缘自适应中值滤波模块（来自Edge and motion-adaptive median filtering for multi-view depth map enhancement）
- **Module C**: 视间一致性细化模块（来自Depth map inter-view consistency refinement for multiview video）

## R34-S02 — 无人机ZED立体匹配网络训练与评测研究

- **可行性裁决**: `feasible` (分数: 85)
- **可行性理由**: 4篇baseline论文均有repo，其中UAVStereo直接匹配无人机场景；2个数据集和3个代码仓库提供充分资源；10篇parallel论文覆盖目标检测、三维重建等扩展方向。
- **复核裁决**: `ACCEPT`
- **领域**: vision\_3d
- **方法关键词**: \['stereo matching', 'neural network training']
- **对象关键词**: \['UAV', 'ZED stereo camera']

### Verified Papers (14 篇)

- **UAVStereo: A Multiple Resolution Dataset for Stereo Matching in UAV Scenarios** — arxiv
  - URL: <http://arxiv.org/abs/2302.10082v1>
  - Abstract: Stereo matching is a fundamental task for 3D scene reconstruction. Recently, deep learning based methods have proven effective on some benchmark datas...
- **A Camera-Based Target Detection and Positioning UAV System for Search and Rescue (SAR) Purposes** — openalex
- **Development and Evaluation of a UAV-Photogrammetry System for Precise 3D Environmental Modeling** — openalex
- **MonSter++: Unified Stereo Matching, Multi-view Stereo, and Real-time Stereo with Monodepth Priors** — arxiv
  - URL: <http://arxiv.org/abs/2501.08643v2>
  - Abstract: We introduce MonSter++, a geometric foundation model for multi-view depth estimation, unifying rectified stereo matching and unrectified multi-view st...
- **Diving into the Fusion of Monocular Priors for Generalized Stereo Matching** — arxiv
  - URL: <http://arxiv.org/abs/2505.14414v2>
  - Abstract: The matching formulation makes it naturally hard for the stereo matching to handle ill-posed regions like occlusions and non-Lambertian surfaces. Fusi...
- **DENSE MULTIPLE STEREO MATCHING OF HIGHLY OVERLAPPING UAV IMAGERY** — openalex
- **Real-Time Dense Stereo Embedded in a UAV for Road Inspection** — openalex
- **Multi-View Stereo Matching Based on Self-Adaptive Patch and Image Grouping for Multiple Unmanned Aerial Vehicle Imagery** — openalex
- **A Convolutional Attention Residual Network for Stereo Matching** — openalex
- **DEFOM-Stereo: Depth Foundation Model Based Stereo Matching** — arxiv
  - URL: <http://arxiv.org/abs/2501.09466v3>
  - Abstract: Stereo matching is a key technique for metric depth estimation in computer vision and robotics. Real-world challenges like occlusion and non-texture h...
- ... 等共 14 篇

### Weak Papers (55 篇)

- **A comparative experimental study of image feature detectors and descriptors** — semantic\_scholar
- **A New Calibration Method Using Low Cost MEM IMUs to Verify the Performance of UAV-Borne MMS Payloads** — semantic\_scholar
- **A Robust Photogrammetric Processing Method of Low-Altitude UAV Images** — semantic\_scholar
- **Automated End-to-End Workflow for Precise and Geo-accurate Reconstructions using Fiducial Markers** — semantic\_scholar
- **MATCH-AT: Recent Developments and Performance** — semantic\_scholar
- ... 等共 55 篇

### Repos (3 个)

- **?**
  - URL: <https://github.com/yudhisteer/Pseudo-LiDARs-with-Stereo-Vision>
- **?**
  - URL: <https://github.com/D3010/Pseudo-LiDARs-with-Stereo-Vision>
- **?**
  - URL: <https://github.com/Balla454/TurtlebotZed_ObjectMatching>

### Datasets (2 个)

- **KITTI** (source: paper\_title\_heuristic)
- **ImageNet** (source: paper\_title\_heuristic)

### Baselines (4 个)

- UAVStereo: A Multiple Resolution Dataset for Stereo Matching in UAV Scenarios
- Efficient Deep Learning for Stereo Matching
- These Maps Are Made by Propagation: Adapting Deep Stereo Networks to Road Scenarios With Decisive Disparity Diffusion
- Stereo Matching with Weighted Feature Constraints for Aerial Images

### Innovation Points (3 个)

- 在UAVStereo baseline的立体匹配网络中，引入MonSter++的几何先验模块，以提升在无人机场景中遮挡和非朗伯表面的匹配鲁棒性。
- 在UAVStereo baseline中融合Diving into the Fusion of Monocular Priors提出的单目先验融合模块，以增强网络对弱纹理区域的泛化能力。
- 在UAVStereo baseline中集成Dense Multiple Stereo Matching of Highly Overlapping UAV Imagery提出的密集多视角匹配策略，以利用高重叠无人机图像序列提升深度估计一致性。

### Stitching Plan (缝合方案)

- **Baseline**: UAVStereo多分辨率立体匹配网络
- **Module B**: MonSter++的几何先验模块
- **Module C**: Diving into the Fusion of Monocular Priors的单目先验融合模块

## R34-S03 — 深度先验引导的无监督立体匹配与视差置信度估计

- **可行性裁决**: `feasible` (分数: 75)
- **可行性理由**: 5篇baseline论文聚焦无监督立体匹配，含损失函数与遮挡处理，11个代码仓库提供复现基础，1个数据集支持实验，但缺乏parallel论文且无repo的论文占多数，整体可行但需加强创新。
- **复核裁决**: `ACCEPT`
- **领域**: unknown
- **方法关键词**: \['无监督立体匹配']
- **对象关键词**: \[]

### Verified Papers (16 篇)

- **Unsupervised Learning of Stereo Matching** — openalex
- **Unsupervised Stereo Matching Using Confidential Correspondence Consistency** — openalex
- **Co-Teaching: an Ark to Unsupervised Stereo Matching** — openalex
- **Multi-directional broad learning system for the unsupervised stereo matching method** — openalex
- **Unsupervised Stereo Matching with Occlusion-Aware Loss** — openalex
- **Unsupervised stereo matching using correspondence consistency** — openalex
- **Occlusion Aware Stereo Matching via Cooperative Unsupervised Learning** — openalex
- **Integrating Disparity Confidence Estimation Into Relative Depth Prior-Guided Unsupervised Stereo Matching** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/b2153b21e9534e81f99f94ea10199d458baee7bf>
  - Abstract: Unsupervised stereo matching has garnered significant attention for its independence from costly disparity annotations. Typical unsupervised methods r...
- **MMGA-KAN Net: KAN-based multi-resolution and multi-scale graph attention network for global and local unsupervised stereo matching** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/6c0d0a7f22ec8ee1b1db540bbd63c0a370bfa282>
- **SRNet: Self-supervised structure regularization for stereo matching** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/827f95b512c5b540191df092f263b738c78138ed>
- ... 等共 16 篇

### Weak Papers (41 篇)

- **An unsupervised stereo matching cost based on sparse representation** — openalex
- **Adaptive Cost Volume Representation for Unsupervised High-Resolution Stereo Matching** — openalex
- **Parallax Attention for Unsupervised Stereo Correspondence Learning** — openalex
- **Unsupervised Cross-Spectral Stereo Matching by Learning to Synthesize** — openalex
- **Unsupervised Monocular Depth Estimation with Left-Right Consistency** — semantic\_scholar
- ... 等共 41 篇

### Repos (11 个)

- **?**
  - URL: <https://github.com/USTCPCS/CVPR2018_attention>
- **?**
  - URL: <https://github.com/Qjizhi/GenStereo>
- **?**
  - URL: <https://github.com/rish-av/cross_spectral_stereo>
- **?**
  - URL: <https://github.com/Magicboomliu/StereoSDF>
- **?**
  - URL: <https://github.com/Magicboomliu/HiddenStereoMatching>
- **?**
  - URL: <https://github.com/itcelaya92/Unsupervised-learning-to-match-points-in-stereoscopic-images>
- **?**
  - URL: <https://github.com/8FDC/TAFM-Stereo>
- **?**
  - URL: <https://github.com/zhao1i/HS-SMR>
- **?**
  - URL: <https://github.com/CwLiuzzZ/Un-ViTAStereo>
- **?**
  - URL: <https://github.com/Elenairene/CBEM>

### Datasets (1 个)

- **KITTI** (source: paper\_title\_heuristic)

### Baselines (16 个)

- Unsupervised Learning of Stereo Matching
- Unsupervised Stereo Matching Using Confidential Correspondence Consistency
- Co-Teaching: an Ark to Unsupervised Stereo Matching
- Multi-directional broad learning system for the unsupervised stereo matching method
- Unsupervised Stereo Matching with Occlusion-Aware Loss
- Unsupervised stereo matching using correspondence consistency
- Occlusion Aware Stereo Matching via Cooperative Unsupervised Learning
- Integrating Disparity Confidence Estimation Into Relative Depth Prior-Guided Unsupervised Stereo Matching
- MMGA-KAN Net: KAN-based multi-resolution and multi-scale graph attention network for global and local unsupervised stereo matching
- SRNet: Self-supervised structure regularization for stereo matching

### Innovation Points (3 个)

- 在无监督立体匹配中引入深度先验作为几何约束，结合视差置信度估计来过滤不可靠匹配，提升遮挡区域和弱纹理区域的匹配精度。
- 利用协同教学（Co-Teaching）框架，结合深度先验和视差置信度，在无监督训练中动态筛选可靠样本，避免噪声标签的累积。
- 在无监督立体匹配中，使用多方向宽度学习系统（BLS）融合深度先验特征，提升视差估计的鲁棒性，并输出置信度图。

### Stitching Plan (缝合方案)

- **Baseline**: Unsupervised Stereo Matching with Occlusion-Aware Loss
- **Module B**: 深度先验引导的视差初始化模块（来自MiDaS或DenseDepth等单目深度估计网络）
- **Module C**: 视差置信度估计与过滤模块（基于左右一致性误差的MLP或置信度网络）

## R34-S03R — 深度先验引导的无监督立体匹配与视差置信度估计

- **可行性裁决**: `feasible` (分数: 75)
- **可行性理由**: 5篇baseline论文（含无监督立体匹配、遮挡感知损失等）和11个代码仓库提供坚实基础；6篇parallel论文（如SRNet、RoSe）拓展思路；数据集1个，整体支撑充分。
- **复核裁决**: `ACCEPT`
- **领域**: unknown
- **方法关键词**: \['无监督立体匹配']
- **对象关键词**: \[]

### Verified Papers (18 篇)

- **Unsupervised Learning of Stereo Matching** — openalex
- **Unsupervised Stereo Matching Using Confidential Correspondence Consistency** — openalex
- **Co-Teaching: an Ark to Unsupervised Stereo Matching** — openalex
- **Multi-directional broad learning system for the unsupervised stereo matching method** — openalex
- **Unsupervised Stereo Matching with Occlusion-Aware Loss** — openalex
- **Unsupervised stereo matching using correspondence consistency** — openalex
- **Occlusion Aware Stereo Matching via Cooperative Unsupervised Learning** — openalex
- **MMGA-KAN Net: KAN-based multi-resolution and multi-scale graph attention network for global and local unsupervised stereo matching** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/6c0d0a7f22ec8ee1b1db540bbd63c0a370bfa282>
- **SRNet: Self-supervised structure regularization for stereo matching** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/827f95b512c5b540191df092f263b738c78138ed>
- **RoSe: Robust Self-Supervised Stereo Matching Under Adverse Weather Conditions** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/f6458ac7745c2402132ecc99bef2e08f1f080892>
  - Abstract: Recent self-supervised stereo matching methods have made significant progress, but their performance significantly degrades under adverse weather cond...
- ... 等共 18 篇

### Weak Papers (43 篇)

- **An unsupervised stereo matching cost based on sparse representation** — openalex
- **Adaptive Cost Volume Representation for Unsupervised High-Resolution Stereo Matching** — openalex
- **Parallax Attention for Unsupervised Stereo Correspondence Learning** — openalex
- **Unsupervised Cross-Spectral Stereo Matching by Learning to Synthesize** — openalex
- **Weakly Supervised Learning of Deep Metrics for Stereo Reconstruction** — semantic\_scholar
- ... 等共 43 篇

### Repos (11 个)

- **?**
  - URL: <https://github.com/USTCPCS/CVPR2018_attention>
- **?**
  - URL: <https://github.com/Qjizhi/GenStereo>
- **?**
  - URL: <https://github.com/rish-av/cross_spectral_stereo>
- **?**
  - URL: <https://github.com/Magicboomliu/StereoSDF>
- **?**
  - URL: <https://github.com/Magicboomliu/HiddenStereoMatching>
- **?**
  - URL: <https://github.com/itcelaya92/Unsupervised-learning-to-match-points-in-stereoscopic-images>
- **?**
  - URL: <https://github.com/8FDC/TAFM-Stereo>
- **?**
  - URL: <https://github.com/zhao1i/HS-SMR>
- **?**
  - URL: <https://github.com/CwLiuzzZ/Un-ViTAStereo>
- **?**
  - URL: <https://github.com/Elenairene/CBEM>

### Datasets (1 个)

- **KITTI** (source: paper\_title\_heuristic)

### Baselines (12 个)

- Unsupervised Learning of Stereo Matching
- Unsupervised Stereo Matching Using Confidential Correspondence Consistency
- Co-Teaching: an Ark to Unsupervised Stereo Matching
- Multi-directional broad learning system for the unsupervised stereo matching method
- Unsupervised Stereo Matching with Occlusion-Aware Loss
- Unsupervised stereo matching using correspondence consistency
- Occlusion Aware Stereo Matching via Cooperative Unsupervised Learning
- MMGA-KAN Net: KAN-based multi-resolution and multi-scale graph attention network for global and local unsupervised stereo matching
- AGSK-Net: Adaptive Geometry-Aware Stereo-KANformer Network for Global and Local Unsupervised Stereo Matching
- Transformer and Trainable Bilateral Filter for Unsupervised Stereo Matching

### Innovation Points (3 个)

- 在无监督立体匹配基线中引入深度先验引导的视差置信度估计模块，通过联合学习视差与置信度，提升遮挡区域和弱纹理区域的匹配鲁棒性。
- 在无监督立体匹配中引入结构正则化模块，利用图像边缘和梯度信息约束视差图平滑性，减少噪声和伪影。
- 在无监督立体匹配中集成多方向特征提取模块，通过宽学习系统增强特征表达能力，提升复杂场景下的匹配精度。

### Stitching Plan (缝合方案)

- **Baseline**: Unsupervised Learning of Stereo Matching (PSMNet-based)
- **Module B**: 深度先验引导的置信度估计网络 (来自UFD-PRiME)
- **Module C**: 边缘感知平滑损失 (来自SRNet)

## R34-S04 — 基于三维点云重建的混凝土结构裂缝定位与追踪

- **可行性裁决**: `feasible` (分数: 75)
- **可行性理由**: 有6篇baseline论文且均含repo，覆盖裂缝检测与3D重建，但无数据集和代码仓库，需自行采集数据。
- **复核裁决**: `ACCEPT`
- **领域**: civil\_infra
- **方法关键词**: \['3D point cloud reconstruction']
- **对象关键词**: \['concrete structure', 'crack']

### Verified Papers (15 篇)

- **Concrete Crack Assessment Using Digital Image Processing and 3D Scene Reconstruction** — core
  - URL: <https://core.ac.uk/download/79707184.pdf>
  - Abstract: Traditional crack assessment methods for concrete structures are time consuming and produce subjective results. The development of a means for automat...
- **Noncontact sensing systems and autonomous decision-making for early-age concrete** — core
  - URL: <https://core.ac.uk/download/328785310.pdf>
  - Abstract: Early-age cracking and spalling in concrete pavements reduces slab capacity, joint load transfer, ride quality, and its long-term performance. These p...
- **A Systematic Approach for Cross-source Point Cloud Registration by Preserving Macro and Micro Structures** — arxiv
  - URL: <http://arxiv.org/abs/1608.05143v2>
  - Abstract: We propose a systematic approach for registering cross-source point clouds. The compelling need for cross-source point cloud registration is motivated...
- **Depth-First Search Based 3D Point Cloud Coordinate Reconstruction Algorithm** — crossref
  - URL: <https://doi.org/10.20944/preprints202502.2231.v1>
  - Abstract: <jats:p>This paper presents a novel approach for three-dimensional point cloud coordinate reconstruction using a depth-first search algorithm combined...
- **ShapeAdv: Generating Shape-Aware Adversarial 3D Point Clouds** — arxiv
  - URL: <http://arxiv.org/abs/2005.11626v1>
  - Abstract: We introduce ShapeAdv, a novel framework to study shape-aware adversarial perturbations that reflect the underlying shape variations (e.g., geometric ...
- **$PC^2$: Projection-Conditioned Point Cloud Diffusion for Single-Image 3D Reconstruction** — arxiv
  - URL: <http://arxiv.org/abs/2302.10668v2>
  - Abstract: Reconstructing the 3D shape of an object from a single RGB image is a long-standing and highly challenging problem in computer vision. In this paper, ...
- **Masked Clustering Prediction for Unsupervised Point Cloud Pre-training** — arxiv
  - URL: <http://arxiv.org/abs/2508.08910v1>
  - Abstract: Vision transformers (ViTs) have recently been widely applied to 3D point cloud understanding, with masked autoencoding as the predominant pre-training...
- **3D Surface Reconstruction from Point-and-Line Cloud** — crossref
  - URL: <https://doi.org/10.1109/3dv.2015.37>
- **Bridge Structural Condition Assessment using 3D Imaging** — core
  - URL: <https://core.ac.uk/download/595636005.pdf>
  - Abstract: Objective, accurate, and fast assessment of bridge structural condition is critical to timely assess safety risks. Current practices for bridge condit...
- **Quantification of Structural Defects Using Pixel Level Spatial Information from Photogrammetry** — core
  - URL: <https://core.ac.uk/download/634418773.pdf>
  - Abstract: Aging infrastructure has drawn increased attention globally, as its collapse would be destructive economically and socially. Precise quantification of...
- ... 等共 15 篇

### Weak Papers (5 篇)

- **Structural health monitoring based on three-dimensional point cloud technology: A systematic review** — semantic\_scholar
- **Automated UAV image-to-BIM registration for planar and curved building façades using structure-from-motion and 3D surface unwrapping** — semantic\_scholar
- **Artificial intelligence-driven safety assessment of scaffolding using LiDAR sensing** — semantic\_scholar
- **A crack detection and quantification framework for high‐resolution images using Mamba and unmanned devices** — semantic\_scholar
- **Panoramic Vision–Driven Deep Learning Framework for Structural Inspection and Condition Assessment** — semantic\_scholar

### Repos (0 个)

（无）

### Datasets (0 个)

（无）

### Baselines (6 个)

- Concrete Crack Assessment Using Digital Image Processing and 3D Scene Reconstruction
- Concrete wind turbine tower crack assessment based on drone imaging using computer vision and artificial intelligence
- Fatigue crack detection and localization in steel box girder using point cloud and image fusion machine vision
- Deep Learning-Based Crack Detection and 3D Reconstruction for Cost-Effective Structural Health Monitoring
- Fast vision-based 3D reconstruction and damage detection of building structures based on visual geometry grounded transformer
- Lightweight panoramic reconstruction and precise defect localization of bridge undersides based on multi-view pose registration

### Innovation Points (3 个)

- 融合多视角图像与三维点云，利用深度优先搜索算法优化裂缝定位与追踪的坐标重建精度
- 结合无人机成像与跨源点云配准方法，提升混凝土结构裂缝追踪的鲁棒性
- 利用投影条件点云扩散模型从单张图像重建三维裂缝点云，实现快速裂缝定位

### Stitching Plan (缝合方案)

- **Baseline**: Concrete Crack Assessment Using Digital Image Processing and 3D Scene Reconstruction
- **Module B**: Depth-First Search Based 3D Point Cloud Coordinate Reconstruction Algorithm
- **Module C**: A Systematic Approach for Cross-source Point Cloud Registration by Preserving Macro and Micro Structures

## R35-033 — 基于YOLOV5的肺结节检测算法研究

- **可行性裁决**: `feasible` (分数: 78)
- **可行性理由**: 有5篇baseline论文（含4个有repo），1个公开数据集（如LIDC-IDRI），代码仓库可用。但涉及医学影像数据合规（需伦理审批），且需注意数据集获取与隐私保护。
- **复核裁决**: `ACCEPT`
- **领域**: medical\_ai
- **方法关键词**: \['YOLOV5']
- **对象关键词**: \['lung nodule']

### Verified Papers (9 篇)

- **Lung Nodule Detection in Medical Images Based on Improved YOLOv5s** — openalex
- **An improved YOLOv5 network for lung nodule detection** — crossref
  - URL: <https://doi.org/10.1109/eiecs53707.2021.9588065>
- **Based on the Improved YOLOv5 Lung Nodule Detection Method** — crossref
  - URL: <https://doi.org/10.12677/sea.2023.122026>
- **Lung Nodule Detection Algorithm Based on Improved YOLOv5 Network Modeling** — crossref
  - URL: <https://doi.org/10.1109/iceict61637.2024.10671019>
- **A Model for Lung Nodule Detection using a Hybrid Approach by Combining YOLOv5 and ResNet101 Pretrained Artificial Intelligence Models** — crossref
  - URL: <https://doi.org/10.5829/ije.2026.39.09c.15>
- **Nodules Detection in Lungs CT Images Using Improved YOLOV5 and Classification of Types of Nodules by CNN-SVM** — openalex
- **Identification of lung nodules CT scan using YOLOv5 based on convolution neural network** — arxiv
  - URL: <http://arxiv.org/abs/2301.02166v1>
  - Abstract: Purpose: The lung nodules localization in CT scan images is the most difficult task due to the complexity of the arbitrariness of shape, size, and tex...
- **LNA-Net: Enhancing detection and classification of benign and malignant pulmonary nodules in CT scans** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/f502997a7cc7c95aba6c9eac6c72ea9065b9b04b>
- **YOLOv5-Z:A Target Detection Algorithm Suitable for New Theories of Medical Image Recognition** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/403e18a68803baac6e40718f95adcc5840a8e443>
  - Abstract: The enhanced YOLO algorithm YOLOv5-Z is designed for precise target detection. This paper primarily focuses on optimizing the YOLOv5 target detection ...

### Weak Papers (43 篇)

- **YOLO-Based Deep Learning Model for Pressure Ulcer Detection and Classification** — openalex
- **Intelligent Solutions in Chest Abnormality Detection Based on YOLOv5 and ResNet50** — openalex
- **Deep learning in pulmonary nodule detection and segmentation: a systematic review** — openalex
- **Automated Brain Tumor Segmentation and Classification in MRI Using YOLO-Based Deep Learning** — openalex
- **A Comprehensive Systematic Review of YOLO for Medical Object Detection (2018 to 2023)** — openalex
- ... 等共 43 篇

### Repos (1 个)

- **?**
  - URL: <https://github.com/anujmundu/lung-nodule-detection>

### Datasets (1 个)

- **COCO** (source: paper\_title\_heuristic)

### Baselines (7 个)

- Lung Nodule Detection in Medical Images Based on Improved YOLOv5s
- An improved YOLOv5 network for lung nodule detection
- Based on the Improved YOLOv5 Lung Nodule Detection Method
- Lung Nodule Detection Algorithm Based on Improved YOLOv5 Network Modeling
- A Model for Lung Nodule Detection using a Hybrid Approach by Combining YOLOv5 and ResNet101 Pretrained Artificial Intelligence Models
- Nodules Detection in Lungs CT Images Using Improved YOLOV5 and Classification of Types of Nodules by CNN-SVM
- Identification of lung nodules CT scan using YOLOv5 based on convolution neural network

### Innovation Points (3 个)

- 在YOLOv5s骨干网络中引入坐标注意力机制（CA），增强对肺结节小目标的特征提取能力，同时结合改进的检测框生成策略（如YOLOv5-Z中的完全包围矩形框），提升结节定位精度。
- 结合ResNet101作为特征提取骨干，替换YOLOv5s的CSPDarknet，利用预训练权重提升肺结节分类性能，同时引入LNA-Net中的良性/恶性分类头，实现检测与分类联合优化。
- 在YOLOv5s的Neck部分引入改进的注意力机制（如CBAM或SE），并采用YOLOv5-Z的检测框优化策略，提升小肺结节的检测精度，同时降低假阳性。

### Stitching Plan (缝合方案)

- **Baseline**: YOLOv5s
- **Module B**: 坐标注意力模块（来自YOLOv5-Z论文中的注意力机制变体）
- **Module C**: 完全包围矩形框生成策略（来自YOLOv5-Z论文）

## R35-046 — 基于视觉的机械臂目标检测和避障路径规划研究与应用

- **可行性裁决**: `feasible` (分数: 75)
- **可行性理由**: 两篇baseline均有代码仓库，但无专用数据集和代码仓库，需自建数据集或仿真环境。硬件依赖高，需实物机械臂和相机，存在获取风险。
- **复核裁决**: `MINOR_REVISION`
- **领域**: unknown
- **方法关键词**: \['避障路径规划研究']
- **对象关键词**: \[]

### Verified Papers (15 篇)

- **Fast Robot Arm Inverse Kinematics and Path Planning Under Complex Static and Dynamic Obstacle Constraints** — arxiv
  - URL: <http://arxiv.org/abs/1906.10678v5>
  - Abstract: Described here is a simple, reliable, and quite general method for rapid computation of robot arm inverse kinematic solutions and motion path plans in...
- **Enhanced Visual Detection and Path Planning for Robotic Arms Using Yolov10n-SSE and Hybrid Algorithms** — core
  - URL: <https://core.ac.uk/download/670609533.pdf>
  - Abstract: Pineapple harvesting in natural orchard environments faces challenges such as high occlusion rates caused by foliage and the need for complex spatial ...
- **Deep learning based system to avoid static obstacles with a 6 DOF fixed robot** — core
  - URL: <https://core.ac.uk/download/690783113.pdf>
  - Abstract: Este documento presenta el diseño de un sistema de seguridad que evita colisiones entre un robot antropomórfico de seis grados de libertad y los opera...
- **Comparative analysis of obstacle avoidance path planning algorithms for robotic manipulators: RRT, APF, and CHOMP** — crossref
  - URL: <https://doi.org/10.36227/techrxiv.176703981.11480674/v1>
  - Abstract: <jats:p>Robotic manipulators operating in 3D environments containing obstacles should be able to generate and follow collision-free and dynamically fe...
- **Obstacle Avoidance of Robotic Arm in Path Planning Based on RRT Algorithm** — crossref
  - URL: <https://doi.org/10.1109/icetac65964.2025.11144270>
- **Obstacle Avoidance Planning Algorithm for Robotic Arm Motion Path Based on Fuzzy Variable Structure Compensation** — crossref
  - URL: <https://doi.org/10.1109/icmtim62047.2024.10629308>
- **Obstacle-Avoidance Path Planning for a Basket-Carrying Robotic Arm Based on an Improved APF-RRT Algorithm** — crossref
  - URL: <https://doi.org/10.21203/rs.3.rs-10165181/v1>
  - Abstract: <title>Abstract</title> <p>Purpose
    This study addresses the challenges of robotic arm path planning in unstructured material-handling...
- **Vision-based obstacle avoidance robotic arm path planning based on a multi-level PPO framework** — crossref
  - URL: <https://doi.org/10.1016/j.rineng.2025.107021>
- **Robotic arm obstacle avoidance path planning based on improved PPO algorithm** — crossref
  - URL: <https://doi.org/10.1117/12.3066339>
- *Obstacle avoidance path planning of 6-DOF robotic arm based on improved A* algorithm and artificial potential field method\* — crossref
  - URL: <https://doi.org/10.1017/s0263574723001546>
  - Abstract: <jats:title>Abstract\</jats:title><jats:p>Most studies on path planning of robotic arm focus on obstacle avoidance at the end position of robotic arm, ...
- ... 等共 15 篇

### Weak Papers (42 篇)

- **Intelligent Singularity Avoidance in UR10 Robotic Arm Path Planning Using Hybrid Fuzzy Logic and Reinforcement Learning** — arxiv
- **Approximate Computing for Robotic path planning -- Experimentation, Case Study and Practical Implications** — arxiv
- **Robust UAV Path Planning with Obstacle Avoidance for Emergency Rescue** — arxiv
- **Global Path-Planning for Constrained and Optimal Visual Servoing** — openalex
- **Visual servoing via navigation functions** — openalex
- ... 等共 42 篇

### Repos (0 个)

（无）

### Datasets (0 个)

（无）

### Baselines (2 个)

- Enhanced Visual Detection and Path Planning for Robotic Arms Using Yolov10n-SSE and Hybrid Algorithms
- Vision-based obstacle avoidance robotic arm path planning based on a multi-level PPO framework

### Innovation Points (4 个)

- 将Yolov10n-SSE视觉检测模块与基于MSC算法的快速逆运动学及路径规划模块缝合，实现复杂静态和动态障碍物环境下的高效目标检测与避障路径规划。
- 将Yolov10n-SSE视觉检测模块与基于深度学习的静态障碍物避让系统缝合，实现固定工作空间中针对静态障碍物的实时避障。
- 将baseline中的混合路径规划算法与RRT算法进行对比和融合，形成RRT-混合路径规划模块，提高在复杂障碍物环境下的路径搜索效率。
- 将baseline中的多级PPO框架与模糊变结构补偿模块缝合，增强路径规划在动态障碍物环境下的鲁棒性和适应性。

### Stitching Plan (缝合方案)

- **Baseline**: Yolov10n-SSE + Hybrid Algorithms
- **Module B**: Fast Robot Arm Inverse Kinematics and Path Planning Under Complex Static and Dynamic Obstacle Constraints
- **Module C**: Deep learning based system to avoid static obstacles with a 6 DOF fixed robot

## R36-003 — 基于点云多平面检测的三维重建关键技术研究

- **可行性裁决**: `risky` (分数: 45)
- **可行性理由**: 有2篇baseline论文且均有repo，但无数据集和代码仓库，且涉及点云多平面检测，硬件依赖（如LiDAR或深度相机）未明确，数据获取存在风险。
- **复核裁决**: `MINOR_REVISION`
- **领域**: vision\_3d
- **方法关键词**: \['point cloud', 'multi-plane detection', '3D reconstruction']
- **对象关键词**: \['point cloud', 'plane']

### Verified Papers (5 篇)

- **3D point cloud model reconstruction method by using multi–view 2D images and 3D point clouds** — crossref
  - URL: <https://doi.org/10.1299/jsmermd.2018.2a1-i17>
- **Improved Plane Detection in 3D Reconstruction from 2D Images** — crossref
  - URL: <https://doi.org/10.58445/rars.3138>
- **A Fast Knowledge-based Plane Reconstruction Method from Noisy 3D Point Cloud Data** — crossref
  - URL: <https://doi.org/10.2316/p.2011.722-025>
- **$PC^2$: Projection-Conditioned Point Cloud Diffusion for Single-Image 3D Reconstruction** — arxiv
  - URL: <http://arxiv.org/abs/2302.10668v2>
  - Abstract: Reconstructing the 3D shape of an object from a single RGB image is a long-standing and highly challenging problem in computer vision. In this paper, ...
- **Parametric Plane Detection from 3D Point Cloud via Probabilistic Clustering** — crossref
  - URL: <https://doi.org/10.2139/ssrn.6466333>
  - Abstract: <jats:p>A plane is the most fundamental isotropic geometric shape commonly found in human-made environments. Plane detection serves as a bridge betwee...

### Weak Papers (14 篇)

- **Linking Points With Labels in 3D: A Review of Point Cloud Semantic Segmentation** — arxiv
- **YOLO3D: End-to-end real-time 3D Oriented Object Bounding Box Detection from LiDAR Point Cloud** — arxiv
- **MAESTRO: A Full Point Cloud Approach for 3D Anomaly Detection Based on Reconstruction** — crossref
- **Joint Denoising and 3D Point Cloud Reconstruction from Single Medical Images** — crossref
- **Masked Clustering Prediction for Unsupervised Point Cloud Pre-training** — arxiv
- ... 等共 14 篇

### Repos (0 个)

（无）

### Datasets (0 个)

（无）

### Baselines (2 个)

- A Fast Knowledge-based Plane Reconstruction Method from Noisy 3D Point Cloud Data
- Parametric Plane Detection from 3D Point Cloud via Probabilistic Clustering

### Innovation Points (3 个)

- 在基于概率聚类的平面检测方法中，引入多视图2D图像投影条件约束，利用投影条件扩散模型提升点云生成质量，从而改善平面检测的鲁棒性。
- 在基于知识的快速平面重建方法中，集成改进的平面检测算法，通过多视图2D图像辅助点云配准，减少噪声影响并提高重建完整性。
- 结合多视图2D图像与3D点云融合方法，在概率聚类平面检测中引入多视图几何约束，提升平面参数估计的准确性。

### Stitching Plan (缝合方案)

- **Baseline**: Parametric Plane Detection from 3D Point Cloud via Probabilistic Clustering
- **Module B**: 投影条件点云扩散模块（来自PC^2: Projection-Conditioned Point Cloud Diffusion for Single-Image 3D Reconstruction）
- **Module C**: 改进的平面检测模块（来自Improved Plane Detection in 3D Reconstruction from 2D Images）

### 标答 (Ground Truth)

- **领域**: 三维视觉/点云
- **可行性**: `risky`
- **标准 Baselines**: ORB-SLAM2
- **标准 Datasets**: KITTI, TUM RGB-D
- **标准 Repos**: ORB\_SLAM2

## R36-007 — 基于视觉的无人机识别与跟踪技术研究

- **可行性裁决**: `feasible` (分数: 75)
- **可行性理由**: 5篇baseline论文均有代码仓库，提供扎实的视觉跟踪基础；但缺少专用无人机数据集，需自行采集或合成，存在硬件依赖风险（需无人机平台和相机）。
- **复核裁决**: `MINOR_REVISION`
- **领域**: vision\_2d
- **方法关键词**: \['visual detection', 'visual tracking']
- **对象关键词**: \['unmanned aerial vehicle']

### Verified Papers (18 篇)

- **Implementation of an Onboard Visual Tracking System with Small Unmanned Aerial Vehicle (UAV)** — arxiv
  - URL: <http://arxiv.org/abs/1205.5742v1>
  - Abstract: This paper presents a visual tracking system that is capable or running real time on-board a small UAV (Unmanned Aerial Vehicle). The tracking system ...
- **Towards Robust Visual Tracking for Unmanned Aerial Vehicle with Tri-Attentional Correlation Filters** — arxiv
  - URL: <http://arxiv.org/abs/2008.00528v2>
  - Abstract: Object tracking has been broadly applied in unmanned aerial vehicle (UAV) tasks in recent years. However, existing algorithms still face difficulties ...
- **Unmanned Aerial Vehicle Visual Detection and Tracking using Deep Neural Networks: A Performance Benchmark** — arxiv
  - URL: <http://arxiv.org/abs/2103.13933v3>
  - Abstract: Unmanned Aerial Vehicles (UAV) can pose a major risk for aviation safety, due to both negligent and malicious use. For this reason, the automated dete...
- **Image Guided Visual Tracking Control System for Unmanned Multirotor Aerial Vehicle with Uncertainty** — crossref
  - URL: <https://doi.org/10.3390/robotics9040103>
  - Abstract: <jats:p>This paper presents a wavelet-based image guided tracking control system for unmanned multirotor aerial vehicle system with the presence of un...
- **Visual tracking and control of Unmanned Aerial Vehicle** — crossref
  - URL: <https://doi.org/10.1109/siu.2015.7130216>
- **Target Tracking with an Unmanned Aerial Vehicle Using Visual Servoing** — crossref
  - URL: <https://doi.org/10.1109/icsc63929.2024.10928827>
- **Tracking of Micro Unmanned Aerial Vehicles: A Comparative Study** — arxiv
  - URL: <http://arxiv.org/abs/2001.06066v1>
  - Abstract: Micro unmanned aerial vehicles (mUAV) became very common in recent years. As a result of their widespread usage, when they are flown by hobbyists ille...
- **Multispectral Detection of Commercial Unmanned Aerial Vehicles** — openalex
- **Air-to-Air Visual Detection of Micro-UAVs: An Experimental Evaluation of Deep Learning** — openalex
- **Vision-Based Detection and Distance Estimation of Micro Unmanned Aerial Vehicles** — openalex
- ... 等共 18 篇

### Weak Papers (25 篇)

- **Semi-Supervised Visual Tracking of Marine Animals using Autonomous Underwater Vehicles** — arxiv
- **Monocular Trail Detection and Tracking Aided by Visual SLAM for Small Unmanned Aerial Vehicles** — arxiv
- **Visual Servoing of Unmanned Surface Vehicle from Small Tethered Unmanned Aerial Vehicle** — arxiv
- **OpenREALM: Real-time Mapping for Unmanned Aerial Vehicles** — arxiv
- **A Comprehensive Survey of Unmanned Aerial Vehicles Detection and Classification Using Machine Learning Approach: Challenges, Solutions, and Future Directions** — openalex
- ... 等共 25 篇

### Repos (2 个)

- **?**
  - URL: <https://github.com/id0ntknowbr0/Drone-Detection-system-with-GUI>
- **?**
  - URL: <https://github.com/AysegulYANIK/my-Master-Thesis>

### Datasets (0 个)

（无）

### Baselines (17 个)

- Implementation of an Onboard Visual Tracking System with Small Unmanned Aerial Vehicle (UAV)
- Towards Robust Visual Tracking for Unmanned Aerial Vehicle with Tri-Attentional Correlation Filters
- Unmanned Aerial Vehicle Visual Detection and Tracking using Deep Neural Networks: A Performance Benchmark
- Image Guided Visual Tracking Control System for Unmanned Multirotor Aerial Vehicle with Uncertainty
- Visual tracking and control of Unmanned Aerial Vehicle
- Target Tracking with an Unmanned Aerial Vehicle Using Visual Servoing
- Tracking of Micro Unmanned Aerial Vehicles: A Comparative Study
- Air-to-Air Visual Detection of Micro-UAVs: An Experimental Evaluation of Deep Learning
- Vision-Based Detection and Distance Estimation of Micro Unmanned Aerial Vehicles
- A SMALL TARGET VISUAL TRACKING METHOD  FOR UNMANNED AERIAL VEHICLE PLATFORM  UNDER CONVOLUTIONAL NEURAL NETWORK

### Innovation Points (3 个)

- 融合多光谱检测与三注意力相关滤波，提升无人机在遮挡和杂乱背景下的鲁棒性
- 结合小波引导视觉跟踪与多光谱检测，提高无人机在不确定性下的跟踪精度
- 将多光谱检测与深度神经网络检测结合，提升无人机检测的鲁棒性

### Stitching Plan (缝合方案)

- **Baseline**: Tri-Attentional Correlation Filters
- **Module B**: 多光谱特征提取模块（来自Multispectral Detection of Commercial Unmanned Aerial Vehicles）
- **Module C**: 三注意力相关滤波跟踪器（来自baseline）

### 标答 (Ground Truth)

- **领域**: 遥感/无人机
- **可行性**: `feasible`
- **标准 Baselines**: YOLOv5
- **标准 Datasets**: DOTA, VisDrone
- **标准 Repos**: ultralytics/yolov5

## R36-015 — 基于患者虚拟定位的三维人体重建关键技术研究

- **可行性裁决**: `risky` (分数: 45)
- **可行性理由**: 5篇baseline有repo，但无数据集和代码仓库；涉及患者定位，存在数据合规风险（需伦理审批），且无公开数据集，自建困难。
- **复核裁决**: `MINOR_REVISION`
- **领域**: medical\_ai
- **方法关键词**: \['virtual patient positioning', '3D human reconstruction']
- **对象关键词**: \['human body']

### Verified Papers (14 篇)

- **3D Reconstruction and alignment by consumer RGB-D sensors and fiducial planar markers for patient positioning in radiation therapy** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/88126d15799b76e4230633da6624a56d193975a7>
  - Abstract: BACKGROUND AND OBJECTIVE
    Patient positioning is a crucial step in radiation therapy, for which non-invasive methods have been developed based on surfa...
- **3D Human Reconstruction from an Image for Mobile Telepresence Systems** — crossref
  - URL: <https://doi.org/10.1109/vrw50115.2020.00237>
- **Image-based 3D reconstruction and articulation of the human body shape and its use in the creation of virtual fitting rooms** — crossref
  - URL: <https://doi.org/10.17918/00000196>
  - Abstract: <jats:p>Image-based 3D shape reconstruction is essential for 3D modeling in recognition, virtual reality, generation of video games, 3D animation, and...
- **3D tomographic reconstruction from portal imaging for patient positioning** — crossref
  - URL: <https://doi.org/10.1016/s0531-5131(03)00513-2>
- **3D Reconstruction of Human Body in Virtual Fitting Room Based on Kinect** — crossref
  - URL: <https://doi.org/10.38007/ijmc.2022.030403>
- **Three-dimensional surface scanning for accurate patient positioning and monitoring during breast cancer radiotherapy** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/d1e8d8a630d8fc1fd4e68d5c74d4ba4ce18d653e>
- **Joint scene and object tracking for cost-Effective augmented reality guided patient positioning in radiation therapy** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/2c3c319197c93fa5d63bbfe37a9a7e0e8ee6b582>
  - Abstract: BACKGROUND AND OBJECTIVE
    The research is done in the field of Augmented Reality (AR) for patient positioning in radiation therapy is scarce. We propos...
- **Joint Scene and Object Tracking for Cost-Effective Augmented Reality Assisted Patient Positioning in Radiation Therapy** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/5797fd399b48b3d6089ac513ff16bcc513420b1e>
- **Clinical evaluation of a commercial surface-imaging system for patient positioning in radiotherapy** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/461481f44ca469c889d3328746b7dc5b9ff278f7>
  - Abstract: BackgroundLaser scanning-based patient surface positioning and surveillance may complement image-guided radiotherapy (IGRT) as a nonradiation-based ap...
- **Head radiotherapy positioning guidance system based on feature recognition and automatic annotation: Clinical validation and error analysis** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/624e8f6f99a6c835c3c77040e06a502e645a8081>
  - Abstract: Positioning accuracy in radiotherapy is critical for treatment outcomes, especially in head tumor radiotherapy, where the target area is small and sur...
- ... 等共 14 篇

### Weak Papers (44 篇)

- **PARTE: Part-Guided Texturing for 3D Human Reconstruction from a Single Image** — arxiv
- **OAHuman: Occlusion-Aware 3D Human Reconstruction from Monocular Images** — arxiv
- **ReFu: Refine and Fuse the Unobserved View for Detail-Preserving Single-Image 3D Human Reconstruction** — arxiv
- **DeepHuman: 3D Human Reconstruction from a Single Image** — arxiv
- **SAT: Supervisor Regularization and Animation Augmentation for Two-process Monocular Texture 3D Human Reconstruction** — arxiv
- ... 等共 44 篇

### Repos (0 个)

（无）

### Datasets (0 个)

（无）

### Baselines (12 个)

- 3D Reconstruction and alignment by consumer RGB-D sensors and fiducial planar markers for patient positioning in radiation therapy
- 3D Human Reconstruction from an Image for Mobile Telepresence Systems
- Image-based 3D reconstruction and articulation of the human body shape and its use in the creation of virtual fitting rooms
- 3D tomographic reconstruction from portal imaging for patient positioning
- 3D Reconstruction of Human Body in Virtual Fitting Room Based on Kinect
- Three-dimensional surface scanning for accurate patient positioning and monitoring during breast cancer radiotherapy
- Clinical evaluation of a commercial surface-imaging system for patient positioning in radiotherapy
- Head radiotherapy positioning guidance system based on feature recognition and automatic annotation: Clinical validation and error analysis
- Exploratory development and clinical research of a mixed reality guided radiotherapy positioning system
- Diplomarbeit Intensity Based Rigid 2 D-3 D Registration Algorithms for Radiation Therapy In collaboration with

### Innovation Points (3 个)

- 结合RGB-D传感器与平面标记物实现患者虚拟定位的三维人体重建，并引入增强现实（AR）场景与患者跟踪模块，提升定位精度与交互性。
- 将图像驱动的三维人体重建方法（如虚拟试衣间中的重建）与RGB-D传感器定位结合，实现从单张图像到三维模型的快速重建，用于患者虚拟定位。
- 利用Kinect深度传感器进行人体三维重建，并融合AR跟踪技术，实现低成本、高交互性的患者定位系统。

### Stitching Plan (缝合方案)

- **Baseline**: 3D Reconstruction and alignment by consumer RGB-D sensors and fiducial planar markers for patient positioning in radiation therapy
- **Module B**: Joint scene and object tracking for cost-Effective augmented reality guided patient positioning in radiation therapy
- **Module C**: Image-based 3D reconstruction and articulation of the human body shape and its use in the creation of virtual fitting rooms

### 标答 (Ground Truth)

- **领域**: 医学/人体重建
- **可行性**: `risky`
- **标准 Baselines**: SMPL
- **标准 Datasets**: SURREAL, Human3.6M
- **标准 Repos**: （无）

## R36-021 — 基于深度学习的自动驾驶感知算法研究

- **可行性裁决**: `feasible` (分数: 78)
- **可行性理由**: 有6篇baseline论文，其中1篇有repo；48篇parallel论文；6个数据集和12个代码仓库。硬件依赖风险高（需GPU集群、传感器），但公开数据集（如KITTI）和仿真平台可缓解。数据合规风险低。
- **复核裁决**: `ACCEPT`
- **领域**: robotics\_control
- **方法关键词**: \['deep learning']
- **对象关键词**: \['autonomous vehicle']

### Verified Papers (55 篇)

- **Deep Multi-Modal Object Detection and Semantic Segmentation for Autonomous Driving: Datasets, Methods, and Challenges** — openalex
- **Deep Learning Sensor Fusion for Autonomous Vehicle Perception and Localization: A Review** — openalex
- **Perception and sensing for autonomous vehicles under adverse weather conditions: A survey** — openalex
- **Deep Learning for Image and Point Cloud Fusion in Autonomous Driving: A Review** — openalex
- **Deep learning for object detection and scene perception in self-driving cars: Survey, challenges, and open issues** — openalex
- **RAF: Reliability-Aware Fusion of Camera, LiDAR, and 4D RADAR for Robust 3D Object Detection in Adverse Weather** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/0afd71e14f5c0a89030213c0d4614c9bbed0bc6c>
  - Abstract: Robust 3D object detection in adverse weather conditions is challenging due to sensor limitations. Although combining complementary modalities such as...
- **D3VO: Deep Depth, Deep Pose and Deep Uncertainty for Monocular Visual Odometry** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/61bbec51fa32571925c17efe8a2c7da48473f419>
  - Abstract: We propose D3VO as a novel framework for monocular visual odometry that exploits deep networks on three levels -- deep depth, pose and uncertainty est...
- **Improving Map Re-localization with Deep ‘Movable’ Objects Segmentation on 3D LiDAR Point Clouds** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/7d5ad4fdce839d2fafef9f4476d4c40a8e02c9a3>
  - Abstract: Localization and Mapping is an essential component to enable Autonomous Vehicles navigation, and requires an accuracy exceeding that of commercial GPS...
- **Real-time Depth Estimation Using Recurrent CNN with Sparse Depth Cues for SLAM System** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/acc71b7ae1e4ef7f7c9a479536b6340f0b34b962>
- **Deep Visible and Thermal Image Fusion for Enhanced Pedestrian Visibility** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/60da4e8ec5746ebe2ad11417e09b770bd65c02eb>
  - Abstract: Reliable vision in challenging illumination conditions is one of the crucial requirements of future autonomous automotive systems. In the last decade,...
- ... 等共 55 篇

### Weak Papers (60 篇)

- **Lidar for Autonomous Driving: The Principles, Challenges, and Trends for Automotive Lidar and Perception Systems** — openalex
- **A Review on Autonomous Vehicles: Progress, Methods and Challenges** — openalex
- **Survey on semantic segmentation using deep learning techniques** — openalex
- **Deep Learning: A Comprehensive Overview on Techniques, Taxonomy, Applications and Research Directions** — openalex
- **Sensor and Sensor Fusion Technology in Autonomous Vehicles: A Review** — openalex
- ... 等共 60 篇

### Repos (12 个)

- **?**
  - URL: <https://github.com/Aryia-Behroziuan/References>
- **?**
  - URL: <https://github.com/Vijayraven95/State-of-the-art-algorithms->
- **?**
  - URL: <https://github.com/Prasham2181/EinsteinVision-Tesla-Inspired-Visual-Perception-System>
- **?**
  - URL: <https://github.com/FerXxk/Auto-Parking-RL>
- **?**
  - URL: <https://github.com/swaranika27nath-spec/autonomous-driving-system>
- **?**
  - URL: <https://github.com/Habmoham/advancing-perception-autonomous-driving>
- **?**
  - URL: <https://github.com/sutharsanan007/Autonomous-Vehicle-Perception-Stack>
- **?**
  - URL: <https://github.com/Gerneve5/autonomous-perception-system>
- **?**
  - URL: <https://github.com/AliRadwan1/Autonomous-Vehicle-Perception-Module>
- **?**
  - URL: <https://github.com/Zyadateff/Autonomous-Vehicle-Perception-Module>

### Datasets (6 个)

- **KITTI** (source: paper\_title\_heuristic)
- **EuRoC** (source: paper\_title\_heuristic)
- **CARLA** (source: paper\_title\_heuristic)
- **Bonn** (source: paper\_title\_heuristic)
- **nuScenes** (source: paper\_title\_heuristic)
- **Cityscapes** (source: paper\_title\_heuristic)

### Baselines (6 个)

- Deep Multi-Modal Object Detection and Semantic Segmentation for Autonomous Driving: Datasets, Methods, and Challenges
- Deep Learning Sensor Fusion for Autonomous Vehicle Perception and Localization: A Review
- Deep Learning for Image and Point Cloud Fusion in Autonomous Driving: A Review
- Deep learning for object detection and scene perception in self-driving cars: Survey, challenges, and open issues
- Vision and Multimodal Perception for Autonomous Driving: Deep Learning Architectures, Tasks, and Sensor Fusion
- E2ETrADS: end-to-end transformer based autonomous driving system for adverse weather conditions

### Innovation Points (4 个)

- 在baseline的多模态融合框架中，引入可靠性感知融合模块，利用不确定性估计动态调整相机、LiDAR和4D雷达的权重，提升恶劣天气下的3D目标检测鲁棒性。
- 在baseline的深度估计网络中，集成循环卷积网络（RCNN）和稀疏深度线索，实现实时深度估计，并用于SLAM系统的定位增强。
- 在baseline的视觉里程计框架中，引入深度、位姿和不确定性的联合自监督学习，提升单目视觉里程计的精度和鲁棒性。
- 在baseline的3D点云定位与建图系统中，集成可移动物体分割模块，过滤动态物体，提升重定位的鲁棒性。

### Stitching Plan (缝合方案)

- **Baseline**: 多模态融合检测网络（基于AVOD或PointPillars）
- **Module B**: 可靠性感知融合模块（来自RAF论文）
- **Module C**: 可移动物体分割模块（来自Improving Map Re-localization论文）

### 标答 (Ground Truth)

- **领域**: 自动驾驶
- **可行性**: `feasible`
- **标准 Baselines**: YOLOv5
- **标准 Datasets**: KITTI, nuScenes
- **标准 Repos**: ultralytics/yolov5

## R36-052 — 基于深度强化学习的无人驾驶感知与决策研究

- **可行性裁决**: `feasible` (分数: 85)
- **可行性理由**: 3篇baseline均有代码仓库，12个仓库资源丰富，但缺乏专用数据集且涉及自动驾驶硬件依赖（传感器、GPU集群），需评估获取可行性。
- **复核裁决**: `ACCEPT`
- **领域**: robotics\_control
- **方法关键词**: \['deep reinforcement learning']
- **对象关键词**: \['autonomous vehicle']

### Verified Papers (4 篇)

- **Multi-agent Reinforcement Learning for Cooperative Lane Changing of Connected and Autonomous Vehicles in Mixed Traffic** — arxiv
  - URL: <http://arxiv.org/abs/2111.06318v2>
  - Abstract: Autonomous driving has attracted significant research interests in the past two decades as it offers many potential benefits, including releasing driv...
- **A Hierarchical Architecture for Sequential Decision-Making in Autonomous Driving using Deep Reinforcement Learning** — arxiv
  - URL: <http://arxiv.org/abs/1906.08464v1>
  - Abstract: Tactical decision making is a critical feature for advanced driving systems, that incorporates several challenges such as complexity of the uncertain ...
- **Deep Reinforcement Learning framework for Autonomous Driving** — arxiv
  - URL: <http://arxiv.org/abs/1704.02532v1>
  - Abstract: Reinforcement learning is considered to be a strong AI paradigm which can be used to teach machines through interaction with the environment and learn...
- **Multi-Agent Connected Autonomous Driving using Deep Reinforcement Learning** — arxiv
  - URL: <http://arxiv.org/abs/1911.04175v1>
  - Abstract: The capability to learn and adapt to changes in the driving environment is crucial for developing autonomous driving systems that are scalable beyond ...

### Weak Papers (6 篇)

- **Distributed Deep Reinforcement Learning Based Gradient Quantization for Federated Learning Enabled Vehicle Edge Computing** — arxiv
- **Classifying Options for Deep Reinforcement Learning** — arxiv
- **Review of Deep Reinforcement Learning for Autonomous Driving** — arxiv
- **Value Bonuses using Ensemble Errors for Exploration in Reinforcement Learning** — arxiv
- **Comparing Deep Reinforcement Learning and Evolutionary Methods in Continuous Control** — arxiv
- ... 等共 6 篇

### Repos (12 个)

- **?**
  - URL: <https://github.com/michigan-traffic-lab/Dense-Deep-Reinforcement-Learning>
- **?**
  - URL: <https://github.com/imasmitja/RLforUTracking>
- **?**
  - URL: <https://github.com/Ice-mao/RL_AUV_tracking>
- **?**
  - URL: <https://github.com/Guojyjy/CoTV>
- **?**
  - URL: <https://github.com/LoheshM/Comparative-Analysis-of-Reinforcement-Learning-Models-for-Lane-Change-Decision-Making>
- **?**
  - URL: <https://github.com/gustavomoers/CollisionAvoidance-Carla-DRL-MPC>
- **?**
  - URL: <https://github.com/Aryia-Behroziuan/References>
- **?**
  - URL: <https://github.com/hoangtranngoc/AirSim-RL>
- **?**
  - URL: <https://github.com/Rishikesh-Jadhav/Reinforcement-Learning-for-Autonomous-Navigation-using-Deep-Q-Network-and-Twin-Delayed-DDPG>
- **?**
  - URL: <https://github.com/EnnaSachdeva/Recurrent-Multiagent-Deep-Deterministic-Policy-Gradient-with-Difference-Rewards>

### Datasets (0 个)

（无）

### Baselines (3 个)

- A Hierarchical Architecture for Sequential Decision-Making in Autonomous Driving using Deep Reinforcement Learning
- Deep Reinforcement Learning framework for Autonomous Driving
- Multi-Agent Connected Autonomous Driving using Deep Reinforcement Learning

### Innovation Points (3 个)

- 在分层决策架构中引入多智能体协同换道模块，提升混合交通流下的决策鲁棒性
- 在端到端DRL框架中集成多智能体通信机制，实现车辆间信息共享与协同决策
- 在多智能体连接自动驾驶中引入分层奖励机制，优化换道决策的长期收益

### Stitching Plan (缝合方案)

- **Baseline**: Hierarchical DRL for Autonomous Driving
- **Module B**: 多智能体协同换道策略（MADDPG）
- **Module C**: 分层奖励函数设计

### 标答 (Ground Truth)

- **领域**: 自动驾驶/强化学习
- **可行性**: `risky`
- **标准 Baselines**: PPO
- **标准 Datasets**: CARLA
- **标准 Repos**: （无）

## R36-060 — 基于深度学习的车道线检测方法研究

- **可行性裁决**: `feasible` (分数: 75)
- **可行性理由**: Baseline论文RONELD和Self Attention Distillation均有公开repo，代码可直接复用；Parallel论文Agnostic Lane Detection提供补充思路。但无专用数据集，需自行采集或使用开源数据（如TuSimple/CULane），存在数据标注工作量。...
- **复核裁决**: `ACCEPT`
- **领域**: vision\_2d
- **方法关键词**: \['deep learning']
- **对象关键词**: \['lane line']

### Verified Papers (3 篇)

- **RONELD: Robust Neural Network Output Enhancement for Active Lane Detection** — arxiv
  - URL: <http://arxiv.org/abs/2010.09548v2>
  - Abstract: Accurate lane detection is critical for navigation in autonomous vehicles, particularly the active lane which demarcates the single road space that th...
- **Agnostic Lane Detection** — arxiv
  - URL: <http://arxiv.org/abs/1905.03704v1>
  - Abstract: Lane detection is an important yet challenging task in autonomous driving, which is affected by many factors, e.g., light conditions, occlusions cause...
- **Learning Lightweight Lane Detection CNNs by Self Attention Distillation** — arxiv
  - URL: <http://arxiv.org/abs/1908.00821v1>
  - Abstract: Training deep models for lane detection is challenging due to the very subtle and sparse supervisory signals inherent in lane annotations. Without lea...

### Weak Papers (3 篇)

- **DILIE: Deep Internal Learning for Image Enhancement** — arxiv
- **Oriented object detection in optical remote sensing images using deep learning: a survey** — arxiv
- **A multitask deep learning model for real-time deployment in embedded systems** — arxiv

### Repos (12 个)

- **?**
  - URL: <https://github.com/Mouiad-JRA/Lane-Line-Detection-using-Image-Processing-vs-Deep-Learning>
- **?**
  - URL: <https://github.com/rhyijg/Deep-Learning-Lane-line-detection>
- **?**
  - URL: <https://github.com/ashokumar06/Road-lane-line-detection>
- **?**
  - URL: <https://github.com/yantiz/Lane-Lines-Segmentation>
- **?**
  - URL: <https://github.com/SCASE-Projects/-Lane-Line-Detection-using-Image-Processing-vs-Deep-Learning>
- **?**
  - URL: <https://github.com/Ayush12062000/Road_lane_Detection>
- **?**
  - URL: <https://github.com/YoussefMoHlemyAlpha/-Identifying-road-lanes-for-autonomous-driving-systems>
- **?**
  - URL: <https://github.com/Sonichannraj/Lane-line-detection>
- **?**
  - URL: <https://github.com/thippeswammy/LaneLinesDetection>
- **?**
  - URL: <https://github.com/suvro5495/Road-Lane-Line-Detection>

### Datasets (0 个)

（无）

### Baselines (2 个)

- RONELD: Robust Neural Network Output Enhancement for Active Lane Detection
- Learning Lightweight Lane Detection CNNs by Self Attention Distillation

### Innovation Points (3 个)

- 在RONELD的后处理模块中引入Agnostic Lane Detection的语义分割分支，以增强对遮挡和光照变化的鲁棒性
- 将Self Attention Distillation的注意力蒸馏机制应用于RONELD的特征提取网络，以提升轻量级模型的检测精度
- 结合Agnostic Lane Detection的全局上下文模块与RONELD的后处理，实现端到端的车道线检测增强

### Stitching Plan (缝合方案)

- **Baseline**: RONELD
- **Module B**: Self Attention Distillation的注意力蒸馏损失
- **Module C**: Agnostic Lane Detection的语义分割分支

## R36-074 — 基于深度学习的混凝土桥梁裂缝检测研究

- **可行性裁决**: `feasible` (分数: 82)
- **可行性理由**: 5篇baseline论文均聚焦混凝土桥梁裂缝检测，方法涵盖分类、检测、分割，且提供3个数据集和5个代码仓库，复现基础扎实。无硬件依赖（仅需图像数据），数据合规风险低（非医疗/人体数据）。
- **复核裁决**: `ACCEPT`
- **领域**: civil\_infra
- **方法关键词**: \['deep learning']
- **对象关键词**: \['concrete bridge', 'crack']

### Verified Papers (43 篇)

- **Crack detection for concrete bridges with imaged based deep learning** — openalex
- **Crack Detection from a Concrete Surface Image Based on Semantic Segmentation Using Deep Learning** — openalex
- **Intelligent Crack Detection and Quantification in the Concrete Bridge: A Deep Learning‐Assisted Image Processing Approach** — openalex
- **Deep learning-based visual defect-inspection system for reinforced concrete bridge substructure: a case of Thailand’s department of highways** — openalex
- **Concrete bridge surface damage detection using a single-stage detector** — openalex
- **Real-Time Detection of Cracks on Concrete Bridge Decks Using Deep Learning in the Frequency Domain** — openalex
- **Automated Vision-Based Detection of Cracks on Concrete Surfaces Using a Deep Learning Technique** — openalex
- **Automatic Bridge Crack Detection Using a Convolutional Neural Network** — openalex
- **HDCB-Net: A Neural Network With the Hybrid Dilated Convolution for Pixel-Level Crack Detection on Concrete Bridges** — openalex
- **SDNET2018: An annotated image dataset for non-contact concrete crack detection using deep convolutional neural networks** — openalex
- ... 等共 43 篇

### Weak Papers (61 篇)

- **Image-Based Crack Detection Methods: A Review** — openalex
- **Autonomous detection of concrete damage under fire conditions** — semantic\_scholar
- **Automatic pavement crack detection using multimodal features fusion deep neural network** — semantic\_scholar
- **PCDNet: Seed Operation–Based Deep Learning Model for Pavement Crack Detection on 3D Asphalt Surface** — semantic\_scholar
- **Automated asphalt pavement damage rate detection based on optimized GA-CNN** — semantic\_scholar
- ... 等共 61 篇

### Repos (5 个)

- **?**
  - URL: <https://github.com/Harshadakokande/Infrastructure-Crack-Detection-using-Computer-Vision->
- **?**
  - URL: <https://github.com/Kalyan0701/khatry2026automated>
- **?**
  - URL: <https://github.com/dengxinhong0222/Intelligent-Detection-of-Concrete-Bridge-Cracks-Based-on-Machine-Vision>
- **?**
  - URL: <https://github.com/zainfaisal220/FYP>
- **?**
  - URL: <https://github.com/Ishfaq9/CSE-4.2-SoftComputing-Lab-Project>

### Datasets (3 个)

- **SDNET2018** (source: paper\_title\_heuristic)
- **DeepCrack** (source: paper\_title\_heuristic)
- **Crack500** (source: paper\_title\_heuristic)

### Baselines (40 个)

- Crack detection for concrete bridges with imaged based deep learning
- Intelligent Crack Detection and Quantification in the Concrete Bridge: A Deep Learning‐Assisted Image Processing Approach
- Concrete bridge surface damage detection using a single-stage detector
- Real-Time Detection of Cracks on Concrete Bridge Decks Using Deep Learning in the Frequency Domain
- Automated Vision-Based Detection of Cracks on Concrete Surfaces Using a Deep Learning Technique
- Automatic Bridge Crack Detection Using a Convolutional Neural Network
- HDCB-Net: A Neural Network With the Hybrid Dilated Convolution for Pixel-Level Crack Detection on Concrete Bridges
- SDNET2018: An annotated image dataset for non-contact concrete crack detection using deep convolutional neural networks
- A novel YOLOv8-GAM-Wise-IoU model for automated detection of bridge surface cracks
- Integrated pixel-level CNN-FCN crack detection via photogrammetric 3D texture mapping of concrete structures

### Innovation Points (3 个)

- 在YOLOv5单阶段检测器基础上，集成频率域预处理模块和语义分割后处理模块，提升裂缝检测的实时性与像素级定位精度
- 在基于图像深度学习的裂缝检测基线中，引入注意力机制增强的特征提取模块和缺陷分类细化模块，提升对复杂背景的鲁棒性
- 在自动化视觉检测基线中，集成语义分割网络作为辅助分支，实现裂缝检测与分割的联合学习，提升检测精度

### Stitching Plan (缝合方案)

- **Baseline**: YOLOv5 (Concrete bridge surface damage detection using a single-stage detector)
- **Module B**: 频率域预处理（FFT带通滤波） from Real-Time Detection of Cracks on Concrete Bridge Decks Using Deep Learning in the Frequency Domain
- **Module C**: 语义分割后处理（U-Net） from Crack Detection from a Concrete Surface Image Based on Semantic Segmentation Using Deep Learning

### 标答 (Ground Truth)

- **领域**: 土木/裂缝
- **可行性**: `feasible`
- **标准 Baselines**: U-Net, YOLOv5
- **标准 Datasets**: DeepCrack, SDNET2018
- **标准 Repos**: ultralytics/yolov5

## R36-079 — 基于结构光的隧道裂缝检测技术研究与实现

- **可行性裁决**: `risky` (分数: 55)
- **可行性理由**: 2篇baseline有repo，但无公开隧道裂缝数据集，自建需结构光硬件和现场采集，周期长风险高。parallel论文提供方法参考但无直接数据支撑。
- **复核裁决**: `MINOR_REVISION`
- **领域**: civil\_infra
- **方法关键词**: \['structured light']
- **对象关键词**: \['tunnel', 'crack']

### Verified Papers (10 篇)

- **Concrete crack detection and quantification using deep learning and structured light** — crossref
  - URL: <https://doi.org/10.1016/j.conbuildmat.2020.119096>
- **Coarse-to-fine crack cue for robust crack detection** — arxiv
  - URL: <http://arxiv.org/abs/2507.16851v1>
  - Abstract: Crack detection is an important task in computer vision. Despite impressive in-dataset performance, deep learning-based methods still struggle in gene...
- **CDSNet: Crack detection and segmentation network for tunnel** — crossref
  - URL: <https://doi.org/10.2139/ssrn.5497574>
- **Research on tunnel crack detection method based on multimodal recognition** — crossref
  - URL: <https://doi.org/10.2139/ssrn.5705398>
- **Detection of Diffuse Seafloor Venting Using Structured Light Imaging** — crossref
  - URL: <https://doi.org/10.23860/thesis-smart-clara-2013>
- **Effective small crack detection based on tunnel crack characteristics and an anchor-free convolutional neural network** — crossref
  - URL: <https://doi.org/10.1038/s41598-024-60454-3>
  - Abstract: <jats:title>Abstract\</jats:title><jats:p>Tunnel cracks are thin and narrow linear targets, and their pixel proportions in images are usually very low,...
- **Tunnel Crack Detection Method Based on Improved CenterNet** — crossref
  - URL: <https://doi.org/10.1109/ccdc62350.2024.10588167>
- **Structured light detection and delineation of tripping hazards for people with impaired vision** — crossref
  - URL: <https://doi.org/10.17760/d20474748>
- **Automatic Classification and Segmentation of Tunnel Cracks Based on Deep Learning and Visual Explanations** — arxiv
  - URL: <http://arxiv.org/abs/2507.14010v1>
  - Abstract: Tunnel lining crack is a crucial indicator of tunnels' safety status. Aiming to classify and segment tunnel cracks with enhanced accuracy and efficien...
- **Research on Tunnel Crack Identification Localization and Segmentation Method Based on Improved YOLOX and UNETR++** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/19996356f8f3aa444ed05b585aac6b13f1cabebb>
  - Abstract: To address the challenges in identifying and segmenting fine irregular cracks in tunnels, this paper proposes a new crack identification, localization...

### Weak Papers (33 篇)

- **Segmentation of Concrete Cracks by Using Fractal Dimension and UHK-Net** — semantic\_scholar
- **Pixel-level pavement crack segmentation with encoder-decoder network** — semantic\_scholar
- **Automatic defect detection and segmentation of tunnel surface using modified Mask R-CNN** — semantic\_scholar
- **Automatic defect detection of metro tunnel surfaces using a vision-based inspection system** — semantic\_scholar
- **Comparison of crack segmentation using digital image correlation measurements and deep learning** — semantic\_scholar
- ... 等共 33 篇

### Repos (0 个)

（无）

### Datasets (0 个)

（无）

### Baselines (2 个)

- Concrete crack detection and quantification using deep learning and structured light
- Research on Tunnel Crack Identification Localization and Segmentation Method Based on Improved YOLOX and UNETR++

### Innovation Points (3 个)

- 在基于结构光的隧道裂缝检测中，引入粗到细的裂缝线索模块（CrackCue）以增强对细长裂缝的检测能力，并改进YOLOX骨干网络以提升小目标裂缝的识别精度。
- 结合CDSNet中的裂缝检测与分割网络结构，在baseline的UNETR++分割分支中引入多尺度特征融合模块，提升对不规则裂缝的分割精度。
- 利用基于隧道裂缝特征的无锚点卷积神经网络（anchor-free CNN）替换baseline中的YOLOX检测头，以更好地检测细小裂缝目标。

### Stitching Plan (缝合方案)

- **Baseline**: 改进YOLOX + UNETR++
- **Module B**: CrackCue粗到细线索模块（来自Coarse-to-fine crack cue for robust crack detection）
- **Module C**: CDSNet多尺度特征融合模块（来自CDSNet: Crack detection and segmentation network for tunnel）

### 标答 (Ground Truth)

- **领域**: 土木/裂缝
- **可行性**: `risky`
- **标准 Baselines**: U-Net
- **标准 Datasets**: DeepCrack
- **标准 Repos**: （无）

## R36-084 — 基于U-Net卷积网络的地质岩层裂缝检测方法

- **可行性裁决**: `feasible` (分数: 75)
- **可行性理由**: 5篇baseline均有repo，代码可复现；但无公开数据集，需自建或标注，存在数据获取风险。地质裂缝检测无需实物硬件，无伦理合规问题。
- **复核裁决**: `ACCEPT`
- **领域**: vision\_2d
- **方法关键词**: \['U-Net', 'convolutional neural network']
- **对象关键词**: \['geological rock formation', 'fracture']

### Verified Papers (9 篇)

- **Fracture Detection and Segmentation From Electrical Image Logs Using YOLOv7-U-Net** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/d8b757d5b1f84078d636a5f55daf45da6dee2f41>
  - Abstract: Image logging provides extensive information about the physical properties and geological
    features of reservoirs. Fracture identification based on el...
- **Application of an Improved U-Net Neural Network on Fracture Segmentation from Outcrop Images** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/810816597f980d7127cc7b49e3be18815912a1e5>
  - Abstract: Outcrop records contain very rich geological historical information, and the study of fractures in outcrop areas is an important part of geological ex...
- **Fracture Structure Detection Based on U-Net With Angle Domain Fracture Scattering Imaging** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/80dbd8ae874453fc510964160003c5e2f8717eb7>
  - Abstract: The analysis of the parameters and configurations of natural or induced fractures is crucial for guiding reservoir development. These fractures produc...
- **Fracture recognition with U-net and pixel-based automatic fracture detection** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/9e534177213eb207969433674eca2881120e58ec>
  - Abstract: Summary Interpretation of fractures in raw outcrop maps is a tedious and time-consuming task. A few semi-automatic or automatic interpretation methods...
- **MS-Unet: A Multi-Scale Feature Fusion U-Net for 3D Seismic Fault Detection** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/60a85f2f73da21f258d5e75802ad4245c5fc32ff>
  - Abstract: Accurate detection of fault structures in seismic data is vital for oil and gas exploration and geological hazard assessment. These faults exhibit div...
- **CFEM-Net: Cross-Scale Feature Enhancement and Edge-Aware Learning for Geological Fracture Segmentation** — crossref
  - URL: <https://doi.org/10.1109/icsp69961.2026.11540892>
- **Dscu-Net: A Deep Learning Framework for Fracture Detection in Underground Roadway Imagery** — crossref
  - URL: <https://doi.org/10.2139/ssrn.5370676>
- **LightECA-UNet: a lightweight model for segmentation of coal fracture CT images** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/bc47ded958f7526b6490bc6f39cf0920c314b168>
  - Abstract: Coal fracture segmentation in CT images is critical for coal structure analysis, coalbed methane extraction, and mine safety, but it is challenged by ...
- **GeoCrack: A High-Resolution Dataset For Segmentation of Fracture Edges in Geological Outcrops** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/4ded132e261ac99f65bdb387ed8db3166f3e8bcf>
  - Abstract: GeoCrack is the first large-scale open source annotated dataset of fracture traces from geological outcrops, enabling deep learning-based fracture seg...

### Weak Papers (18 篇)

- **Seq-U-Net: A One-Dimensional Causal U-Net for Efficient Sequence Modelling** — arxiv
- **Macroscale fracture surface segmentation via semi-supervised learning considering the structural similarity** — arxiv
- **BioLite U-Net: Edge-Deployable Semantic Segmentation for In Situ Bioprinting Monitoring** — arxiv
- **CU-Net: LiDAR Depth-Only Completion With Coupled U-Net** — arxiv
- **Wave-U-Net: A Multi-Scale Neural Network for End-to-End Audio Source Separation** — arxiv
- ... 等共 18 篇

### Repos (0 个)

（无）

### Datasets (0 个)

（无）

### Baselines (8 个)

- Fracture Detection and Segmentation From Electrical Image Logs Using YOLOv7-U-Net
- Application of an Improved U-Net Neural Network on Fracture Segmentation from Outcrop Images
- Fracture Structure Detection Based on U-Net With Angle Domain Fracture Scattering Imaging
- Fracture recognition with U-net and pixel-based automatic fracture detection
- MS-Unet: A Multi-Scale Feature Fusion U-Net for 3D Seismic Fault Detection
- Dscu-Net: A Deep Learning Framework for Fracture Detection in Underground Roadway Imagery
- LightECA-UNet: a lightweight model for segmentation of coal fracture CT images
- GeoCrack: A High-Resolution Dataset For Segmentation of Fracture Edges in Geological Outcrops

### Innovation Points (3 个)

- 在YOLOv7-U-Net基线中引入跨尺度特征增强模块，以提升多尺度裂缝检测能力
- 在改进U-Net裂缝分割基线中融合边缘感知学习模块，增强裂缝边界定位精度
- 在角度域裂缝散射成像U-Net中集成跨尺度特征增强，提升散射波特征提取能力

### Stitching Plan (缝合方案)

- **Baseline**: YOLOv7-U-Net
- **Module B**: CFEM-Net的跨尺度特征增强模块
- **Module C**: CFEM-Net的边缘感知学习模块

### 标答 (Ground Truth)

- **领域**: 土木/裂缝
- **可行性**: `feasible`
- **标准 Baselines**: U-Net
- **标准 Datasets**: DeepCrack, CRACK500
- **标准 Repos**: （无）

## R36-091 — 基于云计算的输电线路缺陷检测平台

- **可行性裁决**: `risky` (分数: 45)
- **可行性理由**: Baseline论文有repo，但无公开数据集和代码仓库；输电线路缺陷检测依赖专用数据集（如绝缘子、异物），自建需大量实地拍摄和标注，周期长；硬件依赖无人机或巡检机器人，获取困难。
- **复核裁决**: `MINOR_REVISION`
- **领域**: energy\_power
- **方法关键词**: \['cloud computing', 'defect detection']
- **对象关键词**: \['transmission line']

### Verified Papers (5 篇)

- **Transmission Line Insulator Defect Detection with Improved YOLOv11** — None
- **Research on Transmission Line Defect Detection System Based on Cloud-Edge-End Collaboration** — crossref
  - URL: <https://doi.org/10.1109/cac59555.2023.10450887>
- **Detection of Transmission Line Insulator Defect Based on Improved YOLOv10** — crossref
  - URL: <https://doi.org/10.1109/eect64505.2025.10966943>
- **RPC-DETR: A Lightweight and Accurate Model for Foreign Object Detection on Transmission Lines** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/8fed2a10c61710b25b95c8e97256897a810b5201>
  - Abstract: Transmission lines are often located in complex environments and prone to interference from foreign objects, which, if not promptly addressed, can lea...
- **FGL-YOLO: A Lightweight and Efficient Network for Insulator Defect Detection on UAV** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/c15386af363d63f7719ba8fef582ecec6fde0cf0>
  - Abstract: Aiming at the challenges of insulator defect detection in transmission line inspection, such as complex background, small target and limited computing...

### Weak Papers (18 篇)

- **Cloud Computing - Architecture and Applications** — arxiv
- **DeepInspect: An AI-Powered Defect Detection for Manufacturing Industries** — arxiv
- **TL-DETR: Efficient transmission line defect detection for edge deployment** — crossref
- **TLDD-YOLO: An Improved YOLO for Transmission Line Component and Defect Detection** — crossref
- **Transmission Line Insulator Defect Detection Based on Enhanced YOLOv5n** — crossref
- ... 等共 18 篇

### Repos (0 个)

（无）

### Datasets (0 个)

（无）

### Baselines (1 个)

- Research on Transmission Line Defect Detection System Based on Cloud-Edge-End Collaboration

### Innovation Points (4 个)

- 在云边端协同的基线框架中，引入改进YOLOv11的轻量化骨干网络和注意力机制，提升绝缘子缺陷检测精度与速度。
- 在云边端协同基线中，集成改进YOLOv10的检测头优化和损失函数改进，增强小目标缺陷检测能力。
- 在云边端协同基线中，缝合RPC-DETR的轻量级Transformer解码器和特征融合模块，提升异物检测的鲁棒性。
- 在云边端协同基线中，引入FGL-YOLO的轻量化网络结构和知识蒸馏策略，实现无人机端高效部署。

### Stitching Plan (缝合方案)

- **Baseline**: Cloud-Edge-End Collaboration System with YOLOv5
- **Module B**: 改进YOLOv11的轻量化骨干和注意力机制
- **Module C**: FGL-YOLO的知识蒸馏策略

### 标答 (Ground Truth)

- **领域**: 电力/巡检
- **可行性**: `risky`
- **标准 Baselines**: YOLOv5
- **标准 Datasets**: （无）
- **标准 Repos**: （无）

## R36-094 — 基于SCADA数据的风机叶片结冰诊断研究

- **可行性裁决**: `risky` (分数: 45)
- **可行性理由**: 35篇baseline论文中仅1篇有代码仓库，无公开数据集，且需SCADA数据（硬件依赖），数据获取风险高。
- **复核裁决**: `MINOR_REVISION`
- **领域**: energy\_power
- **方法关键词**: \['SCADA data analysis', 'ice detection']
- **对象关键词**: \['wind turbine blade', 'ice']

### Verified Papers (37 篇)

- **WaveletAE: A Wavelet-enhanced Autoencoder for Wind Turbine Blade Icing Detection** — arxiv
  - URL: <http://arxiv.org/abs/1902.05625v2>
  - Abstract: Wind power, as an alternative to burning fossil fuels, is abundant and inexhaustible. To fully utilize wind power, wind farms are usually located in a...
- **Intelligent wind turbine blade icing detection using supervisory control and data acquisition data and ensemble deep learning** — openalex
- **Detecting Wind Turbine Blade Icing with a Multiscale Long Short-Term Memory Network** — openalex
- **Wind Turbine Blade Icing Diagnosis Using Convolutional LSTM-GRU With Improved African Vultures Optimization** — openalex
- **A novel NMF-DiCCA deep learning method and its application in wind turbine blade icing failure identification** — openalex
- **Wind turbine condition monitoring by the approach of SCADA data analysis** — openalex
- **ResDenIncepNet-CBAM with principal component analysis for wind turbine blade cracking fault prediction with only short time scale SCADA data** — openalex
- **Using SCADA Data for Wind Turbine Condition Monitoring: A Systematic Literature Review** — openalex
- **Intelligent Icing Detection Model of Wind Turbine Blades Based on SCADA data** — arxiv
  - URL: <http://arxiv.org/abs/2101.07914v2>
  - Abstract: Diagnosis of ice accretion on wind turbine blades is all the time a hard nut to crack in condition monitoring of wind farms. Existing methods focus on...
- **Wind Turbine Blade Icing Detection with SCADA Data** — crossref
  - URL: <https://doi.org/10.1109/ccdc55256.2022.10033566>
- ... 等共 37 篇

### Weak Papers (44 篇)

- **Machine learning methods for wind turbine condition monitoring: A review** — openalex
- **A Comprehensive Review on Signal-Based and Model-Based Condition Monitoring of Wind Turbines: Fault Diagnosis and Lifetime Prognosis** — openalex
- **Bridging Data and Diagnostics: A Systematic Review and Case Study on Integrating Trend Monitoring and Change Point Detection for Wind Turbines** — openalex
- **Wind Turbine Blade Breakage Monitoring With Deep Autoencoders** — openalex
- **A Comprehensive Analysis of Wind Turbine Blade Damage** — openalex
- ... 等共 44 篇

### Repos (0 个)

（无）

### Datasets (0 个)

（无）

### Baselines (35 个)

- WaveletAE: A Wavelet-enhanced Autoencoder for Wind Turbine Blade Icing Detection
- Intelligent wind turbine blade icing detection using supervisory control and data acquisition data and ensemble deep learning
- Detecting Wind Turbine Blade Icing with a Multiscale Long Short-Term Memory Network
- Wind Turbine Blade Icing Diagnosis Using Convolutional LSTM-GRU With Improved African Vultures Optimization
- A novel NMF-DiCCA deep learning method and its application in wind turbine blade icing failure identification
- Wind turbine condition monitoring by the approach of SCADA data analysis
- ResDenIncepNet-CBAM with principal component analysis for wind turbine blade cracking fault prediction with only short time scale SCADA data
- Intelligent Icing Detection Model of Wind Turbine Blades Based on SCADA data
- Wind Turbine Blade Icing Detection with SCADA Data
- Wind Turbine Blade Icing Fault Prediction Based on SCADA Data by XGBoost

### Innovation Points (3 个)

- 将PSO-SVM中的粒子群优化特征选择模块与WaveletAE的小波增强自编码器结合，用于风机叶片结冰诊断的特征提取与分类
- 将PSO-SVM中的粒子群优化模块与多尺度LSTM网络结合，优化LSTM超参数以提升结冰诊断性能
- 将PSO-SVM中的SVM分类器模块与卷积LSTM-GRU混合模型结合，替换原分类头以增强结冰分类能力

### Stitching Plan (缝合方案)

- **Baseline**: WaveletAE
- **Module B**: PSO特征选择模块（来自Predicting fan blade icing by using particle swarm optimization and support vector machine algorithm）
- **Module C**: 无

### 标答 (Ground Truth)

- **领域**: 能源装备/SCADA
- **可行性**: `risky`
- **标准 Baselines**: （无）
- **标准 Datasets**: （无）
- **标准 Repos**: （无）

## R36-100 — 基于深度学习的配电设备视觉识别技术研究

- **可行性裁决**: `risky` (分数: 45)
- **可行性理由**: 3篇baseline论文均无代码仓库，且无公开数据集或自建数据集说明；配电设备视觉识别依赖实物硬件（如无人机、巡检机器人），学生获取硬件存在风险；parallel论文虽多但无直接匹配数据集，需自建，周期可能不足。
- **复核裁决**: `MINOR_REVISION`
- **领域**: energy\_power
- **方法关键词**: \['deep learning', 'visual recognition']
- **对象关键词**: \['distribution equipment']

### Verified Papers (7 篇)

- **Distribution Line Equipment and Defect Identification Based on Deep Learning** — openalex
- **Fault Diagnosis Method of Distribution Equipment Based on Hybrid Model of Robot and Deep Learning** — openalex
- **Power distribution equipment and defect identification technology based on deep learning** — openalex
- **Electric Equipment Image Recognition Based on Deep Learning and Random Forest** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/0a7daf546258d467f4542b7ddcb9079f38979fe3>
- **Automatic Fault Diagnosis of Infrared Insulator Images Based on Image Instance Segmentation and Temperature Analysis** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/0a510e5ca8677b9442e20a632b5b6ddd2c9a85d9>
  - Abstract: As an onsite condition monitoring method, an infrared inspection can help to discover and analyze abnormal temperature increases in power equipment. F...
- **Distribution Line Pole Detection and Counting Based on YOLO Using UAV Inspection Line Video** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/3fbda27f6a0ea10e145a87e4ad09b68dd1f4760f>
- **SSD: Single Shot MultiBox Detector** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/4d7a9197433acbfb24ef0e9d0f33ed1699e4a5b0>
  - Abstract: We present a method for detecting objects in images using a single deep neural network. Our approach, named SSD, discretizes the output space of bound...

### Weak Papers (27 篇)

- **Why & When Deep Learning Works: Looking Inside Deep Learnings** — arxiv
- **Semantic-Aware Scene Recognition** — arxiv
- **Saliency for Fine-grained Object Recognition in Domains with Scarce Training Data** — arxiv
- **Deep Learning in Palmprint Recognition-A Comprehensive Survey** — arxiv
- **The Modern Mathematics of Deep Learning** — arxiv
- ... 等共 27 篇

### Repos (0 个)

（无）

### Datasets (2 个)

- **COCO** (source: paper\_title\_heuristic)
- **Pascal VOC** (source: paper\_title\_heuristic)

### Baselines (3 个)

- Distribution Line Equipment and Defect Identification Based on Deep Learning
- Fault Diagnosis Method of Distribution Equipment Based on Hybrid Model of Robot and Deep Learning
- Power distribution equipment and defect identification technology based on deep learning

### Innovation Points (3 个)

- 在基线模型基础上，引入随机森林分类器替换全连接层，提升配电设备分类准确率与鲁棒性。
- 在基线检测框架中集成实例分割模块，对绝缘子等设备进行像素级分割，结合温度分析实现自动故障诊断。
- 将基线单阶段检测器替换为SSD，利用多尺度特征图提升小目标配电设备（如线杆、绝缘子）的检测精度。

### Stitching Plan (缝合方案)

- **Baseline**: Distribution Line Equipment and Defect Identification Based on Deep Learning
- **Module B**: 随机森林分类器（来自Electric Equipment Image Recognition Based on Deep Learning and Random Forest）
- **Module C**: 实例分割与温度分析模块（来自Automatic Fault Diagnosis of Infrared Insulator Images Based on Image Instance Segmentation and Temperature Analysis）

### 标答 (Ground Truth)

- **领域**: 电力/巡检
- **可行性**: `risky`
- **标准 Baselines**: YOLOv5
- **标准 Datasets**: （无）
- **标准 Repos**: （无）

## R38-004 — 基于深度学习的医学图像分割算法研究

- **可行性裁决**: `risky` (分数: 65)
- **可行性理由**: Baseline≥3且有repo，但无公开数据集，需自建医学图像数据，涉及数据合规风险（伦理审批、隐私法规），且硬件依赖GPU集群，学生获取能力存疑。
- **复核裁决**: `MINOR_REVISION`
- **领域**: medical\_ai
- **方法关键词**: \['deep learning']
- **对象关键词**: \['medical image']

### Verified Papers (8 篇)

- **Test-time generative augmentation for medical image segmentation** — arxiv
  - URL: <http://arxiv.org/abs/2406.17608v2>
  - Abstract: Medical image segmentation is critical for clinical diagnosis, treatment planning, and monitoring, yet segmentation models often struggle with uncerta...
- **Deep learning and its application to medical image segmentation** — arxiv
  - URL: <http://arxiv.org/abs/1803.08691v1>
  - Abstract: One of the most common tasks in medical imaging is semantic segmentation. Achieving this segmentation automatically has been an active area of researc...
- **MambaMIM: Pre-training Mamba with State Space Token Interpolation and its Application to Medical Image Segmentation** — arxiv
  - URL: <http://arxiv.org/abs/2408.08070v2>
  - Abstract: Recently, the state space model Mamba has demonstrated efficient long-sequence modeling capabilities, particularly for addressing long-sequence visual...
- **Cross-dimensional transfer learning in medical image segmentation with deep learning** — arxiv
  - URL: <http://arxiv.org/abs/2307.15872v1>
  - Abstract: Over the last decade, convolutional neural networks have emerged and advanced the state-of-the-art in various image analysis and computer vision appli...
- **MIScnn: A Framework for Medical Image Segmentation with Convolutional Neural Networks and Deep Learning** — arxiv
  - URL: <http://arxiv.org/abs/1910.09308v1>
  - Abstract: The increased availability and usage of modern medical imaging induced a strong need for automatic medical image segmentation. Still, current image se...
- **Test-Time Adaptable Neural Networks for Robust Medical Image Segmentation** — arxiv
  - URL: <http://arxiv.org/abs/2004.04668v4>
  - Abstract: Convolutional Neural Networks (CNNs) work very well for supervised learning problems when the training dataset is representative of the variations exp...
- **Learning With Context Feedback Loop for Robust Medical Image Segmentation** — arxiv
  - URL: <http://arxiv.org/abs/2103.02844v1>
  - Abstract: Deep learning has successfully been leveraged for medical image segmentation. It employs convolutional neural networks (CNN) to learn distinctive imag...
- **Uncertainty-aware multi-view co-training for semi-supervised medical image segmentation and domain adaptation** — arxiv
  - URL: <http://arxiv.org/abs/2006.16806v1>
  - Abstract: Although having achieved great success in medical image segmentation, deep learning-based approaches usually require large amounts of well-annotated d...

### Weak Papers (4 篇)

- **TransMorph: Transformer for unsupervised medical image registration** — arxiv
- **Fréchet Radiomic Distance (FRD): A Versatile Metric for Comparing Medical Imaging Datasets** — arxiv
- **A Survey on Active Learning and Human-in-the-Loop Deep Learning for Medical Image Analysis** — arxiv
- **Building medical image classifiers with very limited data using segmentation networks** — arxiv

### Repos (12 个)

- **?**
  - URL: <https://github.com/black0017/MedicalZooPytorch>
- **?**
  - URL: <https://github.com/microsoft/InnerEye-DeepLearning>
- **?**
  - URL: <https://github.com/frankkramer-lab/MIScnn>
- **?**
  - URL: <https://github.com/marc-gorriz/CEAL-Medical-Image-Segmentation>
- **?**
  - URL: <https://github.com/Bala93/Multi-task-deep-network>
- **?**
  - URL: <https://github.com/HiLab-git/MIDeepSeg>
- **?**
  - URL: <https://github.com/davidiommi/Pytorch--3D-Medical-Images-Segmentation--SALMON>
- **?**
  - URL: <https://github.com/AryaKoureshi/Brain-tumor-detection>
- **?**
  - URL: <https://github.com/xiaofang007/CTO>
- **?**
  - URL: <https://github.com/LIVIAETS/MedicalImageSegmentation>

### Datasets (0 个)

（无）

### Baselines (3 个)

- Deep learning and its application to medical image segmentation
- Cross-dimensional transfer learning in medical image segmentation with deep learning
- MIScnn: A Framework for Medical Image Segmentation with Convolutional Neural Networks and Deep Learning

### Innovation Points (1 个)

- 在Deep learning and its application to medical image segmentation基础上借鉴Test-time generative augmentation for medical image segmentation的模块

### Stitching Plan (缝合方案)

- **Baseline**: Deep learning and its application to medical image segmentation
- **Module B**: Test-time generative augmentation for medical image segmentation
- **Module C**:

## R38-005 — 基于深度学习的钢材表面缺陷检测算法研究

- **可行性裁决**: `feasible` (分数: 88)
- **可行性理由**: baseline≥3（5篇），有2个数据集和12个代码仓库，证据链完整。无硬件依赖或数据合规风险，领域成熟。
- **复核裁决**: `ACCEPT`
- **领域**: vision\_2d
- **方法关键词**: \['deep learning']
- **对象关键词**: \['steel surface defect']

### Verified Papers (38 篇)

- **Dual attention deep learning network for automatic steel surface defect segmentation** — openalex
- **TLU-Net: A Deep Learning Approach for Automatic Steel Surface Defect Detection** — openalex
- **An End-to-End Steel Surface Defect Detection Approach via Fusing Multiple Hierarchical Features** — openalex
- **A deep-learning-based approach for fast and robust steel surface defects classification** — openalex
- **A New Steel Defect Detection Algorithm Based on Deep Learning** — openalex
- **DCC-CenterNet: A rapid detection method for steel surface defects** — openalex
- **A deep learning model for steel surface defect detection** — openalex
- **Automatic Detection and Classification of Steel Surface Defect Using Deep Convolutional Neural Networks** — openalex
- **Deep Learning-Based Defect Detection System in Steel Sheet Surfaces** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/8193f165a00525b8d99a7c432b81f059eb89d76d>
  - Abstract: Steel is one of the most important building materials of modern times and the production process of flat sheet steel is complicated. Before shipping o...
- **CSG-YOLO: a model for detecting minor and irregular steel surface defects based on deformable convolution and cross-layer fusion** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/29b6bab03fb874c08f3c8edade09a11d84b20703>
- ... 等共 38 篇

### Weak Papers (52 篇)

- **State of the Art in Defect Detection Based on Machine Vision** — openalex
- **Using Deep Learning to Detect Defects in Manufacturing: A Comprehensive Survey and Current Challenges** — openalex
- **Steel Surface Defect Recognition: A Survey** — openalex
- **Recent advances and applications of deep learning methods in materials science** — openalex
- **Automated Visual Defect Detection for Flat Steel Surface: A Survey** — semantic\_scholar
- ... 等共 52 篇

### Repos (12 个)

- **?**
  - URL: <https://github.com/5rijan/Steel-Defect-Detection-A-Combined-U-Net-and-CNN-Approach>
- **?**
  - URL: <https://github.com/AnuradhYarasani/Quality-Assurance-within-the-Automobile-Industry>
- **?**
  - URL: <https://github.com/kjdnl/the-project-of-steel-plate-classification-with-transferL>
- **?**
  - URL: <https://github.com/QQ767172261/Deep-Learning-NEUDET-steel-surface-defect-task-detection-based-on-YOLOv5-adding-CFPNet-dynamic-convo>
- **?**
  - URL: <https://github.com/papaicr7/Steel-Surface-Defect-Detection-Using-Deep-Learning-Algorithm>
- **?**
  - URL: <https://github.com/vkajith/Steel-Defect-Detection--Using-Unet>
- **?**
  - URL: <https://github.com/aaburakhia/steel-defect-detection>
- **?**
  - URL: <https://github.com/JerryInCanada/Deep-Learning-Based-Automatic-Defect-Detection-System-for-Steel>
- **?**
  - URL: <https://github.com/Jellal-17/Steel-Defect-Detection>
- **?**
  - URL: <https://github.com/latasarad-gif/Steel-Sheet-Defect-Detection>

### Datasets (2 个)

- **NEU-DET** (source: paper\_title\_heuristic)
- **GC10-DET** (source: paper\_title\_heuristic)

### Baselines (35 个)

- Dual attention deep learning network for automatic steel surface defect segmentation
- TLU-Net: A Deep Learning Approach for Automatic Steel Surface Defect Detection
- An End-to-End Steel Surface Defect Detection Approach via Fusing Multiple Hierarchical Features
- A deep-learning-based approach for fast and robust steel surface defects classification
- A New Steel Defect Detection Algorithm Based on Deep Learning
- DCC-CenterNet: A rapid detection method for steel surface defects
- A deep learning model for steel surface defect detection
- Automatic Detection and Classification of Steel Surface Defect Using Deep Convolutional Neural Networks
- Deep Learning-Based Defect Detection System in Steel Sheet Surfaces
- CSG-YOLO: a model for detecting minor and irregular steel surface defects based on deformable convolution and cross-layer fusion

### Innovation Points (3 个)

- 在TLU-Net的编码器-解码器结构中，引入Fuzzy Logic-Based Hybrid Deep Learning System的模糊逻辑模块，用于动态调整特征融合权重，提升对边缘缺陷的检测鲁棒性。
- 在Dual Attention Deep Learning Network中，集成Generation on Demand的缺陷合成模块，在训练时动态生成位置和形态可控的缺陷样本，解决数据不平衡问题。
- 在An End-to-End Steel Surface Defect Detection Approach via Fusing Multiple Hierarchical Features中，替换其简单的特征融合方式为模糊逻辑动态融合，增强多尺度特征的非线性组合能力。

### Stitching Plan (缝合方案)

- **Baseline**: TLU-Net
- **Module B**: Fuzzy Logic-Based Hybrid Deep Learning System
- **Module C**: Generation on Demand

### 标答 (Ground Truth)

- **领域**: 工业缺陷
- **可行性**: `feasible`
- **标准 Baselines**: YOLOv5
- **标准 Datasets**: NEU-DET
- **标准 Repos**: ultralytics/yolov5

## R38-006 — 基于深度学习的三维物体重建技术研究

- **可行性裁决**: `risky` (分数: 55)
- **可行性理由**: 仅1篇baseline论文且无专用数据集，需自建3D数据或依赖合成数据，存在数据获取风险。并行论文多涉及医学或流体领域，与3D重建不直接相关。12个代码仓库可部分复用，但证据链薄弱。
- **复核裁决**: `MINOR_REVISION`
- **领域**: vision\_3d
- **方法关键词**: \['deep learning']
- **对象关键词**: \['3D object']

### Verified Papers (6 篇)

- **Learning with Noisy Ground Truth: From 2D Classification to 3D Reconstruction** — arxiv
  - URL: <http://arxiv.org/abs/2406.15982v1>
  - Abstract: Deep neural networks has been highly successful in data-intense computer vision applications, while such success relies heavily on the massive and cle...
- **Deep learning observables in computational fluid dynamics** — arxiv
  - URL: <http://arxiv.org/abs/1903.03040v2>
  - Abstract: Many large scale problems in computational fluid dynamics such as uncertainty quantification, Bayesian inversion, data assimilation and PDE constraine...
- **DILIE: Deep Internal Learning for Image Enhancement** — arxiv
  - URL: <http://arxiv.org/abs/2012.06469v1>
  - Abstract: We consider the generic deep image enhancement problem where an input image is transformed into a perceptually better-looking image. Recent methods fo...
- **Physics-informed self-supervised deep learning reconstruction for accelerated first-pass perfusion cardiac MRI** — arxiv
  - URL: <http://arxiv.org/abs/2301.02033v1>
  - Abstract: First-pass perfusion cardiac magnetic resonance (FPP-CMR) is becoming an essential non-invasive imaging method for detecting deficits of myocardial bl...
- **Software Implementation of the Krylov Methods Based Reconstruction for the 3D Cone Beam CT Operator** — arxiv
  - URL: <http://arxiv.org/abs/2110.13526v1>
  - Abstract: Krylov subspace methods are considered a standard tool to solve large systems of linear algebraic equations in many scientific disciplines such as ima...
- **Deep MRI Reconstruction: Unrolled Optimization Algorithms Meet Neural Networks** — arxiv
  - URL: <http://arxiv.org/abs/1907.11711v1>
  - Abstract: Image reconstruction from undersampled k-space data has been playing an important role for fast MRI. Recently, deep learning has demonstrated tremendo...

### Weak Papers (0 篇)

（无）

### Repos (12 个)

- **?**
  - URL: <https://github.com/dfuentes-uah/Deep-Shape-from-Template>
- **?**
  - URL: <https://github.com/hamidlaga/3DObjectReconstruction-Survey>
- **?**
  - URL: <https://github.com/C-H-Chien/Database-Assisted-Object-Retrieval-3D-Room-Reconstruction>
- **?**
  - URL: <https://github.com/prateek0221/3-d_OBJECT_RECONSTRUCTION>
- **?**
  - URL: <https://github.com/JemuelStanley47/Learning-Shape-representations-DeepSDF->
- **?**
  - URL: <https://github.com/meghasv09/UpsamplingofPointclouds>
- **?**
  - URL: <https://github.com/Geshna-B/Markerless-AR-Based-Interactive-Anatomy-Learning>
- **?**
  - URL: <https://github.com/CliveKBinu/Tomogorams_NN>
- **?**
  - URL: <https://github.com/AngelDario/3D_Object_Reconstruction_DL>
- **?**
  - URL: <https://github.com/Vijii444/3D-Object-Reconstruction-From-2D-image-Using-Deep-learning>

### Datasets (0 个)

（无）

### Baselines (1 个)

- Learning with Noisy Ground Truth: From 2D Classification to 3D Reconstruction

### Innovation Points (3 个)

- 在三维重建中引入物理信息约束，利用流体动力学中的物理先验知识增强重建的物理一致性
- 将MRI重建中的展开优化算法引入3D重建，通过迭代网络结构提升重建质量
- 利用Krylov子空间方法加速3D重建中的线性系统求解，提高计算效率

### Stitching Plan (缝合方案)

- **Baseline**: Learning with Noisy Ground Truth: From 2D Classification to 3D Reconstruction
- **Module B**: Deep learning observables in computational fluid dynamics
- **Module C**: DILIE: Deep Internal Learning for Image Enhancement

## R38-008 — 基于机器视觉的PCB缺陷检测系统研究

- **可行性裁决**: `feasible` (分数: 88)
- **可行性理由**: Baseline论文14篇（含5篇直接相关），有3个代码仓库和1个公开数据集，证据链完整。领域风险低：PCB缺陷检测依赖公开数据集（如DeepPCB），无需实物硬件，无数据合规问题。
- **复核裁决**: `ACCEPT`
- **领域**: vision\_2d
- **方法关键词**: \['machine vision']
- **对象关键词**: \['PCB', 'printed circuit board']

### Verified Papers (45 篇)

- **Machine vision based defect detection approach using image processing** — openalex
- **PCB Defect Detection Based on Deep Learning Algorithm** — openalex
- **Printed Circuit Board Defect Detection Using Deep Learning via A Skip-Connected Convolutional Autoencoder** — openalex
- **ChangeChip: A Reference-Based Unsupervised Change Detection for PCB Defect Detection** — arxiv
  - URL: <http://arxiv.org/abs/2109.05746v1>
  - Abstract: The usage of electronic devices increases, and becomes predominant in most aspects of life. Surface Mount Technology (SMT) is the most common industri...
- **Detecting Manufacturing Defects in PCBs via Data-Centric Machine Learning on Solder Paste Inspection Features** — arxiv
  - URL: <http://arxiv.org/abs/2309.03113v1>
  - Abstract: Automated detection of defects in Printed Circuit Board (PCB) manufacturing using Solder Paste Inspection (SPI) and Automated Optical Inspection (AOI)...
- **YOLO-pdd: A Novel Multi-scale PCB Defect Detection Method Using Deep Representations with Sequential Images** — arxiv
  - URL: <http://arxiv.org/abs/2407.15427v1>
  - Abstract: With the rapid growth of the PCB manufacturing industry, there is an increasing demand for computer vision inspection to detect defects during product...
- **Machine vision based online detection of PCB defect** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/49a45b0cb13c5a04ef9dab6067845d43df5e7ed4>
  - Abstract: Abstract The traditional PCB defect on-line detection has the problems of long detection time and poor accuracy of detection results. Therefore, a key...
- **Detection of PCB Surface Defects With Improved Faster-RCNN and Feature Pyramid Network** — openalex
- **TDD‐net: a tiny defect detection network for printed circuit boards** — openalex
- **Detection of Bare PCB Defects by Image Subtraction Method using Machine Vision** — openalex
- ... 等共 45 篇

### Weak Papers (19 篇)

- **Review of vision-based defect detection research and its perspectives for printed circuit board** — openalex
- **FPIC: A Novel Semantic Dataset for Optical PCB Assurance** — arxiv
- **State of the Art in Defect Detection Based on Machine Vision** — openalex
- **A Comprehensive Review of Deep Learning-Based PCB Defect Detection** — semantic\_scholar
- **Enhanced PCB defect detection via HSA-RTDETR on RT-DETR** — semantic\_scholar
- ... 等共 19 篇

### Repos (3 个)

- **?**
  - URL: <https://github.com/Ayush9284/pcb_defect_detection>
- **?**
  - URL: <https://github.com/s-acear/pcb_defect_detection>
- **?**
  - URL: <https://github.com/Rishabose/Automated-PCB-Defect-Detection-and-Decision-Routing-System-using-Machine-Vision->

### Datasets (1 个)

- **NEU-DET** (source: paper\_title\_heuristic)

### Baselines (14 个)

- Machine vision based defect detection approach using image processing
- Machine vision based online detection of PCB defect
- Detection of Bare PCB Defects by Image Subtraction Method using Machine Vision
- Analysis of Key Techniques of PCB Defect Detection Based on Machine Vision
- Machine Vision-Based PCB Defect Detection Method
- Research on PCB solder joint defect detection method based on machine vision
- Development of SBC based machine-vision system for PCB board assembly Automatic Optical Inspection
- A Smart Machine Vision System for PCB Inspection
- Parallel processing machine vision system for bare PCB inspection
- Misalignment inspection of multilayer PCBs with an automated X-ray machine vision system

### Innovation Points (3 个)

- 结合传统图像处理与深度学习特征提取，提出一种混合PCB缺陷检测方法，利用图像减法定位缺陷区域，再通过轻量级CNN进行精确分类。
- 在传统机器视觉检测流程中引入基于参考图像的无监督变化检测方法，提升对微小缺陷的敏感度。
- 将传统图像处理特征与深度学习多尺度检测结合，利用YOLO-pdd的多尺度表示能力提升缺陷检测精度。

### Stitching Plan (缝合方案)

- **Baseline**: Detection of Bare PCB Defects by Image Subtraction Method using Machine Vision
- **Module B**: Skip-Connected Convolutional Autoencoder（来自Printed Circuit Board Defect Detection Using Deep Learning via A Skip-Connected Convolutional Autoencoder）
- **Module C**: 图像减法与差分图像生成（来自baseline）

### 标答 (Ground Truth)

- **领域**: 工业缺陷/PCB
- **可行性**: `feasible`
- **标准 Baselines**: YOLOv5
- **标准 Datasets**: （无）
- **标准 Repos**: ultralytics/yolov5

## R38-009 — 点云的三维重建与纹理映射

- **可行性裁决**: `risky` (分数: 55)
- **可行性理由**: Baseline仅1篇有repo，其余5篇无代码；数据集仅1个且未明确公开；点云重建依赖硬件（如深度相机），学生获取能力未知；无降级方案。
- **复核裁决**: `MINOR_REVISION`
- **领域**: vision\_3d
- **方法关键词**: \['point cloud reconstruction', 'texture mapping']
- **对象关键词**: \['point cloud']

### Verified Papers (31 篇)

- **$PC^2$: Projection-Conditioned Point Cloud Diffusion for Single-Image 3D Reconstruction** — arxiv
  - URL: <http://arxiv.org/abs/2302.10668v2>
  - Abstract: Reconstructing the 3D shape of an object from a single RGB image is a long-standing and highly challenging problem in computer vision. In this paper, ...
- **From point cloud to surface: the modeling and visualization problem** — openalex
- **Multiview Geometry for Texture Mapping 2D Images Onto 3D Range Data** — openalex
- **Parametric as-built model generation of complex shapes from point clouds** — openalex
- **3D Modeling of Building Indoor Spaces and Closed Doors from Imagery and Point Clouds** — openalex
- **Automatic reconstruction of industrial installations: Using point clouds and images** — openalex
- **Meshing Point Clouds Using Spherical Parameterization** — openalex
- **Multiview 3D sensing and analysis for high quality point cloud reconstruction** — openalex
- **A Model Development Approach Based on Point Cloud Reconstruction and Mapping Texture Enhancement** — openalex
- **3D-ReConstnet: A Single-View 3D-Object Point Cloud Reconstruction Network** — openalex
- ... 等共 31 篇

### Weak Papers (62 篇)

- **Reconstruction by Generation: 3D Multi-Object Scene Reconstruction from Sparse Observations** — arxiv
- **Structure-Aware Sparse-View X-ray 3D Reconstruction** — arxiv
- **Learning with Noisy Ground Truth: From 2D Classification to 3D Reconstruction** — arxiv
- **Extreme 3D Face Reconstruction: Seeing Through Occlusions** — arxiv
- **Pointshop 3D** — openalex
- ... 等共 62 篇

### Repos (0 个)

（无）

### Datasets (1 个)

- **AID** (source: paper\_title\_heuristic)

### Baselines (6 个)

- From point cloud to surface: the modeling and visualization problem
- Multiview Geometry for Texture Mapping 2D Images Onto 3D Range Data
- Multiview 3D sensing and analysis for high quality point cloud reconstruction
- A Model Development Approach Based on Point Cloud Reconstruction and Mapping Texture Enhancement
- An automated and accurate procedure for texture mapping from images
- Color map optimization for 3D reconstruction with consumer depth cameras

### Innovation Points (5 个)

- 在点云重建中引入投影条件扩散模型，从单张RGB图像生成稀疏点云，替代传统多视图几何重建方法
- 结合参数化建模与纹理映射，从点云自动生成参数化模型并映射纹理，提升复杂形状的纹理质量
- 利用球面参数化方法对点云进行网格化，再结合图像纹理映射，解决非流形点云的网格生成问题
- 融合室内场景重建与闭合门检测，从点云和图像中自动重建室内空间并映射纹理，提升场景级纹理一致性
- 结合工业设施自动重建与纹理增强，从点云和图像中自动生成工业模型并映射增强纹理

### Stitching Plan (缝合方案)

- **Baseline**: From point cloud to surface: the modeling and visualization problem
- **Module B**: 条件去噪扩散过程（来自$PC^2$: Projection-Conditioned Point Cloud Diffusion for Single-Image 3D Reconstruction）
- **Module C**: 球面参数化网格生成（来自Meshing Point Clouds Using Spherical Parameterization）

## R38-011 — 基于深度学习的锂电池表面缺陷检测方法研究

- **可行性裁决**: `feasible` (分数: 88)
- **可行性理由**: 5篇baseline均有repo，1个公开数据集，代码可复现；无硬件依赖或数据合规风险，证据链完整。
- **复核裁决**: `ACCEPT`
- **领域**: vision\_2d
- **方法关键词**: \['deep learning', 'convolutional neural network', 'object detection']
- **对象关键词**: \['lithium battery surface', 'defect']

### Verified Papers (16 篇)

- **Deep learning-assisted real-time defect detection and process control for electrode manufacturing of lithium-ion battery cells** — core
  - URL: <https://core.ac.uk/download/661286778.pdf>
  - Abstract: Detecting and preventing defects on electrode surfaces during the manufacturing of lithium-ion battery cells remains a crucial challenge to avoid furt...
- **Deep-Learning-Based Lithium Battery Defect Detection via Cross-Domain Generalization** — core
  - URL: <https://core.ac.uk/download/651400826.pdf>
  - Abstract: This research addresses the critical challenge of classifying surface defects in lithium electronic components, crucial for ensuring the reliability a...
- **A comparison of transformer and CNN-based object detection models for surface defects on Li-Ion Battery Electrodes** — core
  - URL: <https://core.ac.uk/download/648519761.pdf>
  - Abstract: Deep learning-based defect detection approaches offer great potential for end-to-end surface defect detection. After the prevalent Convolutional Neura...
- **LITHIUM BATTERY SURFACE DEFECT DETECTION BASED ON REINFORCEMENT ADVERSARIAL LEARNING** — crossref
  - URL: <https://doi.org/10.2316/j.2026.206-1330>
- **SDHNet: a hybrid auxiliary fusion network for lithium battery surface defect detection** — crossref
  - URL: <https://doi.org/10.1016/j.measurement.2025.118324>
- **Surface Defect Image Classification of Lithium Battery Pole Piece Based on Deep Learning** — crossref
  - URL: <https://doi.org/10.1587/transinf.2023edp7058>
- **A Lightweight Neural Network for Surface Defect Detection in Lithium Battery Electrode Sheets** — crossref
  - URL: <https://doi.org/10.23919/ccc64809.2025.11179703>
- **Research on Surface Defect Detection Algorithm of Lithium Battery Based on Multi-Modal Deep Learning** — crossref
  - URL: <https://doi.org/10.62517/jes.202602105>
  - Abstract: <jats:p>With the rapid advancement of new energy technologies, lithium-ion batteries as core energy storage components have been widely adopted in ele...
- **Multi-task Deep Learning Based Defect Detection For Lithium Battery Tabs** — crossref
  - URL: <https://doi.org/10.1109/cac57257.2022.10054847>
- **Negative Sample Learning based Surface Defect Detection for Lithium Battery Tabs** — crossref
  - URL: <https://doi.org/10.1109/aipip66876.2025.11299242>
- ... 等共 16 篇

### Weak Papers (28 篇)

- **Oriented object detection in optical remote sensing images using deep learning: a survey** — arxiv
- **A New Benchmark Dataset for Texture Image Analysis and Surface Defect Detection** — arxiv
- **DeepInspect: An AI-Powered Defect Detection for Manufacturing Industries** — arxiv
- **Deep Learning Pipeline for Defect Detection** — core
- **Online Metallic Surface Defect Detection Using Deep Learning** — None
- ... 等共 28 篇

### Repos (1 个)

- **?**
  - URL: <https://github.com/da62b207/LiIonDefDet->

### Datasets (1 个)

- **COCO** (source: paper\_title\_heuristic)

### Baselines (10 个)

- Deep learning-assisted real-time defect detection and process control for electrode manufacturing of lithium-ion battery cells
- Deep-Learning-Based Lithium Battery Defect Detection via Cross-Domain Generalization
- SDHNet: a hybrid auxiliary fusion network for lithium battery surface defect detection
- Surface Defect Image Classification of Lithium Battery Pole Piece Based on Deep Learning
- A Lightweight Neural Network for Surface Defect Detection in Lithium Battery Electrode Sheets
- Research on Surface Defect Detection Algorithm of Lithium Battery Based on Multi-Modal Deep Learning
- Multi-task Deep Learning Based Defect Detection For Lithium Battery Tabs
- MSA-YOLO: Multi-scale Adaptive Network for surface defect detection of cylindrical lithium battery
- Enhanced YOLOv11 for button cell battery defect detection: Leveraging local channel semantic guidance and multi-scale interaction
- Research on Burr Classification of Battery Pole Pieces Based on Improved ResNet

### Innovation Points (3 个)

- 在baseline的CNN检测框架中，引入parallel论文中的Transformer模块替换部分卷积层，以增强对复杂缺陷的全局特征提取能力。
- 在baseline的缺陷检测流程中，缝合parallel论文中的负样本学习模块，以提升对罕见缺陷的识别能力。
- 在baseline的轻量级网络中，融合parallel论文中的多特征增强Transformer，以在保持低计算量的同时提升检测精度。

### Stitching Plan (缝合方案)

- **Baseline**: Deep learning-assisted real-time defect detection and process control for electrode manufacturing of lithium-ion battery cells
- **Module B**: A comparison of transformer and CNN-based object detection models for surface defects on Li-Ion Battery Electrodes
- **Module C**: Negative Sample Learning based Surface Defect Detection for Lithium Battery Tabs

## R38-013 — 基于机器视觉的板类堆叠零件分拣系统研究

- **可行性裁决**: `risky` (分数: 55)
- **可行性理由**: 仅1篇baseline论文且有repo，但无公开数据集，需自建堆叠零件数据集；涉及机器人分拣硬件（相机、机械臂），存在硬件获取风险；无降级方案。
- **复核裁决**: `MINOR_REVISION`
- **领域**: vision\_3d
- **方法关键词**: \['machine vision', 'object detection', 'pose estimation']
- **对象关键词**: \['board-like stacked parts', 'stacked parts']

### Verified Papers (4 篇)

- **Estimation of Robot Motion Parameters Based on Functional Consistency for Randomly Stacked Parts** — crossref
  - URL: <https://doi.org/10.5220/0011683500003417>
- **Enhancing small parcel sorting accuracy: Robot machine vision in stacking target image experiment** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/7401b2b2e8ad645f04f087d8407fbefe502911f7>
  - Abstract: As robots are increasingly being used in various fields of production and daily life, research in this area has become a hot topic among researchers. ...
- **A Pose Estimation Approach Based on Keypoints Detection for Robotic Bin-picking Application** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/7a0106542a71dab4683060680a717abdc22f46f9>
  - Abstract: Robotic bin-picking is a fundamental yet trouble-some task in robot autonomous manufacturing applications such as industrial parts feeding, assembling...
- **Robotic Sorting of Mechanical and Electrical Parts: An Autonomous Vision-Based Approach in a Practical Case Study** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/bf818319c7f2d0c5dc27744c33763c66b0860fce>
  - Abstract: In today’s industrial landscape, automation has become increasingly vital, particularly in the deployment of robots for tasks such as sorting machine ...

### Weak Papers (26 篇)

- **Automatic Sorting Machine Based on Vision Inspection** — None
- **On-Line Inspection and Sorting System for Mechanical Parts Based on Machine Vision** — crossref
- **Machine vision is used for package sorting** — crossref
- **A machine vision system for inspecting mechanical parts** — crossref
- **Research on Automatic Workpiece Sorting System Based on Machine Vision** — semantic\_scholar
- ... 等共 26 篇

### Repos (0 个)

（无）

### Datasets (0 个)

（无）

### Baselines (1 个)

- A Pose Estimation Approach Based on Keypoints Detection for Robotic Bin-picking Application

### Innovation Points (3 个)

- 在基于关键点检测的位姿估计方法中，引入功能一致性约束来优化堆叠零件的位姿估计，提高遮挡场景下的分拣成功率。
- 在关键点检测位姿估计的基础上，融合堆叠目标图像增强模块，提升小零件在堆叠场景下的检测精度。
- 将关键点检测位姿估计与自主视觉分拣策略结合，实现从位姿估计到抓取排序的完整系统。

### Stitching Plan (缝合方案)

- **Baseline**: Keypoint-based Pose Estimation Network
- **Module B**: 功能一致性损失函数（来自Estimation of Robot Motion Parameters Based on Functional Consistency for Randomly Stacked Parts）
- **Module C**: 堆叠目标图像增强模块（来自Enhancing small parcel sorting accuracy: Robot machine vision in stacking target image experiment）

## R38-014 — 基于生成对抗网络的织物缺陷检测算法研究

- **可行性裁决**: `risky` (分数: 65)
- **可行性理由**: Baseline有5篇且4篇有repo，方法可复现；但无公开数据集，自建织物缺陷数据集需大量实物采集和标注，存在硬件依赖风险（需相机、光源、织物样本），且无降级方案。
- **复核裁决**: `MINOR_REVISION`
- **领域**: vision\_2d
- **方法关键词**: \['generative adversarial network', 'GAN']
- **对象关键词**: \['fabric', 'textile']

### Verified Papers (26 篇)

- **Unsupervised fabric defect detection based on a deep convolutional generative adversarial network** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/dd8502990c6a7c40e95237be1f22c0fc3ac64e39>
  - Abstract: Detecting and locating surface defects in textured materials is a crucial but challenging problem due to factors such as texture variations and lack o...
- **Attention-based Feature Fusion Generative Adversarial Network for yarn-dyed fabric defect detection** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/31c7cf6f678c03ace96d35471af2161ea346311f>
  - Abstract: Defects on the surface of yarn-dyed fabrics are one of the important factors affecting the quality of fabrics. Defect detection is the core link of qu...
- **Conditional image-to-image translation generative adversarial network (cGAN) for fabric defect data augmentation** — openalex
- **Multistage GAN for Fabric Defect Detection** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/c992f74eb6ceddd73eb29a5113d04140484fb8fd>
  - Abstract: Fabric defect detection is an intriguing but challenging topic. Many methods have been proposed for fabric defect detection, but these methods are sti...
- **DeepInspect: An AI-Powered Defect Detection for Manufacturing Industries** — arxiv
  - URL: <http://arxiv.org/abs/2311.03725v2>
  - Abstract: Utilizing Convolutional Neural Networks (CNNs), Recurrent Neural Networks (RNNs), and Generative Adversarial Networks (GANs), our system introduces an...
- **FabricGAN: an enhanced generative adversarial network for data augmentation and improved fabric defect detection** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/9ff76f112366b5db2287ab93ff1f0490e44df19a>
  - Abstract: When deep learning is applied to intelligent textile defect detection, the insufficient training data may result in low accuracy and poor adaptability...
- **Defect detection of fabrics With Generative Adversarial Network Based flaws modeling** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/16bc49d1d7a92dba92b4757adce98e12af0eb523>
  - Abstract: Defect feature extraction is mainly problem of detect detection in fabrics. There are many traditional defect detection methods in it. But deep learni...
- **A contrastive learning‐based attention generative adversarial network for defect detection in colour‐patterned fabric** — openalex
- **Masked contrastive generative adversarial network for defect detection of yarn-dyed fabric** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/e1ad633717993dbdf29a7f5e0b8b3a1d70d35018>
- **Image restoration fabric defect detection based on the dual generative adversarial network patch model** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/755c57dad3f41a9e173988e65f642a902cda2098>
  - Abstract: The training of supervised learning requires the use of ground truth, which is difficult to obtain in large quantities in production practice. Unsuper...
- ... 等共 26 篇

### Weak Papers (26 篇)

- **TransferD2: Automated Defect Detection Approach in Smart Manufacturing using Transfer Learning Techniques** — arxiv
- **Quaternion Generative Adversarial Networks** — arxiv
- **Automatic Defect Detection of Print Fabric Using Convolutional Neural Network** — arxiv
- **A Cascaded Zoom-In Network for Patterned Fabric Defect Detection** — arxiv
- **FashionGAN: Display your fashion design using Conditional Generative Adversarial Nets** — openalex
- ... 等共 26 篇

### Repos (0 个)

（无）

### Datasets (0 个)

（无）

### Baselines (22 个)

- Unsupervised fabric defect detection based on a deep convolutional generative adversarial network
- Attention-based Feature Fusion Generative Adversarial Network for yarn-dyed fabric defect detection
- Conditional image-to-image translation generative adversarial network (cGAN) for fabric defect data augmentation
- Multistage GAN for Fabric Defect Detection
- DeepInspect: An AI-Powered Defect Detection for Manufacturing Industries
- FabricGAN: an enhanced generative adversarial network for data augmentation and improved fabric defect detection
- Defect detection of fabrics With Generative Adversarial Network Based flaws modeling
- A contrastive learning‐based attention generative adversarial network for defect detection in colour‐patterned fabric
- Masked contrastive generative adversarial network for defect detection of yarn-dyed fabric
- Image restoration fabric defect detection based on the dual generative adversarial network patch model

### Innovation Points (3 个)

- 在基线DCGAN的生成器中引入注意力特征融合模块，以增强对织物纹理和缺陷区域的关注，提升重建质量。
- 利用条件GAN进行数据增强，生成多样化的缺陷样本，以缓解缺陷样本稀缺问题，并用于训练基线DCGAN。
- 在基线DCGAN中引入多阶段生成与判别机制，逐步细化缺陷检测结果，提高对微小缺陷的敏感度。

### Stitching Plan (缝合方案)

- **Baseline**: DCGAN（Unsupervised fabric defect detection based on a deep convolutional generative adversarial network）
- **Module B**: 注意力特征融合模块（来自Attention-based Feature Fusion GAN）
- **Module C**: 多尺度特征对比（来自Multistage GAN）

### 标答 (Ground Truth)

- **领域**: 工业缺陷/织物
- **可行性**: `risky`
- **标准 Baselines**: GAN
- **标准 Datasets**: （无）
- **标准 Repos**: （无）

## R38-018 — 基于深度学习的三维点云补全方法研究

- **可行性裁决**: `feasible` (分数: 88)
- **可行性理由**: Baseline论文12篇，其中4篇有repo，2个公开数据集（如ShapeNet、ModelNet），证据链完整。无硬件依赖或数据合规风险，领域成熟。
- **复核裁决**: `ACCEPT`
- **领域**: vision\_3d
- **方法关键词**: \['deep learning', 'point cloud completion']
- **对象关键词**: \['point cloud']

### Verified Papers (17 篇)

- **Point Cloud Completion of Plant Leaves under Occlusion Conditions Based on Deep Learning** — openalex
- **Deep learning-based point cloud completion for MEP components** — openalex
- **Deep-learning-based point cloud completion methods: A review** — openalex
- **Enhancing Performance of Point Cloud Completion Networks with Consistency Loss** — arxiv
  - URL: <http://arxiv.org/abs/2410.07298v3>
  - Abstract: Point cloud completion networks are conventionally trained to minimize the disparities between the completed point cloud and the ground-truth counterp...
- **Cascaded Refinement Network for Point Cloud Completion with Self-supervision** — arxiv
  - URL: <http://arxiv.org/abs/2010.08719v3>
  - Abstract: Point clouds are often sparse and incomplete, which imposes difficulties for real-world applications. Existing shape completion methods tend to genera...
- **Comprehensive Review of Deep Learning-Based 3D Point Cloud Completion Processing and Analysis** — openalex
- **A deep learning framework for road marking extraction, classification and completion from mobile laser scanning point clouds** — openalex
- **Growth parameter acquisition and geometric point cloud completion of lettuce** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/8c883cc143002a9bfbe83e8a8d174bf6eb2c248f>
  - Abstract: The plant factory is a form of controlled environment agriculture (CEA) which is offers a promising solution to the problem of food security worldwide...
- **Unsupervised 3D Shape Completion through GAN Inversion** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/99f2cadcaed68ad07d5377d15c7af8a5422af680>
  - Abstract: Most 3D shape completion approaches rely heavily on partial-complete shape pairs and learn in a fully super-vised manner. Despite their impressive per...
- **Variational Relational Point Completion Network** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/34e170f868551d35788099ce02c3c2d03e06f0d5>
  - Abstract: Real-scanned point clouds are often incomplete due to viewpoint, occlusion, and noise. Existing point cloud completion methods tend to generate global...
- ... 等共 17 篇

### Weak Papers (29 篇)

- **Review: Deep Learning on 3D Point Clouds** — openalex
- **Learn to Accumulate Evidence from All Training Samples: Theory and Practice** — arxiv
- **The Modern Mathematics of Deep Learning** — arxiv
- **Deep Learning for 3D Point Clouds: A Survey** — arxiv
- **Dynamic Graph CNN for Learning on Point Clouds** — openalex
- ... 等共 29 篇

### Repos (9 个)

- **?**
  - URL: <https://github.com/Manojbhat09/Sane-annotation-shape-complete>
- **?**
  - URL: <https://github.com/xiarobin/InceptionFormer>
- **?**
  - URL: <https://github.com/ark1234/CP-Net>
- **?**
  - URL: <https://github.com/fhuang80/TC-Net>
- **?**
  - URL: <https://github.com/lorenzo-delsignore/pointclouds-search-engine>
- **?**
  - URL: <https://github.com/I2S9/SparseLIDAR-Completion>
- **?**
  - URL: <https://github.com/codedbyankit/3D-Scene-Completion-with-PointNet-Autoencoder>
- **?**
  - URL: <https://github.com/abq2904/6d-object-pose-estimation-using-maskrcnn-and-point-cloud-completion>
- **?**
  - URL: <https://github.com/GIKI-AI33-FYP/MOSAIC-Multimodal-Open-Source-Archaeological-Intelligent-Completion>

### Datasets (2 个)

- **ShapeNet** (source: paper\_title\_heuristic)
- **KITTI** (source: paper\_title\_heuristic)

### Baselines (12 个)

- Point Cloud Completion of Plant Leaves under Occlusion Conditions Based on Deep Learning
- Deep learning-based point cloud completion for MEP components
- Enhancing Performance of Point Cloud Completion Networks with Consistency Loss
- Cascaded Refinement Network for Point Cloud Completion with Self-supervision
- Growth parameter acquisition and geometric point cloud completion of lettuce
- Variational Relational Point Completion Network
- PF-Net: Point Fractal Network for 3D Point Cloud Completion
- RL-GAN-Net: A Reinforcement Learning Agent Controlled GAN Network for Real-Time Point Cloud Shape Completion
- PCN: Point Completion Network
- Research on Deep Learning-Based Point Cloud Completion and Recognition Methods for Mechanical Parts

### Innovation Points (3 个)

- 在基于深度学习的植物叶片点云补全网络中，引入级联细化网络的两分支结构，以增强细节生成能力。
- 在MEP组件点云补全中，引入GAN反演的无监督方法，减少对成对数据的依赖。
- 在生菜几何点云补全中，结合道路标线提取框架中的多任务学习策略，同时完成补全和参数提取。

### Stitching Plan (缝合方案)

- **Baseline**: Point Cloud Completion of Plant Leaves under Occlusion Conditions Based on Deep Learning
- **Module B**: Cascaded Refinement Network for Point Cloud Completion with Self-supervision
- **Module C**: Enhancing Performance of Point Cloud Completion Networks with Consistency Loss

## R38-023 — 基于深度学习的焊缝缺陷检测技术研究

- **可行性裁决**: `feasible` (分数: 85)
- **可行性理由**: Baseline论文31篇，有1个数据集和12个代码仓库，证据链完整。领域为2D视觉，无硬件依赖或数据合规风险，数据集可获取。
- **复核裁决**: `ACCEPT`
- **领域**: vision\_2d
- **方法关键词**: \['deep learning']
- **对象关键词**: \['weld seam', 'weld defect']

### Verified Papers (42 篇)

- **Ensemble-based deep learning model for welding defect detection and classification** — openalex
- **A New Image Recognition and Classification Method Combining Transfer Learning Algorithm and MobileNet Model for Welding Defects** — openalex
- **Deep Learning Based Steel Pipe Weld Defect Detection** — openalex
- **An automatic welding defect location algorithm based on deep learning** — openalex
- **Weld image deep learning-based on-line defects detection using convolutional neural networks for Al alloy in robotic arc welding** — openalex
- **Weld Defect Detection Based on Deep Learning Method** — openalex
- **Welding defects detection based on deep learning with multiple optical sensors during disk laser welding of thick plates** — openalex
- **Fast segmentation method for defects detection in radiographic images of welds** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/ba5a39dfcc04b28bc5fcd63146c4420653eb7748>
- **Welding image defect detection based on YOLO11** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/f0e6a464e51c56451f6c34f36e9acf2998be2e18>
  - Abstract: This study aims to focus on the rapid and accurate localization and identification of welding defects using low-brightness, low-contrast and high-reso...
- **Hybrid Deep Learning-Based Automatic Identification, Localization and Quantitative Evaluation of Internal Defects in Welds** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/7c70e9f6dbdd0976e9fce5c5dcdc7ebe552f73fe>
- ... 等共 42 篇

### Weak Papers (47 篇)

- **Defect Detection Methods for Industrial Products Using Deep Learning Techniques: A Review** — openalex
- **Review on Computer Aided Weld Defect Detection from Radiography Images** — openalex
- **A Smart Monitoring System for Automatic Welding Defect Detection** — openalex
- **State of the Art in Defect Detection Based on Machine Vision** — openalex
- **Using Deep Learning to Detect Defects in Manufacturing: A Comprehensive Survey and Current Challenges** — openalex
- ... 等共 47 篇

### Repos (12 个)

- **?**
  - URL: <https://github.com/huangyebiaoke/steel-pipe-weld-defect-detection>
- **?**
  - URL: <https://github.com/asad-gulshair/Weld-Defect-Detection-using-Deep-Learning>
- **?**
  - URL: <https://github.com/SujayanV/MC-CNN-for-defect-detection>
- **?**
  - URL: <https://github.com/ragavpn/WELD_DETECTION>
- **?**
  - URL: <https://github.com/rugvedrkulkarni/weld-defect-detection-unet>
- **?**
  - URL: <https://github.com/AshwanthReddy-exe/Welding-Defect-Detection>
- **?**
  - URL: <https://github.com/varun040705/welding-defect-detection-ml>
- **?**
  - URL: <https://github.com/shishyanthabm/Automated-Detection-of-Aesthetic-Defects-in-EV-Battery-Welds-Using-Deep-Learning-Machine-Learning>
- **?**
  - URL: <https://github.com/QQ767172261/How-to-use-the-deep-learning-target-detection-algorithm-yolo-to-train-JPEGWD-dataset-weld-defect-det>
- **?**
  - URL: <https://github.com/hxrsha05/Defectron-Realtime-Defect-Detection>

### Datasets (1 个)

- **NEU-DET** (source: paper\_title\_heuristic)

### Baselines (31 个)

- Ensemble-based deep learning model for welding defect detection and classification
- A New Image Recognition and Classification Method Combining Transfer Learning Algorithm and MobileNet Model for Welding Defects
- Deep Learning Based Steel Pipe Weld Defect Detection
- An automatic welding defect location algorithm based on deep learning
- Weld image deep learning-based on-line defects detection using convolutional neural networks for Al alloy in robotic arc welding
- Weld Defect Detection Based on Deep Learning Method
- Welding defects detection based on deep learning with multiple optical sensors during disk laser welding of thick plates
- Welding image defect detection based on YOLO11
- Hybrid Deep Learning-Based Automatic Identification, Localization and Quantitative Evaluation of Internal Defects in Welds
- Weld defect detection based on improved YOLOv8n.

### Innovation Points (5 个)

- 融合集成学习与迁移学习的焊缝缺陷检测模型，利用MobileNet作为基础特征提取器，结合集成策略提升分类精度
- 结合深度估计与双注意力点云网络的焊缝缺陷检测方法，利用2D图像生成3D点云特征，增强缺陷空间定位能力
- 结合RNN与SVM的焊缝缺陷时序分类模型，利用RNN提取焊缝序列特征，SVM进行最终分类，提升小样本下的鲁棒性
- 结合平面电磁检测与选择性测量的焊缝缺陷实时检测框架，利用深度学习网络处理稀疏测量数据，实现离线与在线检测
- 结合DAMHO优化与SCA-FlowNet的像素级缺陷量化方法，利用元启发式算法优化光流网络，提升低质量X射线图像中的缺陷分割精度

### Stitching Plan (缝合方案)

- **Baseline**: Ensemble-based deep learning model for welding defect detection and classification
- **Module B**: MobileNet迁移学习模块（来自A New Image Recognition and Classification Method Combining Transfer Learning Algorithm and MobileNet Model for Welding Defects）
- **Module C**: 集成策略（来自Ensemble-based baseline本身）

## R38-026 — 基于深度卷积神经网络的巡检图像电力部件识别方法研究

- **可行性裁决**: `risky` (分数: 55)
- **可行性理由**: 仅1篇baseline论文且有repo，但无公开数据集和代码仓库；电力巡检图像需自建数据集，存在数据获取和标注风险；无硬件依赖但数据合规风险较低。
- **复核裁决**: `MINOR_REVISION`
- **领域**: unknown
- **方法关键词**: \['巡检图像电力部件识别方法研究']
- **对象关键词**: \[]

### Verified Papers (3 篇)

- **Power Equipment Fault Image Recognition and Diagnosis Based on Convolutional Neural Network** — crossref
  - URL: <https://doi.org/10.1109/icsadl65848.2025.10933017>
- **Automatic Defect Detection of Fasteners on the Catenary Support Device Using Deep Convolutional Neural Network** — openalex
- **Segmentation of vegetation encroachment on electrical transmission lines using deep learning on drone images** — core
  - URL: <https://core.ac.uk/download/597474431.pdf>
  - Abstract: El trabajo de tesis se enfoca en abordar el problema de los cortes de energía en líneas de transmisión eléctrica debido a la invasión de vegetación. S...

### Weak Papers (14 篇)

- **Research on image classification model based on deep convolution neural network** — openalex
- **Recent Advances in Convolutional Neural Networks** — openalex
- **Deep Learning: A Comprehensive Overview on Techniques, Taxonomy, Applications and Research Directions** — openalex
- **Review on Convolutional Neural Network (CNN) Applied to Plant Leaf Disease Classification** — openalex
- **Convolutional Neural Network in Image Recognition** — crossref
- ... 等共 14 篇

### Repos (0 个)

（无）

### Datasets (0 个)

（无）

### Baselines (1 个)

- Power Equipment Fault Image Recognition and Diagnosis Based on Convolutional Neural Network

### Innovation Points (2 个)

- 在基线CNN电力设备故障识别模型基础上，引入并行论文中的紧固件缺陷检测模块，利用其多尺度特征提取能力增强对巡检图像中微小电力部件（如螺栓、绝缘子）的识别精度。
- 在基线CNN模型基础上，融合并行论文中的植被侵占分割模块，利用其语义分割能力对巡检图像中的背景干扰（如树木、杂草）进行抑制，提升电力部件前景识别效果。

### Stitching Plan (缝合方案)

- **Baseline**: CNN-based power equipment fault classifier
- **Module B**: 多尺度卷积特征提取模块（来自Automatic Defect Detection of Fasteners on the Catenary Support Device Using Deep Convolutional Neural Network）
- **Module C**: 语义分割编码器-解码器模块（来自Segmentation of vegetation encroachment on electrical transmission lines using deep learning on drone images）

## R38-027 — 基于深度学习的农作物病虫害检测研究

- **可行性裁决**: `feasible` (分数: 88)
- **可行性理由**: Baseline论文42篇，有5个公开数据集和12个代码仓库，证据链完整。领域为农作物病虫害检测，无硬件依赖或数据合规风险，数据集可获取。
- **复核裁决**: `ACCEPT`
- **领域**: vision\_2d
- **方法关键词**: \['deep learning']
- **对象关键词**: \['crop', 'pest', 'disease']

### Verified Papers (48 篇)

- **Deep Learning for Image-Based Cassava Disease Detection** — openalex
- **A Recognition Method for Rice Plant Diseases and Pests Video Detection Based on Deep Convolutional Neural Network** — openalex
- **Using Deep Learning for Image-Based Plant Disease Detection** — openalex
- **Comparative Study Of Deep Learning Algorithms For Disease And Pest Detection In Rice Crops** — openalex
- **Intelligent agriculture: deep learning in UAV-based remote sensing imagery for crop diseases and pests detection** — openalex
- **AI-powered banana diseases and pest detection** — openalex
- **Plant Disease Detection and Classification by Deep Learning** — openalex
- **Tomato Diseases and Pests Detection Based on Improved Yolo V3 Convolutional Neural Network** — openalex
- **Deep learning models for plant disease detection and diagnosis** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/3f611458b84ca8756c863916b33d12c704687127>
- **A Robust Deep-Learning-Based Detector for Real-Time Tomato Plant Diseases and Pests Recognition** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/886674a5abae3c9bfd262006c67d4ba078e1462b>
  - Abstract: Plant Diseases and Pests are a major challenge in the agriculture sector. An accurate and a faster detection of diseases and pests in plants could hel...
- ... 等共 48 篇

### Weak Papers (62 篇)

- **Machine Learning in Agriculture: A Review** — openalex
- **Advances in Deep Learning Applications for Plant Disease and Pest Detection: A Review** — openalex
- **Plant Disease Detection and Classification by Deep Learning—A Review** — openalex
- **Plant diseases and pests detection based on deep learning: a review** — openalex
- **DetNet: Design Backbone for Object Detection** — semantic\_scholar
- ... 等共 62 篇

### Repos (12 个)

- **?**
  - URL: <https://github.com/vushakolaPhanindra/AI-Crop-Disease-and-Pests-Detection>
- **?**
  - URL: <https://github.com/Retesh-vhavle/Plant-Disease-Detection-and-Classification-with-Pesticides-Suggestions>
- **?**
  - URL: <https://github.com/MaestriaElectronicaTEC/adversarial-anomaly-detector>
- **?**
  - URL: <https://github.com/Pradeepakaliraj/Crop-Pest-and-Disease-Detection-Using-Deep-Learning>
- **?**
  - URL: <https://github.com/GargiJadhav005/ai-pest-disease-assistant>
- **?**
  - URL: <https://github.com/Kamal-Shirupa/Cotton-Disease-Detection-and-Pesticide-Suggestion-System>
- **?**
  - URL: <https://github.com/Pankajkr2004/Pesticide-Detection-Automatic-Sprinkle-System>
- **?**
  - URL: <https://github.com/radhaneelamani/LeafiVision>
- **?**
  - URL: <https://github.com/MindDock/crop-pest-detection>
- **?**
  - URL: <https://github.com/ugreshaggarwal/AI-Crop-Disease-and-Pest-Detection->

### Datasets (5 个)

- **COCO** (source: paper\_title\_heuristic)
- **Pascal VOC** (source: paper\_title\_heuristic)
- **ImageNet** (source: paper\_title\_heuristic)
- **PlantVillage** (source: paper\_title\_heuristic)
- **AID** (source: paper\_title\_heuristic)

### Baselines (42 个)

- Deep Learning for Image-Based Cassava Disease Detection
- A Recognition Method for Rice Plant Diseases and Pests Video Detection Based on Deep Convolutional Neural Network
- Using Deep Learning for Image-Based Plant Disease Detection
- Comparative Study Of Deep Learning Algorithms For Disease And Pest Detection In Rice Crops
- Intelligent agriculture: deep learning in UAV-based remote sensing imagery for crop diseases and pests detection
- AI-powered banana diseases and pest detection
- Plant Disease Detection and Classification by Deep Learning
- Tomato Diseases and Pests Detection Based on Improved Yolo V3 Convolutional Neural Network
- Deep learning models for plant disease detection and diagnosis
- A Robust Deep-Learning-Based Detector for Real-Time Tomato Plant Diseases and Pests Recognition

### Innovation Points (4 个)

- 在基于深度学习的农作物病虫害检测中，引入YOLOv2的改进策略（如批量归一化、高分辨率分类器、锚框机制）替换baseline中的基础CNN检测器，提升检测速度和精度。
- 结合无人机遥感影像（来自baseline的UAV检测）与热成像多模态数据（来自parallel的番茄病害检测），构建双流CNN融合模型，提升早期病害识别鲁棒性。
- 在baseline的稻作物病虫害视频检测中，引入YOLOv2的实时检测优化（如多尺度训练、Darknet-19）替代原有帧处理模块，实现端到端视频流实时检测。
- 将parallel中水果病害识别的自适应图像分割方法（如颜色空间转换、阈值分割）集成到baseline的木薯病害检测流程中，提升复杂背景下的病害区域定位精度。

### Stitching Plan (缝合方案)

- **Baseline**: Deep Learning for Image-Based Cassava Disease Detection (CNN分类器)
- **Module B**: YOLOv2检测框架（来自YOLO9000: Better, Faster, Stronger）
- **Module C**: 自适应颜色空间分割模块（来自Adapted Approach for Fruit Disease Identification using Images）

### 标答 (Ground Truth)

- **领域**: 遥感/无人机
- **可行性**: `feasible`
- **标准 Baselines**: YOLOv5
- **标准 Datasets**: DOTA
- **标准 Repos**: ultralytics/yolov5

## R38-029 — 基于多种数据库的改进YOLO算法研究

- **可行性裁决**: `risky` (分数: 65)
- **可行性理由**: Baseline论文5篇且有4个repo，方法可复现，但无数据集和代码仓库，需自建数据集，存在数据获取风险。无硬件依赖或合规风险。
- **复核裁决**: `MINOR_REVISION`
- **领域**: vision\_2d
- **方法关键词**: \['improved YOLO', 'multi-database']
- **对象关键词**: \['object detection']

### Verified Papers (10 篇)

- **Object detection using YOLO: challenges, architectural successors, datasets and applications** — openalex
- **You Only Look Once: Unified, Real-Time Object Detection** — openalex
- **YOLO-v1 to YOLO-v8, the Rise of YOLO and Its Complementary Nature toward Digital Manufacturing and Industrial Defect Detection** — openalex
- **Poly-YOLO: higher speed, more precise detection and instance segmentation for YOLOv3** — arxiv
  - URL: <http://arxiv.org/abs/2005.13243v2>
  - Abstract: We present a new version of YOLO with better performance and extended with instance segmentation called Poly-YOLO. Poly-YOLO builds on the original id...
- **Lmf-Yolo: An Improved Yolo Algorithm for Road Object Detection in Autonomous Driving** — crossref
  - URL: <https://doi.org/10.2139/ssrn.5179459>
- **YOLO-DYN: An Improved YOLOv8 Model for Multi-Scale Object Detection** — crossref
  - URL: <https://doi.org/10.1109/ijcnn64981.2025.11228386>
- **Intelligent defect‑detection framework integrating a modified YOLO algorithm, a domain knowledge graph, and RAG‑enabled large language model** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/318610c8aad22eda35f3685b8a3ebf0c87df9e6d>
- **Ancient oracle bone inscription detection and translation based on depthwise-conv dual-cascade attention YOLOv12** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/8e2cfce1810ad0b30e073b2fe5de69c20a2a0328>
- **Application Research of Improved YOLO V3 Algorithm in PCB Electronic Component Detection** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/1662871e3ca2af703ddf32341642bb24575fcc29>
  - Abstract: Target detection of electronic components on PCB (Printed circuit board) based on vision is the core technology for 3C (Computer, Communication and Co...
- **Autonomous crop and weed detection in multiple agricultural fields using YOLO-based models with combined real and synthesized images** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/e1dfca3e49ede6323b240cf99c9117772666959e>

### Weak Papers (71 篇)

- **MS-YOLO: Infrared Object Detection for Edge Deployment via MobileNetV4 and SlideLoss** — arxiv
- **DAMO-YOLO : A Report on Real-Time Object Detection Design** — arxiv
- **SPMamba-YOLO: An Underwater Object Detection Network Based on Multi-Scale Feature Enhancement and Global Context Modeling** — arxiv
- **YOLO-World: Real-Time Open-Vocabulary Object Detection** — arxiv
- **YOLO-IOD: Towards Real Time Incremental Object Detection** — arxiv
- ... 等共 71 篇

### Repos (0 个)

（无）

### Datasets (0 个)

（无）

### Baselines (7 个)

- You Only Look Once: Unified, Real-Time Object Detection
- Poly-YOLO: higher speed, more precise detection and instance segmentation for YOLOv3
- Lmf-Yolo: An Improved Yolo Algorithm for Road Object Detection in Autonomous Driving
- YOLO-DYN: An Improved YOLOv8 Model for Multi-Scale Object Detection
- Intelligent defect‑detection framework integrating a modified YOLO algorithm, a domain knowledge graph, and RAG‑enabled large language model
- Ancient oracle bone inscription detection and translation based on depthwise-conv dual-cascade attention YOLOv12
- Application Research of Improved YOLO V3 Algorithm in PCB Electronic Component Detection

### Innovation Points (3 个)

- 在Poly-YOLO基础上，引入Lmf-Yolo的多尺度特征融合模块和YOLO-DYN的动态锚框机制，提升小目标检测精度和模型鲁棒性。
- 在Poly-YOLO基础上，融合Intelligent defect-detection框架中的知识图谱增强模块和YOLO-DYN的多尺度检测头，提升复杂场景下的检测性能。
- 在Poly-YOLO基础上，结合Lmf-Yolo的注意力机制和Object detection using YOLO中的数据增强策略，提升模型在农业场景下的泛化能力。

### Stitching Plan (缝合方案)

- **Baseline**: Poly-YOLO
- **Module B**: 多尺度特征融合模块（来自Lmf-Yolo）
- **Module C**: 动态锚框机制（来自YOLO-DYN）

## R38-034 — 基于深度学习的目标检测算法研究

- **可行性裁决**: `risky` (分数: 55)
- **可行性理由**: 仅1篇baseline论文（Hierarchical Object Detection with Deep Reinforcement Learning），无专用数据集，需自建或依赖公开数据集（如COCO），但题目宽泛且无明确数据来源，存在数据获取风险。
- **复核裁决**: `MINOR_REVISION`
- **领域**: vision\_2d
- **方法关键词**: \['deep learning', 'object detection']
- **对象关键词**: \['object']

### Verified Papers (4 篇)

- **Hierarchical Object Detection with Deep Reinforcement Learning** — arxiv
  - URL: <http://arxiv.org/abs/1611.03718v2>
  - Abstract: We present a method for performing hierarchical object detection in images guided by a deep reinforcement learning agent. The key idea is to focus on ...
- **Deep learning observables in computational fluid dynamics** — arxiv
  - URL: <http://arxiv.org/abs/1903.03040v2>
  - Abstract: Many large scale problems in computational fluid dynamics such as uncertainty quantification, Bayesian inversion, data assimilation and PDE constraine...
- **DILIE: Deep Internal Learning for Image Enhancement** — arxiv
  - URL: <http://arxiv.org/abs/2012.06469v1>
  - Abstract: We consider the generic deep image enhancement problem where an input image is transformed into a perceptually better-looking image. Recent methods fo...
- **Generalized Regularized Evidential Deep Learning Models: Theory and Comprehensive Evaluation** — arxiv
  - URL: <http://arxiv.org/abs/2512.23753v1>
  - Abstract: Evidential deep learning (EDL) models, based on Subjective Logic, introduce a principled and computationally efficient way to make deterministic neura...

### Weak Papers (0 篇)

（无）

### Repos (12 个)

- **?**
  - URL: <https://github.com/WZMIAOMIAO/deep-learning-for-image-processing>
- **?**
  - URL: <https://github.com/hoya012/deep_learning_object_detection>
- **?**
  - URL: <https://github.com/amusi/awesome-object-detection>
- **?**
  - URL: <https://github.com/abhineet123/Deep-Learning-for-Tracking-and-Detection>
- **?**
  - URL: <https://github.com/curiousily/Getting-Things-Done-with-Pytorch>
- **?**
  - URL: <https://github.com/curiousily/Deep-Learning-For-Hackers>
- **?**
  - URL: <https://github.com/jiwei0921/SOD-CNNs-based-code-summary->
- **?**
  - URL: <https://github.com/yuanmaoxun/Awesome-RGBT-Fusion>
- **?**
  - URL: <https://github.com/vvincenttttt/Awesome-3D-Object-Detection>
- **?**
  - URL: <https://github.com/abdur75648/Deep-Learning-Specialization-Coursera>

### Datasets (0 个)

（无）

### Baselines (1 个)

- Hierarchical Object Detection with Deep Reinforcement Learning

### Innovation Points (3 个)

- 将强化学习驱动的层次化目标检测与基于深度学习的流体动力学观测量预测相结合，利用强化学习智能体聚焦图像中信息丰富的区域，同时引入流体动力学特征作为辅助监督信号，提升检测精度和鲁棒性。
- 在层次化目标检测中引入深度内部学习（DILIE）的图像增强模块，对检测窗口进行预处理，提升低质量图像中的检测性能。
- 将层次化目标检测与广义正则化证据深度学习（GREDL）结合，利用证据学习量化检测不确定性，提升模型在开放世界场景下的可靠性。

### Stitching Plan (缝合方案)

- **Baseline**: Hierarchical Object Detection with Deep Reinforcement Learning
- **Module B**: Deep learning observables in computational fluid dynamics
- **Module C**: DILIE: Deep Internal Learning for Image Enhancement

## R38-037 — 基于无人机遥感的森林火灾检测算法研究

- **可行性裁决**: `feasible` (分数: 88)
- **可行性理由**: 5篇baseline均有repo，1个公开数据集，代码可复现；硬件依赖无人机但可用公开数据替代，无合规风险。
- **复核裁决**: `ACCEPT`
- **领域**: unknown
- **方法关键词**: \['森林火灾检测算法研究']
- **对象关键词**: \[]

### Verified Papers (41 篇)

- **A survey on technologies for automatic forest fire monitoring, detection, and fighting using unmanned aerial vehicles and remote sensing techniques** — openalex
- **LUFFD-YOLO: A Lightweight Model for UAV Remote Sensing Forest Fire Detection Based on Attention Mechanism and Multi-Level Feature Fusion** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/a29949f03e77545670d579f104ef58f73b8e04d5>
  - Abstract: The timely and precise detection of forest fires is critical for halting the spread of wildfires and minimizing ecological and economic damage. Howeve...
- **Enhancing Forest Fire Detection Accuracy of UAV Remote Sensing Technoloy Using Retinex Theory Algorithm** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/ac1d2aedc5eb9c15ea32ef390900df7712de15a4>
  - Abstract: This paper focuses on the application of UAV remote sensing technology in forest fire monitoring based on Retinex theory algorithm. This paper expound...
- **Background-robust knowledge distillation for forest fire detection in UAV remote sensing** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/779840153b383faa8cad74ab2b35e917069cbe9f>
- **UAV Remote Sensing Image Forest Fire Monitoring Method Based on FF-YOLO** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/de350c4f6bd49975bf61145b85e6032916cc529a>
  - Abstract: With the intensification of climate change and the global push toward carbon neutrality, forest fire monitoring has become a critical topic in environ...
- **Early Forest Fire Detection With UAV Image Fusion: A Novel Deep Learning Method Using Visible and Infrared Sensors** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/be4d51932fe5aa2f08d7d23f5770c54418b557a3>
  - Abstract: Global warming has significantly increased the frequency of forest fires. Unmanned aerial vehicles (UAVs) provide rapid response and real-time monitor...
- **Edge Computing-Based Real-Time Forest Fire Detection Using UAV Thermal and Color Images** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/1a81c1e42bd10d6a32e4602a7c407f94de58b98f>
  - Abstract: Fire detection using aerial platform is an important technology for forest surveillance. But the real-time detection capability is still a challenging...
- **A UAV-Based Multi-Scenario RGB-Thermal Dataset and Fusion Model for Enhanced Forest Fire Detection** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/20185526153be134620b8165feafe5db4e7fc991>
  - Abstract: UAVs are essential for forest fire detection due to vast forest areas and inaccessibility of high-risk zones, enabling rapid long-range inspection and...
- **Application of UAV Remote Sensing Technology in Forest Fire Monitoring Based on Retinex Theory Algorithm** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/1b5442c101fadddf8e8594b21299b645465d009c>
  - Abstract: This paper discusses the application of UAV remote sensing technology based on Retinex theory algorithm in forest fire monitoring. Firstly, the import...
- **Airborne Optical and Thermal Remote Sensing for Wildfire Detection and Monitoring** — openalex
- ... 等共 41 篇

### Weak Papers (37 篇)

- **A Survey on Object Detection in Optical Remote Sensing Images** — arxiv
- **Oriented object detection in optical remote sensing images using deep learning: a survey** — arxiv
- **Data Assimilation of Satellite Fire Detection in Coupled Atmosphere-Fire Simulation by WRF-SFIRE** — arxiv
- **A Review on Early Forest Fire Detection Systems Using Optical Remote Sensing** — openalex
- **Unmanned Aerial Vehicles (UAVs): A Survey on Civil Applications and Key Research Challenges** — openalex
- ... 等共 37 篇

### Repos (1 个)

- **?**
  - URL: <https://github.com/Weaston-create/forest-wildfire-asca-yolo>

### Datasets (1 个)

- **COCO** (source: paper\_title\_heuristic)

### Baselines (20 个)

- LUFFD-YOLO: A Lightweight Model for UAV Remote Sensing Forest Fire Detection Based on Attention Mechanism and Multi-Level Feature Fusion
- Background-robust knowledge distillation for forest fire detection in UAV remote sensing
- UAV Remote Sensing Image Forest Fire Monitoring Method Based on FF-YOLO
- Residual capsule network with threshold convolution and attention mechanism for forest fire detection using UAV imagery
- A Lightweight Forest Fire Detection Method Based on UAV Dual-Modal Images
- An Improved Unmanned Aerial Vehicle Forest Fire Detection Model Based on YOLOv8
- FF-Mamba-YOLO: An SSM-Based Benchmark for Forest Fire Detection in UAV Remote Sensing Images
- Efficient Detection of Forest Fire Smoke in UAV Aerial Imagery Based on an Improved Yolov5 Model and Transfer Learning
- FL-YOLOv7: A Lightweight Small Object Detection Algorithm in Forest Fire Detection
- YOlOv5s-ACE: Forest Fire Object Detection Algorithm Based on Improved YOLOv5s

### Innovation Points (4 个)

- 在LUFFD-YOLO的轻量级骨干网络中引入Retinex理论算法进行图像增强，提升复杂光照条件下的火焰检测鲁棒性。
- 在LUFFD-YOLO中融合可见光和红外双模态图像，利用特征级融合提升多尺度火焰目标的检测精度。
- 在LUFFD-YOLO中集成边缘计算优化模块，将模型剪枝和量化部署到无人机边缘设备，实现实时检测。
- 在LUFFD-YOLO中引入多场景RGB-热红外融合数据集和对应的融合检测头，增强模型对不同场景（如烟雾遮挡、夜间）的适应性。

### Stitching Plan (缝合方案)

- **Baseline**: LUFFD-YOLO
- **Module B**: Retinex图像增强模块（来自Enhancing Forest Fire Detection Accuracy of UAV Remote Sensing Technoloy Using Retinex Theory Algorithm）
- **Module C**: 双模态特征融合模块（来自Early Forest Fire Detection With UAV Image Fusion: A Novel Deep Learning Method Using Visible and Infrared Sensors）

## R38-040 — 基于改进YOLO网络与极限学习机的绝缘子故障检测

- **可行性裁决**: `risky` (分数: 65)
- **可行性理由**: Baseline≥3且有repo，方法可复现；但无公开数据集，需自建绝缘子故障图像，存在数据获取风险；无硬件依赖或合规风险。
- **复核裁决**: `MINOR_REVISION`
- **领域**: energy\_power
- **方法关键词**: \['improved YOLO', 'extreme learning machine']
- **对象关键词**: \['insulator']

### Verified Papers (14 篇)

- **SMI-YOLO: Insulator Fault Detection Network Based on Improved YOLOv5** — crossref
  - URL: <https://doi.org/10.62953/ijamce.530458>
- **MPA-YOLO: Insulator Defect Detection Based on Improved YOLOV11 Algorithm** — crossref
  - URL: <https://doi.org/10.1109/safeprocess67117.2025.11267908>
- **Ialf-Yolo: Insulator Defect Detection Method Combining Improved Attention Mechanism and Lightweight Feature Fusion Network** — crossref
  - URL: <https://doi.org/10.2139/ssrn.4898785>
- **Wire Insulator Fault and Foreign Body Detection Algorithm Based on YOLO v5 and YOLO v7** — crossref
  - URL: <https://doi.org/10.1109/iceace60673.2023.10442092>
- **Fault-YOLO: A method for power line insulator fault detection** — crossref
  - URL: <https://doi.org/10.1088/1742-6596/3255/1/012002>
  - Abstract: <jats:title>Abstract\</jats:title>
    <jats:p>Insulators perform both insulation and support functions in transmission lines, and their ...
- **DFW-YOLO: A small insulator target defect detection algorithm based on improved YOLOv8s** — crossref
  - URL: <https://doi.org/10.18287/2412-6179-co-1600>
  - Abstract: <jats:p>With the continuous progress of deep learning technology, UAV aerial photography faces significant challenges for insulator defect detection. ...
- **MFI-YOLO: Multi-Fault Insulator Detection Based on an Improved YOLOv8** — crossref
  - URL: <https://doi.org/10.1109/tpwrd.2023.3328178>
- **MS-YOLO: An Improved Lightweight Transmission Line Insulator Defect Detection Algorithm Based on YOLOv8** — crossref
  - URL: <https://doi.org/10.1007/978-3-031-70235-8_53>
- **SFCF-YOLO: An Improved YOLO Architecture with Spatial-Focus Cross-Fusion Mechanism for Insulator Defect Detection** — crossref
  - URL: <https://doi.org/10.1109/irac67707.2025.11381267>
- **ACRC-YOLO: An Improved Algorithm for Insulator Defect Detection** — crossref
  - URL: <https://doi.org/10.1109/icaide65466.2025.11189512>
- ... 等共 14 篇

### Weak Papers (24 篇)

- **Learning Curves for Decision Making in Supervised Machine Learning: A Survey** — arxiv
- **Active learning for data streams: a survey** — arxiv
- **MS-YOLO: Infrared Object Detection for Edge Deployment via MobileNetV4 and SlideLoss** — arxiv
- **DAMO-YOLO : A Report on Real-Time Object Detection Design** — arxiv
- **Fault Detection in New Wind Turbines with Limited Data by Generative Transfer Learning** — arxiv
- ... 等共 24 篇

### Repos (0 个)

（无）

### Datasets (0 个)

（无）

### Baselines (13 个)

- SMI-YOLO: Insulator Fault Detection Network Based on Improved YOLOv5
- MPA-YOLO: Insulator Defect Detection Based on Improved YOLOV11 Algorithm
- Ialf-Yolo: Insulator Defect Detection Method Combining Improved Attention Mechanism and Lightweight Feature Fusion Network
- Wire Insulator Fault and Foreign Body Detection Algorithm Based on YOLO v5 and YOLO v7
- Fault-YOLO: A method for power line insulator fault detection
- DFW-YOLO: A small insulator target defect detection algorithm based on improved YOLOv8s
- MFI-YOLO: Multi-Fault Insulator Detection Based on an Improved YOLOv8
- MS-YOLO: An Improved Lightweight Transmission Line Insulator Defect Detection Algorithm Based on YOLOv8
- SFCF-YOLO: An Improved YOLO Architecture with Spatial-Focus Cross-Fusion Mechanism for Insulator Defect Detection
- ACRC-YOLO: An Improved Algorithm for Insulator Defect Detection

### Innovation Points (3 个)

- 结合SMI-YOLO的注意力机制与Fault-YOLO的多尺度特征融合，提升绝缘子微小故障检测精度
- 将MPA-YOLO的轻量化主干与Ialf-Yolo的注意力机制结合，实现高效绝缘子缺陷检测
- 融合Wire Insulator Fault Detection中的YOLOv5与YOLOv7双模型集成策略与Lightweight Insulator Defect Detection的系统级协同设计，提升高分辨率无人机图像检测鲁棒性

### Stitching Plan (缝合方案)

- **Baseline**: SMI-YOLO (基于YOLOv5)
- **Module B**: Fault-YOLO的多尺度特征融合模块
- **Module C**: Lightweight Insulator Defect Detection的系统级协同设计模块

## R38-043 — 基于无人机平台的动态目标检测系统开发

- **可行性裁决**: `feasible` (分数: 85)
- **可行性理由**: Baseline论文14篇（含5篇有repo），1个数据集和1个代码仓库，证据链完整。但涉及无人机硬件平台，需评估实物获取与飞行许可风险。
- **复核裁决**: `ACCEPT`
- **领域**: vision\_2d
- **方法关键词**: \['object detection', 'dynamic target detection', 'UAV platform']
- **对象关键词**: \['dynamic target', 'moving object']

### Verified Papers (35 篇)

- **A Survey of Indoor and Outdoor UAV-Based Target Tracking Systems: Current Status, Challenges, Technologies, and Future Directions** — openalex
- **Dynamic Target Tracking of Small UAVs in Unstructured Environment** — openalex
- **Dynamic Object Tracking on Autonomous UAV System for Surveillance Applications** — openalex
- **Dynamic Target Tracking and Following with UAVs Using Multi-Target Information: Leveraging YOLOv8 and MOT Algorithms** — openalex
- **Speed Estimation of Multiple Moving Objects from a Moving UAV Platform** — openalex
- **DynaSLAM: Tracking, Mapping, and Inpainting in Dynamic Scenes** — openalex
- **A Boosted Particle Filter: Multitarget Detection and Tracking** — openalex
- **Multiple Object Tracking Using K-Shortest Paths Optimization** — openalex
- **UAV Images Dataset for Moving Object Detection from Moving Cameras** — arxiv
  - URL: <http://arxiv.org/abs/2103.11460v2>
  - Abstract: This paper presents a new high resolution aerial images dataset in which moving objects are labelled manually. It aims to contribute to the evaluation...
- **Multi-UAV Dynamic Target search Scheme by a Novel SCA-MAPPO Algorithm** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/ad45828391c3d93c0037091990def480c528ed61>
  - Abstract: This paper investigates the problem of cooperative dynamic target search for UAV swarms under the constraints of local observability and inter-agent c...
- ... 等共 35 篇

### Weak Papers (40 篇)

- **A Survey of the Multi-Sensor Fusion Object Detection Task in Autonomous Driving** — openalex
- **A Survey of Indoor UAV Obstacle Avoidance Research** — openalex
- **Oriented object detection in optical remote sensing images using deep learning: a survey** — arxiv
- **Tools, techniques, datasets and application areas for object detection in an image: a review** — openalex
- **Research on object detection and recognition in remote sensing images based on YOLOv11** — openalex
- ... 等共 40 篇

### Repos (1 个)

- **?**
  - URL: <https://github.com/stqchv/acro-uav-target-pursuit>

### Datasets (1 个)

- **AID** (source: paper\_title\_heuristic)

### Baselines (14 个)

- Dynamic Target Tracking and Following with UAVs Using Multi-Target Information: Leveraging YOLOv8 and MOT Algorithms
- Reinforcement Learning for Joint Radar and Communication Enabled Multi-UAV Cooperative Dynamic Target Detection and Tracking
- DMF-YOLO: Dynamic Multi-Scale Feature Fusion Network-Driven Small Target Detection in UAV Aerial Images
- SDFA-Net: Synergistic Dynamic Fusion Architecture With Deformable Attention for UAV Small Target Detection
- IEC-YOLOX:A Lightweight Object Detection Algorithm for UAV Target Detection
- Dynamic Backbone Optimization of Yolov10 for Real-Time Object Detection in Uav-Based Search and Rescue Missions
- YOLOv8n for UAV Object Detection with Dynamic Fusion and Gradient Path Encoding
- Dynamic CNN Parameter Exploration for Multi-Altitude UAV Object Detection
- UAV Target Detection: A Method Based on Dynamic Cross-Scale Attention Fusion Mechanism
- Semantic-Aware Dynamic Feature Selection and Fusion for Object Detection in UAV Videos

### Innovation Points (5 个)

- 在YOLOv8+MOT框架中集成动态多尺度特征融合网络DMF-YOLO，提升小目标检测精度
- 在YOLOv8+MOT框架中引入SDFA-Net的协同动态融合架构与可变形注意力，增强小目标检测鲁棒性
- 在YOLOv8+MOT框架中融合IEC-YOLOX的轻量级检测头，提升无人机平台实时性
- 在YOLOv8+MOT框架中集成DynaSLAM的动态场景处理模块，提升动态目标跟踪稳定性
- 在YOLOv8+MOT框架中引入增强粒子滤波（Boosted Particle Filter）进行多目标检测与跟踪，提升遮挡鲁棒性

### Stitching Plan (缝合方案)

- **Baseline**: YOLOv8+MOT
- **Module B**: DMF-YOLO动态多尺度特征融合模块
- **Module C**: IEC-YOLOX轻量级检测头

## R38-047 — 基于深度学习的交通标志识别算法研究

- **可行性裁决**: `feasible` (分数: 88)
- **可行性理由**: 29篇baseline论文（含1篇有repo）、14篇parallel论文、1个公开数据集、12个代码仓库，证据链完整。交通标志识别为2D视觉任务，无硬件依赖或数据合规风险，数据集可获取。
- **复核裁决**: `ACCEPT`
- **领域**: vision\_2d
- **方法关键词**: \['deep learning', 'convolutional neural network']
- **对象关键词**: \['traffic sign']

### Verified Papers (43 篇)

- **An Incremental Framework for Video-Based Traffic Sign Detection, Tracking, and Recognition** — openalex
- **Traffic sign detection and recognition using fully convolutional network guided proposals** — openalex
- **Deep neural network for traffic sign recognition systems: An analysis of spatial transformers and stochastic optimisation methods** — openalex
- **Traffic sign recognition based on deep learning** — openalex
- **Indian traffic sign detection and recognition using deep learning** — openalex
- **Traffic-Sign Recognition Using Deep Learning** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/07d8e1b7ea48324df070fe5d67ac290b4a6e2f7c>
  - Abstract: Traffic-sign recognition (TSR) has been an essential part of driver-assistance systems, which is able to assist drivers in avoiding a vast number of p...
- **Traffic Sign Recognition using You Look Only Once Version 8 with Vision Transformer** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/70ef9ac30bf45765565abe81d5baa965e9755483>
  - Abstract: In recent years, Traffic Sign Recognition (TSR) has become an emerging computer vision task which allows vehicles to detect and interpret road signs f...
- **Automated Traffic Sign Recognition via CNN Deep Learning** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/9e238e665bea7b9a77e9fc3b1fbebcfb4a9b6bfa>
  - Abstract: The rapid development of the road traffic systems is a very important component of the nation’s infrastructure, and that is reflected in growing impor...
- **Advancing Traffic Sign Recognition: Explainable Deep CNN for Enhanced Robustness in Adverse Environments** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/76abf1a8665c598984f3ff4437f9a27e4dd38fc6>
  - Abstract: This paper presents a traffic sign recognition (TSR) system based on the deep convolutional neural network (CNN) architecture, which proves to be extr...
- **Traffic Sign Recognition Based on Improved SSD Model** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/3301642638c6afd16207cf9dd6ee27857647b076>
  - Abstract: In view of the problems of missed detection and low detection accuracy of the SSD model in the detection of small targets, an improved SSD model for t...
- ... 等共 43 篇

### Weak Papers (41 篇)

- **Review of deep learning: concepts, CNN architectures, challenges, applications, future directions** — openalex
- **Deep Learning for Generic Object Detection: A Survey** — openalex
- **A Survey of Deep Learning-Based Object Detection** — openalex
- **Deep Learning for Safe Autonomous Driving: Current Challenges and Future Directions** — openalex
- **Small Object Detection in Traffic Scenes Based on Attention Feature Fusion** — semantic\_scholar
- ... 等共 41 篇

### Repos (12 个)

- **?**
  - URL: <https://github.com/jluo-bgl/Traffic-Sign-Recognition-with-Deep-Learning-CNN>
- **?**
  - URL: <https://github.com/alexandrosstergiou/Traffic-Sign-Recognition-basd-on-Synthesised-Training-Data>
- **?**
  - URL: <https://github.com/yiliucs/Federated-Learning-for-Traffic-Sign-Recognition>
- **?**
  - URL: <https://github.com/chandansaha2014/Real-time-Traffic-Sign-Recognition>
- **?**
  - URL: <https://github.com/sovit-123/German-Traffic-Sign-Recognition-with-Deep-Learning>
- **?**
  - URL: <https://github.com/P-Darabi/Traffic-Signs-Detection-By-YOLOv8>
- **?**
  - URL: <https://github.com/Navkrish04/German-Traffic-Sign-Classification>
- **?**
  - URL: <https://github.com/SMQuadri/Road-Traffic-Sign-Recognition>
- **?**
  - URL: <https://github.com/Manasvi-V/Traffic-Sign-Recognition-using-Machine-Learning>
- **?**
  - URL: <https://github.com/AvishkaSandeepa/Traffic-Signs-Recognition>

### Datasets (1 个)

- **VisDrone** (source: paper\_title\_heuristic)

### Baselines (29 个)

- Traffic sign detection and recognition using fully convolutional network guided proposals
- Deep neural network for traffic sign recognition systems: An analysis of spatial transformers and stochastic optimisation methods
- Traffic sign recognition based on deep learning
- Indian traffic sign detection and recognition using deep learning
- Traffic-Sign Recognition Using Deep Learning
- Automated Traffic Sign Recognition via CNN Deep Learning
- Advancing Traffic Sign Recognition: Explainable Deep CNN for Enhanced Robustness in Adverse Environments
- Traffic Sign Recognition Based on Improved SSD Model
- Real-Time Embedded Traffic Sign Recognition Using Efficient Convolutional Neural Network
- Evaluation of deep neural network traffic sign recognition system with focus on data augmentation

### Innovation Points (5 个)

- 在FCN引导提议的交通标志检测与识别框架中，集成Vision Transformer模块以增强特征提取和分类能力，提升复杂场景下的识别鲁棒性。
- 在基于深度学习的交通标志识别baseline中，引入增量式视频框架，实现连续帧的检测、跟踪与识别，提升实时性和稳定性。
- 在空间变换器网络优化的交通标志识别baseline中，融合复杂天气下的检测Transformer，提升雨雾等恶劣条件下的识别性能。
- 在印度交通标志检测与识别baseline中，集成实时框架的轻量化卷积和注意力机制，提升推理速度同时保持精度。
- 在交通标志识别baseline中，引入Instasign系统的端到端识别流水线，优化从图像采集到分类的完整流程。

### Stitching Plan (缝合方案)

- **Baseline**: FCN引导提议的交通标志检测与识别模型
- **Module B**: Vision Transformer特征提取模块（来自Traffic Sign Recognition using YOLOv8 with Vision Transformer）
- **Module C**: 增量式跟踪模块（来自An Incremental Framework for Video-Based Traffic Sign Detection, Tracking, and Recognition）

### 标答 (Ground Truth)

- **领域**: 自动驾驶/交通标志
- **可行性**: `feasible`
- **标准 Baselines**: YOLOv5
- **标准 Datasets**: GTSRB
- **标准 Repos**: ultralytics/yolov5

## R38-049 — 基于特征点的目标位姿估计与机械臂抓取控制

- **可行性裁决**: `risky` (分数: 55)
- **可行性理由**: baseline仅5篇且无repo无数据集，涉及机械臂硬件依赖（实物获取风险高），无降级方案。
- **复核裁决**: `MINOR_REVISION`
- **领域**: robotics\_control
- **方法关键词**: \['feature point extraction', 'pose estimation']
- **对象关键词**: \['target', 'robot arm']

### Verified Papers (25 篇)

- **Object Pose Estimation and Feature Extraction Based on PVNet** — openalex
- **High-resolution open-vocabulary object 6D pose estimation** — arxiv
  - URL: <http://arxiv.org/abs/2406.16384v2>
  - Abstract: The generalisation to unseen objects in the 6D pose estimation task is very challenging. While Vision-Language Models (VLMs) enable using natural lang...
- **Visual Detection, Tracking and Pose Estimation of a Robotic Arm End Effector** — openalex
- **Object pose estimation based on stereo vision with improved K-D tree ICP algorithm** — None
- **Extraction method of position and posture information of robot arm picking up target based on RGB-D data** — openalex
- **An Improved Pose Estimation Method Based on Projection Vector With Noise Error Uncertainty** — openalex
- **Object Recognition and Grasping for Collaborative Robots Based on Vision** — openalex
- **Autonomous Robotic Manipulation: Real-Time, Deep-Learning Approach for Grasping of Unknown Objects** — openalex
- **A Likelihood-Based Pose Estimation Method for Robotic Arm Repeatability Measurement Using Monocular Vision** — openalex
- **Target Localization and Grasping of NAO Robot Based on YOLOv8 Network and Monocular Ranging** — openalex
- ... 等共 25 篇

### Weak Papers (70 篇)

- **AHY-SLAM: Toward Faster and More Accurate Visual SLAM in Dynamic Scenes Using Homogenized Feature Extraction and Object Detection Method** — openalex
- **Robust pose estimation for non-cooperative space objects based on multichannel matching method** — openalex
- **Integrated Pose Estimation Using 2D Lidar and INS Based on Hybrid Scan Matching** — openalex
- **Visual-based Positioning and Pose Estimation** — arxiv
- **One-Shot Imitation Learning: A Pose Estimation Perspective** — arxiv
- ... 等共 70 篇

### Repos (0 个)

（无）

### Datasets (1 个)

- **nuScenes** (source: paper\_title\_heuristic)

### Baselines (10 个)

- Object Pose Estimation and Feature Extraction Based on PVNet
- Object pose estimation based on stereo vision with improved K-D tree ICP algorithm
- Extraction method of position and posture information of robot arm picking up target based on RGB-D data
- An Improved Pose Estimation Method Based on Projection Vector With Noise Error Uncertainty
- A target recognition and 3d pose estimation method in non-structural environment
- Revisiting the PnP Problem: A Fast, General and Optimal Solution
- Monocular Visual Pose Estimation Method Based on Spherical Cooperative Target
- EPro-PnP: Generalized End-to-End Probabilistic Perspective-n-Points for Monocular Object Pose Estimation
- A simple, robust and fast method for the perspective-n-point Problem
- Single image based camera calibration and pose estimation of the end-effector of a robot

### Innovation Points (4 个)

- 在PVNet特征点检测基础上，融合高分辨率开放词汇6D姿态估计中的视觉-语言模型（VLM）模块，实现未知物体的零样本姿态估计
- 在改进K-D tree ICP算法基础上，集成协作机器人视觉抓取中的实时目标检测与跟踪模块，提升动态场景下的位姿跟踪鲁棒性
- 在RGB-D数据提取位姿方法基础上，融合自主机器人操作中的深度学习抓取检测模块，实现未知物体的实时抓取位姿生成
- 在投影向量噪声误差不确定性姿态估计方法基础上，集成单目视觉重复性测量中的似然估计模块，提升位姿估计的精度与置信度评估

### Stitching Plan (缝合方案)

- **Baseline**: PVNet
- **Module B**: High-resolution open-vocabulary object 6D pose estimation中的VLM语义对齐模块
- **Module C**: Object Recognition and Grasping for Collaborative Robots Based on Vision中的YOLO检测+卡尔曼滤波跟踪模块

### 标答 (Ground Truth)

- **领域**: 机器人/机械臂
- **可行性**: `not_recommended`
- **标准 Baselines**: （无）
- **标准 Datasets**: YCB
- **标准 Repos**: （无）

## R38-050 — 基于深度学习的行人检测与跟踪算法研究

- **可行性裁决**: `feasible` (分数: 82)
- **可行性理由**: Baseline有5篇，涉及热成像、YOLOv4等，但无repo；有3个数据集和12个代码仓库，证据链较完整。无硬件依赖或数据合规风险。
- **复核裁决**: `ACCEPT`
- **领域**: vision\_2d
- **方法关键词**: \['deep learning', 'object detection', 'object tracking']
- **对象关键词**: \['pedestrian']

### Verified Papers (26 篇)

- **Nighttime Pedestrian Detection Based on Thermal Imaging and Convolutional Neural Networks** — openalex
- **Pedestrian detection algorithm in traffic scene based on weakly supervised hierarchical deep model** — openalex
- **A real-time Deep Learning pedestrian detector for robot navigation** — openalex
- **Deep learning for occluded and multi‐scale pedestrian detection: A review** — openalex
- **An FPGA-Accelerated Design for Deep Learning Pedestrian Detection in Self-Driving Vehicles** — openalex
- **Study on Pedestrian Detection Based on an Improved YOLOv4 Algorithm** — openalex
- **A Comparative Study and State-of-the-art Evaluation for Pedestrian Detection** — openalex
- **Pedestrian Detection via Mixture of CNN Experts and Thresholded Aggregated Channel Features** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/7b965bf132e5971dfa95c67bc7685b73b32e07df>
- **Local Decorrelation For Improved Pedestrian Detection** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/c7056ac425f07984d6fefd4446b4c6028f6405e1>
- **Learning Mutual Visibility Relationship for Pedestrian Detection with a Deep Model** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/2a3f1533726adcbfa0694aec5335c2df266437c7>
- ... 等共 26 篇

### Weak Papers (35 篇)

- **Nighttime Foreground Pedestrian Detection Based on Three-Dimensional Voxel Surface Model** — openalex
- **Research on unsupervised people re-identification based on k-means clustering** — openalex
- **\[Retracted] A Review of Intelligent Driving Pedestrian Detection Based on Deep Learning** — openalex
- **Pedestrian detection with dilated convolution, region proposal network and boosted decision trees** — openalex
- **A Comparative Review of Recent Few-Shot Object Detection Algorithms** — semantic\_scholar
- ... 等共 35 篇

### Repos (12 个)

- **?**
  - URL: <https://github.com/yuanmaoxun/Awesome-RGBT-Fusion>
- **?**
  - URL: <https://github.com/Aryia-Behroziuan/neurons>
- **?**
  - URL: <https://github.com/Aryia-Behroziuan/References>
- **?**
  - URL: <https://github.com/WoShiDongZhiWu/deepLearning_UCAS2019>
- **?**
  - URL: <https://github.com/sezer-muhammed/Teknofest-Ulasimda-Yapay-Zeka-Veri-Seti>
- **?**
  - URL: <https://github.com/thomaswengerter/FMCW_Radar_Target_Simulator>
- **?**
  - URL: <https://github.com/LeadingIndiaAI/Real-Time-Multiple-Object-Detection>
- **?**
  - URL: <https://github.com/danxuhk/CMT-CNN>
- **?**
  - URL: <https://github.com/cosminbvb/Clothing-Pedestrian-Detection>
- **?**
  - URL: <https://github.com/LeadingIndiaAI/Pedestrian-Detection>

### Datasets (3 个)

- **KITTI** (source: paper\_title\_heuristic)
- **Pascal VOC** (source: paper\_title\_heuristic)
- **EuRoC** (source: paper\_title\_heuristic)

### Baselines (23 个)

- Nighttime Pedestrian Detection Based on Thermal Imaging and Convolutional Neural Networks
- Pedestrian detection algorithm in traffic scene based on weakly supervised hierarchical deep model
- A real-time Deep Learning pedestrian detector for robot navigation
- An FPGA-Accelerated Design for Deep Learning Pedestrian Detection in Self-Driving Vehicles
- Study on Pedestrian Detection Based on an Improved YOLOv4 Algorithm
- Pedestrian Detection via Mixture of CNN Experts and Thresholded Aggregated Channel Features
- Local Decorrelation For Improved Pedestrian Detection
- Learning Mutual Visibility Relationship for Pedestrian Detection with a Deep Model
- Pedestrian detection with a Large-Field-Of-View deep network
- Deep Learning of Scene-Specific Classifier for Pedestrian Detection

### Innovation Points (3 个)

- 融合热成像特征与改进YOLOv4的夜间行人检测模块
- 弱监督层次深度模型与实时轻量检测器融合的交通场景行人检测
- FPGA加速设计与YOLOv4改进算法结合的硬件高效行人检测

### Stitching Plan (缝合方案)

- **Baseline**: Nighttime Pedestrian Detection Based on Thermal Imaging and Convolutional Neural Networks
- **Module B**: 改进YOLOv4的骨干网络与检测头（来自Study on Pedestrian Detection Based on an Improved YOLOv4 Algorithm）
- **Module C**: 热成像预处理与特征提取模块（来自Nighttime Pedestrian Detection Based on Thermal Imaging and Convolutional Neural Networks）

### 标答 (Ground Truth)

- **领域**: 自动驾驶
- **可行性**: `feasible`
- **标准 Baselines**: YOLOv5
- **标准 Datasets**: KITTI, nuScenes
- **标准 Repos**: ultralytics/yolov5

## R38-057 — 基于深度相机的机械臂动态避障规划研究

- **可行性裁决**: `risky` (分数: 65)
- **可行性理由**: Baseline有8篇但无数据集和代码仓库，需自建深度相机与机械臂硬件平台，存在硬件获取与复现风险。
- **复核裁决**: `MINOR_REVISION`
- **领域**: robotics\_control
- **方法关键词**: \['depth camera', 'dynamic obstacle avoidance', 'motion planning']
- **对象关键词**: \['robotic arm', 'manipulator']

### Verified Papers (23 篇)

- **Multisensor Data Fusion for Reliable Obstacle Avoidance** — arxiv
  - URL: <http://arxiv.org/abs/2212.13218v1>
  - Abstract: In this work, we propose a new approach that combines data from multiple sensors for reliable obstacle avoidance. The sensors include two depth camera...
- **Intelligent Seven-DoF Robot With Dynamic Obstacle Avoidance and 3-D Object Recognition for Industrial Cyber–Physical Systems in Manufacturing Automation** — openalex
- **Learning Dynamic Obstacle Avoidance for a Robot Arm Using Neuroevolution** — openalex
- **An obstacle avoidance method for robotic arm based on reinforcement learning** — openalex
- **Dynamic Obstacle Avoidance Algorithm for Robot Arm Based on Deep Reinforcement Learning** — openalex
- **Research on 3D Obstacle Avoidance Path Planning for Apple Picking Robotic Arm** — openalex
- **On-line collision avoidance for collaborative robot manipulators by adjusting off-line generated paths: An industrial use case** — openalex
- **Dynamic Obstacle Avoidance Planning for Manipulators of Home** — openalex
- **Towards Dynamic Obstacle Avoidance for Robot Manipulators with Deep Reinforcement Learning** — None
- **Motion Planning and Control of Redundant Manipulators for Dynamical Obstacle Avoidance** — openalex
- ... 等共 23 篇

### Weak Papers (80 篇)

- **Vision-based Obstacle Removal System for Autonomous Ground Vehicles Using a Robotic Arm** — arxiv
- **Perceptive Pedipulation with Local Obstacle Avoidance** — arxiv
- **Configuration-Aware Safe Control for Mobile Robotic Arm with Control Barrier Functions** — arxiv
- **Intelligent Singularity Avoidance in UR10 Robotic Arm Path Planning Using Hybrid Fuzzy Logic and Reinforcement Learning** — arxiv
- *Adaptive Step RRT*-Based Method for Path Planning of Tea-Picking Robotic Arm\* — openalex
- ... 等共 80 篇

### Repos (0 个)

（无）

### Datasets (0 个)

（无）

### Baselines (8 个)

- Intelligent Seven-DoF Robot With Dynamic Obstacle Avoidance and 3-D Object Recognition for Industrial Cyber–Physical Systems in Manufacturing Automation
- Learning Dynamic Obstacle Avoidance for a Robot Arm Using Neuroevolution
- An obstacle avoidance method for robotic arm based on reinforcement learning
- Dynamic Obstacle Avoidance Algorithm for Robot Arm Based on Deep Reinforcement Learning
- Dynamic Obstacle Avoidance Planning for Manipulators of Home
- Towards Dynamic Obstacle Avoidance for Robot Manipulators with Deep Reinforcement Learning
- Motion Planning and Control of Redundant Manipulators for Dynamical Obstacle Avoidance
- Optimizing Robotic Arm Obstacle Avoidance via Improved Random Tree Star (RRT)\* and Deep Reinforcement Learning Coordination

### Innovation Points (3 个)

- 融合深度相机与LiDAR的多传感器数据，提升动态障碍物检测的可靠性和覆盖范围，并集成到基于深度强化学习的避障规划框架中
- 结合Bi-RRT与SAC两层规划架构，先离线生成全局路径，再在线用SAC进行动态避障微调，提高实时性与路径质量
- 利用深度相机与碰撞检测算法实现快速障碍物检测，并集成到神经进化避障框架中，提升复杂人机交互场景下的检测速度

### Stitching Plan (缝合方案)

- **Baseline**: Dynamic Obstacle Avoidance Algorithm for Robot Arm Based on Deep Reinforcement Learning
- **Module B**: Multisensor Data Fusion for Reliable Obstacle Avoidance
- **Module C**: A SAC-Bi-RRT Two-Layer Real-Time Motion Planning Approach for Robot Assembly Tasks in Unstructured Environments

### 标答 (Ground Truth)

- **领域**: 机器人/机械臂
- **可行性**: `not_recommended`
- **标准 Baselines**: （无）
- **标准 Datasets**: （无）
- **标准 Repos**: （无）

## R38-067 — 基于深度学习的车辆检测及应用研究

- **可行性裁决**: `feasible` (分数: 85)
- **可行性理由**: Baseline论文5篇，含SECOND、YOLO、PIXOR等，有2个数据集和12个代码仓库，证据链完整。领域为2D/3D车辆检测，无硬件依赖或数据合规风险。
- **复核裁决**: `ACCEPT`
- **领域**: vision\_2d
- **方法关键词**: \['deep learning']
- **对象关键词**: \['vehicle']

### Verified Papers (18 篇)

- **SECOND: Sparsely Embedded Convolutional Detection** — openalex
- **Object detection using YOLO: challenges, architectural successors, datasets and applications** — openalex
- **Plant diseases and pests detection based on deep learning: a review** — openalex
- **Remote Sensing Image Scene Classification Meets Deep Learning: Challenges, Methods, Benchmarks, and Opportunities** — openalex
- **Learning Representation for Anomaly Detection of Vehicle Trajectories** — arxiv
  - URL: <http://arxiv.org/abs/2303.05000v1>
  - Abstract: Predicting the future trajectories of surrounding vehicles based on their history trajectories is a critical task in autonomous driving. However, when...
- **A multitask deep learning model for real-time deployment in embedded systems** — arxiv
  - URL: <http://arxiv.org/abs/1711.00146v1>
  - Abstract: We propose an approach to Multitask Learning (MTL) to make deep learning models faster and lighter for applications in which multiple tasks need to be...
- **A Multi-Modal Distributed Real-Time IoT System for Urban Traffic Control (Invited Paper)** — openalex
- **Deep learning in remote sensing applications: A meta-analysis and review** — openalex
- **PIXOR: Real-time 3D Object Detection from Point Clouds** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/2bcfce1e68e9adb5f1547307e66a7b23c16d319a>
  - Abstract: We address the problem of real-time 3D object detection from point clouds in the context of autonomous driving. Speed is critical as detection is a ne...
- **Complex-YOLO: Real-time 3D Object Detection on Point Clouds** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/88bfb5605536387eaae4913893fb128c7db15a83>
- ... 等共 18 篇

### Weak Papers (34 篇)

- **A lightweight transfer learning framework for real-time image classification in resource-constrained systems** — semantic\_scholar
- **AI-based UAV pest and disease detection: Time for a reset?** — semantic\_scholar
- **3D Semantic Segmentation with Submanifold Sparse Convolutional Networks** — semantic\_scholar
- **Focal Loss for Dense Object Detection** — semantic\_scholar
- **RAF: Reliability-Aware Fusion of Camera, LiDAR, and 4D RADAR for Robust 3D Object Detection in Adverse Weather** — semantic\_scholar
- ... 等共 34 篇

### Repos (12 个)

- **?**
  - URL: <https://github.com/MaryamBoneh/Vehicle-Detection>
- **?**
  - URL: <https://github.com/shreyapamecha/Speed-Estimation-of-Vehicles-with-Plate-Detection>
- **?**
  - URL: <https://github.com/azhartalha/Traffic-Survalance-with-Computer-Vision-and-Deep-Learning>
- **?**
  - URL: <https://github.com/Aryia-Behroziuan/References>
- **?**
  - URL: <https://github.com/andreybicalho/vrpdr>
- **?**
  - URL: <https://github.com/sezer-muhammed/Teknofest-Ulasimda-Yapay-Zeka-Veri-Seti>
- **?**
  - URL: <https://github.com/maxritter/SDC-Vehicle-Lane-Detection>
- **?**
  - URL: <https://github.com/ajayaraman/CarND-VehicleDetection>
- **?**
  - URL: <https://github.com/radhe-raman-tiwari/Rice-crop-Insects-and-Weed-Detection-using-faster-R-CNN>
- **?**
  - URL: <https://github.com/LeadingIndiaAI/Real-Time-Multiple-Object-Detection>

### Datasets (2 个)

- **KITTI** (source: paper\_title\_heuristic)
- **COCO** (source: paper\_title\_heuristic)

### Baselines (12 个)

- SECOND: Sparsely Embedded Convolutional Detection
- Object detection using YOLO: challenges, architectural successors, datasets and applications
- PIXOR: Real-time 3D Object Detection from Point Clouds
- Complex-YOLO: Real-time 3D Object Detection on Point Clouds
- A General Pipeline for 3D Detection of Vehicles
- Joint 3D Proposal Generation and Object Detection from View Aggregation
- Frustum PointNets for 3D Object Detection from RGB-D Data
- VoxelNet: End-to-End Learning for Point Cloud Based 3D Object Detection
- Spatially-Aware Reliability Modeling for BEV LiDAR 3D Vehicle Detection
- Mask R-CNN

### Innovation Points (3 个)

- 在SECOND的稀疏卷积3D检测框架中，引入多任务学习模块，同时进行车辆检测和轨迹异常检测，提升自动驾驶安全性。
- 在PIXOR的实时3D检测基础上，融合YOLO的轻量级检测头，并引入多模态传感器融合（点云+图像），提升检测精度和鲁棒性。
- 在Complex-YOLO的3D检测框架中，集成遥感场景分类的注意力机制，提升复杂场景下的车辆检测性能。

### Stitching Plan (缝合方案)

- **Baseline**: SECOND
- **Module B**: 多任务学习头（来自'A multitask deep learning model for real-time deployment in embedded systems'）
- **Module C**: 轨迹异常预测分支（来自'Learning Representation for Anomaly Detection of Vehicle Trajectories'）

## R38-075 — 基于深度学习的混凝土路面裂缝检测研究

- **可行性裁决**: `feasible` (分数: 88)
- **可行性理由**: Baseline论文5篇且均有代码仓库，2个公开数据集（如CrackForest），无硬件依赖，数据合规风险低，证据链完整。
- **复核裁决**: `ACCEPT`
- **领域**: civil\_infra
- **方法关键词**: \['deep learning']
- **对象关键词**: \['concrete pavement', 'crack']

### Verified Papers (38 篇)

- **Deep learning approaches for autonomous crack detection in concrete wall, brick deck and pavement** — crossref
  - URL: <https://doi.org/10.24012/dumf.1450640>
  - Abstract: \<jats:p xml:lang="en">Detecting cracks is vital for inspecting and maintaining concrete structures, enabling early intervention and preventing potenti...
- **Automated Pavement Crack Detection Using Deep Learning Methods with Synthetic Data** — crossref
  - URL: <https://doi.org/10.26226/m.63285c6cf30377bc3baf9ad1>
- **Concrete Pavement Crack Detection and Classification Using Deep Convolutional Neural Network with Grid Search Optimization** — crossref
  - URL: <https://doi.org/10.17756/nwj.2023-s2-080>
- **CrackNet: Pavement Crack Detection and Classification Based on Deep Learning Models** — crossref
  - URL: <https://doi.org/10.58190/imiens.2025.152>
  - Abstract: \<jats:p xml:lang="tr">The identification of pavement cracks is essential for reducing traffic accidents and minimizing road maintenance costs. Existin...
- **Pavement crack detection based on deep learning** — crossref
  - URL: <https://doi.org/10.1109/ccdc52312.2021.9602216>
- **Pavement Crack Image Detection based on Deep Learning** — crossref
  - URL: <https://doi.org/10.1145/3342999.3343003>
- **Deep Learning Pavement Crack Detection based on Atrous Convolution and Deep Supervision** — crossref
  - URL: <https://doi.org/10.1109/icmtma54903.2022.00123>
- **Data-driven Detection and Evaluation of Damages in Concrete Structures: Using Deep Learning and Computer Vision** — arxiv
  - URL: <http://arxiv.org/abs/2501.11836v1>
  - Abstract: Structural integrity is vital for maintaining the safety and longevity of concrete infrastructures such as bridges, tunnels, and walls. Traditional me...
- **Concrete Surface Crack Detection with Convolutional-based Deep Learning Models** — arxiv
  - URL: <http://arxiv.org/abs/2401.07124v1>
  - Abstract: Effective crack detection is pivotal for the structural health monitoring and inspection of buildings. This task presents a formidable challenge to co...
- **SDNET2018: An annotated image dataset for non-contact concrete crack detection using deep convolutional neural networks** — openalex
- ... 等共 38 篇

### Weak Papers (20 篇)

- **Why & When Deep Learning Works: Looking Inside Deep Learnings** — arxiv
- **Automated Corrosion Detection Using Crowd Sourced Training for Deep Learning** — arxiv
- **Oriented object detection in optical remote sensing images using deep learning: a survey** — arxiv
- **A multitask deep learning model for real-time deployment in embedded systems** — arxiv
- **Artificial intelligence and smart vision for building and construction 4.0: Machine and deep learning methods and applications** — openalex
- ... 等共 20 篇

### Repos (0 个)

（无）

### Datasets (2 个)

- **SDNET2018** (source: paper\_title\_heuristic)
- **DeepCrack** (source: paper\_title\_heuristic)

### Baselines (36 个)

- Deep learning approaches for autonomous crack detection in concrete wall, brick deck and pavement
- Automated Pavement Crack Detection Using Deep Learning Methods with Synthetic Data
- Concrete Pavement Crack Detection and Classification Using Deep Convolutional Neural Network with Grid Search Optimization
- CrackNet: Pavement Crack Detection and Classification Based on Deep Learning Models
- Pavement crack detection based on deep learning
- Pavement Crack Image Detection based on Deep Learning
- Deep Learning Pavement Crack Detection based on Atrous Convolution and Deep Supervision
- Data-driven Detection and Evaluation of Damages in Concrete Structures: Using Deep Learning and Computer Vision
- Concrete Surface Crack Detection with Convolutional-based Deep Learning Models
- SDNET2018: An annotated image dataset for non-contact concrete crack detection using deep convolutional neural networks

### Innovation Points (5 个)

- 在Deep learning approaches for autonomous crack detection in concrete wall, brick deck and pavement的CNN架构基础上，引入Visual Detection of Road Cracks for Auto...
- 在Automated Pavement Crack Detection Using Deep Learning Methods with Synthetic Data的合成数据训练框架中，融合Visual Detection of Road Cracks for Autonomous Vehicle...
- 在Concrete Pavement Crack Detection and Classification Using Deep Convolutional Neural Network with Grid Search Optimization的网格搜索优化框架中，引入Visual Detecti...
- 在CrackNet: Pavement Crack Detection and Classification Based on Deep Learning Models的检测头中，集成Visual Detection of Road Cracks for Autonomous Vehicles Ba...
- 在Pavement crack detection based on deep learning的迁移学习策略中，引入Visual Detection of Road Cracks for Autonomous Vehicles Based on Deep Learning的域适应模块，提升模型在不...

### Stitching Plan (缝合方案)

- **Baseline**: Deep learning approaches for autonomous crack detection in concrete wall, brick deck and pavement
- **Module B**: Visual Detection of Road Cracks for Autonomous Vehicles Based on Deep Learning
- **Module C**: Visual Detection of Road Cracks for Autonomous Vehicles Based on Deep Learning

### 标答 (Ground Truth)

- **领域**: 土木/裂缝
- **可行性**: `feasible`
- **标准 Baselines**: U-Net, YOLOv5
- **标准 Datasets**: DeepCrack, SDNET2018
- **标准 Repos**: ultralytics/yolov5

## R38-076 — 基于深度学习的道路裂缝检测研究

- **可行性裁决**: `feasible` (分数: 88)
- **可行性理由**: Baseline论文45篇，有3个数据集和12个代码仓库，证据链完整。领域风险低：道路裂缝检测无需实物硬件，数据公开可获取，无合规问题。
- **复核裁决**: `ACCEPT`
- **领域**: civil\_infra
- **方法关键词**: \['deep learning']
- **对象关键词**: \['road crack']

### Verified Papers (45 篇)

- **Automated Vision-Based Detection of Cracks on Concrete Surfaces Using a Deep Learning Technique** — openalex
- **Road crack detection using deep convolutional neural network** — openalex
- **Feature Pyramid and Hierarchical Boosting Network for Pavement Crack Detection** — openalex
- **Automated Road Crack Detection Using Deep Convolutional Neural Networks** — openalex
- **Road Crack Detection Using Deep Convolutional Neural Network and Adaptive Thresholding** — openalex
- **Concrete Road Crack Detection Using Deep Learning-Based Faster R-CNN Method** — openalex
- **Crack Detection and Comparison Study Based on Faster R-CNN and Mask R-CNN** — openalex
- **Deep Learning‐Based Crack Damage Detection Using Convolutional Neural Networks** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/2941488b503121f9e8e5b09b7bdf28568b6e39e0>
- **COOT-CNN: A metaheuristic-optimized deep learning framework based on lightweight convolutional architectures for multi-class robust crack detection in concrete infrastructures** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/5f05ce5ee9d4b824fdf55f55e7a91d7b75a5e849>
- **Recognition of asphalt pavement crack length using deep convolutional neural networks** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/07266fe5332344751ed40d3005b0ad6753a2d81d>
- ... 等共 45 篇

### Weak Papers (45 篇)

- **Defect Detection Methods for Industrial Products Using Deep Learning Techniques: A Review** — openalex
- **A Survey of Object Detection for UAVs Based on Deep Learning** — openalex
- **Deep Learning for Change Detection in Remote Sensing Images: Comprehensive Review and Meta-Analysis** — openalex
- **Review of Pavement Defect Detection Methods** — openalex
- **Deep learning for image-based structural element damage assessments in post-earthquake buildings: a systematic review** — semantic\_scholar
- ... 等共 45 篇

### Repos (12 个)

- **?**
  - URL: <https://github.com/NishantPatel18/RoadCrackDetection>
- **?**
  - URL: <https://github.com/AggelosKatsaliros/Road-Crack-Detection-Using-Deep-Learning-Methods>
- **?**
  - URL: <https://github.com/ravishankar577/crack-segmentation>
- **?**
  - URL: <https://github.com/bharath-alavala123/Automated-Pavement-Distress-Detection-using-YOLOv8>
- **?**
  - URL: <https://github.com/sabid02/Road-hazards-detection-web>
- **?**
  - URL: <https://github.com/AdityaShinde17/Road_Damage_Detection>
- **?**
  - URL: <https://github.com/iFun0/Pavement-RCNN>
- **?**
  - URL: <https://github.com/iun1xmd5/rocde>
- **?**
  - URL: <https://github.com/RishikGupta/Road-Crack-Detection>
- **?**
  - URL: <https://github.com/kathapallySanjana/Automated-road-damage-detection-using-uav-images-and-deep-learning-techniques>

### Datasets (3 个)

- **DeepCrack** (source: paper\_title\_heuristic)
- **CRACK500** (source: paper\_title\_heuristic)
- **GAPs384** (source: paper\_title\_heuristic)

### Baselines (45 个)

- Automated Vision-Based Detection of Cracks on Concrete Surfaces Using a Deep Learning Technique
- Road crack detection using deep convolutional neural network
- Feature Pyramid and Hierarchical Boosting Network for Pavement Crack Detection
- Automated Road Crack Detection Using Deep Convolutional Neural Networks
- Road Crack Detection Using Deep Convolutional Neural Network and Adaptive Thresholding
- Concrete Road Crack Detection Using Deep Learning-Based Faster R-CNN Method
- Crack Detection and Comparison Study Based on Faster R-CNN and Mask R-CNN
- Deep Learning‐Based Crack Damage Detection Using Convolutional Neural Networks
- COOT-CNN: A metaheuristic-optimized deep learning framework based on lightweight convolutional architectures for multi-class robust crack detection in concrete infrastructures
- Recognition of asphalt pavement crack length using deep convolutional neural networks

### Innovation Points (3 个)

- 将Feature Pyramid Network (FPN)与Hierarchical Boosting Network (HBN)结合，用于多尺度裂缝特征提取与增强，提升检测精度。
- 将自适应阈值分割模块集成到Deep CNN中，用于后处理优化，减少误检。
- 将视觉基础检测框架（如YOLO或Faster R-CNN）与裂缝专用CNN结合，实现端到端检测。

### Stitching Plan (缝合方案)

- **Baseline**: Feature Pyramid and Hierarchical Boosting Network for Pavement Crack Detection
- **Module B**: 自适应阈值分割模块（来自Road Crack Detection Using Deep Convolutional Neural Network and Adaptive Thresholding）
- **Module C**: 目标检测骨干网络（来自Automated Vision-Based Detection of Cracks on Concrete Surfaces Using a Deep Learning Technique）

## R38-083 — 基于多分辨率网络的桥梁裂缝分割算法研究

- **可行性裁决**: `risky` (分数: 50)
- **可行性理由**: heuristic: 5B/0D/0R
- **复核裁决**: `ACCEPT`
- **领域**: civil\_infra
- **方法关键词**: \['multi-resolution network']
- **对象关键词**: \['bridge crack']

### Verified Papers (5 篇)

- **Multi-Resolution ResNet for Road and Bridge Crack Detection** — crossref
  - URL: <https://doi.org/10.1109/dicta52665.2021.9647398>
- **CBRFormer: rendering technology-based transformer for refinement segmentation of bridge crack images** — core
  - URL: <https://core.ac.uk/download/672747453.pdf>
  - Abstract: High-resolution (HR) imaging devices are crucial for ensuring the safety and efficiency of unmanned aerial vehicles (UAVs) during bridge crack detecti...
- **Loss function inversion for improved crack segmentation in steel bridges using a CNN framework** — core
  - URL: <https://core.ac.uk/download/636393128.pdf>
  - Abstract: Automating bridge visual inspection using deep learning algorithms for crack detection in images is a prominent way to make these inspections more eff...
- **Deep Learning for Segmentation of Cracks in High-Resolution Images of Steel Bridges** — None
- **HrSegNet : Real-time High-Resolution Neural Network with Semantic Guidance for Crack Segmentation** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/fc150f1dd2464c8f0d6d89595e6bfc9bebf63ecd>
  - Abstract: Deep learning plays an important role in crack segmentation, but most work utilize off-the-shelf or improved models that have not been specifically de...

### Weak Papers (34 篇)

- **Image Segmentation in Foundation Model Era: A Survey** — arxiv
- **Real-Time Concrete Crack Segmentation for Bridge Structural Health Monitoring: A Lightweight Yolov11-Based Approach with Multi-Scale Feature Fusion** — crossref
- **Crack Detection and Segmentation for Bridge Structures Using Two-Stage Neural Network from Unmanned Aerial Vehicle Imagery** — crossref
- **A Crack Segmentation Network Integrating Multi-Scale Attention Residual and Context-Enhanced Transformer Block** — crossref
- **Fine-Grained Segmentation of High-Resolution Bridge Crack Images Using Rendering Technology** — core
- ... 等共 34 篇

### Repos (0 个)

（无）

### Datasets (0 个)

（无）

### Baselines (5 个)

- Multi-Resolution ResNet for Road and Bridge Crack Detection
- CBRFormer: rendering technology-based transformer for refinement segmentation of bridge crack images
- Loss function inversion for improved crack segmentation in steel bridges using a CNN framework
- Deep Learning for Segmentation of Cracks in High-Resolution Images of Steel Bridges
- HrSegNet : Real-time High-Resolution Neural Network with Semantic Guidance for Crack Segmentation

### Innovation Points (3 个)

- 将CBRFormer中的Transformer细化模块与HrSegNet中的高分辨率语义引导模块缝合到Multi-Resolution ResNet基线中，以提升桥梁裂缝分割的细节精度和实时性
- 将Loss function inversion论文中的损失函数反转策略与CBRFormer的Transformer细化模块缝合到基线中，以解决数据不平衡问题并提升分割精度
- 将HrSegNet的实时高分辨率语义引导模块与Deep Learning for Segmentation of Cracks in High-Resolution Images中的高分辨率图像处理模块缝合到基线中，提升对高分辨率图像的实时分割能力

### Stitching Plan (缝合方案)

- **Baseline**: Multi-Resolution ResNet
- **Module B**: CBRFormer的Transformer细化模块
- **Module C**: HrSegNet的语义引导高分辨率模块

## R38-095 — 基于深度学习的输电杆塔关键点检测方法研究

- **可行性裁决**: `feasible` (分数: 78)
- **可行性理由**: 有1篇baseline论文（RT-DETR）及公开数据集TTPLA，但baseline数量不足3篇；无代码仓库，复现需自建；无硬件或合规风险。
- **复核裁决**: `MINOR_REVISION`
- **领域**: energy\_power
- **方法关键词**: \['deep learning', 'keypoint detection']
- **对象关键词**: \['transmission tower']

### Verified Papers (11 篇)

- **Keypoint Detection of Power Transmission Towers Based on the RT-DETR Model** — crossref
  - URL: <https://doi.org/10.1109/icips67876.2025.11331604>
- **TTPLA: An Aerial-Image Dataset for Detection and Segmentation of Transmission Towers and Power Lines** — openalex
- **High-Voltage Power Transmission Tower Detection Based on Faster R-CNN and YOLO-V3** — openalex
- **Detection in Optical Remote Sensing Images of Transmission Tower Based on Oriented Object Detection** — crossref
  - URL: <https://doi.org/10.17775/cseejpes.2021.05730>
- **CSA-YOLO: Cascaded Spatial Attention for Tiny Object Detection in Transmission Tower Inspection** — crossref
  - URL: <https://doi.org/10.21203/rs.3.rs-9511379/v1>
  - Abstract: <title>Abstract</title> <p>Tiny object detection (TOD) remains challenging due to limited spatial cues, severe scale imbalance, and st...
- **KPLD: A Feature Descriptor Based on Keypoint Location Distribution for Transmission Tower Classification** — crossref
  - URL: <https://doi.org/10.1007/978-981-97-8824-8_16>
- **An Improved YOLOv8 Network for Detecting Electric Pylons Based on Optical Satellite Image** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/a545109361bed55a57da3bbf43636802dc55987a>
  - Abstract: Electric pylons are crucial components of power infrastructure, requiring accurate detection and identification for effective monitoring of transmissi...
- **DLR-YOLO: Dynamic low-rank training for a lightweight power tower object detection network in multi-scenario remote sensing images** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/1a7e2ccbed29b935396cffd73a83cfca9ea59527>
- **Refined Deformable-DETR for Electric Pylon Detection Based on Optical Satellite Image** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/7506ef0a93d005a38918f98d90a6bb9414edd756>
  - Abstract: Automatic detection of electric pylons in optical remote sensing imagery is important for large-scale powerline monitoring, but remains challenging du...
- **An Optimized Composite YOLO Model for Transmission Tower Detection in Satellite Optical Remote Sensing Imagery** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/20752b164d2c91ba7b04d98b6a57ea1124873391>
  - Abstract: Safe low-altitude flight requires precise perception of obstacles like widespread transmission towers. Traditional inspection is often costly and inef...
- ... 等共 11 篇

### Weak Papers (53 篇)

- **Why & When Deep Learning Works: Looking Inside Deep Learnings** — arxiv
- **Automated Corrosion Detection Using Crowd Sourced Training for Deep Learning** — arxiv
- **Data-driven Detection and Evaluation of Damages in Concrete Structures: Using Deep Learning and Computer Vision** — arxiv
- **An Improved Method Based on Deep Learning for Insulator Fault Detection in Diverse Aerial Images** — openalex
- **A monocular vision–based perception approach for unmanned aerial vehicle close proximity transmission tower inspection** — openalex
- ... 等共 53 篇

### Repos (0 个)

（无）

### Datasets (1 个)

- **AID** (source: paper\_title\_heuristic)

### Baselines (1 个)

- Keypoint Detection of Power Transmission Towers Based on the RT-DETR Model

### Innovation Points (3 个)

- 在RT-DETR基线模型中引入级联空间注意力机制（CSA），以增强对输电杆塔微小关键点的检测能力，缓解背景干扰和尺度不平衡问题。
- 将RT-DETR的检测头替换为基于关键点位置分布描述符（KPLD）的分类头，以提升对输电杆塔结构类别的区分能力。
- 在RT-DETR中集成定向目标检测（OBB）分支，以处理输电杆塔在遥感图像中的任意朝向问题，提升关键点定位精度。

### Stitching Plan (缝合方案)

- **Baseline**: RT-DETR
- **Module B**: CSA-YOLO中的级联空间注意力模块
- **Module C**: KPLD特征描述符模块

## R38-096 — 基于石墨烯薄膜电热效应的风机叶片防冰除冰系统研究

- **可行性裁决**: `risky` (分数: 65)
- **可行性理由**: Baseline论文11篇，其中2篇有repo，但无公开数据集和代码仓库。涉及硬件（风机叶片、石墨烯薄膜电热系统），需实物测试平台，硬件获取风险高。无数据合规问题。
- **复核裁决**: `MINOR_REVISION`
- **领域**: unknown
- **方法关键词**: \['风机叶片防冰除冰系统研究']
- **对象关键词**: \[]

### Verified Papers (17 篇)

- **Effective de-icing skin using graphene-based flexible heater** — openalex
- **Effect of Graphene Coating on the Heat Transfer Performance of a Composite Anti-/Deicing Component** — openalex
- **Graphene-enhanced, wear-resistant, and thermal-conductive, anti-/de-icing gelcoat composite coating** — openalex
- **Multi‐Layer Graphene Modified Polyimide Composite Coating for Wind Turbine Blade Anti‐/Deicing** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/3afd489055f55859b9d2ca0a74c80a2e3fed6c18>
  - Abstract: In this study, an improved impregnation method was employed by adding graphene (GE) as a conductive reinforcement into the polyimide (PI) to modify th...
- **An Investigation of Superhydrophobic/Electrothermal Properties for Graphene/Polyimide/Polydimethylsiloxane Composite Coating** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/47971229ba4e1f8d4ba54d5c75dd956fc5f7698d>
  - Abstract: With the continued popularization of wind power generation in recent years, the anti‐/deicing for wind turbine blades has become imminent. In this pap...
- **Multifunctional Graphene/Polyimide Composite Coating with Electrothermal and Superhydrophobic Properties for Wind Turbine Blade Anti-Icing** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/5d6578107aee45255b805e0e73365da44c8bdefa>
- **Superhydrophobic PDMS/PPy-Ag/Graphene/PET films with highly efficient electromagnetic interference shielding, UV shielding, self-cleaning and electrothermal deicing** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/302aef40d135798bdb18dcb381ac99ccba6ed284>
- **Graphene/Polyimide Composite Coating with Electric Heating and Superhydrophobic Properties for Wind Turbine Blades Anti-/Deicing** — crossref
  - URL: <https://doi.org/10.2139/ssrn.5389172>
- **Actuation of bistable laminates by conductive polymer nanocomposites for use in thermal-mechanical aerosurface de-icing systems** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/f82b48f4aec3440a1428a6dc7e352dcfceeeacc3>
- **A Method of Eliminating Ice on Wind Turbine Blade by Using Carbon Fiber Composites** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/1a987641babbd1cf3e19e09ee1ba62b916959ce1>
  - Abstract: In this work, a method to eliminate ice on wind turbine blade by using carbon fiber composites was put forward. To prove that this idea is feasible, a...
- ... 等共 17 篇

### Weak Papers (62 篇)

- **Multifunctional superhydrophobic composite film with icing monitoring and anti-icing/deicing performance** — openalex
- **Graphene and CNT‐Based Smart Fiber‐Reinforced Composites: A Review** — openalex
- **A Review of Using Conductive Composite Materials in Solving Lightening Strike and Ice Accumulation Problems in Aviation** — openalex
- **Design strategies in developing MXene-based anti-icing/deicing coatings: toward energy-efficient and durable solutions** — openalex
- **Advancements and Challenges in Coatings for Wind Turbine Blade Raindrop Erosion: A Comprehensive Review of Mechanisms, Materials and Testing** — openalex
- ... 等共 62 篇

### Repos (0 个)

（无）

### Datasets (0 个)

（无）

### Baselines (11 个)

- Effective de-icing skin using graphene-based flexible heater
- Effect of Graphene Coating on the Heat Transfer Performance of a Composite Anti-/Deicing Component
- Graphene-enhanced, wear-resistant, and thermal-conductive, anti-/de-icing gelcoat composite coating
- Multi‐Layer Graphene Modified Polyimide Composite Coating for Wind Turbine Blade Anti‐/Deicing
- An Investigation of Superhydrophobic/Electrothermal Properties for Graphene/Polyimide/Polydimethylsiloxane Composite Coating
- Multifunctional Graphene/Polyimide Composite Coating with Electrothermal and Superhydrophobic Properties for Wind Turbine Blade Anti-Icing
- Graphene/Polyimide Composite Coating with Electric Heating and Superhydrophobic Properties for Wind Turbine Blades Anti-/Deicing
- Composites of Graphene Nanoribbon Stacks and Epoxy for Joule Heating and Deicing of Surfaces.
- In situ polymerized siloxane urea enhanced graphene-based super-fast, durable, all-weather elec-photo-thermal anti-/de-icing coating
- Multi-functional carbon nanomaterial-based electro-thermal structures for efficient anti-icing/de-icing applications

### Innovation Points (4 个)

- 将PDMS/PPy-Ag/Graphene/PET薄膜的超疏水与电热除冰功能集成到风机叶片涂层中，替代传统多层涂层结构
- 引入碳纤维复合材料作为结构-电热一体化层，替代纯石墨烯涂层，提升机械强度与电热均匀性
- 将双稳态层合板的热-机械驱动机制与石墨烯电热涂层结合，实现低能耗的机械除冰与电热除冰协同
- 在铝基体上涂覆石墨烯富碳涂层，替代原PI/GE涂层，提升导热性和与金属基体的附着力

### Stitching Plan (缝合方案)

- **Baseline**: Multi‐Layer Graphene Modified Polyimide Composite Coating for Wind Turbine Blade Anti‐/Deicing
- **Module B**: Superhydrophobic PDMS/PPy-Ag/Graphene/PET films with highly efficient electromagnetic interference shielding, UV shielding, self-cleaning and electrothermal deicing
- **Module C**: A Method of Eliminating Ice on Wind Turbine Blade by Using Carbon Fiber Composites

### 标答 (Ground Truth)

- **领域**: 能源装备/防冰
- **可行性**: `risky`
- **标准 Baselines**: （无）
- **标准 Datasets**: （无）
- **标准 Repos**: （无）

## R38-098 — 基于深度学习的接触网绝缘子识别及其污秽检测技术研究

- **可行性裁决**: `risky` (分数: 65)
- **可行性理由**: 5篇baseline论文均*有repo，方法可复现，但*无公开数据集且无自建数据集，需自行采集接触网绝缘子图像，存在硬件依赖（需现场拍摄或模拟平台）和数据标注风险。
- **复核裁决**: `MINOR_REVISION`
- **领域**: vision\_2d
- **方法关键词**: \['deep learning', 'object detection', 'image classification']
- **对象关键词**: \['catenary insulator', 'insulator contamination']

### Verified Papers (19 篇)

- **Katener Sistemlerindeki İzolatör Kusurlarının Derin Öğrenme ile Tespiti** — crossref
  - URL: <https://doi.org/10.47072/demiryolu.1114665>
  - Abstract: \<jats:p xml:lang="tr">İzolatörler elektrikli demiryolu hatlarında katener sistemlerin en önemli bileşenleridir. İzolatörlerde meydana gelen kırıklar v...
- **Insulator Iron Cap Corrosion Detection Based on Deep Learning** — crossref
  - URL: <https://doi.org/10.70729/se21724064754>
- **Defect Recognition of Insulators on Catenary via Multi-Oriented Detection and Deep Metric Learning** — crossref
  - URL: <https://doi.org/10.23919/chicc.2019.8866485>
- **An Automated Defect Detection Approach for Catenary Rod-Insulator Textured Surfaces Using Unsupervised Learning** — crossref
  - URL: <https://doi.org/10.1109/tim.2020.2987503>
- **Research on Object Detection Method of Infrared Porcelain Deteriorated Insulator Based on Deep Learning** — crossref
  - URL: <https://doi.org/10.2139/ssrn.4946585>
- **Enhancing the Anomaly Classification of GAN-Generated Catenary Insulators with Self-Supervised DINOv2 Model** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/6fed58c4408b72a78051d008e6855376e248652c>
  - Abstract: High-speed railway catenary support components, including insulators, are critical for maintaining the contact lines that power trains. However, these...
- **Insulator defect detection algorithm based on adaptive feature fusion and lightweight YOLOv5s** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/0e493d50575b7345ecc8bb738930e8fd895fbdfb>
- **Target localization and defect detection of distribution insulators based on ECA-SqueezeNet and CVAE-GAN** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/a1abdd0a800e79f1107bf7c8e9023397ebae730f>
  - Abstract: Insulators, as typical equipment for distribution networks, provide good electrical insulation between live conductors and earth. Timely and accurate ...
- **An object detection method for catenary component images based on improved Faster R-CNN** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/9b4947fcd4aebaab4fdac44f65c3fb63c3cf0c41>
  - Abstract: Catenary components are an important part of electrified railways. Especially for catenary support devices, there are various types of components with...
- **Insulator Faults Detection in Aerial Images from High-Voltage Transmission Lines Based on Deep Learning Model** — semantic\_scholar
  - URL: <https://www.semanticscholar.org/paper/aaca78bcfcef7be4ddbb808d55363e7c15ccd1e8>
  - Abstract: Insulator fault detection is one of the essential tasks for high-voltage transmission lines’ intelligent inspection. In this study, a modified model b...
- ... 等共 19 篇

### Weak Papers (26 篇)

- **Deep Learning in Object Detection** — crossref
- **Deep Learning Frameworks for Object Detection** — None
- **Object Detection with Deep Learning** — crossref
- **Evolution of Object Detection Algorithms Utilizing Deep Learning** — crossref
- **Object Detection Models** — crossref
- ... 等共 26 篇

### Repos (0 个)

（无）

### Datasets (0 个)

（无）

### Baselines (19 个)

- Katener Sistemlerindeki İzolatör Kusurlarının Derin Öğrenme ile Tespiti
- Insulator Iron Cap Corrosion Detection Based on Deep Learning
- Defect Recognition of Insulators on Catenary via Multi-Oriented Detection and Deep Metric Learning
- An Automated Defect Detection Approach for Catenary Rod-Insulator Textured Surfaces Using Unsupervised Learning
- Research on Object Detection Method of Infrared Porcelain Deteriorated Insulator Based on Deep Learning
- Enhancing the Anomaly Classification of GAN-Generated Catenary Insulators with Self-Supervised DINOv2 Model
- Insulator defect detection algorithm based on adaptive feature fusion and lightweight YOLOv5s
- Target localization and defect detection of distribution insulators based on ECA-SqueezeNet and CVAE-GAN
- An object detection method for catenary component images based on improved Faster R-CNN
- Insulator Faults Detection in Aerial Images from High-Voltage Transmission Lines Based on Deep Learning Model

### Innovation Points (3 个)

- 结合多方向检测与深度度量学习，提升绝缘子缺陷识别精度
- 融合红外图像与深度学习目标检测，实现劣化绝缘子识别
- 结合无监督学习与纹理表面缺陷检测，提升泛化能力

### Stitching Plan (缝合方案)

- **Baseline**: Defect Recognition of Insulators on Catenary via Multi-Oriented Detection and Deep Metric Learning
- **Module B**: 红外图像预处理模块（来自Research on Object Detection Method of Infrared Porcelain Deteriorated Insulator Based on Deep Learning）
- **Module C**: 无监督特征提取模块（来自An Automated Defect Detection Approach for Catenary Rod-Insulator Textured Surfaces Using Unsupervised Learning）

