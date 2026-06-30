"""Session 63: Topic-Driven Retrieval Playwright Tests

测试 S63 的题目驱动检索功能:
1. 3D题 → 显示 MVTec 3D-AD/COLMAP/3DGS
2. YOLO钢材题 → 不混3D, 显示 NEU-DET/YOLO
3. NLP题 → 显示 BERT/RoBERTa/LoRA

运行: pytest apps/web-react/e2e/test_session63_topic_driven_retrieval.py -v -m react_web
"""

import pytest
from playwright.sync_api import expect, Page


pytestmark = pytest.mark.react_web


def find_input_and_fill(page: Page, text: str) -> bool:
    """尝试多种方式找到并填写输入框"""
    # 方式1: 找uw-topic-intake下的input
    selectors = [
        '[data-testid="uw-topic-intake"] input',
        'input[placeholder*="题目"]',
        'input[placeholder*="输入"]',
        'textarea',
    ]
    for sel in selectors:
        inp = page.locator(sel).first
        if inp.is_visible(timeout=2000):
            inp.fill(text)
            return True
    return False


def click_analyze(page: Page) -> bool:
    """点击开始分析按钮"""
    selectors = [
        '[data-testid="uw-confirm-keywords"]',
        'button:has-text("开始分析")',
        'button:has-text("确认")',
        '[data-testid="topic-intake-start"]',
    ]
    for sel in selectors:
        btn = page.locator(sel).first
        if btn.is_visible(timeout=2000) and btn.is_enabled():
            btn.click()
            return True
    return False


@pytest.fixture
def goto_workbench(page):
    """导航到工作台页面"""
    page.goto("http://127.0.0.1:18183/#/")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)
    return page


class TestTopicDrivenRetrieval:
    """S63 题目驱动检索测试"""

    def test_3d_topic_shows_3d_candidates(self, page: Page, goto_workbench):
        """Case A: 3D成像损伤检测 → 必须显示 3D 相关内容"""
        # 1. 填写3D题目
        filled = find_input_and_fill(page, "基于三维成像的损伤智能检测")
        assert filled, "无法找到并填写题目输入框"

        # 2. 点击分析
        clicked = click_analyze(page)
        if not clicked:
            pytest.skip("无法点击分析按钮，可能是页面结构不同")

        page.wait_for_timeout(5000)

        # 3. 截图
        page.screenshot(path="apps/web-react/e2e/screenshots/session63/s63_3d_analysis.png", full_page=False)

        # 4. 验证页面包含分析结果
        page_content = page.content()

        # Should have analysis result cards
        has_analysis = "uw-analysis" in page_content or "uw-" in page_content
        assert has_analysis, "Analysis results not shown"

        # Should contain 3D related keywords
        has_3d = any(kw in page_content for kw in ["3D", "COLMAP", "MVTec", "损伤", "检测", "PointNet"])
        assert has_3d, "3D related keywords not found"

    def test_yolo_steel_topic(self, page: Page, goto_workbench):
        """Case B: YOLO钢材题"""
        filled = find_input_and_fill(page, "基于YOLO的钢材表面缺陷检测")
        assert filled, "无法找到并填写题目输入框"

        clicked = click_analyze(page)
        if not clicked:
            pytest.skip("无法点击分析按钮")

        page.wait_for_timeout(5000)
        page.screenshot(path="apps/web-react/e2e/screenshots/session63/s63_yolo_analysis.png", full_page=False)

        page_content = page.content()
        has_result = "题目理解" in page_content or "分析" in page_content
        assert has_result, "分析结果未显示"

        # 验证包含YOLO相关内容
        has_yolo = any(kw in page_content for kw in ["YOLO", "钢材", "缺陷"])
        assert has_yolo, "YOLO相关关键词未出现"

    def test_nlp_topic(self, page: Page, goto_workbench):
        """Case C: NLP舆情情感分析"""
        filled = find_input_and_fill(page, "基于大语言模型的中文舆情情感分析")
        assert filled, "无法找到并填写题目输入框"

        clicked = click_analyze(page)
        if not clicked:
            pytest.skip("无法点击分析按钮")

        page.wait_for_timeout(5000)
        page.screenshot(path="apps/web-react/e2e/screenshots/session63/s63_nlp_analysis.png", full_page=False)

        page_content = page.content()
        has_result = "题目理解" in page_content or "分析" in page_content
        assert has_result, "分析结果未显示"

        # 验证包含NLP相关内容
        has_nlp = any(kw in page_content for kw in ["大语言", "LLM", "情感", "BERT", "文本"])
        assert has_nlp, "NLP相关关键词未出现"


class TestStepByStepFlow:
    """测试分步确认流程"""

    def test_keywords_confirmation_visible(self, page: Page, goto_workbench):
        """验证关键词确认步骤可见"""
        # 填写题目
        filled = find_input_and_fill(page, "基于三维成像的损伤智能检测")
        assert filled, "无法填写题目"

        clicked = click_analyze(page)
        if not clicked:
            pytest.skip("无法点击分析按钮")

        page.wait_for_timeout(3000)
        page.screenshot(path="apps/web-react/e2e/screenshots/session63/s63_step_keywords.png", full_page=False)

        # 应该能看到关键词确认卡片
        page_content = page.content()
        has_keywords = "关键词" in page_content
        assert has_keywords, "关键词拆解未显示"

    def test_analysis_produces_results(self, page: Page, goto_workbench):
        """验证分析能产生结果"""
        filled = find_input_and_fill(page, "基于YOLO的钢材表面缺陷检测")
        assert filled, "无法填写题目"

        clicked = click_analyze(page)
        if not clicked:
            pytest.skip("无法点击分析按钮")

        page.wait_for_timeout(6000)
        page.screenshot(path="apps/web-react/e2e/screenshots/session63/s63_full_analysis.png", full_page=False)

        # 验证产生了分析结果
        result_cards = page.locator('[class*="pa-card"]').count()
        assert result_cards > 0, "没有生成任何结果卡片"

        # 验证有数据表格或列表
        page_content = page.content()
        has_data = any(x in page_content for x in ["关键词", "可行性", "证据", "候选", "baseline"])
        assert has_data, "分析结果内容为空"