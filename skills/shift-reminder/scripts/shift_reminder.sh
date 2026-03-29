#!/usr/bin/env bash
# 倒班提醒脚本 (纯 Bash + curl + jq)
# 周期：4天一轮（夜班 -> 下夜班+休息 -> 休息 -> 白班）
# 起始：2026年2月13日(周五)夜班

set -euo pipefail

LOCK_FILE="/tmp/shift_reminder.lock"
DATA_DIR="$(cd "$(dirname "$0")/../data" && pwd)"
MEMORY_FILE="$DATA_DIR/sent_reminders.json"
CONFIG_FILE="/root/.openclaw/openclaw.json"
FEISHU_OPEN_ID="ou_c5c98e2002a34a9b10f15fd0b6463d06"
START_EPOCH=$(( $(date -u -d '2026-02-13 00:00:00 +08:00' +%s) ))

# 获取班次 (1-4)
get_shift_day() {
    local date_epoch="$1" # 该天 00:00:00 北京时间对应的 epoch
    local diff=$(( (date_epoch - START_EPOCH) / 86400 ))
    echo $(( (diff % 4 + 4) % 4 + 1 ))
}

# 判断周末 (周五5/周六6/周日0)
is_weekend() {
    local dow="$1" # date +%w
    [[ "$dow" == "0" || "$dow" == "5" || "$dow" == "6" ]]
}

# 格式化日期
fmt_date() { date -d "@$1" "+%Y-%m-%d" 2>/dev/null || date -r "$1" "+%Y-%m-%d" 2>/dev/null; }

# 获取北京时间信息
get_beijing_info() {
    #TZ=Asia/Shanghai date 等效
    TZ=Asia/Shanghai date "+%Y-%m-%d %H:%M %w"
}

# 获取班次详情 -> 输出: shift_day|name|work_day|reminder_time,type,msg|reminder_time2,type2,msg2
get_shift_info() {
    local date_epoch="$1"
    local dow="$2"
    local shift_day
    shift_day=$(get_shift_day "$date_epoch")

    case "$shift_day" in
        1) # 夜班
            if is_weekend "$dow"; then
                echo "1|夜班|1|19:50,上班,⏰ 夜班上班了，抓紧刷脸！"
            else
                echo "1|夜班|1|19:20,上班,⏰ 夜班上班了，抓紧刷脸！"
            fi
            ;;
        2) # 下夜班+休息
            echo "2|下夜班+休息|0|08:50,下班,🌅 下班了，抓紧刷脸！"
            ;;
        3) # 休息
            echo "3|休息|0|"
            ;;
        4) # 白班
            echo "4|白班|1|07:50,上班,⏰ 白班上班了，抓紧刷脸！|20:50,下班,🌙 下班了，抓紧刷脸！"
            ;;
    esac
}

# 获取飞书 token
get_feishu_token() {
    local app_id app_secret
    app_id=$(jq -r '.channels.feishu.accounts.main.appId' "$CONFIG_FILE")
    app_secret=$(jq -r '.channels.feishu.accounts.main.appSecret' "$CONFIG_FILE")
    local resp
    resp=$(curl -s -X POST 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal' \
        -H 'Content-Type: application/json' \
        -d "{\"app_id\":\"$app_id\",\"app_secret\":\"$app_secret\"}")
    echo "$resp" | jq -r '.tenant_access_token // empty'
}

# 发送飞书消息
send_feishu_msg() {
    local token="$1" text="$2"
    local resp
    resp=$(curl -s -X POST 'https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id' \
        -H "Authorization: Bearer $token" \
        -H 'Content-Type: application/json' \
        -d "{\"receive_id\":\"$FEISHU_OPEN_ID\",\"msg_type\":\"text\",\"content\":\"$(echo -n "$text" | jq -Rs .)\"}")
    echo "$resp" | jq -r '.code // -1'
}

# 读取已发送记录的时间戳 (毫秒)
get_sent_time() {
    local key="$1"
    if [[ -f "$MEMORY_FILE" ]]; then
        jq -r --arg k "$key" '.[$k] // 0' "$MEMORY_FILE" 2>/dev/null || echo 0
    else
        echo 0
    fi
}

# 保存已发送记录
save_sent() {
    local key="$1" ts="$2"
    mkdir -p "$DATA_DIR"
    local tmp
    tmp=$(mktemp)
    if [[ -f "$MEMORY_FILE" ]]; then
        jq --arg k "$key" --argjson v "$ts" '.[$k] = $v' "$MEMORY_FILE" > "$tmp" 2>/dev/null || echo "{\"$key\":$ts}" > "$tmp"
    else
        echo "{\"$key\":$ts}" > "$tmp"
    fi
    mv "$tmp" "$MEMORY_FILE"
}

# === test 模式 ===
do_test() {
    echo "=== 倒班日历 ==="
    echo ""
    local day_names=("日" "一" "二" "三" "四" "五" "六")
    for i in $(seq 0 7); do
        local d_epoch dow date_str
        d_epoch=$(TZ=Asia/Shanghai date -d "+${i} days" +%s)
        # 获取当天 00:00 北京时间的 epoch (近似: 用 date 算日期再转)
        date_str=$(TZ=Asia/Shanghai date -d "+${i} days" "+%Y-%m-%d")
        dow=$(TZ=Asia/Shanghai date -d "+${i} days" +%w)
        d_epoch=$(TZ=Asia/Shanghai date -d "$date_str 00:00:00" +%s)

        local info shift_day name rest
        info=$(get_shift_info "$d_epoch" "$dow")
        shift_day=$(echo "$info" | cut -d'|' -f1)
        name=$(echo "$info" | cut -d'|' -f2)
        rest=$(echo "$info" | cut -d'|' -f4-)

        local line="${date_str} 周${day_names[$dow]} - 第${shift_day}天 ${name}"
        if [[ -n "$rest" && "$rest" != " " ]]; then
            local times=""
            IFS='|' read -ra reminders <<< "$rest"
            for r in "${reminders[@]}"; do
                [[ -n "$r" ]] && times="${times}$(echo "$r" | cut -d',' -f1), "
            done
            times="${times%, }"
            [[ -n "$times" ]] && line+=" [${times}]"
        fi
        echo "$line"
    done
}

# === status 模式 ===
do_status() {
    local date_str hour_min dow now_epoch
    read -r date_str hour_min dow <<< "$(TZ=Asia/Shanghai date '+%Y-%m-%d %H:%M %w')"
    local now_epoch
    now_epoch=$(TZ=Asia/Shanghai date -d "$date_str 00:00:00" +%s)

    local info shift_day name work_day rest
    info=$(get_shift_info "$now_epoch" "$dow")
    shift_day=$(echo "$info" | cut -d'|' -f1)
    name=$(echo "$info" | cut -d'|' -f2)
    work_day=$(echo "$info" | cut -d'|' -f3)
    rest=$(echo "$info" | cut -d'|' -f4-)

    echo ""
    echo "📅 今天: $date_str"
    echo "班次: 第${shift_day}天 - $name"
    if [[ "$work_day" == "1" ]]; then
        echo "是否上班: 是"
    else
        echo "是否上班: 否"
    fi

    if [[ -n "$rest" && "$rest" != " " ]]; then
        echo "提醒:"
        IFS='|' read -ra reminders <<< "$rest"
        for r in "${reminders[@]}"; do
            [[ -n "$r" ]] && echo "  $(echo "$r" | cut -d',' -f1) $(echo "$r" | cut -d',' -f2): $(echo "$r" | cut -d',' -f3-)"
        done
    fi
}

# === 主逻辑 ===
do_main() {
    local date_str hour_min dow now_epoch now_ms
    read -r date_str hour_min dow <<< "$(TZ=Asia/Shanghai date '+%Y-%m-%d %H:%M %w')"
    now_ms=$(date +%s%3N 2>/dev/null || python3 -c 'import time;print(int(time.time()*1000))')
    now_epoch=$(TZ=Asia/Shanghai date -d "$date_str 00:00:00" +%s)

    local hour minute
    hour=${hour_min:0:2}
    minute=${hour_min:3:2}
    local current_time="${hour_min}"

    echo "[${date_str} ${current_time}] 检查倒班提醒..."

    local info shift_day name rest
    info=$(get_shift_info "$now_epoch" "$dow")
    shift_day=$(echo "$info" | cut -d'|' -f1)
    name=$(echo "$info" | cut -d'|' -f2)
    rest=$(echo "$info" | cut -d'|' -f4-)

    echo "今天: 第${shift_day}天 - ${name}"

    if [[ -z "$rest" || "$rest" == " " ]]; then
        return 0
    fi

    IFS='|' read -ra reminders <<< "$rest"
    for r in "${reminders[@]}"; do
        [[ -z "$r" ]] && continue

        local r_time r_type r_msg
        r_time=$(echo "$r" | cut -d',' -f1)
        r_type=$(echo "$r" | cut -d',' -f2)
        r_msg=$(echo "$r" | cut -d',' -f3-)

        # 时间比较
        local rh=${r_time:0:2} rm=${r_time:3:2}
        local r_total=$(( 10#$rh * 60 + 10#$rm ))
        local n_total=$(( 10#$hour * 60 + 10#$minute ))
        local diff=$(( n_total - r_total ))
        if [[ $diff -lt 0 ]]; then diff=$((-diff)); fi

        if [[ $diff -le 1 ]]; then
            local key="${date_str}-${r_time}-${r_type}"
            local sent_ts
            sent_ts=$(get_sent_time "$key")
            local elapsed=$(( now_ms - sent_ts ))

            if [[ "$elapsed" -lt 600000 ]]; then
                echo "已发送过: ${r_type} ${r_time}"
                continue
            fi

            echo "发送提醒: ${r_msg}"
            local token
            token=$(get_feishu_token)
            if [[ -z "$token" ]]; then
                echo "无法获取 Token"
                continue
            fi

            local code
            code=$(send_feishu_msg "$token" "$r_msg")
            if [[ "$code" == "0" ]]; then
                save_sent "$key" "$now_ms"
                echo "✅ 已发送: ${key}"
            else
                echo "✗ 发送失败: code=$code"
            fi
        fi
    done
}

# === 入口 ===
exec 200>"$LOCK_FILE"
flock -n 200 || { echo "另一个实例正在运行"; exit 0; }

case "${1:-}" in
    test)   do_test ;;
    status) do_status ;;
    *)      do_main ;;
esac
