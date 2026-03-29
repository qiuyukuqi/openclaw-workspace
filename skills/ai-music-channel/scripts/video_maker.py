#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
秋晴FM — 译制片风格歌词视频制作器
- 歌名：PIL渲染艺术字，顶部显示后淡出
- 歌词：底部双语字幕，ASS卡拉OK高亮
- Whisper精准时间对齐
"""

import os, sys, json, subprocess, re, time, random, tempfile
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

WORKSPACE = os.path.expanduser("~/.openclaw/workspace")

# 字体
FONT_TITLE = "/usr/share/fonts/chinese/LXGWWenKai-Regular.ttf"
FONT_LYRICS_CN = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FONT_EN = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
DEEPSEEK_KEY = "sk-162c19004d444d73a49c735c4de9d82f"


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def get_audio_duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", path], capture_output=True, text=True, timeout=10)
    return float(r.stdout.strip())


# ===== 1. Whisper时间对齐 =====
def align_lyrics_with_whisper(audio_path):
    """用Whisper识别音频，返回每行的时间轴"""
    log("  🔊 Whisper识别中...")
    out_dir = tempfile.mkdtemp(prefix="whisper_")
    subprocess.run(
        ["whisper", audio_path, "--model", "tiny", "--language", "zh",
         "--output_format", "json", "--output_dir", out_dir],
        capture_output=True, timeout=600
    )
    # 读取结果
    json_file = os.path.join(out_dir, os.path.splitext(os.path.basename(audio_path))[0] + ".json")
    if not os.path.exists(json_file):
        # 查找任何json
        jsons = [f for f in os.listdir(out_dir) if f.endswith(".json")]
        if jsons:
            json_file = os.path.join(out_dir, jsons[0])
        else:
            raise RuntimeError("Whisper未生成结果")
    
    with open(json_file) as f:
        data = json.load(f)
    
    segments = []
    for seg in data.get("segments", []):
        segments.append({
            "start": seg["start"],
            "end": seg["end"],
            "text": seg["text"].strip()
        })
    
    log(f"  ✅ 识别完成: {len(segments)}段")
    return segments


# ===== 2. AI翻译歌词 =====
def translate_lyrics(lines):
    """用DeepSeek翻译歌词为英文"""
    log("  🌐 翻译歌词中...")
    text = "\n".join(f"{i+1}. {line}" for i, line in enumerate(lines))
    
    resp = subprocess.run(
        ["curl", "-s", "-X", "POST", "https://api.deepseek.com/v1/chat/completions",
         "-H", f"Authorization: Bearer {DEEPSEEK_KEY}",
         "-H", "Content-Type: application/json",
         "-d", json.dumps({
             "model": "deepseek-chat",
             "messages": [{
                 "role": "system",
                 "content": "你是歌词翻译专家。将中文歌词翻译为英文，保持诗意和意境。每行翻译一行，保持编号格式。只输出翻译结果，不要解释。"
             }, {
                 "role": "user",
                 "content": text
             }],
             "temperature": 0.7,
             "max_tokens": 2000
         })],
        capture_output=True, text=True, timeout=60
    )
    
    try:
        result = json.loads(resp.stdout)
        translated = result["choices"][0]["message"]["content"].strip()
        en_lines = []
        for line in translated.split("\n"):
            line = re.sub(r'^\d+[\.\)]\s*', '', line).strip()
            if line:
                en_lines.append(line)
        log(f"  ✅ 翻译完成: {len(en_lines)}行")
        return en_lines
    except Exception as e:
        log(f"  ⚠️ 翻译失败: {e}")
        return [""] * len(lines)


# ===== 3. 歌名与Whisper文本对齐 =====
def match_lyrics(lyrics_text, whisper_segments):
    """将Suno原始歌词与Whisper识别结果对齐，返回带时间轴的歌词"""
    # 提取Suno歌词纯文本行（去掉标签行如[Verse]、[Chorus]等）
    cn_lines = []
    for line in lyrics_text.replace('\r\n', '\n').split('\n'):
        line = line.strip()
        if line and not re.match(r'^\[[\w\s]+\]$', line):
            cn_lines.append(line)
    
    if not cn_lines:
        return []
    
    if len(whisper_segments) == len(cn_lines):
        # 行数相同，直接一一对应
        return [{
            "start": seg["start"],
            "end": seg["end"],
            "cn": cn_lines[i],
            "en": ""
        } for i, seg in enumerate(whisper_segments)]
    
    # 行数不同，用DTW或简单对齐：按时间均匀分配
    total_dur = whisper_segments[-1]["end"] - whisper_segments[0]["start"] if whisper_segments else 0
    start_time = whisper_segments[0]["start"] if whisper_segments else 0
    per_line = total_dur / len(cn_lines) if cn_lines else 0
    
    return [{
        "start": start_time + i * per_line,
        "end": start_time + (i + 1) * per_line,
        "cn": line,
        "en": ""
    } for i, line in enumerate(cn_lines)]


# ===== 4. PIL渲染艺术字歌名 =====
def render_title_image(song_name, width=1280, height=150):
    """生成带阴影效果的艺术字标题图片"""
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 尝试多个字号，选最合适的
    font_size = 72
    try:
        font = ImageFont.truetype(FONT_TITLE, font_size)
    except:
        font = ImageFont.truetype(FONT_LYRICS_CN, font_size)
    
    # 自动缩小到适合宽度
    bbox = draw.textbbox((0, 0), song_name, font=font)
    text_w = bbox[2] - bbox[0]
    max_w = width - 100
    if text_w > max_w:
        scale = max_w / text_w
        font_size = int(font_size * scale)
        font = ImageFont.truetype(FONT_TITLE, font_size)
    
    # 渲染文字 - 白色
    bbox = draw.textbbox((0, 0), song_name, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (width - text_w) // 2
    y = (height - text_h) // 2 - 10
    
    # 多层阴影效果
    for offset, alpha in [(4, 40), (3, 60), (2, 100), (1, 150)]:
        shadow = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        s_draw = ImageDraw.Draw(shadow)
        s_draw.text((x + offset, y + offset), song_name, font=font, fill=(0, 0, 0, alpha))
        img = Image.alpha_composite(img, shadow)
    
    # 主文字
    draw = ImageDraw.Draw(img)
    draw.text((x, y), song_name, font=font, fill=(255, 255, 255, 240))
    
    # 描边
    outline = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    o_draw = ImageDraw.Draw(outline)
    for dx in [-2, -1, 0, 1, 2]:
        for dy in [-2, -1, 0, 1, 2]:
            if dx or dy:
                o_draw.text((x + dx, y + dy), song_name, font=font, fill=(0, 0, 0, 180))
    img = Image.alpha_composite(img, outline)
    
    # 再画一遍主文字（在描边之上）
    draw = ImageDraw.Draw(img)
    draw.text((x, y), song_name, font=font, fill=(255, 255, 255, 245))
    
    return img


# ===== 5. ASS字幕生成 =====
def generate_ass_subtitles(timed_lyrics, duration):
    """生成ASS卡拉OK字幕 - 译制片风格"""
    lines = []
    
    # 样式定义
    # 中文字幕：底部居中，大号
    # 英文字幕：中文下方，较小
    # 当前行：白色高亮
    # 前后行：灰色半透明
    
    lines.append("[Script Info]")
    lines.append("Title: Lyrics")
    lines.append("WrapStyle: 0")
    lines.append("")
    lines.append("[V4+ Styles]")
    lines.append("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding")
    # 中文-当前行（白色高亮）
    lines.append(f"Style: CN_Active,Noto Sans CJK SC,40,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,0,2,20,20,60,1")
    # 中文-其他行（灰色半透明）
    lines.append(f"Style: CN_Dim,Noto Sans CJK SC,36,&H80909090,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,0,0,2,20,20,60,1")
    # 英文-当前行
    lines.append(f"Style: EN_Active,DejaVu Sans,28,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,1,0,100,100,0,0,1,2,0,0,2,20,20,25,1")
    # 英文-其他行
    lines.append(f"Style: EN_Dim,DejaVu Sans,24,&H60909090,&H000000FF,&H00000000,&H80000000,0,0,1,0,100,100,0,0,1,1,0,0,2,20,20,25,1")
    lines.append("")
    lines.append("[Events]")
    lines.append("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text")
    
    for i, lyric in enumerate(timed_lyrics):
        s = lyric["start"]
        e = lyric["end"]
        cn = lyric["cn"].replace("{", "\\{").replace("}", "\\}")
        en = lyric.get("en", "").replace("{", "\\{").replace("}", "\\}")
        
        # 确定当前行高亮窗口
        prev_end = lyric["start"] - 0.3 if i > 0 else 0
        next_start = lyric["end"] + 0.3 if i < len(timed_lyrics) - 1 else duration
        
        start_str = f"{int(s//60)}:{s%60:05.2f}"
        end_str = f"{int(e//60)}:{e%60:05.2f}"
        
        # 中文行
        lines.append(f"Dialogue: 0,{start_str},{end_str},CN_Active,,0,0,0,,{cn}")
        
        # 英文行（如果有）
        if en:
            lines.append(f"Dialogue: 0,{start_str},{end_str},EN_Active,,0,0,0,,{en}")
    
    return "\n".join(lines)


# ===== 6. 合成视频 =====
def create_video(bg_image, audio_path, timed_lyrics, song_name, output_path):
    """合成译制片风格歌词视频"""
    log(f"🎬 制作视频: {song_name}")
    
    duration = get_audio_duration(audio_path)
    log(f"  时长: {duration:.1f}秒, 歌词: {len(timed_lyrics)}行")
    
    # Step 1: 渲染艺术字歌名
    title_img = render_title_image(song_name)
    title_png = output_path + ".title.png"
    title_img.save(title_png)
    log(f"  ✅ 歌名渲染完成")
    
    # Step 2: 生成ASS字幕
    ass_content = generate_ass_subtitles(timed_lyrics, duration)
    ass_path = output_path + ".ass"
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass_content)
    log(f"  ✅ ASS字幕生成完成")
    
    # Step 3: ffmpeg合成
    # 歌名显示8秒后淡出（alpha通道渐变用enable+fade）
    # 用overlay把歌名图片叠在顶部
    fade_start = 6.0   # 6秒开始淡出
    fade_dur = 2.0     # 2秒淡完
    
    # 构建filter
    # 视频流：背景图 → scale/pad → 叠加歌名（带淡出） → ASS字幕
    vf = (
        f"scale=1280:720:force_original_aspect_ratio=decrease,"
        f"pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"movie='{title_png}'[title];"
        f"[in][title]overlay=(main_w-overlay_w)/2:30:format=auto,"
        f"enable='lte(t\\,{fade_start+fade_dur})',"
        # 歌名淡出不好在overlay里做，用drawtext代替更可靠
    )
    
    # 简化方案：用drawtext显示歌名（支持alpha淡出），ASS显示歌词
    safe_song = song_name.replace("'", "'").replace(":", "\\:").replace("%", "\\%").replace("'", "\\'")
    # drawtext不支持真正的alpha渐变，但支持enable
    # 更好的方案：分两段，第一段(0-8s)有歌名，第二段(8s-)无歌名，用两次drawtext+enable
    # 最简方案：用两步ffmpeg
    
    # 方案A：先做带字幕的视频，再叠加歌名（更可靠）
    
    # 第一步：背景图+ASS字幕 → 临时视频
    temp_video = output_path + ".temp.mp4"
    
    cmd1 = [
        "ffmpeg", "-y",
        "-framerate", "1", "-loop", "1", "-i", bg_image,
        "-i", audio_path,
        "-vf", (
            f"scale=1280:720:force_original_aspect_ratio=decrease,"
            f"pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"ass='{ass_path}'"
        ),
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-movflags", "+faststart",
        temp_video
    ]
    
    log(f"  🎞️ 合成字幕视频...")
    r = subprocess.run(cmd1, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        # 降级：无字幕
        log(f"  ⚠️ ASS字幕失败，使用纯视频...")
        r2 = subprocess.run([
            "ffmpeg", "-y", "-framerate", "1", "-loop", "1", "-i", bg_image,
            "-i", audio_path,
            "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
            temp_video
        ], capture_output=True, text=True, timeout=300)
        if r2.returncode != 0:
            raise RuntimeError(f"视频合成失败: {r2.stderr[-300:]}")
    
    # 第二步：叠加歌名图片（带淡出）
    # 使用overlay + fade滤镜
    title_fade_out = f"{fade_start+fade_dur}"
    cmd2 = [
        "ffmpeg", "-y",
        "-i", temp_video,
        "-i", title_png,
        "-filter_complex",
        (
            f"[1:v]format=rgba,colorchannelmixer=aa=1[title];"
            f"[0:v][title]overlay=(main_w-overlay_w)/2:20:format=auto:"
            f"enable='between(t,0,{title_fade_out})',"
            f"[1:v]format=rgba,fade=t=out:st={fade_start}:d={fade_dur}[t2];"
            f"[0:v][t2]overlay=(main_w-overlay_w)/2:20:format=auto"
        ),
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        "-movflags", "+faststart",
        output_path
    ]
    
    log(f"  🎨 叠加歌名...")
    r = subprocess.run(cmd2, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        # 简化：直接用drawtext叠歌名
        log(f"  ⚠️ overlay失败，用drawtext...")
        cmd3 = [
            "ffmpeg", "-y", "-i", temp_video,
            "-vf", f"drawtext=fontfile={FONT_TITLE}:text='{safe_song}':fontsize=60:fontcolor=white:borderw=3:bordercolor=black:x=(w-text_w)/2:y=30:enable='between(t,0,8)'",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "copy", "-movflags", "+faststart", output_path
        ]
        r = subprocess.run(cmd3, capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            # 最终降级：直接复制
            import shutil
            shutil.copy2(temp_video, output_path)
    
    # 清理临时文件
    for f in [temp_video, title_png, ass_path]:
        if os.path.exists(f):
            os.remove(f)
    
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    log(f"  ✅ 视频: {size_mb:.1f}MB")
    return output_path


# ===== 主入口 =====
def make_lyric_video(bg_image, audio_path, lyrics_text, song_name, output_path):
    """
    完整歌词视频制作流程：
    1. Whisper时间对齐
    2. AI翻译歌词
    3. 匹配歌词+时间
    4. 生成ASS字幕
    5. 渲染艺术字歌名
    6. 合成视频
    """
    duration = get_audio_duration(audio_path)
    
    # 1. Whisper对齐
    whisper_segs = align_lyrics_with_whisper(audio_path)
    
    # 2. 匹配歌词
    timed_lyrics = match_lyrics(lyrics_text, whisper_segs)
    if not timed_lyrics:
        raise RuntimeError("歌词匹配失败")
    
    # 3. 翻译
    cn_only = [l["cn"] for l in timed_lyrics]
    en_lines = translate_lyrics(cn_only)
    for i, en in enumerate(en_lines):
        if i < len(timed_lyrics):
            timed_lyrics[i]["en"] = en
    
    # 4. 合成视频
    return create_video(bg_image, audio_path, timed_lyrics, song_name, output_path)


if __name__ == "__main__":
    # 测试
    print("=== 译制片风格歌词视频测试 ===")
    bg = sys.argv[1] if len(sys.argv) > 1 else "/root/.openclaw/workspace/skills/ai-music-channel/covers/6fd3c23b-4833-4772-af25-36d0a8304525.png"
    audio = sys.argv[2] if len(sys.argv) > 2 else "/tmp/openclaw/music/同桌以后的你_v1.mp3"
    lyrics_file = sys.argv[3] if len(sys.argv) > 3 else "/tmp/openclaw/music/同桌以后的你_lyrics.txt"
    
    with open(lyrics_file, encoding="utf-8") as f:
        lyrics_text = f.read()
    
    out = "/tmp/openclaw/test_dubbed.mp4"
    make_lyric_video(bg, audio, lyrics_text, "同桌以后的你", out)
