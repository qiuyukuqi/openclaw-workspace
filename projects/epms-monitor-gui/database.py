# -*- coding: utf-8 -*-
"""SQLite 数据库模块"""

import sqlite3
import os
from datetime import datetime
from config import DB_NAME


class Database:
    def __init__(self, db_path=None):
        self.db_path = db_path if db_path else DB_NAME
        self._conn = None
        self._init_db()
    
    def _get_conn(self):
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        return self._conn
    
    def _init_db(self):
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS tsp_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_code TEXT NOT NULL,
            device_name TEXT NOT NULL,
            tsp_value REAL,
            data_time TEXT NOT NULL,
            recorded_at TEXT NOT NULL
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS alert_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_code TEXT NOT NULL,
            device_name TEXT NOT NULL,
            alert_type TEXT NOT NULL,
            message TEXT,
            tsp_value REAL,
            alert_time TEXT NOT NULL
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_data_time ON tsp_data(data_time)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_data_device ON tsp_data(device_code, data_time)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_alert_time ON alert_history(alert_time)")
        conn.commit()
        # conn.close()
    
    def insert_data(self, device_code, device_name, tsp_value, data_time):
        conn = self._get_conn()
        try:
            # 按分钟去重：同一设备同一分钟只保留最新一条
            minute_key = data_time[:16] if data_time and len(data_time) >= 16 else ""
            if minute_key:
                conn.execute(
                    "DELETE FROM tsp_data WHERE device_code = ? AND substr(data_time, 1, 16) = ?",
                    (device_code, minute_key)
                )
            conn.execute(
                "INSERT INTO tsp_data (device_code, device_name, tsp_value, data_time, recorded_at) VALUES (?, ?, ?, ?, ?)",
                (device_code, device_name, tsp_value, data_time, datetime.now().isoformat())
            )
            conn.commit()
        except Exception:
            conn.rollback()
        # conn.close()
    
    def insert_alert(self, device_code, device_name, alert_type, message, tsp_value=None):
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO alert_history (device_code, device_name, alert_type, message, tsp_value, alert_time) VALUES (?, ?, ?, ?, ?, ?)",
            (device_code, device_name, alert_type, message, tsp_value, datetime.now().isoformat())
        )
        conn.commit()
        # conn.close()
    
    def query_data(self, device_code=None, start_time=None, end_time=None, limit=1000):
        conn = self._get_conn()
        c = conn.cursor()
        sql = "SELECT device_code, device_name, tsp_value, data_time FROM tsp_data WHERE 1=1"
        params = []
        if device_code:
            sql += " AND device_code = ?"
            params.append(device_code)
        if start_time:
            sql += " AND data_time >= ?"
            params.append(start_time)
        if end_time:
            sql += " AND data_time <= ?"
            params.append(end_time)
        sql += " ORDER BY data_time DESC LIMIT ?"
        params.append(limit)
        c.execute(sql, params)
        rows = c.fetchall()
        # conn.close()
        return rows
    
    def query_alerts(self, device_code=None, alert_type=None, start_time=None, end_time=None, limit=500):
        conn = self._get_conn()
        c = conn.cursor()
        sql = "SELECT device_code, device_name, alert_type, message, tsp_value, alert_time FROM alert_history WHERE 1=1"
        params = []
        if device_code:
            sql += " AND device_code = ?"
            params.append(device_code)
        if alert_type:
            sql += " AND alert_type = ?"
            params.append(alert_type)
        if start_time:
            sql += " AND alert_time >= ?"
            params.append(start_time)
        if end_time:
            sql += " AND alert_time <= ?"
            params.append(end_time)
        sql += " ORDER BY alert_time DESC LIMIT ?"
        params.append(limit)
        c.execute(sql, params)
        rows = c.fetchall()
        # conn.close()
        return rows
    
    def clear_alerts(self):
        conn = self._get_conn()
        conn.execute("DELETE FROM alert_history")
        conn.commit()
        # conn.close()
