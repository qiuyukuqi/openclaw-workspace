#!/usr/bin/env python3
"""
跨平台内容分发 - 统一入口
从公众号文章或Markdown文件，一键发布到头条号+小红书

用法:
    python3 distribute.py --url "https://mp.weixin.qq.com/s/xxx" --cover cover.jpg
    python3 distribute.py --file article.md --cover cover.jpg
    python3 distribute.py --title "标题" --content "正文" --cover cover.jpg
    python3 distribute.py --url "..." --platforms toutiao xiaohongshu
"""
import asyncio
import json
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def get_content(args) -> tuple[str, str]:
    """获取标题和正文内容"""
    if args.title and args.content:
        return args.title, args.content

    if args.url:
        from core.wechat_reader import fetch_wechat_article
        print(f"📖 读取公众号文章: {args.url}")
        article = fetch_wechat_article(args.url)
        if "error" in article:
            raise RuntimeError(f"读取失败: {article['error']}")
        title = article['title']
        content = article.get('content_markdown', '')
        print(f"   标题: {title}")
        print(f"   正文: {len(content)} 字符")
        return title, content

    if args.file:
        with open(args.file, 'r', encoding='utf-8') as f:
            content = f.read()
        # 从Markdown第一行提取标题
        title = args.title or ""
        if not title and content.startswith('# '):
            title = content.split('\n')[0].lstrip('# ').strip()
        if not title:
            title = args.file.replace('.md', '').replace('.txt', '')
        return title, content

    raise ValueError("请提供 --url、--file 或 --title + --content")


async def publish_to_platform(platform: str, title: str, content: str, cover: str):
    """发布到指定平台"""
    print(f"\n{'='*50}")
    print(f"📱 发布到 {platform}")
    print(f"{'='*50}")

    if platform == "toutiao":
        from platforms.toutiao import ToutiaoPublisher
        # 头条用纯文本正文（去掉Markdown标记）
        from core.markdown_converter import md_to_plaintext
        plain = md_to_plaintext(content)
        pub = ToutiaoPublisher()
        await pub.setup()
        try:
            result = await pub.publish(title=title, content=plain, cover_image=cover)
            return result
        finally:
            await pub.close()

    elif platform == "xiaohongshu":
        from platforms.xiaohongshu import XiaohongshuPublisher
        from core.markdown_converter import md_to_plaintext
        plain = md_to_plaintext(content)
        pub = XiaohongshuPublisher()
        await pub.setup()
        try:
            result = await pub.publish(title=title, content=plain, cover_image=cover)
            return result
        finally:
            await pub.close()

    elif platform == "zhihu":
        print("⚠️ 知乎暂不可用（反自动化检测）")
        return False

    else:
        print(f"❌ 未知平台: {platform}")
        return False


async def main():
    parser = argparse.ArgumentParser(description="跨平台内容分发")
    parser.add_argument("--url", help="公众号文章URL")
    parser.add_argument("--file", "-f", help="Markdown文件路径")
    parser.add_argument("--title", "-t", help="文章标题")
    parser.add_argument("--content", "-c", help="文章正文")
    parser.add_argument("--cover", help="封面图片路径（默认自动生成）")
    parser.add_argument("--platforms", "-p", nargs="+", default=["toutiao", "xiaohongshu"],
                        help="目标平台（默认: toutiao xiaohongshu）")
    args = parser.parse_args()

    # 1. 获取内容
    title, content = await get_content(args)

    # 2. 准备封面
    cover = args.cover
    if not cover:
        # 生成默认测试封面
        cover = "/tmp/openclaw/test_cover.jpg"
        if not os.path.exists(cover):
            os.makedirs(os.path.dirname(cover), exist_ok=True)
            # 用纯色图片
            from playwright.async_api import async_playwright
            pw = await async_playwright().start()
            browser = await pw.chromium.launch(headless=True, args=["--no-sandbox"])
            page = await browser.new_page(viewport={"width": 800, "height": 600})
            await page.set_content(f'<body style="margin:0;display:flex;align-items:center;justify-content:center;height:100vh;background:linear-gradient(135deg,#667eea,#764ba2);color:white;font-family:sans-serif;font-size:32px;text-align:center;padding:40px"><h1>{title}</h1></body>')
            await page.screenshot(path=cover, full_page=False)
            await browser.close()
            await pw.stop()
            print(f"🖼️ 已生成封面: {cover}")

    # 3. 逐平台发布
    results = {}
    for platform in args.platforms:
        success = await publish_to_platform(platform, title, content, cover)
        results[platform] = "✅ 成功" if success else "❌ 失败"

    # 4. 汇总
    print(f"\n{'='*50}")
    print(f"📊 发布汇总")
    print(f"{'='*50}")
    for p, r in results.items():
        print(f"  {p}: {r}")

    return 0 if all(v == "✅ 成功" for v in results.values()) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
