#!/usr/bin/env python3
"""小红书笔记自动发布脚本

使用Playwright + cookie注入发布图文笔记到小红书。

流程：打开发布页 → 切换图文模式 → 上传图片 → 填标题 → 填正文 → 发布
"""
import asyncio
import json
import os
import sys

from core.base import BasePublisher
from core.notifier import notify_success, notify_failure
from config import DEFAULT_TIMEOUT


class XiaohongshuPublisher(BasePublisher):
    """小红书内容发布器"""

    def __init__(self, cookie_path: str = None):
        super().__init__("xiaohongshu")
        self._cookie_path = cookie_path or "/tmp/openclaw/xiaohongshu_cookies.json"

    async def setup(self, headless: bool = True):
        """初始化浏览器 - cookie注入模式"""
        from playwright.async_api import async_playwright

        if not os.path.exists(self._cookie_path):
            raise FileNotFoundError(f"Cookie文件不存在: {self._cookie_path}")

        with open(self._cookie_path) as f:
            state = json.load(f)
        cookies = state['cookies'] if isinstance(state, dict) else state

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900}
        )
        await self.context.add_cookies(cookies)
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = {runtime: {}};
        """)
        self.page = await self.context.new_page()
        self.page.set_default_timeout(DEFAULT_TIMEOUT)
        print(f"[{self.platform_name}] 浏览器已启动，{len(cookies)} 个cookie")

    async def publish(self, title: str, content: str, cover_image: str = None, **kwargs) -> bool:
        """发布图文笔记到小红书

        Args:
            title: 笔记标题
            content: 笔记正文（纯文本）
            cover_image: 封面图片路径（小红书必须上传图片）

        Returns:
            bool: 是否发布成功
        """
        try:
            # Step 1: 打开发布页
            print(f"[{self.platform_name}] 📝 打开发布页...")
            await self.page.goto("https://creator.xiaohongshu.com/publish/publish",
                                 wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)

            if 'login' in self.page.url.lower():
                raise RuntimeError("需要登录，cookie可能已过期")
            await self.screenshot("01_loaded")

            # Step 2: 切换到图文模式
            print(f"[{self.platform_name}] 📌 切换图文模式...")
            try:
                await self.page.evaluate("""(() => {
                    const items = document.querySelectorAll('div, span, a');
                    for (const item of items) {
                        const t = (item.innerText || '').trim();
                        if (t === '上传图文' && item.offsetParent) { item.click(); return; }
                    }
                })()""")
                await asyncio.sleep(2)
            except:
                pass

            # Step 3: 上传图片（必须，上传后才会出现标题/正文输入框）
            images = []
            if cover_image and os.path.exists(cover_image):
                images.append(cover_image)
            if kwargs.get('images'):
                for img in kwargs['images']:
                    if os.path.exists(img) and img not in images:
                        images.append(img)

            if not images:
                raise RuntimeError("小红书必须上传至少一张图片")

            print(f"[{self.platform_name}] 🖼️ 上传 {len(images)} 张图片...")
            await self.page.locator('input[type="file"]').first.set_input_files(images)

            # 等标题输入框出现
            for i in range(30):
                await asyncio.sleep(1)
                el = await self.page.query_selector('input[placeholder*="标题"]')
                if el:
                    print(f"[{self.platform_name}] ✅ 图片上传完成 ({i+1}s)")
                    break
            else:
                raise RuntimeError("图片上传超时，标题输入框未出现")
            await self.screenshot("02_uploaded")

            # Step 4: 填写标题
            print(f"[{self.platform_name}] 📌 填写标题: {title[:20]}...")
            await self.page.locator('input[placeholder*="标题"]').click()
            await asyncio.sleep(0.5)
            await self.page.keyboard.type(title, delay=50)
            await asyncio.sleep(1)
            await self.screenshot("03_title")

            # Step 5: 填写正文
            print(f"[{self.platform_name}] 📄 填写正文...")
            await self.page.locator('[contenteditable="true"]').click()
            await asyncio.sleep(0.5)
            # 分段输入
            for i, para in enumerate(content.split('\n')):
                para = para.strip()
                if not para:
                    continue
                await self.page.keyboard.type(para, delay=20)
                if i < len(content.split('\n')) - 1:
                    await self.page.keyboard.press('Enter')
                    await asyncio.sleep(0.3)
            await self.screenshot("04_content")

            # Step 6: 添加标签（如有）
            tags = kwargs.get('tags', [])
            if tags:
                print(f"[{self.platform_name}] 🏷️ 添加标签: {tags}")
                await asyncio.sleep(0.5)
                # 小红书标签通过 # 在正文中添加
                for tag in tags:
                    clean = tag.lstrip('#')
                    await self.page.keyboard.type(f" #{clean}", delay=30)
                    await asyncio.sleep(0.5)

            await asyncio.sleep(1)

            # Step 7: 点击发布
            print(f"[{self.platform_name}] 🚀 发布...")
            await self.page.evaluate("""(() => {
                const btns = document.querySelectorAll('button');
                for (const b of btns) {
                    if (b.innerText.trim() === '发布' && b.offsetParent) {
                        b.click(); return;
                    }
                }
            })()""")
            await asyncio.sleep(5)
            await self.screenshot("05_publish")

            # 检查结果
            result = await self.page.evaluate("""(() => {
                const t = document.body.innerText;
                if (t.includes('发布成功') || t.includes('成功发布')) return 'SUCCESS';
                if (location.href.includes('success')) return 'SUCCESS';
                if (t.includes('发布失败') || t.includes('失败')) return 'FAIL';
                return 'UNKNOWN';
            })()""")

            if result == 'SUCCESS':
                notify_success(self.platform_name, title, await self.screenshot("success"))
                print(f"[{self.platform_name}] ✅ 发布成功！")
                return True
            else:
                notify_failure(self.platform_name, f"发布状态: {result}", await self.screenshot("result"))
                print(f"[{self.platform_name}] ⚠️ 发布状态: {result}")
                return False

        except Exception as e:
            notify_failure(self.platform_name, str(e), await self.screenshot("error"))
            print(f"[{self.platform_name}] ❌ 发布失败: {e}")
            return False


# 独立运行入口
async def _standalone():
    import argparse
    parser = argparse.ArgumentParser(description="小红书笔记自动发布")
    parser.add_argument("--title", "-t", default="AI自动化测试")
    parser.add_argument("--content", "-c", default="")
    parser.add_argument("--cover", "-f", default="/tmp/openclaw/test_cover.jpg")
    parser.add_argument("--cookie", default="/tmp/openclaw/xiaohongshu_cookies.json")
    parser.add_argument("--tags", nargs="*", help="标签列表")
    args = parser.parse_args()

    content = args.content or (
        "自动化发布正在改变内容创作者的工作方式。通过AI技术，可以更高效地管理和发布文章。"
    )

    pub = XiaohongshuPublisher(cookie_path=args.cookie)
    try:
        await pub.setup()
        result = await pub.publish(title=args.title, content=content,
                                    cover_image=args.cover, tags=args.tags)
        print(f"\n结果: {'✅ 成功' if result else '❌ 失败'}")
        return 0 if result else 1
    finally:
        await pub.close()


if __name__ == "__main__":
    asyncio.run(_standalone())
