"""知乎发布器 - 支持专栏文章和问题回答两种模式"""
import os
from playwright.async_api import Page

from config import ZHIHU_EDITOR_URL, DEFAULT_TIMEOUT
from core.base import BasePublisher
from core.markdown_converter import md_to_html, md_to_plaintext
from core.notifier import notify_success, notify_failure


class ZhihuPublisher(BasePublisher):
    """知乎发布器，支持专栏文章和回答问题"""
    
    def __init__(self):
        super().__init__("zhihu")
    
    async def publish(self, title: str, content: str, cover_image: str = None, 
                      question_url: str = None, **kwargs) -> bool:
        """发布内容到知乎
        
        Args:
            title: 文章标题（专栏模式需要）
            content: Markdown格式内容
            cover_image: 封面图（知乎专栏可能支持）
            question_url: 问题URL，传入则进入回答模式
        """
        try:
            if question_url:
                return await self._publish_answer(question_url, content)
            else:
                return await self._publish_article(title, content)
        except Exception as e:
            print(f"[{self.platform_name}] ❌ 发布失败: {e}")
            screenshot_path = await self.screenshot("error")
            notify_failure(self.platform_name, str(e), screenshot_path)
            return False
    
    async def _publish_article(self, title: str, content: str) -> bool:
        """专栏模式：发布文章"""
        # 1. 打开专栏编辑器
        print(f"[{self.platform_name}] 📝 打开专栏编辑器...")
        await self.page.goto(ZHIHU_EDITOR_URL, wait_until="domcontentloaded", timeout=60000)
        await self.page.wait_for_load_state("networkidle", timeout=30000)
        await self.random_delay(1.0, 2.0)
        await self.screenshot("01_zhuanlan_loaded")
        
        # 2. 等待编辑器加载
        print(f"[{self.platform_name}] ⏳ 等待编辑器...")
        editor_ready = await self._wait_for_editor()
        if not editor_ready:
            await self.screenshot("02_editor_timeout")
            raise RuntimeError("专栏编辑器加载超时")
        await self.screenshot("02_editor_ready")
        
        # 3. 填写标题
        print(f"[{self.platform_name}] 📌 填写标题: {title[:30]}...")
        title_filled = await self._fill_title(title)
        if not title_filled:
            raise RuntimeError("标题填写失败")
        await self.random_delay(0.5, 1.0)
        await self.screenshot("03_title_filled")
        
        # 4. 填写正文
        print(f"[{self.platform_name}] 📄 填写正文...")
        html_content = md_to_html(content)
        content_filled = await self._fill_content(html_content)
        if not content_filled:
            raise RuntimeError("正文填写失败")
        await self.random_delay(1.0, 2.0)
        await self.screenshot("04_content_filled")
        
        # 5. 点击发布
        print(f"[{self.platform_name}] 🚀 点击发布...")
        await self.random_delay(1.0, 2.0)
        published = await self._click_publish_article()
        
        if published:
            await self.random_delay(2.0, 3.0)
            screenshot_path = await self.screenshot("05_publish_success")
            notify_success(self.platform_name, title, screenshot_path)
            print(f"[{self.platform_name}] ✅ 专栏文章发布成功！")
            return True
        else:
            screenshot_path = await self.screenshot("05_publish_failed")
            notify_failure(self.platform_name, "发布失败", screenshot_path)
            return False
    
    async def _publish_answer(self, question_url: str, content: str) -> bool:
        """回答模式：回答问题"""
        # 1. 打开问题页面
        print(f"[{self.platform_name}] 💬 打开问题页面...")
        await self.page.goto(question_url, wait_until="domcontentloaded", timeout=60000)
        await self.page.wait_for_load_state("networkidle", timeout=30000)
        await self.random_delay(1.0, 2.0)
        await self.screenshot("01_question_loaded")
        
        # 2. 点击"写回答"按钮
        print(f"[{self.platform_name}] 🖊️ 点击写回答...")
        clicked = await self.click_by_text("写回答", tag="button", timeout=10000)
        if not clicked:
            # fallback: 尝试其他selector
            answer_selectors = [
                ".QuestionAnswer-WriteBtn",
                "button[class*='Answer']",
                "a[href*='answer']",
            ]
            found = False
            for sel in answer_selectors:
                try:
                    el = await self.page.wait_for_selector(sel, timeout=3000, state="visible")
                    await el.click()
                    found = True
                    break
                except Exception:
                    continue
            if not found:
                raise RuntimeError("未找到'写回答'按钮")
        await self.random_delay(1.0, 2.0)
        await self.screenshot("02_answer_editor_ready")
        
        # 3. 填写回答内容
        print(f"[{self.platform_name}] 📄 填写回答内容...")
        html_content = md_to_html(content)
        content_filled = await self._fill_content(html_content)
        if not content_filled:
            raise RuntimeError("回答内容填写失败")
        await self.random_delay(1.0, 2.0)
        await self.screenshot("03_answer_filled")
        
        # 4. 点击提交回答
        print(f"[{self.platform_name}] 🚀 提交回答...")
        await self.random_delay(1.0, 2.0)
        submitted = await self._click_submit_answer()
        
        if submitted:
            await self.random_delay(2.0, 3.0)
            screenshot_path = await self.screenshot("04_submit_success")
            notify_success(self.platform_name, f"回答: {question_url[:50]}", screenshot_path)
            print(f"[{self.platform_name}] ✅ 回答提交成功！")
            return True
        else:
            screenshot_path = await self.screenshot("04_submit_failed")
            notify_failure(self.platform_name, "回答提交失败", screenshot_path)
            return False
    
    async def _wait_for_editor(self) -> bool:
        """等待知乎编辑器加载"""
        selectors = [
            ".WriteIndex-titleInput",         # 专栏标题输入
            "input[placeholder*='输入文章标题']",
            ".RichTextEditor",                 # 富文本编辑器
            ".ProseMirror",                    # ProseMirror编辑器
            "[contenteditable='true']",
            ".DraftEditor-root",              # Draft.js编辑器
        ]
        for sel in selectors:
            try:
                await self.page.wait_for_selector(sel, timeout=5000, state="visible")
                print(f"[{self.platform_name}] 编辑器已就绪 (selector: {sel})")
                return True
            except Exception:
                continue
        return False
    
    async def _fill_title(self, title: str) -> bool:
        """填写专栏标题"""
        selectors = [
            ".WriteIndex-titleInput",
            "input[placeholder*='输入文章标题']",
            "input[placeholder*='标题']",
        ]
        fallbacks = selectors[1:]
        return await self.wait_and_fill(selectors[0], title, timeout=10000, fallback_selectors=fallbacks)
    
    async def _fill_content(self, html_content: str) -> bool:
        """Fill content via clipboard paste for ProseMirror compatibility"""
        content_selectors = [
            ".ProseMirror",
            ".public-DraftEditor-content",
            ".RichTextEditor [contenteditable]",
            "[contenteditable='true']",
            ".ql-editor",
        ]
        
        for sel in content_selectors:
            try:
                el = await self.page.wait_for_selector(sel, timeout=5000, state="visible")
                await el.click()
                await self.random_delay(0.3, 0.5)
                
                # Use clipboard API to paste HTML
                await self.page.evaluate("""
                    async (html) => {
                        const editor = document.querySelector(arguments[0]);
                        const sel2 = document.querySelector(arguments[0]);
                        if (!sel2) return false;
                        // Focus
                        sel2.focus();
                        // Use execCommand to insert HTML (works with ProseMirror)
                        document.execCommand('insertHTML', false, html);
                        // Also dispatch input event
                        sel2.dispatchEvent(new Event('input', {bubbles: true}));
                        return true;
                    }
                """, sel)
                
                # Alternative: use keyboard paste with clipboard write
                await self.page.evaluate("""
                    (html) => {
                        // Select all contenteditable
                        const editors = document.querySelectorAll('[contenteditable="true"]');
                        for (const ed of editors) {
                            if (ed.classList.contains('ProseMirror') || ed.closest('.ProseMirror')) {
                                ed.focus();
                                document.execCommand('selectAll');
                                document.execCommand('insertHTML', false, html);
                                return true;
                            }
                        }
                        // Fallback: find by selector
                        const el = document.querySelector(arguments[0]);
                        if (el) {
                            el.focus();
                            el.innerHTML = html;
                            el.dispatchEvent(new Event('input', {bubbles: true}));
                            el.dispatchEvent(new Event('change', {bubbles: true}));
                        }
                        return false;
                    }
                """, sel)
                print(f"[{self.platform_name}] content injected via {sel}")
                return True
            except Exception as e:
                print(f"[{self.platform_name}] {sel} failed: {e}")
                continue
        
        # Last resort: keyboard paste
        try:
            import pyperclip
            pyperclip.copy(html_content)
            await self.page.keyboard.press("Control+a")
            await self.random_delay(0.1)
            await self.page.keyboard.press("Control+v")
            print(f"[{self.platform_name}] content pasted via keyboard")
            return True
        except:
            pass
        
        print(f"[{self.platform_name}] content fill failed")
        return False


    
    async def _click_publish_article(self) -> bool:
        """点击专栏发布按钮"""
        # 知乎专栏发布按钮
        btn_selectors = [
            "button.WriteIndex-publishBtn",
            "button[class*='publish']",
            "button:has-text('发布')",
            "button:has-text('发布文章')",
        ]
        for sel in btn_selectors:
            try:
                el = await self.page.wait_for_selector(sel, timeout=3000, state="visible")
                if el:
                    await el.click()
                    print(f"[{self.platform_name}] 发布按钮已点击 (selector: {sel})")
                    return True
            except Exception:
                continue
        
        if await self.click_by_text("发布", timeout=3000):
            return True
        
        print(f"[{self.platform_name}] ❌ 未找到发布按钮")
        return False
    
    async def _click_submit_answer(self) -> bool:
        """点击提交回答按钮"""
        btn_selectors = [
            "button.AnswerSubmitBtn",
            "button[class*='Submit']",
            "button:has-text('提交回答')",
        ]
        for sel in btn_selectors:
            try:
                el = await self.page.wait_for_selector(sel, timeout=3000, state="visible")
                if el:
                    await el.click()
                    print(f"[{self.platform_name}] 提交按钮已点击 (selector: {sel})")
                    return True
            except Exception:
                continue
        
        if await self.click_by_text("提交回答", timeout=3000):
            return True
        
        print(f"[{self.platform_name}] ❌ 未找到提交回答按钮")
        return False
