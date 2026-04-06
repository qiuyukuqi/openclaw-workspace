# -*- coding: utf-8 -*-
"""主窗口"""

import sys
import os
from datetime import datetime

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QStatusBar, QSystemTrayIcon, QMenu, QApplication, QMessageBox,
    QLabel, QPushButton, QFrame, QDialog
)
from PyQt5.QtCore import QTimer, Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QIcon, QPixmap, QColor, QPainter, QFont

from config import DEVICES, CONFIG_FILE
from epms_client import EPMSClient
from database import Database
from alert_sounds import get_alert_sound
from settings import load_config, save_config
from styles import GLOBAL_STYLE
from tabs.monitor_tab import MonitorTab
from tabs.settings_tab import SettingsTab
from tabs.report_tab import ReportTab
from tabs.alert_tab import AlertTab


class AlertDialog(QDialog):
    """告警弹窗 - 支持合并多条告警，居中显示"""
    def __init__(self, title, messages, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(550, 300)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setStyleSheet("""
            QDialog { background: #1e1e2e; }
            QLabel { color: #cdd6f4; font-family: "Microsoft YaHei UI"; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        title_label = QLabel("⚠  EPMS 告警通知")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #f38ba8; padding: 10px 0 5px 0;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background: #45475a; max-height: 1px;")
        layout.addWidget(sep)

        self._content_label = QLabel("\n\n".join(messages))
        self._content_label.setStyleSheet("font-size: 22px; color: #f38ba8; font-weight: bold; padding: 15px 20px; line-height: 1.6;")
        self._content_label.setAlignment(Qt.AlignCenter)
        self._content_label.setWordWrap(True)
        layout.addWidget(self._content_label)

        layout.addSpacing(10)

        btn = QPushButton("确认知悉")
        btn.setStyleSheet("""
            QPushButton { background: #f38ba8; color: #1e1e2e; font-size: 16px;
                font-weight: bold; padding: 12px 40px; border-radius: 8px; border: none; }
            QPushButton:hover { background: #eba0ac; }
        """)
        btn.clicked.connect(self.accept)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def _update_messages(self, messages):
        self._content_label.setText("\n\n".join(messages))
        self.adjustSize()


class AlertLoopThread(QThread):
    """持续音频告警线程"""
    finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.wav_path = None
        self._running = True
        self._path_lock = __import__('threading').Lock()

    def set_sound(self, wav_path):
        with self._path_lock:
            if self.wav_path and os.path.exists(self.wav_path):
                try: os.unlink(self.wav_path)
                except: pass
            self.wav_path = wav_path

    def run(self):
        import winsound
        while self._running:
            with self._path_lock:
                path = self.wav_path
            if not path or not os.path.exists(path):
                self.msleep(500)
                continue
            try:
                winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_NODEFAULT)
                self.msleep(1000)
            except:
                self.msleep(500)
        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
            if self.wav_path and os.path.exists(self.wav_path):
                os.unlink(self.wav_path)
        except:
            pass

    def stop(self):
        self._running = False
        try:
            import winsound
            winsound.PlaySound(None, winsound.SND_PURGE)
        except:
            pass
        self.wait(3000)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EPMS TSP 监控系统")
        self.setFixedSize(1300, 800)
        self.setStyleSheet(GLOBAL_STYLE)

        self.client = EPMSClient()
        self.db = Database()
        self.config = load_config()
        if self.config.get("api_base"):
            self.client.api_base = self.config["api_base"]

        # 状态数据
        self.device_data = {}
        self.last_alert_time = {}
        self.fail_counts = {}
        self.is_online = True
        self.has_over_limit = False
        self._data_changed = False  # 标记数据是否有变化，避免无意义刷新

        # 告警
        self._alert_thread = AlertLoopThread()
        self._alert_thread.start()
        self._alert_dismissed = {}
        self._active_alerts = {}

        self._init_ui()
        self._init_tray()
        self._init_timers()
        self.client.login()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(0)

        top_bar = QHBoxLayout()
        top_bar.setSpacing(0)
        title_label = QLabel("  EPMS TSP 监控系统")
        title_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #89b4fa; padding: 10px 0;")
        top_bar.addWidget(title_label)
        main_layout.addLayout(top_bar)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background: #313244; max-height: 1px;")
        main_layout.addWidget(line)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setUsesScrollButtons(False)
        self.tabs.setStyleSheet("QTabBar::tab { min-width: 130px; padding: 8px 18px; }")

        self.monitor_tab = MonitorTab(self)
        self.settings_tab = SettingsTab(self)
        self.report_tab = ReportTab(self)
        self.alert_tab = AlertTab(self)

        self.tabs.addTab(self.monitor_tab, "◈ 实时监控")
        self.tabs.addTab(self.settings_tab, "◈ 参数设置")
        self.tabs.addTab(self.report_tab, "◈ 报表导出")
        self.tabs.addTab(self.alert_tab, "◈ 告警历史")

        main_layout.addWidget(self.tabs)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("正在初始化...")

    def _init_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(self.style().SP_ComputerIcon))
        self.tray_icon.setToolTip("EPMS TSP 监控系统")
        menu = QMenu()
        menu.addAction("打开主界面", self.show)
        menu.addAction("退出", QApplication.quit)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._tray_activated)
        self.tray_icon.show()

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show()

    def _init_timers(self):
        # 数据采集定时器
        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self._check_loop)
        self.check_timer.start(self.config["check_interval"] * 1000)

        # UI刷新定时器：2秒（降低CPU占用）
        self.ui_timer = QTimer()
        self.ui_timer.timeout.connect(self._update_ui)
        self.ui_timer.start(2000)

    def _check_loop(self):
        try:
            self._do_check()
        except:
            pass

    def _do_check(self):
        any_over = False

        for device in DEVICES:
            code = device["code"]
            name = device["name"]
            threshold = self._get_threshold(code)
            no_data_timeout = self.config["no_data_timeout"]

            record = self.client.fetch_data(device)

            if record is None:
                self.fail_counts[code] = self.fail_counts.get(code, 0) + 1
                if self.fail_counts[code] >= 3:
                    old_status = self.device_data.get(code, {}).get("status")
                    self.device_data[code] = {"value": None, "data_time": "", "status": "offline"}
                    if old_status != "offline":
                        self._data_changed = True
                    self._trigger_alert(code, "fetch_fail",
                        f"设备 {name} 连续3次获取数据失败",
                        persistent=True, alert_key="offline")
                continue
            else:
                self.fail_counts[code] = 0
                self._alert_dismissed.pop(f"{code}_fetch_fail", None)

            tsp_value = record.get("TSP", 0)
            data_time = record.get("Date", "")

            try:
                self.db.insert_data(code, name, tsp_value, data_time)
            except:
                pass

            old_status = self.device_data.get(code, {}).get("status")
            new_status = "normal"

            if tsp_value is not None and tsp_value > threshold:
                any_over = True
                new_status = "over_limit"
                self._trigger_alert(code, "over_limit",
                    f"⚠️ {name} TSP超标\n当前值: {tsp_value} μg/m³\n阈值: {threshold} μg/m³",
                    persistent=True, alert_key="over_limit")
            else:
                self._alert_dismissed.pop(f"{code}_over_limit", None)

            if data_time:
                try:
                    dt = datetime.fromisoformat(data_time)
                    gap = (datetime.now() - dt).total_seconds() / 60
                    if gap > no_data_timeout:
                        new_status = "no_data"
                        self._trigger_alert(code, "no_data",
                            f"⚠️ {name} 数据中断\n最后数据: {data_time}\n已中断: {int(gap)} 分钟",
                            persistent=True, alert_key="no_data")
                    else:
                        self._alert_dismissed.pop(f"{code}_no_data", None)
                except:
                    pass

            # 仅在数据变化时标记需要刷新UI
            old_val = self.device_data.get(code, {}).get("value")
            if old_val != tsp_value or old_status != new_status:
                self._data_changed = True

            self.device_data[code] = {"value": tsp_value, "data_time": data_time, "status": new_status}

        self.has_over_limit = any_over

        any_alert = any(d.get("status") in ("over_limit", "no_data", "offline") for d in self.device_data.values())
        if not any_alert:
            self._alert_thread.set_sound(None)
            self._active_alerts.clear()
            if hasattr(self, '_current_alert_dlg') and self._current_alert_dlg:
                try: self._current_alert_dlg.close()
                except: pass
                self._current_alert_dlg = None

    def _trigger_alert(self, device_code, alert_type, message, tsp_value=None, persistent=False, alert_key=None):
        key = f"{device_code}_{alert_type}"
        cooldown = self.config.get("alert_cooldown", 60)
        now = datetime.now().timestamp()
        if key not in self.last_alert_time or (now - self.last_alert_time[key]) >= cooldown:
            self.last_alert_time[key] = now
            name = next((d["name"] for d in DEVICES if d["code"] == device_code), device_code)
            self.db.insert_alert(device_code, name, alert_type, message, tsp_value)
            self.alert_tab.refresh()

        if persistent and alert_key:
            now_ts = datetime.now().timestamp()
            last_dismiss = self._alert_dismissed.get(key, 0)
            if now_ts - last_dismiss < 60:
                return
            self._show_persistent_alert(key, message, alert_key)

    def _show_persistent_alert(self, key, message, alert_key):
        self._active_alerts[key] = message
        all_messages = list(self._active_alerts.values())
        if hasattr(self, '_current_alert_dlg') and self._current_alert_dlg:
            try:
                self._current_alert_dlg._update_messages(all_messages)
                self._current_alert_dlg.raise_()
                self._current_alert_dlg.activateWindow()
            except:
                self._do_show_alert(key, all_messages, alert_key)
        else:
            self._do_show_alert(key, all_messages, alert_key)
        sound_path = get_alert_sound(alert_key)
        if sound_path:
            self._alert_thread.set_sound(sound_path)

    def _do_show_alert(self, key, messages, alert_key):
        if hasattr(self, '_current_alert_dlg') and self._current_alert_dlg:
            try: self._current_alert_dlg.blockSignals(True)
            except: pass
        dlg = AlertDialog("EPMS 告警", messages)
        screen = QApplication.primaryScreen().geometry()
        dlg.move(screen.center() - dlg.rect().center())
        self._alert_dialog_id = getattr(self, '_alert_dialog_id', 0) + 1
        dlg_id = self._alert_dialog_id
        dlg.finished.connect(lambda checked, did=dlg_id: self._on_alert_dialog_closed(did))
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
        self._current_alert_dlg = dlg
        self._current_alert_dlg_id = dlg_id

    def _on_alert_dialog_closed(self, dlg_id):
        if dlg_id != getattr(self, '_current_alert_dlg_id', 0):
            return
        self._dismiss_all_alerts()

    def _dismiss_all_alerts(self):
        now = datetime.now().timestamp()
        for key in self._active_alerts:
            self._alert_dismissed[key] = now
        self._active_alerts.clear()
        self._alert_thread.set_sound(None)
        self._current_alert_dlg = None

    def _get_threshold(self, code):
        for d in self.config.get("devices", []):
            if d["code"] == code:
                return d.get("threshold", 400)
        return 400

    def _update_ui(self):
        # 数据无变化时只更新时钟，跳过重绘
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        interval = self.config.get("check_interval", 10)
        online_text = "● 在线" if self.is_online else "● 离线"
        self.status_bar.showMessage(f"⏱ {now_str}  |  {online_text}  |  刷新间隔: {interval}s")

        if not self._data_changed:
            return
        self._data_changed = False

        self.monitor_tab.update_data(self.device_data)

    def update_config(self, cfg):
        self.config = cfg
        save_config(cfg)
        self.check_timer.setInterval(cfg["check_interval"] * 1000)
        if "api_base" in cfg:
            self.client.api_base = cfg["api_base"]

    def closeEvent(self, event):
        self._alert_thread.stop()
        event.ignore()
        self.hide()
        self.tray_icon.showMessage("EPMS TSP 监控", "程序已最小化到系统托盘", QSystemTrayIcon.Information, 2000)

    def resizeEvent(self, event):
        try:
            super().resizeEvent(event)
            QTimer.singleShot(100, self._safe_update_chart)
        except:
            pass

    def _safe_update_chart(self):
        try:
            if hasattr(self, 'monitor_tab'):
                self.monitor_tab._update_chart()
        except:
            pass
