#!/bin/bash
# 文本重排序 - 智谱 Rerank
# 用法: rerank.sh "查询" "候选1" "候选2" [候选3...]

API_KEY="579714647a6c40d7bb95632559736fb2.VqYfT1pnRPS34CQu"
QUERY="$1"
shift

# 构建 documents JSON 数组
DOCS="["
FIRST=true
for doc in "$@"; do
  $FIRST || DOCS+=","
  DOCS+="\"$(echo "$doc" | sed 's/"/\\"/g')\""
  FIRST=false
done
DOCS+="]"

RESULT=$(curl -s -X POST "https://open.bigmodel.cn/api/paas/v4/rerank" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"rerank\",\"query\":\"$(echo "$QUERY" | sed 's/"/\\"/g')\",\"documents\":$DOCS,\"return_documents\":true}")

echo "$RESULT" | jq -r '.results[] | "  [\(.relevance_score // .score | . * 1000 | floor / 1000)] \(.document // .document.text // "N/A")"'
