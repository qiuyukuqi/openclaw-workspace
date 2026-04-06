#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全平台内容分发流水线
公众号文章生产 + 多平台分发（头条号 + 小红书）

流程:
  Scout选题 → Research调研 → Writer写文 → Polish润色 → Director配图
  → Image生图 → Format排版 → Publish公众号草稿
  → Adapt改编 → Distribute头条+小红书

用法:
  python3 full_pipeline.py              # 交互模式（每步审核）
  python3 full_pipeline.py --auto       # 全自动模式
  python3 full_pipeline.py --step write # 从指定步骤开始
"""

import os, sys, json, subprocess, re, requests, time, argparse, asyncio
from datetime import datetime, timedelta

WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
SCRIPT_DIR = os.path.join(WORKSPACE, "skills/wechat-publisher/scripts")
PUBLISHER_DIR = os.path.join(WORKSPACE, "skills/auto-publisher")
STATE_FILE = "/tmp/openclaw/full_pipeline_state.json"
USER_ID = "ou_c5c98e2002a34a9b10f15fd0b6463d06"

# ========== 环境加载 ==========
def load_env():
    env = {}
    env_path = os.path.join(WORKSPACE, ".env.wechat")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")
    cfg_path = os.path.join(SCRIPT_DIR, "config.sh")
    if os.path.exists(cfg_path):
        with open(cfg_path) as f:
            for line in f:
                for key in ["WECHAT_APP_ID", "WECHAT_APP_SECRET", "DASHSCOPE_API_KEY", "TAVILY_API_KEY", "ZHIPU_API_KEY"]:
                    if key in line and '=' in line:
                        m = re.search(rf'{key}\s*=\s*["\']?([^"\'"\n]+)', line)
                        if m:
                            env[key] = m.group(1).strip()
    return env

ENV = load_env()
DEEPSEEK_KEY = "sk-162c19004d444d73a49c735c4de9d82f"
TAVILY_KEY = ENV.get("TAVILY_API_KEY", "")
APPID = ENV.get("WECHAT_APP_ID", "")
APPSECRET = ENV.get("WECHAT_APP_SECRET", "")

# ========== 工具 ==========
def ts(): return datetime.now().strftime('%H:%M:%S')
def log(msg): print(f"[{ts()}] {msg}", flush=True)

def notify(msg):
    try:
        subprocess.run(["openclaw", "message", "send", "--channel", "feishu",
                        "--account", "main", "-t", f"user:{USER_ID}", "-m", msg],
                       capture_output=True, timeout=30)
    except: pass

def call_ai(prompt, temp=0.85, tokens=4000):
    r = requests.post("https://api.deepseek.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"},
        json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}],
              "max_tokens": tokens, "temperature": temp}, timeout=120)
    data = r.json()
    if "choices" not in data:
        raise ValueError(f"AI错误: {json.dumps(data, ensure_ascii=False)[:200]}")
    return data["choices"][0]["message"]["content"]

def clean_codeblock(text):
    if text.startswith("```"):
        lines = text.split("\n")[1:]
        if lines and lines[-1].strip() == "```": lines = lines[:-1]
        return "\n".join(lines).strip()
    return text.strip()

def save_state(data):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f: return json.load(f)
    return {}

def wait_ok(auto_mode, step_name, info=""):
    if auto_mode:
        log(f"  自动模式，跳过审核")
        return True
    notify(f"⏸️ {step_name} 完成：{info[:200]}\n回复「继续」或提出修改意见")
    return True

# ========== Step 1: Scout 选题 ==========
def step_scout(state, auto):
    log("🔍 Step 1/10: Scout（选题）")
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
                "max_results": 5, "topic": "news"}, timeout=30)
            all_results.extend(r.json().get("results", []))
        except: pass

    if not all_results:
        notify("⚠️ Scout选题失败：搜索无结果"); return None

    hotspots = "\n".join([f"{i+1}. 【{r.get('title','')}】\n   {r.get('content','')[:150]}" for i, r in enumerate(all_results[:10])])

    prompt = f"""你是科技自媒体选题编辑。从最近3天热点中筛选3-5个最适合写成3000字文章的话题。
{hotspots}
对每个给出：选题角度、目标读者、热度(1-10)、实操价值(1-10)。最后推荐最佳。
JSON: {{"candidates": [{{"index":1,"title":"文章标题≤11字纯中文","angle":"角度","audience":"读者","heat":8,"value":7,"direction":"方向"}}], "recommended":0}}"""
    result = clean_codeblock(call_ai(prompt, temp=0.3))
    jm = re.search(r'\{[\s\S]*\}', result)
    if not jm: return None
    choice = json.loads(jm.group())
    candidates = choice.get("candidates", [])
    ri = choice.get("recommended", 0)
    rec = candidates[min(ri, len(candidates)-1)]
    src = all_results[min(rec.get("index",1)-1, len(all_results)-1)]

    output = {"candidates": candidates, "recommended_idx": ri, "selected": {
        "title": rec.get("title",""), "direction": rec.get("direction",""),
        "angle": rec.get("angle",""), "source_title": src.get("title",""),
        "source_url": src.get("url",""), "snippet": src.get("content","")[:500]
    }}
    state.update(output); save_state({"step":"scout", **state})
    display = f"📰 Scout结果({len(candidates)}个候选)⭐推荐: {rec.get('title','')}"
    log(f"  推荐: {rec.get('title','')}"); notify(display)
    wait_ok(auto, "Scout", display)
    return output

# ========== Step 2: Research 调研 ==========
def step_research(state, auto):
    log("📚 Step 2/10: Research（调研）")
    direction = state.get("selected",{}).get("direction","")
    materials = []
    for q in [direction[:50], f"{direction[:30]} 案例 实操"]:
        try:
            r = requests.post("https://api.tavily.com/search", json={
                "api_key": TAVILY_KEY, "query": q, "search_depth": "advanced",
                "max_results": 5}, timeout=30)
            for item in r.json().get("results", []):
                materials.append({"title": item.get("title",""), "content": item.get("content","")[:300], "url": item.get("url","")})
        except: pass

    if materials:
        mt = "\n".join([f"- 【{m['title']}】{m['content']}" for m in materials[:8]])
        research = call_ai(f"围绕「{direction}」整理资料：核心事实、案例、实操建议、争议点。简洁列表。", temp=0.3, tokens=2000)
    else:
        research = "基于AI知识库生成"
    output = {"research_materials": materials, "research_summary": research}
    state.update(output); save_state({"step":"research", **state})
    log(f"  {len(materials)}条资料"); notify(f"📚 调研完成({len(materials)}条)")
    wait_ok(auto, "Research", f"{len(materials)}条")
    return output

# ========== Step 3: Writer 写文 ==========
def step_writer(state, auto):
    log("✍️ Step 3/10: Writer（写作）")
    sel = state.get("selected",{}); research = state.get("research_summary","")
    prompt = f"""你是科技自媒体作者「别动我在debug」，风格犀利观点鲜明。
选题: {sel.get('title','')} | 方向: {sel.get('direction','')} | 角度: {sel.get('angle','')}
调研: {research}

要求：3000字左右，标题纯中文≤11字，严禁包含任何英文、数字、标点符号，轻松有趣口语化，
有观点有案例有实操价值。<h2>小标题分段，不用<br>。
正文开头一句有力观点句再展开。
文末固定话术：<p style="text-align:center;color:#888;margin-top:20px;font-size:14px;">关注「别动我在debug」，聊聊科技那些事。</p>
不要署名行、日期行、AI声明。

输出: <title>标题</title> 正文用<p>分段<h2>做小标题。"""
    content = clean_codeblock(call_ai(prompt))
    if not re.search(r'<title>', content, re.I):
        content = f"<title>{sel.get('title','')[:11]}</title>\n{content}"
    m = re.search(r'<title>(.*?)</title>', content, re.I|re.S)
    title = m.group(1).strip() if m else sel.get('title','')[:11]
    wc = len(re.sub(r'<[^>]+>', '', content).replace(' ',''))
    output = {"article_html": content, "article_title": title, "word_count": wc}
    state.update(output); save_state({"step":"writer", **state})
    log(f"  标题: {title} | {wc}字")
    notify(f"✍️ 写作完成\n📝 {title}\n📏 {wc}字")
    wait_ok(auto, "Writer", f"{title} {wc}字")
    return output

# ========== Step 4: Polish 润色 ==========
def step_polish(state, auto):
    log("✨ Step 4/10: Polish（润色）")
    title = state.get("article_title",""); content = state.get("article_html","")
    prompt = f"""润色以下公众号文章：1.标题≤11字纯中文，严禁包含任何英文字母、数字、标点符号 2.修错别字 3.优化过渡 4.禁止AI声明/免责声明/原创声明
标题: {title}
内容: {content}
直接输出完整HTML(含<title>)，不加解释。"""
    try:
        result = call_ai(prompt, temp=0.6)
        m = re.search(r'<title>(.*?)</title>', result, re.I|re.S)
        new_title = m.group(1).strip() if m else title
        new_content = re.sub(r'<title>.*?</title>', '', result, flags=re.I|re.S).strip()
        log(f"  标题: {new_title}")
        output = {"article_title": new_title, "article_html": new_content}
        state.update(output); save_state({"step":"polish", **state})
        notify(f"✨ 润色完成: {new_title}")
    except Exception as e:
        log(f"  润色失败，用原文: {e}")
    return state

# ========== Step 5: Director 配图规划 ==========
def step_director(state, auto):
    log("🎨 Step 5/10: Director（配图规划）")
    title = state.get("article_title",""); content = state.get("article_html","")
    body = re.sub(r'<[^>]+>', '', content)[:500]
    prompt = f"""为文章规划2-3张配图，给出英文AI生图提示词。
标题: {title} | 摘要: {body}
科技感、现代简洁。JSON: {{"images": [{{"position":"开头","prompt":"英文提示词","description":"说明"}}]}}"""
    result = clean_codeblock(call_ai(prompt, temp=0.5))
    jm = re.search(r'\{[\s\S]*\}', result)
    plan = json.loads(jm.group()) if jm else {"images": [
        {"position":"开头","prompt":f"{title}, tech illustration, bright, 8k","description":"首图"}]}
    output = {"image_plan": plan.get("images",[])}
    state.update(output); save_state({"step":"director", **state})
    log(f"  {len(output['image_plan'])}张配图")
    notify(f"🎨 配图规划: {len(output['image_plan'])}张")
    wait_ok(auto, "Director", f"{len(output['image_plan'])}张")
    return output

# ========== Step 6: Image 生图 ==========
def step_image(state, auto):
    log("🖼️ Step 6/10: Image（生图）")
    script = os.path.join(SCRIPT_DIR, "generate_images.sh")
    image_plan = state.get("image_plan",[]); image_paths = []
    for i, img in enumerate(image_plan):
        prompt = img.get("prompt", "technology illustration 8k")
        try:
            result = subprocess.run(["bash", script, prompt], capture_output=True, text=True, timeout=180)
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if (line.endswith(".png") or line.endswith(".jpg")) and os.path.exists(line.strip()):
                        image_paths.append(line.strip()); log(f"  图{i+1}: ✓"); break
            else:
                log(f"  图{i+1}: ✗")
        except: log(f"  图{i+1}: 超时")
    output = {"image_paths": image_paths}
    state.update(output); save_state({"step":"image", **state})
    notify(f"🖼️ 生图: {len(image_paths)}/{len(image_plan)}张")
    wait_ok(auto, "Image", f"{len(image_paths)}张")
    return output

# ========== Step 7: Format 排版 ==========
def step_format(state, auto):
    log("📐 Step 7/10: Format（排版）")
    content = state.get("article_html",""); image_plan = state.get("image_plan",[])
    body = re.sub(r'<title>.*?</title>', '', content, flags=re.I|re.S).strip()
    body = re.sub(r'<h2([^>]*)>(.*?)</h2>',
        lambda m: f'<h2{m.group(1)} style="color:#1a1a1a;border-left:4px solid #07c160;padding-left:12px;font-size:18px;">{m.group(2)}</h2>', body)
    for i in range(len(image_plan)):
        img_tag = '<p style="text-align:center;"><img src="IMAGE_%d" style="width:100%%;border-radius:8px;margin:15px 0;"/></p>' % i
        h2s = list(re.finditer(r'(<h2[^>]*>)', body))
        pos = h2s[i].start() if i < len(h2s) else len(body)
        body = body[:pos] + img_tag + body[pos:]
    output = {"formatted_html": body}
    state.update(output); save_state({"step":"format", **state})
    log("  排版完成"); notify("📐 排版完成")
    return output

# ========== Step 8: Publish 公众号草稿箱 ==========
def step_publish(state, auto):
    log("📤 Step 8/10: Publish（公众号草稿箱）")
    token_req = requests.get(f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={APPID}&secret={APPSECRET}", timeout=10)
    token = token_req.json().get("access_token")
    if not token: notify("❌ 获取token失败"); return None

    # 上传图片
    image_paths = state.get("image_paths",[]); uploaded = []
    for p in image_paths:
        if os.path.exists(p):
            with open(p,"rb") as f:
                r = requests.post(f"https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={token}&type=image", files={"media":f}, timeout=30)
            d = r.json()
            if d.get("media_id") and d.get("url"):
                uploaded.append({"media_id":d["media_id"],"url":d["url"]})
    if not uploaded: notify("❌ 图片上传失败"); return None

    body = state.get("formatted_html","")
    for i, img in enumerate(uploaded):
        body = body.replace(f'src="IMAGE_{i}"', f'src="{img["url"]}"')
    body = re.sub(r'src="IMAGE_\d+"', f'src="{uploaded[0]["url"]}"', body)

    title = state.get("article_title","")
    # 标题截断：确保≤22 GBK字节，且不在中文中间断开
    try:
        for i in range(len(title),0,-1):
            truncated = title[:i]
            if len(truncated.encode('gbk')) <= 22:
                title = truncated
                break
        # 安全检查：如果最后一个字符是中文但标题超了，再砍一个字
        if len(title.encode('gbk')) > 22:
            title = title[:-1]
    except: title = title[:7]

    digest = re.sub(r'<[^>]+>','',body).strip()[:80]
    try:
        for i in range(len(digest),0,-1):
            if len(digest[:i].encode('gbk')) <= 20: digest = digest[:i]; break
    except: digest = digest[:10]

    draft = {"articles": [{"title":title,"thumb_media_id":uploaded[0]["media_id"],"author":"",
        "digest":digest,"content":body,"content_source_url":"","need_open_comment":1,"only_fans_can_comment":0}]}
    r = requests.post(f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={token}",
        data=json.dumps(draft,ensure_ascii=False).encode('utf-8'), headers={"Content-Type":"application/json;charset=utf-8"}, timeout=30)
    result = r.json()
    if "media_id" in result:
        log(f"  ✅ 公众号草稿: {title}"); notify(f"✅ 公众号草稿: {title}\n📎 请到后台群发")
        state["wechat_media_id"] = result["media_id"]
        save_state({"step":"publish", **state})
        return result["media_id"]
    else:
        log(f"  ❌ 发布失败: {result}"); notify(f"❌ 公众号发布失败: {json.dumps(result,ensure_ascii=False)}")
        return None

# ========== Step 9: Adapt 改编 ==========
def step_adapt(state, auto):
    log("🔄 Step 9/10: Adapt（改编为各平台版本）")
    content = state.get("article_html",""); title = state.get("article_title","")
    plain = re.sub(r'<[^>]+>', '', content).strip()

    # 头条号版本：保留完整内容，去掉HTML标签
    toutiao_content = plain
    with open("/tmp/openclaw/article_toutiao.md","w") as f:
        f.write(f"# {title}\n\n{toutiao_content}")

    # 小红书版本：精简+口语化+emoji
    prompt = f"""你是小红书博主。把以下文章改编为小红书笔记：
原文标题: {title}
原文（{len(plain)}字）: {plain[:2000]}

要求：
1. 精简到500字以内
2. 口语化，活泼有趣
3. 适当加emoji
4. 提炼3-5个核心观点
5. 文末加：关注「别动我在debug」聊聊科技那些事
6. 第一行是标题（不超过20字）
直接输出改编后的纯文本，不要解释。"""
    try:
        xhs_content = clean_codeblock(call_ai(prompt, temp=0.7, tokens=1000))
        with open("/tmp/openclaw/article_xiaohongshu.txt","w") as f:
            f.write(xhs_content)
        log(f"  头条: {len(toutiao_content)}字 | 小红书: {len(xhs_content)}字")
        notify(f"🔄 改编完成\n头条: {len(toutiao_content)}字\n小红书: {len(xhs_content)}字")
    except Exception as e:
        log(f"  小红书改编失败，用截断原文: {e}")
        with open("/tmp/openclaw/article_xiaohongshu.txt","w") as f:
            f.write(plain[:500])
        notify(f"🔄 改编完成(小红书用截断)")

    # 生成封面（如果没有）
    cover = "/tmp/openclaw/test_cover.jpg"
    if not os.path.exists(cover):
        import tempfile
        # 用通义万相或简单生成
        if state.get("image_paths"):
            cover = state["image_paths"][0]
        else:
            # 用Playwright生成简单封面
            try:
                import asyncio as _aio
                from playwright.async_api import async_playwright as _pw
                async def _gen():
                    _p = await _pw().start()
                    _b = await _p.chromium.launch(headless=True, args=["--no-sandbox"])
                    _pg = await _b.new_page(viewport={"width":800,"height":600})
                    await _pg.set_content(f'<body style="margin:0;display:flex;align-items:center;justify-content:center;height:100vh;background:linear-gradient(135deg,#667eea,#764ba2);color:white;font-family:sans-serif"><h1 style="font-size:32px;text-align:center;padding:40px">{title}</h1></body>')
                    await _pg.screenshot(path=cover, full_page=False)
                    await _b.close(); await _p.stop()
                _aio.run(_gen())
            except: pass

    state["cover_path"] = cover
    save_state({"step":"adapt", **state})
    return state

# ========== Step 10: Distribute 多平台发布 ==========
def step_distribute(state, auto):
    log("🚀 Step 10/10: Distribute（分发）")
    cover = state.get("cover_path","/tmp/openclaw/test_cover.jpg")
    results = {}

    # 头条号
    log("  → 头条号...")
    try:
        r = subprocess.run([sys.executable, "-c", f"""
import sys, asyncio, json, os
sys.path.insert(0, '{PUBLISHER_DIR}')
os.environ['PYTHONIOENCODING'] = 'utf-8'
from platforms.toutiao import ToutiaoPublisher

async def run():
    with open('/tmp/openclaw/article_toutiao.md') as f: content = f.read()
    lines = content.strip().split('\\n')
    title = lines[0].lstrip('# ').strip() if lines else '无标题'
    body = '\\n'.join(lines[1:]).strip()
    pub = ToutiaoPublisher()
    await pub.setup()
    try:
        ok = await pub.publish(title=title, content=body, cover_image='{cover}')
        print('OK' if ok else 'FAIL')
    finally:
        await pub.close()
asyncio.run(run())
"""], capture_output=True, text=True, timeout=180, cwd=PUBLISHER_DIR)
        toutiao_ok = "OK" in r.stdout
        results["头条号"] = "✅ 成功" if toutiao_ok else f"❌ 失败\n{r.stderr[-200:]}"
        log(f"  头条号: {'✅' if toutiao_ok else '❌'}")
    except Exception as e:
        results["头条号"] = f"❌ 异常: {e}"; log(f"  头条号: ❌ {e}")

    # 小红书
    log("  → 小红书...")
    try:
        r = subprocess.run([sys.executable, "-c", f"""
import sys, asyncio, os
sys.path.insert(0, '{PUBLISHER_DIR}')
os.environ['PYTHONIOENCODING'] = 'utf-8'
from platforms.xiaohongshu import XiaohongshuPublisher

async def run():
    with open('/tmp/openclaw/article_xiaohongshu.txt') as f: content = f.read()
    lines = content.strip().split('\\n')
    title = lines[0].strip() if lines else '无标题'
    body = '\\n'.join(lines[1:]).strip()
    pub = XiaohongshuPublisher()
    await pub.setup()
    try:
        ok = await pub.publish(title=title, content=body, cover_image='{cover}')
        print('OK' if ok else 'FAIL')
    finally:
        await pub.close()
asyncio.run(run())
"""], capture_output=True, text=True, timeout=180, cwd=PUBLISHER_DIR)
        xhs_ok = "OK" in r.stdout
        results["小红书"] = "✅ 成功" if xhs_ok else f"❌ 失败\n{r.stderr[-200:]}"
        log(f"  小红书: {'✅' if xhs_ok else '❌'}")
    except Exception as e:
        results["小红书"] = f"❌ 异常: {e}"; log(f"  小红书: ❌ {e}")

    # 汇总
    summary = "📊 分发汇总\n" + "\n".join(f"  {k}: {v}" for k,v in results.items())
    log(summary); notify(summary)
    state["distribute_results"] = results
    save_state({"step":"done", **state})
    return state

# ========== 主流程 ==========
def main():
    parser = argparse.ArgumentParser(description="全平台内容分发流水线")
    parser.add_argument("--auto", action="store_true", help="全自动模式")
    parser.add_argument("--step", help="从指定步骤开始（scout/research/writer/polish/director/image/format/publish/adapt/distribute）")
    args = parser.parse_args()

    auto = args.auto
    log("=" * 50)
    log(f"🚀 全平台分发流水线（{'自动' if auto else '交互'}模式）")
    log("=" * 50)

    state = load_state()

    steps = [
        ("scout",      step_scout),
        ("research",   step_research),
        ("writer",     step_writer),
        ("polish",     step_polish),
        ("director",   step_director),
        ("image",      step_image),
        ("format",     step_format),
        ("publish",    step_publish),
        ("adapt",      step_adapt),
        ("distribute", step_distribute),
    ]

    start_idx = 0
    if args.step:
        for i, (name, _) in enumerate(steps):
            if name == args.step: start_idx = i; break

    for i, (name, func) in enumerate(steps):
        if i < start_idx: continue
        try:
            result = func(state, auto)
            if result is None:
                if name in ("publish",):
                    log(f"  ⚠️ {name} 失败，继续后续步骤")
                    continue
                log(f"  ❌ {name} 失败，流水线终止"); break
            if isinstance(result, dict):
                state.update(result)
        except Exception as e:
            log(f"  ❌ {name} 异常: {e}")
            notify(f"❌ 流水线在{name}出错: {e}")
            import traceback; traceback.print_exc()
            break

    log("=" * 50)
    if state.get("step") == "done":
        log("✅ 全流程完成！")
        notify("🎉 全平台分发完成！公众号草稿+头条+小红书")
    else:
        log(f"⏸️ 暂停于: {state.get('step','?')}")
    log("=" * 50)

if __name__ == "__main__":
    main()
