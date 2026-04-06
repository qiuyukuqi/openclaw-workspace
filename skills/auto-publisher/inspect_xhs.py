#!/usr/bin/env python3
"""Inspect xiaohongshu publish page selectors"""
import sys, os, asyncio
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def inspect():
    from playwright.async_api import async_playwright
    from core.login_manager import get_browser_context

    pw = await async_playwright().start()
    _, ctx = await get_browser_context(pw, "xiaohongshu", headless=True)
    page = await ctx.new_page()
    
    await page.goto("https://creator.xiaohongshu.com/publish/publish", wait_until="domcontentloaded", timeout=60000)
    await asyncio.sleep(3)
    
    # Click image-text tab
    for sel in ["span:has-text('上传图文')", "div:has-text('上传图文')"]:
        try:
            el = await page.wait_for_selector(sel, timeout=5000, state="visible")
            await el.click()
            await asyncio.sleep(2)
            print(f"Clicked: {sel}")
            break
        except:
            pass
    
    # Screenshot
    await page.screenshot(path="temp/xhs_inspect.png", full_page=True)
    
    # Find all input/textarea/contenteditable elements
    elements = await page.query_selector_all("input, textarea, [contenteditable='true'], [contenteditable]")
    print(f"\nFound {len(elements)} editable elements:")
    for i, el in enumerate(elements):
        tag = await el.evaluate("e => e.tagName")
        placeholder = await el.get_attribute("placeholder") or ""
        cls = await el.get_attribute("class") or ""
        eid = await el.get_attribute("id") or ""
        ce = await el.get_attribute("contenteditable") or ""
        visible = await el.is_visible()
        print(f"  [{i}] <{tag}> id={eid} class={cls[:60]} placeholder={placeholder} contenteditable={ce} visible={visible}")

    await ctx.close()
    await pw.stop()

asyncio.run(inspect())
