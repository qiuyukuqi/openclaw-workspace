#!/usr/bin/env python3
import sys, os, asyncio
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def main():
    from playwright.async_api import async_playwright
    from core.login_manager import get_browser_context

    pw = await async_playwright().start()
    _, ctx = await get_browser_context(pw, "toutiao", headless=True)
    page = await ctx.new_page()
    await page.goto("https://mp.toutiao.com/profile_v4/graphic/articles/new", wait_until="domcontentloaded", timeout=60000)
    await asyncio.sleep(8)
    print("URL:", page.url)
    html = await page.content()
    print("HTML length:", len(html))
    # Check title
    title = await page.title()
    print("Title:", title)
    # Check body text
    body_text = await page.evaluate("() => document.body?.innerText?.substring(0, 500)")
    print("Body text:", body_text)
    # Check iframes
    iframes = await page.query_selector_all("iframe")
    print(f"Iframes: {len(iframes)}")
    for i, f in enumerate(iframes):
        src = await f.get_attribute("src")
        print(f"  iframe[{i}]: {src[:100] if src else 'no-src'}")
    await page.screenshot(path="temp/tt_debug2.png", full_page=True)
    await ctx.close()
    await pw.stop()

asyncio.run(main())
