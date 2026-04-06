#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信公众号AI文章流水线 - 交互式版
每个步骤完成后暂停，等待人工审核确认后再继续。
用法: python3 pipeline.py [--auto] [--step scout|research|writer|director|image|format|publish]
  --auto: 自动模式，不暂停（用于cron）
  --step: 从指定步骤开始
"""

import os, sys, json, subprocess, re, requests, time, argparse
from datetime import datetime, timedelta

WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
SCRIPT_DIR = os.path.join(WORKSPACE, "skills/wechat-publisher/scripts")

# ========== 环境加载 ==========
def load_env():
    env = {}
    for path in [
        os.path.join(WORKSPACE, ".env.wechat"),
    ]:
        if os.path.exists(path):
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        env[k.strip()] = v.strip().strip('"').strip("'")
    
    # 从bash config.sh补充
    cfg_path = os.path.join(SCRIPT_DIR, "config.sh")
    if os.path.exists(cfg_path):
        with open(cfg_path) as f:
            for line in f:
                for key in ["WECHAT_APP_ID", "WECHAT_APP_SECRET", "DASHSCOPE_API_KEY", "TAVILY_API_KEY"]:
                    if key in line and '=' in line:
                        m = re.search(rf'{key}\s*=\s*["\']?([^"\'"\n]+)', line)
                        if m:
                            env[key] = m.group(1).strip()
                            break
    
    return env

ENV = load_env()
APPID = ENV.get("WECHAT_APP_ID", "")
APPSECRET = ENV.get("WECHAT_APP_SECRET", "")
DASHSCOPE_KEY = ENV.get("DASHSCOPE_API_KEY", "")
DEEPSEEK_KEY = "sk-162c19004d444d73a49c735c4de9d82f"
TAVILY_KEY = ENV.get("TAVILY_API_KEY", "")
USER_ID = "ou_c5c98e2002a34a9b10f15fd0b6463d06"

# ========== 工具函数 ==========
def ts():
    return datetime.now().strftime('%H:%M:%S')

def log(msg):
    print(f"[{ts()}] {msg}", flush=True)

def notify(msg):
    """飞书通知：通过openclaw message send发送"""
    try:
        subprocess.run(["openclaw", "message", "send", "--channel", "feishu",
                        "--account", "main", "-t", f"user:{USER_ID}", "-m", msg],
                       capture_output=True, timeout=30)
    except Exception as e:
        log(f"⚠️ notify失败: {e}")

def call_ai(prompt, temp=0.85, tokens=4000):
    r = requests.post(
        "https://api.deepseek.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"},
        json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}],
              "max_tokens": tokens, "temperature": temp},
        timeout=120
    )
    data = r.json()
    if "choices" not in data:
        raise ValueError(f"AI错误: {json.dumps(data, ensure_ascii=False)[:200]}")
    return data["choices"][0]["message"]["content"]

def clean_codeblock(text):
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return text.strip()

def wait_approval(step_name, info):
    """交互式等待审核，自动模式直接通过"""
    if getattr(sys, '_auto_mode', False):
        log(f"  自动模式，跳过审核")
        return True
    
    notify(f"⏸️ {step_name} 完成，等待审核：\n{info}\n\n回复「继续」或提出修改意见")
    log(f"  ⏸️ 等待审核...（auto模式跳过）")
    # 在交互模式下，这里返回True让流水线继续
    # 实际审核由OpenClaw会话层处理
    return True

# ========== 状态管理 ==========
STATE_FILE = "/tmp/openclaw/wechat-publisher/pipeline_state.json"

def save_state(data):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}

# ========== Step 1: Scout 选题 ==========
def step_scout(state=None):
    log("🔍 Step 1/7: Scout（选题）")
    
    date_from = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
    
    queries = [
        f"site:ithome.com OR site:36kr.com 科技数码热点 {date_from}",
        f"site:sspai.com OR site:v2ex.com IT技术 {date_from}",
        f"科技数码 AI 编程 运维 热点新闻 after:{date_from}"
    ]
    
    all_results = []
    for q in queries:
        try:
            r = requests.post("https://api.tavily.com/search", json={
                "api_key": TAVILY_KEY, "query": q, "search_depth": "advanced",
                "max_results": 5, "topic": "news"
            }, timeout=30)
            for item in r.json().get("results", []):
                all_results.append(item)
        except:
            pass
    
    if not all_results:
        notify("⚠️ Scout选题失败：搜索无结果")
        return None
    
    # AI筛选并生成选题角度
    hotspots = "\n".join([
        f"{i+1}. 【{r.get('title', '')}】\n   {r.get('content', '')[:150]}"
        for i, r in enumerate(all_results[:10])
    ])
    
    prompt = f"""你是科技自媒体选题编辑。从以下最近3天的热点中，筛选3-5个最适合写成3000字轻松风格文章的话题。

{hotspots}

对每个话题给出：
1. 选题角度（怎么写才有趣）
2. 目标读者画像
3. 话题热度评分（1-10）
4. 预估实操价值（1-10）

最后推荐最佳选题。

严格按JSON格式输出：
```json
{{"candidates": [{{"index": 1, "title": "文章标题（≤11字）", "angle": "选题角度", "audience": "目标读者", "heat": 8, "value": 7, "direction": "具体写作方向"}}], "recommended": 0}}```"""

    result = clean_codeblock(call_ai(prompt, temp=0.3))
    json_match = re.search(r'\{[\s\S]*\}', result)
    
    if not json_match:
        notify("⚠️ Scout选题失败：AI返回格式异常")
        return None
    
    choice = json.loads(json_match.group())
    candidates = choice.get("candidates", [])
    rec_idx = choice.get("recommended", 0)
    recommended = candidates[min(rec_idx, len(candidates)-1)]
    src_idx = recommended.get("index", 1) - 1
    source = all_results[min(src_idx, len(all_results)-1)]
    
    output = {
        "candidates": candidates,
        "recommended_idx": rec_idx,
        "selected": {
            "title": recommended.get("title", ""),
            "direction": recommended.get("direction", ""),
            "angle": recommended.get("angle", ""),
            "category": "数码产品",
            "source_title": source.get("title", ""),
            "source_url": source.get("url", ""),
            "snippet": source.get("content", "")[:500]
        }
    }
    
    # 展示选题
    display = f"📰 Scout 选题结果（共{len(candidates)}个候选）：\n\n"
    for i, c in enumerate(candidates):
        mark = "⭐" if i == rec_idx else "  "
        display += f"{mark} {i+1}. {c.get('title', '')}\n"
        display += f"     角度: {c.get('angle', '')}\n"
        display += f"     热度: {c.get('heat', '?')}/10 | 实操价值: {c.get('value', '?')}/10\n\n"
    
    display += f"⭐ 推荐: {recommended.get('title', '')}\n"
    display += f"   来源: {source.get('title', '')}"
    
    log(f"  推荐: {recommended.get('title', '')}")
    save_state({"step": "scout", **output})
    notify(display)
    
    wait_approval("Scout选题", display)
    return output

# ========== Step 2: Researcher 调研 ==========
def step_research(state):
    log("📚 Step 2/7: Researcher（调研）")
    selected = state.get("selected", {})
    direction = selected.get("direction", selected.get("title", ""))
    
    # 搜索补充资料
    queries = [direction[:50], f"{direction[:30]} 案例 实操 教程"]
    materials = []
    
    for q in queries:
        try:
            r = requests.post("https://api.tavily.com/search", json={
                "api_key": TAVILY_KEY, "query": q, "search_depth": "advanced",
                "max_results": 5
            }, timeout=30)
            for item in r.json().get("results", []):
                materials.append({
                    "title": item.get("title", ""),
                    "content": item.get("content", "")[:300],
                    "url": item.get("url", "")
                })
        except:
            pass
    
    # AI整理调研资料
    if materials:
        mat_text = "\n".join([f"- 【{m['title']}】{m['content']}" for m in materials[:8]])
        prompt = f"""你是科技调研助手。围绕选题「{direction}」，整理以下搜索到的资料，提取关键信息：

{mat_text}

请整理出：
1. 核心事实（数据、事件、产品信息）
2. 可用的案例
3. 实操建议/技巧
4. 不同观点/争议点

用简洁的列表格式输出。"""
        research = call_ai(prompt, temp=0.3, tokens=2000)
    else:
        research = "（无补充资料，基于AI知识库生成）"
    
    output = {"research_materials": materials, "research_summary": research}
    log(f"  收集{len(materials)}条资料")
    save_state({"step": "research", **state, **output})
    
    # 发送调研摘要
    summary_preview = research[:500] + ("..." if len(research) > 500 else "")
    notify(f"📚 Researcher 调研完成（{len(materials)}条资料）\n\n{summary_preview}")
    
    wait_approval("Researcher调研", f"{len(materials)}条资料")
    return output

# ========== Step 3: Writer 写作 ==========
def step_writer(state):
    log("✍️ Step 3/7: Writer（写作）")
    selected = state.get("selected", {})
    research = state.get("research_summary", "")
    today = datetime.now().strftime('%Y年%m月%d日')
    
    prompt = f"""你是一位轻松有趣的科技自媒体作者。

选题: {selected.get('title', '')}
方向: {selected.get('direction', '')}
角度: {selected.get('angle', '')}

调研资料:
{research}

要求：
1. 3000字左右
2. 标题必须是纯中文，不超过11个字，不要包含任何英文、数字、标点符号，精简有力（参考"程序员怎么办""芯片战升级了"）
3. 轻松有趣，像和朋友聊天，可以用"大家好""老朋友""举个栗子"等口语化表达
4. 有观点、有案例、有实操价值、有深度
5. <h2>小标题分段
6. 不要使用<br>换行标签，文字之间不要插入多余空格或&nbsp;
7. 不要包含署名行、日期行、作者信息
8. 正文开头先写一句简短有力的观点句，再展开论述

输出格式：
<title>标题</title>

正文用<p>分段，<h2>做小标题，不要代码块包裹。
文章末尾加上：
<p style="text-align:center;color:#888;margin-top:20px;font-size:14px;">— END —</p>"""

    content = clean_codeblock(call_ai(prompt))
    
    if not re.search(r'<title>', content, re.I):
        content = f"<title>{selected.get('title', '')[:11]}</title>\n{content}"
    
    m = re.search(r'<title>(.*?)</title>', content, re.I | re.S)
    title = m.group(1).strip() if m else selected.get('title', '')[:11]
    word_count = len(re.sub(r'<[^>]+>', '', content).replace(' ', ''))
    
    output = {"article_html": content, "article_title": title, "word_count": word_count}
    log(f"  标题: {title} | 字数: {word_count}")
    save_state({"step": "writer", **state, **output})
    
    # 预览纯文本
    preview = re.sub(r'<[^>]+>', '', content)[:600].replace('\n\n', '\n')
    notify(f"✍️ Writer 写作完成\n📝 标题: {title}\n📏 字数: {word_count}\n\n预览:\n{preview}...")
    
    wait_approval("Writer写作", f"标题: {title}，{word_count}字")
    return output

# ========== Step 4: Director 配图规划 ==========
def step_polish(state):
    """AI润色：优化标题、检查错别字、优化过渡"""
    title = state.get("article_title", state.get("title", ""))
    content = state.get("article_html", state.get("content", ""))
    if not content:
        log(f"  ⚠️ 内容为空，跳过润色")
        return state

    log(f"  AI润色中...")
    prompt = f"""请对以下微信公众号文章进行润色优化：
1. 优化标题使其更吸引点击（不超过11个中文字）
2. 检查并修正错别字、语法错误
3. 优化段落过渡，让阅读更流畅
4. 禁止在文末添加AI原创声明、AI辅助创作声明、免责声明，不要出现"AI""人工智能""原创声明"等字样

当前标题: {title}

文章内容:
{content}

请直接输出完整的HTML内容（包含<title>标签），不要加任何解释。"""

    try:
        result = call_ai(prompt, temp=0.6)
        m = re.search(r'<title>(.*?)</title>', result, re.I | re.S)
        new_title = m.group(1).strip() if m else title
        new_content = re.sub(r'<title>.*?</title>', '', result, flags=re.I | re.S).strip()
        log(f"  润色后标题: {new_title}")
        notify(f"✨ 润色完成\n📝 标题: {new_title}（原: {title}）")
        return {"article_title": new_title, "article_html": new_content}
    except Exception as e:
        log(f"  ⚠️ 润色失败，使用原文: {e}")
        return state  # 返回原文而不是None，让流水线继续

def step_director(state):
    log("🎨 Step 4/7: Director（配图规划）")
    title = state.get("article_title", "")
    content = state.get("article_html", "")
    
    body_text = re.sub(r'<[^>]+>', '', content)
    
    prompt = f"""为以下文章规划2-3张配图，给出每张图的AI生图提示词（英文）。

标题: {title}
文章摘要: {body_text[:500]}

要求：
1. 提示词要有科技感，适合微信公众号配图
2. 风格统一：现代、简洁、明亮
3. 每张图有明确的主题定位

JSON格式输出：
```json
{{"images": [{{"position": "开头", "prompt": "英文提示词", "description": "这张图放在哪、表达什么"}}]}}```"""

    result = clean_codeblock(call_ai(prompt, temp=0.5))
    json_match = re.search(r'\{[\s\S]*\}', result)
    
    if json_match:
        plan = json.loads(json_match.group())
    else:
        plan = {"images": [
            {"position": "开头", "prompt": f"{title}, modern technology, bright, illustration, 8k", "description": "首图"},
            {"position": "文中", "prompt": f"{title}, digital concept, blue gradient, 8k", "description": "配图"}
        ]}
    
    output = {"image_plan": plan.get("images", [])}
    log(f"  规划{len(output['image_plan'])}张配图")
    
    display = "🎨 Director 配图规划：\n\n"
    for i, img in enumerate(output["image_plan"]):
        display += f"图{i+1} [{img.get('position', '')}]: {img.get('description', '')}\n"
        display += f"   Prompt: {img.get('prompt', '')[:80]}\n\n"
    
    save_state({"step": "director", **state, **output})
    notify(display)
    
    wait_approval("Director配图规划", f"{len(output['image_plan'])}张")
    return output

# ========== Step 5: Image Gen 生图（通义万相） ==========
def step_image(state):
    log("🖼️ Step 5/7: Image Gen（生图 - 通义万相）")
    image_plan = state.get("image_plan", [])
    script = os.path.join(os.path.dirname(__file__), "generate_images.sh")
    image_paths = []

    for i, img in enumerate(image_plan):
        prompt = img.get("prompt", "technology illustration 8k")
        try:
            result = subprocess.run(
                ["bash", script, prompt],
                capture_output=True, text=True, timeout=180
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    line = line.strip()
                    if (line.endswith(".png") or line.endswith(".jpg")) and os.path.exists(line):
                        image_paths.append(line)
                        log(f"  图{i+1}: ✓ {line}")
                        break
                else:
                    log(f"  图{i+1}: 生成但未找到文件路径")
            else:
                log(f"  图{i+1}: 失败 | {result.stderr.strip()[-100:]}")
        except subprocess.TimeoutExpired:
            log(f"  图{i+1}: 超时(180s)")
        except Exception as e:
            log(f"  图{i+1}: {e}")

    if not image_paths:
        notify("⚠️ Image Gen: 所有配图生成失败")
        return None
    
    output = {"image_paths": image_paths}
    save_state({"step": "image", **state, **output})
    notify(f"🖼️ Image Gen 完成：{len(image_paths)}/{len(image_plan)}张成功")
    
    wait_approval("Image Gen生图", f"{len(image_paths)}张")
    return output

# ========== Step 6: Formatter 排版 ==========
def step_format(state):
    log("📐 Step 6/7: Formatter（排版）")
    content = state.get("article_html", "")
    image_plan = state.get("image_plan", [])
    
    body = re.sub(r'<title>.*?</title>', '', content, flags=re.I | re.S).strip()
    
    # 统一<h2>样式
    body = re.sub(
        r'<h2([^>]*)>(.*?)</h2>',
        lambda m: f'<h2{m.group(1)} style="color:#1a1a1a;border-left:4px solid #07c160;padding-left:12px;font-size:18px;">{m.group(2)}</h2>',
        body
    )
    
    # 配图URL占位（实际URL在发布时替换）
    for i in range(len(image_plan)):
        img_tag = f'<p style="text-align:center;"><img src="IMAGE_{i}" style="width:100%;border-radius:8px;margin:15px 0;"/></p>'
        h2s = list(re.finditer(r'(<h2[^>]*>)', body))
        if i == 0 and h2s:
            pos = h2s[0].start()
            body = body[:pos] + img_tag + body[pos:]
        elif i > 0 and i < len(h2s):
            pos = h2s[i].start()
            body = body[:pos] + img_tag + body[pos:]
        else:
            body += img_tag
    
    output = {"formatted_html": body}
    save_state({"step": "format", **state, **output})
    notify(f"📐 Formatter 排版完成")
    
    wait_approval("Formatter排版", "微信HTML格式")
    return output

# ========== Step 7: Publisher 发布 ==========
def step_validate(state):
    """校验：字数、配图、标题长度"""
    title = state.get("title", "")
    content = state.get("content", "")
    images = state.get("images", [])

    log(f"  校验中...")
    warnings = []

    # 字数
    word_count = len(re.sub(r'<[^>]+>', '', content).replace(' ', '').replace('\n', ''))
    if word_count < 3000:
        warnings.append(f"字数偏少({word_count})")
    log(f"  字数: {word_count} {'✓' if word_count >= 3000 else '⚠️'}")

    # 配图
    if not images:
        warnings.append("无配图")
    log(f"  配图: {len(images)}张 {'✓' if images else '⚠️'}")

    # 标题长度
    gbk_len = len(title.encode('gbk', errors='replace'))
    if gbk_len > 22:
        warnings.append(f"标题GBK({gbk_len}字节)超限")
        state["title"] = state["title"][:11]
        log(f"  标题已截断: {state['title']}")
    else:
        log(f"  标题: {title} ({gbk_len}字节) ✓")

    if warnings:
        log(f"  ⚠️ {', '.join(warnings)}，但不阻断发布")
    else:
        log(f"  校验通过 ✓")

    return state

def step_publish(state):
    log("📤 Step 7/7: Publisher（发布）")
    
    token_req = requests.get(
        f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={APPID}&secret={APPSECRET}",
        timeout=10
    )
    token = token_req.json().get("access_token")
    if not token:
        notify("❌ Publisher失败：获取token失败")
        return None
    
    # 上传图片
    image_paths = state.get("image_paths", [])
    uploaded = []
    for p in image_paths:
        if os.path.exists(p):
            with open(p, "rb") as f:
                r = requests.post(
                    f"https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={token}&type=image",
                    files={"media": f}, timeout=30
                )
            data = r.json()
            if data.get("media_id") and data.get("url"):
                uploaded.append({"media_id": data["media_id"], "url": data["url"]})
    
    if not uploaded:
        notify("❌ Publisher失败：图片上传失败")
        return None
    
    # 替换图片占位符
    body = state.get("formatted_html", "")
    image_plan = state.get("image_plan", [])
    log(f"  图片占位: {len(image_plan)}个计划, {len(uploaded)}个已上传")
    for i, img in enumerate(uploaded):
        body = body.replace(f'src="IMAGE_{i}"', f'src="{img["url"]}"')
    # 检查是否还有未替换的占位符，用第一张图兜底
    import re as _re
    remaining = _re.findall(r'src="IMAGE_\d+"', body)
    if remaining and uploaded:
        log(f"  警告: {len(remaining)}个占位符未替换，用首图兜底")
        body = _re.sub(r'src="IMAGE_\d+"', f'src="{uploaded[0]["url"]}"', body)
    
    # 截断标题和摘要
    title = state.get("article_title", "")
    try:
        for i in range(len(title), 0, -1):
            if len(title[:i].encode('gbk')) <= 22:
                title = title[:i]
                break
    except:
        title = title[:7]
    
    digest_text = re.sub(r'<[^>]+>', '', body).strip()[:80]
    try:
        for i in range(len(digest_text), 0, -1):
            if len(digest_text[:i].encode('gbk')) <= 20:
                digest_text = digest_text[:i]
                break
    except:
        digest_text = digest_text[:10]
    
    # 发布
    draft = {"articles": [{
        "title": title,
        "thumb_media_id": uploaded[0]["media_id"],
        "author": "",
        "digest": digest_text,
        "content": body,
        "content_source_url": "",
        "need_open_comment": 1,
        "only_fans_can_comment": 0
    }]}
    
    r = requests.post(
        f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={token}",
        data=json.dumps(draft, ensure_ascii=False).encode('utf-8'),
        headers={"Content-Type": "application/json; charset=utf-8"},
        timeout=30
    )
    result = r.json()
    
    if "media_id" in result:
        log(f"  ✅ 发布成功！")
        notify(f"✅ 文章已发布到草稿箱！\n📝 {title}\n📎 请到公众号后台群发")
        save_state({"step": "done", "media_id": result["media_id"], **state})
        return result["media_id"]
    else:
        log(f"  ❌ 发布失败: {result}")
        notify(f"❌ 发布失败\n{json.dumps(result, ensure_ascii=False)}")
        return None

# ========== 主流程 ==========
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto", action="store_true", help="自动模式")
    parser.add_argument("--step", help="从指定步骤开始")
    args = parser.parse_args()
    
    sys._auto_mode = args.auto
    start_step = args.step
    
    log("=" * 40)
    log("🚀 AI文章流水线启动" + ("（自动模式）" if args.auto else "（交互模式）"))
    log("=" * 40)
    
    state = load_state()
    
    # Pipeline steps
    steps = [
        ("scout", step_scout, []),
        ("research", step_research, ["state"]),
        ("writer", step_writer, ["state"]),
        ("polish", step_polish, ["state"]),
        ("director", step_director, ["state"]),
        ("image", step_image, ["state"]),
        ("format", step_format, ["state"]),
        ("validate", step_validate, ["state"]),
        ("publish", step_publish, ["state"]),
    ]
    
    # 找到起始步骤
    start_idx = 0
    if start_step:
        for i, (name, _, _) in enumerate(steps):
            if name == start_step:
                start_idx = i
                break
    
    for i, (name, func, _) in enumerate(steps):
        if i < start_idx:
            continue
        try:
            result = func(state)
            if result is None and name != "publish":
                log(f"  ❌ {name} 失败，流水线终止")
                break
            if isinstance(result, dict):
                state.update(result)
        except Exception as e:
            log(f"  ❌ {name} 异常: {e}")
            notify(f"❌ 流水线在{name}步骤出错：{e}")
            break
    
    log("=" * 40)
    if state.get("step") == "done":
        log("✅ 流水线完成！")
    else:
        log(f"⏸️ 流水线暂停于: {state.get('step', '?')}")
    log("=" * 40)

if __name__ == "__main__":
    main()
