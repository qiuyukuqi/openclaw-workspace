#!/usr/bin/env bash
# 新闻RSS订阅 - Bash版 (替代 news_rss.py)
# 用法: news_rss.sh [--force]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="$SCRIPT_DIR/../data"
STATE_FILE="$DATA_DIR/news_state.json"
FORCE=false
[[ "${1:-}" == "--force" ]] && FORCE=true

mkdir -p "$DATA_DIR"

# 飞书配置
FEISHU_ACCOUNT="main"
FEISHU_USER_ID="ou_c5c98e2002a34a9b10f15fd0b6463d06"

# 天气配置
CITY_NAME="嘉峪关"
CITY_ID="101161401"

# 过滤关键词
FILTER_KEYWORDS="切尔西|皇马|巴萨|曼联|曼城|利物浦|阿森纳|NBA|CBA|中超|英超|西甲|意甲|德甲|法甲|娱乐|明星|综艺|电视剧|电影|歌手|游戏|电竞|直播"

# 天气代码映射
get_weather_desc() {
    local code="$1"
    case "$code" in
        00) echo "晴";; 01) echo "多云";; 02) echo "阴";; 03) echo "阵雨";; 04) echo "雷阵雨";;
        05) echo "雷阵雨伴有冰雹";; 06) echo "雨夹雪";; 07) echo "小雨";; 08) echo "中雨";;
        09) echo "大雨";; 10) echo "暴雨";; 11) echo "大暴雨";; 12) echo "特大暴雨";;
        13) echo "阵雪";; 14) echo "小雪";; 15) echo "中雪";; 16) echo "大雪";; 17) echo "暴雪";;
        18) echo "雾";; 19) echo "冻雨";; 20) echo "沙尘暴";; 21) echo "小雨转中雨";;
        22) echo "中雨转大雨";; 23) echo "大雨转暴雨";; 24) echo "暴雨转大暴雨";;
        25) echo "大暴雨转特大暴雨";; 26) echo "小雪转中雪";; 27) echo "中雪转大雪";;
        28) echo "大雪转暴雪";; 29) echo "浮尘";; 30) echo "扬沙";; 31) echo "强沙尘暴";;
        *) echo "未知";;
    esac
}

get_emoji() {
    local wt="$1"
    case "$wt" in
        *晴*) echo "☀️";;
        *多云*) echo "⛅";;
        *阴*) echo "☁️";;
        *雨*) echo "🌧️";;
        *雪*) echo "🌨️";;
        *雾*|*霾*|*扬沙*|*浮尘*) echo "🌫️";;
        *沙尘暴*) echo "🌪️";;
        *) echo "🌤️";;
    esac
}

# ==================== 天气 ====================
get_weather() {
    local url="https://d1.weather.com.cn/weather_index/${CITY_ID}.html?_=$(date +%s000)"
    local raw
    raw=$(curl -s --max-time 10 -H "User-Agent: Mozilla/5.0" -H "Referer: https://www.weather.com.cn/" "$url") || {
        echo "🌤️ 天气预报"; echo "📍 $CITY_NAME"; echo "获取失败"; return 0;
    }

    # 提取 dataSK JSON
    local sk_json
    sk_json=$(echo "$raw" | sed -n 's/.*var dataSK = \({.*}\);.*/\1/p' | head -1) || sk_json="{}"
    # 提取 fc JSON (可能跨行)
    local fc_json
    fc_json=$(echo "$raw" | grep -oP 'var fc = \K\{.*?\};' | head -1 | sed 's/;$//') || fc_json="{}"

    local city temp wind_dir wind_speed humidity time_str
    city=$(echo "$sk_json" | jq -r '.cityname // empty') || city="$CITY_NAME"
    temp=$(echo "$sk_json" | jq -r '.temp // empty') || temp="?"
    wind_dir=$(echo "$sk_json" | jq -r '.WD // empty') || wind_dir="?"
    wind_speed=$(echo "$sk_json" | jq -r '.WS // empty') || wind_speed="?"
    humidity=$(echo "$sk_json" | jq -r '.SD // empty') || humidity="?"
    time_str=$(echo "$sk_json" | jq -r '.time // empty') || time_str="??:??"

    [[ -z "$city" ]] && city="$CITY_NAME"
    [[ -z "$temp" ]] && temp="?"
    [[ -z "$wind_dir" ]] && wind_dir="?"
    [[ -z "$wind_speed" ]] && wind_speed="?"
    [[ -z "$humidity" ]] && humidity="?"
    [[ -z "$time_str" ]] && time_str="??:??"

    local realtime="📍 ${city} 实时天气（${time_str}）

🌡️ 温度: ${temp}℃
🌬️ 风向: ${wind_dir}
💨 风力: ${wind_speed}
💧 湿度: ${humidity}"

    # 5天预报
    local forecast="📅 5天预报"
    local day_names=("今天" "明天" "后天")
    local i=0
    while [ $i -lt 5 ]; do
        local fa fb fc_temp fd fi fj
        fa=$(echo "$fc_json" | jq -r ".f[$i].fa // \"00\"")
        fb=$(echo "$fc_json" | jq -r ".f[$i].fb // \"00\"")
        fc_temp=$(echo "$fc_json" | jq -r ".f[$i].fc // \"?\"")
        fd=$(echo "$fc_json" | jq -r ".f[$i].fd // \"?\"")
        fi=$(echo "$fc_json" | jq -r ".f[$i].fi // \"\"")
        fj=$(echo "$fc_json" | jq -r ".f[$i].fj // \"\"")

        local w_day w_night w_type
        w_day=$(get_weather_desc "$fa")
        w_night=$(get_weather_desc "$fb")
        if [[ "$w_day" == "$w_night" || -z "$w_night" ]]; then
            w_type="$w_day"
        else
            w_type="${w_day}转${w_night}"
        fi

        local emoji
        emoji=$(get_emoji "$w_type")

        local day_desc
        if [ $i -lt 3 ]; then
            day_desc="${day_names[$i]} ${fi}"
        elif [[ -n "$fj" ]]; then
            day_desc="${fj} ${fi}"
        else
            day_desc="第$((i+1))天 ${fi}"
        fi

        forecast+="\n${day_desc} ${emoji} ${w_type} ${fd} 至 ${fc_temp}℃"
        ((i++)) || true
    done

    echo -e "${realtime}\n\n${forecast}"
}

# ==================== 新闻抓取 ====================
fetch_sina_world() {
    local html
    html=$(curl -s --max-time 30 -H "User-Agent: Mozilla/5.0" "https://news.sina.com.cn/world/") || return 1
    echo "$html" | grep -oP '<a[^>]+href="[^"]*news\.sina\.com\.cn[^"]*"[^>]*>\K[^<]+' | \
        sed 's/&nbsp;/ /g' | while IFS= read -r title; do
            title=$(echo "$title" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            [[ -n "$title" && ${#title} -gt 5 ]] && echo "$title"
        done | grep -vE "$FILTER_KEYWORDS" | head -10
}

fetch_ithome_rss() {
    local xml
    xml=$(curl -s --max-time 30 -H "User-Agent: Mozilla/5.0" "https://www.ithome.com/rss/") || return 1
    echo "$xml" | xmllint --xpath '//item/title/text()' - 2>/dev/null | while IFS= read -r line; do
        title=$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        [[ -n "$title" ]] && echo "$title"
    done | grep -vE "$FILTER_KEYWORDS" | head -10
}

# ==================== 去重 ====================
load_state() {
    if [[ -f "$STATE_FILE" ]]; then
        # 只保留今天的记录，昨天的自动清除
        local today
        today=$(date "+%Y-%m-%d")
        cat "$STATE_FILE" | jq --arg today "$today" 'to_entries | map(select(.value | startswith($today))) | from_entries'
    else
        echo '{}'
    fi
}

is_sent() {
    local news_id="$1"
    local state="$2"
    echo "$state" | jq -r --arg id "$news_id" '.[$id] // empty' | grep -q .
}

mark_sent() {
    local news_id="$1"
    local state="$2"
    local now_ts
    now_ts=$(date -Iseconds)
    echo "$state" | jq --arg id "$news_id" --arg ts "$now_ts" '. + {($id): $ts}'
}

# ==================== 主逻辑 ====================
main() {
    local now_time now_date now_weekday time_hm
    now_time=$(date "+%Y年%m月%d日")
    time_hm=$(date "+%H:%M")
    now_weekday=$(date "+%A" | sed 's/Monday/星期一/;s/Tuesday/星期二/;s/Wednesday/星期三/;s/Thursday/星期四/;s/Friday/星期五/;s/Saturday/星期六/;s/Sunday/星期日/')

    local weather
    weather=$(get_weather)

    local separator="──────────────────────────────"
    local report="📰 每日新闻简报
📅 ${now_time} ${now_weekday} ${time_hm}
${separator}
${weather}
${separator}

"

    local state new_count=0
    state=$(load_state)

    # 国际新闻
    report+="【国际新闻】\n"
    local titles count=0
    titles=$(fetch_sina_world) || titles=""
    while IFS= read -r title; do
        [[ $count -ge 5 ]] && break
        [[ -z "$title" ]] && continue
        local news_id
        news_id=$(echo -n "国际新闻${title}" | md5sum | cut -c1-12)
        if $FORCE || ! is_sent "$news_id" "$state"; then
            report+="${count}. ${title}\n"
            state=$(mark_sent "$news_id" "$state")
            ((count++)) || true
            ((new_count++)) || true
        fi
    done <<< "$titles"
    [[ $count -eq 0 ]] && report+="暂无新内容\n"
    report+="\n"

    # IT简报
    report+="【IT简报】\n"
    count=0
    titles=$(fetch_ithome_rss) || titles=""
    while IFS= read -r title; do
        [[ $count -ge 5 ]] && break
        [[ -z "$title" ]] && continue
        local news_id
        news_id=$(echo -n "IT简报${title}" | md5sum | cut -c1-12)
        if $FORCE || ! is_sent "$news_id" "$state"; then
            report+="${count}. ${title}\n"
            state=$(mark_sent "$news_id" "$state")
            ((count++)) || true
            ((new_count++)) || true
        fi
    done <<< "$titles"
    [[ $count -eq 0 ]] && report+="暂无新内容\n"
    report+="\n${separator}"

    # 保存状态
    state=$(echo "$state" | jq -c 'to_entries | sort_by(.value) | reverse | .[0:500] | from_entries')
    echo "$state" | jq '.' > "$STATE_FILE"

    # 发送
    if $FORCE || [[ $new_count -gt 0 ]]; then
        echo -e "$report" | openclaw message send --channel feishu --account "$FEISHU_ACCOUNT" -t "user:$FEISHU_USER_ID" -m -
        if [[ $? -eq 0 ]]; then
            echo "已发送 $new_count 条新闻" >&2
        else
            echo "飞书推送失败" >&2
            exit 1
        fi
    else
        echo "没有新新闻" >&2
    fi
}

main
