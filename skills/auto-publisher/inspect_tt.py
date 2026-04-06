#!/usr/bin/env python3
import sys, os, asyncio
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def inspect():
    from playwright.async_api import async_playwright
    from core.login_manager import get_browser_context

    pw = await async_playwright().start()
    _, ctx = await get_browser_context(pw, "toutiao", headless=True)
    page = await ctx.new_page()

    await page.goto("https://mp.toutiao.com/profile_v4/graphic/articles/new", wait_until="domcontentloaded", timeout=60000)
    await asyncio.sleep(5)
    # Click left menu "文章"
    await page.evaluate("() => { const els = document.querySelectorAll('span,div,a'); for(const e of els) { if(e.textContent.trim()==='文章' && e.offsetParent!==null) { e.click(); break; } } }")
    await asyncio.sleep(3)

    await page.screenshot(path="temp/toutiao_inspect.png", full_page=True)

    elements = await page.query_selector_all("input, textarea, [contenteditable='true'], [contenteditable], iframe")
    print(f"Found {len(elements)} elements:")
    for i, el in enumerate(elements):
        tag = await el.evaluate("e => e.tagName")
        placeholder = await el.get_attribute("placeholder") or ""
        eid = await el.get_attribute("id") or ""
        cls = (await el.get_attribute("class") or "")[:80]
        ce = await el.get_attribute("contenteditable") or ""
        visible = await el.is_visible()
        if tag == "IFRAME":
            src = (await el.get_attribute("src") or "")[:80]
            print(f"  [{i}] <{tag}> src={src}")
        else:
            print(f"  [{i}] <{tag}> id={eid} ph={placeholder} cls={cls} ce={ce} vis={visible}")

    await ctx.close()
    await pw.stop()

asyncio.run(inspect())
