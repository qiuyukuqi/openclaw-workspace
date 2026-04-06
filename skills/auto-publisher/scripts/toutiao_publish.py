#!/usr/bin/env python3
"""
头条号文章自动发布脚本
使用Playwright浏览器自动化 + cookie注入

流程：
1. 打开头条号编辑器
2. 填写标题和正文（keyboard.type模拟真人打字）
3. 上传封面图
4. 通过路由拦截将save=0改为save=1（头条save=1=发布）
5. 文章进入审核状态

依赖：pip install playwright && playwright install chromium
Cookie来源：从Windows服务器Playwright持久化context导出
  scp Administrator@43.135.179.141:"C:/Users/Administrator/auto-publisher/auth/toutiao_data/storage_state.json" /tmp/openclaw/toutiao_cookies.json
"""

import asyncio
import json
import sys
import os
from urllib.parse import unquote


async def publish_article(title: str, content: str, cover_path: str = "/tmp/openclaw/test_cover.jpg",
                         cookie_path: str = "/tmp/openclaw/toutiao_cookies.json"):
    """发布文章到头条号

    Args:
        title: 文章标题（2-30字）
        content: 文章正文（纯文本，>30字）
        cover_path: 封面图片路径
        cookie_path: cookie文件路径

    Returns:
        dict: {success, pgc_id, article_url, message}
    """
    from playwright.async_api import async_playwright

    if not os.path.exists(cookie_path):
        return {"success": False, "message": f"Cookie文件不存在: {cookie_path}"}

    with open(cookie_path) as f:
        state = json.load(f)
    cookies = state['cookies'] if isinstance(state, dict) else state

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900}
        )
        await ctx.add_cookies(cookies)
        await ctx.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = {runtime: {}};
            localStorage.clear();
            sessionStorage.clear();
        """)
        page = await ctx.new_page()

        pgc_id = [None]
        errors = []

        # 路由拦截：save=0 → save=1（头条save=1=发布/提交审核）
        async def intercept_publish(route):
            body = route.request.post_data or ''
            url = route.request.url
            if 'article/publish' in url and 'save=0' in body and 'pgc_id=' not in body:
                new_body = body.replace('save=0', 'save=1')
                await route.continue_(post_data=new_body)
                return
            await route.continue_()

        async def on_resp(resp):
            url = resp.url
            if 'article/publish' in url:
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

        await page.route('**/article/publish**', intercept_publish)
        page.on("response", on_resp)

        # Step 1: 加载编辑器
        try:
            await page.goto("https://mp.toutiao.com/profile_v4/graphic/publish",
                           wait_until="networkidle", timeout=30000)
            await page.wait_for_selector('.ProseMirror', timeout=15000)
        except Exception as e:
            await browser.close()
            return {"success": False, "message": f"编辑器加载失败: {e}"}

        # 关闭AI助手drawer
        try:
            await page.click('.byte-drawer-mask', timeout=3000)
            await asyncio.sleep(1)
        except:
            pass

        # Step 2: 填写标题
        try:
            ta = page.locator('textarea[placeholder*="标题"]')
            await ta.click()
            await page.keyboard.type(title, delay=50)
            await asyncio.sleep(1)
        except Exception as e:
            errors.append(f"标题填写失败: {e}")

        # Step 3: 填写正文（分段输入）
        try:
            ed = page.locator('.ProseMirror:not(.syl-placeholder)')
            await ed.click()
            await asyncio.sleep(0.5)
            paragraphs = content.split('\n')
            for i, para in enumerate(paragraphs):
                para = para.strip()
                if not para:
                    continue
                await page.keyboard.type(para, delay=20)
                if i < len(paragraphs) - 1:
                    await page.keyboard.press('Enter')
                    await asyncio.sleep(0.3)
        except Exception as e:
            errors.append(f"正文填写失败: {e}")

        # Step 4: 等待pgc_id（自动保存触发）
        for _ in range(20):
            await asyncio.sleep(1)
            if pgc_id[0]:
                break
        else:
            # 手动触发
            try:
                await page.evaluate(
                    "document.querySelector('textarea[placeholder*=\\\"标题\\\"]')?.dispatchEvent(new Event('input',{bubbles:true}))")
                await asyncio.sleep(5)
            except:
                pass

        if not pgc_id[0]:
            await browser.close()
            return {"success": False, "message": "无法获取pgc_id", "errors": errors}

        # Step 5: 上传封面
        if cover_path and os.path.exists(cover_path):
            try:
                done = asyncio.Event()

                async def on_upload(r):
                    if 'upload' in r.url and r.url.startswith('https://mp.toutiao.com'):
                        try:
                            if (await r.json()).get('code') == 0:
                                done.set()
                        except:
                            pass

                page.on("response", on_upload)

                # 关闭drawer
                try:
                    await page.evaluate("document.querySelector('.byte-drawer-mask')?.click()")
                except:
                    pass
                await asyncio.sleep(1)

                await page.click('.article-cover-add')
                await asyncio.sleep(1)
                await page.locator('input[type="file"]').first.set_input_files(cover_path)
                try:
                    await asyncio.wait_for(done.wait(), timeout=30)
                except:
                    errors.append("封面上传超时")
            except Exception as e:
                errors.append(f"封面上传失败: {e}")

        await asyncio.sleep(2)
        await browser.close()

        # 查询文章状态
        article_url = f"https://www.toutiao.com/item/{pgc_id[0]}/"

        return {
            "success": True,
            "pgc_id": pgc_id[0],
            "article_url": article_url,
            "status": "审核中",
            "message": "文章已提交审核",
            "errors": errors if errors else None
        }


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description="头条号文章自动发布")
    parser.add_argument("--title", "-t", default="AI自动化发布的优势与挑战", help="文章标题")
    parser.add_argument("--content", "-c", default="", help="文章正文")
    parser.add_argument("--cover", "-f", default="/tmp/openclaw/test_cover.jpg", help="封面图片路径")
    parser.add_argument("--cookie", default="/tmp/openclaw/toutiao_cookies.json", help="Cookie文件路径")
    args = parser.parse_args()

    content = args.content or "自动化发布正在改变内容创作者的工作方式。通过人工智能技术，内容创作者可以更高效地管理和发布文章，节省大量时间和精力。本文将探讨AI自动化发布的优势与面临的挑战。从内容生成到分发优化，AI工具正在重塑整个内容生态。让我们一起来了解这一领域的最新发展。"

    result = asyncio.run(publish_article(
        title=args.title,
        content=content,
        cover_path=args.cover,
        cookie_path=args.cookie
    ))

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
