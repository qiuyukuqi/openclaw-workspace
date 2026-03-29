#!/usr/bin/env python3
"""
🚀 YouTube多频道自动上传调度
生成视频 → 上传YouTube → 通知结果
"""
import os, sys, json, subprocess, time

SCRIPTS_DIR = os.path.expanduser("~/.openclaw/workspace/skills/yt-auto-channel/scripts")
YOUTUBE_UPLOAD = os.path.expanduser("~/.openclaw/workspace/skills/ai-music-channel/scripts/youtube_upload.py")
PLAYLISTS = json.load(open(os.path.expanduser("~/.openclaw/workspace/.youtube_playlists.json")))

def upload_to_youtube(video_path, title, description, tags, playlist_key=None):
    """上传视频到YouTube"""
    cmd = ['python3', YOUTUBE_UPLOAD,
        '--file', video_path,
        '--title', title,
        '--description', description,
        '--tags'] + tags
    if playlist_key and playlist_key in PLAYLISTS:
        cmd.extend(['--playlist', PLAYLISTS[playlist_key]])
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    print(result.stdout)
    if result.returncode != 0:
        print(f"上传失败: {result.stderr}")
        return None
    
    # 提取URL
    for line in result.stdout.split('\n'):
        if 'youtube.com/watch' in line:
            return line.strip()
    return None

def run_lyrics_pipeline(prompt, tags, title="AI歌词视频"):
    """歌词视频流水线"""
    print("🎵 === 歌词视频流水线 ===")
    cmd = ['python3', os.path.join(SCRIPTS_DIR, 'generate_lyrics_video.py'), prompt, tags]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=SCRIPTS_DIR)
    print(result.stdout)
    if result.returncode != 0:
        print(f"生成失败: {result.stderr}")
        return
    
    video_path = None
    for line in result.stdout.split('\n'):
        if line.startswith("OUTPUT:"):
            video_path = line.replace("OUTPUT:", "")
    
    if video_path and os.path.exists(video_path):
        url = upload_to_youtube(video_path, title,
            f"🎵 AI生成的歌词视频 | {prompt}",
            ["AI音乐", "歌词视频", "AI歌词", tags],
            "lyrics")
        if url:
            print(f"✅ 上传成功: {url}")

def run_sleep_pipeline(style="rain"):
    """助眠视频流水线"""
    print(f"🌙 === 助眠视频流水线 ({style}) ===")
    cmd = ['python3', os.path.join(SCRIPTS_DIR, 'generate_sleep_video.py'), style]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=SCRIPTS_DIR)
    print(result.stdout)
    if result.returncode != 0:
        print(f"生成失败: {result.stderr}")
        return
    
    video_path = None
    for line in result.stdout.split('\n'):
        if line.startswith("OUTPUT:"):
            video_path = line.replace("OUTPUT:", "")
    
    if video_path and os.path.exists(video_path):
        url = upload_to_youtube(video_path, f"🌙 {style}助眠音乐 | 深度睡眠白噪音",
            f"放松身心，沉浸式助眠体验 | AI生成",
            ["助眠音乐", "白噪音", "深度睡眠", "放松", "冥想", style],
            "sleep")
        if url:
            print(f"✅ 上传成功: {url}")

def run_story_pipeline(story_text, title="AI故事朗读"):
    """故事朗读流水线"""
    print("📖 === 故事朗读流水线 ===")
    story_file = os.path.join(SCRIPTS_DIR, "..", "data", "story", "current_story.txt")
    with open(story_file, 'w') as f:
        f.write(story_text)
    
    cmd = ['python3', os.path.join(SCRIPTS_DIR, 'generate_story_video.py'), story_file, story_text, title]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=900, cwd=SCRIPTS_DIR)
    print(result.stdout)
    if result.returncode != 0:
        print(f"生成失败: {result.stderr}")
        return
    
    video_path = None
    for line in result.stdout.split('\n'):
        if line.startswith("OUTPUT:"):
            video_path = line.replace("OUTPUT:", "")
    
    if video_path and os.path.exists(video_path):
        url = upload_to_youtube(video_path, f"📖 {title} | AI故事朗读",
            f"AI配音故事朗读，陪伴你的每一个夜晚",
            ["故事朗读", "AI配音", "睡前故事", "有声书", "AI故事"],
            "story")
        if url:
            print(f"✅ 上传成功: {url}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  python3 pipeline.py lyrics <prompt> <tags> [title]")
        print("  python3 pipeline.py sleep [rain|forest|ocean|piano|space]")
        print("  python3 pipeline.py story <story_text> [title]")
        sys.exit(1)
    
    mode = sys.argv[1]
    if mode == "lyrics":
        prompt = sys.argv[2] if len(sys.argv) > 2 else "A beautiful Chinese pop song"
        tags = sys.argv[3] if len(sys.argv) > 3 else "chinese pop"
        title = sys.argv[4] if len(sys.argv) > 4 else "AI歌词视频"
        run_lyrics_pipeline(prompt, tags, title)
    elif mode == "sleep":
        style = sys.argv[2] if len(sys.argv) > 2 else "rain"
        run_sleep_pipeline(style)
    elif mode == "story":
        story = sys.argv[2] if len(sys.argv) > 2 else "这是一个关于星星的故事..."
        title = sys.argv[3] if len(sys.argv) > 3 else "AI故事朗读"
        run_story_pipeline(story, title)
