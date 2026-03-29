#!/bin/bash
# 文字生图 - 智谱 GLM-Image 异步API
# 用法: text2img.sh "描述" [size] [output]
# 示例: text2img.sh "一只猫" 1728x960 /tmp/cat.png

API_KEY="579714647a6c40d7bb95632559736fb2.VqYfT1pnRPS34CQu"
PROMPT="$1"
SIZE="${2:-1280x1280}"
OUTPUT="${3:-/tmp/openclaw/t2i_$(date +%s).png}"
WATERMARK="${4:-true}"  # true/false

mkdir -p /tmp/openclaw

# 提交任务
TASK=$(curl -s -X POST "https://open.bigmodel.cn/api/paas/v4/async/images/generations" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"glm-image\",\"prompt\":\"$PROMPT\",\"quality\":\"hd\",\"size\":\"$SIZE\",\"watermark_enabled\":$WATERMARK}")
TASK_ID=$(echo "$TASK" | jq -r '.id')

if [ "$TASK_ID" = "null" ] || [ -z "$TASK_ID" ]; then
  echo "❌ Submit failed: $TASK" >&2
  exit 1
fi
echo "📝 Task: $TASK_ID" >&2

# 轮询结果
for i in $(seq 1 60); do
  sleep 3
  RESULT=$(curl -s "https://open.bigmodel.cn/api/paas/v4/async-result/$TASK_ID" \
    -H "Authorization: Bearer $API_KEY")
  STATUS=$(echo "$RESULT" | jq -r '.task_status')
  [ "$STATUS" = "FAIL" ] && { echo "❌ Failed: $RESULT" >&2; exit 1; }
  [ "$STATUS" = "SUCCESS" ] && break
  echo "  ⏳ $STATUS..." >&2
done

# 下载图片
IMG_URL=$(echo "$RESULT" | jq -r '.image_result[0].url // empty')
if [ -z "$IMG_URL" ]; then
  echo "❌ No image URL: $RESULT" >&2; exit 1
fi
curl -s -o "$OUTPUT" "$IMG_URL"
echo "$OUTPUT"
