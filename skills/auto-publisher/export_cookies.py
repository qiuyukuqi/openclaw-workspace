"""Export toutiao cookies to JSON file"""
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
        await page.goto("https://mp.toutiao.com/profile_v4/graphic/articles/new",
                       wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)
        
        state = await context.storage_state()
        output_path = os.path.join("auth", "toutiao_data", "storage_state.json")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        
        count = len(state.get('cookies', []))
        print(f"OK - exported {count} cookies to {output_path}")
        
        await context.close()
    finally:
        await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
