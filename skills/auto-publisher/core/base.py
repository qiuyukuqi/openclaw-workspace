"""BasePublisher基类 - 所有平台发布器的父类"""
import os
import random
import asyncio
from playwright.async_api import async_playwright, Page, BrowserContext, Browser

from config import TEMP_DIR, DEFAULT_TIMEOUT
from core.notifier import notify_info, notify_failure


class BasePublisher:
    """平台发布器基类，提供通用的浏览器操作方法"""
    
    def __init__(self, platform_name: str):
        self.platform_name = platform_name
        self.page: Page | None = None
        self.context: BrowserContext | None = None
        self.browser: Browser | None = None
        self.playwright = None
    
    async def setup(self, headless: bool = True):
        """初始化浏览器和上下文（持久化模式）
        
        Args:
            headless: 是否无头模式
        """
        from core.login_manager import get_browser_context
        
        self.playwright = await async_playwright().start()
        _browser, self.context = await get_browser_context(
            self.playwright, self.platform_name, headless=headless
        )
        self.page = await self.context.new_page()
        self.page.set_default_timeout(DEFAULT_TIMEOUT)
    
    async def close(self):
        """关闭浏览器，释放资源"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            print(f"[{self.platform_name}] 关闭浏览器时出错: {e}")
    
    async def screenshot(self, name: str) -> str:
        """截图并保存到temp目录
        
        Args:
            name: 截图名称（不含扩展名）
            
        Returns:
            截图文件的完整路径
        """
        if not self.page:
            return ""
        filename = f"{self.platform_name}_{name}.png"
        filepath = os.path.join(TEMP_DIR, filename)
        try:
            await self.page.screenshot(path=filepath, full_page=True)
            print(f"[截图] {filepath}")
        except Exception as e:
            print(f"[截图失败] {name}: {e}")
        return filepath
    
    async def wait_and_click(self, selector: str, timeout: int = DEFAULT_TIMEOUT,
                              fallback_selectors: list[str] = None) -> bool:
        """等待元素出现并点击，支持fallback selector
        
        Args:
            selector: CSS选择器
            timeout: 超时毫秒
            fallback_selectors: 备选选择器列表
            
        Returns:
            是否点击成功
        """
        selectors = [selector]
        if fallback_selectors:
            selectors.extend(fallback_selectors)
        
        for sel in selectors:
            try:
                await self.page.wait_for_selector(sel, timeout=timeout, state="visible")
                await self.random_delay(0.3, 0.8)
                await self.page.click(sel)
                return True
            except Exception:
                continue
        
        print(f"[{self.platform_name}] ❌ 未找到可点击元素: {selector}")
        await self.screenshot("click_failed")
        return False
    
    async def wait_and_fill(self, selector: str, text: str, timeout: int = DEFAULT_TIMEOUT,
                             fallback_selectors: list[str] = None) -> bool:
        """等待元素出现并填写文本
        
        Args:
            selector: CSS选择器
            text: 要填写的文本
            timeout: 超时毫秒
            fallback_selectors: 备选选择器列表
            
        Returns:
            是否填写成功
        """
        selectors = [selector]
        if fallback_selectors:
            selectors.extend(fallback_selectors)
        
        for sel in selectors:
            try:
                await self.page.wait_for_selector(sel, timeout=timeout, state="visible")
                await self.random_delay(0.3, 0.8)
                await self.page.fill(sel, text)
                return True
            except Exception:
                continue
        
        print(f"[{self.platform_name}] ❌ 未找到可填写元素: {selector}")
        await self.screenshot("fill_failed")
        return False
    
    async def wait_and_type(self, selector: str, text: str, timeout: int = DEFAULT_TIMEOUT,
                             fallback_selectors: list[str] = None) -> bool:
        """等待元素出现并用keyboard.type()输入（用于contenteditable元素）
        
        Args:
            selector: CSS选择器
            text: 要输入的文本
            timeout: 超时毫秒
            fallback_selectors: 备选选择器列表
            
        Returns:
            是否输入成功
        """
        selectors = [selector]
        if fallback_selectors:
            selectors.extend(fallback_selectors)
        
        for sel in selectors:
            try:
                el = await self.page.wait_for_selector(sel, timeout=timeout, state="visible")
                await self.random_delay(0.3, 0.8)
                await el.click()
                await self.random_delay(0.2, 0.5)
                await self.page.keyboard.type(text, delay=random.randint(20, 80))
                return True
            except Exception:
                continue
        
        print(f"[{self.platform_name}] ❌ 未找到可输入元素: {selector}")
        await self.screenshot("type_failed")
        return False
    
    async def random_delay(self, min_s: float = 0.5, max_s: float = 2.0):
        """随机延迟，模拟人类操作间隔
        
        Args:
            min_s: 最小延迟秒数
            max_s: 最大延迟秒数
        """
        delay = random.uniform(min_s, max_s)
        await asyncio.sleep(delay)
    
    async def click_by_text(self, text: str, tag: str = "button", timeout: int = DEFAULT_TIMEOUT) -> bool:
        """通过按钮/链接文本点击
        
        Args:
            text: 按钮文本（支持包含匹配）
            tag: HTML标签名
            timeout: 超时毫秒
            
        Returns:
            是否点击成功
        """
        try:
            # 尝试精确匹配
            btn = self.page.locator(f'{tag}:has-text("{text}")').first
            await btn.wait_for(state="visible", timeout=timeout)
            await self.random_delay(0.3, 0.8)
            await btn.click()
            return True
        except Exception as e:
            print(f"[{self.platform_name}] ❌ 未找到文本为'{text}'的{tag}: {e}")
            await self.screenshot("click_text_failed")
            return False
    
    async def publish(self, title: str, content: str, cover_image: str = None, **kwargs) -> bool:
        """发布文章 - 子类必须实现
        
        Args:
            title: 文章标题
            content: Markdown格式的文章内容
            cover_image: 封面图片路径（可选）
            **kwargs: 其他平台特定参数
            
        Returns:
            是否发布成功
        """
        raise NotImplementedError(f"{self.__class__.__name__} 必须实现 publish 方法")
