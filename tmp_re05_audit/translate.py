"""Translate English academic titles to short Chinese meanings deterministically.

Built-in phrase map for the most common Acronym + Token patterns seen in
Balanced40. Falls back to (中文含义由英文派生) when no rule matches — the audit
report still shows the English title verbatim so the reader always has ground truth.
"""
import re

# Order matters: longer / more specific keys must come first.
# Each entry is a (regex, replacement) pair.
_TOKEN_RULES: list[tuple[re.Pattern, str]] = [
    # SLAM / VO / 3D Vision
    (re.compile(r"\bSLAM\b", re.I), "SLAM"),
    (re.compile(r"\bSLAM Book\b", re.I), "SLAM 十四讲"),
    (re.compile(r"\bVisual Odometry\b", re.I), "视觉里程计"),
    (re.compile(r"\bVisual[-\s]Inertial\b", re.I), "视觉惯性"),
    (re.compile(r"\bORB[-\s]?SLAM\b", re.I), "ORB-SLAM"),
    (re.compile(r"\bPoint Cloud(?:s)?\b", re.I), "点云"),
    (re.compile(r"\bPoint Cloud Registration\b", re.I), "点云配准"),
    (re.compile(r"\bPoint Cloud Completion\b", re.I), "点云补全"),
    (re.compile(r"\b3D\b", re.I), "三维"),
    (re.compile(r"\bMulti[-\s]?View\b", re.I), "多视图"),
    (re.compile(r"\bRGB[-\s]?D\b", re.I), "RGB-D"),
    (re.compile(r"\bLiDAR\b", re.I), "激光雷达"),
    (re.compile(r"\bLoop Closure\b", re.I), "回环检测"),
    (re.compile(r"\bSemantic(?:s)?\b", re.I), "语义"),
    # Detection / recognition
    (re.compile(r"\bObject Detection\b", re.I), "目标检测"),
    (re.compile(r"\bSmall Object(?:s)?\b", re.I), "小目标"),
    (re.compile(r"\bLane Detection\b", re.I), "车道线检测"),
    (re.compile(r"\bTraffic (?:Sign|Sign|signs?)\b", re.I), "交通标志"),
    (re.compile(r"\bAircraft\b", re.I), "飞机"),
    (re.compile(r"\bVehicle(?:s)?\b", re.I), "车辆"),
    (re.compile(r"\bPedestrian\b", re.I), "行人"),
    (re.compile(r"\bInsulator(?:s)?\b", re.I), "绝缘子"),
    (re.compile(r"\bCrack(?:s)?\b", re.I), "裂缝"),
    (re.compile(r"\bDefect(?:s)?\b", re.I), "缺陷"),
    (re.compile(r"\bDetection\b", re.I), "检测"),
    (re.compile(r"\bRecognition\b", re.I), "识别"),
    (re.compile(r"\bClassification\b", re.I), "分类"),
    (re.compile(r"\bSegmentation\b", re.I), "分割"),
    (re.compile(r"\bTracking\b", re.I), "跟踪"),
    (re.compile(r"\bReconstruction\b", re.I), "重建"),
    (re.compile(r"\bRegistration\b", re.I), "配准"),
    # Deep Learning / training
    (re.compile(r"\bDeep Learning\b", re.I), "深度学习"),
    (re.compile(r"\bDeep (?:Residual|Convolutional)\b", re.I), "深度残差卷积"),
    (re.compile(r"\bConv(?:olution|olutional)?\b", re.I), "卷积"),
    (re.compile(r"\bNeural Network(?:s)?\b", re.I), "神经网络"),
    (re.compile(r"\bGraph Neural Network(?:s)?\b", re.I), "图神经网络"),
    (re.compile(r"\bTransformer(?:s)?\b", re.I), "Transformer"),
    (re.compile(r"\bSelf[-\s]?supervised\b", re.I), "自监督"),
    (re.compile(r"\bUnsupervised\b", re.I), "无监督"),
    (re.compile(r"\bSupervised\b", re.I), "有监督"),
    (re.compile(r"\bGenerative Adversarial Network(?:s)?\b", re.I), "生成对抗网络 GAN"),
    (re.compile(r"\bGAN\b"), "GAN"),
    (re.compile(r"\bDiffusion\b", re.I), "扩散模型"),
    (re.compile(r"\bContrastive\b", re.I), "对比学习"),
    (re.compile(r"\bTransfer Learning\b", re.I), "迁移学习"),
    (re.compile(r"\bFew[-\s]?shot\b", re.I), "少样本"),
    (re.compile(r"\bMulti[-\s]?task\b", re.I), "多任务"),
    # Datasets / surveys
    (re.compile(r"\bSurvey\b", re.I), "综述"),
    (re.compile(r"\bBenchmark\b", re.I), "基准"),
    (re.compile(r"\bDataset\b", re.I), "数据集"),
    (re.compile(r"\bA(?:wesome)?[-\s]?List\b", re.I), "awesome 清单"),
    # Specific methods / repos
    (re.compile(r"\bYOLO(?:v\d(?:[a-z])?)?\b", re.I), "YOLO 实时目标检测"),
    (re.compile(r"\bMask R[-\s]?CNN\b", re.I), "Mask R-CNN"),
    (re.compile(r"\bFaster R[-\s]?CNN\b", re.I), "Faster R-CNN"),
    (re.compile(r"\bU[-\s]?Net\b", re.I), "U-Net"),
    (re.compile(r"\bResNet\b", re.I), "ResNet"),
    (re.compile(r"\bPointNet(?:\+\+)?\b", re.I), "PointNet"),
    (re.compile(r"\bDCP\b"), "DCP 深度最近点"),
    (re.compile(r"\bICP\b"), "ICP"),
    (re.compile(r"\bMamba\b", re.I), "Mamba"),
    (re.compile(r"\bViT\b"), "Vision Transformer"),
    (re.compile(r"\bDETR\b"), "DETR 目标检测"),
    (re.compile(r"\bSMPL\b"), "SMPL 人体参数化"),
    (re.compile(r"\bKinect\b", re.I), "Kinect 深度相机"),
    (re.compile(r"\bNeRF\b"), "NeRF 神经辐射场"),
    (re.compile(r"\b3D Gaussian Splatting\b", re.I), "3D 高斯泼溅"),
    (re.compile(r"\bLight[-\s]?Detection And Ranging\b", re.I), "激光雷达"),
    # Misc
    (re.compile(r"\bSelf[-\s]?Driving\b", re.I), "自动驾驶"),
    (re.compile(r"\bAutonomous Driving\b", re.I), "自动驾驶"),
    (re.compile(r"\bCar\b", re.I), "汽车"),
    (re.compile(r"\bRoad\b", re.I), "道路"),
    (re.compile(r"\bRobot(?:ic|s)?\b", re.I), "机器人"),
    (re.compile(r"\bManipulator\b", re.I), "机械臂"),
    (re.compile(r"\bDynamic(?:s)?\b", re.I), "动态"),
    (re.compile(r"\bEmbedded\b", re.I), "嵌入式"),
    (re.compile(r"\bRealtime|Real[-\s]?time\b", re.I), "实时"),
    (re.compile(r"\bLightweight\b", re.I), "轻量化"),
    (re.compile(r"\bMobile\b", re.I), "移动"),
    # Noise tokens to flag
    (re.compile(r"\bAGN\b"), "AGN (天文主动星系核，强噪声)"),
    (re.compile(r"\bJATS\b"), "JATS (XML 出版标准，强噪声)"),
    (re.compile(r"\bBoötes\b", re.I), "Boötes 天文巡天 (强噪声)"),
]

# Tool / framework / repo abbreviations — kept verbatim
_VERBATIM_TOKENS = {
    "RGB-D", "ORB-SLAM", "YOLOv5", "YOLOv7", "YOLOX", "DETR", "Mamba",
    "NeRF", "GAN", "DCP", "ICP", "SMPL", "ViT", "OKVIS2-X", "TJU-DHD",
    "MLP-SLAM", "PL-VINS", "DS-SLAM", "DBLD-SLAM", "VAR-SLAM",
    "DynoSAM", "ViSTA-SLAM", "OKVIS", "CMake", "ROS", "AGV",
}


def translate_title_to_zh(title: str) -> str:
    """Quick deterministic translator for English academic titles -> 中文含义."""
    if not title:
        return "(中文含义由英文派生)"

    # If this looks like a repo path (contains / or endswith .git / no spaces),
    # keep verbatim.
    if "/" in title and ("/" in title[:40]) and " " not in title[:50]:
        return f"仓库 {title}"

    t = title
    # Strip leading articles
    t = re.sub(r"^(?:The|A|An)\s+", "", t)
    t = t.replace(" — ", "—").replace(" - ", "—")

    out = t
    for pat, rep in _TOKEN_RULES:
        out = pat.sub(rep, out)

    # Heuristics for repeated phrases
    out = out.replace("  ", " ").strip()

    # If output is empty or unchanged, fallback
    if not out or out == title:
        return "(中文含义由英文派生)"
    return out
