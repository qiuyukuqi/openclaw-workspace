#!/bin/bash
# 微信公众号自动发布 - 纯 Bash + curl + jq 版本
# 用法: echo '<html>...</html>' | ./publish.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/config.sh"

if [ -t 0 ]; then
    echo "=== 搜索热门话题 ===" >&2
    bash "$SCRIPT_DIR/search_topics.sh"
    exit 0
fi

# 从 stdin 读取 HTML
HTML_CONTENT=$(cat)
if [ -z "$HTML_CONTENT" ]; then
    echo "ERROR: 请通过 stdin 传入 HTML 内容" >&2
    exit 1
fi

# 提取 <title>（纯 bash/sed）
TITLE=$(echo "$HTML_CONTENT" | sed -n 's/.*<title>\(.*\)<\/title>.*/\1/pi' | head -1)
if [ -z "$TITLE" ]; then
    echo "ERROR: HTML 中未找到 <title> 标签" >&2
    exit 1
fi

# 微信标题限制：GBK编码不超过22字节（约11个纯中文字）
TITLE_BYTES=$(echo -n "$TITLE" | iconv -t GBK 2>/dev/null | wc -c)
if [ "$TITLE_BYTES" -gt 22 ]; then
    # 逐步截断直到符合限制
    SHORT_TITLE="$TITLE"
    while [ "$(echo -n "$SHORT_TITLE" | iconv -t GBK 2>/dev/null | wc -c)" -gt 22 ]; do
        SHORT_TITLE="${SHORT_TITLE%?}"
    done
    echo "标题超限(${TITLE_BYTES}字节)，截断为: $SHORT_TITLE" >&2
    TITLE="$SHORT_TITLE"
fi
echo "标题: $TITLE (GBK ${TITLE_BYTES}字节)" >&2

# 生成配图
echo "=== 生成配图 ===" >&2
IMAGE_DIR="$DATA_DIR/images_$(date +%s)"
mkdir -p "$IMAGE_DIR"
IMAGE_PROMPT="$TITLE 科技感 配图 高清"
IMAGE_PATHS=$("$SCRIPT_DIR/generate_images.sh" "$IMAGE_PROMPT" 2>&1 | tee /dev/stderr)

if [ $? -ne 0 ] || [ -z "$IMAGE_PATHS" ]; then
    echo "WARNING: 图片生成失败，将使用无图模式发布" >&2
    IMAGE_URLS="[]"
else
    # 上传图片到微信
    echo "=== 上传图片到微信 ===" >&2
    URL_ARRAY=""
    FIRST=true
    while IFS= read -r img_path; do
        if [ -n "$img_path" ] && [ -f "$img_path" ]; then
            URL=$("$SCRIPT_DIR/upload_image.sh" "$img_path")
            if [ $? -eq 0 ] && [ -n "$URL" ]; then
                [ "$FIRST" = true ] && FIRST=false || URL_ARRAY+=","
                URL_ARRAY+="\"$URL\""
            fi
        fi
    done <<< "$IMAGE_PATHS"
    IMAGE_URLS="[$URL_ARRAY]"
fi

# 获取 token
TOKEN=$("$SCRIPT_DIR/get_token.sh")
if [ $? -ne 0 ] || [ -z "$TOKEN" ]; then
    echo "ERROR: 获取 token 失败" >&2
    exit 1
fi

# 找第一张本地图片
FIRST_IMG=""
while IFS= read -r img_path; do
    if [ -n "$img_path" ] && [ -f "$img_path" ]; then
        FIRST_IMG="$img_path"
        break
    fi
done <<< "$IMAGE_PATHS"

if [ -z "$FIRST_IMG" ]; then
    echo "ERROR: 至少需要一张配图作为封面" >&2
    exit 1
fi

# 上传封面图（thumb 永久素材）
echo "=== 上传封面图 ===" >&2
THUMB_RESP=$(curl -s -F media="@$FIRST_IMG" \
    "https://api.weixin.qq.com/cgi-bin/material/add_material?access_token=$TOKEN&type=thumb")
THUMB_MEDIA_ID=$(echo "$THUMB_RESP" | jq -r '.media_id // empty')

if [ -z "$THUMB_MEDIA_ID" ]; then
    echo "ERROR: 上传封面失败: $THUMB_RESP" >&2
    exit 1
fi

# 构建图文内容（插入图片到 HTML）
# 从 HTML 中提取 body 内容（去掉 <title> 标签）
BODY_CONTENT=$(echo "$HTML_CONTENT" | sed 's/<title>.*<\/title>//i')
CONTENT_FILE="$IMAGE_DIR/content.html"

# 在文章中插入配图（如果HTML中没有img标签）
if ! echo "$BODY_CONTENT" | grep -qi '<img'; then
    # 用 python3 安全拼接 HTML + 图片URLs
    CONTENT_WITH_IMAGES=$(python3 -c "
import json, sys
html = '''$BODY_CONTENT'''
urls = $IMAGE_URLS
if urls:
    img_html = '<p style=\"text-align:center;\"><img src=\"' + urls[0] + '\" style=\"width:100%;border-radius:8px;margin:15px 0;\"/></p>'
    for u in urls[1:]:
        img_html += '<p style=\"text-align:center;\"><img src=\"' + u + '\" style=\"width:100%;border-radius:8px;margin:15px 0;\"/></p>'
    # 在第一个 <h2> 前插入第一张图，其余追加到文末
    import re
    parts = re.split(r'(<h2[^>]*>)', html, maxsplit=1)
    if len(parts) == 3:
        html = parts[0] + img_html + parts[1] + parts[2]
    else:
        html = img_html + html
print(html)
" 2>/dev/null)
else
    CONTENT_WITH_IMAGES="$BODY_CONTENT"
fi

# 构建 digest（从正文中提取纯文本，截断到9个中文字）
DIGEST=$(echo "$BODY_CONTENT" | sed 's/<[^>]*>//g' | tr -s ' \n' | head -c 50 | sed 's/[[:space:]]*$//')

# 构建草稿 JSON
DRAFT_JSON=$(jq -n \
    --arg title "$TITLE" \
    --arg thumb "$THUMB_MEDIA_ID" \
    --arg content "$CONTENT_WITH_IMAGES" \
    --arg digest "$DIGEST" \
    '{
        articles: [{
            title: $title,
            thumb_media_id: $thumb,
            author: "",
            digest: $digest,
            content: $content,
            content_source_url: "",
            need_open_comment: 0,
            only_fans_can_comment: 0
        }]
    }')

# 创建草稿
echo "=== 创建草稿 ===" >&2
DRAFT_RESP=$(curl -s -X POST \
    "https://api.weixin.qq.com/cgi-bin/draft/add?access_token=$TOKEN" \
    -H "Content-Type: application/json" \
    -d "$DRAFT_JSON")

MEDIA_ID=$(echo "$DRAFT_RESP" | jq -r '.media_id // empty')

if [ -z "$MEDIA_ID" ]; then
    echo "ERROR: 创建草稿失败: $DRAFT_RESP" >&2
    exit 1
fi

echo "草稿 media_id: $MEDIA_ID" >&2
echo "{\"status\": \"draft\", \"media_id\": \"$MEDIA_ID\", \"message\": \"文章已在草稿箱，请到公众号后台手动群发\"}"
