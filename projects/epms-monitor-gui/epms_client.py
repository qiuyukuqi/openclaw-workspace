# -*- coding: utf-8 -*-
"""EPMS API 通信模块"""

import requests
import time
import json
from config import API_BASE, API_SOURCES, ACCOUNT, PASSWORD_MD5


class EPMSClient:
    """EPMS平台API客户端"""
    
    def __init__(self):
        self.token = ""
        self.token_expire = 0
        self._api_base = API_BASE
    
    @property
    def api_base(self):
        return self._api_base
    
    @api_base.setter
    def api_base(self, url):
        if url != self._api_base:
            self._api_base = url
            self.token = ""
            self.token_expire = 0
    
    def login(self):
        """登录获取token"""
        try:
            resp = requests.post(
                f"{self._api_base}/api/base/SysLogin/LoginWithoutCode",
                json={"account": ACCOUNT, "password": PASSWORD_MD5},
                timeout=10
            )
            data = resp.json()
            if data.get("ResultType") == 200 and data.get("Data", {}).get("Token"):
                self.token = data["Data"]["Token"]
                # 内网token有效期短，30秒续期
                self.token_expire = time.time() + 30
                return True
            else:
                return False
        except Exception as e:
            print(f"登录异常: {e}")
            return False
    
    def get_token(self):
        """获取有效token，过期自动重新登录"""
        if not self.token or time.time() > self.token_expire:
            self.login()
        return self.token if self.token else None
    
    def fetch_data(self, device):
        """获取指定设备最新数据，token过期自动重试一次"""
        for attempt in range(2):
            auth = self.get_token()
            if not auth:
                return None
            try:
                resp = requests.post(
                    f"{self._api_base}/api/EPMS/Emission/History/QueryByPage",
                    headers={"Content-Type": "application/json", "authorization": auth},
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
                # 可能token过期被踢，强制重新登录重试
                if attempt == 0 and data.get("ResultType") in (401, 400):
                    self.token = ""
                    self.token_expire = 0
                    continue
                return None
            except Exception as e:
                print(f"获取数据异常: {e}")
                return None
        return None
    
    def is_connected(self):
        """测试连接"""
        return self.get_token() is not None
