#!/usr/bin/env python3
"""
歌词视频生成流水线
输入：音频文件(MP3/WAV) + 歌词文本文件(TXT)
输出：歌词视频(MP4)

用法：
  python3 lyric_video.py audio.mp3 lyrics.txt
  python3 lyric_video.py audio.mp3 lyrics.txt -o output.mp4
  python3 lyric_video.py audio.mp3 lyrics.txt --bg 暗色星空 --font-size 48

歌词格式要求：
  纯文本，每行一句歌词，空行分隔段落
  也可以是SRT格式（带时间轴直接用）
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
import urllib.error

# === 配置 ===
DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "sk-bdc4ae848a284a459a9e9c2413daa8ce")
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "medium")  # tiny/base/small/medium/large

def set_whisper_model(model):
    global WHISPER_MODEL
    WHISPER_MODEL = model
OUTPUT_WIDTH = 1280
OUTPUT_HEIGHT = 720
FPS = 30

# ASS字幕样式预设
STYLES = {
    "默认": {
        "fontname": "Microsoft YaHei",
        "fontsize": 44,
        "primary_color": "&H00FFFFFF",      # 白色
        "secondary_color": "&H000000FF",
        "outline_color": "&H40000000",       # 半透明黑色描边
        "back_color": "&H00000000",
        "bold": False,
        "italic": False,
        "alignment": 5,                      # 底部居中 → 改为8屏幕居中
        "border_style": 1,
        "outline": 2,
        "shadow": 0,
        "margin_l": 80,
        "margin_r": 80,
        "margin_v": 40,
        "encoding": 0,
    },
    "居中大字": {
        "fontname": "Microsoft YaHei",
        "fontsize": 52,
        "primary_color": "&H00FFFFFF",
        "secondary_color": "&H000000FF",
        "outline_color": "&H40000000",
        "back_color": "&H00000000",
        "bold": True,
        "italic": False,
        "alignment": 8,                      # 屏幕正中
        "border_style": 1,
        "outline": 2,
        "shadow": 0,
        "margin_l": 60,
        "margin_r": 60,
        "margin_v": 40,
        "encoding": 0,
    },
    "底部小字": {
        "fontname": "Microsoft YaHei",
        "fontsize": 36,
        "primary_color": "&H00FFFFFF",
        "secondary_color": "&H000000FF",
        "outline_color": "&H40000000",
        "back_color": "&H00000000",
        "bold": False,
        "italic": False,
        "alignment": 2,                      # 底部居中
        "border_style": 1,
        "outline": 2,
        "shadow": 1,
        "margin_l": 40,
        "margin_r": 40,
        "margin_v": 30,
        "encoding": 0,
    },
}

# 背景图提示词
BG_PROMPTS = {
    "暗色星空": "A dark starry night sky with subtle purple nebula, minimal, dark background, cinematic, 4k",
    "蓝色海洋": "Dark ocean waves at night with moonlight reflection, cinematic dark blue background, 4k",
    "城市夜景": "Bokeh city lights at night, dark moody background, out of focus, cinematic, 4k",
    "森林": "Dark misty forest with moonlight rays, cinematic dark background, atmospheric, 4k",
    "雪花": "Dark background with gently falling snow, cinematic moody, cold atmosphere, 4k",
    "雨滴": "Dark window with raindrops, moody cinematic background, blue tones, 4k",
}


def check_dependencies():
    """检查依赖工具"""
    for cmd in ["ffmpeg", "whisper"]:
        result = subprocess.run(["which", cmd], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ 缺少工具: {cmd}")
            print(f"   ffmpeg: apt install ffmpeg")
            print(f"   whisper: pip install openai-whisper")
            sys.exit(1)


def get_audio_duration(audio_path):
    """获取音频时长"""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", audio_path],
        capture_output=True, text=True
    )
    return float(result.stdout.strip())


def is_srt(text):
    """判断文本是否为SRT格式"""
    return bool(re.search(r'\d{2}:\d{2}:\d{2}[,\.]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[,\.]\d{3}', text))


def parse_srt(text):
    """解析SRT文件"""
    blocks = re.split(r'\n\s*\n', text.strip())
    subs = []
    for block in blocks:
        lines = block.strip().split('\n')
        for i, line in enumerate(lines):
            m = re.match(r'(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})', line)
            if m:
                sub_text = ' '.join(lines[i+1:]).strip()
                if sub_text:
                    subs.append({
                        'start': m.group(1).replace('.', ','),
                        'end': m.group(2).replace('.', ','),
                        'text': sub_text
                    })
                break
    return subs


def lyrics_to_plain_lines(text):
    """将歌词文本转为纯文本行列表"""
    lines = []
    for line in text.strip().split('\n'):
        line = line.strip()
        if line and not line.startswith('#') and not line.startswith('//'):
            # 去除时间标签如 [00:12.34] 或 [00:12]
            line = re.sub(r'\[\d{1,2}:\d{2}(?:[.\:]\d{1,3})?\]', '', line).strip()
            if line:
                lines.append(line)
    return lines


def step1_generate_srt(audio_path, lyrics_path, work_dir):
    """步骤1：生成带时间轴的SRT字幕"""
    srt_path = os.path.join(work_dir, "subtitle.srt")

    # 如果歌词文件已经是SRT格式，直接用
    with open(lyrics_path, 'r', encoding='utf-8') as f:
        lyrics_text = f.read()

    if is_srt(lyrics_text):
        print("  检测到SRT格式歌词，直接使用")
        with open(srt_path, 'w', encoding='utf-8') as f:
            f.write(lyrics_text)
        return srt_path

    # 用Whisper生成时间轴
    print(f"  用Whisper({WHISPER_MODEL})识别音频时间轴...")
    duration = get_audio_duration(audio_path)
    print(f"  音频时长: {duration:.1f}s")

    result = subprocess.run(
        ["whisper", audio_path,
         "--model", WHISPER_MODEL,
         "--language", "zh",
         "--output_format", "srt",
         "--output_dir", work_dir,
         "--word_timestamps", "False",
         "--condition_on_previous_text", "False"],
        capture_output=True, text=True,
        timeout=max(300, int(duration * 2))
    )

    # Whisper输出文件名可能带后缀
    whisper_srt = os.path.join(work_dir, os.path.splitext(os.path.basename(audio_path))[0] + ".srt")
    if not os.path.exists(whisper_srt):
        # 搜索work_dir下的srt文件
        for f in os.listdir(work_dir):
            if f.endswith('.srt'):
                whisper_srt = os.path.join(work_dir, f)
                break

    if not os.path.exists(whisper_srt):
        print(f"  ❌ Whisper识别失败: {result.stderr[:200]}")
        sys.exit(1)

    # 解析Whisper结果
    whisper_subs = parse_srt(open(whisper_srt, encoding='utf-8').read())

    # 解析纯文本歌词
    lyrics_lines = lyrics_to_plain_lines(lyrics_text)

    if not whisper_subs or not lyrics_lines:
        print("  ❌ 无法获取时间轴或歌词为空")
        sys.exit(1)

    print(f"  Whisper识别: {len(whisper_subs)} 段")
    print(f"  歌词行数: {len(lyrics_lines)} 行")

    # 用AI对齐歌词和时间轴（调用通义千问）
    print("  AI对齐歌词和时间轴...")
    aligned = align_lyrics_with_timestamps(whisper_subs, lyrics_lines)

    # 写入SRT
    with open(srt_path, 'w', encoding='utf-8') as f:
        for i, sub in enumerate(aligned, 1):
            f.write(f"{i}\n{sub['start']} --> {sub['end']}\n{sub['text']}\n\n")

    print(f"  ✅ 对齐完成: {len(aligned)} 条字幕 → {srt_path}")
    return srt_path


def align_lyrics_with_timestamps(whisper_subs, lyrics_lines):
    """
    用AI将歌词行与Whisper时间轴对齐
    策略：基于Whisper识别的文本片段，找到与歌词行最匹配的时间段
    """
    # 构建Whisper文本片段
    whisper_segments = []
    for sub in whisper_subs:
        # 提取纯文本（去掉标点）
        text = re.sub(r'[，。！？、；：\u201c\u201d\u2018\u2019（）\\s]', '', sub['text'])
        whisper_segments.append({
            'start': sub['start'],
            'end': sub['end'],
            'clean_text': text,
            'original_text': sub['text']
        })

    # 拼接所有Whisper文本和歌词用于AI匹配
    whisper_text = '\n'.join([f"[{i}] {s['clean_text']}" for i, s in enumerate(whisper_segments)])
    lyrics_text = '\n'.join([f"[{i}] {line}" for i, line in enumerate(lyrics_lines)])

    prompt = f"""你是一个歌词时间轴对齐专家。请将歌词行与语音识别结果匹配对齐。

语音识别结果（带编号）：
{whisper_text}

歌词文本（带编号）：
{lyrics_text}

任务：为每行歌词分配语音识别中的时间段。
规则：
1. 每行歌词对应一段连续的时间（可能跨越多个语音片段）
2. 按歌词顺序匹配，不要打乱顺序
3. 歌词和语音文本可能有差异（同音字、口语化），按语义匹配
4. 时间不能重叠，每行歌词的起始时间 >= 上一行的结束时间
5. 最后一行的结束时间可以稍微延长

请严格按以下JSON格式输出，不要加任何其他内容：
{{"aligned": [
  {{"start": "00:00:01,000", "end": "00:00:04,500", "text": "第一行歌词"}},
  ...
]}}"""

    result = call_qwen(prompt)
    try:
        # 提取JSON
        json_match = re.search(r'\{[\s\S]*\}', result)
        if json_match:
            data = json.loads(json_match.group())
            return data['aligned']
    except (json.JSONDecodeError, KeyError):
        pass

    # AI失败，用简单均匀分配兜底
    print("  ⚠️ AI对齐失败，使用均匀时间分配")
    duration = sum(get_srt_seconds(s['end']) - get_srt_seconds(s['start']) for s in whisper_subs)
    if duration <= 0:
        duration = get_audio_duration(whisper_subs[0]['start']) if whisper_subs else 180

    interval = duration / len(lyrics_lines)
    aligned = []
    current_time = 0
    for line in lyrics_lines:
        aligned.append({
            'start': seconds_to_srt(current_time),
            'end': seconds_to_srt(current_time + interval),
            'text': line
        })
        current_time += interval
    return aligned


def call_qwen(prompt):
    """调用通义千问"""
    body = json.dumps({
        "model": "qwen-plus",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 4000
    }).encode()

    req = urllib.request.Request(
        "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DASHSCOPE_API_KEY}"
        }
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())["choices"][0]["message"]["content"]


def get_srt_seconds(time_str):
    """SRT时间转秒数"""
    m = re.match(r'(\d{2}):(\d{2}):(\d{2})[,\.](\d{3})', time_str)
    if not m:
        return 0
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) + int(m.group(4)) / 1000


def seconds_to_srt(seconds):
    """秒数转SRT时间格式"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def step2_generate_bg(bg_prompt, work_dir):
    """步骤2：生成背景图"""
    bg_path = os.path.join(work_dir, "background.png")

    if bg_prompt and bg_prompt in BG_PROMPTS:
        bg_prompt = BG_PROMPTS[bg_prompt]

    if not bg_prompt:
        bg_prompt = "Dark cinematic background with soft bokeh lights, moody atmosphere, dark blue and purple tones, minimal, 4k"

    print(f"  生成背景图...")
    print(f"  提示词: {bg_prompt}")

    # 提交异步任务
    body = json.dumps({
        "model": "wanx-v1",
        "input": {"prompt": bg_prompt},
        "parameters": {
            "size": f"{OUTPUT_WIDTH}*{OUTPUT_HEIGHT}",
            "n": 1
        }
    }).encode()

    req = urllib.request.Request(
        "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
            "X-DashScope-Async": "enable"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            task_id = result.get("output", {}).get("task_id")
            if not task_id:
                print(f"  ⚠️ 背景生成失败: {result}")
                return create_fallback_bg(bg_path)

        # 轮询等待
        import time
        for i in range(30):
            time.sleep(3)
            check_req = urllib.request.Request(
                f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}",
                headers={"Authorization": f"Bearer {DASHSCOPE_API_KEY}"}
            )
            with urllib.request.urlopen(check_req, timeout=10) as resp:
                status = json.loads(resp.read())
                task_status = status.get("output", {}).get("task_status", "")
                if task_status == "SUCCEEDED":
                    results = status["output"].get("results", [])
                    if results:
                        url = results[0].get("url")
                        urllib.request.urlretrieve(url, bg_path)
                        print(f"  ✅ 背景图已生成")
                        return bg_path
                elif task_status == "FAILED":
                    print(f"  ⚠️ 背景生成失败")
                    break
                else:
                    print(f"  等待生成... ({task_status})", end="\r")
        print()
    except Exception as e:
        print(f"  ⚠️ 背景生成异常: {e}")

    # 兜底：用FFmpeg生成纯色背景
    return create_fallback_bg(bg_path)


def create_fallback_bg(bg_path):
    """生成兜底纯色背景"""
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"color=c=0x0a0a1a:s={OUTPUT_WIDTH}x{OUTPUT_HEIGHT}:d=1",
        "-frames:v", "1", bg_path
    ], capture_output=True)
    print(f"  ✅ 使用纯色背景")
    return bg_path


def step3_srt_to_ass(srt_path, ass_path, style_name="居中大字", font_size=None):
    """步骤3：将SRT转为ASS字幕（带样式和动画）"""
    style = STYLES.get(style_name, STYLES["居中大字"]).copy()
    if font_size:
        style["fontsize"] = font_size

    with open(srt_path, 'r', encoding='utf-8') as f:
        subs = parse_srt(f.read())

    ass_lines = [
        "[Script Info]",
        "Title: Lyric Video",
        "ScriptType: v4.00+",
        "PlayResX: 1280",
        "PlayResY: 720",
        "WrapStyle: 0",
        "",
        "[V4+ Styles]",
        f"Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{style['fontname']},{style['fontsize']},{style['primary_color']},{style['secondary_color']},{style['outline_color']},{style['back_color']},{-1 if style['bold'] else 0},{-1 if style['italic'] else 0},0,0,100,100,0,0,{style['border_style']},{style['outline']},{style['shadow']},{style['alignment']},{style['margin_l']},{style['margin_r']},{style['margin_v']},{style['encoding']}",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    for sub in subs:
        # SRT时间转ASS时间 (00:00:00,000 -> 0:00:00.00)
        start = srt_to_ass_time(sub['start'])
        end = srt_to_ass_time(sub['end'])
        # ASS特殊字符转义
        text = sub['text'].replace('\\', '\\\\').replace('{', '\\{').replace('}', '\\}')
        ass_lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

    with open(ass_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(ass_lines))

    return ass_path


def srt_to_ass_time(srt_time):
    """SRT时间格式转ASS时间格式"""
    m = re.match(r'(\d{2}):(\d{2}):(\d{2})[,\.](\d{3})', srt_time)
    if not m:
        return "0:00:00.00"
    return f"{int(m.group(1))}:{m.group(2)}:{m.group(3)}.{m.group(4)}"


def step4_compose_video(audio_path, bg_path, ass_path, output_path):
    """步骤4：合成最终视频"""
    print(f"  合成视频: {OUTPUT_WIDTH}x{OUTPUT_HEIGHT} {FPS}fps")

    # 背景图循环 + 音频 + ASS字幕
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", bg_path,                    # 背景图循环
        "-i", audio_path,                                 # 音频
        "-vf", f"ass={ass_path},scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        "-r", str(FPS),
        output_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        print(f"  ❌ 合成失败: {result.stderr[-300:]}")
        sys.exit(1)

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"  ✅ 视频已生成: {output_path} ({size_mb:.1f}MB)")


def main():
    parser = argparse.ArgumentParser(
        description="歌词视频生成流水线",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基础用法
  python3 lyric_video.py song.mp3 lyrics.txt

  # 指定输出和背景
  python3 lyric_video.py song.mp3 lyrics.txt -o video.mp4 --bg 暗色星空

  # 自定义字幕样式
  python3 lyric_video.py song.mp3 lyrics.txt --style 底部小字 --font-size 42

  # 使用SRT歌词（已有时轴）
  python3 lyric_video.py song.mp3 subtitle.srt
""")
    parser.add_argument("audio", help="音频文件 (MP3/WAV)")
    parser.add_argument("lyrics", help="歌词文件 (TXT纯文本或SRT)")
    parser.add_argument("-o", "--output", help="输出视频路径 (默认: audio_lyric.mp4)")
    parser.add_argument("--bg", default="暗色星空", choices=list(BG_PROMPTS.keys()),
                        help=f"背景风格 (默认: 暗色星空)")
    parser.add_argument("--bg-custom", default="", help="自定义背景图路径 (优先于--bg)")
    parser.add_argument("--style", default="居中大字",
                        choices=list(STYLES.keys()), help="字幕样式")
    parser.add_argument("--font-size", type=int, default=None, help="自定义字号")
    parser.add_argument("--whisper-model", default=WHISPER_MODEL,
                        choices=["tiny","base","small","medium","large"],
                        help=f"Whisper模型 (默认: {WHISPER_MODEL})")
    parser.add_argument("--srt-only", action="store_true",
                        help="只生成SRT字幕，不合成视频")
    parser.add_argument("--keep-workdir", action="store_true",
                        help="保留工作目录（不自动清理）")

    args = parser.parse_args()

    set_whisper_model(args.whisper_model)

    if not os.path.exists(args.audio):
        print(f"❌ 音频文件不存在: {args.audio}")
        sys.exit(1)
    if not os.path.exists(args.lyrics):
        print(f"❌ 歌词文件不存在: {args.lyrics}")
        sys.exit(1)

    # 默认输出路径
    output_path = args.output or os.path.splitext(args.audio)[0] + "_lyric.mp4"

    print("=" * 50)
    print("🎬 歌词视频生成流水线")
    print("=" * 50)

    # 创建工作目录
    work_dir = tempfile.mkdtemp(prefix="lyric_video_")
    print(f"📁 工作目录: {work_dir}")

    try:
        # === 步骤1：生成SRT字幕 ===
        print("\n[1/3] 生成字幕时间轴...")
        srt_path = step1_generate_srt(args.audio, args.lyrics, work_dir)

        if args.srt_only:
            import shutil
            final_srt = os.path.splitext(output_path)[0] + ".srt"
            shutil.copy2(srt_path, final_srt)
            print(f"\n✅ SRT已保存: {final_srt}")
            return

        # === 步骤2：生成背景图 ===
        print("\n[2/3] 生成背景图...")
        if args.bg_custom and os.path.exists(args.bg_custom):
            bg_path = args.bg_custom
            print(f"  使用自定义背景: {bg_path}")
        else:
            bg_path = step2_generate_bg(args.bg, work_dir)

        # === 步骤3：SRT → ASS字幕 ===
        print("\n[3/3] 合成视频...")
        ass_path = os.path.join(work_dir, "subtitle.ass")
        step3_srt_to_ass(srt_path, ass_path, args.style, args.font_size)

        # === 步骤4：合成视频 ===
        step4_compose_video(args.audio, bg_path, ass_path, output_path)

        print(f"\n{'=' * 50}")
        print(f"✅ 完成！视频已保存: {output_path}")

    finally:
        # 清理工作目录
        if not args.keep_workdir:
            import shutil
            shutil.rmtree(work_dir, ignore_errors=True)
            print(f"🗑️  已清理工作目录")


if __name__ == "__main__":
    main()
