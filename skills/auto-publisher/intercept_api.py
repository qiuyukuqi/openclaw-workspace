"""Intercept toutiao API by overriding XMLHttpRequest"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from playwright.async_api import async_playwright
from core.login_manager import get_browser_context
from config import TOUTIAO_EDITOR_URL


async def main():
    pw = await async_playwright().start()
    try:
        _browser, context = await get_browser_context(pw, "toutiao", headless=False)
        page = await context.new_page()

        # Inject XHR interceptor BEFORE page loads
        await page.add_init_script("""
            window.__captured_requests = [];
            
            // Intercept fetch
            var origFetch = window.fetch;
            window.fetch = function() {
                var args = arguments;
                var url = typeof args[0] === 'string' ? args[0] : (args[0].url || '');
                var method = args[1] && args[1].method ? args[1].method : 'GET';
                
                if (url.indexOf('article') !== -1 && (method === 'POST' || method === 'PUT')) {
                    var body = null;
                    if (args[1] && args[1].body) {
                        body = args[1].body;
                        if (typeof body !== 'string') {
                            body = JSON.stringify(body);
                        }
                    }
                    window.__captured_requests.push({
                        url: url,
                        method: method,
                        body: body,
                        timestamp: Date.now()
                    });
                    console.log('[CAPTURE FETCH] ' + method + ' ' + url);
                    if (body) console.log('[BODY] ' + body.substring(0, 2000));
                }
                
                return origFetch.apply(this, args).then(function(resp) {
                    if (url.indexOf('article') !== -1 && (method === 'POST' || method === 'PUT')) {
                        resp.clone().text().then(function(text) {
                            console.log('[RESP] ' + url + ' => ' + text.substring(0, 500));
                            window.__captured_requests[window.__captured_requests.length - 1].response = text.substring(0, 2000);
                        });
                    }
                    return resp;
                });
            };
            
            // Intercept XMLHttpRequest
            var origOpen = XMLHttpRequest.prototype.open;
            var origSend = XMLHttpRequest.prototype.send;
            XMLHttpRequest.prototype.open = function(method, url) {
                this.__url = url;
                this.__method = method;
                return origOpen.apply(this, arguments);
            };
            XMLHttpRequest.prototype.send = function(body) {
                if (this.__url && this.__url.indexOf('article') !== -1 && this.__method === 'POST') {
                    window.__captured_requests.push({
                        url: this.__url,
                        method: this.__method,
                        body: typeof body === 'string' ? body : null,
                        timestamp: Date.now()
                    });
                    console.log('[CAPTURE XHR] ' + this.__method + ' ' + this.__url);
                }
                return origSend.apply(this, arguments);
            };
        """)

        print("=== Opening editor with interceptor ===")
        await page.goto(TOUTIAO_EDITOR_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)

        # Click article menu via JS
        print("=== Clicking article menu ===")
        await page.evaluate("""
            var items = document.querySelectorAll('.byte-menu-item');
            for (var i = 0; i < items.length; i++) {
                if (items[i].textContent.indexOf('\u6587\u7ae0') !== -1) {
                    items[i].click();
                    break;
                }
            }
        """)
        await asyncio.sleep(10)

        # Check editor state
        editor = await page.query_selector("[contenteditable='true']")
        if editor:
            print("=== Editor found! Trying to fill and publish ===")
            await editor.click()
            await asyncio.sleep(0.3)
            await page.keyboard.type("Test Title", delay=30)
            await asyncio.sleep(0.5)
            await page.keyboard.press("Enter")
            await page.keyboard.type("Test content for API capture.", delay=30)
            await asyncio.sleep(2)

            # Click publish button
            await page.evaluate("""
                var btns = document.querySelectorAll('button');
                for (var i = btns.length - 1; i >= 0; i--) {
                    var t = btns[i].textContent.trim();
                    if (t.indexOf('\u53d1\u5e03') !== -1) {
                        btns[i].click();
                        break;
                    }
                }
            """)
            await asyncio.sleep(10)
        else:
            print("=== Editor not found. Checking page state... ===")

        # Get captured requests
        captured = await page.evaluate("window.__captured_requests || []")
        print(f"\n=== Captured {len(captured)} article requests ===")
        
        output_path = os.path.join("temp", "captured_api.json")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(captured, f, ensure_ascii=False, indent=2)
        
        for req in captured:
            print(f"\n--- {req['method']} {req['url']} ---")
            if req.get('body'):
                print(f"BODY: {req['body'][:2000]}")
            if req.get('response'):
                print(f"RESP: {req['response'][:500]}")
        
        print(f"\nSaved to {output_path}")

        await context.close()
    finally:
        await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
