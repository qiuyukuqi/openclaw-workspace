"""Toutiao publisher - fix overlay issue"""
import os
import asyncio
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from playwright.async_api import async_playwright
from core.login_manager import get_browser_context
from core.markdown_converter import md_to_html
from core.notifier import notify_success, notify_failure
from config import TEMP_DIR, TOUTIAO_EDITOR_URL


async def main():
    title = "AI自动化发布的优势与挑战"
    content_file = "test_article.md"
    cover_file = "test_cover.jpg"

    with open(content_file, "r", encoding="utf-8") as f:
        content = f.read()

    pw = await async_playwright().start()
    try:
        print("[toutiao] Starting browser (headful)...")
        _browser, context = await get_browser_context(pw, "toutiao", headless=False)
        page = await context.new_page()

        # 1. Open editor URL
        print("[toutiao] Opening editor page...")
        await page.goto(TOUTIAO_EDITOR_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)

        # 2. Click "文章" menu - handle overlay by scrolling and using JS
        print("[toutiao] Clicking article menu...")
        # First scroll the menu item into view
        await page.evaluate("""
            var items = document.querySelectorAll('.byte-menu-item');
            for (var i = 0; i < items.length; i++) {
                if (items[i].textContent.indexOf('\u6587\u7ae0') !== -1) {
                    items[i].scrollIntoView({block: 'center'});
                    break;
                }
            }
        """)
        await asyncio.sleep(0.5)
        # Click via JS to bypass overlay
        await page.evaluate("""
            var items = document.querySelectorAll('.byte-menu-item');
            for (var i = 0; i < items.length; i++) {
                if (items[i].textContent.indexOf('\u6587\u7ae0') !== -1) {
                    items[i].click();
                    break;
                }
            }
        """)
        print("[toutiao] Clicked article menu via JS")
        await asyncio.sleep(5)

        # 3. Screenshot to see state
        await page.screenshot(path=os.path.join(TEMP_DIR, "tt_01_after_menu.png"))
        
        # 4. Wait for editor - try multiple selectors
        editor = None
        for attempt in range(5):
            print(f"[toutiao] Attempt {attempt+1} to find editor...")
            # Try all possible editor selectors
            for sel in ["[contenteditable='true']", "#title", ".ql-editor", ".ProseMirror", 
                         "div[class*='editor']", "div[class*='Editor']", "textarea", 
                         "input[placeholder*='标题']"]:
                el = await page.query_selector(sel)
                if el:
                    try:
                        visible = await el.is_visible()
                        if visible:
                            editor = el
                            print(f"[toutiao] Editor found: {sel}")
                            break
                    except:
                        pass
            if editor:
                break
            # Reload and retry
            await page.reload(wait_until="domcontentloaded")
            await asyncio.sleep(3)
            await page.evaluate("""
                var items = document.querySelectorAll('.byte-menu-item');
                for (var i = 0; i < items.length; i++) {
                    if (items[i].textContent.indexOf('\u6587\u7ae0') !== -1) {
                        items[i].click();
                        break;
                    }
                }
            """)
            await asyncio.sleep(8)
        
        if not editor:
            await page.screenshot(path=os.path.join(TEMP_DIR, "tt_error_no_editor.png"))
            print("[toutiao] ERROR: Editor not found after 5 attempts")
            print("[toutiao] Dumping page URL and visible elements...")
            url = page.url
            print(f"[toutiao] URL: {url}")
            # Check if we got redirected
            if "login" in url.lower():
                print("[toutiao] Redirected to login page!")
            raise RuntimeError("Editor not found")

        await page.screenshot(path=os.path.join(TEMP_DIR, "tt_02_editor_found.png"))

        # 5. Fill title
        print(f"[toutiao] Filling title: {title[:30]}...")
        tag = await editor.evaluate("e => e.tagName")
        await editor.click()
        await asyncio.sleep(0.3)
        if tag in ("INPUT", "TEXTAREA"):
            await editor.fill(title)
        else:
            await page.keyboard.type(title, delay=30)
        await page.screenshot(path=os.path.join(TEMP_DIR, "tt_03_title.png"))

        # 6. Fill content
        print("[toutiao] Filling content...")
        await page.keyboard.press("Enter")
        await asyncio.sleep(0.5)
        html_content = md_to_html(content)
        await page.evaluate("(html) => { document.execCommand('insertHTML', false, html); }", html_content)
        await asyncio.sleep(1)
        await page.screenshot(path=os.path.join(TEMP_DIR, "tt_04_content.png"))

        # 7. Upload cover image
        print(f"[toutiao] Uploading cover: {cover_file}...")
        file_inputs = await page.query_selector_all("input[type='file']")
        for inp in file_inputs:
            try:
                abs_path = os.path.abspath(cover_file)
                await inp.set_input_files(abs_path)
                print("[toutiao] Cover uploaded")
                break
            except Exception as e:
                print(f"[toutiao] upload failed on input: {e}")
                continue
        await asyncio.sleep(3)
        await page.screenshot(path=os.path.join(TEMP_DIR, "tt_05_cover.png"))

        # 8. Click publish - try button text match
        print("[toutiao] Clicking publish...")
        await asyncio.sleep(1)
        
        # Try "预览并发布" first (bottom of page)
        clicked = await page.evaluate("""
            var btns = document.querySelectorAll('button');
            for (var i = btns.length - 1; i >= 0; i--) {
                var t = btns[i].textContent.trim();
                if (t === '\u9884\u89c8\u5e76\u53d1\u5e03') {
                    btns[i].click();
                    return 'clicked: ' + t;
                }
            }
            return 'not found';
        """)
        print(f"[toutiao] {clicked}")
        await asyncio.sleep(5)
        await page.screenshot(path=os.path.join(TEMP_DIR, "tt_06_after_publish_click.png"))

        # 9. If modal appeared, upload cover in modal and confirm
        # Check for upload dialog
        modal_inputs = await page.query_selector_all("input[type='file']")
        if len(modal_inputs) > 0:
            print("[toutiao] Modal detected, uploading cover...")
            try:
                abs_path = os.path.abspath(cover_file)
                await modal_inputs[0].set_input_files(abs_path)
                print("[toutiao] Cover uploaded in modal")
                await asyncio.sleep(5)
            except Exception as e:
                print(f"[toutiao] Modal upload failed: {e}")
            
            await page.screenshot(path=os.path.join(TEMP_DIR, "tt_07_modal_cover.png"))
            
            # Hide drawers
            await page.evaluate("""
                var els = document.querySelectorAll('.byte-drawer-wrapper, .byte-drawer-mask');
                for (var i = 0; i < els.length; i++) {
                    els[i].style.display = 'none';
                    els[i].style.pointerEvents = 'none';
                }
            """)
            await asyncio.sleep(1)
        
        # 10. Click confirm publish
        print("[toutiao] Confirming publish...")
        confirmed = await page.evaluate("""
            var btns = document.querySelectorAll('button');
            for (var i = btns.length - 1; i >= 0; i--) {
                var t = btns[i].textContent.trim();
                if (t === '\u9884\u89c8\u5e76\u53d1\u5e03') {
                    btns[i].dispatchEvent(new MouseEvent('click', {bubbles: true}));
                    return true;
                }
            }
            return false;
        """)
        print(f"[toutiao] Confirmed: {confirmed}")
        await asyncio.sleep(5)
        
        screenshot = os.path.join(TEMP_DIR, "tt_08_final.png")
        await page.screenshot(path=screenshot)
        notify_success("toutiao", title, screenshot)
        print("[toutiao] Done!")
        
        await context.close()
    except Exception as e:
        print(f"[toutiao] ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
