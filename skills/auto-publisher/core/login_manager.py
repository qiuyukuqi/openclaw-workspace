"""登录管理 - Playwright持久化上下文（launch_persistent_context）"""
import os
import platform as pf
from config import AUTH_DIR


def _user_data_dir(platform: str) -> str:
    """获取指定平台的用户数据目录（持久化存储）"""
    return os.path.join(AUTH_DIR, f"{platform}_data")


def has_state(platform: str) -> bool:
    """检查平台是否有已保存的登录数据目录"""
    return os.path.exists(_user_data_dir(platform))


def _find_chrome():
    """查找系统已安装的Chrome路径"""
    if pf.system() == "Windows":
        candidates = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        ]
    else:
        candidates = ["/usr/bin/google-chrome", "/usr/bin/google-chrome-stable",
                       "/usr/bin/chromium-browser", "/usr/bin/chromium"]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


async def get_browser_context(playwright, platform: str, headless: bool = True, force_login: bool = False):
    """创建持久化浏览器上下文，一次登录终身有效

    Args:
        playwright: Playwright实例
        platform: 平台名称
        headless: 是否无头模式
        force_login: 强制重新登录（即使目录已存在）

    Returns:
        (None, context) 元组。
    """
    user_data_dir = _user_data_dir(platform)
    os.makedirs(user_data_dir, exist_ok=True)

    # 反检测启动参数
    launch_args = [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-blink-features=AutomationControlled",
        "--disable-features=AutomationControlled",
        "--exclude-switches=enable-automation",
        "--disable-infobars",
    ]

    context_options = {
        "headless": headless,
        "args": launch_args,
        "viewport": {"width": 1920, "height": 1080},
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        "locale": "zh-CN",
        "no_viewport": False,
        "ignore_default_args": ["--enable-automation"],
    }

    chrome_path = _find_chrome()
    if chrome_path:
        context_options["executable_path"] = chrome_path
        print(f"[LOGIN] 使用系统Chrome: {chrome_path}")
    else:
        print(f"[LOGIN] 未找到系统Chrome，使用Playwright Chromium")

    context = await playwright.chromium.launch_persistent_context(
        user_data_dir, **context_options
    )

    # 移除webdriver标记
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    """)

    if force_login or not has_state(platform):
        if headless:
            await context.close()
            raise RuntimeError(
                f"[LOGIN] {platform} 没有登录过，headless模式无法登录。\n"
                f"请先在有GUI的电脑上运行: python publisher.py login {platform}"
            )
        await _wait_for_manual_login(context, platform)

    return None, context


async def _wait_for_manual_login(context, platform: str, timeout: int = 600):
    """等待用户手动登录后关闭浏览器（数据已自动持久化）"""
    import asyncio
    import threading

    login_urls = {
        "toutiao": "https://mp.toutiao.com/profile_v4/",
        "zhihu": "https://www.zhihu.com/signin",
        "xiaohongshu": "https://creator.xiaohongshu.com/login",
    }

    page = await context.new_page()
    url = login_urls.get(platform, "")
    if url:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)

    print(f"\n{'='*60}")
    print(f"[LOGIN] 浏览器已打开，请在浏览器中登录 {platform}")
    print(f"[LOGIN] 登录完成后，请回到此窗口按 回车键")
    print(f"{'='*60}\n")

    loop = asyncio.get_event_loop()
    user_confirmed = asyncio.Event()

    def wait_for_enter():
        input("")
        loop.call_soon_threadsafe(user_confirmed.set)

    t = threading.Thread(target=wait_for_enter, daemon=True)
    t.start()

    try:
        await asyncio.wait_for(user_confirmed.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        print(f"[LOGIN] ⏰ 等待超时（{timeout}秒）")
        raise TimeoutError(f"等待 {platform} 手动登录超时")

    print(f"[LOGIN] ✅ {platform} 登录状态已保存到 {_user_data_dir(platform)}")
    await page.close()
