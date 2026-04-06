#!/usr/bin/env python3
"""通过Chrome DevTools Protocol获取已登录平台的状态
用法: python cdp_capture.py all
"""
import sys, os, asyncio, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.login_manager import save_state

PLATFORM_URLS = {
    "toutiao": "https://mp.toutiao.com/profile_v4/graphic/articles/new",
    "zhihu": "https://www.zhihu.com",
    "xiaohongshu": "https://creator.xiaohongshu.com/home",
}

async def capture(platform, port=9222):
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    try:
        browser = await pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        context = browser.contexts[0]
        
        # 打开平台页面确保cookie加载
        page = context.new_page()
        url = PLATFORM_URLS.get(platform, "")
        print(f"[{platform}] 访问 {url}...")
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)
        
        # 检查是否登录成功
        current_url = page.url
        login_kw = ["login", "signin", "auth/page"]
        is_login = any(kw in current_url.lower() for kw in login_kw)
        
        if is_login:
            print(f"[{platform}] ❌ 未登录（被重定向到 {current_url[:60]}）")
            await page.close()
            return False
        
        # 保存state
        state = await context.storage_state()
        save_state(platform, state)
        print(f"[{platform}] ✅ 成功！cookies: {len(state.get('cookies', []))}")
        print(f"[{platform}] 页面: {current_url[:80]}")
        
        await page.close()
        return True
    except Exception as e:
        print(f"[{platform}] ❌ 错误: {e}")
        return False
    finally:
        await pw.stop()

async def main():
    platform = sys.argv[1] if len(sys.argv) > 1 else "all"
    platforms = list(PLATFORM_URLS.keys()) if platform == "all" else [platform]
    
    for p in platforms:
        await capture(p)
    
    print("\n✅ 完成！auth/ 目录下有各平台的state文件")

if __name__ == "__main__":
    asyncio.run(main())
