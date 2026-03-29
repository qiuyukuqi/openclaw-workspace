#!/bin/bash
# 语音转文本 - 智谱 GLM-ASR
# 用法: asr.sh <audio.wav|mp3>

API_KEY="579714647a6c40d7bb95632559736fb2.VqYfT1pnRPS34CQu"
FILE="$1"

if [ -z "$FILE" ]; then echo "Usage: asr.sh <audio_file>"; exit 1; fi

RESULT=$(curl -s -X POST "https://open.bigmodel.cn/api/paas/v4/audio/transcriptions" \
  -H "Authorization: Bearer $API_KEY" \
  -F "file=@$FILE" \
  -F "model=glm-asr-2512" \
  -F "stream=false")

echo "$RESULT" | jq -r '.text // empty'
