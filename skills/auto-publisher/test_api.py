"""Toutiao publisher - try correct API format"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import requests
from core.markdown_converter import md_to_html
from config import TEMP_DIR


def main():
    title = "AI自动化发布的优势与挑战"
    content_file = "test_article.md"
    cover_file = "test_cover.jpg"

    with open(content_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Load cookies
    state_path = os.path.join("auth", "toutiao_data", "storage_state.json")
    with open(state_path, "r", encoding="utf-8") as f:
        state = json.load(f)

    session = requests.Session()
    for cookie in state.get("cookies", []):
        session.cookies.set(cookie["name"], cookie["value"], domain=cookie.get("domain", ".toutiao.com"))

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        "Referer": "https://mp.toutiao.com/profile_v4/graphic/articles/new",
        "Origin": "https://mp.toutiao.com",
    }

    # 1. Check login
    resp = session.get("https://mp.toutiao.com/mp/agw/media/user_login_status_api", headers=headers, timeout=10)
    print(f"[login] {resp.json()}")

    # 2. Upload cover image
    abs_path = os.path.abspath(cover_file)
    upload_url = "https://mp.toutiao.com/mp/agw/article_material/photo/upload_picture"
    upload_params = {"type": "ueditor", "pgc_watermark": "0", "action": "uploadimage", "encode": "utf-8", "is_private": "0"}
    with open(abs_path, "rb") as f:
        files = {"upfile": (os.path.basename(abs_path), f, "image/jpeg")}
        resp = session.post(upload_url, params=upload_params, headers=headers, files=files, timeout=30)
    upload_result = resp.json()
    print(f"[upload] {json.dumps(upload_result, ensure_ascii=False)[:300]}")
    web_uri = upload_result.get("data", {}).get("web_uri", "")

    # 3. Try multiple publish API formats
    html_content = md_to_html(content)

    # Format 1: Simple pgc_info format
    data1 = {
        "title": title,
        "content": html_content,
        "cover_image_web_uri": web_uri,
        "article_type": "article",
    }

    # Format 2: Nested pgc_info
    data2 = {
        "title": title,
        "content": html_content,
        "article_type": "article",
        "pgc_info": json.dumps({
            "title": title,
            "content": html_content,
            "web_uri": web_uri,
        }),
    }

    # Format 3: Draft style
    data3 = {
        "draft_status": 0,
        "article_type": "article",
        "title": title,
        "content": html_content,
        "cover_image_web_uri": web_uri,
        "tag": "auto_publish",
        "verify_content": html_content,
    }

    # Format 4: wtt format with signature
    data4 = {
        "title": title,
        "content": html_content,
        "abstract": content[:50],
        "article_type": "article",
        "cover_image_web_uri": web_uri,
    }

    endpoints = [
        "https://mp.toutiao.com/mp/agw/article/publish",
        "https://mp.toutiao.com/mp/agw/article/article/save",
        "https://mp.toutiao.com/mp/agw/article/article/publish",
        "https://mp.toutiao.com/mp/agw/content/article/publish",
    ]

    json_headers = {**headers, "Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest"}

    for ep in endpoints:
        for i, data in enumerate([data1, data2, data3, data4], 1):
            try:
                body = json.dumps(data, ensure_ascii=False).encode("utf-8")
                resp = session.post(ep, headers=json_headers, data=body, timeout=15)
                text = resp.text[:300]
                print(f"[{ep.split('/')[-1]}][f{i}] status={resp.status_code} body={text}")
            except Exception as e:
                print(f"[{ep.split('/')[-1]}][f{i}] error={e}")
            print()

    # Also try form-data style
    form_headers = {**headers, "X-Requested-With": "XMLHttpRequest"}
    for ep in endpoints:
        try:
            resp = session.post(ep, headers=form_headers, data=data3, timeout=15)
            text = resp.text[:300]
            print(f"[{ep.split('/')[-1]}][form] status={resp.status_code} body={text}")
        except Exception as e:
            print(f"[{ep.split('/')[-1]}][form] error={e}")

    # Try /core/article/add/ page endpoint
    resp = session.post("https://mp.toutiao.com/core/article/add/", headers=json_headers,
                       data=json.dumps(data3, ensure_ascii=False).encode("utf-8"), timeout=15)
    print(f"\n[core/add] status={resp.status_code} body={resp.text[:300]}")


if __name__ == "__main__":
    main()
