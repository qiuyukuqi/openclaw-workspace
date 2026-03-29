#!/bin/bash
# 微信公众号全自动发布脚本（纯 Bash + curl）
# 搜索话题（按分类轮换）→ AI生成文章HTML → 生成配图 → 发布到草稿箱
# 用法: ./auto_publish.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/config.sh"
source ~/.openclaw/workspace/.env.wechat

WORK_DIR="$DATA_DIR/auto_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$WORK_DIR"

LOG="$WORK_DIR/publish.log"
exec > >(tee -a "$LOG") 2>&1

echo "=== $(date '+%Y-%m-%d %H:%M:%S') 开始自动发布 ==="

# 1. 搜索热门话题
echo "[1/4] 搜索热门话题..."
TOPICS_JSON=$(python3 "$SCRIPT_DIR/search_topics.py" 2>"$WORK_DIR/search.log")
if [ $? -ne 0 ] || [ -z "$TOPICS_JSON" ]; then
    echo "ERROR: 搜索话题失败"
    cat "$WORK_DIR/search.log"
    openclaw send --message "⚠️ 微信公众号发布失败：搜索话题阶段出错" 2>/dev/null
    exit 1
fi

# 提取信息（用 python3 最小化解析，仅提取分类/标题/score）
META=$(echo "$TOPICS_JSON" | python3 -c "
import json,sys
d=json.load(sys.stdin)
cats=d.get('category','未知')
topics=d.get('topics',[])
extra=d.get('extra_prompt','')
title=topics[0]['title'] if topics else ''
score=topics[0]['score'] if topics else 0
snippet=topics[0]['snippet'] if topics else ''
# 输出用分隔符隔开
print(f'{cats}|{title}|{score}|{snippet}|{extra}')
" 2>/dev/null)

CATEGORY=$(echo "$META" | cut -d'|' -f1)
TOP_TITLE=$(echo "$META" | cut -d'|' -f2)
TOP_SNIPPET=$(echo "$META" | cut -d'|' -f4)
EXTRA_PROMPT=$(echo "$META" | cut -d'|' -f5)

echo "今日分类: $CATEGORY"
echo "选中话题: $TOP_TITLE"

# 2. AI生成文章（纯 curl + jq）
echo "[2/4] AI生成文章..."

# 构建 prompt（用临时文件避免 bash 引号问题）
PROMPT_FILE="$WORK_DIR/prompt.txt"
TODAY=$(date +%Y年%m月%d日)

cat > "$PROMPT_FILE" << PROMPTEOF
你是一位资深科技行业分析师，专注${CATEGORY}领域。请根据以下热点话题，写一篇1500-2000字的深度分析文章。

话题标题: ${TOP_TITLE}
话题摘要: ${TOP_SNIPPET}

${EXTRA_PROMPT}

通用要求:
1. 标题必须是纯中文，不超过11个字，不要包含任何英文、数字、标点符号（冒号、问号等也不要），精简有力
2. 写作风格：通俗易懂，像和朋友聊天一样，语言口语化、接地气，可以用"大家好""老朋友""举个栗子"等口语化表达
3. 内容要有深度：分析行业背景、技术原理、市场格局、竞争态势、未来趋势
4. 用数据和案例支撑观点，引用具体厂商/产品/数据
5. 段落分明，使用<h2>小标题分层论述
6. 文末给出有洞察力的总结判断
7. 摘要(digest)不超过9个中文字
8. 标题格式参考："程序员怎么办""芯片战升级了""手机市场大洗牌"这种纯中文、短小精悍的格式，绝对不能出现英文或数字

输出格式要求（严格遵守）：
1. 不要包含署名行、日期行、作者信息
2. 第一行必须是标题（非<p>包裹的纯文字），格式如："Vibe Coding席卷IT圈：会用AI的人，正在替代不会用AI的人"
3. 紧跟一个空行
4. 然后是正文内容（用<p>分段）
5. 包含<title>标签（放在正文最后或开头均可）
6. 使用<p>分段，<h2>做小标题
7. 不需要<head><body>
8. 不要用markdown代码块包裹
9. 不要使用<br>换行标签，段落之间用</p><p>分隔即可
10. 文字之间不要插入多余空格或&nbsp;等HTML实体
11. 正文开头先写一句简短有力的观点句（如"AI编程不是在消灭程序员，而是在淘汰不愿进化的程序员。"），再展开论述
12. 语言风格：口语化、接地气、有代入感，类似公众号爆款文的写法
PROMPTEOF

PROMPT_CONTENT=$(cat "$PROMPT_FILE")

ARTICLE_HTML=$(curl -s --max-time 120 \
    "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions" \
    -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
    -H "Content-Type: application/json" \
    -d "$(jq -n \
        --arg prompt "$PROMPT_CONTENT" \
        '{
            model: "qwen-plus",
            messages: [{role: "user", content: $prompt}],
            max_tokens: 3000,
            temperature: 0.8
        }')" | jq -r '.choices[0].message.content // empty')

# 清理HTML中可能导致字间距空格的标签
ARTICLE_HTML=$(echo "$ARTICLE_HTML" | sed 's/<br\s*\/\?>//gi; s/&nbsp;/ /g; s/<code[^>]*>/<p>/gi; s/<\/code>/<\/p>/gi')

# 清理 prompt 临时文件
rm -f "$PROMPT_FILE"

if [ -z "$ARTICLE_HTML" ]; then
    echo "ERROR: AI生成文章失败"
    openclaw send --message "⚠️ 微信公众号发布失败：AI生成文章阶段出错" 2>/dev/null
    exit 1
fi

# 确保有 title 标签
if ! echo "$ARTICLE_HTML" | grep -qi '<title>'; then
    ARTICLE_HTML="<title>${TOP_TITLE}</title>${ARTICLE_HTML}"
fi

echo "文章内容预览:"
echo "$ARTICLE_HTML" | head -20
echo "..."

# 3&4. 生成配图并发布
echo "[3/4] 生成配图并发布..."
PUBLISH_RESULT=$(echo "$ARTICLE_HTML" | bash "$SCRIPT_DIR/publish.sh" 2>&1)

echo "发布结果: $PUBLISH_RESULT"

if echo "$PUBLISH_RESULT" | grep -q '"draft"'; then
    MEDIA_ID=$(echo "$PUBLISH_RESULT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('media_id',''))" 2>/dev/null)
    ARTICLE_TITLE=$(echo "$ARTICLE_HTML" | python3 -c "
import sys, re
html = sys.stdin.read()
m = re.search(r'<title>(.*?)</title>', html, re.I|re.S)
print(m.group(1).strip() if m else '未知')
" 2>/dev/null)
    
    echo "=== 发布成功 ==="
    echo "标题: $ARTICLE_TITLE"
    echo "草稿ID: $MEDIA_ID"
    
    openclaw send --message "✅ 微信公众号文章已发布到草稿箱
📝 标题: $ARTICLE_TITLE
📂 分类: $CATEGORY
📎 草稿ID: $MEDIA_ID

请到公众号后台查看并群发" 2>/dev/null
else
    echo "ERROR: 发布失败"
    openclaw send --message "⚠️ 微信公众号发布失败：发布阶段出错
$PUBLISH_RESULT" 2>/dev/null
    exit 1
fi

# 清理旧数据（保留最近3天的）
find "$DATA_DIR" -maxdepth 1 -type d -name "auto_*" -mtime +3 -exec rm -rf {} + 2>/dev/null

echo "=== $(date '+%Y-%m-%d %H:%M:%S') 完成 ==="
