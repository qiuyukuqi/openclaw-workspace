#!/usr/bin/env python3
"""
📖 故事朗读视频生成流水线
流程: 故事文本分段 → 智谱voice_clone配音 → 即梦生插图 → ffmpeg合成
"""
import os, sys, json, subprocess, time, requests, re

ZHIPU_KEY = "579714647a6c40d7bb95632559736fb2.VqYfT1pnRPS34CQu"
DASHSCOPE_KEY = "sk-bdc4ae848a284a459a9e9c2413daa8ce"
SUNO_API_KEY = "sk-VRTrDBlfKY1TXdffDiDNJtgUajH0EY7AN15pLWN1GDVbZC6c"
OUTPUT_DIR = os.path.expanduser("~/.openclaw/workspace/skills/yt-auto-channel/data/story")
TEMP_DIR = "/tmp/openclaw/yt-story"

VOICE_REF = os.path.expanduser("~/.openclaw/workspace/skills/yt-auto-channel/data/voice_ref.wav")  # 音色参考文件

def generate_voice(text, output_path):
    """用智谱TTS生成语音"""
    r = requests.post("https://open.bigmodel.cn/api/paas/v4/audio/speech",
        headers={"Authorization": f"Bearer {ZHIPU_KEY}"},
        json={
            "model": "tts-1",
            "input": text,
            "voice": "male-qn-qingse"  # 清澈男声
        }, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"TTS失败: {r.status_code} {r.text}")
    with open(output_path, 'wb') as f:
        f.write(r.content)

def generate_bgm():
    """用Suno生成背景音乐"""
    r = requests.post("https://api.302.ai/suno/submit/music/custom",
        headers={"Authorization": f"Bearer {SUNO_API_KEY}"},
        json={
            "gpt_description_prompt": "Soft gentle background music for storytelling, very quiet, no melody, ambient pad",
            "prompt": "",
            "tags": "ambient, storytelling bgm, quiet, gentle, no drums",
            "mv": "chirp-crow",
            "title": "",
            "make_instrumental": True
        }, timeout=30)
    task_id = r.json().get("data", {}).get("task_id") or r.json().get("task_id")
    if not task_id:
        return None
    
    start = time.time()
    while time.time() - start < 600:
        try:
            r = requests.get(f"https://api.302.ai/suno/fetch/{task_id}",
                headers={"Authorization": f"Bearer {SUNO_API_KEY}"}, timeout=15)
            data = r.json()
            for song in data.get("data", {}).get("data", []):
                if song.get("status") == "complete":
                    return song["audio_url"]
        except:
            pass
        time.sleep(15)
    return None

def generate_image(prompt):
    """生成插图"""
    r = requests.post("https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis",
        headers={"Authorization": f"Bearer {DASHSCOPE_KEY}", "X-DashScope-Async": "enable"},
        json={
            "model": "wanx-v1",
            "input": {"prompt": prompt + ", illustration style, warm colors, storybook, 4k, no text"},
            "parameters": {"size": "1280*720", "n": 1}
        }, timeout=30)
    task_id = r.json().get("output", {}).get("task_id")
    if not task_id:
        return None
    for _ in range(120):
        time.sleep(3)
        r = requests.get(f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}",
            headers={"Authorization": f"Bearer {DASHSCOPE_KEY}"}, timeout=15)
        result = r.json()
        if result.get("output", {}).get("task_status") == "SUCCEEDED":
            return result["output"]["results"][0]["url"]
    return None

def download_file(url, path):
    r = requests.get(url, timeout=60, stream=True)
    with open(path, 'wb') as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)

def get_duration(path):
    r = subprocess.run(['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
        '-of', 'csv=p=0', path], capture_output=True, text=True, timeout=10)
    return float(r.stdout.strip())

def compose_story_video(voice_path, bgm_path, image_paths, subtitle_path, output_path):
    """合成故事视频: 插图+配音+字幕+背景音乐"""
    voice_dur = get_duration(voice_path)
    
    # 生成每段对应的图片序列
    segment_dur = voice_dur / len(image_paths) if image_paths else voice_dur
    
    # 用单图+Ken Burns（简化版，避免复杂concat）
    # 先把所有配音段拼接
    # 再生成封面图
    if image_paths:
        # 创建图片列表文件，每张图显示一段时间
        img_dur = voice_dur / len(image_paths)
        with open(os.path.join(TEMP_DIR, "imglist.txt"), 'w') as f:
            for img in image_paths:
                f.write(f"file '{img}'\n")
                f.write(f"duration {img_dur}\n")
            # 最后一行需要重复最后一张图
            f.write(f"file '{image_paths[-1]}'\n")
        
        cmd = [
            'ffmpeg', '-y',
            '-f', 'concat', '-safe', '0', '-i', os.path.join(TEMP_DIR, "imglist.txt"),
            '-i', voice_path,
        ]
        if bgm_path and os.path.exists(bgm_path):
            cmd.extend(['-i', bgm_path])
        
        vfilter = "scale=1280:720,zoompan=z='min(zoom+0.0002,1.1)':d=300:s=1280x720:fps=24"
        if subtitle_path and os.path.exists(subtitle_path):
            vfilter += f",subtitles={subtitle_path}"
        
        cmd.extend([
            '-vf', vfilter,
            '-map', '0:v', '-map', '1:a',
        ])
        
        if bgm_path and os.path.exists(bgm_path):
            cmd.extend([
                '-filter_complex', f'[2:a]volume=0.15[bgm]',
                '-map', '[bgm]'
            ])
            cmd.extend(['-c:a', 'aac', '-b:a', '192k'])
            # Mix voice and bgm
            cmd = [
                'ffmpeg', '-y',
                '-f', 'concat', '-safe', '0', '-i', os.path.join(TEMP_DIR, "imglist.txt"),
                '-i', voice_path,
                '-i', bgm_path,
                '-filter_complex', 
                    f'[0:v]scale=1280:720,zoompan=z=\'min(zoom+0.0002,1.1)\':d=300:s=1280x720:fps=24{",subtitles=" + subtitle_path if subtitle_path else ""}[v];'
                    f'[1:a][2:a]amix=inputs=2:weights=1 0.15[a]',
                '-map', '[v]', '-map', '[a]',
            ]
        
        cmd.extend([
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
            '-c:a', 'aac', '-b:a', '192k',
            '-shortest', '-movflags', '+faststart',
            output_path
        ])
    else:
        # 无图，纯音频+字幕
        cmd = ['ffmpeg', '-y', '-i', voice_path]
        if bgm_path:
            cmd.extend(['-i', bgm_path])
        cmd.extend(['-vf', f'color=c=0x1a1a2e:s=1280x720:d={int(voice_dur)},format=yuv420p' + (f',subtitles={subtitle_path}' if subtitle_path else '')])
        cmd.extend(['-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
            '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', output_path])
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg失败: {result.stderr[-500:]}")

def main():
    story_file = sys.argv[1] if len(sys.argv) > 1 else None
    story_text = sys.argv[2] if len(sys.argv) > 2 else None
    title = sys.argv[3] if len(sys.argv) > 3 else "AI故事朗读"
    
    if story_file:
        with open(story_file, 'r') as f:
            story_text = f.read()
    elif not story_text:
        story_text = "从前有一座山，山里有个庙，庙里有个老和尚在给小和尚讲故事。故事讲的是，从前有一座山..."
    
    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 分段（每段约200字配一张插图）
    paragraphs = [p.strip() for p in re.split(r'\n{2,}|\n', story_text) if p.strip()]
    
    print(f"📖 Step 1: 生成配音 ({len(paragraphs)}段)...")
    voice_segments = []
    for i, para in enumerate(paragraphs):
        vp = os.path.join(TEMP_DIR, f"voice_{i}.mp3")
        generate_voice(para[:500], vp)  # TTS限长
        voice_segments.append(vp)
        print(f"  段{i+1}/{len(paragraphs)} 完成")
    
    # 拼接配音
    voice_path = os.path.join(TEMP_DIR, "voice_full.mp3")
    concat_file = os.path.join(TEMP_DIR, "voice_list.txt")
    with open(concat_file, 'w') as f:
        for vp in voice_segments:
            f.write(f"file '{vp}'\n")
    subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', concat_file, '-c', 'copy', voice_path],
        capture_output=True, timeout=30)
    
    # 生成字幕
    sub_path = os.path.join(TEMP_DIR, "subs.srt")
    generate_subtitles(paragraphs, voice_segments, sub_path)
    
    print("🎵 Step 2: 生成背景音乐...")
    bgm_path = os.path.join(TEMP_DIR, "bgm.mp3")
    bgm_url = generate_bgm()
    if bgm_url:
        download_file(bgm_url, bgm_path)
        print("✅ BGM生成完成")
    else:
        bgm_path = None
        print("⚠️ BGM生成跳过")
    
    print("🖼️ Step 3: 生成插图...")
    image_paths = []
    for i, para in enumerate(paragraphs[:5]):  # 最多5张插图
        img_prompt = para[:100]  # 用前100字作为图片提示
        img_url = generate_image(img_prompt)
        if img_url:
            img_path = os.path.join(TEMP_DIR, f"img_{i}.jpg")
            download_file(img_url, img_path)
            image_paths.append(img_path)
            print(f"  插图{i+1} 完成")
    print(f"✅ 共生成{len(image_paths)}张插图")
    
    print("🎬 Step 4: 合成视频...")
    output_path = os.path.join(OUTPUT_DIR, f"{int(time.time())}_{title[:20]}.mp4")
    compose_story_video(voice_path, bgm_path, image_paths, sub_path, output_path)
    
    size_mb = os.path.getsize(output_path) / 1024 / 1024
    dur = get_duration(output_path)
    print(f"\n✅ 完成! {output_path}")
    print(f"大小: {size_mb:.1f}MB, 时长: {dur:.0f}秒")
    return output_path

def generate_subtitles(paragraphs, voice_segments, output_path):
    """根据段落和音频时长生成SRT字幕"""
    srt = ""
    idx = 1
    ts = 0.0
    for i, seg_path in enumerate(voice_segments):
        dur = get_duration(seg_path)
        text = paragraphs[i] if i < len(paragraphs) else ""
        # 按句号分句
        sentences = re.split(r'[。！？\.\!\?]', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        sent_dur = dur / max(len(sentences), 1)
        for sent in sentences:
            h, rem = divmod(int(ts), 3600)
            m, s = divmod(rem, 60)
            ms = int((ts % 1) * 1000)
            ts2 = ts + sent_dur
            h2, rem2 = divmod(int(ts2), 3600)
            m2, s2 = divmod(rem2, 60)
            ms2 = int((ts2 % 1) * 1000)
            srt += f"{idx}\n00:{m:02d}:{s:02d},{ms:03d} --> 00:{m2:02d}:{s2:02d},{ms2:03d}\n{sent}\n\n"
            ts = ts2
            idx += 1
    with open(output_path, 'w') as f:
        f.write(srt)

if __name__ == "__main__":
    result = main()
    print(f"OUTPUT:{result}")
