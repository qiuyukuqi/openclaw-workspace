"""头条号微头条发布 - CDP连接本地Chrome"""
import os, sys, time, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright
from config import TEMP_DIR

CDP_URL = "http://localhost:18800"
PUBLISH_URL = "https://mp.toutiao.com/profile_v4/weitoutiao/publish?from=toutiao_pc"


def publish_weitoutiao(content, image_path=None):
    with sync_playwright() as p:
        print("[toutiao] Connecting to Chrome via CDP...")
        try:
            browser = p.chromium.connect_over_cdp(CDP_URL)
        except Exception as e:
            print(f"[toutiao] Cannot connect: {e}")
            print("[toutiao] Please start Chrome with: chrome --remote-debugging-port=18800")
            return False

        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.new_page()

        # Navigate to publish page
        print("[toutiao] Opening publish page...")
        page.goto(PUBLISH_URL, wait_until="domcontentloaded", timeout=30000)
        time.sleep(5)

        # Close popups/drawers
        page.evaluate("""
            () => {
                document.querySelectorAll('.byte-drawer-mask, .publish-assistant-old, [class*="drawer-mask"]').forEach(el => {
                    el.style.display = 'none';
                });
            }
        """)
        time.sleep(1)

        # Wait for contenteditable editor
        print("[toutiao] Finding editor...")
        editor = None
        for sel in ["div[contenteditable='true']", ".weitoutiao-editor", "textarea"]:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=3000):
                    editor = el
                    print(f"[toutiao] Editor found: {sel}")
                    break
            except: pass

        if not editor:
            page.screenshot(path=os.path.join(TEMP_DIR, "tt_error.png"))
            print("[toutiao] Editor not found")
            page.close()
            return False

        # Fill content via JS
        print(f"[toutiao] Filling content ({len(content)} chars)...")
        js_content = content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')
        page.evaluate(f"""
            () => {{
                const editor = document.querySelector('div[contenteditable="true"]');
                if (editor) {{
                    editor.innerHTML = `{js_content}`;
                    editor.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    editor.dispatchEvent(new Event('change', {{ bubbles: true }}));
                }}
            }}
        """)
        time.sleep(2)
        page.screenshot(path=os.path.join(TEMP_DIR, "tt_01_filled.png"))

        # Upload image
        if image_path and os.path.exists(image_path):
            print(f"[toutiao] Uploading image: {image_path}")
            try:
                # Click image button
                img_btn = page.locator('text=图片').first
                if img_btn.is_visible(timeout=2000):
                    img_btn.click()
                    time.sleep(1.5)

                    # Click local upload
                    local_btn = page.locator('text=本地上传').first
                    if local_btn.is_visible(timeout=2000):
                        local_btn.click()
                        time.sleep(1)

                    # Set file
                    file_input = page.locator('input[type="file"]').first
                    if file_input.count() > 0:
                        file_input.set_input_files(os.path.abspath(image_path))
                        time.sleep(3)

                        # Click confirm
                        confirm = page.locator('button:has-text("确定")').last
                        if confirm.is_visible(timeout=3000):
                            confirm.click()
                            time.sleep(1.5)
                        print("[toutiao] Image uploaded!")
                    else:
                        print("[toutiao] No file input found")
                else:
                    print("[toutiao] Image button not found")
            except Exception as e:
                print(f"[toutiao] Image upload failed: {e}")

            page.screenshot(path=os.path.join(TEMP_DIR, "tt_02_image.png"))

        # Click publish
        print("[toutiao] Clicking publish...")
        try:
            pub_btn = page.locator('button:has-text("发布")').first
            if pub_btn.is_visible(timeout=3000):
                pub_btn.click()
                print("[toutiao] Publish clicked!")
                time.sleep(5)

                # Check result
                current_url = page.url
                page.screenshot(path=os.path.join(TEMP_DIR, "tt_03_result.png"))
                print(f"[toutiao] Current URL: {current_url}")
                print("[toutiao] Done!")
                page.close()
                return True
            else:
                print("[toutiao] Publish button not found")
                page.screenshot(path=os.path.join(TEMP_DIR, "tt_error.png"))
                page.close()
                return False
        except Exception as e:
            print(f"[toutiao] Publish failed: {e}")
            page.screenshot(path=os.path.join(TEMP_DIR, "tt_error.png"))
            page.close()
            return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", default=None)  # not used for weitoutiao
    parser.add_argument("--content", default="test_article.md")
    parser.add_argument("--cover", default=None)
    args = parser.parse_args()

    with open(args.content, "r", encoding="utf-8") as f:
        content = f.read()

    if len(content) < 100:
        content += "\n\n作为一个人工智能助手，我正在学习如何使用各种平台和工具。今日头条是一个很好的内容创作和分享平台，感谢头条提供这么好的创作平台！"

    publish_weitoutiao(content, args.cover)


if __name__ == "__main__":
    main()
