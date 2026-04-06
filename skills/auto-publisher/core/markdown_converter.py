"""Markdown转各平台HTML/纯文本"""
import re
import markdown


def md_to_html(content: str) -> str:
    """Markdown转HTML，用于头条号和知乎等富文本编辑器
    
    Args:
        content: Markdown文本
        
    Returns:
        HTML字符串
    """
    extensions = [
        "fenced_code",       # 代码块
        "tables",            # 表格
        "nl2br",             # 换行转<br>
        "sane_lists",        # 更好的列表
    ]
    html = markdown.markdown(content, extensions=extensions)
    return html


def md_to_plaintext(content: str) -> str:
    """Markdown转纯文本，用于小红书等只支持纯文本的平台
    
    - 去掉标题标记，保留文字
    - 去掉链接标记，保留文字
    - 去掉图片标记
    - 去掉加粗/斜体标记
    - 去掉代码块标记
    - 去掉列表标记
    - 保留换行
    
    Args:
        content: Markdown文本
        
    Returns:
        纯文本字符串
    """
    text = content
    # 去掉图片 ![alt](url)
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    # 链接保留文字 [text](url) → text
    text = re.sub(r'\[([^\]]*)\]\(.*?\)', r'\1', text)
    # 标题 ## → 去掉#号但保留文字和换行
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # 加粗 **text** → text
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    # 斜体 *text* → text
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    # 行内代码 `code` → code
    text = re.sub(r'`(.+?)`', r'\1', text)
    # 代码块 ```...```
    text = re.sub(r'```[\s\S]*?```', '', text)
    # 无序列表 - item → item
    text = re.sub(r'^[\s]*[-*+]\s+', '', text, flags=re.MULTILINE)
    # 有序列表 1. item → item
    text = re.sub(r'^[\s]*\d+\.\s+', '', text, flags=re.MULTILINE)
    # 引用 > text → text
    text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)
    # 分隔线
    text = re.sub(r'^[-*_]{3,}$', '', text, flags=re.MULTILINE)
    # 多余空行合并
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def extract_images(content: str) -> list[str]:
    """从Markdown中提取所有图片URL
    
    Args:
        content: Markdown文本
        
    Returns:
        图片URL列表
    """
    return re.findall(r'!\[.*?\]\((.*?)\)', content)
