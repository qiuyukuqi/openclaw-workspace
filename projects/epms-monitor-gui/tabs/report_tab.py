# -*- coding: utf-8 -*-
"""报表导出 Tab"""

from datetime import datetime, timedelta

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QDateEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QButtonGroup, QRadioButton, QCheckBox, QGroupBox, QMessageBox
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QColor


class ReportTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel("报表导出")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #cdd6f4; padding: 8px 0;")
        layout.addWidget(title)
        
        # 筛选条件
        filter_group = QGroupBox("筛选条件")
        fl = QHBoxLayout(filter_group)
        
        # 设备选择
        fl.addWidget(QLabel("设备："))
        self.device_combo = QComboBox()
        self.device_combo.addItems(["全部设备", "TSP_347（可逆皮带）", "TSP_346（给煤机皮带）"])
        self.device_combo.setFixedWidth(200)
        fl.addWidget(self.device_combo)
        fl.addSpacing(20)
        
        # 时间范围快捷选择
        time_group = QGroupBox("时间范围")
        tl = QHBoxLayout(time_group)
        self.time_buttons = QButtonGroup()
        presets = [("近1小时", 1), ("近6小时", 6), ("近24小时", 24), ("近7天", 168), ("近30天", 720), ("自定义", 0)]
        for text, val in presets:
            rb = QRadioButton(text)
            self.time_buttons.addButton(rb, val)
            if text == "近24小时":
                rb.setChecked(True)
            tl.addWidget(rb)
            self.time_buttons.idClicked.connect(self._on_time_preset)
        fl.addWidget(time_group)
        layout.addWidget(filter_group)
        
        # 自定义时间
        self.custom_time_widget = QWidget()
        self.custom_time_layout = QHBoxLayout(self.custom_time_widget)
        self.custom_time_layout.setContentsMargins(0, 0, 0, 0)
        self.custom_time_layout.addWidget(QLabel("从："))
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate().addDays(-1))
        self.start_date.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.start_date.setFixedWidth(180)
        self.custom_time_layout.addWidget(self.start_date)
        self.custom_time_layout.addWidget(QLabel("至："))
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.end_date.setFixedWidth(180)
        self.custom_time_layout.addWidget(self.end_date)
        layout.addWidget(self.custom_time_widget)
        self.custom_time_widget.setVisible(False)
        
        # 数据预览表格
        layout.addWidget(QLabel("数据预览"))
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["设备", "时间", "TSP", "状态"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)
        
        # 导出按钮
        btn_layout = QHBoxLayout()
        self.preview_btn = QPushButton("🔍 查询预览")
        self.preview_btn.clicked.connect(self._preview)
        btn_layout.addWidget(self.preview_btn)
        
        self.export_excel_btn = QPushButton("📊 导出 Excel")
        self.export_excel_btn.clicked.connect(lambda: self._export("xlsx"))
        btn_layout.addWidget(self.export_excel_btn)
        
        self.export_csv_btn = QPushButton("📄 导出 CSV")
        self.export_csv_btn.clicked.connect(lambda: self._export("csv"))
        btn_layout.addWidget(self.export_csv_btn)
        
        btn_layout.addStretch()
        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color: #6c7086;")
        btn_layout.addWidget(self.count_label)
        layout.addLayout(btn_layout)
    
    def _on_time_preset(self, idx):
        if idx == 0:
            self.custom_time_widget.setVisible(True)
        else:
            self.custom_time_layout.setVisible(False)
            self._preview()
    
    def _get_time_range(self):
        """获取查询时间范围"""
        idx = self.time_buttons.checkedId()
        now = datetime.now()
        if idx == 0:
            start = datetime.combine(self.start_date.date().toPyDate(), self.start_date.time().toPyTime())
            end = datetime.combine(self.end_date.date().toPyDate(), self.end_date.time().toPyTime())
        else:
            end = now
            start = now - timedelta(hours=idx)
        return start.strftime("%Y-%m-%dT%H:%M:%S"), end.strftime("%Y-%m-%dT%H:%M:%S")
    
    def _get_device_filter(self):
        idx = self.device_combo.currentIndex()
        if idx == 1:
            return "TSP_347"
        elif idx == 2:
            return "TSP_346"
        return None
    
    def _preview(self):
        start_time, end_time = self._get_time_range()
        device_code = self._get_device_filter()
        
        rows = self.mw.db.query_data(
            device_code=device_code,
            start_time=start_time,
            end_time=end_time,
            limit=5000
        )
        
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            code, name, tsp, data_time = row
            device_threshold = self.mw._get_threshold(code)
            dt_str = data_time.split("T")[-1] if "T" in data_time else data_time
            if "T" in data_time:
                date_str = data_time.split("T")[0]
                dt_str = f"{date_str} {dt_str}"
            
            items = [
                (name, Qt.AlignLeft, None),
                (dt_str, Qt.AlignCenter, None),
                (f"{tsp:.1f}" if tsp else "--", Qt.AlignCenter, '#f38ba8' if tsp and tsp > device_threshold else None),
                ("超标" if tsp and tsp > device_threshold else "正常", Qt.AlignCenter, '#f38ba8' if tsp and tsp > device_threshold else '#a6e3a1'),
            ]
            for j, (text, align, color) in enumerate(items):
                item = QTableWidgetItem(text)
                item.setTextAlignment(align)
                if color:
                    item.setForeground(QColor(color))
                self.table.setItem(i, j, item)
        
        self.count_label.setText(f"共 {len(rows)} 条记录")
    
    def _export(self, fmt):
        rows = self.mw.db.query_data(
            device_code=self._get_device_filter(),
            start_time=self._get_time_range()[0],
            end_time=self._get_time_range()[1],
            limit=50000
        )
        
        if not rows:
            QMessageBox.warning(self, "提示", "无数据可导出")
            return
        
        now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if fmt == "xlsx":
            path, _ = QFileDialog.getSaveFileName(self, "导出Excel", f"TSP报表_{now_str}.xlsx", "Excel Files (*.xlsx)")
            if path:
                import openpyxl
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "TSP数据"
                ws.append(["设备", "时间", "TSP", "状态"])
                for code, name, tsp, data_time in rows:
                    device_threshold = self.mw._get_threshold(code)
                    status = "超标" if tsp and tsp > device_threshold else "正常"
                    ws.append([name, data_time, tsp, status])
                wb.save(path)
                QMessageBox.information(self, "成功", f"已导出 {len(rows)} 条记录到\n{path}")
        
        elif fmt == "csv":
            path, _ = QFileDialog.getSaveFileName(self, "导出CSV", f"TSP报表_{now_str}.csv", "CSV Files (*.csv)")
            if path:
                import csv
                with open(path, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.writer(f)
                    writer.writerow(["设备", "时间", "TSP", "状态"])
                    for code, name, tsp, data_time in rows:
                        device_threshold = self.mw._get_threshold(code)
                        status = "超标" if tsp and tsp > device_threshold else "正常"
                        writer.writerow([name, data_time, tsp, status])
                QMessageBox.information(self, "成功", f"已导出 {len(rows)} 条记录到\n{path}")
    
    def showEvent(self, event):
        super().showEvent(event)
        self._preview()
