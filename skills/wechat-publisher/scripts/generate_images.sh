#!/bin/bash
# 通义万相生成图片
# 用法: ./generate_images.sh <描述>
# 输出: 本地图片路径列表（每行一个）

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/config.sh"

if [ -z "$1" ]; then
    echo "ERROR: 请提供图片描述" >&2
    exit 1
fi

PROMPT="$1"
TIMESTAMP=$(date +%s)
OUT_DIR="$DATA_DIR/images_$TIMESTAMP"
mkdir -p "$OUT_DIR"

# 提交异步任务
TASK_RESPONSE=$(curl -s -X POST "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis" \
    -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
    -H "Content-Type: application/json" \
    -H "X-DashScope-Async: enable" \
    -d "{
        \"model\": \"wanx-v1\",
        \"input\": {
            \"prompt\": \"$PROMPT\"
        },
        \"parameters\": {
            \"n\": 2,
            \"size\": \"1024*1024\"
        }
    }")

TASK_ID=$(echo "$TASK_RESPONSE" | python3 -c "import json,sys; print(json.load(sys.stdin).get('output',{}).get('task_id',''))" 2>/dev/null)

if [ -z "$TASK_ID" ]; then
    echo "ERROR: 提交生成任务失败: $TASK_RESPONSE" >&2
    exit 1
fi

echo "任务已提交: $TASK_ID，等待生成..." >&2

# 轮询结果（最多等待3分钟）
for i in $(seq 1 36); do
    sleep 5
    STATUS_RESPONSE=$(curl -s "https://dashscope.aliyuncs.com/api/v1/tasks/$TASK_ID" \
        -H "Authorization: Bearer $DASHSCOPE_API_KEY")

    TASK_STATUS=$(echo "$STATUS_RESPONSE" | python3 -c "import json,sys; print(json.load(sys.stdin).get('output',{}).get('task_status',''))" 2>/dev/null)

    if [ "$TASK_STATUS" = "SUCCEEDED" ]; then
        echo "$STATUS_RESPONSE" | python3 -c "
import json, sys, urllib.request
data = json.load(sys.stdin)
results = data['output']['results']
urls = [r['url'] for r in results]
for i, url in enumerate(urls):
    path = '$OUT_DIR/image_' + str(i+1) + '.jpg'
    urllib.request.urlretrieve(url, path)
    print(path)
" 2>&1
        exit 0
    elif [ "$TASK_STATUS" = "FAILED" ]; then
        echo "ERROR: 生成失败: $STATUS_RESPONSE" >&2
        exit 1
    fi
done

echo "ERROR: 生成超时" >&2
exit 1
