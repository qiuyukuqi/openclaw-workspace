"""飞书通知模块 - 通过打印标记通知，由外部脚本捕获处理"""
import os
from config import TEMP_DIR


def notify(message: str, screenshot_path: str = None):
    """打印飞书通知标记，外部脚本可捕获这些标记发送通知
    
    Args:
        message: 通知消息文本
        screenshot_path: 可选的截图路径，会附带在通知中
    """
    if screenshot_path:
        tag = f"[FEISHU_NOTIFY] {message} 截图: {screenshot_path}"
    else:
        tag = f"[FEISHU_NOTIFY] {message}"
    print(tag)


def notify_success(platform: str, title: str, screenshot_path: str = None):
    """发布成功通知"""
    notify(f"✅ {platform} 发布成功: {title}", screenshot_path)


def notify_failure(platform: str, error: str, screenshot_path: str = None):
    """发布失败通知"""
    notify(f"❌ {platform} 发布失败: {error}", screenshot_path)


def notify_info(message: str):
    """信息通知"""
    notify(f"ℹ️ {message}")
