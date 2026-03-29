#!/bin/bash
# 邮件日报生成脚本 (Bash版)
# 每天7:00由cron触发，生成前一天的邮件统计报告并推送到飞书
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="$SCRIPT_DIR/../data"
LOCK_FILE="$DATA_DIR/report.lock"
ENV_FILE="$HOME/.openclaw/workspace/.env.email"
FEISHU_ACCOUNT="main"
FEISHU_USER_ID="ou_c5c98e2002a34a9b10f15fd0b6463d06"

# flock文件锁防止重复执行
exec 200>"$LOCK_FILE"
if ! flock -n 200; then
    echo "另一个日报实例正在运行，跳过" >&2
    exit 0
fi

# 加载.env.email配置
if [[ ! -f "$ENV_FILE" ]]; then
    echo "错误: 无法加载邮箱配置 $ENV_FILE" >&2
    exit 1
fi
export $(grep -v '^#' "$ENV_FILE" | grep -v '^$' | xargs)

if [[ -z "$EMAIL_IMAP_SERVER" || -z "$EMAIL_USER" || -z "$EMAIL_PASSWORD" ]]; then
    echo "错误: 邮箱配置不完整" >&2
    exit 1
fi

echo "生成邮件日报..." >&2

# 用python3单行命令获取昨天的邮件（IMAP部分）
# 输出JSON数组: [{"subject":"...","from":"..."}, ...]
emails_json=$(python3 -c "
import imaplib, ssl, email, json
from email.header import decode_header, make_header
from datetime import datetime, timedelta

def decode_str(s):
    if not s: return ''
    try: return str(make_header(decode_header(s)))
    except:
        try:
            parts = decode_header(s)
            r = []
            for p, c in parts:
                r.append(p.decode(c or 'utf-8', errors='replace') if isinstance(p, bytes) else p)
            return ''.join(r)
        except: return str(s)

import socket; socket.setdefaulttimeout(15)
ctx = ssl.create_default_context()
m = imaplib.IMAP4_SSL('${EMAIL_IMAP_SERVER}', ${EMAIL_IMAP_PORT:-993}, ssl_context=ctx)
m.login('${EMAIL_USER}', '${EMAIL_PASSWORD}')
m.select('INBOX')
y = (datetime.now() - timedelta(days=1)).strftime('%d-%b-%Y')
_, ids = m.search(None, 'ON \"%s\"' % y)
result = []
for eid in (ids[0].split() or [])[::-1]:
    _, data = m.fetch(eid, '(BODY[HEADER.FIELDS (FROM SUBJECT)])')
    raw = data[0][1].decode(errors='replace') if isinstance(data[0][1], bytes) else data[0][1]
    msg = email.message_from_string('From: a@b.com\n' + raw if 'From:' not in raw else raw)
    result.append({'subject': decode_str(msg.get('Subject','')), 'from': decode_str(msg.get('From',''))})
m.logout()
print(json.dumps(result, ensure_ascii=False))
" 2>/dev/null) || {
    echo "获取邮件失败" >&2
    emails_json="[]"
}

echo "获取到 $(echo "$emails_json" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))") 封邮件" >&2

# 生成日报文本
yesterday=$(date -d "yesterday" "+%Y年%m月%d日")
count=$(echo "$emails_json" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")

report="📊 邮件统计概览

📅 ${yesterday}
📥 昨日共计收到 ${count} 封邮件
"

if [[ "$count" -gt 0 ]]; then
    report+="邮件列表（从最新到最旧）：
────────────────────
"
    # 用python3解析JSON并格式化邮件列表
    report+=$(echo "$emails_json" | python3 -c "
import sys, json
emails = json.load(sys.stdin)
for i, em in enumerate(emails, 1):
    subj = em['subject'][:50] + '...' if len(em['subject']) > 50 else em['subject']
    print(f\"{i}. {subj}\")
    from_name = em['from'].split('<')[0].strip().strip('\"')
    if from_name:
        print(f\"   📧 {from_name}\")
")
else
    report+="📭 昨日没有收到邮件
"
fi

echo "报告内容:" >&2
echo "$report" >&2

# 推送到飞书
if openclaw message send --channel feishu --account "$FEISHU_ACCOUNT" -t "user:$FEISHU_USER_ID" -m "$report" 2>/dev/null; then
    echo "日报发送成功" >&2
else
    echo "日报发送失败" >&2
    exit 1
fi
