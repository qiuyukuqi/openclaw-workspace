#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信公众号全自动发布脚本（Python版）
流程：AI选题 → AI写文 → AI润色 → AI配图 → 排版 → 校验 → 发布草稿箱
定时：crontab 每天 8:30 触发
"""

import os, sys, json, subprocess, re, requests, time, random
from datetime import datetime

# ========== 配置 ==========
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.expanduser("~/.openclaw/workspace")

def load_env(path):
    env = {}
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")
    return env

env = load_env(os.path.join(WORKSPACE, ".env.wechat"))

# 从bash config.sh补充读取
for cfg_key, aliases in [
    ("DASHSCOPE_API_KEY", ["DASHSCOPE_API_KEY"]),
    ("TAVILY_API_KEY", ["TAVILY_API_KEY"]),
    ("WECHAT_APP_ID", ["WECHAT_APP_ID", "APPID"]),
    ("WECHAT_APP_SECRET", ["WECHAT_APP_SECRET", "APPSECRET"]),
]:
    if not env.get(cfg_key):
        try:
            with open(os.path.join(WORKSPACE, "skills/wechat-publisher/scripts/config.sh")) as f:
                for line in f:
                    for alias in aliases:
                        if alias in line and '=' in line:
                            m = re.search(rf'{alias}\s*=\s*["\']?([^"\'"\n]+)', line)
                            if m:
                                env[cfg_key] = m.group(1).strip()
                                break
                    if env.get(cfg_key):
                        break
        except:
            pass

APPID = env.get("WECHAT_APP_ID", "")
APPSECRET = env.get("WECHAT_APP_SECRET", "")
DASHSCOPE_API_KEY = env.get("DASHSCOPE_API_KEY", "")
CHANNEL = "feishu"
USER_ID = "ou_c5c98e2002a34a9b10f15fd0b6463d06"

WORK_DIR = f"/tmp/openclaw/wechat-publisher/data/auto_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
os.makedirs(WORK_DIR, exist_ok=True)

# ========== 主题库 ==========
TOPIC_LIBRARY = {
    "数码产品": [
        "手机/电脑/智能设备新品发布与评测",
        "折叠屏手机最新进展",
        "笔记本电脑选购指南",
        "智能手表/手环新品资讯",
        "平板电脑市场竞争格局",
        "无线耳机/音箱产品对比",
        "智能家居设备体验分享",
        "摄影器材与手机影像对比",
        "游戏主机与PC硬件资讯",
        "新能源汽车智能座舱体验"
    ],
    "IT技术": [
        "前端框架最新动态（React/Vue/Svelte）",
        "AI编程助手使用技巧与效率提升",
        "Python/Go/Rust语言新特性",
        "后端架构设计与微服务实践",
        "数据库优化与新技术对比",
        "开源项目推荐与使用体验",
        "Git工作流与团队协作最佳实践",
        "Docker/K8s容器化部署技巧",
        "低代码/无代码平台评测",
        "WebAssembly与边缘计算趋势"
    ],
    "运维知识": [
        "Linux服务器管理实战技巧",
        "Nginx/HAProxy负载均衡配置",
        "CI/CD流水线搭建与优化",
        "监控告警系统选型与实践",
        "云服务器成本优化方案",
        "Kubernetes集群运维经验",
        "日志分析与故障排查方法论",
        "网络安全与防火墙配置",
        "自动化运维脚本编写",
        "高可用架构设计与容灾方案"
    ]
}

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def notify_feishu(message):
    try:
        subprocess.run(
            ["openclaw", "message", "send", "--channel", CHANNEL,
             "-t", f"user:{USER_ID}", "-m", message],
            capture_output=True, timeout=30
        )
    except:
        pass

def call_ai(prompt, temperature=0.85, max_tokens=4000):
    """调用通义千问API"""
    r = requests.post(
        "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        headers={"Authorization": f"Bearer {DASHSCOPE_API_KEY}", "Content-Type": "application/json"},
        json={"model": "qwen-plus", "messages": [{"role": "user", "content": prompt}],
              "max_tokens": max_tokens, "temperature": temperature},
        timeout=120
    )
    data = r.json()
    if "choices" not in data:
        raise ValueError(f"AI返回异常: {json.dumps(data, ensure_ascii=False)[:300]}")
    return data["choices"][0]["message"]["content"]

def clean_html(text):
    """清理markdown代码块包裹"""
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()

def get_access_token():
    r = requests.get(
        f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={APPID}&secret={APPSECRET}",
        timeout=10
    )
    return r.json()["access_token"]

def upload_image(token, path):
    with open(path, "rb") as f:
        r = requests.post(
            f"https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={token}&type=image",
            files={"media": f}, timeout=30
        )
    data = r.json()
    return data.get("media_id"), data.get("url")

def truncate_gbk(text, max_bytes):
    """截断文本使其GBK编码不超过max_bytes字节"""
    try:
        for i in range(len(text), 0, -1):
            if len(text[:i].encode('gbk')) <= max_bytes:
                return text[:i]
    except:
        pass
    return text[:max_bytes // 2]

# ========== Step 1: AI选题 ==========
def select_topic():
    log("[1/7] AI选题（Tavily搜索最近3天热点）")
    
    # 从技术/数码媒体搜索最近3天热点
    date_from = (datetime.now() - __import__('datetime').timedelta(days=3)).strftime('%Y-%m-%d')
    
    queries = [
        "site:ithome.com OR site:36kr.com 最新科技新闻",
        "site:sspai.com OR site:v2ex.com 技术热点",
        f"科技数码 IT技术 运维 热点新闻 {date_from}"
    ]
    
    all_results = []
    for query in queries:
        try:
            r = requests.post("https://api.tavily.com/search", json={
                "api_key": env.get("TAVILY_API_KEY", TAVILY_API_KEY),
                "query": query,
                "search_depth": "advanced",
                "max_results": 5,
                "include_answer": False,
                "topic": "news"
            }, timeout=30)
            data = r.json()
            for item in data.get("results", []):
                item["_query"] = query
                all_results.append(item)
        except Exception as e:
            log(f"  搜索失败: {e}")
    
    if not all_results:
        log("  搜索无结果，回退到主题库")
        categories = list(TOPIC_LIBRARY.keys())
        category = categories[datetime.now().weekday() % len(categories)]
        topics = TOPIC_LIBRARY[category]
        week = datetime.now().isocalendar()[1]
        topic = topics[(week + datetime.now().weekday()) % len(topics)]
        return {"category": category, "direction": topic}
    
    # AI分析哪些适合写文章，选最有话题性的
    hotspots = "\n".join([
        f"{i+1}. 标题: {r.get('title', '')}\n   摘要: {r.get('content', '')[:200]}\n   来源: {r.get('url', '')}"
        for i, r in enumerate(all_results[:10])
    ])
    
    prompt = f"""以下是最近3天的科技/数码/IT技术新闻热点列表：

{hotspots}

请分析这些热点，选择最适合写成一篇3000字轻松风格科技文章的话题。选择标准：
1. 话题性强，读者感兴趣
2. 有足够的素材可以展开
3. 适合轻松有趣的写作风格

请严格按以下JSON格式输出（不要加其他文字）：
{{"selected_index": 编号, "topic_title": "拟定的文章标题（不超过11个中文字）", "direction": "具体写作方向描述", "category": "数码产品/IT技术/运维知识 之一"}}"""

    try:
        result = call_ai(prompt, temperature=0.3)
        # 提取JSON
        json_match = re.search(r'\{[^}]+\}', result, re.DOTALL)
        if json_match:
            choice = json.loads(json_match.group())
            idx = choice.get("selected_index", 1) - 1
            selected = all_results[min(idx, len(all_results)-1)]
            log(f"  AI选择: {choice.get('topic_title', '')}")
            log(f"  来源: {selected.get('url', '')[:80]}")
            return {
                "category": choice.get("category", "数码产品"),
                "direction": choice.get("direction", choice.get("topic_title", "")),
                "title": choice.get("topic_title", ""),
                "source": selected.get("title", ""),
                "source_url": selected.get("url", ""),
                "snippet": selected.get("content", "")[:500]
            }
    except Exception as e:
        log(f"  AI选题失败: {e}，取第一条")
    
    # 回退：取搜索结果第一条
    first = all_results[0]
    return {
        "category": "数码产品",
        "direction": first.get("title", ""),
        "source": first.get("url", ""),
        "snippet": first.get("content", "")[:500]
    }

# ========== Step 2: AI写文 ==========
def generate_article(topic):
    log("[2/7] AI写文（3000字，轻松风格）")
    today = datetime.now().strftime('%Y年%m月%d日')
    
    source_info = ""
    if topic.get("source"):
        source_info = f"\n参考素材标题: {topic['source']}\n参考素材摘要: {topic.get('snippet', '')}"
    
    prompt = f"""你是一位轻松有趣的科技自媒体作者，擅长把硬核科技话题写得通俗易懂、引人入胜。

写作方向: {topic['direction']}
分类: {topic['category']}
{source_info}

要求:
1. 写一篇3000字左右的原创文章
2. 标题不超过11个中文字，有趣但不标题党
3. 写作风格：轻松有趣，像和朋友聊天一样，适当用比喻和类比
4. 内容要有料：真实的产品信息、数据、案例
5. 段落分明，使用<h2>小标题
6. 文末给出实用建议或观点总结
7. 禁止使用"大家好""老朋友"等开场白，直接切入主题

内容质量要求（重要！）：
- 有观点：明确表达你的判断和立场，不要和稀泥
- 有案例：引用具体产品、真实事件、数据对比，不要泛泛而谈
- 有实操价值：给读者能用的建议、技巧或避坑指南，不是纯科普
- 有深度：不只说"是什么"，要说"为什么"和"意味着什么"

输出格式（严格遵守）：
1. 最前面放 <title>标题</title>
2. 直接开始正文，不要作者信息行
3. 使用<p>分段，<h2>做小标题
4. 文末加 <p style="text-align:center;color:#888;margin-top:20px;font-size:14px;">— END —</p>
5. 不需要<head><body>，不要markdown代码块包裹"""

    content = clean_html(call_ai(prompt))
    
    if not re.search(r'<title>', content, re.I):
        content = f"<title>{topic['direction'][:11]}</title>\n{content}"
    
    m = re.search(r'<title>(.*?)</title>', content, re.I | re.S)
    title = m.group(1).strip() if m else topic['direction'][:11]
    body_text = re.sub(r'<[^>]+>', '', content)
    word_count = len(body_text.replace('\n', '').replace(' ', ''))
    
    log(f"  标题: {title} | 字数: {word_count}")
    return content, title, word_count

# ========== Step 3: AI润色 ==========
def polish_article(content, title):
    log("[3/7] AI润色（优化标题、检查错别字）")
    
    prompt = f"""请对以下微信公众号文章进行润色优化：
1. 优化标题使其更吸引点击（不超过11个中文字）
2. 检查并修正错别字、语法错误
3. 优化段落过渡，让阅读更流畅
4. 保持轻松有趣的风格

当前标题: {title}

文章内容:
{content}

请直接输出完整的HTML内容（包含<title>标签），不要加任何解释。"""

    try:
        polished = clean_html(call_ai(prompt, temperature=0.6))
        m = re.search(r'<title>(.*?)</title>', polished, re.I | re.S)
        new_title = m.group(1).strip() if m else title
        log(f"  润色后标题: {new_title}")
        return polished, new_title
    except Exception as e:
        log(f"  WARNING: 润色失败，使用原文: {e}")
        return content, title

# ========== Step 4: AI配图 ==========
def generate_images(title):
    log("[4/7] AI配图（通义万相，2-3张）")
    image_paths = []
    prompts = [
        f"{title}, modern technology, clean design, bright colors, illustration style, 8k",
        f"{title}, digital concept art, blue gradient, futuristic, 8k",
        f"{title}, minimal flat design, infographic style, tech theme, 8k"
    ]
    script = os.path.join(WORKSPACE, "scripts/text2img.sh")
    
    for i, prompt in enumerate(prompts):
        try:
            result = subprocess.run(
                ["bash", script, prompt],
                capture_output=True, text=True, timeout=120, cwd=WORKSPACE
            )
            if result.returncode == 0:
                for line in reversed(result.stdout.strip().split("\n")):
                    if line.strip().endswith(".png") and os.path.exists(line.strip()):
                        image_paths.append(line.strip())
                        log(f"  配图{i+1}: ✓")
                        break
            else:
                log(f"  配图{i+1}: 失败")
        except subprocess.TimeoutExpired:
            log(f"  配图{i+1}: 超时")
        except Exception as e:
            log(f"  配图{i+1}: {e}")
        # 至少要有2张，第3张失败不影响
        if i == 1 and len(image_paths) < 2:
            log("  WARNING: 仅生成1张配图，继续执行")
    
    return image_paths

# ========== Step 5: 排版 ==========
def format_content(html_content, title, image_urls):
    log("[5/7] 排版（微信图文HTML格式）")
    body = re.sub(r'<title>.*?</title>', '', html_content, flags=re.I | re.S).strip()
    
    # <h2>统一样式
    body = re.sub(
        r'<h2([^>]*)>(.*?)</h2>',
        lambda m: f'<h2{m.group(1)} style="color:#1a1a1a;border-left:4px solid #07c160;padding-left:12px;font-size:18px;">{m.group(2)}</h2>',
        body
    )
    
    # 插入配图
    if image_urls:
        first = f'<p style="text-align:center;"><img src="{image_urls[0]}" style="width:100%;border-radius:8px;margin:15px 0;"/></p>'
        h2s = list(re.finditer(r'(<h2[^>]*>)', body))
        if h2s:
            pos = h2s[0].start()
            body = body[:pos] + first + body[pos:]
        else:
            body = first + body
        
        # 剩余图片插入文中
        for idx, url in enumerate(image_urls[1:], 1):
            img = f'<p style="text-align:center;"><img src="{url}" style="width:100%;border-radius:8px;margin:15px 0;"/></p>'
            if idx < len(h2s):
                pos = h2s[idx].start()
                body = body[:pos] + img + body[pos:]
            else:
                body += img
    
    return body

# ========== Step 6: 校验 ==========
def validate(title, body, image_paths):
    log("[6/7] 校验")
    
    # 字数检查
    word_count = len(re.sub(r'<[^>]+>', '', body).replace(' ', '').replace('\n', ''))
    if word_count < 800:
        log(f"  WARNING: 字数偏少 ({word_count})，但不阻断发布")
    else:
        log(f"  字数: {word_count} ✓")
    
    # 图片检查
    if not image_paths:
        log("  WARNING: 无配图")
        return False
    log(f"  配图: {len(image_paths)}张 ✓")
    
    # 标题长度
    gbk_len = len(title.encode('gbk', errors='replace'))
    if gbk_len > 22:
        log(f"  WARNING: 标题GBK({gbk_len}字节)超限，将自动截断")
    else:
        log(f"  标题: {title} ({gbk_len}字节) ✓")
    
    return True

# ========== Step 7: 发布 ==========
def publish_to_draft(title, body, image_paths):
    log("[7/7] 发布到草稿箱")
    
    token = get_access_token()
    
    # 上传图片
    uploaded = []
    for p in image_paths:
        if os.path.exists(p):
            mid, url = upload_image(token, p)
            if mid and url:
                uploaded.append({"media_id": mid, "url": url})
    
    if not uploaded:
        log("ERROR: 配图上传失败")
        notify_feishu("⚠️ 微信公众号发布失败：配图上传失败")
        sys.exit(1)
    
    # 截断标题和摘要
    title = truncate_gbk(title, 22)
    digest = truncate_gbk(re.sub(r'<[^>]+>', '', body).strip()[:100], 20)
    
    draft = {
        "articles": [{
            "title": title,
            "thumb_media_id": uploaded[0]["media_id"],
            "author": "",
            "digest": digest,
            "content": body,
            "content_source_url": "",
            "need_open_comment": 1,
            "only_fans_can_comment": 0
        }]
    }
    
    r = requests.post(
        f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={token}",
        data=json.dumps(draft, ensure_ascii=False).encode('utf-8'),
        headers={"Content-Type": "application/json; charset=utf-8"},
        timeout=30
    )
    result = r.json()
    
    if "media_id" in result:
        log(f"✅ 草稿创建成功！标题: {title}")
        notify_feishu(f"✅ 微信公众号文章已发布到草稿箱\n📝 标题: {title}\n📂 请到公众号后台群发")
        return True
    else:
        log(f"ERROR: 发布失败: {result}")
        notify_feishu(f"⚠️ 微信公众号发布失败\n{json.dumps(result, ensure_ascii=False)}")
        return False

def cleanup_old(days=3):
    import shutil
    data_dir = os.path.dirname(WORK_DIR)
    cutoff = time.time() - days * 86400
    for d in os.listdir(data_dir):
        full = os.path.join(data_dir, d)
        if os.path.isdir(full) and d.startswith("auto_") and os.path.getmtime(full) < cutoff:
            shutil.rmtree(full, ignore_errors=True)

# ========== 主流程 ==========
def main():
    log("=" * 40)
    log("微信公众号自动化发文系统")
    log("=" * 40)
    
    topic = select_topic()
    content, title, word_count = generate_article(topic)
    content, title = polish_article(content, title)
    image_paths = generate_images(title)
    body = format_content(content, title, [p for p in image_paths])  # URLs在format里不用，后面重新上传
    if not validate(title, body, image_paths):
        notify_feishu("⚠️ 校验未通过，跳过发布")
        sys.exit(1)
    
    # 发布（内部会上传图片并插入URL）
    publish_to_draft(title, body, image_paths)
    cleanup_old()
    
    log("=" * 40)
    log("完成！请到公众号后台手动群发")
    log("=" * 40)

if __name__ == "__main__":
    main()
