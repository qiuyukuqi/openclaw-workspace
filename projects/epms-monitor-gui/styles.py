# -*- coding: utf-8 -*-
"""全局样式（Catppuccin Mocha，大字体版）"""

GLOBAL_STYLE = """
    /* 全局基础 */
    QWidget {
        font-family: "Microsoft YaHei UI", "微软雅黑", "Segoe UI", sans-serif;
        font-size: 15px;
        color: #cdd6f4;
    }
    QMainWindow {
        background: #1e1e2e;
    }

    /* Tab栏 */
    QTabWidget::pane {
        border: 1px solid #313244;
        background: #1e1e2e;
        border-radius: 6px;
    }
    QTabBar::tab {
        background: #313244;
        color: #a6adc8;
        padding: 12px 36px;
        margin-right: 2px;
        border-top-left-radius: 8px;
        border-top-right-radius: 8px;
        font-size: 16px;
        font-weight: bold;
    }
    QTabBar::tab:selected {
        background: #45475a;
        color: #cdd6f4;
    }
    QTabBar::tab:hover:!selected {
        background: #3d3e50;
    }

    /* 分组框 */
    QGroupBox {
        font-size: 16px;
        font-weight: bold;
        color: #bac2de;
        border: 1px solid #313244;
        border-radius: 8px;
        margin-top: 16px;
        padding: 20px 16px 16px 16px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 4px 14px;
    }

    /* 表格 */
    QTableWidget {
        background: #1e1e2e;
        gridline-color: #313244;
        border: 1px solid #313244;
        border-radius: 6px;
        selection-background-color: #3d3e50;
        selection-color: #cdd6f4;
        alternate-background-color: #232336;
        font-size: 14px;
    }
    QTableWidget::item {
        padding: 8px 12px;
        min-height: 32px;
    }
    QTableWidget::item:selected {
        background-color: #3d3e50;
        color: #cdd6f4;
    }
    QHeaderView::section {
        background: #313244;
        color: #bac2de;
        padding: 10px 14px;
        border: none;
        border-bottom: 2px solid #45475a;
        font-size: 15px;
        font-weight: bold;
    }

    /* 按钮 */
    QPushButton {
        background: #45475a;
        color: #cdd6f4;
        border: none;
        padding: 10px 28px;
        border-radius: 6px;
        font-size: 15px;
        font-weight: bold;
    }
    QPushButton:hover {
        background: #585b70;
    }
    QPushButton:pressed {
        background: #6c7086;
    }

    /* 输入框 */
    QLineEdit, QSpinBox, QDoubleSpinBox {
        background: #313244;
        color: #cdd6f4;
        border: 1px solid #45475a;
        border-radius: 4px;
        padding: 8px 12px;
        font-size: 15px;
        min-height: 28px;
    }
    QLineEdit:focus, QSpinBox:focus {
        border-color: #89b4fa;
    }

    /* 下拉框 */
    QComboBox {
        background: #313244;
        color: #cdd6f4;
        border: 1px solid #45475a;
        border-radius: 4px;
        padding: 8px 12px;
        font-size: 15px;
        min-height: 28px;
    }
    QComboBox::drop-down {
        border: none;
        width: 30px;
    }
    QComboBox QAbstractItemView {
        background: #313244;
        color: #cdd6f4;
        selection-background-color: #3d3e50;
        selection-color: #cdd6f4;
        font-size: 14px;
    }

    /* 日期选择 */
    QDateEdit {
        background: #313244;
        color: #cdd6f4;
        border: 1px solid #45475a;
        border-radius: 4px;
        padding: 8px 12px;
        font-size: 15px;
        min-height: 28px;
    }

    /* 滑块 */
    QSlider::groove:horizontal {
        height: 8px;
        background: #313244;
        border-radius: 4px;
    }
    QSlider::handle:horizontal {
        width: 22px;
        height: 22px;
        background: #89b4fa;
        border-radius: 11px;
        margin: -7px 0;
    }
    QSlider::sub-page:horizontal {
        background: #89b4fa;
        border-radius: 4px;
    }

    /* 单选按钮 */
    QRadioButton {
        font-size: 15px;
        spacing: 10px;
    }
    QRadioButton::indicator {
        width: 18px;
        height: 18px;
    }

    /* 复选框 */
    QCheckBox {
        font-size: 15px;
        spacing: 10px;
    }
    QCheckBox::indicator {
        width: 18px;
        height: 18px;
    }

    /* 滚动条 */
    QScrollBar:vertical {
        background: #1e1e2e;
        width: 12px;
        border-radius: 6px;
    }
    QScrollBar::handle:vertical {
        background: #45475a;
        border-radius: 6px;
        min-height: 36px;
    }
    QScrollBar::handle:vertical:hover {
        background: #585b70;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }

    /* 标签 */
    QLabel {
        font-size: 15px;
    }

    /* 状态栏 */
    QStatusBar {
        background: #181825;
        color: #a6adc8;
        font-size: 14px;
        padding: 4px 8px;
    }
"""
