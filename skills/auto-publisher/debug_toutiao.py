"""Toutiao debug - use profile directly"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

user_data_dir = os.path.abspath("auth/toutiao_data")
options = uc.ChromeOptions()
options.add_argument("--window-size=1920,1080")
options.add_argument("--no-sandbox")

print("[1] Starting Chrome with profile...")
try:
    driver = uc.Chrome(options=options, headless=False, use_subprocess=True, version_main=146, user_data_dir=user_data_dir)
except Exception as e:
    print(f"Profile mode failed: {e}")
    print("[1b] Falling back to new profile + cookie injection...")
    import json
    driver = uc.Chrome(options=options, headless=False, use_subprocess=True, version_main=146)
    driver.get("https://mp.toutiao.com")
    time.sleep(2)
    state_path = os.path.join("auth", "toutiao_data", "storage_state.json")
    with open(state_path, "r", encoding="utf-8") as f:
        state = json.load(f)
    for c in state.get("cookies", []):
        d = {"name": c["name"], "value": c["value"]}
        if c.get("domain"): d["domain"] = c["domain"]
        if c.get("path"): d["path"] = c["path"]
        try: driver.add_cookie(d)
        except: pass

driver.set_window_size(1920, 1080)
print(f"[2] Title: {driver.title}")

print("[3] Opening editor...")
driver.get("https://mp.toutiao.com/profile_v4/graphic/articles/new")
print("[4] Waiting 15s...")
time.sleep(15)

driver.save_screenshot(os.path.join("temp", "debug_01.png"))

editors = driver.find_elements(By.CSS_SELECTOR, "[contenteditable='true']")
print(f"[5] Contenteditable: {len(editors)}")

file_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
print(f"[6] File inputs: {len(file_inputs)}")

buttons = driver.find_elements(By.CSS_SELECTOR, "button")
btns = [(b.text.strip(), b.is_displayed()) for b in buttons if b.text.strip()]
print(f"[7] Buttons: {btns}")

# Click menu if no editor
if not editors:
    print("[8] No editor, clicking menu...")
    menus = driver.find_elements(By.CSS_SELECTOR, ".byte-menu-item")
    for m in menus:
        if "\u6587\u7ae0" in m.text:
            driver.execute_script("arguments[0].click();", m)
            break
    time.sleep(15)
    editors = driver.find_elements(By.CSS_SELECTOR, "[contenteditable='true']")
    print(f"[9] Contenteditable after menu: {len(editors)}")
    driver.save_screenshot(os.path.join("temp", "debug_02.png"))

print("[10] Done")
try: driver.quit()
except: pass
