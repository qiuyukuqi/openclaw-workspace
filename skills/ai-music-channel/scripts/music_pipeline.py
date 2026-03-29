#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
秋晴FM — AI翻唱经典歌曲自动化流水线
流程：选歌 → Suno翻唱 → 封面图 → 歌词视频 → 上传YouTube
"""

import os, sys, json, subprocess, re, time, requests, random, uuid, tempfile
from datetime import datetime
WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
SCRIPT_DIR = os.path.join(WORKSPACE, "skills/ai-music-channel/scripts")
DATA_DIR = os.path.join(WORKSPACE, "skills/ai-music-channel/data")
COVER_DIR = os.path.join(WORKSPACE, "skills/ai-music-channel/covers")
COVER_TRACKER = os.path.join(DATA_DIR, "used_covers.json")
os.makedirs(DATA_DIR, exist_ok=True)

SUNO_API_KEY = os.environ.get("SUNO_API_KEY", "sk-VRTrDBlfKY1TXdffDiDNJtgUajH0EY7AN15pLWN1GDVbZC6c")
SUNO_BASE = "https://api.302.ai"
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "sk-162c19004d444d73a49c735c4de9d82f")
USER_ID = "ou_c5c98e2002a34a9b10f15fd0b6463d06"

# 字体配置
FONT_TITLE = "/usr/share/fonts/chinese/LXGWWenKai-Regular.ttf"  # 霞鹜文楷（歌名艺术字）
FONT_LYRICS = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"  # Noto黑体（歌词）
FONT_EN = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"  # 英文字体

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def notify(msg):
    try:
        subprocess.run(["openclaw", "message", "send", "--channel", "feishu",
                        "-t", f"user:{USER_ID}", "-m", msg],
                       capture_output=True, timeout=30)
    except:
        pass

# ========== 封面图管理 ==========
def get_unused_cover():
    """获取一张未使用的封面图"""
    used = set()
    if os.path.exists(COVER_TRACKER):
        with open(COVER_TRACKER) as f:
            used = set(json.load(f).get("used", []))
    
    candidates = []
    for fname in os.listdir(COVER_DIR):
        fpath = os.path.join(COVER_DIR, fname)
        if not os.path.isfile(fpath):
            continue
        ext = fname.lower().split('.')[-1]
        if ext not in ('jpg', 'jpeg', 'png', 'webp'):
            continue
        if fname not in used:
            candidates.append(fpath)
    
    if not candidates:
        notify("⚠️ 封面图用完了！请发送新图片给我。")
        return None
    
    return random.choice(candidates)

def mark_cover_used(filepath):
    """标记封面图为已使用"""
    fname = os.path.basename(filepath)
    used = []
    if os.path.exists(COVER_TRACKER):
        with open(COVER_TRACKER) as f:
            used = json.load(f).get("used", [])
    if fname not in used:
        used.append(fname)
    with open(COVER_TRACKER, 'w') as f:
        json.dump({"used": used}, f, ensure_ascii=False, indent=2)

def get_remaining_covers():
    """获取剩余可用封面图数量"""
    used = set()
    if os.path.exists(COVER_TRACKER):
        with open(COVER_TRACKER) as f:
            used = set(json.load(f).get("used", []))
    count = 0
    for fname in os.listdir(COVER_DIR):
        ext = fname.lower().split('.')[-1]
        if ext in ('jpg', 'jpeg', 'png', 'webp') and fname not in used:
            count += 1
    return count

# ========== Step 1: 选歌 ==========
def select_song():
    """从经典华语歌曲库选一首"""
    song_library = [
        {"name": "月亮代表我的心", "artist": "邓丽君", "style": "温柔抒情，经典华语流行，钢琴配乐，女声"},
        {"name": "恰似你的温柔", "artist": "蔡琴", "style": "温暖民谣，原声吉他，柔和女声"},
        {"name": "海阔天空", "artist": "Beyond", "style": "摇滚励志，电吉他，粤语男声"},
        {"name": "千里之外", "artist": "周杰伦", "style": "中国风，R&B融合，古筝配乐"},
        {"name": "容易受伤的女人", "artist": "王菲", "style": "空灵女声，合成器流行，90年代港风"},
        {"name": "同桌的你", "artist": "老狼", "style": "校园民谣，木吉他，清朗男声"},
        {"name": "吻别", "artist": "张学友", "style": "经典情歌，流行抒情，深情男声"},
        {"name": "漫步人生路", "artist": "邓丽君", "style": "轻快粤语歌，欢快节奏，温暖女声"},
        {"name": "夜来香", "artist": "邓丽君", "style": "复古爵士，萨克斯，慵懒女声"},
        {"name": "光辉岁月", "artist": "Beyond", "style": "摇滚经典，电吉他solo，粤语"},
        {"name": "红豆", "artist": "王菲", "style": "抒情慢歌，钢琴弦乐，空灵女声"},
        {"name": "一路上有你", "artist": "张学友", "style": "深情情歌，流行编曲，男声"},
        {"name": "小城故事", "artist": "邓丽君", "style": "田园民谣，原声乐，温柔女声"},
        {"name": "沧海一声笑", "artist": "许冠杰", "style": "武侠古风，笛子古筝，豪迈男声"},
        {"name": "我只在乎你", "artist": "邓丽君", "style": "经典情歌，弦乐配乐，深情女声"},
        {"name": "大约在冬季", "artist": "齐秦", "style": "冬日情歌，吉他配乐，忧郁男声"},
        {"name": "朋友的酒", "artist": "姜育恒", "style": "友情歌曲，摇滚编曲，沧桑男声"},
        {"name": "梦醒时分", "artist": "陈淑桦", "style": "都市情歌，合成器流行，90年代风格"},
        {"name": "忘情水", "artist": "刘德华", "style": "流行情歌，抒情编曲，深情男声"},
        {"name": "甜蜜蜜", "artist": "邓丽君", "style": "甜蜜情歌，轻快编曲，温暖女声"},
    ]
    
    song = random.choice(song_library)
    log(f"🎵 选歌: {song['name']} - {song['artist']}")
    return song

# ========== Step 2: Suno生成 ==========
def generate_music(song):
    """用Suno AI翻唱经典歌曲（通过bash脚本调用）"""
    log(f"🎸 Suno生成: {song['name']} ({song['artist']})...")
    
    prompt = f"AI翻唱经典歌曲《{song['name']}，原唱{song['artist']}，{song['style']}，保留原曲旋律和歌词，用现代编曲重新演绎"
    
    result = subprocess.run(
        ["bash", os.path.join(WORKSPACE, "scripts/suno_music.sh"), prompt],
        capture_output=True, text=True, timeout=300, cwd=WORKSPACE
    )
    
    if result.returncode != 0:
        raise RuntimeError(f"Suno生成失败: {result.stderr[-300:]}")
    
    # 解析输出，找到音频文件
    audio_files = []
    lyrics_file = None
    for line in result.stdout.split("\n"):
        line = line.strip()
        if "文件保存在" in line or "歌词" in line:
            continue
        if ".mp3" in line:
            # 提取路径: 可能是 "v1: title - /path/file.mp3" 格式
            parts = line.split("/tmp/openclaw/music/")
            if len(parts) >= 2:
                fpath = "/tmp/openclaw/music/" + parts[-1].strip()
                if os.path.exists(fpath):
                    audio_files.append(fpath)
        if "_lyrics.txt" in line:
            parts = line.split("/tmp/openclaw/music/")
            if len(parts) >= 2:
                fpath = "/tmp/openclaw/music/" + parts[-1].strip()
                if os.path.exists(fpath):
                    lyrics_file = fpath
    
    # 备选：直接扫描输出目录
    if not audio_files:
        music_dir = "/tmp/openclaw/music/"
        for f in sorted(os.listdir(music_dir), reverse=True):
            if f.endswith(".mp3") and os.path.exists(os.path.join(music_dir, f)):
                audio_files.append(os.path.join(music_dir, f))
        if not audio_files:
            raise RuntimeError(f"Suno生成成功但未找到音频文件")
    
    # 读取歌词
    lyrics = ""
    if lyrics_file:
        with open(lyrics_file, encoding="utf-8") as f:
            lyrics = f.read()
    
    log(f"  ✅ 生成完成: {len(audio_files)}个版本")
    return {
        "audio_path": audio_files[0],
        "lyrics": lyrics,
        "title": f"AI翻唱-{song['name']}",
    }

# ========== Step 3: 下载音频 ==========
def download_audio(url, output_path):
    r = requests.get(url, timeout=120, stream=True)
    with open(output_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    size = os.path.getsize(output_path) / (1024*1024)
    log(f"  音频: {size:.1f}MB")
    return output_path

# ========== Step 4: 制作歌词视频 ==========
def translate_lyrics(lyrics_lines):
    """用DeepSeek翻译歌词为英文"""
    text = "\n".join(lyrics_lines)
    try:
        r = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "Translate Chinese song lyrics to English. Return ONLY the translated lines, one per line, same number of lines. Keep poetic and emotional. Do not add any explanation."},
                    {"role": "user", "content": text}
                ],
                "temperature": 0.7,
                "max_tokens": 2000,
            },
            timeout=30,
        )
        if r.status_code == 200:
            en_text = r.json()["choices"][0]["message"]["content"]
            en_lines = [l.strip() for l in en_text.split("\n") if l.strip()]
            # 对齐行数
            while len(en_lines) < len(lyrics_lines):
                en_lines.append("")
            return en_lines[:len(lyrics_lines)]
    except Exception as e:
        log(f"  翻译失败: {e}")
    return [""] * len(lyrics_lines)

def whisper_align(audio_file):
    """用Whisper获取歌词时间轴"""
    tmp_dir = tempfile.mkdtemp()
    result = subprocess.run(
        ["whisper", audio_file, "--model", "small", "--language", "zh",
         "--output_format", "srt", "--output_dir", tmp_dir,
         "--word_timestamps", "False"],
        capture_output=False, text=True, timeout=900
    )
    # 找到SRT文件
    srt_file = None
    for f in os.listdir(tmp_dir):
        if f.endswith(".srt"):
            srt_file = os.path.join(tmp_dir, f)
            break
    
    if not srt_file:
        raise RuntimeError("Whisper未生成SRT文件")
    
    # 解析SRT
    timestamps = []
    with open(srt_file, encoding="utf-8") as f:
        content = f.read()
    
    for block in re.split(r'\n\s*\n', content.strip()):
        lines = block.strip().split('\n')
        if len(lines) >= 3:
            time_line = lines[1]
            text = ' '.join(lines[2:])
            m = re.match(r'(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})', time_line)
            if m:
                start = int(m[1])*3600 + int(m[2])*60 + int(m[3]) + int(m[4])/1000
                end = int(m[5])*3600 + int(m[6])*60 + int(m[7]) + int(m[8])/1000
                timestamps.append({"start": start, "end": end, "text": text})
    
    # 清理
    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)
    
    log(f"  Whisper识别: {len(timestamps)}行")
    return timestamps

def create_lyrics_video(bg_image, audio_file, lyrics, title, output_path):
    """
    制作译制片风格歌词视频：
    - 歌名：霞鹜文楷大号，居中，显示10秒后淡出
    - 歌词：底部，当前行高亮（白色大号），前后行半透明
    - 中英双语字幕同时显示
    """
    log(f"🎬 制作歌词视频...")
    
    # 清理歌词（去掉[Verse]等标签）
    raw_lines = [l.strip() for l in lyrics.replace('\r\n', '\n').split('\n') 
                 if l.strip() and not l.strip().startswith('[')]
    if not raw_lines:
        raw_lines = [title]
    
    # 获取音频时长
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", audio_file],
        capture_output=True, text=True, timeout=10
    )
    duration = float(probe.stdout.strip())
    
    # Whisper时间轴对齐
    log(f"  Whisper对齐中...")
    timestamps = whisper_align(audio_file)
    
    # 把原始歌词和Whisper时间轴对齐（用编辑距离匹配）
    aligned = []
    ts_idx = 0
    for cn_line in raw_lines:
        if ts_idx < len(timestamps):
            # 找最匹配的时间戳
            best_idx = ts_idx
            best_score = float('inf')
            search_range = min(5, len(timestamps) - ts_idx)
            for j in range(search_range):
                idx = ts_idx + j
                dist = abs(len(timestamps[idx]["text"]) - len(cn_line))
                if dist < best_score:
                    best_score = dist
                    best_idx = idx
            aligned.append({
                "start": timestamps[best_idx]["start"],
                "end": timestamps[best_idx]["end"],
                "cn": cn_line,
            })
            ts_idx = best_idx + 1
        else:
            # 用上一次的时间递推
            last = aligned[-1] if aligned else {"start": 0, "end": 5}
            aligned.append({
                "start": last["end"],
                "end": min(last["end"] + 6, duration),
                "cn": cn_line,
            })
    
    log(f"  翻译歌词...")
    cn_only = [a["cn"] for a in aligned]
    en_lines = translate_lyrics(cn_only)
    for i, en in enumerate(en_lines):
        aligned[i]["en"] = en
    
    log(f"  生成ASS字幕（{len(aligned)}行）...")
    
    # 只显示歌名，去掉AI翻唱前缀
    song_name = re.sub(r'^AI翻唱[-—]?\s*', '', title).strip()
    
    # 生成ASS字幕
    ass_path = output_path + ".ass"
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write("[Script Info]\nTitle: Lyrics\nWrapStyle: 0\nPlayResX: 1280\nPlayResY: 720\n\n")
        
        # 样式定义
        f.write("[V4+ Styles]\n")
        f.write("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
        
        # 歌名样式：大号文楷，居中
        f.write(f"Style: Title,{os.path.basename(FONT_TITLE)},52,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,0,8,10,10,0,1\n")
        # 当前行中文：大号，白色，底部居中
        f.write(f"Style: CurrentCN,{os.path.basename(FONT_LYRICS)},36,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,0,2,10,10,50,1\n")
        # 前后行中文：半透明灰色
        f.write(f"Style: DimCN,{os.path.basename(FONT_LYRICS)},30,&H80999999,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,1,0,2,10,10,50,1\n")
        # 英文翻译：较小
        f.write(f"Style: CurrentEN,{os.path.basename(FONT_EN)},24,&H00CCCCCC,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,1,0,2,10,10,20,1\n")
        # 前后行英文
        f.write(f"Style: DimEN,{os.path.basename(FONT_EN)},20,&H80666666,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,1,0,2,10,10,20,1\n")
        
        f.write("\n[Events]\n")
        f.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        
        # 歌名：显示10秒后淡出（用{\fad}标签）
        f.write(f"Dialogue: 0,0:00:00.00,0:00:12.00,Title,,0,0,0,,{{\\fad(1000,2000)}}{song_name}\n")
        
        # 歌词行
        for i, item in enumerate(aligned):
            s = item["start"]
            e = item["end"]
            sh, sm, ss = int(s//3600), int((s%3600)//60), s%60
            eh, em, es = int(e//3600), int((e%3600)//60), e%60
            start_s = f"{sh}:{sm:02d}:{ss:05.2f}"
            end_s = f"{eh}:{em:02d}:{es:05.2f}"
            
            safe_cn = item["cn"].replace("{", "\\{").replace("}", "\\}")
            safe_en = item["en"].replace("{", "\\{").replace("}", "\\}")
            
            # 判断是否为当前行（简化：每行都是"当前行"，通过时序自然过渡）
            # 用淡入淡出让切换更自然
            cn_text = f"{{\\fad(200,200)}}{safe_cn}"
            en_text = f"{{\\fad(200,200)}}{safe_en}" if safe_en else ""
            
            # 主歌词行（当前行）
            f.write(f"Dialogue: 0,{start_s},{end_s},CurrentCN,,0,0,0,,{cn_text}\n")
            if en_text:
                f.write(f"Dialogue: 0,{start_s},{end_s},CurrentEN,,0,0,0,,{en_text}\n")
            
            # 显示前后各1行（上下文）
            for offset, style_cn, style_en in [(-1, "DimCN", "DimEN"), (1, "DimCN", "DimEN")]:
                adj = i + offset
                if 0 <= adj < len(aligned):
                    adj_item = aligned[adj]
                    adj_s = adj_item["start"]
                    adj_e = adj_item["end"]
                    ash, asm, ass_ = int(adj_s//3600), int((adj_s%3600)//60), adj_s%60
                    aeh, aem, aes = int(adj_e//3600), int((adj_e%3600)//60), adj_e%60
                    adj_start = f"{ash}:{asm:02d}:{ass_:05.2f}"
                    adj_end = f"{aeh}:{aem:02d}:{aes:05.2f}"
                    adj_cn = adj_item["cn"].replace("{", "\\{").replace("}", "\\}")
                    adj_en = adj_item["en"].replace("{", "\\{").replace("}", "\\}")
                    f.write(f"Dialogue: 0,{adj_start},{adj_end},{style_cn},,0,0,0,,{adj_cn}\n")
                    if adj_en:
                        f.write(f"Dialogue: 0,{adj_start},{adj_end},{style_en},,0,0,0,,{adj_en}\n")
    
    # ffmpeg合成（用ass滤镜需要fonts被系统识别）
    # 先确保字体名正确（ass里用的是字体文件名的basename）
    # 更安全的方式：用fontsdir参数
    font_dir = os.path.dirname(FONT_TITLE)
    
    cmd = [
        "ffmpeg", "-y",
        "-framerate", "1", "-loop", "1", "-i", bg_image,
        "-i", audio_file,
        "-vf", f"scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black,ass='{ass_path}'",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest", "-movflags", "+faststart",
        output_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        # 降级：纯drawtext
        log(f"  ASS渲染失败，降级为drawtext...")
        log(f"  错误: {result.stderr[-200:]}")
        
        safe_song = song_name.replace("'", "'").replace(":", "\\:").replace("%", "\\%")
        vf = (
            f"scale=1280:720:force_original_aspect_ratio=decrease,"
            f"pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"drawtext=fontfile={FONT_TITLE}:text='{safe_song}':"
            f"fontsize=48:fontcolor=white:borderw=2:bordercolor=black@0.5:"
            f"x=(w-text_w)/2:y=(h-text_h)/2-40"
            f":enable='between(t,0,10)'"
        )
        
        cmd2 = [
            "ffmpeg", "-y", "-framerate", "1", "-loop", "1", "-i", bg_image,
            "-i", audio_file,
            "-vf", vf,
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest", "-movflags", "+faststart", output_path
        ]
        result = subprocess.run(cmd2, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"视频制作失败: {result.stderr[-300:]}")
    else:
        # 清理ASS
        if os.path.exists(ass_path):
            os.remove(ass_path)
    
    size_mb = os.path.getsize(output_path) / (1024*1024)
    log(f"  ✅ 视频: {size_mb:.1f}MB")

# ========== Step 5: 上传YouTube ==========
def upload_youtube(video_path, title, song_name):
    log(f"📤 上传YouTube: {title}")
    sys.path.insert(0, SCRIPT_DIR)
    from youtube_upload import upload_video
    
    desc = f"AI翻唱经典歌曲《{song_name}》\n\n🎤 原唱翻唱 | AI编曲演绎\n🎵 秋晴FM — 用AI重新诠释经典\n\n#acover #AI翻唱 #经典歌曲 #秋晴FM"
    
    vid, url = upload_video(
        file_path=video_path,
        title=title,
        description=desc,
        tags=["AI翻唱", "经典歌曲", "华语音乐", "Suno", "秋晴FM", song_name],
    )
    log(f"  ✅ {url}")
    return vid, url

# ========== 完整流水线 ==========
def run():
    log("=" * 50)
    log("🎵 秋晴FM — AI翻唱经典歌曲流水线")
    log("=" * 50)
    
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    work_dir = os.path.join(DATA_DIR, f"run_{ts}")
    os.makedirs(work_dir, exist_ok=True)
    
    # 检查封面图库存
    remaining = get_remaining_covers()
    log(f"📸 剩余封面图: {remaining}张")
    if remaining < 3:
        notify(f"⚠️ 封面图库存不足（仅剩{remaining}张），请尽快补充新图！")
    
    # Step 1: 选歌
    song = select_song()
    
    # Step 2: 获取封面图
    cover = get_unused_cover()
    if not cover:
        notify("❌ 没有可用封面图，请发送新图片")
        return
    
    # Step 3: Suno生成
    music = generate_music(song)
    
    # Step 4: 制作视频
    video_path = os.path.join(work_dir, "output.mp4")
    create_lyrics_video(cover, music["audio_path"], music["lyrics"], music["title"], video_path)
    
    # Step 6: 上传
    vid, url = upload_youtube(video_path, music["title"], song["name"])
    
    # 标记封面已使用
    mark_cover_used(cover)
    new_remaining = get_remaining_covers()
    
    notify(
        f"🎵 秋晴FM 发布成功！\n"
        f"📝 {music['title']}\n"
        f"🎵 原唱: {song['artist']}\n"
        f"🔗 {url}\n"
        f"📸 剩余封面图: {new_remaining}张"
        + (f"\n\n⚠️ 封面图库存不足（{new_remaining}张），请补充！" if new_remaining < 3 else "")
    )
    
    log("=" * 50)
    log(f"✅ 完成！{url}")
    log("=" * 50)

if __name__ == "__main__":
    run()
