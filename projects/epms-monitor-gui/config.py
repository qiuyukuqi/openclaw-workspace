# -*- coding: utf-8 -*-
import os
import sys

# exe所在目录（PyInstaller打包后__file__指向临时目录，需用sys.executable）
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

# 设备配置
DEVICES = [
    {"code": "TSP_347", "name": "TSP_347（可逆皮带）", "type": "tsp", "threshold": 400, "monitor_fields": ["TSP"]},
    {"code": "TSP_346", "name": "TSP_346（给煤机皮带）", "type": "tsp", "threshold": 400, "monitor_fields": ["TSP"]},
]

# EPMS API
API_BASE = "http://10.99.81.197:8089"
ACCOUNT = "00008323"
PASSWORD_MD5 = "df66717d95cbcea8e2fe13ef3ed23b21"

# 内外网地址配置
API_SOURCES = {
    "外网": "http://60.164.184.43:17641",
    "内网": "http://10.99.81.197:8089",
}
DEFAULT_API_SOURCE = "外网"

# 默认参数
DEFAULT_CHECK_INTERVAL = 10  # 秒
DEFAULT_NO_DATA_TIMEOUT = 4  # 分钟
DEFAULT_ALERT_COOLDOWN = 60  # 秒（同类告警冷却）

# 数据库
DB_NAME = os.path.join(APP_DIR, "data.db")

# 配置文件
CONFIG_FILE = os.path.join(APP_DIR, "config.json")
