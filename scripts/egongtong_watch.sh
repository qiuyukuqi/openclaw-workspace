#!/bin/bash
# 易工通自动挂机 + 人脸识别检测
# 每隔10秒检查页面，发现人脸识别弹窗则截图通知飞书

SCREENSHOT="/tmp/egongtong_face.png"
LOG="/root/.openclaw/workspace/scripts/egongtong_watch.log"
USER_ID="ou_c5c98e2002a34a9b10f15fd0b6463d06"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG"; }

# 发飞书通知+图片
notify_with_image() {
    local msg="$1"
    local img="$2"
    # 先发文字
    openclaw message send --channel feishu --account main -t "user:$USER_ID" -m "$msg" 2>/dev/null
    # 再发图片
    openclaw message send --channel feishu --account main -t "user:$USER_ID" -m "$msg" --media "$img" 2>/dev/null
}

# 检查是否有弹窗（人脸识别/二维码相关元素）
check_popup() {
    agent-browser snapshot -c 2>&1
}

# 保持视频播放
keep_alive() {
    agent-browser eval "
    (function(){
        var v = document.querySelector('video');
        if(v && v.paused) v.play();
        // 模拟页面活跃
        document.dispatchEvent(new Event('mousemove'));
        document.dispatchEvent(new Event('focus'));
        return 'ok';
    })()
    " 2>/dev/null
}

log "易工通挂机监控启动"

while true; do
    # 保持视频播放
    keep_alive
    
    # 检查页面状态
    snapshot=$(check_popup)
    
    # 检测人脸识别/二维码弹窗关键词
    if echo "$snapshot" | grep -qi "人脸\|识别\|扫码\|二维码\|face\|verify\|验证"; then
        log "⚠️ 检测到人脸识别弹窗！"
        agent-browser screenshot "$SCREENSHOT" 2>/dev/null
        notify_with_image "⚠️ 易工通人脸识别验证！请扫描二维码完成验证" "$SCREENSHOT"
        log "已发送通知，等待用户扫码..."
        # 等待60秒让用户扫码
        sleep 60
        log "等待完成，继续监控"
    fi
    
    # 检测视频是否结束
    video_status=$(agent-browser eval "
    (function(){
        var v = document.querySelector('video');
        if(!v) return 'no_video';
        return v.ended ? 'ended' : 'playing_' + Math.floor(v.currentTime) + 's';
    })()
    " 2>/dev/null)
    
    if echo "$video_status" | grep -q "ended"; then
        log "📺 当前视频播放结束"
        # 截图看看页面状态
        agent-browser screenshot "/tmp/egongtong_next.png" 2>/dev/null
        notify_with_image "📺 当前视频已播放完成，请检查下一节" "/tmp/egongtong_next.png"
        sleep 30
    fi
    
    # 每30秒记录一次进度
    if echo "$video_status" | grep -q "playing_"; then
        progress=$(echo "$video_status" | grep -oP 'playing_\K\d+')
        log "▶️ 播放进度: ${progress}s"
    fi
    
    sleep 10
done
