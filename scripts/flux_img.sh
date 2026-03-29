#!/bin/bash
# FLUX 图像生成 - 硅基流动 API
# 用法: bash flux_img.sh "提示词" [输出路径] [宽度] [高度]

API_KEY="sk-eldykavfswqslktlqdohofcwjwaswdebmbpjtvkmcbyzljhw"
API_URL="https://api.siliconflow.cn/v1/images/generations"
MODEL="Kwai-Kolors/Kolors"

PROMPT="$1"
OUTPUT="${2:-/tmp/openclaw/flux_$(date +%s).png}"
WIDTH="${3:-1024}"
HEIGHT="${4:-576}"

if [ -z "$PROMPT" ]; then
  echo "用法: bash flux_img.sh \"提示词\" [输出路径] [宽] [高]"
  exit 1
fi

RESPONSE=$(curl -s "$API_URL" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"$MODEL\",
    \"prompt\": \"$PROMPT\",
    \"image_size\": \"${WIDTH}x${HEIGHT}\",
    \"num_inference_steps\": 20
  }")

echo "$RESPONSE" | head -c 200

# 提取图片URL并下载
IMG_URL=$(echo "$RESPONSE" | jq -r '.images[0].url // empty')

if [ -n "$IMG_URL" ]; then
  curl -s -o "$OUTPUT" "$IMG_URL"
  echo ""
  echo "✅ 已保存: $OUTPUT"
else
  echo ""
  echo "❌ 生成失败"
  echo "$RESPONSE"
fi
