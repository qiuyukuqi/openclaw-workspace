# -*- coding: utf-8 -*-
"""配置管理模块"""

import json
import os
from config import DEVICES, DEFAULT_CHECK_INTERVAL, DEFAULT_NO_DATA_TIMEOUT, DEFAULT_ALERT_COOLDOWN, CONFIG_FILE, API_SOURCES, DEFAULT_API_SOURCE


def load_config():
    """加载配置，与默认值合并"""
    default = {
        "devices": [
            {"code": d["code"], "name": d["name"], "threshold": d["threshold"]}
            for d in DEVICES
        ],
        "check_interval": DEFAULT_CHECK_INTERVAL,
        "no_data_timeout": DEFAULT_NO_DATA_TIMEOUT,
        "alert_cooldown": DEFAULT_ALERT_COOLDOWN,
        "api_source": DEFAULT_API_SOURCE,
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            # 合并
            for dev in default["devices"]:
                for s in saved.get("devices", []):
                    if s["code"] == dev["code"]:
                        dev["threshold"] = s.get("threshold", dev["threshold"])
            default["check_interval"] = saved.get("check_interval", default["check_interval"])
            default["no_data_timeout"] = saved.get("no_data_timeout", default["no_data_timeout"])
            default["alert_cooldown"] = saved.get("alert_cooldown", default["alert_cooldown"])
        except:
            pass
    return default


def save_config(cfg):
    """保存配置"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
