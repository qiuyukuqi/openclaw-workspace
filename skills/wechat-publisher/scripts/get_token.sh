#!/bin/bash
# 获取微信公众号 access_token
# 用法: ./get_token.sh
# 输出: token字符串到stdout

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/config.sh"

TOKEN_CACHE="$DATA_DIR/access_token.json"

# 检查缓存是否有效（提前10分钟过期）
if [ -f "$TOKEN_CACHE" ]; then
    expires_at=$(python3 -c "import json,time; d=json.load(open('$TOKEN_CACHE')); print(d.get('expires_at',0))" 2>/dev/null)
    if [ -n "$expires_at" ] && [ "$(date +%s)" -lt "$expires_at" ]; then
        python3 -c "import json; print(json.load(open('$TOKEN_CACHE'))['access_token'])"
        exit 0
    fi
fi

# 请求新token
RESPONSE=$(curl -s "https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid=$WECHAT_APP_ID&secret=$WECHAT_APP_SECRET")

# 检查错误
errcode=$(echo "$RESPONSE" | python3 -c "import json,sys; print(json.load(sys.stdin).get('errcode',''))" 2>/dev/null)
if [ "$errcode" != "" ] && [ "$errcode" != "0" ]; then
    echo "ERROR: 获取token失败: $RESPONSE" >&2
    exit 1
fi

# 保存缓存（有效期2小时，提前10分钟）
echo "$RESPONSE" | python3 -c "
import json, sys, time
data = json.load(sys.stdin)
data['expires_at'] = int(time.time()) + data.get('expires_in', 7200) - 600
with open('$TOKEN_CACHE', 'w') as f:
    json.dump(data, f)
print(data['access_token'])
"
