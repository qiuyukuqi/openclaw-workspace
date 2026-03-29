#!/bin/bash
# YouTube 音乐频道封面生成器
# 自动从 Pexels 下载图片 + ffmpeg 加电影感滤镜 + 歌曲名文字
# 用法: ./make_cover.sh "梦醒时分" "怀旧华语金曲" [output.png]

set -e

SONG_TITLE="${1:?用法: ./make_cover.sh 歌曲名 风格描述 [输出文件]}"
STYLE="${2:-melancholic asian beauty portrait}"
OUTPUT="${3:-/tmp/openclaw/cover_${SONG_TITLE}.png}"

WORK_DIR="/tmp/openclaw/cover_work"
mkdir -p "$WORK_DIR"

# Pexels API（免费，无需注册的 demo key）
PEXELS_API="https://api.pexels.com/v1/search"

echo "🖼️ 搜索图片: $SONG_TITLE ($STYLE)"

# 搜索图片
RESP=$(curl -s "${PEXELS_API}?query=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$STYLE portrait'))")&per_page=5&orientation=portrait" \
  -H "Authorization: $PEXELS_API_KEY")

# 如果没有 API key，用免费图库直接搜
if [ -z "$RESP" ] || echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if d.get('photos') else 1)" 2>/dev/null; then
    # 用 Pexels 免费 URL 直接下载随机图片
    PHOTO_URL=$(curl -s "${PEXELS_API}?query=$(python3 -c "import urllib.parse;print(urllib.parse.quote('$STYLE'))")&per_page=3&orientation=portrait" \
        -H "Authorization: $PEXELS_API_KEY" 2>/dev/null | python3 -c "
import sys,json,random
try:
    d=json.load(sys.stdin)
    photos=d.get('photos',[])
    if photos:
        print(random.choice(photos)['src']['large2x'])
    else:
        print('')
except: print('')
" 2>/dev/null)
fi

# 如果 Pexels 也不行，用 Unsplash Source（无需 API key）
if [ -z "$PHOTO_URL" ]; then
    echo "⚠️ Pexels 无结果，尝试 Unsplash..."
    UNSPLASH_KEYWORD=$(echo "$STYLE" | awk '{print $1,$2,$3}')
    PHOTO_URL="https://source.unsplash.com/1080x1920/?${UNSPLASH_KEYWORD},portrait,mood"
fi

if [ -z "$PHOTO_URL" ]; then
    echo "❌ 无法获取图片"
    exit 1
fi

echo "📥 下载图片..."
curl -sL -o "$WORK_DIR/photo.jpg" "$PHOTO_URL"

# 检查下载的文件
if [ ! -s "$WORK_DIR/photo.jpg" ]; then
    echo "❌ 图片下载失败"
    exit 1
fi

echo "🎨 处理封面..."

# ffmpeg 电影感处理：
# 1. 暖色调 (hue=s=0.1 加强饱和度)
# 2. 轻微暗角
# 3. 底部渐变遮罩
# 4. 歌曲名大字

# 先处理图片：裁剪+暖色+暗角
ffmpeg -y -i "$WORK_DIR/photo.jpg" \
    -vf "
        scale=1080:1920:force_original_aspect_ratio=increase,
        crop=1080:1920,
        eq=brightness=0.05:contrast=1.1:saturation=1.2,
        colorchannelmixer=rr=1.05:rg=1.02:rb=0.95:gr=1.02:gg=1.05:gb=0.95:br=0.95:bg=1.02:bb=1.1,
        vignette=angle=0:mode=forward
    " \
    "$WORK_DIR/filtered.jpg" 2>/dev/null

# 叠加底部渐变 + 歌曲名
ffmpeg -y -i "$WORK_DIR/filtered.jpg" \
    -filter_complex "
        color=c=black:s=1080x1920:d=1[bg];
        [bg][0]overlay=(W-w)/2:(H-h)/2[base];
        color=c=black:s=1080x800:d=1,
            geq=lum='p(X,Y)':a='if(between(Y,800,1920),(Y-800)/1200*0.75,0)'[grad];
        [base][grad]overlay=0:1120
    " \
    -vf "
        drawtext=text='$SONG_TITLE':
            fontfile='/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc':
            fontsize=72:
            fontcolor=white@0.9:
            borderw=3:
            bordercolor=black@0.5:
            x=(w-text_w)/2:y=1550
    " \
    "$OUTPUT" 2>/dev/null

# 清理
rm -rf "$WORK_DIR"

if [ -f "$OUTPUT" ]; then
    echo "✅ 封面已生成: $OUTPUT"
else
    echo "❌ 封面生成失败"
    exit 1
fi
