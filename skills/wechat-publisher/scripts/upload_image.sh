#!/bin/bash
# 上传图片到微信素材库
# 用法: ./upload_image.sh <image_path>
# 输出: 微信图片URL

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/config.sh"

if [ -z "$1" ]; then
    echo "ERROR: 请指定图片路径" >&2
    exit 1
fi

IMAGE_PATH="$1"
if [ ! -f "$IMAGE_PATH" ]; then
    echo "ERROR: 图片不存在: $IMAGE_PATH" >&2
    exit 1
fi

TOKEN=$("$SCRIPT_DIR/get_token.sh")
if [ $? -ne 0 ]; then
    echo "ERROR: 获取token失败" >&2
    exit 1
fi

RESPONSE=$(curl -s -F media="@$IMAGE_PATH" "https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token=$TOKEN")

URL=$(echo "$RESPONSE" | python3 -c "import json,sys; print(json.load(sys.stdin).get('url',''))" 2>/dev/null)

if [ -z "$URL" ]; then
    echo "ERROR: 上传失败: $RESPONSE" >&2
    exit 1
fi

echo "$URL"
