#!/bin/bash
# 智谱 CogView-3-Flash 生成图片
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

# 调用智谱API（同步返回URL）
RESPONSE=$(curl -s --max-time 120 -X POST "https://open.bigmodel.cn/api/paas/v4/images/generations" \
    -H "Authorization: Bearer $ZHIPU_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{
        \"model\": \"cogview-3-flash\",
        \"prompt\": \"$PROMPT\"
    }")

# 下载图片
echo "$RESPONSE" | python3 -c "
import json, sys, urllib.request
data = json.load(sys.stdin)
if 'data' not in data:
    print('ERROR: 生成失败: ' + str(data), file=sys.stderr)
    sys.exit(1)
for i, item in enumerate(data['data']):
    url = item.get('url', '')
    if not url:
        continue
    path = '$OUT_DIR/image_' + str(i+1) + '.png'
    try:
        urllib.request.urlretrieve(url, path)
        print(path)
    except Exception as e:
        print(f'ERROR: 下载失败: {e}', file=sys.stderr)
" 2>&1
