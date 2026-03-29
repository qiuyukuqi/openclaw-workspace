#!/usr/bin/env python3
"""
邮件日报生成脚本
每天生成前一天的邮件统计报告
"""

import os
import sys
import json
import email
import imaplib
import ssl
import subprocess
from email.header import decode_header, make_header
from datetime import datetime, timedelta
from pathlib import Path

# 配置文件路径
CONFIG_DIR = Path(__file__).parent.parent / "data"

# 飞书配置
FEISHU_ACCOUNT = "main"
FEISHU_USER_ID = "ou_c5c98e2002a34a9b10f15fd0b6463d06"


def load_env():
    """从 .env.email 文件加载环境变量"""
    env_paths = [
        Path(__file__).parent.parent.parent.parent / ".env.email",
        Path.home() / ".openclaw" / "workspace" / ".env.email",
    ]
    
    for env_path in env_paths:
        if env_path.exists():
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        key, value = line.split("=", 1)
                        os.environ.setdefault(key, value)
            return True
    return False


def get_config():
    """获取邮箱配置"""
    return {
        "imap_server": os.environ.get("EMAIL_IMAP_SERVER"),
        "imap_port": int(os.environ.get("EMAIL_IMAP_PORT", 993)),
        "user": os.environ.get("EMAIL_USER"),
        "password": os.environ.get("EMAIL_PASSWORD"),
    }


def decode_str(s):
    """解码邮件头字符串"""
    if s is None:
        return ""
    
    try:
        decoded = str(make_header(decode_header(s)))
        return decoded
    except Exception:
        pass
    
    try:
        decoded_parts = decode_header(s)
        result = []
        for part, charset in decoded_parts:
            if isinstance(part, bytes):
                result.append(part.decode(charset or "utf-8", errors="replace"))
            else:
                result.append(part)
        return "".join(result)
    except Exception:
        return s if isinstance(s, str) else str(s)


def get_yesterday_emails(config):
    """获取昨天的所有邮件"""
    import socket
    
    # 带重试的IMAP连接
    mail = None
    for attempt in range(3):
        try:
            socket.setdefaulttimeout(15)
            ssl_context = ssl.create_default_context()
            mail = imaplib.IMAP4_SSL(config["imap_server"], config["imap_port"], ssl_context=ssl_context)
            mail.login(config["user"], config["password"])
            mail.select("INBOX")
            break
        except Exception as e:
            if mail:
                try: mail.logout()
                except: pass
            if attempt < 2:
                import time; time.sleep(3)
            else:
                raise e
    
    try:
        
        # 计算昨天的日期范围
        yesterday = datetime.now() - timedelta(days=1)
        date_str = yesterday.strftime("%d-%b-%Y")
        
        # 搜索昨天的邮件
        status, messages = mail.search(None, f'ON "{date_str}"')
        
        if status != "OK":
            mail.logout()
            return []
        
        email_ids = messages[0].split()
        emails = []
        
        # 从最新的邮件开始获取（倒序）
        for email_id in reversed(email_ids):
            status, msg_data = mail.fetch(email_id, "(BODY[HEADER.FIELDS (FROM SUBJECT DATE)])")
            if status != "OK":
                continue
            
            raw = msg_data[0][1]
            if isinstance(raw, bytes):
                raw = raw.decode(errors='replace')
            msg = email.message_from_string('From: a@b.com\n' + raw if 'From:' not in raw else raw)
            
            subject = decode_str(msg.get("Subject", ""))
            from_addr = decode_str(msg.get("From", ""))
            date = msg.get("Date", "")
            
            emails.append({
                "subject": subject,
                "from": from_addr,
                "date": date
            })
        
        mail.logout()
        return emails
        
    except Exception as e:
        print(f"获取邮件失败: {e}", file=sys.stderr)
        return []


def generate_report(emails):
    """生成邮件日报"""
    yesterday = datetime.now() - timedelta(days=1)
    date_str = yesterday.strftime("%Y年%m月%d日")
    
    report = f"📊 邮件统计概览\n\n"
    report += f"📅 {date_str}\n"
    report += f"📥 昨日共计收到 {len(emails)} 封邮件\n\n"
    
    if emails:
        report += "邮件列表（从最新到最旧）：\n"
        report += "─" * 20 + "\n"
        for i, em in enumerate(emails, 1):
            # 截取过长的标题
            subject = em["subject"][:50] + "..." if len(em["subject"]) > 50 else em["subject"]
            report += f"{i}. {subject}\n"
            # 显示发件人（去掉尖括号中的邮箱地址）
            from_name = em["from"].split("<")[0].strip().strip('"')
            if from_name:
                report += f"   📧 {from_name}\n"
    else:
        report += "📭 昨日没有收到邮件\n"
    
    return report


def notify_feishu(message):
    """推送到飞书"""
    try:
        result = subprocess.run(
            [
                "openclaw", "message", "send",
                "--channel", "feishu",
                "--account", FEISHU_ACCOUNT,
                "-t", f"user:{FEISHU_USER_ID}",
                "-m", message
            ],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            print(f"飞书推送失败: {result.stderr}", file=sys.stderr)
            return False
        print(f"飞书推送成功", file=sys.stderr)
        return True
    except Exception as e:
        print(f"飞书推送失败: {e}", file=sys.stderr)
        return False


def main():
    """主函数"""
    # 使用文件锁防止多个实例同时运行
    import fcntl
    lock_file = CONFIG_DIR / "report.lock"
    lock_fd = open(lock_file, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        print("另一个日报实例正在运行，跳过", file=sys.stderr)
        return
    
    try:
        if not load_env():
            print("错误: 无法加载邮箱配置", file=sys.stderr)
            return
        
        config = get_config()
        
        if not all([config["imap_server"], config["user"], config["password"]]):
            print("错误: 邮箱配置不完整", file=sys.stderr)
            return
        
        print("生成邮件日报...", file=sys.stderr)
        
        # 获取昨天的邮件
        emails = get_yesterday_emails(config)
        print(f"获取到 {len(emails)} 封邮件", file=sys.stderr)
        
        # 生成报告
        report = generate_report(emails)
        print("报告内容:", file=sys.stderr)
        print(report, file=sys.stderr)
        
        # 推送到飞书
        if notify_feishu(report):
            print("日报发送成功", file=sys.stderr)
        else:
            print("日报发送失败", file=sys.stderr)
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


if __name__ == "__main__":
    main()
