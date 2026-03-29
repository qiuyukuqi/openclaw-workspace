#!/bin/bash
# 文档解析(GLM-OCR) - 智谱高级文档布局识别
# 用法: doc_parse.sh <file.pdf|png|jpg> [start_page] [end_page]

API_KEY="579714647a6c40d7bb95632559736fb2.VqYfT1pnRPS34CQu"
FILE="$1"

if [ -z "$FILE" ]; then echo "Usage: doc_parse.sh <file>"; exit 1; fi

# Base64 编码
B64=$(base64 -w0 "$FILE")
EXT=$(echo "${FILE##*.}" | tr '[:upper:]' '[:lower:]')
MIME="image/$EXT"
[ "$EXT" = "pdf" ] && MIME="application/pdf"
FILE_DATA="data:$MIME;base64,$B64"

BODY="{\"model\":\"glm-ocr\",\"file\":\"$FILE_DATA\"}"
[ -n "$2" ] && BODY=$(echo "$BODY" | sed "s/}/,\"start_page_id\":$2}/")
[ -n "$3" ] && BODY=$(echo "$BODY" | sed "s/}/,\"end_page_id\":$3}/")

echo "⏳ Parsing ($EXT)..." >&2
RESULT=$(curl -s -X POST "https://open.bigmodel.cn/api/paas/v4/layout_parsing" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d "$BODY")

MD=$(echo "$RESULT" | jq -r '.md_results // empty')
if [ -n "$MD" ]; then
  echo "$MD"
else
  echo "$RESULT" | jq '.'
fi
