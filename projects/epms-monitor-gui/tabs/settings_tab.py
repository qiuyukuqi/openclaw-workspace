# -*- coding: utf-8 -*-
"""参数设置 Tab"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QSlider,
    QSpinBox, QPushButton, QMessageBox
)
from PyQt5.QtCore import Qt
from config import DEVICES


class SettingsTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title = QLabel("参数设置")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #cdd6f4; padding: 8px 0;")
        layout.addWidget(title)
        
        # 设备阈值设置
        for device in DEVICES:
            group = self._create_device_group(device)
            layout.addWidget(group)
        
        # 通用设置
        general = QGroupBox("通用设置")
        general.setStyleSheet("QGroupBox { font-size: 16px; }")
        gl = QVBoxLayout(general)
        
        # 检查间隔
        gl.addLayout(self._create_spin_row("检查间隔（秒）", 1, 120, self.mw.config.get("check_interval", 10), "check_interval"))
        
        # 数据中断告警
        gl.addLayout(self._create_spin_row("数据中断告警（分钟）", 1, 60, self.mw.config.get("no_data_timeout", 4), "no_data_timeout"))
        
        # 告警冷却
        gl.addLayout(self._create_spin_row("同类告警冷却（秒）", 60, 7200, self.mw.config.get("alert_cooldown", 60), "alert_cooldown"))
        
        layout.addWidget(general)
        
        layout.addStretch()
        
        # 按钮
        btn_layout = QHBoxLayout()
        reset_btn = QPushButton("恢复默认")
        reset_btn.clicked.connect(self._reset)
        save_btn = QPushButton("💾 保存设置")
        save_btn.setStyleSheet("QPushButton { background: #89b4fa; color: #1e1e2e; font-weight: bold; padding: 8px 24px; } QPushButton:hover { background: #74c7ec; }")
        save_btn.clicked.connect(self._save)
        
        btn_layout.addStretch()
        btn_layout.addWidget(reset_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)
    
    def _create_device_group(self, device):
        code = device["code"]
        threshold = self.mw._get_threshold(code)
        
        group = QGroupBox(device["name"])
        group.setStyleSheet("QGroupBox { font-size: 16px; }")
        layout = QVBoxLayout(group)
        
        # TSP阈值滑块
        h = QHBoxLayout()
        label = QLabel("TSP报警阈值：")
        label.setFixedWidth(100)
        
        slider = QSlider(Qt.Horizontal)
        slider.setObjectName(f"slider_{code}")
        slider.setRange(0, 1000)
        slider.setValue(int(threshold))
        slider.setTickPosition(QSlider.TicksBelow)
        slider.setTickInterval(100)
        
        spin = QSpinBox()
        spin.setObjectName(f"spin_{code}")
        spin.setRange(0, 1000)
        spin.setValue(int(threshold))
        spin.setSuffix(" μg/m³")
        spin.setFixedWidth(120)
        
        # 同步滑块和输入框
        slider.valueChanged.connect(lambda v, s=spin: s.setValue(v))
        spin.valueChanged.connect(lambda v, s=slider: s.setValue(v))
        
        h.addWidget(label)
        h.addWidget(slider, stretch=1)
        h.addWidget(spin)
        layout.addLayout(h)
        
        return group
    
    def _create_spin_row(self, label_text, min_val, max_val, default, key):
        h = QHBoxLayout()
        label = QLabel(label_text)
        label.setFixedWidth(160)
        
        spin = QSpinBox()
        spin.setObjectName(f"spin_{key}")
        spin.setRange(min_val, max_val)
        spin.setValue(default)
        spin.setFixedWidth(120)
        
        h.addWidget(label)
        h.addWidget(spin)
        h.addStretch()
        return h
    
    def _save(self):
        cfg = self.mw.config.copy()
        cfg["devices"] = []
        
        for device in DEVICES:
            code = device["code"]
            spin = self.findChild(QSpinBox, f"spin_{code}")
            cfg["devices"].append({
                "code": code,
                "name": device["name"],
                "threshold": spin.value() if spin else 400
            })
        
        for key in ["check_interval", "no_data_timeout", "alert_cooldown"]:
            spin = self.findChild(QSpinBox, f"spin_{key}")
            if spin:
                cfg[key] = spin.value()
        
        self.mw.update_config(cfg)
        msg = QMessageBox(self)
        msg.setWindowTitle("成功")
        msg.setText("设置已保存")
        msg.setStyleSheet("""
            QMessageBox { background: #1e1e2e; min-width: 400px; min-height: 200px; }
            QLabel { color: #cdd6f4; font-size: 16px; min-width: 360px; min-height: 120px; }
            QPushButton { min-width: 120px; min-height: 40px; font-size: 15px; }
        """)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.button(QMessageBox.Ok).setText("确定")
        msg.setAttribute(Qt.WA_DeleteOnClose)
        msg.setWindowFlags(msg.windowFlags() | Qt.WindowStaysOnTopHint)
        msg.show()
    
    def _reset(self):
        """恢复默认值"""
        for device in DEVICES:
            code = device["code"]
            spin = self.findChild(QSpinBox, f"spin_{code}")
            slider = self.findChild(QSlider, f"slider_{code}")
            if spin:
                spin.setValue(400)
            if slider:
                slider.setValue(400)
        
        defaults = {"check_interval": 10, "no_data_timeout": 4, "alert_cooldown": 60}
        for key, val in defaults.items():
            spin = self.findChild(QSpinBox, f"spin_{key}")
            if spin:
                spin.setValue(val)
    
    def showEvent(self, event):
        super().showEvent(event)
        # 刷新为当前配置值
        for device in DEVICES:
            code = device["code"]
            threshold = self.mw._get_threshold(code)
            spin = self.findChild(QSpinBox, f"spin_{code}")
            slider = self.findChild(QSlider, f"slider_{code}")
            if spin:
                spin.setValue(int(threshold))
            if slider:
                slider.setValue(int(threshold))
        
        for key in ["check_interval", "no_data_timeout", "alert_cooldown"]:
            spin = self.findChild(QSpinBox, f"spin_{key}")
            if spin:
                spin.setValue(self.mw.config.get(key, 10))
