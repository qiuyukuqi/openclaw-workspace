#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信公众号热门话题搜索（Python + Tavily API）
按分类轮换：数码产品、IT技术、运维知识
输出: JSON（category, extra_prompt, topics）
"""

import json
import random
import sys
from datetime import datetime
import requests

SCRIPT_DIR = sys.path[0]

# 加载配置
def load_config():
    import os
    config = {}
    # 从 config.sh 风格的 .env.wechat 读取
    # 优先从 config.sh 读取，其次从 .env.wechat
    for env_file in [
        os.path.expanduser("~/.openclaw/workspace/skills/wechat-publisher/scripts/config.sh"),
        os.path.expanduser("~/.openclaw/workspace/.env.wechat")
    ]:
        if os.path.exists(env_file):
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if '=' in line and not line.startswith('#'):
                        key, _, val = line.partition('=')
                        config[key.strip()] = val.strip().strip('"')
    return config

CATEGORIES = {
    "数码产品": {
        "keywords": [
            "手机评测 新品发布 2026",
            "笔记本电脑 电脑硬件 2026",
            "智能手表 智能穿戴 新品 2026",
            "平板电脑 iPad 评测 2026",
            "耳机 音响 数码配件 2026",
            "手机芯片 处理器 性能对比 2026",
            "折叠屏手机 柔性屏 2026"
        ],
        "prompt": "请以科技自媒体博主的视角，围绕数码产品的新品、评测或行业趋势撰写文章，风格轻松有趣，要有个人观点和购买建议。"
    },
    "IT技术": {
        "keywords": [
            "Python JavaScript 编程语言 新特性 2026",
            "AI编程工具 Copilot Cursor 开发效率 2026",
            "Web开发 React Vue 前端框架 2026",
            "开源项目 GitHub 热门 2026",
            "云原生 Kubernetes Docker 微服务 2026",
            "大语言模型 LLM 应用开发 2026",
            "数据库 PostgreSQL Redis MySQL 新版本 2026"
        ],
        "prompt": "请以资深程序员的视角，围绕IT技术的新趋势、新工具或实战经验撰写文章，要有代码示例或技术分析，面向有一定技术基础的开发者。"
    },
    "运维知识": {
        "keywords": [
            "Linux服务器运维 实战技巧 2026",
            "网络安全 漏洞防护 服务器加固 2026",
            "DevOps CI/CD 自动化部署 2026",
            "云服务器 AWS 阿里云 腾讯云 2026",
            "Nginx 网站优化 负载均衡 2026",
            "监控告警 Prometheus Grafana Zabbix 2026",
            "容器化部署 Kubernetes 生产实践 2026"
        ],
        "prompt": "请以运维工程师的视角，围绕服务器运维、网络管理或DevOps实战撰写文章，要有实际操作步骤和经验总结，面向运维和后端开发人员。"
    }
}

def search_tavily(api_key, query):
    """调用 Tavily API 搜索"""
    resp = requests.post("https://api.tavily.com/search", json={
        "api_key": api_key,
        "query": query,
        "topic": "news",
        "days": 3,
        "max_results": 8,
        "include_answer": False,
        "search_depth": "basic"
    }, timeout=30)
    resp.raise_for_status()
    return resp.json()

def main():
    config = load_config()
    tavily_key = config.get("TAVILY_API_KEY", "")
    if not tavily_key:
        print("ERROR: TAVILY_API_KEY not found in .env.wechat", file=sys.stderr)
        sys.exit(1)

    # 按日期轮换分类（每3天一轮）
    day_of_year = datetime.now().timetuple().tm_yday
    cat_names = list(CATEGORIES.keys())
    category = cat_names[day_of_year % 3]

    cat_info = CATEGORIES[category]
    keyword = random.choice(cat_info["keywords"])
    extra_prompt = cat_info["prompt"]

    print(f"[分类] {category} | [关键词] {keyword}", file=sys.stderr)

    try:
        result = search_tavily(tavily_key, keyword)
    except Exception as e:
        print(f"ERROR: Tavily API 调用失败: {e}", file=sys.stderr)
        sys.exit(1)

    topics = []
    for item in result.get("results", []):
        topics.append({
            "title": item.get("title", ""),
            "snippet": item.get("content", ""),
            "url": item.get("url", ""),
            "score": item.get("score", 0)
        })

    output = {
        "category": category,
        "extra_prompt": extra_prompt,
        "topics": topics
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
