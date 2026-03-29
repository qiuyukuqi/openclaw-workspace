#!/usr/bin/env python3
"""
AI字幕清洗工具
输入：Whisper生成的SRT字幕
输出：AI清洗后的高质量SRT字幕

用法：
  python3 subtitle_clean.py input.srt [-o output.srt] [-t 主题] [-l zh-CN]
  python3 subtitle_clean.py input.srt --bilingual              # 生成中英双语
  python3 subtitle_clean.py input.srt --backend gemini         # 用Gemini（需翻墙）
"""

import argparse
import json
import re
import sys
import os
import urllib.request
import urllib.error

# === 配置 ===
QWEN_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "sk-bdc4ae848a284a459a9e9c2413daa8ce")
QWEN_MODEL = "qwen-plus"
QWEN_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"

# 代理（用于Gemini）
PROXY = os.environ.get("HTTPS_PROXY", os.environ.get("https_proxy", ""))


def parse_srt(text):
    """解析SRT文件，返回 [{start, end, text}]"""
    blocks = re.split(r'\n\s*\n', text.strip())
    subs = []
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 2:
            continue
        # 找时间轴行
        time_match = None
        for i, line in enumerate(lines):
            m = re.match(r'(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})', line)
            if m:
                time_match = (m.group(1), m.group(2))
                text_lines = lines[i+1:]
                break
        if time_match:
            text = ' '.join(text_lines).strip()
            subs.append({
                'start': time_match[0],
                'end': time_match[1],
                'text': text
            })
    return subs


def format_srt_time(t):
    """统一时间格式为逗号分隔"""
    return t.replace('.', ',')


def to_srt(subs):
    """转回SRT格式"""
    lines = []
    for i, sub in enumerate(subs, 1):
        lines.append(str(i))
        lines.append(f"{format_srt_time(sub['start'])} --> {format_srt_time(sub['end'])}")
        lines.append(sub['text'])
        lines.append('')
    return '\n'.join(lines)


def call_qwen(prompt, system=None):
    """调用通义千问API"""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    body = json.dumps({
        "model": QWEN_MODEL,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 8000
    }).encode()

    req = urllib.request.Request(QWEN_URL, data=body, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {QWEN_API_KEY}"
    })

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            return result["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        print(f"❌ API错误: {e.code} {e.read().decode()[:200]}", file=sys.stderr)
        sys.exit(1)


def call_gemini(prompt, system=None):
    """调用Gemini API（需要翻墙）"""
    if not GEMINI_API_KEY:
        print("❌ 需要设置 GEMINI_API_KEY 环境变量", file=sys.stderr)
        sys.exit(1)

    url = GEMINI_URL.format(model=GEMINI_MODEL, key=GEMINI_API_KEY)

    contents = []
    if system:
        contents.append({"role": "user", "parts": [{"text": f"系统指令：{system}"}]})
        contents.append({"role": "model", "parts": [{"text": "明白，我会遵循这些指令。"}]})
    contents.append({"role": "user", "parts": [{"text": prompt}]})

    body = json.dumps({"contents": contents, "generationConfig": {"temperature": 0.3}}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})

    # 设置代理
    if PROXY:
        import socket
        proxy_handler = urllib.request.ProxyHandler({"https": PROXY, "http": PROXY})
        opener = urllib.request.build_opener(proxy_handler)
    else:
        opener = urllib.request.build_opener()

    try:
        with opener.open(req, timeout=120) as resp:
            result = json.loads(resp.read())
            return result["candidates"][0]["content"]["parts"][0]["text"]
    except urllib.error.HTTPError as e:
        print(f"❌ Gemini API错误: {e.code} {e.read().decode()[:200]}", file=sys.stderr)
        sys.exit(1)


def clean_subtitle_text(text, lang="zh-CN"):
    """用AI清洗字幕纯文本"""
    lang_name = "简体中文" if "zh-CN" in lang or "zh-Hans" in lang else "繁体中文"
    if lang.startswith("en"):
        lang_name = "English"

    system = f"你是一个专业的字幕校对编辑。你的任务是清洗和优化{lang_name}字幕。"
    prompt = f"""以下是视频的原始字幕（SRT格式），请进行清洗和优化：

要求：
1. 去除口语废话（嗯、啊、就是、然后、那个、这个、就是说、对吧、你知道吗）
2. 修正同音字错误和错别字
3. 优化断句，每句不超过15个字，语义完整
4. 修正标点符号
5. 保留所有时间轴编号，严格保持SRT格式
6. 不要合并或拆分时间轴条目（每条编号对应的时间轴保持不变）
7. 如果某条字幕内容为空或无法识别，保留时间轴但将内容改为"..."
8. 如果有明显的专有名词识别错误，根据上下文修正

原始字幕：
{text}

请直接输出清洗后的SRT内容，不要加任何解释。"""

    return prompt, system


def bilingual_prompt(text, lang="zh-CN"):
    """生成双语字幕提示词"""
    system = "你是一个专业的字幕翻译和校对编辑。"
    prompt = f"""以下是的视频字幕，请：

1. 先清洗中文内容（去口语废话、修错别字、优化断句）
2. 翻译成英文
3. 合并为双语SRT格式：每条字幕第一行中文，第二行英文
4. 严格保持原有时间轴和编号不变

原始字幕：
{text}

请直接输出双语SRT内容，不要加任何解释。"""

    return prompt, system


def merge_subtitle_pairs(cleaned_text, original_subs):
    """将AI输出的SRT与原始时间轴合并，防止时间轴错乱"""
    cleaned_subs = parse_srt(cleaned_text)

    # 如果AI输出的条目数和原始一致，直接用AI的文本
    if len(cleaned_subs) == len(original_subs):
        for i, cs in enumerate(cleaned_subs):
            original_subs[i]['text'] = cs['text']
        return original_subs

    # 不一致时，尝试按编号匹配
    cleaned_by_id = {}
    for block in re.split(r'\n\s*\n', cleaned_text.strip()):
        lines = block.strip().split('\n')
        if not lines:
            continue
        try:
            idx = int(lines[0]) - 1
            text_lines = [l for l in lines[2:] if l.strip()]
            cleaned_by_id[idx] = '\n'.join(text_lines)
        except (ValueError, IndexError):
            continue

    for i in range(len(original_subs)):
        if i in cleaned_by_id:
            original_subs[i]['text'] = cleaned_by_id[i]

    return original_subs


def process(input_file, output_file, topic="", lang="zh-CN", bilingual=False, backend="qwen"):
    """主处理流程"""

    # 读取输入
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()

    if not content.strip():
        print("❌ 输入文件为空", file=sys.stderr)
        sys.exit(1)

    print(f"📄 读取字幕: {input_file} ({len(content)} bytes)")

    # 解析原始字幕
    original_subs = parse_srt(content)
    print(f"📝 共 {len(original_subs)} 条字幕")

    # 构建提示词
    topic_line = f"\n此视频的主题是：{topic}" if topic else ""
    srt_for_ai = content + topic_line

    if bilingual:
        prompt, system = bilingual_prompt(srt_for_ai, lang)
        label = "双语字幕生成"
    else:
        prompt, system = clean_subtitle_text(srt_for_ai, lang)
        label = "字幕清洗"

    print(f"🤖 调用 {backend} {label}...")
    print(f"   字幕约 {len(content)} 字符，可能需要1-2分钟")

    # 调用AI
    if backend == "gemini":
        result = call_gemini(prompt, system)
    else:
        result = call_qwen(prompt, system)

    # 提取SRT内容（AI可能包裹在代码块中）
    srt_match = re.search(r'```(?:srt)?\s*\n([\s\S]*?)\n```', result)
    if srt_match:
        result = srt_match.group(1)

    # 合并时间轴
    merged = merge_subtitle_pairs(result, original_subs)
    output = to_srt(merged)

    # 写输出
    out_path = output_file or input_file.replace('.srt', '_cleaned.srt')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(output)

    print(f"✅ 完成！输出: {out_path}")
    print(f"   原始: {len(original_subs)} 条 → 清洗后: {len(merged)} 条")

    return out_path


def main():
    parser = argparse.ArgumentParser(description="AI字幕清洗工具")
    parser.add_argument("input", help="输入SRT文件路径")
    parser.add_argument("-o", "--output", help="输出SRT文件路径（默认: input_cleaned.srt）")
    parser.add_argument("-t", "--topic", default="", help="视频主题（帮助AI理解上下文）")
    parser.add_argument("-l", "--lang", default="zh-CN", help="语言 (zh-CN/zh-TW/en)")
    parser.add_argument("--bilingual", action="store_true", help="生成中英双语字幕")
    parser.add_argument("--backend", choices=["qwen", "gemini"], default="qwen", help="AI后端 (默认: qwen)")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"❌ 文件不存在: {args.input}", file=sys.stderr)
        sys.exit(1)

    process(args.input, args.output, args.topic, args.lang, args.bilingual, args.backend)


if __name__ == "__main__":
    main()
