#!/usr/bin/env python3
"""
新闻RSS订阅 - 简洁版
国际新闻：新浪国际
IT简报：IT之家
"""

import os
import sys
import json
import hashlib
import subprocess
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import re
from datetime import datetime, timedelta
from pathlib import Path

# 配置
CONFIG_DIR = Path(__file__).parent.parent / "data"
STATE_FILE = CONFIG_DIR / "news_state.json"

# 飞书配置
FEISHU_ACCOUNT = "main"
FEISHU_USER_ID = "ou_c5c98e2002a34a9b10f15fd0b6463d06"

# 天气配置
WEATHER_LOCATION = "嘉峪关"
WEATHER_CITY_ID = "101161401"  # 嘉峪关城市ID (中国天气网)

# RSS源（支持RSS和网页）
SOURCES = {
    "国际新闻": "https://news.sina.com.cn/world/",
    "IT简报": "https://www.ithome.com/rss/"
}

# 新闻过滤关键词（排除这些）
NEWS_FILTER = [
    "切尔西", "皇马", "巴萨", "曼联", "曼城", "利物浦", "阿森纳",
    "NBA", "CBA", "中超", "英超", "西甲", "意甲", "德甲", "法甲",
    "娱乐", "明星", "综艺", "电视剧", "电影", "歌手",
    "游戏", "电竞", "直播"
]


def load_state():
    """加载已处理的新闻ID"""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {}


def save_state(state):
    """保存状态"""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_weather():
    """获取天气预报（中国天气网官方数据）"""
    try:
        import re as re_module
        
        # 中国天气网官方API
        url = f"https://d1.weather.com.cn/weather_index/{WEATHER_CITY_ID}.html?_={int(datetime.now().timestamp()*1000)}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.weather.com.cn/"
        })
        with urllib.request.urlopen(req, timeout=10) as response:
            text = response.read().decode("utf-8")
        
        # 解析JSONP数据
        def extract_var(var_name):
            marker = f'var {var_name} ='
            if marker not in text:
                return {}
            start = text.index(marker) + len(marker)
            brace_count = 0
            end = start
            for i, c in enumerate(text[start:]):
                if c == '{':
                    brace_count += 1
                elif c == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end = start + i + 1
                        break
            try:
                return json.loads(text[start:end])
            except:
                return {}
        
        dataSK = extract_var("dataSK")
        fc_data = extract_var("fc")
        
        # 实时天气
        city = dataSK.get("cityname", WEATHER_LOCATION)
        temp = dataSK.get("temp", "?")
        wind_dir = dataSK.get("WD", "?")
        wind_speed = dataSK.get("WS", "?")
        humidity = dataSK.get("SD", "?")
        time_str = dataSK.get("time", "??:??")
        
        # 天气emoji映射
        weather_emoji = {
            "晴": "☀️", "多云": "⛅", "阴": "☁️", "小雨": "🌧️", "中雨": "🌧️",
            "大雨": "🌧️", "暴雨": "⛈️", "雷阵雨": "⛈️", "小雪": "🌨️", "中雪": "🌨️",
            "大雪": "❄️", "暴雪": "❄️", "雨夹雪": "🌨️", "雾": "🌫️", "霾": "🌫️",
            "扬沙": "🌫️", "浮尘": "🌫️", "沙尘暴": "🌪️", "雪": "🌨️"
        }
        
        # 天气代码映射
        weather_codes = {
            "00": "晴", "01": "多云", "02": "阴", "03": "阵雨", "04": "雷阵雨",
            "05": "雷阵雨伴有冰雹", "06": "雨夹雪", "07": "小雨", "08": "中雨",
            "09": "大雨", "10": "暴雨", "11": "大暴雨", "12": "特大暴雨",
            "13": "阵雪", "14": "小雪", "15": "中雪", "16": "大雪", "17": "暴雪",
            "18": "雾", "19": "冻雨", "20": "沙尘暴", "21": "小雨转中雨",
            "22": "中雨转大雨", "23": "大雨转暴雨", "24": "暴雨转大暴雨",
            "25": "大暴雨转特大暴雨", "26": "小雪转中雪", "27": "中雪转大雪",
            "28": "大雪转暴雪", "29": "浮尘", "30": "扬沙", "31": "强沙尘暴"
        }
        
        def get_emoji(weather_type):
            for k, v in weather_emoji.items():
                if k in weather_type:
                    return v
            return "🌤️"
        
        # 构建实时天气
        realtime = f"""📍 {city} 实时天气（{time_str}）

🌡️ 温度: {temp}℃
🌬️ 风向: {wind_dir}
💨 风力: {wind_speed}
💧 湿度: {humidity}"""
        
        # 构建5天预报
        forecast_list = fc_data.get("f", [])
        forecast_lines = []
        day_names = ["今天", "明天", "后天"]
        
        for i, day in enumerate(forecast_list[:5]):
            fa = day.get("fa", "00")
            fb = day.get("fb", "00")
            fc = day.get("fc", "?")
            fd = day.get("fd", "?")
            fi = day.get("fi", "")
            fj = day.get("fj", "")
            
            weather_day = weather_codes.get(fa, "未知")
            weather_night = weather_codes.get(fb, "")
            
            if weather_day == weather_night or not weather_night:
                weather_type = weather_day
            else:
                weather_type = f"{weather_day}转{weather_night}"
            
            emoji = get_emoji(weather_type)
            
            if i < 3:
                day_desc = f"{day_names[i]} {fi}"
            else:
                day_desc = f"{fj} {fi}" if fj else f"第{i+1}天 {fi}"
            
            forecast_lines.append(f"{day_desc} {emoji} {weather_type} {fd} 至 {fc}℃")
        
        output = realtime + "\n\n📅 5天预报\n" + "\n".join(forecast_lines)
        return output
        
    except Exception as e:
        print(f"获取天气失败: {e}", file=sys.stderr)
        return f"🌤️ 天气预报\n📍 {WEATHER_LOCATION}\n获取失败"


def fetch_feed(url):
    """获取RSS/Atom内容"""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.read().decode("utf-8")
    except Exception as e:
        print(f"获取失败 {url}: {e}", file=sys.stderr)
        return None


def is_valid_news(title):
    """过滤无效新闻（体育、娱乐、游戏等）"""
    for keyword in NEWS_FILTER:
        if keyword in title:
            return False
    return True

def parse_feed(xml_content, url=""):
    """解析RSS/Atom/HTML，返回标题列表"""
    items = []
    try:
        # 判断是RSS还是HTML
        if xml_content.strip().startswith("<?xml") or "<rss" in xml_content[:100]:
            # RSS/Atom格式
            root = ET.fromstring(xml_content)
            
            # RSS格式
            for item in root.findall(".//item"):
                title_elem = item.find("title")
                if title_elem is not None and title_elem.text:
                    title = re.sub(r'<[^>]+>', '', title_elem.text).strip()
                    if title and is_valid_news(title):
                        items.append(title)
            
            # Atom格式
            for entry in root.findall(".//{http://www.w3.org/2005/Atom}entry"):
                title_elem = entry.find("{http://www.w3.org/2005/Atom}title")
                if title_elem is not None and title_elem.text:
                    title = re.sub(r'<[^>]+>', '', title_elem.text).strip()
                    if title and is_valid_news(title):
                        items.append(title)
            
            # 通用entry
            for entry in root.findall(".//entry"):
                title_elem = entry.find("title")
                if title_elem is not None and title_elem.text:
                    title = re.sub(r'<[^>]+>', '', title_elem.text).strip()
                    if title and is_valid_news(title):
                        items.append(title)
        else:
            # HTML格式（新浪新闻）
            # 匹配新闻标题链接
            titles = re.findall(r'<a[^>]+href="[^"]*news\.sina\.com\.cn[^"]*"[^>]*>([^<]+)</a>', xml_content)
            for title in titles:
                title = title.strip()
                if title and len(title) > 5 and is_valid_news(title):
                    items.append(title)
                    
    except Exception as e:
        print(f"解析失败: {e}", file=sys.stderr)
    
    return items


def send_to_feishu(message):
    """发送到飞书"""
    try:
        result = subprocess.run(
            [
                "openclaw", "message", "send",
                "--channel", "feishu",
                "--account", FEISHU_ACCOUNT,
                "-t", f"user:{FEISHU_USER_ID}",
                "-m", message
            ],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            print(f"飞书推送失败: {result.stderr}", file=sys.stderr)
            return False
        print("飞书推送成功", file=sys.stderr)
        return True
    except Exception as e:
        print(f"飞书推送失败: {e}", file=sys.stderr)
        return False


def main():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    state = load_state()
    
    now = datetime.now()
    date_str = now.strftime("%Y年%m月%d日")
    time_str = now.strftime("%H:%M")
    weekday = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][now.weekday()]
    
    # 获取天气
    weather = get_weather()
    
    # 生成简报
    report = f"📰 每日新闻简报\n"
    report += f"📅 {date_str} {weekday} {time_str}\n"
    report += "─" * 30 + "\n"
    report += f"{weather}\n"
    report += "─" * 30 + "\n\n"
    
    new_count = 0
    
    for category, url in SOURCES.items():
        report += f"【{category}】\n"
        
        xml_content = fetch_feed(url)
        if not xml_content:
            report += "获取失败\n\n"
            continue
        
        items = parse_feed(xml_content, url)
        
        count = 0
        for title in items:
            if count >= 5:
                break
            
            # 生成唯一ID
            news_id = hashlib.md5(f"{category}{title}".encode()).hexdigest()[:12]
            
            # 检查是否已发送
            if news_id in state:
                continue
            
            report += f"{count + 1}. {title}\n"
            state[news_id] = now.isoformat()
            count += 1
            new_count += 1
        
        if count == 0:
            report += "暂无新内容\n"
        
        report += "\n"
    
    report += "─" * 30
    
    # 限制状态大小
    if len(state) > 500:
        sorted_items = sorted(state.items(), key=lambda x: x[1], reverse=True)[:500]
        state = dict(sorted_items)
    
    save_state(state)
    
    # 发送
    if new_count > 0:
        if send_to_feishu(report):
            print(f"已发送 {new_count} 条新闻", file=sys.stderr)
    else:
        print("没有新新闻", file=sys.stderr)


if __name__ == "__main__":
    main()
