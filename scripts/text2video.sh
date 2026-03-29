#!/bin/bash
# 文字生视频 - 智谱 CogVideoX-3 异步API
# 用法: text2video.sh "描述" [output]
# 示例: text2video.sh "猫咪玩球" /tmp/cat.mp4

API_KEY="579714647a6c40d7bb95632559736fb2.VqYfT1pnRPS34CQu"
PROMPT="$1"
OUTPUT="${2:-/tmp/openclaw/t2v_$(date +%s).mp4}"
SIZE="${3:-1920x1080}"

mkdir -p /tmp/openclaw

# 提交任务
TASK=$(curl -s -X POST "https://open.bigmodel.cn/api/paas/v4/videos/generations" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"cogvideox-3\",\"prompt\":\"$PROMPT\",\"quality\":\"quality\",\"size\":\"$SIZE\",\"fps\":30,\"duration\":5}")
TASK_ID=$(echo "$TASK" | jq -r '.id')

if [ "$TASK_ID" = "null" ] || [ -z "$TASK_ID" ]; then
  echo "❌ Submit failed: $TASK" >&2; exit 1
fi
echo "📝 Task: $TASK_ID" >&2

# 轮询结果(视频较长，等10分钟)
for i in $(seq 1 120); do
  sleep 5
  RESULT=$(curl -s "https://open.bigmodel.cn/api/paas/v4/async-result/$TASK_ID" \
    -H "Authorization: Bearer $API_KEY")
  STATUS=$(echo "$RESULT" | jq -r '.task_status')
  [ "$STATUS" = "FAIL" ] && { echo "❌ Failed: $RESULT" >&2; exit 1; }
  [ "$STATUS" = "SUCCESS" ] && break
  echo "  ⏳ $STATUS..." >&2
done

# 下载视频
VID_URL=$(echo "$RESULT" | jq -r '.video_result[0].url // empty')
if [ -z "$VID_URL" ]; then
  echo "❌ No video URL: $RESULT" >&2; exit 1
fi
echo "⬇️ Downloading..." >&2
curl -s -o "$OUTPUT" "$VID_URL"
echo "$OUTPUT"
