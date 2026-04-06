"""Capture toutiao API - minimal version, just find the right endpoint"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')


async def main():
    from playwright.async_api import async_playwright
    from core.login_manager import get_browser_context

    pw = await async_playwright().start()
    try:
        _browser, context = await get_browser_context(pw, "toutiao", headless=False)
        page = await context.new_page()
        
        # Capture ALL POST requests
        async def on_request(request):
            if request.method == 'POST':
                url = request.url
                if 'toutiao.com' in url:
                    print(f"[POST] {url}")
                    if request.post_data:
                        print(f"  BODY: {request.post_data[:500]}")
                    print()
        
        async def on_response(response):
            url = response.url
            if response.request.method == 'POST' and 'toutiao.com' in url:
                try:
                    body = await response.text()
                    if len(body) < 1000:
                        print(f"[RESP] {url} => {body[:500]}")
                except:
                    pass
        
        page.on("request", on_request)
        page.on("response", on_response)
        
        print("=== Opening editor page ===")
        await page.goto("https://mp.toutiao.com/profile_v4/graphic/articles/new",
                       wait_until="domcontentloaded", timeout=60000)
        print("=== Page loaded, waiting 8s for JS ===")
        await asyncio.sleep(8)
        
        print("=== Clicking article menu ===")
        await page.evaluate("""
            var els = document.querySelectorAll('span,div,a,p');
            for (var i = 0; i < els.length; i++) {
                if (els[i].textContent.trim() === '\u6587\u7ae0' && els[i].offsetParent !== null) {
                    els[i].click();
                    break;
                }
            }
        """)
        await asyncio.sleep(8)
        
        # Check if editor loaded
        editor = await page.query_selector("[contenteditable='true']")
        if editor:
            print("=== Editor found! Filling content... ===")
            await editor.click()
            await asyncio.sleep(0.3)
            await page.keyboard.type("API Capture Test", delay=30)
            await asyncio.sleep(0.5)
            await page.keyboard.press("Enter")
            await page.keyboard.type("This is a test article for API capture.", delay=30)
            await asyncio.sleep(2)
            
            print("=== Clicking publish button ===")
            await page.evaluate("""
                var btns = document.querySelectorAll('button');
                for (var i = 0; i < btns.length; i++) {
                    var t = btns[i].textContent.trim();
                    if (t.indexOf('\u53d1\u5e03') !== -1 || t.indexOf('\u9884\u89c8\u5e76\u53d1\u5e03') !== -1) {
                        if (btns[i].offsetParent !== null) {
                            console.log('Clicking button: ' + t);
                            btns[i].click();
                            break;
                        }
                    }
                }
            """)
            await asyncio.sleep(10)
        else:
            print("=== Editor NOT found. Checking page state... ===")
            # Dump all visible text
            text = await page.evaluate("document.body.innerText.substring(0, 500)")
            print(f"Page text: {text}")
            
            # List all POST requests made so far
            print("\nDone. No editor found.")
        
        await context.close()
    finally:
        await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
