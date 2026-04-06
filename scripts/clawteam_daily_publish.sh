#!/bin/bash
# ClawTeam 多Agent每日公众号涨粉流程
# 用法: bash clawteam_daily_publish.sh [--step scout|write|distribute|publish]
# 默认执行完整流程

set -e

WORKSPACE="$HOME/.openclaw/workspace"
TEAM_NAME="wechat-growth"
DATA_DIR="/tmp/openclaw/wechat-publisher/cross-platform"
TODAY=$(date +%Y%m%d)

mkdir -p "$DATA_DIR"

# 检查clawteam是否可用
if ! command -v clawteam &> /dev/null; then
    echo "❌ clawteam 未安装，请先运行: pip install -e /tmp/ClawTeam-OpenClaw"
    exit 1
fi

# 检查tmux
if ! tmux has-session -t clawteam 2>/dev/null; then
    tmux new-session -d -s clawteam -x 200 -y 50
    echo "✅ 创建 tmux session: clawteam"
fi

STEP="${1:-all}"

case "$STEP" in
    scout)
        echo "🚀 Step 1: 启动Scout Agent选题..."
        clawteam spawn tmux openclaw --team "$TEAM_NAME" \
            --agent-name scout \
            --task "你是科技热点选题猎手。请搜索今天（$(date +%Y-%m-%d)）的AI/科技领域热点新闻，输出5个候选选题。

每个选题格式：
标题：xxx
角度：xxx（独特的切入角度）
热度：x/10
实操价值：x/10
推荐理由：一句话

输出后，用 clawteam inbox send $TEAM_NAME leader 发送结果给leader。

最后用 clawteam task create $TEAM_NAME --title '今日选题' --owner scout 记录任务。"
        
        echo "📋 Scout已启动，在tmux窗口中查看进度"
        echo "👉 tmux attach -t clawteam"
        ;;
        
    write)
        echo "✍️ Step 2: 启动Writer Agent写作..."
        TOPIC="${2:-AI/科技最新热点}"
        
        clawteam spawn tmux openclaw --team "$TEAM_NAME" \
            --agent-name writer \
            --task "你是资深科技自媒体写手。请围绕以下选题写一篇2000字左右的微信公众号文章：

选题：$TOPIC
要求：
1. 开头3句话抓住读者（制造好奇/反差/共鸣）
2. 3-4个小标题，每个小标题是一个独立观点
3. 观点犀利，有明确立场和判断，不怕得罪人
4. 不要只是搬运新闻，要有深度分析
5. 结尾引导关注公众号「别动我在debug」
6. 适合手机阅读，段落简短
7. 禁止自编公众号名，必须是「别动我在debug」

写完后：
1. 保存到 /tmp/openclaw/wechat-publisher/drafts/article_${TODAY}.md
2. 用 clawteam inbox send $TEAM_NAME leader 通知完成"

        echo "✍️ Writer已启动"
        echo "👉 tmux attach -t clawteam"
        ;;
        
    distribute)
        echo "📢 Step 3: 启动Distributor Agent跨平台改编..."
        ARTICLE="${2:-/tmp/openclaw/wechat-publisher/drafts/article_${TODAY}.md}"
        
        if [ ! -f "$ARTICLE" ]; then
            echo "❌ 文章不存在: $ARTICLE"
            echo "请先执行 write 步骤"
            exit 1
        fi
        
        CONTENT=$(cat "$ARTICLE")
        
        clawteam spawn tmux openclaw --team "$TEAM_NAME" \
            --agent-name distributor \
            --task "你是内容分发专家。请将以下文章改编为3个平台的版本，保存到对应文件：

原文：
$(head -20 "$ARTICLE")
...（完整文章请读取 $ARTICLE）

输出要求：
1. 知乎回答版 → /tmp/openclaw/wechat-publisher/cross-platform/zhihu_${TODAY}.md
   - 1000-1500字，问答格式
   - 开头直接给出核心观点
   - 文末加：'更多科技前沿解读，关注公众号【别动我在debug】'
   
2. 小红书图文版 → /tmp/openclaw/wechat-publisher/cross-platform/xiaohongshu_${TODAY}.md
   - 300-500字
   - 标题格式：数字+情绪词（如'5个AI工具，第3个绝了'）
   - 列表体，适合配图
   - 文末引导关注
   
3. 头条号文章版 → /tmp/openclaw/wechat-publisher/cross-platform/toutiao_${TODAY}.md
   - 原文基础上优化SEO标题
   - 保持2000字左右
   - 标题嵌入搜索关键词

全部完成后用 clawteam inbox send $TEAM_NAME leader 通知。"

        echo "📢 Distributor已启动"
        echo "👉 tmux attach -t clawteam"
        ;;
        
    publish)
        echo "📤 Step 4: 发布到微信公众号..."
        cd "$WORKSPACE"
        python3 skills/wechat-publisher/scripts/pipeline.py --auto --step publish
        echo "✅ 公众号发布完成"
        
        echo ""
        echo "📋 跨平台分发内容（需手动发布）："
        for platform in zhihu xiaohongshu toutiao; do
            f="$DATA_DIR/${platform}_${TODAY}.md"
            if [ -f "$f" ]; then
                echo "  ✅ $platform: $f"
            else
                echo "  ⏳ $platform: 未生成"
            fi
        done
        ;;
        
    board)
        echo "📊 打开ClawTeam看板..."
        clawteam board attach "$TEAM_NAME"
        ;;
        
    all)
        echo "🚀 启动完整每日流程..."
        echo "==============================="
        echo "Step 1: Scout选题"
        echo "Step 2: Writer写作"  
        echo "Step 3: Distributor跨平台改编"
        echo "Step 4: 自动发布公众号"
        echo "==============================="
        echo ""
        
        # 按顺序启动（实际可以并行scout，等scout完再启动writer+distributor）
        echo "🔄 创建团队..."
        clawteam team spawn-team "$TEAM_NAME" -d "每日公众号涨粉内容生产" -n leader
        
        echo ""
        echo "🚀 启动Scout选题..."
        "$0" scout
        
        echo ""
        echo "⏳ 等待Scout完成选题后，执行以下命令继续："
        echo "  $0 write '选定的选题标题'"
        echo "  $0 distribute"
        echo "  $0 publish"
        echo ""
        echo "📊 查看进度: tmux attach -t clawteam"
        echo "📊 查看看板: $0 board"
        ;;
        
    *)
        echo "用法: $0 [scout|write|distribute|publish|board|all]"
        echo ""
        echo "  scout       - 启动选题Agent"
        echo "  write [选题] - 启动写作Agent"
        echo "  distribute  - 启动跨平台分发Agent"
        echo "  publish     - 发布到公众号"
        echo "  board       - 打开看板监控"
        echo "  all         - 完整流程"
        exit 1
        ;;
esac
