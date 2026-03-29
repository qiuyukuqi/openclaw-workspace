#!/bin/bash
# 微信公众号热门话题搜索（纯 Bash + curl + jq）
# 按分类轮换：数码产品、IT技术、运维知识
# 输出: JSON（category, extra_prompt, topics）

source "$(dirname "$0")/config.sh"

# 主题库
TOPICS_JSON='{
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
}'

# 按日期轮换分类（每3天一轮）
DAY_OF_YEAR=$(date +%j)
CAT_INDEX=$(( (10#$DAY_OF_YEAR) % 3 ))
CAT_NAMES=("数码产品" "IT技术" "运维知识")
CATEGORY="${CAT_NAMES[$CAT_INDEX]}"

# 提取该分类的关键词数组，随机选一个
KEYWORDS=$(echo "$TOPICS_JSON" | jq -r ".\"$CATEGORY\".keywords | length")
RAND_INDEX=$(( RANDOM % KEYWORDS ))
KEYWORD=$(echo "$TOPICS_JSON" | jq -r ".\"$CATEGORY\".keywords[$RAND_INDEX]")
EXTRA_PROMPT=$(echo "$TOPICS_JSON" | jq -r ".\"$CATEGORY\".prompt")

echo "[分类] $CATEGORY | [关键词] $KEYWORD" >&2

# 调用 Tavily API
RESPONSE=$(curl -s --max-time 30 "https://api.tavily.com/search" \
    -H "Content-Type: application/json" \
    -d "$(jq -n \
        --arg api_key "$TAVILY_API_KEY" \
        --arg query "$KEYWORD" \
        '{
            api_key: $api_key,
            query: $query,
            topic: "news",
            days: 3,
            max_results: 8,
            include_answer: false,
            search_depth: "basic"
        }')")

# 输出 JSON
echo "$RESPONSE" | jq -c --arg cat "$CATEGORY" --arg prompt "$EXTRA_PROMPT" \
    '{
        category: $cat,
        extra_prompt: $prompt,
        topics: [.results[]? | {
            title: .title,
            snippet: .content,
            url: .url,
            score: .score
        }]
    }'
