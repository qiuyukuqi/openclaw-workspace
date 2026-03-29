#!/usr/bin/env python3
"""
🌙 助眠/白噪音视频生成流水线
流程: Suno纯音乐 → 即梦生图(多张) → ffmpeg合成动态视频
"""
import os, sys, json, subprocess, time, requests

SUNO_API_KEY = "sk-VRTrDBlfKY1TXdffDiDNJtgUajH0EY7AN15pLWN1GDVbZC6c"
DASHSCOPE_KEY = "sk-bdc4ae848a284a459a9e9c2413daa8ce"
OUTPUT_DIR = os.path.expanduser("~/.openclaw/workspace/skills/yt-auto-channel/data/sleep")
TEMP_DIR = "/tmp/openclaw/yt-sleep"

def submit_suno_instrumental(prompt, tags, duration=None):
    """提交Suno纯音乐生成"""
    payload = {
        "gpt_description_prompt": prompt,
        "prompt": "",
        "tags": tags,
        "mv": "chirp-crow",
        "title": "",
        "make_instrumental": True
    }
    if duration:
        payload["duration"] = duration
    r = requests.post("https://api.302.ai/suno/submit/music/custom",
        headers={"Authorization": f"Bearer {SUNO_API_KEY}"},
        json=payload, timeout=30)
    return r.json()

def wait_suno(task_id, max_wait=600):
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

def generate_images(prompt, count=3):
    """生成多张风景图"""
    r = requests.post("https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis",
        headers={"Authorization": f"Bearer {DASHSCOPE_KEY}", "X-DashScope-Async": "enable"},
        json={
            "model": "wanx-v1",
            "input": {"prompt": prompt},
            "parameters": {"size": "1280*720", "n": count}
        }, timeout=30)
    task_id = r.json().get("output", {}).get("task_id")
    if not task_id:
        raise RuntimeError(f"万相提交失败: {r.text}")
    
    for _ in range(120):
        time.sleep(3)
        r = requests.get(f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}",
            headers={"Authorization": f"Bearer {DASHSCOPE_KEY}"}, timeout=15)
        result = r.json()
        if result.get("output", {}).get("task_status") == "SUCCEEDED":
            return [item["url"] for item in result["output"]["results"]]
    raise RuntimeError("万相生成超时")

def download_file(url, path):
    r = requests.get(url, timeout=60, stream=True)
    with open(path, 'wb') as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)

def get_duration(path):
    r = subprocess.run(['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
        '-of', 'csv=p=0', path], capture_output=True, text=True, timeout=10)
    return float(r.stdout.strip())

def compose_sleep_video(audio_path, image_paths, output_path):
    """合成助眠视频: 多图缓慢切换+Ken Burns效果+音频"""
    dur = get_duration(audio_path)
    
    # 生成concat文件：每张图显示若干秒，缓慢缩放
    segment_dur = dur / len(image_paths)
    filter_parts = []
    for i, img in enumerate(image_paths):
        filter_parts.append(
            f"[{i}:v]scale=1280:720,zoompan=z='min(zoom+0.0002,1.1)':"
            f"d={int(segment_dur)}:s=1280x720:fps=30,format=yuv420p[v{i}]"
        )
    
    # concat所有段
    vfilter = ";".join(filter_parts)
    concat_inputs = "".join(f"[v{i}]" for i in range(len(image_paths)))
    vfilter += f";{concat_inputs}concat=n={len(image_paths)}:v=1:a=0[outv]"
    
    inputs = []
    for img in image_paths:
        inputs.extend(['-loop', '1', '-t', str(segment_dur), '-i', img])
    inputs.extend(['-i', audio_path])
    
    cmd = ['ffmpeg', '-y'] + inputs + [
        '-filter_complex', vfilter,
        '-map', '[outv]', '-map', f'{len(image_paths)}:a',
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
        '-c:a', 'aac', '-b:a', '192k',
        '-shortest',
        '-movflags', '+faststart',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg失败: {result.stderr[-500:]}")

def main():
    style = sys.argv[1] if len(sys.argv) > 1 else "rain"
    
    themes = {
        "rain": {
            "prompt": "Gentle rain on window at night, cozy room, warm lamp, cinematic, 4k, no text, peaceful",
            "tags": "ambient, rain sounds, lofi, peaceful, sleep",
            "title_prefix": "雨夜助眠"
        },
        "forest": {
            "prompt": "Misty forest at dawn, ethereal light through trees, cinematic, 4k, no text, nature",
            "tags": "ambient, nature sounds, forest, peaceful, meditation",
            "title_prefix": "森林冥想"
        },
        "ocean": {
            "prompt": "Ocean waves at sunset, calm sea, golden hour, cinematic, 4k, no text, peaceful",
            "tags": "ambient, ocean waves, calming, sleep, relaxation",
            "title_prefix": "海浪助眠"
        },
        "piano": {
            "prompt": "Grand piano in dark room, moonlight through window, cinematic, 4k, no text, elegant",
            "tags": "ambient, piano, classical, relaxing, sleep",
            "title_prefix": "钢琴助眠"
        },
        "space": {
            "prompt": "Starry night sky, northern lights, galaxy, cinematic, 4k, no text, dreamy",
            "tags": "ambient, space, cosmic, meditation, sleep",
            "title_prefix": "星空冥想"
        }
    }
    
    theme = themes.get(style, themes["rain"])
    
    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print(f"🌙 Step 1: 生成{theme['title_prefix']}纯音乐...")
    submit = submit_suno_instrumental(theme["prompt"], theme["tags"])
    task_id = submit.get("data", {}).get("task_id") or submit.get("task_id")
    if not task_id:
        raise RuntimeError(f"Suno提交失败: {submit}")
    
    song = wait_suno(task_id)
    audio_url = song["audio_url"]
    title = f"{theme['title_prefix']} - {song.get('title', 'AI Ambient')}"
    
    audio_path = os.path.join(TEMP_DIR, "audio.mp3")
    download_file(audio_url, audio_path)
    print(f"✅ 音频生成完成: {title}")
    
    print(f"🖼️ Step 2: 生成背景图(3张)...")
    image_urls = generate_images(theme["prompt"], count=3)
    image_paths = []
    for i, url in enumerate(image_urls):
        p = os.path.join(TEMP_DIR, f"bg_{i}.jpg")
        download_file(url, p)
        image_paths.append(p)
    print(f"✅ 背景图生成完成")
    
    print("🎬 Step 3: 合成视频...")
    output_path = os.path.join(OUTPUT_DIR, f"{int(time.time())}_{theme['title_prefix']}.mp4")
    compose_sleep_video(audio_path, image_paths, output_path)
    
    size_mb = os.path.getsize(output_path) / 1024 / 1024
    dur = get_duration(output_path)
    print(f"\n✅ 完成! {output_path}")
    print(f"大小: {size_mb:.1f}MB, 时长: {dur:.0f}秒")
    return output_path

if __name__ == "__main__":
    result = main()
    print(f"OUTPUT:{result}")
