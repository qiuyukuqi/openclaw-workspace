#!/usr/bin/env python3
import sys, os
os.environ['PYTHONIOENCODING'] = 'utf-8'
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
"""自动发布框架 - 统一CLI入口
用法:
    # 登录（在有GUI的电脑上运行）
    python publisher.py login toutiao
    python publisher.py login zhihu
    python publisher.py login xiaohongshu
    
    # 发布文章
    python publisher.py publish toutiao --title "标题" --content article.md
    python publisher.py publish toutiao --title "标题" --content article.md --cover cover.jpg
    python publisher.py publish zhihu --title "标题" --content article.md
    python publisher.py publish zhihu --content article.md --question-url "https://zhihu.com/question/xxx"
    python publisher.py publish xiaohongshu --title "标题" --content article.md --cover cover.jpg
    
    # 测试登录状态
    python publisher.py test toutiao
"""
import argparse
import asyncio
import sys
import os

# 将项目根目录加入path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def cmd_login(platform: str, force: bool = False):
    """有头模式打开浏览器，让用户扫码登录"""
    from core.login_manager import get_browser_context
    
    print(f"\n🔐 正在启动 {platform} 登录流程...")
    print(f"{'='*50}")
    
    from playwright.async_api import async_playwright
    
    pw = await async_playwright().start()
    try:
        _browser, context = await get_browser_context(pw, platform, headless=False, force_login=force)
        # 登录状态已自动持久化到 auth/{platform}_data/
        await context.close()
        print(f"\n✅ {platform} 登录状态已保存！")
        print(f"📁 数据目录: auth/{platform}_data/")
        print(f"📦 此目录即为持久化用户数据，直接在服务器上复用即可\n")
    except Exception as e:
        print(f"\n❌ 登录失败: {e}")
    finally:
        await pw.stop()


async def cmd_publish(platform: str, title: str, content_file: str,
                       cover_image: str = None, question_url: str = None,
                       tags: list[str] = None):
    """无头模式自动发布文章"""
    # 创建对应的发布器
    publishers = {
        "toutiao": "platforms.toutiao:ToutiaoPublisher",
        "zhihu": "platforms.zhihu:ZhihuPublisher",
        "xiaohongshu": "platforms.xiaohongshu:XiaohongshuPublisher",
    }
    
    module_path, class_name = publishers[platform].split(":")
    parts = module_path.split(".")
    module = __import__(module_path)
    for part in parts[1:]:
        module = getattr(module, part)
    PublisherClass = getattr(module, class_name)
    
    # 读取内容文件
    with open(content_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    print(f"\n🚀 开始发布到 {platform}")
    print(f"📌 标题: {title}")
    print(f"📄 内容长度: {len(content)} 字符")
    if cover_image:
        print(f"🖼️ 封面图: {cover_image}")
    if question_url:
        print(f"💬 回答问题: {question_url}")
    print(f"{'='*50}\n")
    
    # 创建发布器实例
    publisher = PublisherClass()
    try:
        # 初始化浏览器（无头模式）
        await publisher.setup(headless=True)
        # 执行发布
        kwargs = {}
        if question_url:
            kwargs["question_url"] = question_url
        if tags:
            kwargs["tags"] = tags
        result = await publisher.publish(title=title, content=content,
                                          cover_image=cover_image, **kwargs)
        if result:
            print(f"\n🎉 {platform} 发布完成！")
            return 0
        else:
            print(f"\n💥 {platform} 发布失败！")
            return 1
    except Exception as e:
        print(f"\n❌ 发布过程出错: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        await publisher.close()


async def cmd_test(platform: str):
    """测试登录状态是否有效"""
    from core.login_manager import has_state
    from playwright.async_api import async_playwright
    
    if not has_state(platform):
        print(f"❌ {platform} 没有已保存的登录数据")
        print(f"   请先运行: python publisher.py login {platform}")
        return 1
    
    print(f"✅ {platform} 登录数据目录存在")
    print(f"🔍 正在验证登录状态是否仍然有效...")
    
    pw = await async_playwright().start()
    try:
        from core.login_manager import get_browser_context
        _browser, context = await get_browser_context(pw, platform, headless=True)
        page = await context.new_page()
        
        # 访问平台首页验证cookie
        test_urls = {
            "toutiao": "https://mp.toutiao.com/profile_v4/graphic/articles/new",
            "zhihu": "https://www.zhihu.com",
            "xiaohongshu": "https://creator.xiaohongshu.com",
        }
        
        url = test_urls.get(platform, "")
        response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)
        
        # 截图
        from config import TEMP_DIR
        screenshot_path = os.path.join(TEMP_DIR, f"{platform}_test.png")
        await page.screenshot(path=screenshot_path, full_page=True)
        print(f"📸 测试截图: {screenshot_path}")
        print(f"[FEISHU_NOTIFY] {platform} 登录测试截图: {screenshot_path}")
        
        # 检查是否跳转到登录页
        current_url = page.url
        page_content = await page.content()
        
        login_keywords = ["login", "signin", "登录", "sign_in"]
        is_login_page = any(kw in current_url.lower() for kw in login_keywords)
        
        if is_login_page:
            print(f"❌ Cookie已过期，被重定向到登录页")
            print(f"   请重新运行: python publisher.py login {platform}")
            return 1
        else:
            print(f"✅ {platform} 登录状态有效！")
            print(f"   当前页面: {current_url[:80]}")
            return 0
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return 1
    finally:
        try:
            await pw.stop()
        except Exception:
            pass


def _null_context():
    """空上下文管理器"""
    from contextlib import asynccontextmanager
    @asynccontextmanager
    async def _ctx():
        yield
    return _ctx()


async def main():
    parser = argparse.ArgumentParser(
        description="跨平台自动发布工具 - 支持头条号、知乎、小红书",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s login toutiao              # 登录头条号
  %(prog)s publish toutiao --title "标题" --content article.md
  %(prog)s publish zhihu --title "标题" --content article.md --question-url "https://zhihu.com/question/123"
  %(prog)s publish xiaohongshu --title "标题" --content article.md --cover img.jpg
  %(prog)s test toutiao               # 测试登录状态
        """
    )
    
    sub = parser.add_subparsers(dest="command", help="子命令")
    
    # login命令
    login_parser = sub.add_parser("login", help="登录平台（需要GUI）")
    login_parser.add_argument("platform", choices=["toutiao", "zhihu", "xiaohongshu"],
                              help="平台名称")
    login_parser.add_argument("--force", "-f", action="store_true",
                              help="强制重新登录（即使已有登录数据）")
    
    # publish命令
    pub_parser = sub.add_parser("publish", help="发布文章（headless模式）")
    pub_parser.add_argument("platform", choices=["toutiao", "zhihu", "xiaohongshu"],
                            help="平台名称")
    pub_parser.add_argument("--title", "-t", required=True, help="文章标题")
    pub_parser.add_argument("--content", "-c", required=True, help="Markdown文件路径")
    pub_parser.add_argument("--cover", help="封面图路径")
    pub_parser.add_argument("--question-url", "-q", help="知乎回答模式的问题URL")
    pub_parser.add_argument("--tags", nargs="*", help="标签列表（小红书）")
    
    # test命令
    test_parser = sub.add_parser("test", help="测试登录状态是否有效")
    test_parser.add_argument("platform", choices=["toutiao", "zhihu", "xiaohongshu"],
                             help="平台名称")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    if args.command == "login":
        return await cmd_login(args.platform, force=args.force)
    elif args.command == "publish":
        return await cmd_publish(
            platform=args.platform,
            title=args.title,
            content_file=args.content,
            cover_image=args.cover,
            question_url=args.question_url,
            tags=args.tags,
        )
    elif args.command == "test":
        return await cmd_test(args.platform)
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code if exit_code is not None else 0)
