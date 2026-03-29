#!/usr/bin/env python3
"""
🎵 歌词视频生成流水线
流程: Suno生成歌曲 → 提取音频+歌词 → 即梦生图 → ffmpeg合成动态歌词视频
"""
import os, sys, json, subprocess, time, re, requests

SUNO_API_KEY = "sk-VRTrDBlfKY1TXdffDiDNJtgUajH0EY7AN15pLWN1GDVbZC6c"
DASHSCOPE_KEY = "sk-bdc4ae848a284a459a9e9c2413daa8ce"
OUTPUT_DIR = os.path.expanduser("~/.openclaw/workspace/skills/yt-auto-channel/data/lyrics")
TEMP_DIR = "/tmp/openclaw/yt-lyrics"

def submit_suno(prompt, tags, model="chirp-crow", make_instrumental=False):
    """提交Suno生成任务"""
    r = requests.post("https://api.302.ai/suno/submit/music/custom",
        headers={"Authorization": f"Bearer {SUNO_API_KEY}"},
        json={
            "gpt_description_prompt": prompt,
            "prompt": "",
            "tags": tags,
            "mv": model,
            "title": "",
            "make_instrumental": make_instrumental
        }, timeout=30)
    return r.json()

def wait_suno(task_id, max_wait=600):
    """等待Suno生成完成"""
    start = time.time()
    while time.time() - start < max_wait:
        r = requests.get(f"https://api.302.ai/suno/fetch/{task_id}",
            headers={"Authorization": f"Bearer {SUNO_API_KEY}"}, timeout=15)
        data = r.json()
        if not data.get("data") or not data["data"].get("data"):
            print(f"等待中... ({int(time.time()-start)}s)")
            time.sleep(15)
            continue
        for song in data["data"]["data"]:
            if song.get("status") == "complete":
                return song
        print(f"等待中... ({int(time.time()-start)}s)")
        time.sleep(15)
    raise RuntimeError("Suno生成超时")

def download_file(url, path):
    """下载文件"""
    r = requests.get(url, timeout=60, stream=True)
    with open(path, 'wb') as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)

def generate_background_image(prompt):
    """用通义万相生成背景图"""
    r = requests.post("https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis",
        headers={"Authorization": f"Bearer {DASHSCOPE_KEY}", "X-DashScope-Async": "enable"},
        json={
            "model": "wanx-v1",
            "input": {"prompt": prompt},
            "parameters": {"size": "1280*720", "n": 1}
        }, timeout=30)
    task_id = r.json().get("output", {}).get("task_id")
    if not task_id:
        raise RuntimeError(f"万相提交失败: {r.text}")
    
    for _ in range(60):
        time.sleep(3)
        r = requests.get(f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}",
            headers={"Authorization": f"Bearer {DASHSCOPE_KEY}"}, timeout=15)
        result = r.json()
        if result.get("output", {}).get("task_status") == "SUCCEEDED":
            return result["output"]["results"][0]["url"]
    raise RuntimeError("万相生成超时")

def parse_lyrics(lyrics_text):
    """解析歌词文本为SRT格式"""
    lines = [l.strip() for l in lyrics_text.strip().split('\n') if l.strip()]
    # 按时间戳或行号分块
    srt_entries = []
    ts = 0
    idx = 1
    for line in lines:
        if line.startswith('[') and line.endswith(']'):
            continue  # skip metadata
        duration = max(2, min(5, len(line) * 0.3))  # 每行2-5秒
        srt_entries.append(f"{idx}\n{format_time(ts)} --> {format_time(ts+duration)}\n{line}\n")
        ts += duration
        idx += 1
    return '\n'.join(srt_entries), ts

def format_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"00:{m:02d}:{s:02d},{ms:03d}"

def compose_video(audio_path, bg_image_path, srt_path, output_path):
    """用ffmpeg合成歌词视频: 背景+音频+歌词字幕"""
    # 生成字幕ass文件（更好看）
    ass_path = srt_path.replace('.srt', '.ass')
    subprocess.run(['ffmpeg', '-y', '-i', srt_path, '-f', 'ass', ass_path],
        capture_output=True, timeout=10)
    
    cmd = [
        'ffmpeg', '-y',
        '-loop', '1', '-i', bg_image_path,  # 循环背景图
        '-i', audio_path,
        '-vf', f"scale=1280:720,ass={ass_path},zoompan=z='min(zoom+0.0003,1.15)':d={get_duration(audio_path)}:s=1280x720:fps=30",
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
        '-c:a', 'aac', '-b:a', '192k',
        '-shortest',
        '-movflags', '+faststart',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg失败: {result.stderr[-500:]}")

def get_duration(audio_path):
    r = subprocess.run(['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
        '-of', 'csv=p=0', audio_path], capture_output=True, text=True, timeout=10)
    return int(float(r.stdout.strip()))

def main():
    prompt = sys.argv[1] if len(sys.argv) > 1 else "A beautiful Chinese pop song about autumn memories"
    tags = sys.argv[2] if len(sys.argv) > 2 else "chinese pop, emotional, ballad"
    
    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("🎵 Step 1: Suno生成歌曲...")
    submit = submit_suno(prompt, tags)
    task_id = submit.get("data", {}).get("task_id") or submit.get("task_id")
    if not task_id:
        raise RuntimeError(f"Suno提交失败: {submit}")
    print(f"Task ID: {task_id}")
    
    song = wait_suno(task_id)
    audio_url = song["audio_url"]
    lyrics_text = song.get("prompt", song.get("lyrics", ""))
    title = song.get("title", "AI Music")
    
    print(f"✅ 歌曲生成完成: {title}")
    
    # 下载音频
    audio_path = os.path.join(TEMP_DIR, "song.mp3")
    download_file(audio_url, audio_path)
    
    print("🖼️ Step 2: 生成背景图...")
    bg_prompt = f"Beautiful artistic background for music video, {tags}, dreamy atmosphere, cinematic lighting, 4k, no text"
    bg_url = generate_background_image(bg_prompt)
    bg_path = os.path.join(TEMP_DIR, "bg.jpg")
    download_file(bg_url, bg_path)
    
    print("📝 Step 3: 生成歌词字幕...")
    srt_path = os.path.join(TEMP_DIR, "lyrics.srt")
    srt_content, total_duration = parse_lyrics(lyrics_text)
    with open(srt_path, 'w') as f:
        f.write(srt_content)
    
    print("🎬 Step 4: 合成视频...")
    output_path = os.path.join(OUTPUT_DIR, f"{int(time.time())}_{title[:20]}.mp4")
    compose_video(audio_path, bg_path, srt_path, output_path)
    
    print(f"\n✅ 完成! 视频已保存: {output_path}")
    print(f"文件大小: {os.path.getsize(output_path)/1024/1024:.1f}MB")
    print(f"时长: {total_duration}秒")
    return output_path

if __name__ == "__main__":
    result = main()
    print(f"OUTPUT:{result}")
