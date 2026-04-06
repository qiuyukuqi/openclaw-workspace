#!/bin/bash
# 头条号发布脚本 - agent-browser版
set -e

cd ~/.openclaw/workspace/skills/auto-publisher

STATE="/tmp/openclaw/toutiao_state.json"
TITLE="${1:-AI自动化发布的优势与挑战}"
CONTENT_FILE="${2:-test_article.md}"

# Read content
CONTENT=$(cat "$CONTENT_FILE")

echo "[toutiao] Loading state..."
agent-browser close 2>/dev/null || true
agent-browser state load "$STATE"

echo "[toutiao] Opening editor..."
agent-browser open "https://mp.toutiao.com/profile_v4/graphic/articles/new" --timeout 30000
agent-browser wait 3000

echo "[toutiao] Clicking article menu..."
agent-browser snapshot -i --timeout 5000 | grep -q "文章" && {
    ARTICLE_REF=$(agent-browser snapshot -i --timeout 5000 | grep '"文章"' | grep -oP '\[ref=\K[^]]+')
    agent-browser click "@$ARTICLE_REF" --timeout 5000
}
agent-browser wait 15000

echo "[toutiao] Filling title..."
agent-browser eval "const t = document.querySelector('textarea[placeholder*=\"标题\"]'); if(t) { t.focus(); t.value = '$TITLE'; t.dispatchEvent(new Event('input', {bubbles:true})); } 'ok'"
agent-browser wait 1000

echo "[toutiao] Filling content..."
# Escape content for JS
ESCAPED=$(echo "$CONTENT" | sed "s/'/\\\\'/g" | tr '\n' ' ')
agent-browser eval "const e = document.querySelector('.ProseMirror:not(.syl-placeholder)'); if(e) { e.innerHTML = '<p>' + '$ESCAPED'.replace(/\\n/g, '</p><p>') + '</p>'; e.dispatchEvent(new Event('input', {bubbles:true})); } 'ok'"
agent-browser wait 1000

echo "[toutiao] Clicking publish..."
PUBLISH_REF=$(agent-browser snapshot -i --timeout 5000 | grep '预览并发布' | grep -oP '\[ref=\K[^]]+')
agent-browser click "@$PUBLISH_REF" --timeout 10000
agent-browser wait 5000

echo "[toutiao] Screenshot..."
agent-browser screenshot --timeout 5000 tt_result.png 2>/dev/null || echo "Screenshot failed"

echo "[toutiao] Done!"
