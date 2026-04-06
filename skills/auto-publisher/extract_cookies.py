#!/usr/bin/env python3
"""从Windows Chrome Cookie数据库提取登录状态
用法: python extract_cookies.py <platform>
"""
import sys, os, json, sqlite3, shutil, tempfile

def get_cookie_path():
    p = os.path.expandvars(r"%LocalAppData%\Google\Chrome\User Data\Default\Network\Cookies")
    if os.path.exists(p):
        return p
    return None

def decrypt_value(encrypted_value):
    if not encrypted_value:
        return ""
    if encrypted_value[:3] == b'v10':
        try:
            import ctypes, ctypes.wintypes
            class DATA_BLOB(ctypes.Structure):
                _fields_ = [('cbData', ctypes.wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_char))]
            CryptUnprotectData = ctypes.windll.crypt32.CryptUnprotectData
            CryptUnprotectData.argtypes = [ctypes.POINTER(DATA_BLOB), ctypes.POINTER(ctypes.c_ulong),
                ctypes.POINTER(DATA_BLOB), ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(DATA_BLOB), ctypes.c_ulong]
            CryptUnprotectData.restype = ctypes.wintypes.BOOL
            blob_in = DATA_BLOB()
            blob_in.cbData = len(encrypted_value)
            blob_in.pbData = ctypes.create_string_buffer(encrypted_value, len(encrypted_value))
            blob_out = DATA_BLOB()
            if CryptUnprotectData(ctypes.byref(blob_in), None, None, None, None, ctypes.byref(blob_out), 0):
                value = ctypes.string_at(blob_out.pbData, blob_out.cbData)
                ctypes.windll.kernel32.LocalFree(blob_out.pbData)
                return value.decode('utf-8', errors='replace')
        except Exception as e:
            print(f"[WARN] 解密失败: {e}")
    try:
        return encrypted_value.decode('utf-8')
    except:
        return ""

def extract(domain_keywords):
    cookie_path = get_cookie_path()
    if not cookie_path:
        print("[ERROR] 未找到Chrome Cookie文件")
        return []
    
    # 复制到临时文件（Chrome运行时文件被锁，需要先关闭Chrome）
    tmp = os.path.join(tempfile.gettempdir(), "chrome_cookies_copy")
    try:
        shutil.copy2(cookie_path, tmp)
    except PermissionError:
        print("[ERROR] Chrome正在运行，Cookie文件被锁定")
        print("[HINT] 请先完全关闭Chrome（任务管理器确认没有chrome.exe进程），然后重试")
        print("[HINT] 或者在CMD运行: taskkill /F /IM chrome.exe")
        return []
    
    cookies = []
    try:
        conn = sqlite3.connect(tmp)
        cursor = conn.cursor()
        for kw in domain_keywords:
            cursor.execute("SELECT name, encrypted_value, host_key, path, is_secure, is_httponly, expires_utc, samesite FROM cookies WHERE host_key LIKE ?", (f"%{kw}%",))
            for name, enc_val, host, path, secure, httponly, expires, ss in cursor.fetchall():
                val = decrypt_value(enc_val)
                cookies.append({
                    "name": name, "value": val, "domain": host, "path": path,
                    "httpOnly": bool(httponly), "secure": bool(secure),
                    "sameSite": {0:"None",1:"Lax",2:"Strict",-1:"None"}.get(ss,"None"),
                    "expires": expires / 1000000 - 11644473600 if expires > 0 else -1,
                })
        conn.close()
    finally:
        try:
            os.remove(tmp)
        except:
            pass
    return cookies

DOMAINS = {
    "toutiao": ["toutiao.com", "douyin.com", "bytedance.com"],
    "zhihu": ["zhihu.com"],
    "xiaohongshu": ["xiaohongshu.com", "xhscdn.com"],
}

KEY_COOKIES = {
    "toutiao": ["sessionid"],
    "zhihu": ["z_c0", "_xsrf"],
    "xiaohongshu": ["web_session", "webId"],
}

def main():
    if len(sys.argv) < 2:
        print("用法: python extract_cookies.py <toutiao|zhihu|xiaohongshu|all>")
        sys.exit(1)
    
    platform = sys.argv[1]
    platforms = list(DOMAINS.keys()) if platform == "all" else [platform]
    os.makedirs("auth", exist_ok=True)
    
    for p in platforms:
        print(f"\n[{p}] 提取Cookie中...")
        raw = extract(DOMAINS[p])
        if not raw:
            continue
        # 去重
        seen = set()
        unique = []
        for c in raw:
            k = (c["name"], c["domain"])
            if k not in seen:
                seen.add(k)
                unique.append(c)
        
        state = {"cookies": unique, "origins": []}
        path = f"auth/{p}_state.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        
        print(f"[{p}] OK {len(unique)} cookies -> {path}")
        for kn in KEY_COOKIES.get(p, []):
            found = [c["value"][:20]+"..." for c in unique if c["name"] == kn]
            if found:
                print(f"[{p}] KEY [{kn}]: {found[0]}")

if __name__ == "__main__":
    main()
