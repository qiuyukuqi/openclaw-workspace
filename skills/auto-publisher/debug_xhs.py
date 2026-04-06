#!/usr/bin/env python3
"""Debug xhs page after image upload"""
import sys, os, asyncio
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def debug():
    from playwright.async_api import async_playwright
    from core.login_manager import get_browser_context

    pw = await async_playwright().start()
    _, ctx = await get_browser_context(pw, "xiaohongshu", headless=True)
    page = await ctx.new_page()

    await page.goto("https://creator.xiaohongshu.com/publish/publish", wait_until="domcontentloaded", timeout=60000)
    await asyncio.sleep(3)

    # List all tabs/links with text
    tabs = await page.query_selector_all("span, div, a, button")
    print("=== All visible text elements ===")
    for t in tabs:
        try:
            txt = (await t.text_content() or "").strip()
            visible = await t.is_visible()
            tag = await t.evaluate("e => e.tagName")
            if txt and visible and len(txt) < 30 and ("上传" in txt or "图文" in txt or "视频" in txt or "长文" in txt):
                cls = (await t.get_attribute("class") or "")[:50]
                print(f"  <{tag}> text='{txt}' class='{cls}'")
        except:
            pass

    # Try clicking the exact tab
    print("\n=== Trying to click tabs ===")
    for text in ["上传图文", "图文"]:
        try:
            btn = page.locator(f"span:has-text('{text}')").first
            await btn.wait_for(state="visible", timeout=3000)
            box = await btn.bounding_box()
            print(f"  Found '{text}': bounding_box={box}")
            if box:
                await page.mouse.click(box["x"] + box["width"]/2, box["y"] + box["height"]/2)
                print(f"  Clicked '{text}'")
                await asyncio.sleep(3)
                break
        except Exception as e:
            print(f"  '{text}' not found: {e}")

    # Now upload image
    print("\n=== Uploading image ===")
    file_input = await page.query_selector("input[type='file']")
    if file_input:
        await file_input.set_input_files("test_cover.jpg")
        print("  Image uploaded, waiting 5s...")
        await asyncio.sleep(5)

    # Check editable elements again
    elements = await page.query_selector_all("input, textarea, [contenteditable='true'], [contenteditable]")
    print(f"\n=== Editable elements after upload: {len(elements)} ===")
    for i, el in enumerate(elements):
        tag = await el.evaluate("e => e.tagName")
        placeholder = await el.get_attribute("placeholder") or ""
        eid = await el.get_attribute("id") or ""
        ce = await el.get_attribute("contenteditable") or ""
        visible = await el.is_visible()
        print(f"  [{i}] <{tag}> id={eid} placeholder={placeholder} contenteditable={ce} visible={visible}")

    await page.screenshot(path="temp/xhs_debug.png", full_page=True)
    print("\nScreenshot saved to temp/xhs_debug.png")

    await ctx.close()
    await pw.stop()

asyncio.run(debug())
