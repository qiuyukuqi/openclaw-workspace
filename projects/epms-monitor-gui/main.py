#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EPMS TSP 监控桌面软件
双设备TSP实时监控、告警、报表导出
"""

import sys
import os

os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt

from main_window import MainWindow
import resources_rc

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setQuitOnLastWindowClosed(False)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
