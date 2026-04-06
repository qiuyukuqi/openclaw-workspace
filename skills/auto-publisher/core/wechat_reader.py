#!/usr/bin/env python3
"""微信公众号文章读取器
从公众号文章URL提取标题和正文内容（Markdown格式）。
"""
import re
import json
import sys

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("需要安装依赖: pip install requests beautifulsoup4")
    sys.exit(1)


def fetch_wechat_article(url: str) -> dict:
    """从公众号文章URL提取内容

    Args:
        url: 公众号文章URL (mp.weixin.qq.com)

    Returns:
        dict: {title, author, content_html, content_markdown, publish_time}
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
    }

    resp = requests.get(url, headers=headers, timeout=15)
    resp.encoding = "utf-8"
    soup = BeautifulSoup(resp.text, "html.parser")

    # 标题
    title_el = soup.select_one("#activity-name") or soup.select_one(".rich_media_title")
    title = title_el.get_text(strip=True) if title_el else ""

    # 作者
    author_el = soup.select_one("#js_name") or soup.select_one(".rich_media_meta_nickname a")
    author = author_el.get_text(strip=True) if author_el else ""

    # 正文
    content_el = soup.select_one("#js_content") or soup.select_one(".rich_media_content")
    if not content_el:
        return {"title": title, "author": author, "error": "正文内容未找到"}

    # 清理正文：移除脚本和样式
    for tag in content_el.find_all(["script", "style"]):
        tag.decompose()

    content_html = str(content_el)

    # 简单HTML转Markdown
    content_markdown = _html_to_markdown(content_el)

    return {
        "title": title,
        "author": author,
        "content_html": content_html,
        "content_markdown": content_markdown,
        "publish_time": soup.select_one("#publish_time"),
        "url": url,
    }


def _html_to_markdown(el) -> str:
    """简单HTML转Markdown（专门处理公众号文章格式）"""
    parts = []

    def _convert(node):
        if isinstance(node, str):
            parts.append(node)
            return
        tag = node.name

        if tag in ("p", "section", "div"):
            # 处理段落
            children_text = "".join(_convert(c) for c in node.children)
            if children_text.strip():
                parts.append(children_text.strip() + "\n\n")
        elif tag == "h1":
            parts.append(f"# {_get_text(node)}\n\n")
        elif tag == "h2":
            parts.append(f"## {_get_text(node)}\n\n")
        elif tag == "h3":
            parts.append(f"### {_get_text(node)}\n\n")
        elif tag == "strong" or tag == "b":
            parts.append(f"**{_get_text(node)}**")
        elif tag == "em" or tag == "i":
            parts.append(f"*{_get_text(node)}*")
        elif tag == "br":
            parts.append("\n")
        elif tag == "img":
            src = node.get("data-src") or node.get("src", "")
            alt = node.get("alt", "")
            if src:
                parts.append(f"![{alt}]({src})\n")
        elif tag == "blockquote":
            text = _get_text(node)
            parts.append(f"> {text}\n\n")
        elif tag == "a":
            href = node.get("href", "")
            text = _get_text(node)
            if href and text:
                parts.append(f"[{text}]({href})")
            else:
                parts.append(text)
        elif tag in ("ul", "ol"):
            for li in node.find_all("li", recursive=False):
                parts.append(f"- {_get_text(li)}\n")
            parts.append("\n")
        else:
            for child in node.children:
                _convert(child)

    def _get_text(node):
        return node.get_text(strip=True) if hasattr(node, "get_text") else str(node)

    _convert(el)
    result = "".join(parts)
    # 清理多余空行
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result.strip()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="读取公众号文章")
    parser.add_argument("url", help="公众号文章URL")
    parser.add_argument("--json", action="store_true", help="JSON格式输出")
    parser.add_argument("--markdown", action="store_true", help="只输出Markdown正文")
    args = parser.parse_args()

    result = fetch_wechat_article(args.url)

    if args.json:
        # 不输出HTML（太大）
        result.pop("content_html", None)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.markdown:
        print(f"# {result['title']}\n\n来源：{result.get('author', '')} ({args.url})\n\n---\n\n")
        print(result.get("content_markdown", result.get("error", "")))
    else:
        print(f"标题: {result['title']}")
        print(f"作者: {result.get('author', '')}")
        print(f"正文长度: {len(result.get('content_markdown', ''))} 字符")
        if "error" in result:
            print(f"错误: {result['error']}")
        else:
            print(f"\n--- 预览 ---")
            text = result.get("content_markdown", "")[:500]
            print(text + ("..." if len(result.get("content_markdown", "")) > 500 else ""))
