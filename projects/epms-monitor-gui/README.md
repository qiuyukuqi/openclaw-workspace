# EPMS TSP 监控桌面软件

双设备TSP实时监控、语音告警、报表导出桌面应用

## 功能

- 📊 实时监控：设备卡片 + 趋势曲线 + 分钟数据表格
- ⚙️ 参数设置：TSP报警阈值、检查间隔等
- 📋 报表导出：时间范围筛选 + Excel/CSV导出
- 📜 告警历史：告警记录查询 + 导出
- 🔔 语音告警：Windows SAPI TTS语音播报
- 💻 系统托盘：最小化后台运行

## 开发环境运行

```bash
pip install -r requirements.txt
python main.py
```

## 打包为 Windows exe

在 Windows 环境下：

```bash
pip install pyinstaller
pyinstaller --onefile --name "EPMS-TSP监控" --windowed main.py
```

产物：`dist/EPMS-TSP监控.exe`

## 文件说明

| 文件 | 说明 |
|------|------|
| main.py | 入口文件 |
| main_window.py | 主窗口 + 数据采集 + 告警逻辑 |
| config.py | 设备和API配置 |
| epms_client.py | EPMS平台API通信 |
| database.py | SQLite本地数据存储 |
| voice_alert.py | 语音告警（pyttsx3） |
| settings.py | 配置文件读写 |
| tabs/monitor_tab.py | 实时监控页面 |
| tabs/settings_tab.py | 参数设置页面 |
| tabs/report_tab.py | 报表导出页面 |
| tabs/alert_tab.py | 告警历史页面 |
| config.json | 运行时配置（自动生成） |
| data.db | 历史数据（自动生成） |
