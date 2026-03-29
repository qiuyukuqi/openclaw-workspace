#!/bin/bash
# Suno AI 音乐生成脚本 (通过302.ai API)
# 用法: ./suno_music.sh "描述" [模型] [纯音乐]
# 示例: ./suno_music.sh "A Chinese pop ballad about autumn rain"
# 示例: ./suno_music.sh "Sad piano melody" chirp-crow true

API_KEY="sk-VRTrDBlfKY1TXdffDiDNJtgUajH0EY7AN15pLWN1GDVbZC6c"
API_BASE="https://api.302.ai"
PROMPT="${1:?用法: $0 \"歌曲描述\" [模型] [纯音乐true/false]}"
MODEL="${2:-chirp-crow}"
INSTRUMENTAL="${3:-false}"
OUTPUT_DIR="/tmp/openclaw/music"

mkdir -p "$OUTPUT_DIR"

# 1. 提交任务
echo "📝 提交音乐生成任务..."
RESP=$(curl -s "$API_BASE/suno/submit/music" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d "{
    \"mv\": \"$MODEL\",
    \"gpt_description_prompt\": \"$PROMPT\",
    \"make_instrumental\": $INSTRUMENTAL
  }")

TASK_ID=$(echo "$RESP" | jq -r '.data')
if [ "$TASK_ID" = "null" ] || [ -z "$TASK_ID" ]; then
  echo "❌ 提交失败: $RESP"
  exit 1
fi
echo "📝 Task ID: $TASK_ID"

# 2. 轮询结果
echo "⏳ 生成中..."
for i in $(seq 1 60); do
  sleep 10
  RESULT=$(curl -s "$API_BASE/suno/fetch/$TASK_ID" \
    -H "Authorization: Bearer $API_KEY")
  STATUS=$(echo "$RESULT" | jq -r '.data.status')
  if [ "$STATUS" = "SUCCESS" ] || [ "$STATUS" = "complete" ]; then
    break
  fi
  echo "  [$i] $STATUS"
  if [ "$STATUS" = "FAILED" ]; then
    echo "❌ 生成失败"
    exit 1
  fi
done

# 3. 提取并下载两首歌
echo "✅ 生成完成！下载音频..."
TITLE=$(echo "$RESULT" | jq -r '.data.data[0].title // "suno_music"')

# 清理标题中的特殊字符
SAFE_TITLE=$(echo "$TITLE" | tr '/' '_' | tr ' ' '_')

for i in 0 1; do
  AUDIO_URL=$(echo "$RESULT" | jq -r ".data.data[$i].audio_url // .data.data[$i].metadata.audio_url // empty")
  VIDEO_URL=$(echo "$RESULT" | jq -r ".data.data[$i].video_url // empty")
  SONG_TITLE=$(echo "$RESULT" | jq -r ".data.data[$i].title // empty")
  DURATION=$(echo "$RESULT" | jq -r ".data.data[$i].metadata.duration // 0")
  TAGS=$(echo "$RESULT" | jq -r ".data.data[$i].metadata.tags // empty")

  if [ -n "$AUDIO_URL" ]; then
    OUTFILE="$OUTPUT_DIR/${SAFE_TITLE}_v$((i+1)).mp3"
    curl -s -o "$OUTFILE" "$AUDIO_URL"
    echo "  ✅ v$((i+1)): ${SONG_TITLE} (${DURATION}s) - $OUTFILE"
    echo "     标签: $TAGS"
  fi
done

# 4. 输出歌词
LYRICS=$(echo "$RESULT" | jq -r '.data.data[0].prompt // empty')
if [ -n "$LYRICS" ] && [ "$LYRICS" != "null" ]; then
  echo ""
  echo "=== 歌词 ==="
  echo "$LYRICS"
  echo "$LYRICS" > "$OUTPUT_DIR/${SAFE_TITLE}_lyrics.txt"
fi

echo ""
echo "🎵 完成！文件保存在: $OUTPUT_DIR/"
ls -lh "$OUTPUT_DIR/${SAFE_TITLE}"*
