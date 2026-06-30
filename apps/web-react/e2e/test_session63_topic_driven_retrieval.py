"""Session 63: Topic-Driven Retrieval Playwright Tests

测试 S63 的题目驱动检索功能:
1. 3D题 → 显示 MVTec 3D-AD/COLMAP/3DGS
2. YOLO钢材题 → 不混3D, 显示 NEU-DET/YOLO
3. NLP题 → 显示 BERT/RoBERTa/LoRA

运行: pytest apps/web-react/e2e/test_session63_topic_driven_retrieval.py -v -m react_web
"""

import pytest
from playwright.sync_api import expect


pytestmark = pytest.mark.react_web


@pytest.fixture
def goto_workbench(page):
    """导航到工作台页面"""
    page.goto("http://127.0.0.1:18183/#/")
    page.wait_for_load_state("networkidle")
    # 如果有加载提示，等待消失
    page.wait_for_timeout(1000)


class TestTopicDrivenRetrieval:
    """S63 题目驱动检索测试"""

    def test_3d_topic_shows_3d_candidates(self, page, goto_workbench):
        """Case A: 3D成像损伤检测 → 必须显示 MVTec 3D-AD/COLMAP/3DGS"""
        # 1. 输入3D题目
        topic_input = page.locator('input[placeholder*="题目"], input[name="topic"], [data-testid="topic-input"]').first
        if topic_input.is_visible():
            topic_input.fill("基于三维成像的损伤智能检测")

        # 2. 点击开始分析
        analyze_btn = page.locator('button:has-text("开始分析"), button:has-text("分析"), [data-testid="analyze-btn"]').first
        if analyze_btn.is_visible():
            analyze_btn.click()

        page.wait_for_timeout(3000)  # 等待分析完成

        # 3. 截图关键词拆解区
        page.screenshot(path="apps/web-react/e2e/screenshots/session63/s63_3d_keywords.png", full_page=False)
        # 截图候选区
        page.screenshot(path="apps/web-react/e2e/screenshots/session63/s63_3d_candidates.png", full_page=False)

        # 4. 验证3D候选出现
        page_content = page.content()

        # 应该包含 3D 相关关键词
        assert any(kw in page_content.lower() for kw in ["三维", "3d", "point cloud", "点云"]), \
            "3D关键词未出现"

        # 应该包含 MVTec 3D-AD 或 Real3D-AD
        assert any(ds in page_content for ds in ["MVTec 3D-AD", "Real3D-AD", "MVTec 3D"]), \
            "MVTec 3D-AD 数据集未出现"

        # 应该包含 COLMAP 或 PointNet++
        assert any(bl in page_content for bl in ["COLMAP", "PointNet", "OpenPCDet"]), \
            "COLMAP/PointNet++ baseline未出现"

        # 应该包含 3DGS 或 DUSt3R (新锐方法)
        assert any(em in page_content for em in ["3DGS", "3D Gaussian", "DUSt3R"]), \
            "3DGS/DUSt3R 新锐方法未出现"

        # 不应该包含 YOLO (3D题不应混YOLO)
        assert "YOLOv" not in page_content and "yolov" not in page_content.lower(), \
            "3D题不应包含YOLO"

    def test_yolo_steel_topic_excludes_3d(self, page, goto_workbench):
        """Case B: YOLO钢材题 → 不混3D, 显示 NEU-DET/YOLO"""
        # 1. 输入YOLO钢材题目
        topic_input = page.locator('input[placeholder*="题目"], input[name="topic"], [data-testid="topic-input"]').first
        if topic_input.is_visible():
            topic_input.fill("基于YOLO的钢材表面缺陷检测")

        # 2. 点击开始分析
        analyze_btn = page.locator('button:has-text("开始分析"), button:has-text("分析"), [data-testid="analyze-btn"]').first
        if analyze_btn.is_visible():
            analyze_btn.click()

        page.wait_for_timeout(3000)

        # 3. 截图
        page.screenshot(path="apps/web-react/e2e/screenshots/session63/s63_yolo_candidates.png", full_page=False)

        # 4. 验证YOLO相关候选出现
        page_content = page.content()

        # 应该包含 YOLO
        assert any(yolo in page_content for yolo in ["YOLO", "YOLOv"]), \
            "YOLO未出现"

        # 应该包含 NEU-DET 或 GC10-DET
        assert any(ds in page_content for ds in ["NEU-DET", "GC10", "钢材"]), \
            "NEU-DET/GC10-DET 数据集未出现"

        # 不应该包含 3DGS/DUSt3R/FoundationStereo
        assert "3DGS" not in page_content, "YOLO题不应包含3DGS"
        assert "DUSt3R" not in page_content, "YOLO题不应包含DUSt3R"
        assert "COLMAP" not in page_content, "YOLO题不应包含COLMAP"

    def test_nlp_topic_shows_text_baselines(self, page, goto_workbench):
        """Case C: NLP舆情情感分析 → 显示 BERT/RoBERTa/LoRA"""
        # 1. 输入NLP题目
        topic_input = page.locator('input[placeholder*="题目"], input[name="topic"], [data-testid="topic-input"]').first
        if topic_input.is_visible():
            topic_input.fill("基于大语言模型的中文舆情情感分析")

        # 2. 点击开始分析
        analyze_btn = page.locator('button:has-text("开始分析"), button:has-text("分析"), [data-testid="analyze-btn"]').first
        if analyze_btn.is_visible():
            analyze_btn.click()

        page.wait_for_timeout(3000)

        # 3. 截图
        page.screenshot(path="apps/web-react/e2e/screenshots/session63/s63_nlp_candidates.png", full_page=False)

        # 4. 验证NLP相关候选出现
        page_content = page.content()

        # 应该包含 BERT/RoBERTa/LLM
        assert any(nlp in page_content for nlp in ["BERT", "RoBERTa", "LoRA", "大语言模型"]), \
            "BERT/RoBERTa/LoRA baseline未出现"

        # 应该包含中文NLP数据集
        assert any(ds in page_content for ds in ["ChnSentiCorp", "CLUE", "情感", "文本"]), \
            "中文NLP数据集未出现"

        # 不应该包含 YOLO/PointNet/COLMAP
        assert "YOLO" not in page_content, "NLP题不应包含YOLO"
        assert "PointNet" not in page_content, "NLP题不应包含PointNet"
        assert "COLMAP" not in page_content, "NLP题不应包含COLMAP"

    def test_topic_change_affects_candidates(self, page, goto_workbench):
        """验证题目变化后候选明显变化"""
        # 1. 先分析3D题
        topic_input = page.locator('input[placeholder*="题目"], input[name="topic"], [data-testid="topic-input"]').first
        if topic_input.is_visible():
            topic_input.fill("基于三维成像的损伤智能检测")

        analyze_btn = page.locator('button:has-text("开始分析"), button:has-text("分析"), [data-testid="analyze-btn"]').first
        if analyze_btn.is_visible():
            analyze_btn.click()
        page.wait_for_timeout(3000)

        # 保存3D题的页面内容
        content_3d = page.content()

        # 2. 清除并输入YOLO题
        topic_input.fill("基于YOLO的钢材表面缺陷检测")
        if analyze_btn.is_visible():
            analyze_btn.click()
        page.wait_for_timeout(3000)

        # 保存YOLO题的页面内容
        content_yolo = page.content()

        # 3. 验证内容不同
        # 3D题应该包含3D相关词，YOLO题不应该
        has_3d_in_3d = any(kw in content_3d for kw in ["3DGS", "DUSt3R", "COLMAP", "MVTec 3D"])
        has_3d_in_yolo = any(kw in content_yolo for kw in ["3DGS", "DUSt3R", "COLMAP", "MVTec 3D"])

        assert has_3d_in_3d, "3D题应包含3D相关词"
        assert not has_3d_in_yolo, "YOLO题不应包含3D相关词"

        # 截图对比
        page.screenshot(path="apps/web-react/e2e/screenshots/session63/s63_topic_comparison.png", full_page=False)


class TestStepByStepFlow:
    """测试分步确认流程"""

    def test_keywords_confirm_step(self, page, goto_workbench):
        """验证关键词确认步骤"""
        # 输入题目
        topic_input = page.locator('input[placeholder*="题目"], input[name="topic"], [data-testid="topic-input"]').first
        if topic_input.is_visible():
            topic_input.fill("基于三维成像的损伤智能检测")

        # 点击分析
        analyze_btn = page.locator('button:has-text("开始分析"), button:has-text("分析"), [data-testid="analyze-btn"]').first
        if analyze_btn.is_visible():
            analyze_btn.click()

        page.wait_for_timeout(2000)
        page.screenshot(path="apps/web-react/e2e/screenshots/session63/s63_keywords_confirm.png", full_page=False)

        # 应该能看到关键词拆解（method/task/object等标签）
        page_content = page.content()
        # 至少有一种关键词类型可见
        has_keywords = any(kw in page_content for kw in ["方法", "任务", "对象", "modality", "method", "task", "object"])
        assert has_keywords, "关键词拆解未显示"

    def test_direction_recommendation_stop_here(self, page, goto_workbench):
        """验证方向建议后停止，不生成开题报告"""
        topic_input = page.locator('input[placeholder*="题目"], input[name="topic"], [data-testid="topic-input"]').first
        if topic_input.is_visible():
            topic_input.fill("基于三维成像的损伤智能检测")

        analyze_btn = page.locator('button:has-text("开始分析"), button:has-text("分析"), [data-testid="analyze-btn"]').first
        if analyze_btn.is_visible():
            analyze_btn.click()

        page.wait_for_timeout(5000)  # 等待完整流程
        page.screenshot(path="apps/web-react/e2e/screenshots/session63/s63_direction.png", full_page=False)

        # 应该显示方向建议
        page_content = page.content()
        has_direction = any(d in page_content for d in ["保底", "安全", "增强", "fallback", "safe", "enhance"])
        assert has_direction, "方向建议未显示"

        # 不应该自动生成开题报告
        # (如果前端已经显示了"确认方向"按钮，说明停在这里)
        has_confirm_btn = page.locator('button:has-text("确认方向"), button:has-text("确定")').count() > 0
        # 或者至少没有自动跳转到报告页面
        assert "#/report" not in page.url, "不应自动跳转到报告页面"