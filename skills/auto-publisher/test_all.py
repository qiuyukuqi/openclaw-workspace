#!/usr/bin/env python3
import sys, os, asyncio
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['PYTHONIOENCODING'] = 'utf-8'

async def test_all():
    from playwright.async_api import async_playwright
    from core.login_manager import has_state, get_browser_context
    
    platforms = ["toutiao", "zhihu", "xiaohongshu"]
    test_urls = {
        "toutiao": "https://mp.toutiao.com/profile_v4/graphic/articles/new",
        "zhihu": "https://www.zhihu.com",
        "xiaohongshu": "https://creator.xiaohongshu.com",
    }
    
    pw = await async_playwright().start()
    
    for platform in platforms:
        print(f"\n{'='*50}")
        print(f"🔍 测试 {platform}...")
        
        if not has_state(platform):
            # 尝试用旧的 state.json
            old_state = os.path.join(os.path.dirname(__file__), "auth", f"{platform}_state.json")
            if os.path.exists(old_state):
                print(f"⚠️  {platform} 只有旧的 state.json，没有持久化数据目录")
                print(f"   新方案需要 auth/{platform}_data/ 目录")
                print(f"   请在有GUI的电脑上重新运行: python publisher.py login {platform}")
            else:
                print(f"❌ {platform} 没有任何登录数据")
            continue
        
        try:
            _browser, context = await get_browser_context(pw, platform, headless=True)
            page = await context.new_page()
            
            url = test_urls[platform]
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)
            
            current_url = page.url
            login_keywords = ["login", "signin", "登录", "sign_in"]
            is_login = any(kw in current_url.lower() for kw in login_keywords)
            
            if is_login:
                print(f"❌ Cookie已过期，被重定向到登录页: {current_url[:80]}")
            else:
                print(f"✅ 登录状态有效！当前页面: {current_url[:80]}")
            
            screenshot_path = os.path.join(os.path.dirname(__file__), "temp", f"{platform}_test.png")
            os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
            await page.screenshot(path=screenshot_path, full_page=True)
            print(f"📸 截图: {screenshot_path}")
            
            await page.close()
            await context.close()
        except Exception as e:
            print(f"❌ 测试失败: {e}")
    
    await pw.stop()
    print(f"\n{'='*50}")
    print("🏁 测试完成")

asyncio.run(test_all())
