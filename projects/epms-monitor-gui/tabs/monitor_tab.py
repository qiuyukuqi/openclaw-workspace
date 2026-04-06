# -*- coding: utf-8 -*-
"""实时监控 Tab"""

import math
import time

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QFrame, QPushButton, QButtonGroup
)
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect, pyqtProperty
from PyQt5.QtGui import QColor, QFont, QPainter, QPen, QRadialGradient
import pyqtgraph as pg
pg.setConfigOptions(useOpenGL=False)

from config import DEVICES
from database import Database


class BreathingLight(QWidget):
    """呼吸灯指示器"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._radius = 48
        self._opacity = 1.0
        self._color = QColor("#a6e3a1")  # 绿
        self.setFixedSize(200, 150)
        
        # 呼吸动画
        self._anim = QPropertyAnimation(self, b"opacity")
        self._duration_normal = 1200
        self._duration_alert = 500
        self._anim.setDuration(self._duration_normal)
        self._anim.setStartValue(0.3)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.InOutSine)
        self._anim.setLoopCount(-1)
        self._anim.start()
    
    def get_opacity(self):
        return self._opacity
    
    def set_opacity(self, val):
        self._opacity = val
        self.update()
    
    opacity = pyqtProperty(float, get_opacity, set_opacity)
    
    def set_status(self, status):
        """ok=绿 warning=橙 error=红"""
        colors = {"ok": "#a6e3a1", "no_data": "#fab387", "over_limit": "#89b4fa", "offline": "#f38ba8"}
        self._color = QColor(colors.get(status, "#6c7086"))
        if status == "ok":
            self._anim.setDuration(self._duration_normal)
        else:
            self._anim.setDuration(self._duration_alert)
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        cx = self.width() // 2
        cy = 65
        r = self._radius
        
        # 1. 金属边框
        painter.setPen(QPen(QColor(60, 60, 65), 5))
        painter.setBrush(QColor(25, 25, 30))
        painter.drawEllipse(cx - r - 3, cy - r - 3, (r + 3) * 2, (r + 3) * 2)
        
        # 2. 灯体 - 纯色圆，不随opacity变暗
        painter.setPen(Qt.NoPen)
        painter.setBrush(self._color)
        painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)
        
        # 3. 高光 - 左上角椭圆
        painter.setBrush(QColor(255, 255, 255, 80))
        painter.drawEllipse(cx - r * 0.5, cy - r * 0.6, r * 0.6, r * 0.4)
        
        # 4. 外发光 - 用opacity控制
        glow_color = QColor(self._color)
        glow_color.setAlpha(int(self._opacity * 60))
        painter.setBrush(glow_color)
        painter.drawEllipse(cx - r - 15, cy - r - 15, (r + 15) * 2, (r + 15) * 2)
        
        painter.end()


class MonitorTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.db = main_window.db
        self.history_data_min = {}  # 每分钟数据（近60分钟）
        self.history_data_hour = {}  # 每小时数据（近24小时）
        self._max_min_history = 60
        self._max_hour_history = 24
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        
        # 设备卡片 + 呼吸灯 区域
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(20)
        
        # 左：呼吸灯指示器
        light_frame = QFrame()
        light_frame.setStyleSheet("QFrame { background: transparent; }")
        light_layout = QVBoxLayout(light_frame)
        light_layout.setSpacing(4)
        light_layout.setAlignment(Qt.AlignCenter)
        
        self.breathing_light = BreathingLight()
        light_layout.addSpacing(16)
        light_layout.addWidget(self.breathing_light, alignment=Qt.AlignCenter)
        
        self.status_label = QLabel("运行正常")
        self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #a6e3a1;")
        self.status_label.setAlignment(Qt.AlignCenter)
        light_layout.addWidget(self.status_label, alignment=Qt.AlignCenter)
        
        self.online_label = QLabel("● 已连接")
        self.online_label.setStyleSheet("font-size: 14px; color: #6c7086;")
        self.online_label.setAlignment(Qt.AlignCenter)
        light_layout.addWidget(self.online_label, alignment=Qt.AlignCenter)
        
        cards_layout.addWidget(light_frame)
        
        # 右：设备卡片
        cards_inner = QHBoxLayout()
        cards_inner.setSpacing(16)
        for device in DEVICES:
            card = self._create_device_card(device)
            cards_inner.addWidget(card)
        cards_inner.addStretch()
        cards_layout.addLayout(cards_inner, stretch=1)
        layout.addLayout(cards_layout)
        
        # 分钟数据表格区域（并排）
        tables_title_layout = QHBoxLayout()
        tables_title_layout.addWidget(self._create_table_title("TSP_347（可逆皮带）"))
        tables_title_layout.addWidget(self._create_table_title("TSP_346（给煤机皮带）"))
        layout.addLayout(tables_title_layout)
        
        tables_data_layout = QHBoxLayout()
        tables_data_layout.setSpacing(12)
        self.table_347 = self._create_data_table()
        self.table_346 = self._create_data_table()
        tables_data_layout.addWidget(self.table_347)
        tables_data_layout.addWidget(self.table_346)
        layout.addLayout(tables_data_layout)
        
        # 趋势图 + 切换按钮
        chart_header = QHBoxLayout()
        chart_title = QLabel("趋势曲线")
        chart_title.setStyleSheet("font-weight: bold; font-size: 16px; color: #bac2de; padding: 4px 0;")
        chart_header.addWidget(chart_title)
        chart_header.addStretch()
        
        self.chart_btn_group = QButtonGroup()
        btn_60 = QPushButton("近60分钟")
        btn_60.setCheckable(True)
        btn_60.setChecked(True)
        btn_60.setFixedHeight(32)
        btn_60.setStyleSheet("""
            QPushButton { background: #89b4fa; color: #1e1e2e; font-size: 14px; font-weight: bold; 
                           padding: 4px 16px; border-radius: 4px; }
            QPushButton:hover { background: #74c7ec; }
        """)
        
        btn_24h = QPushButton("近24小时")
        btn_24h.setCheckable(True)
        btn_24h.setFixedHeight(32)
        btn_24h.setStyleSheet("""
            QPushButton { background: #45475a; color: #cdd6f4; font-size: 14px; font-weight: bold; 
                           padding: 4px 16px; border-radius: 4px; }
            QPushButton:hover { background: #585b70; }
            QPushButton:checked { background: #89b4fa; color: #1e1e2e; }
        """)
        
        self.chart_btn_group.addButton(btn_60, 0)
        self.chart_btn_group.addButton(btn_24h, 1)
        self.chart_btn_group.buttonClicked[int].connect(self._switch_chart_mode)
        self._chart_mode = "minute"  # minute / hour
        
        chart_header.addWidget(btn_60)
        chart_header.addWidget(btn_24h)
        layout.addLayout(chart_header)
        
        self.chart = pg.PlotWidget()
        self.chart.setBackground('#1e1e2e')
        self.chart.showGrid(x=True, y=True, alpha=0.2)
        self.chart.setLabel('left', 'TSP', **{'font-size': '14px'})
        self.chart.setLabel('bottom', '时间', **{'font-size': '14px'})
        self.chart.enableAutoRange(axis='y', enable=False)
        self.chart.setYRange(0, 500, padding=0.05)
        self.chart.setMaximumHeight(340)
        self.chart.setMinimumHeight(200)
        self.chart.getAxis('left').setTickFont(QFont("Microsoft YaHei UI", 12))
        self.chart.getAxis('bottom').setTickFont(QFont("Microsoft YaHei UI", 12))
        
        self.curve_347 = self.chart.plot(pen=pg.mkPen('#89b4fa', width=2.5), name="TSP_347")
        self.curve_346 = self.chart.plot(pen=pg.mkPen('#a6e3a1', width=2.5), name="TSP_346")
        self.threshold_line = pg.InfiniteLine(pos=400, angle=0, pen=pg.mkPen('#f38ba8', width=1.5, style=Qt.DashLine))
        self.chart.addItem(self.threshold_line)
        self.chart.addLegend(offset=(10, 10), labelTextColor='#a6adc8', labelTextSize='14px', brush='#1e1e2ecc')
        self.chart.setYRange(0, 500, padding=0.05)
        
        layout.addWidget(self.chart)
        
        # 初始化历史缓存
        for d in DEVICES:
            self.history_data_min[d["code"]] = []
            self.history_data_hour[d["code"]] = []
    
    def _create_device_card(self, device):
        frame = QFrame()
        frame.setFixedWidth(340)
        frame.setMinimumHeight(140)
        frame.setStyleSheet("""
            QFrame { background: #313244; border-radius: 12px; }
        """)
        layout = QVBoxLayout(frame)
        layout.setSpacing(6)
        layout.setContentsMargins(20, 16, 20, 16)
        
        name_label = QLabel(device["name"])
        name_label.setStyleSheet("font-size: 17px; font-weight: bold; color: #bac2de;")
        layout.addWidget(name_label)
        
        value_label = QLabel("--")
        value_label.setObjectName(f"value_{device['code']}")
        value_label.setStyleSheet("font-size: 52px; font-weight: bold; color: #cdd6f4;")
        value_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(value_label)
        
        time_label = QLabel("等待数据...")
        time_label.setObjectName(f"time_{device['code']}")
        time_label.setStyleSheet("font-size: 15px; color: #6c7086;")
        time_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(time_label)
        
        return frame
    
    def _create_table_title(self, text):
        label = QLabel(f"📈 {text}")
        label.setStyleSheet("font-weight: bold; font-size: 15px; color: #a6adc8; padding: 6px 0;")
        return label
    
    def _create_data_table(self):
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["时间", "TSP", "状态"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        table.setColumnWidth(0, 110)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(34)
        table.setRowCount(10)
        table.setMaximumHeight(400)
        table.setAlternatingRowColors(True)
        return table
    
    def _switch_chart_mode(self, idx):
        if idx == 0:
            self._chart_mode = "minute"
        else:
            self._chart_mode = "hour"
        self._update_chart()
    
    def update_data(self, device_data):
        for device in DEVICES:
            code = device["code"]
            data = device_data.get(code, {})
            value = data.get("value")
            data_time = data.get("data_time", "")
            status = data.get("status", "normal")
            
            value_label = self.findChild(QLabel, f"value_{code}")
            time_label = self.findChild(QLabel, f"time_{code}")
            card = value_label.parent() if value_label else None
            
            if value is not None:
                value_label.setText(f"{value:.1f}")
                dt_str = data_time.split("T")[-1][:5] if "T" in data_time else data_time[-5:]
                time_label.setText(f"📅 {dt_str}")
            else:
                value_label.setText("--")
                time_label.setText("无数据")
            
            if status == "over_limit":
                value_label.setStyleSheet("font-size: 52px; font-weight: bold; color: #89b4fa;")
                if card: card.setStyleSheet("QFrame { background: #313244; border-radius: 12px; border: 2px solid #89b4fa; }")
            elif status == "no_data":
                value_label.setStyleSheet("font-size: 52px; font-weight: bold; color: #fab387;")
                if card: card.setStyleSheet("QFrame { background: #313244; border-radius: 12px; border: 2px solid #fab387; }")
            elif status == "offline":
                value_label.setStyleSheet("font-size: 52px; font-weight: bold; color: #f38ba8;")
                if card: card.setStyleSheet("QFrame { background: #45273a; border-radius: 12px; border: 2px solid #f38ba8; }")
            else:
                value_label.setStyleSheet("font-size: 52px; font-weight: bold; color: #cdd6f4;")
                if card: card.setStyleSheet("QFrame { background: #313244; border-radius: 12px; }")
            
            # 缓存分钟数据
            if value is not None:
                hist = self.history_data_min.get(code, [])
                hist.append(value)
                if len(hist) > self._max_min_history:
                    hist = hist[-self._max_min_history:]
                self.history_data_min[code] = hist
        
        # 更新呼吸灯
        any_offline = any(d.get("status") == "offline" for d in device_data.values())
        any_no_data = any(d.get("status") == "no_data" for d in device_data.values())
        any_over = any(d.get("status") == "over_limit" for d in device_data.values())
        
        if any_offline or (not self.mw.is_online):
            self.breathing_light.set_status("offline")
            self.status_label.setText("网络离线")
            self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #f38ba8;")
            self.online_label.setText("● 已离线")
            self.online_label.setStyleSheet("font-size: 14px; color: #f38ba8;")
        elif any_no_data:
            self.breathing_light.set_status("no_data")
            self.status_label.setText("数据中断")
            self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #fab387;")
            self.online_label.setText("● 已连接")
            self.online_label.setStyleSheet("font-size: 14px; color: #fab387;")
        elif any_over:
            self.breathing_light.set_status("over_limit")
            self.status_label.setText("数据超标")
            self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #89b4fa;")
            self.online_label.setText("● 已连接")
            self.online_label.setStyleSheet("font-size: 14px; color: #89b4fa;")
        else:
            self.breathing_light.set_status("ok")
            self.status_label.setText("运行正常")
            self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #a6e3a1;")
            self.online_label.setText("● 已连接")
            self.online_label.setStyleSheet("font-size: 14px; color: #a6e3a1;")
        
        self._update_chart()
        
        # 表格每30秒刷新（降低DB查询频率）
        if not hasattr(self, '_last_table_update') or time.time() - self._last_table_update > 30:
            self._last_table_update = time.time()
            self._update_tables()
    
    def _update_chart(self):
        if self._chart_mode == "minute":
            for code, curve in [("TSP_347", self.curve_347), ("TSP_346", self.curve_346)]:
                hist = self.history_data_min.get(code, [])
                if hist:
                    curve.setData(hist)
            self.chart.setTitle("趋势曲线（近60分钟·每分钟）", **{'color': '#a6adc8', 'size': '15px'})
        else:
            # 24h模式：每60秒才查一次DB，其余用缓存
            now = time.time()
            if not hasattr(self, '_hourly_cache_time') or now - self._hourly_cache_time > 60:
                self._hourly_cache_time = now
                for code in ["TSP_347", "TSP_346"]:
                    rows = self.db.query_data(device_code=code, limit=1440)
                    hourly = {}
                    for r in reversed(rows):
                        _, _, tsp, dt = r
                        if tsp is None: continue
                        h = dt[:13]
                        if h not in hourly:
                            hourly[h] = tsp
                    self.history_data_hour[code] = list(hourly.values())
            for code, curve in [("TSP_347", self.curve_347), ("TSP_346", self.curve_346)]:
                vals = self.history_data_hour.get(code, [])
                if vals:
                    curve.setData(vals)
            self.chart.setTitle("趋势曲线（近24小时·每小时）", **{'color': '#a6adc8', 'size': '15px'})
        
        threshold = self.mw._get_threshold("TSP_347")
        self.threshold_line.setValue(threshold)
        # Y轴范围：最大值到阈值上浮30%，至少200
        all_vals = list(self.history_data_min.get("TSP_347", [])) + list(self.history_data_min.get("TSP_346", []))
        if self._chart_mode == "hour":
            all_vals += list(self.history_data_hour.get("TSP_347", [])) + list(self.history_data_hour.get("TSP_346", []))
        if all_vals:
            max_val = max(all_vals)
            y_max = max(max_val * 1.3, threshold * 1.2, 200)
            self.chart.setYRange(0, y_max, padding=0.05)
    
    def _update_tables(self):
        """刷新分钟数据表格，显示最近10条（去重）"""
        # TSP_347
        rows_347 = self.db.query_data(device_code="TSP_347", limit=60)
        unique_347 = self._deduplicate(rows_347)[:10]
        self._fill_table(self.table_347, unique_347)
        
        # TSP_346
        rows_346 = self.db.query_data(device_code="TSP_346", limit=60)
        unique_346 = self._deduplicate(rows_346)[:10]
        self._fill_table(self.table_346, unique_346)
    
    def _deduplicate(self, rows):
        """按分钟去重，保留每分钟最新的一条"""
        seen = set()
        result = []
        for row in rows:  # rows已按时间降序
            code, name, tsp, data_time = row
            # 提取到分钟: "2026-04-02T01:17"
            minute_key = data_time[:16] if data_time else ""
            if minute_key not in seen:
                seen.add(minute_key)
                result.append(row)
        return result
    
    def _fill_table(self, table, rows):
        table.setRowCount(10)
        for i in range(10):
            if i < len(rows):
                code, name, tsp, data_time = rows[i]
                threshold = self.mw._get_threshold(code)
                dt_str = data_time.split("T")[-1][:5] if "T" in data_time else ""
                
                item_time = QTableWidgetItem(dt_str)
                item_time.setTextAlignment(Qt.AlignCenter)
                item_time.setFont(QFont("Microsoft YaHei UI", 13))
                table.setItem(i, 0, item_time)
                
                item_val = QTableWidgetItem(f"{tsp:.1f}" if tsp else "--")
                item_val.setTextAlignment(Qt.AlignCenter)
                item_val.setFont(QFont("Microsoft YaHei UI", 14, QFont.Bold))
                if tsp and tsp > threshold:
                    item_val.setForeground(QColor('#f38ba8'))
                table.setItem(i, 1, item_val)
                
                status = "正常"
                color = '#a6e3a1'
                if tsp and tsp > threshold:
                    status = "超标"
                    color = '#89b4fa'
                dev_status = self.mw.device_data.get(code, {}).get("status", "")
                if dev_status == "no_data":
                    status = "中断"
                    color = '#fab387'
                elif dev_status == "offline":
                    status = "离线"
                    color = '#f38ba8'
                item_status = QTableWidgetItem(status)
                item_status.setTextAlignment(Qt.AlignCenter)
                item_status.setForeground(QColor(color))
                item_status.setFont(QFont("Microsoft YaHei UI", 13))
                table.setItem(i, 2, item_status)
            else:
                for j in range(3):
                    item = QTableWidgetItem("")
                    table.setItem(i, j, item)
    
    def showEvent(self, event):
        super().showEvent(event)
        self._update_tables()
    
    def resizeEvent(self, event):
        try:
            # pyqtgraph 在 Windows 打包环境下 resize 容易崩溃，保护处理
            if hasattr(self, 'chart'):
                self.chart.setEnabled(False)
            super().resizeEvent(event)
            if hasattr(self, 'chart'):
                self.chart.setEnabled(True)
                try:
                    self._update_chart()
                except Exception:
                    pass
        except Exception:
            pass
