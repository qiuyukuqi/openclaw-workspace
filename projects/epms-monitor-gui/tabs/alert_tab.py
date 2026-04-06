# -*- coding: utf-8 -*-
"""告警历史 Tab"""

from datetime import datetime, timedelta

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QFileDialog,
    QMessageBox, QGroupBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor


class AlertTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel("告警历史")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #cdd6f4; padding: 8px 0;")
        layout.addWidget(title)
        
        # 筛选
        filter_group = QGroupBox("筛选")
        fl = QHBoxLayout(filter_group)
        
        fl.addWidget(QLabel("设备："))
        self.device_combo = QComboBox()
        self.device_combo.addItems(["全部", "TSP_347（可逆皮带）", "TSP_346（给煤机皮带）"])
        self.device_combo.setFixedWidth(200)
        fl.addWidget(self.device_combo)
        
        fl.addWidget(QLabel("类型："))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["全部", "TSP超标", "数据中断", "获取失败"])
        self.type_combo.setFixedWidth(120)
        fl.addWidget(self.type_combo)
        
        fl.addWidget(QLabel("时间："))
        self.time_combo = QComboBox()
        self.time_combo.addItems(["近7天", "近30天", "近90天", "全部"])
        self.time_combo.setFixedWidth(100)
        fl.addWidget(self.time_combo)
        
        fl.addStretch()
        
        search_btn = QPushButton("🔍 查询")
        search_btn.clicked.connect(self.refresh)
        fl.addWidget(search_btn)
        
        clear_btn = QPushButton("🗑️ 清空历史")
        clear_btn.clicked.connect(self._clear)
        fl.addWidget(clear_btn)
        
        export_btn = QPushButton("📊 导出")
        export_btn.clicked.connect(self._export)
        fl.addWidget(export_btn)
        
        layout.addWidget(filter_group)
        
        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["时间", "设备", "类型", "详情"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)
    
    def refresh(self):
        """刷新告警列表"""
        device_code = self.device_combo.currentIndex()  # 0=全部, 1=347, 2=346
        alert_type = self.type_combo.currentIndex()  # 0=全部, 1=超标, 2=中断, 3=失败
        time_range = self.time_combo.currentIndex()  # 0=7天, 1=30天, 2=90天, 3=全部
        
        # 设备过滤
        dc = None
        if device_code == 1:
            dc = "TSP_347"
        elif device_code == 2:
            dc = "TSP_346"
        
        # 类型过滤
        at = None
        if alert_type == 1:
            at = "over_limit"
        elif alert_type == 2:
            at = "no_data"
        elif alert_type == 3:
            at = "fetch_fail"
        
        # 时间过滤
        start_time = None
        hours = [168, 720, 2160, None]
        h = hours[time_range]
        if h:
            start_time = (datetime.now() - timedelta(hours=h)).isoformat()
        
        rows = self.mw.db.query_alerts(
            device_code=dc,
            alert_type=at,
            start_time=start_time,
            limit=1000
        )
        
        self._fill_table(rows)
    
    def _fill_table(self, rows):
        type_icons = {
            "over_limit": ("🔴 TSP超标", "#f38ba8"),
            "no_data": ("⚠️ 数据中断", "#fab387"),
            "fetch_fail": ("❌ 获取失败", "#f38ba8"),
        }
        
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            code, name, alert_type, message, tsp, alert_time = row
            
            # 时间
            item_time = QTableWidgetItem(alert_time.split(".")[0] if alert_time else "")
            item_time.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 0, item_time)
            
            # 设备
            item_dev = QTableWidgetItem(name or code)
            self.table.setItem(i, 1, item_dev)
            
            # 类型
            icon_text, color = type_icons.get(alert_type, (alert_type, "#cdd6f4"))
            item_type = QTableWidgetItem(icon_text)
            item_type.setForeground(QColor(color))
            self.table.setItem(i, 2, item_type)
            
            # 详情
            item_msg = QTableWidgetItem(message or "")
            item_msg.setForeground(QColor('#a6adc8'))
            self.table.setItem(i, 3, item_msg)
    
    def _clear(self):
        reply = QMessageBox.question(self, "确认", "确定要清空所有告警历史吗？", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.mw.db.clear_alerts()
            self.table.setRowCount(0)
    
    def _export(self):
        rows = self.mw.db.query_alerts(limit=10000)
        if not rows:
            QMessageBox.warning(self, "提示", "无数据可导出")
            return
        
        path, _ = QFileDialog.getSaveFileName(self, "导出告警历史", "告警历史.csv", "CSV Files (*.csv)")
        if path:
            import csv
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["时间", "设备", "类型", "详情", "TSP值"])
                for code, name, alert_type, message, tsp, alert_time in rows:
                    writer.writerow([alert_time, name, alert_type, message, tsp])
            QMessageBox.information(self, "成功", f"已导出 {len(rows)} 条记录")
    
    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()
