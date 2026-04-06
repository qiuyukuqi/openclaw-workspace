"""头条号文章发布器

使用Playwright + cookie注入发布文章到头条号。

核心发现：头条article/publish API中save参数：
- save=0: 保存草稿（需pgc_id，新文章没有时返回7050）
- save=1: 提交发布/审核

方案：路由拦截，将无pgc_id的save=0改为save=1，直接提交审核。
"""
import asyncio
import json
import os
import sys

from core.base import BasePublisher
from core.notifier import notify_success, notify_failure
from config import DEFAULT_TIMEOUT


class ToutiaoPublisher(BasePublisher):
    """头条号内容发布器"""

    def __init__(self, cookie_path: str = None):
        super().__init__("toutiao")
        self._cookie_path = cookie_path or "/tmp/openclaw/toutiao_cookies.json"

    async def setup(self, headless: bool = True):
        """初始化浏览器 - 使用cookie注入而非持久化context（因为运行在Linux服务器上）"""
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
            localStorage.clear();
            sessionStorage.clear();
        """)
        self.page = await self.context.new_page()
        self.page.set_default_timeout(DEFAULT_TIMEOUT)
        print(f"[{self.platform_name}] 浏览器已启动，{len(cookies)} 个cookie")

    async def publish(self, title: str, content: str, cover_image: str = None, **kwargs) -> bool:
        """发布文章到头条号

        Args:
            title: 文章标题（2-30字）
            content: 文章正文（纯文本或Markdown）
            cover_image: 封面图片路径

        Returns:
            bool: 是否发布成功
        """
        try:
            # Step 1: 加载编辑器
            print(f"[{self.platform_name}] 📝 打开编辑器...")
            await self.page.goto("https://mp.toutiao.com/profile_v4/graphic/publish",
                                 wait_until="networkidle", timeout=30000)
            await self.page.wait_for_selector('.ProseMirror', timeout=15000)
            print(f"[{self.platform_name}] ✅ 编辑器加载完成")

            # 关闭AI助手drawer
            try:
                await self.page.click('.byte-drawer-mask', timeout=3000)
                await asyncio.sleep(1)
            except:
                pass
            await self.screenshot("01_editor")

            # Step 2: 设置路由拦截
            pgc_id = [None]
            errors = []

            async def intercept_publish(route):
                body = route.request.post_data or ''
                url = route.request.url
                if 'article/publish' in url and 'save=0' in body and 'pgc_id=' not in body:
                    await route.continue_(post_data=body.replace('save=0', 'save=1'))
                    return
                await route.continue_()

            async def on_resp(resp):
                if 'article/publish' in resp.url:
                    try:
                        b = await resp.json()
                        d = b.get('data', {})
                        c = b.get('code')
                        if isinstance(d, dict) and d.get('pgc_id') and str(d['pgc_id']) != '0':
                            pgc_id[0] = str(d['pgc_id'])
                        if c and c != 0:
                            errors.append(f"API code:{c} msg:{b.get('message', '')}")
                    except:
                        pass

            await self.page.route('**/article/publish**', intercept_publish)
            self.page.on("response", on_resp)

            # Step 3: 填写标题
            print(f"[{self.platform_name}] 📌 填写标题: {title[:30]}...")
            await self.page.locator('textarea[placeholder*="标题"]').click()
            await self.page.keyboard.type(title, delay=50)
            await asyncio.sleep(1)
            await self.screenshot("02_title")

            # Step 4: 填写正文（分段输入）
            print(f"[{self.platform_name}] 📄 填写正文...")
            ed = self.page.locator('.ProseMirror:not(.syl-placeholder)')
            await ed.click()
            await asyncio.sleep(0.5)
            for i, para in enumerate(content.split('\n')):
                para = para.strip()
                if not para:
                    continue
                await self.page.keyboard.type(para, delay=20)
                if i < len(content.split('\n')) - 1:
                    await self.page.keyboard.press('Enter')
                    await asyncio.sleep(0.3)
            await self.screenshot("03_content")

            # Step 5: 等待pgc_id
            print(f"[{self.platform_name}] ⏳ 等待自动保存...")
            for i in range(20):
                await asyncio.sleep(1)
                if pgc_id[0]:
                    print(f"[{self.platform_name}] ✅ pgc_id: {pgc_id[0]} ({i+1}s)")
                    break
            else:
                await self.page.evaluate(
                    "document.querySelector('textarea[placeholder*=\\\"标题\\\"]')?.dispatchEvent(new Event('input',{bubbles:true}))")
                await asyncio.sleep(5)

            if not pgc_id[0]:
                notify_failure(self.platform_name, "无法获取pgc_id", await self.screenshot("error"))
                return False

            # Step 6: 上传封面
            if cover_image and os.path.exists(cover_image):
                print(f"[{self.platform_name}] 🖼️ 上传封面...")
                if await self._upload_cover(cover_image):
                    print(f"[{self.platform_name}] ✅ 封面上传成功")
                else:
                    errors.append("封面上传失败")

            await asyncio.sleep(2)
            await self.screenshot("04_done")

            article_url = f"https://www.toutiao.com/item/{pgc_id[0]}/"
            msg = f"文章已提交审核 ({article_url})"
            if errors:
                msg += f" 警告: {errors}"
            notify_success(self.platform_name, title, await self.screenshot("success"))
            print(f"[{self.platform_name}] ✅ {msg}")
            return True

        except Exception as e:
            notify_failure(self.platform_name, str(e), await self.screenshot("error"))
            print(f"[{self.platform_name}] ❌ 发布失败: {e}")
            return False

    async def _upload_cover(self, cover_path: str) -> bool:
        """上传封面图片"""
        done = asyncio.Event()

        async def on_upload(resp):
            if 'upload' in resp.url and resp.url.startswith('https://mp.toutiao.com'):
                try:
                    if (await resp.json()).get('code') == 0:
                        done.set()
                except:
                    pass

        self.page.on("response", on_upload)
        try:
            await self.page.evaluate("document.querySelector('.byte-drawer-mask')?.click()")
        except:
            pass
        await asyncio.sleep(1)

        await self.page.click('.article-cover-add')
        await asyncio.sleep(1)

        try:
            await self.page.locator('input[type="file"]').first.set_input_files(cover_path)
            await asyncio.wait_for(done.wait(), timeout=30)
            return True
        except:
            return False
