"""Toutiao publisher using undetected-chromedriver"""
import os, sys, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import undetected_chromedriver as uc
from config import TEMP_DIR

def main():
    title = "AI自动化发布的优势与挑战"
    content_file = "test_article.md"
    cover_file = "test_cover.jpg"
    with open(content_file, "r", encoding="utf-8") as f:
        content = f.read()

    options = uc.ChromeOptions()
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")

    print("[toutiao] Starting undetected Chrome...")
    driver = uc.Chrome(options=options, headless=False, use_subprocess=True, version_main=146)
    driver.set_window_size(1920, 1080)

    # Inject cookies from saved state
    state_path = os.path.join("auth", "toutiao_data", "storage_state.json")
    if os.path.exists(state_path):
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
        # Navigate to toutiao domain first so cookies stick
        driver.get("https://mp.toutiao.com")
        time.sleep(2)
        for cookie in state.get("cookies", []):
            c = {"name": cookie["name"], "value": cookie["value"]}
            if cookie.get("domain"): c["domain"] = cookie["domain"]
            if cookie.get("path"): c["path"] = cookie["path"]
            try: driver.add_cookie(c)
            except: pass
        print("[toutiao] Injected cookies")

    try:
        print("[toutiao] Opening editor...")
        driver.get("https://mp.toutiao.com/profile_v4/graphic/articles/new")
        time.sleep(5)

        print("[toutiao] Clicking article menu...")
        menus = driver.find_elements("css selector", ".byte-menu-item")
        for m in menus:
            if "文章" in m.text:
                m.click()
                print("[toutiao] Clicked article menu")
                break
        time.sleep(10)

        driver.save_screenshot(os.path.join(TEMP_DIR, "uc_01.png"))

        # Find editor
        editor = None
        for sel in ["[contenteditable='true']", "#title", ".ql-editor", "textarea"]:
            try:
                e = driver.find_element("css selector", sel)
                if e.is_displayed():
                    editor = e
                    print(f"[toutiao] Editor found: {sel}")
                    break
            except: pass

        if not editor:
            driver.save_screenshot(os.path.join(TEMP_DIR, "uc_error.png"))
            print("[toutiao] ERROR: Editor not found")
            return

        driver.save_screenshot(os.path.join(TEMP_DIR, "uc_02.png"))

        # Fill title - use JS click to bypass overlay
        print(f"[toutiao] Title: {title[:30]}...")
        driver.execute_script("arguments[0].click();", editor)
        time.sleep(0.5)
        editor.send_keys(title)
        time.sleep(1)

        # Fill content
        from selenium.webdriver.common.keys import Keys
        editor.send_keys(Keys.ENTER)
        time.sleep(0.5)
        editor.send_keys(content[:200])
        time.sleep(1)

        # Close drawer mask first
        driver.execute_script("""
            document.querySelectorAll('.byte-drawer-mask, .byte-drawer-wrapper').forEach(function(e) {
                e.style.display = 'none'; e.style.pointerEvents = 'none';
            });
        """)
        time.sleep(0.5)

        # Upload cover
        abs_path = os.path.abspath(cover_file)
        file_inputs = driver.find_elements("css selector", "input[type='file']")
        if file_inputs:
            file_inputs[0].send_keys(abs_path)
            print("[toutiao] Cover uploaded")
            time.sleep(3)

        driver.save_screenshot(os.path.join(TEMP_DIR, "uc_03.png"))

        # Click publish
        print("[toutiao] Publishing...")
        buttons = driver.find_elements("css selector", "button")
        for b in buttons:
            t = b.text.strip()
            if "预览并发布" in t or t == "发布":
                driver.execute_script("arguments[0].scrollIntoView(true);", b)
                time.sleep(0.5)
                b.click()
                print(f"[toutiao] Clicked: {t}")
                break
        time.sleep(5)

        # Handle modal - upload cover if needed
        modal_inputs = driver.find_elements("css selector", "input[type='file']")
        if modal_inputs:
            try:
                modal_inputs[0].send_keys(abs_path)
                time.sleep(3)
            except: pass

        # Hide drawers and confirm
        driver.execute_script("""
            document.querySelectorAll('.byte-drawer-wrapper, .byte-drawer-mask').forEach(function(e) {
                e.style.display = 'none'; e.style.pointerEvents = 'none';
            });
        """)
        time.sleep(1)

        buttons = driver.find_elements("css selector", "button")
        for b in buttons:
            if b.text.strip() == "预览并发布":
                driver.execute_script("arguments[0].dispatchEvent(new MouseEvent('click', {bubbles: true}));", b)
                break
        time.sleep(5)

        driver.save_screenshot(os.path.join(TEMP_DIR, "uc_04_final.png"))
        print("[toutiao] Done!")

    except Exception as e:
        print(f"[toutiao] ERROR: {e}")
        import traceback; traceback.print_exc()
        try: driver.save_screenshot(os.path.join(TEMP_DIR, "uc_error.png"))
        except: pass
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
