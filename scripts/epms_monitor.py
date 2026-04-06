#!/usr/bin/env python3
"""
EPMS 排放数据监控脚本
监控多个设备排放数据，异常时飞书通知
"""

import json
import time
import hashlib
import requests
import subprocess
import sys
import os
from datetime import datetime, timedelta

# ============ 配置区 ============
API_BASE = "http://60.164.184.43:17641"
ACCOUNT = "00008323"
PASSWORD_MD5 = "df66717d95cbcea8e2fe13ef3ed23b21"

# 监控设备列表
DEVICES = [
    {
        "code": "TSP_347",
        "type": "tsp",
        "name": "TSP_347（可逆皮带）",
        "thresholds": {"TSP": 400},
        "monitor_fields": ["TSP"],
    },
    {
        "code": "TSP_346",
        "type": "tsp",
        "name": "TSP_346（给煤机皮带）",
        "thresholds": {"TSP": 400},
        "monitor_fields": ["TSP"],
    },
]

# 数据中断告警（分钟）
NO_DATA_TIMEOUT = 4  # 超过4分钟没新数据就告警

# 检查间隔（秒）
CHECK_INTERVAL = 10

# 飞书配置（从环境变量或配置文件读取）
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK", "")

# 状态文件
STATE_FILE = os.path.join(os.path.dirname(__file__), "epms_monitor_state.json")

# 防止重复告警冷却期（秒）
ALERT_COOLDOWN = 1800  # 同类告警30分钟内不重复

# ============ 全局变量 ============
token = ""
token_expire = 0

def login():
    """登录获取token"""
    global token, token_expire
    try:
        resp = requests.post(f"{API_BASE}/api/base/SysLogin/LoginWithoutCode",
            json={"account": ACCOUNT, "password": PASSWORD_MD5},
            timeout=10)
        data = resp.json()
        if data.get("ResultType") == 200 and data.get("Data", {}).get("Token"):
            token = data["Data"]["Token"]
            token_expire = time.time() + 50  # token有效期约60秒，提前刷新
            return True
        else:
            print(f"[{now()}] 登录失败: {data.get('Message')}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"[{now()}] 登录异常: {e}", file=sys.stderr)
        return False

def get_auth():
    """获取有效token"""
    if not token or time.time() > token_expire:
        if not login():
            return None
    return token

def fetch_data(device):
    """获取指定设备最新排放数据"""
    auth = get_auth()
    if not auth:
        return None
    
    try:
        resp = requests.post(
            f"{API_BASE}/api/EPMS/Emission/History/QueryByPage",
            headers={
                "Content-Type": "application/json",
                "authorization": auth
            },
            json={
                "deviceType": device["type"],
                "DeviceCode": device["code"],
                "pageIndex": 1,
                "pageSize": 1,
                "step": 60
            },
            timeout=10
        )
        data = resp.json()
        if data.get("ResultType") == 200 and data["Data"].get("Page"):
            return data["Data"]["Page"][0]
        else:
            print(f"[{now()}] {device['code']} 获取数据失败: {data.get('Message')}", file=sys.stderr)
            return None
    except Exception as e:
        print(f"[{now()}] {device['code']} 请求异常: {e}", file=sys.stderr)
        return None

def load_state():
    """加载状态"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {"last_alert_time": {}, "last_data_time": None}

def save_state(state):
    """保存状态"""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def send_feishu(title, content):
    """发送飞书通知（直接通过飞书API）"""
    try:
        import requests as req
        
        # 从openclaw配置读取飞书凭证
        oc_path = "/root/.openclaw/openclaw.json"
        with open(oc_path) as f:
            oc = json.load(f)
        feishu = oc.get("channels", {}).get("feishu", {}).get("accounts", {}).get("main", {})
        app_id = feishu.get("appId", "")
        app_secret = feishu.get("appSecret", "")
        
        if not app_id or not app_secret:
            print(f"[{now()}] 飞书appId/appSecret未配置", file=sys.stderr)
            return
        
        user_id = "ou_c5c98e2002a34a9b10f15fd0b6463d06"
        
        # 获取token
        tok = req.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret}, timeout=10).json()
        token = tok.get("tenant_access_token", "")
        if not token:
            print(f"[{now()}] 获取token失败: {tok}", file=sys.stderr)
            return
        
        # 发送消息
        resp = req.post("https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"receive_id": user_id, "msg_type": "text",
                  "content": json.dumps({"text": f"⚠️ {title}\n{content}"})},
            timeout=10).json()
        
        if resp.get("code") == 0:
            print(f"[{now()}] 飞书通知已发送", file=sys.stderr)
        else:
            print(f"[{now()}] 发送失败: {resp.get('msg')}", file=sys.stderr)
    except Exception as e:
        print(f"[{now()}] 通知异常: {e}", file=sys.stderr)

def check(fail_counts):
    """执行一次检查（所有设备）"""
    state = load_state()
    
    for device in DEVICES:
        record = fetch_data(device)
        code = device["code"]
        name = device["name"]
        thresholds = device["thresholds"]
        fields = device["monitor_fields"]
        
        if record is None:
            # 连续3次失败才告警，避免偶发超时误报
            fail_counts[code] = fail_counts.get(code, 0) + 1
            if fail_counts[code] >= 3:
                send_feishu("EPMS数据获取失败", f"设备 {name} 连续{fail_counts[code]}次无法获取数据，请检查平台是否正常运行。")
                fail_counts[code] = 0  # 告警后重置，避免持续刷
            else:
                print(f"[{now()}] {name} 获取失败({fail_counts[code]}/3)，暂不告警", file=sys.stderr)
            continue
        else:
            fail_counts[code] = 0  # 成功则重置计数
        
        data_time = record.get("Date", "")
        values = {f: record.get(f, 0) for f in fields}
        
        # 构建日志
        log_parts = [f"{f}={values[f]}" for f in fields]
        print(f"[{now()}] {name}: {', '.join(log_parts)}, 时间={data_time}", file=sys.stderr)
        
        # 1. 检查阈值超标（只检查monitor_fields）
        alerts = []
        for key in fields:
            if key in thresholds:
                value = values[key]
                if value is not None and value > thresholds[key]:
                    alerts.append(f"🔴 {key}: {value} (阈值: {thresholds[key]})")
        
        if alerts:
            # 超标告警：每次检查都通知
            msg = f"设备 {name} 数据超标告警：\n" + "\n".join(alerts) + f"\n数据时间: {data_time}"
            send_feishu("EPMS排放超标告警", msg)
        
        # 2. 检查数据中断
        if data_time:
            try:
                dt = datetime.fromisoformat(data_time)
                gap = (datetime.now() - dt).total_seconds() / 60
                if gap > NO_DATA_TIMEOUT:
                    # 每次检查都告警
                    msg = f"设备 {name} 数据中断告警：\n最后数据时间: {data_time}\n已中断: {int(gap)} 分钟"
                    send_feishu("EPMS数据中断告警", msg)
                else:
                    # 数据恢复，清除中断标记
                    state.setdefault("last_alert_time", {})
                    state["last_alert_time"].pop(f"{code}_no_data", None)
            except:
                pass
        
        state[f"last_data_{code}"] = data_time
    
    save_state(state)

def main():
    print(f"[{now()}] EPMS监控启动", file=sys.stderr)
    for d in DEVICES:
        print(f"[{now()}]   {d['code']}: 阈值={d['thresholds']}, 监控={d['monitor_fields']}", file=sys.stderr)
    print(f"[{now()}] 数据中断告警: {NO_DATA_TIMEOUT}分钟 | 间隔: {CHECK_INTERVAL}秒", file=sys.stderr)
    
    fail_counts = {}
    
    # 首次登录
    if not login():
        print("登录失败，退出", file=sys.stderr)
        sys.exit(1)
    
    while True:
        try:
            check(fail_counts)
            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            print(f"\n[{now()}] 监控已停止", file=sys.stderr)
            break
        except Exception as e:
            print(f"[{now()}] 异常: {e}", file=sys.stderr)
            time.sleep(10)

if __name__ == "__main__":
    main()
