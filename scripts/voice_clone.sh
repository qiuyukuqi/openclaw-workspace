#!/bin/bash
# 音色复刻 - 智谱 GLM-TTS-Clone
# 用法: voice_clone.sh <sample.wav> "合成文本" [音色名称]

API_KEY="579714647a6c40d7bb95632559736fb2.VqYfT1pnRPS34CQu"
AUDIO="$1"
TEXT="$2"
NAME="${3:-voice_$(date +%s)}"

if [ -z "$AUDIO" ] || [ -z "$TEXT" ]; then
  echo "Usage: voice_clone.sh <sample.wav> \"text\" [name]"
  exit 1
fi

# Step 1: 上传音频
echo "⏳ Uploading..." >&2
UPLOAD=$(curl -s -X POST "https://open.bigmodel.cn/api/paas/v4/files/upload" \
  -H "Authorization: Bearer $API_KEY" \
  -F "purpose=voice-audio" \
  -F "file=@$AUDIO")
FILE_ID=$(echo "$UPLOAD" | jq -r '.id // empty')
if [ -z "$FILE_ID" ]; then
  echo "❌ Upload failed: $UPLOAD" >&2; exit 1
fi
echo "📎 file_id: $FILE_ID" >&2

# Step 2: 音色复刻
echo "🎙️ Cloning..." >&2
RESULT=$(curl -s -X POST "https://open.bigmodel.cn/api/paas/v4/voice/clone" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"glm-tts-clone\",\"voice_name\":\"$NAME\",\"file_id\":\"$FILE_ID\",\"input\":\"$(echo "$TEXT" | sed 's/"/\\"/g')\"}")

VOICE=$(echo "$RESULT" | jq -r '.voice // empty')
echo "✅ Voice: $VOICE" >&2
echo "$RESULT" | jq '.'
